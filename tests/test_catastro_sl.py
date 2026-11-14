"""Tests sin internet del conector CATASTRO_SL (spec 025): el visor APEX y el GeoServer del Catastro están simulados."""

import asyncio

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rotaterra.fuentes import catastro_sl
from rotaterra.geo import validar_poligono

SERVIDOR = "http://mapa.catastro.prueba"
VISOR_HTML = f"""<form action="wwv_flow.accept">
<input type="hidden" name="p_instance" value="9564563888057" id="pInstance" />
<input type="hidden" name="p_t01" id="P1_CATGIS_VISUALIZADOR_URL"
 value="http:&#x2F;&#x2F;mapa.catastro.prueba&#x2F;mapsPortlet&#x2F;?TOKEN=ABC123"></form>"""


def caja(oeste, sur, este, norte) -> list:
    return [[[oeste, sur], [este, sur], [este, norte], [oeste, norte], [oeste, sur]]]


def parcela(fid, nomenclatura, partida, numero, sup_m2, anillos, tipo="RURAL", multi=False) -> dict:
    ficha = (f" Parcela: {numero} \\n Nom.Catastral: {nomenclatura} \\n Nom.Tributaria: {partida} \\n "
             f"Sup. Terreno: {sup_m2} m2 \\n Tipo Parcela: {tipo} \\n Plano Mensura: 03-234-2020")
    geometria = {"type": "MultiPolygon", "coordinates": anillos} if multi else {"type": "Polygon",
                                                                                 "coordinates": anillos}
    return {"type": "Feature", "id": f"GIS_PARCELAS_RUR_VV.{fid}", "geometry": geometria,
            "properties": {"ETIQUETA": str(numero), "NOMBRE": ficha, "LINK": "http://...", "CATNMC_TRI": partida,
                           "CATNMC_CAT": nomenclatura, "CATMEN_CODIGO": "03-234-2020"}}


# lote de 0,01° × 0,01° alrededor de (-33,700; -65,300): ~102,9 ha
LOTE = parcela(1, "E5-03-01-00-000000-003565", "01-1064404", "3565", 1_028_650,
               caja(-65.305, -33.705, -65.295, -33.695))
VECINA = parcela(2, "00-03-28-00-000000-000895", "01-95692", "895", 4_000_000, caja(-65.295, -33.705, -65.285, -33.695))


@pytest.fixture(autouse=True)
def sesion_nueva():
    catastro_sl._sesion.update(servidor=None, hasta=0.0)
    catastro_sl._mapa.update(gz=None, cantidad=0, hasta=0.0)


def simulado(capas: dict, pedidos: list | None = None, visor: int | str = VISOR_HTML) -> httpx.AsyncClient:
    """capas: nombre de capa -> lista de features, o un código HTTP de error. Resuelve bbox y CQL igual que GeoServer."""
    from shapely.geometry import box, shape

    def responder(pedido: httpx.Request) -> httpx.Response:
        if pedidos is not None:
            pedidos.append(pedido)
        if "sistemacatastro" in pedido.url.host:
            if isinstance(visor, int):
                return httpx.Response(visor, text="caído")
            return httpx.Response(200, text=visor, headers={"content-type": "text/html"})
        assert str(pedido.url).startswith(f"{SERVIDOR}/geoserver/wfs")
        params = pedido.url.params
        assert params["srsName"] == "EPSG:4326"
        respuesta = capas.get(params["typeName"], [])
        if isinstance(respuesta, int):
            return httpx.Response(respuesta, text="error")
        if "bbox" in params:
            *numeros, crs = params["bbox"].split(",")
            assert crs == "EPSG:4326"
            zona = box(*map(float, numeros))
            elegidas = [f for f in respuesta if shape(f["geometry"]).intersects(zona)]
        elif "CQL_FILTER" in params:
            campo, valor = params["CQL_FILTER"].split("=")
            elegidas = [f for f in respuesta if f["properties"][campo] == valor.strip("'")]
        else:
            elegidas = list(respuesta)
        if "maxFeatures" in params:
            elegidas = elegidas[:int(params["maxFeatures"])]
        return httpx.Response(200, json={"type": "FeatureCollection", "features": elegidas},
                              headers={"content-type": "application/json;charset=UTF-8"})

    return httpx.AsyncClient(transport=httpx.MockTransport(responder))


def correr(coro):
    return asyncio.run(coro)


RURALES = "SanLuis:GIS_PARCELAS_RUR_VV"


def test_punto_dentro_de_una_parcela():
    pedidos = []
    p = correr(catastro_sl.parcela_en_punto(-33.700, -65.300, simulado({RURALES: [LOTE, VECINA]}, pedidos)))
    assert p.nomenclatura_catastral == "E5-03-01-00-000000-003565"
    assert p.partida_inmobiliaria == "01-1064404"
    assert p.numero_parcela == "3565"
    assert p.tipo_parcela == "RURAL"
    assert p.plano_mensura == "03-234-2020"
    assert p.superficie_registrada_m2 == 1_028_650
    assert p.superficie_calculada_m2 == pytest.approx(1_028_650, rel=0.01)
    assert p.calidad == "buena"
    assert p.capa == RURALES
    validar_poligono(p.geometria_lote)  # sirve directo para recortar satélites
    assert "sesión APEX nueva" in p.nota


def test_la_sesion_apex_se_lee_del_visor_y_nunca_es_fija():
    pedidos = []
    correr(catastro_sl.parcela_en_punto(-33.700, -65.300, simulado({RURALES: [LOTE]}, pedidos)))
    assert pedidos[0].url.host == "www.sistemacatastro.sanluis.gov.ar"
    assert pedidos[0].url.params["p"] == "VISPUB:1"  # sin Session ID: APEX asigna uno nuevo
    assert all(p.url.host == "mapa.catastro.prueba" for p in pedidos[1:])  # el servidor sale del visor
    assert len(pedidos) == 1 + len(catastro_sl.CAPAS)


def test_si_el_visor_no_responde_se_usa_el_servidor_conocido(monkeypatch):
    monkeypatch.setattr(catastro_sl, "SERVIDOR_CONOCIDO", SERVIDOR)
    p = correr(catastro_sl.parcela_en_punto(-33.700, -65.300, simulado({RURALES: [LOTE]}, visor=503)))
    assert p.nomenclatura_catastral == "E5-03-01-00-000000-003565"
    assert "servidor conocido" in p.nota


def test_visor_cambiado_tambien_cae_al_servidor_conocido(monkeypatch):
    monkeypatch.setattr(catastro_sl, "SERVIDOR_CONOCIDO", SERVIDOR)
    p = correr(catastro_sl.parcela_en_punto(-33.700, -65.300, simulado({RURALES: [LOTE]}, visor="<html></html>")))
    assert p.calidad == "buena"
    assert "servidor conocido" in p.nota


def test_punto_en_un_camino_no_inventa_nada():
    p = correr(catastro_sl.parcela_en_punto(-33.700, -65.2949, simulado({RURALES: [parcela(
        1, "X", "Y", "1", 100, caja(-65.305, -33.705, -65.2950, -33.695))]})))
    assert p.calidad == "descartada"
    assert p.nomenclatura_catastral is None and p.geometria_lote is None and p.superficie_registrada_m2 is None
    assert "no cae dentro de ninguna parcela" in p.nota
    assert "1 parcelas a menos" in p.nota


def test_superficie_muy_distinta_queda_dudosa():
    mal = parcela(1, "E5-1", "01-1", "1", 500_000, caja(-65.305, -33.705, -65.295, -33.695))
    p = correr(catastro_sl.parcela_en_punto(-33.700, -65.300, simulado({RURALES: [mal]})))
    assert p.calidad == "dudosa"
    assert "SUPUESTO" in p.nota


def test_parcela_en_varias_partes_devuelve_la_mayor_para_recortar():
    multi = parcela(1, "E5-2", "01-2", "2", 1_028_650 + 10_000, [caja(-65.305, -33.705, -65.295, -33.695),
                                                              caja(-65.31, -33.71, -65.309, -33.709)], multi=True)
    p = correr(catastro_sl.parcela_en_punto(-33.700, -65.300, simulado({RURALES: [multi]})))
    assert p.geometria_parcela["type"] == "MultiPolygon"
    assert p.geometria_lote["type"] == "Polygon"
    assert p.geometria_lote["coordinates"][0][0] == [-65.305, -33.705]
    assert p.calidad == "dudosa" and "2 partes" in p.nota


def test_parcelas_superpuestas_elige_la_mas_chica():
    grande = parcela(9, "GRANDE", "01-9", "9", 4 * 1_028_650, caja(-65.31, -33.71, -65.29, -33.69))
    p = correr(catastro_sl.parcela_en_punto(-33.700, -65.300, simulado({RURALES: [grande, LOTE]})))
    assert p.nomenclatura_catastral == "E5-03-01-00-000000-003565"
    assert p.calidad == "dudosa" and "GRANDE" in p.nota


def test_parcela_urbana_sale_de_su_capa():
    urbana = parcela(3, "01-01-01-01-000001-000001", "01-3", "1", 1_028_650, caja(-65.305, -33.705, -65.295, -33.695),
                     tipo="URBANA")
    p = correr(catastro_sl.parcela_en_punto(-33.700, -65.300, simulado({"SanLuis:GIS_PARCELAS_URB_VV": [urbana]})))
    assert p.tipo_parcela == "URBANA"
    assert p.capa == "SanLuis:GIS_PARCELAS_URB_VV"


def test_busqueda_por_nomenclatura_y_por_partida():
    capas = {RURALES: [LOTE, VECINA]}
    p = correr(catastro_sl.parcela_por_nomenclatura("e5-03-01-00-000000-003565 ", simulado(capas)))
    assert p.partida_inmobiliaria == "01-1064404" and p.calidad == "buena"
    p = correr(catastro_sl.parcela_por_partida("01-95692", simulado(capas)))
    assert p.nomenclatura_catastral == "00-03-28-00-000000-000895"


def test_codigo_inexistente_no_inventa_nada():
    p = correr(catastro_sl.parcela_por_nomenclatura("00-00-00-00-000000-000000", simulado({RURALES: [LOTE]})))
    assert p.calidad == "descartada" and p.geometria_lote is None
    assert "ninguna parcela" in p.nota


def test_codigo_con_comillas_se_rechaza_sin_consultar():
    pedidos = []
    with pytest.raises(ValueError):
        correr(catastro_sl.parcela_por_nomenclatura("x' OR 1=1 --", simulado({}, pedidos)))
    assert pedidos == []


def test_geoserver_caido_es_error_del_catastro():
    with pytest.raises(catastro_sl.ErrorCatastro):
        correr(catastro_sl.parcela_en_punto(-33.700, -65.300, simulado({RURALES: 503})))


def test_coordenadas_fuera_de_rango():
    with pytest.raises(ValueError):
        correr(catastro_sl.parcela_en_punto(-65.3, -333.7, simulado({})))


def test_leer_ficha_con_saltos_reales_o_escapados():
    assert catastro_sl.leer_ficha(" Parcela: 1 \\n Sup. Terreno: 10.5 m2")["sup. terreno"] == "10.5 m2"
    assert catastro_sl.leer_ficha(" Parcela: 1 \n Tipo Parcela: RURAL")["tipo parcela"] == "RURAL"


def test_endpoint(monkeypatch):
    async def falso_punto(lat, lon):
        return catastro_sl.sin_parcela(f"punto {lat} {lon}")

    async def falso_codigo(codigo):
        if "'" in codigo:
            raise ValueError("Código inválido")
        raise catastro_sl.ErrorCatastro("caído")

    monkeypatch.setattr(catastro_sl, "parcela_en_punto", falso_punto)
    monkeypatch.setattr(catastro_sl, "parcela_por_nomenclatura", falso_codigo)
    app = FastAPI()
    app.include_router(catastro_sl.router)
    cliente = TestClient(app)
    r = cliente.get("/catastro-sl/parcela", params={"lat": -33.7, "lon": -65.3})
    assert r.status_code == 200 and r.json()["calidad"] == "descartada" and r.json()["fuente"] == "Catastro San Luis"
    assert cliente.get("/catastro-sl/parcela", params={"nomenclatura": "A-1"}).status_code == 502
    assert cliente.get("/catastro-sl/parcela", params={"nomenclatura": "a'"}).status_code == 422
    assert cliente.get("/catastro-sl/parcela").status_code == 422


# ---------- mapa de parcelas rurales ----------

def test_mapa_completo_de_parcelas_rurales():
    datos = correr(catastro_sl.parcelas_rurales(cliente=simulado({RURALES: [LOTE, VECINA]})))
    assert datos["type"] == "FeatureCollection" and datos["crs"] == "EPSG:4326"
    assert datos["cantidad"] == 2 and datos["truncado"] is False
    primera = datos["features"][0]
    assert primera["id"] == "E5-03-01-00-000000-003565"
    assert primera["properties"] == {"nomenclatura_catastral": "E5-03-01-00-000000-003565",
                                     "partida_inmobiliaria": "01-1064404", "numero_parcela": "3565",
                                     "tipo_parcela": "RURAL", "plano_mensura": "03-234-2020",
                                     "superficie_registrada_m2": 1_028_650, "geometria_reparada": False}
    assert primera["geometry"]["coordinates"][0][0] == [-65.305, -33.705]


def test_coordenadas_redondeadas_a_6_decimales():
    fina = parcela(5, "F", "01-5", "5", 1, caja(-65.30512345678, -33.705, -65.295, -33.695))
    datos = correr(catastro_sl.parcelas_rurales(cliente=simulado({RURALES: [fina]})))
    assert datos["features"][0]["geometry"]["coordinates"][0][0] == [-65.305123, -33.705]


def test_mapa_por_zona_y_recorte_si_hay_demasiadas(monkeypatch):
    monkeypatch.setattr(catastro_sl, "MAX_EN_ZONA", 1)
    pedidos = []
    datos = correr(catastro_sl.parcelas_rurales((-65.31, -33.71, -65.28, -33.69), simulado({RURALES: [LOTE, VECINA]},
                                                                                            pedidos)))
    assert pedidos[-1].url.params["bbox"] == "-65.31,-33.71,-65.28,-33.69,EPSG:4326"
    assert pedidos[-1].url.params["maxFeatures"] == "2"
    assert datos["cantidad"] == 1 and datos["truncado"] is True and "acercá el mapa" in datos["nota"]


def test_zona_sin_parcelas_no_inventa_nada():
    datos = correr(catastro_sl.parcelas_rurales((-60.66, -33.97, -60.64, -33.95), simulado({RURALES: [LOTE]})))
    assert datos["cantidad"] == 0 and datos["features"] == [] and "No hay parcelas" in datos["nota"]


def test_caja_invertida_se_rechaza():
    with pytest.raises(ValueError):
        correr(catastro_sl.parcelas_rurales((-65.28, -33.71, -65.31, -33.69), simulado({})))


def test_endpoint_del_mapa_completo_comprimido_y_guardado(monkeypatch):
    import gzip
    import json

    llamadas = []

    async def falso(caja=None, cliente=None):
        llamadas.append(caja)
        return catastro_sl.coleccion([LOTE, VECINA], "prueba")

    monkeypatch.setattr(catastro_sl, "parcelas_rurales", falso)
    app = FastAPI()
    app.include_router(catastro_sl.router)
    cliente = TestClient(app)
    r = cliente.get("/catastro-sl/parcelas-rurales")
    assert r.status_code == 200 and r.headers["content-type"] == "application/geo+json"
    assert r.headers["x-cantidad-parcelas"] == "2" and r.json()["cantidad"] == 2
    crudo = cliente.get("/catastro-sl/parcelas-rurales", headers={"Accept-Encoding": "identity"})
    assert json.loads(crudo.content)["features"][1]["id"] == "00-03-28-00-000000-000895"
    assert llamadas == [None]  # la segunda vez sale de memoria
    assert gzip.decompress(catastro_sl._mapa["gz"])
    zona = cliente.get("/catastro-sl/parcelas-rurales", params={"oeste": -65.31, "sur": -33.71, "este": -65.28,
                                                               "norte": -33.69})
    assert zona.status_code == 200 and llamadas[-1] == (-65.31, -33.71, -65.28, -33.69)
    assert cliente.get("/catastro-sl/parcelas-rurales", params={"oeste": -65.31}).status_code == 422


def test_mapa_reintenta_una_vez_si_el_catastro_rechaza(monkeypatch):
    monkeypatch.setattr(catastro_sl, "ESPERA_REINTENTO", 0)
    respuestas = iter([403, None])
    base = simulado({RURALES: [LOTE]})

    def responder(pedido):
        if "sistemacatastro" in pedido.url.host:
            return httpx.Response(200, text=VISOR_HTML)
        codigo = next(respuestas)
        if codigo:
            return httpx.Response(codigo, text="prohibido")
        return httpx.Response(200, json={"type": "FeatureCollection", "features": [LOTE]},
                              headers={"content-type": "application/json"})

    datos = correr(catastro_sl.parcelas_rurales(cliente=httpx.AsyncClient(transport=httpx.MockTransport(responder))))
    assert datos["cantidad"] == 1
    correr(base.aclose())

    siempre = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda p: httpx.Response(200, text=VISOR_HTML) if "sistemacatastro" in p.url.host else httpx.Response(403)))
    with pytest.raises(catastro_sl.ErrorCatastro):
        correr(catastro_sl.parcelas_rurales(cliente=siempre))


# parcela 2160 (B5-06-43-00-000000-002160) viene del Catastro con el borde cruzado sobre sí mismo
CRUZADA = parcela(3, "B5-06-43-00-000000-002160", "13-968774", "2160", 1_028_650,
                  [[[-65.305, -33.705], [-65.295, -33.705], [-65.295, -33.695], [-65.300, -33.695],
                    [-65.300, -33.705], [-65.300, -33.700], [-65.305, -33.695], [-65.305, -33.705]]])


def test_un_poligono_cruzado_se_repara_y_queda_dudoso():
    from rotaterra.geo import validar_poligono
    from shapely.geometry import shape

    assert not shape(CRUZADA["geometry"]).is_valid
    resultado = catastro_sl.armar(catastro_sl.CAPAS["RURAL"], CRUZADA, "prueba")
    validar_poligono(resultado.geometria_lote)  # /consulta lo acepta
    assert resultado.calidad == "dudosa"
    assert "se cruza a sí mismo" in resultado.nota
    assert shape(resultado.geometria_parcela).is_valid


def test_el_mapa_entrega_poligonos_validos_y_avisa_cuales_se_repararon():
    from shapely.geometry import shape

    mapa = catastro_sl.coleccion([LOTE, CRUZADA], "prueba")
    assert all(shape(f["geometry"]).is_valid for f in mapa["features"])
    assert [f["properties"]["geometria_reparada"] for f in mapa["features"]] == [False, True]
    assert "1 parcela(s)" in mapa["nota"]


# ---------- copia del mapa para cuando el Catastro no contesta (spec 045) ----------

import gzip  # noqa: E402
import json  # noqa: E402

import actualizar_copia_catastro  # noqa: E402

CAIDO = catastro_sl.ErrorCatastro("El Catastro de San Luis no respondió: ConnectTimeout: timed out")


@pytest.fixture(autouse=True)
def copia_de_prueba(tmp_path, monkeypatch):
    """Una copia chica con LOTE y VECINA, armada con la misma herramienta que arma la copia real."""
    datos = catastro_sl.coleccion([LOTE, VECINA], "prueba")
    datos["fecha_consulta"] = "2026-10-05"
    actualizar_copia_catastro.guardar_copia(datos, tmp_path)
    monkeypatch.setattr(catastro_sl, "COPIA", tmp_path / catastro_sl.COPIA.name)
    monkeypatch.setattr(catastro_sl, "COPIA_INFO", tmp_path / catastro_sl.COPIA_INFO.name)
    return tmp_path


@pytest.fixture
def catastro_caido(monkeypatch):
    def no_contesta(pedido):
        raise httpx.ConnectTimeout("timed out")

    async def mapa_caido(caja=None, cliente=None):
        raise CAIDO

    monkeypatch.setattr(catastro_sl, "_cliente", lambda: httpx.AsyncClient(transport=httpx.MockTransport(no_contesta)))
    monkeypatch.setattr(catastro_sl, "parcelas_rurales", mapa_caido)
    app = FastAPI()
    app.include_router(catastro_sl.router)
    return TestClient(app)


def test_con_el_catastro_caido_la_parcela_por_punto_sale_de_la_copia(catastro_caido):
    r = catastro_caido.get("/catastro-sl/parcela", params={"lat": -33.70, "lon": -65.30})
    assert r.status_code == 200 and r.headers["x-copia-del-catastro"] == "2026-10-05"
    p = r.json()
    assert p["nomenclatura_catastral"] == "E5-03-01-00-000000-003565" and p["partida_inmobiliaria"] == "01-1064404"
    assert p["numero_parcela"] == "3565" and p["plano_mensura"] == "03-234-2020" and p["tipo_parcela"] == "RURAL"
    assert p["superficie_registrada_m2"] == 1_028_650 and p["calidad"] == "buena"
    assert p["fecha_consulta"] == "2026-10-05"
    assert p["nota"].startswith("El Catastro de San Luis no respondió: ConnectTimeout")
    assert "Se usó la copia del mapa de parcelas rurales guardada en el repo el 2026-10-05" in p["nota"]
    validar_poligono(p["geometria_lote"])


def test_con_el_catastro_caido_la_parcela_por_partida_y_nomenclatura_sale_de_la_copia(catastro_caido):
    por_partida = catastro_caido.get("/catastro-sl/parcela", params={"partida": "01-95692"})
    assert por_partida.status_code == 200 and por_partida.json()["nomenclatura_catastral"] == VECINA["properties"][
        "CATNMC_CAT"]
    por_nomenclatura = catastro_caido.get("/catastro-sl/parcela", params={"nomenclatura": "e5-03-01-00-000000-003565"})
    assert por_nomenclatura.status_code == 200 and por_nomenclatura.json()["partida_inmobiliaria"] == "01-1064404"
    assert por_nomenclatura.headers["x-copia-del-catastro"] == "2026-10-05"


def test_lo_que_no_esta_en_la_copia_sigue_siendo_error_con_los_dos_motivos(catastro_caido):
    r = catastro_caido.get("/catastro-sl/parcela", params={"partida": "01-1"})
    assert r.status_code == 502
    assert "no respondió" in r.json()["detail"] and "Tampoco está en la copia del 2026-10-05" in r.json()["detail"]
    lejos = catastro_caido.get("/catastro-sl/parcela", params={"lat": -33.0, "lon": -66.0})
    assert lejos.status_code == 502 and "no cae en ninguna" in lejos.json()["detail"]
    assert catastro_caido.get("/catastro-sl/parcela", params={"partida": "a'"}).status_code == 422


def test_con_el_catastro_caido_el_mapa_completo_sale_de_la_copia(catastro_caido):
    r = catastro_caido.get("/catastro-sl/parcelas-rurales")
    assert r.status_code == 200 and r.headers["x-copia-del-catastro"] == "2026-10-05"
    assert r.headers["x-cantidad-parcelas"] == "2" and r.headers["cache-control"] == "no-store"
    datos = r.json()
    assert datos["cantidad"] == 2 and datos["fecha_consulta"] == "2026-10-05"
    assert datos["nota"].startswith("Copia del mapa de parcelas rurales guardada en el repo el 2026-10-05")
    assert catastro_sl._mapa["gz"] is None  # la copia no queda en memoria: la próxima vez se prueba el Catastro


def test_con_el_catastro_caido_una_zona_sale_de_la_copia(catastro_caido, monkeypatch):
    r = catastro_caido.get("/catastro-sl/parcelas-rurales",
                           params={"oeste": -65.31, "sur": -33.71, "este": -65.299, "norte": -33.69})
    assert r.status_code == 200 and r.headers["x-copia-del-catastro"] == "2026-10-05"
    datos = r.json()
    assert [f["id"] for f in datos["features"]] == ["E5-03-01-00-000000-003565"]  # la vecina queda fuera
    assert "Se usó la copia" in datos["nota"] and datos["fecha_consulta"] == "2026-10-05"
    monkeypatch.setattr(catastro_sl, "MAX_EN_ZONA", 1)
    ambas = catastro_caido.get("/catastro-sl/parcelas-rurales",
                               params={"oeste": -65.31, "sur": -33.71, "este": -65.28, "norte": -33.69}).json()
    assert ambas["truncado"] is True and ambas["cantidad"] == 1
    nada = catastro_caido.get("/catastro-sl/parcelas-rurales",
                              params={"oeste": -60, "sur": -30, "este": -59, "norte": -29}).json()
    assert nada["cantidad"] == 0 and "No hay parcelas rurales en esa zona de la copia" in nada["nota"]


def test_con_el_catastro_andando_no_se_usa_la_copia(monkeypatch):
    async def punto(lat, lon):
        return catastro_sl.sin_parcela("del Catastro")

    monkeypatch.setattr(catastro_sl, "parcela_en_punto", punto)
    monkeypatch.setattr(catastro_sl, "leer_copia", lambda: pytest.fail("no tenía que leer la copia"))
    app = FastAPI()
    app.include_router(catastro_sl.router)
    r = TestClient(app).get("/catastro-sl/parcela", params={"lat": -33.70, "lon": -65.30})
    assert r.status_code == 200 and r.json()["nota"] == "del Catastro" and "x-copia-del-catastro" not in r.headers


def test_la_copia_marca_dudoso_el_poligono_que_se_reparo(copia_de_prueba):
    cruzado = parcela(3, "X1-00-00-00-000000-000001", "09-1", "1", 50_000,
                      [[[-65.0, -33.0], [-64.99, -32.99], [-65.0, -32.99], [-64.99, -33.0], [-65.0, -33.0]]])
    datos = {**catastro_sl.coleccion([cruzado], "prueba"), "fecha_consulta": "2026-10-05"}
    (copia_de_prueba / catastro_sl.COPIA_INFO.name).unlink()
    actualizar_copia_catastro.guardar_copia(datos, copia_de_prueba)
    p = catastro_sl.parcela_por_codigo_de_la_copia("CATNMC_TRI", "09-1", CAIDO)
    assert p.calidad == "dudosa" and "la copia lo guarda reparado" in p.nota
    validar_poligono(p.geometria_lote)


def test_un_mapa_nuevo_incompleto_no_reemplaza_la_copia(copia_de_prueba):
    antes = (copia_de_prueba / catastro_sl.COPIA.name).read_bytes()
    with pytest.raises(SystemExit, match="parece incompleto"):
        actualizar_copia_catastro.guardar_copia({**catastro_sl.coleccion([LOTE], "x"), "fecha_consulta": "2026-11-01"},
                                                copia_de_prueba)
    assert (copia_de_prueba / catastro_sl.COPIA.name).read_bytes() == antes
    info = actualizar_copia_catastro.guardar_copia(
        {**catastro_sl.coleccion([LOTE, VECINA], "x"), "fecha_consulta": "2026-11-01"}, copia_de_prueba)
    assert info["fecha"] == "2026-11-01" and info["cantidad"] == 2
    assert json.loads(gzip.decompress((copia_de_prueba / catastro_sl.COPIA.name).read_bytes()))["cantidad"] == 2


def test_la_copia_del_repo_tiene_las_3_parcelas_del_piloto(monkeypatch):
    """Con la copia real del 5/10/2026 (prueba del piloto, 16/10/2026)."""
    from shapely.geometry import shape

    monkeypatch.undo()
    assert catastro_sl.info_de_la_copia()["cantidad"] == 17976
    piloto = {"01-90230": ("00-03-28-00-000000-000134", 123.3), "06-924206": ("F5-03-26-00-000000-000009", 456.1),
              "02-950571": ("G5-09-09-00-000000-000465", 196.5)}
    for partida, (nomenclatura, ha) in piloto.items():
        p = catastro_sl.parcela_por_codigo_de_la_copia("CATNMC_TRI", partida, CAIDO)
        assert (p.nomenclatura_catastral, round(p.superficie_registrada_m2 / 1e4, 1)) == (nomenclatura, ha)
        adentro = shape(p.geometria_lote).representative_point()
        en_punto = catastro_sl.parcela_en_punto_de_la_copia(adentro.y, adentro.x, CAIDO)
        assert en_punto.partida_inmobiliaria == partida and en_punto.fecha_consulta.isoformat() == "2026-10-05"
