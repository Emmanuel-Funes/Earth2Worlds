"""Tests sin internet del conector GeoINTA (specs 020 y 021): los geoservicios del INTA están simulados."""

import re
from datetime import date

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rotaterra.fuentes import geointa
from rotaterra.geo import poligono_desde_esquinas

# lote de 0,01° × 0,01° en Pergamino
LOTE = poligono_desde_esquinas("-33.885, -60.575; -33.885, -60.565; -33.895, -60.565; -33.895, -60.575")
OESTE, SUR, ESTE, NORTE = -60.575, -33.895, -60.565, -33.885


def caja(oeste, sur, este, norte) -> dict:
    anillo = [[oeste, sur], [este, sur], [este, norte], [oeste, norte], [oeste, sur]]
    return {"type": "MultiPolygon", "coordinates": [[anillo]]}


def atlas(fid, simbc, ip, geometria, **extra) -> dict:
    propiedades = {"provincia": "BUENOS AIRES", "simbc": simbc, "tipo_uc": "Consociacion", "ind_prod": ip,
                   "limit_ppal": "Sin limitaciones", "limit_secu": "-", "limit_terc": "-",
                   "porc_sue1": 100, "posi_sue1": "Loma", "sgrup_sue1": "Argiudoles tipico",
                   "text_sups1": "Franco limosa", "text_bs1": "Franco arcillo limos", "drenaje_s1": "Bien drenado",
                   "porc_sue2": 0, "sgrup_sue2": None, "porc_sue3": 0, "sgrup_sue3": None}
    propiedades.update(extra)
    return {"type": "Feature", "id": f"suelos_argentina_1_500.{fid}", "geometry": geometria, "properties": propiedades}


def bsas(fid, simbc, cap_uso, geometria, serie="Pergamino", fase="severamente erosionada") -> dict:
    propiedades = {"SIMBC": simbc, "Nombre_UC": f"Consociacion {serie} 3", "TIPO": "Consociacion",
                   "SERIE1": serie, "PORC1": 100, "SERIE2": "", "PORC2": 0, "FASE1": fase, "FASE2": "",
                   "PAISAJE": "", "CAP_USO": cap_uso, "taxo_ppal": "Argiudol tipico"}
    return {"type": "Feature", "id": f"Suelos_BA_50mil_V2.{fid}", "geometry": geometria, "properties": propiedades}


def geotiff(codigos, caja_pedida: str, ancho: int, alto: int, georreferenciado: bool = True) -> bytes:
    """GeoTIFF del tamaño pedido: codigos(lon, lat) da el valor de cada píxel según su centro."""
    import numpy as np
    import rasterio
    from rasterio.transform import from_bounds

    oeste, sur, este, norte = (float(x) for x in caja_pedida.split(","))
    transform = from_bounds(oeste, sur, este, norte, ancho, alto)
    lon = [oeste + (este - oeste) * (c + 0.5) / ancho for c in range(ancho)]
    lat = [norte - (norte - sur) * (f + 0.5) / alto for f in range(alto)]
    datos = np.array([[codigos(x, y) for x in lon] for y in lat], dtype="float32")
    # códigos enteros (Mapa de Cultivos) en uint8; valores continuos (carbono) en float32, como los publica el INTA
    tipo = "uint8" if np.all(np.isfinite(datos)) and np.all(datos == np.round(datos)) and np.all((datos >= 0) & (datos < 256)) \
        else "float32"
    datos = datos.astype(tipo)
    with rasterio.MemoryFile() as archivo:
        perfil = dict(crs="EPSG:4326", transform=transform) if georreferenciado else {}
        with archivo.open(driver="GTiff", width=ancho, height=alto, count=1, dtype=tipo, **perfil) as raster:
            raster.write(datos, 1)
        return archivo.read()


def leyenda_json(clases: dict[int, str]) -> dict:
    entradas = [{"quantity": str(codigo), "label": nombre, "color": "#000000"} for codigo, nombre in clases.items()]
    return {"Legend": [{"layerName": "x", "rules": [{"symbolizers": [{"Raster": {"colormap": {"entries": entradas}}}]}]}]}


def cliente_simulado(respuestas: dict, pedidos: list | None = None, rasters: dict | None = None,
                     leyendas: dict | None = None, georreferenciado: bool = True,
                     pixeles: dict | None = None) -> httpx.Client:
    """Geoservicios de GeoServer de mentira.

    respuestas: capa WFS -> lista de features, o un código HTTP de error. Resuelve el filtro CQL
    INTERSECTS(<geometría>, <WKT>) con shapely y devuelve solo los atributos pedidos, sin geometría, como el
    servidor real con propertyName.
    rasters: cobertura WCS -> función (lon, lat) -> código del píxel. leyendas: capa -> {código: clase}.
    pixeles: capa WMS -> función (lon, lat) -> valor que devuelve GetFeatureInfo (None = sin dato).
    Lo que no está cargado responde 500.
    """
    from shapely import wkt
    from shapely.geometry import shape

    def responder(pedido: httpx.Request) -> httpx.Response:
        if pedidos is not None:
            pedidos.append(pedido)
        params = pedido.url.params
        if params.get("request") == "GetCoverage":
            codigos = (rasters or {}).get(params["coverage"])
            if codigos is None:
                return httpx.Response(500, text="sin cobertura")
            return httpx.Response(200, content=geotiff(codigos, params["bbox"], int(params["width"]),
                                                       int(params["height"]), georreferenciado),
                                  headers={"content-type": "image/tiff"})
        if params.get("request") == "GetFeatureInfo":
            valor = (pixeles or {}).get(params["query_layers"])
            if valor is None:
                return httpx.Response(500, text="sin capa")
            oeste, sur, este, norte = (float(x) for x in params["bbox"].split(","))
            dato = valor((oeste + este) / 2, (sur + norte) / 2)
            elementos = [] if dato is None else [{"type": "Feature", "properties": {"GRAY_INDEX": dato}}]
            return httpx.Response(200, json={"type": "FeatureCollection", "features": elementos},
                                  headers={"content-type": "application/json;charset=UTF-8"})
        if params.get("request") == "GetLegendGraphic":
            clases = (leyendas or {}).get(params["layer"])
            if clases is None:
                return httpx.Response(500, text="sin leyenda")
            return httpx.Response(200, json=leyenda_json(clases), headers={"content-type": "application/json"})
        respuesta = respuestas.get(params["typeName"], [])
        if isinstance(respuesta, int):
            return httpx.Response(respuesta, text="error del servidor")
        geometria, zona = re.fullmatch(r"INTERSECTS\((\w+), (.*)\)", params["CQL_FILTER"]).groups()
        assert geometria in ("the_geom", "geometry")
        zona = wkt.loads(zona)
        campos = params["propertyName"].split(",")
        elegidas = [{"type": "Feature", "id": f["id"], "geometry": None,
                     "properties": {c: f["properties"].get(c) for c in campos}}
                    for f in respuesta if shape(f["geometry"]).intersects(zona)][:int(params["maxFeatures"])]
        return httpx.Response(200, json={"type": "FeatureCollection", "features": elegidas},
                              headers={"content-type": "application/json;charset=UTF-8"})
    return httpx.Client(transport=httpx.MockTransport(responder))


def por_variable(observaciones):
    return {o.variable: o for o in observaciones}


def test_pergamino_indice_y_capacidad_de_uso():
    pedidos = []
    corte = OESTE + (ESTE - OESTE) * 0.8  # Pe3 cubre el 80 % oeste del lote, AD1 el 20 % este
    cliente = cliente_simulado({
        geointa.ATLAS.capa: [atlas(4414, "MItc-1", 95, caja(-61, -34, -60, -33))],
        geointa.BUENOS_AIRES.capa: [bsas(1716, "Pe3", "IVe", caja(OESTE - 1, SUR - 1, corte, NORTE + 1)),
                                    bsas(228, "AD1", "IIIe", caja(corte, SUR - 1, ESTE + 1, NORTE + 1),
                                         serie="Arroyo Dulce", fase="")],
    }, pedidos)
    obs = por_variable(geointa.obtener_suelo("lote-1", LOTE, cliente))

    ip = obs["suelo_indice_productividad"]
    assert (ip.valor, ip.unidad, ip.fuente, ip.calidad) == (95.0, "IP 0-100", "GeoINTA", "buena")
    assert ip.fecha == date(2013, 1, 7) and ip.resolucion_m == 250
    assert "MItc-1" in ip.nota and "Argiudoles tipico 100 %" in ip.nota and "franco limosa" in ip.nota
    assert "cubre 100% del lote (muestreo de puntos)" in ip.nota

    cu = obs["suelo_clase_capacidad_uso"]
    assert (cu.valor, cu.unidad, cu.calidad, cu.resolucion_m) == (4.0, "clase 1-8", "buena", 25)
    assert cu.fecha == date(2023, 4, 17)
    assert "Pe3" in cu.nota and "Pergamino 100 %" in cu.nota and "subclase e (erosión)" in cu.nota
    assert "cubre 80% del lote" in cu.nota and "AD1 20%" in cu.nota

    # primero el polígono del lote en lon/lat, después un punto por cada nodo de la grilla de 5 × 5
    primero = pedidos[0].url.params
    assert primero["typeName"] == geointa.ATLAS.capa and "POLYGON ((-60.575000 -33.885000" in primero["CQL_FILTER"]
    assert "the_geom" not in primero["propertyName"] and "ind_prod" in primero["propertyName"]
    puntos = [p for p in pedidos if "POINT" in p.url.params.get("CQL_FILTER", "")]
    assert len(puntos) == 2 * 25 and all(p.url.params["maxFeatures"] == "1" for p in puntos)


SAN_LUIS = poligono_desde_esquinas("-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300")
VILLA_MERCEDES = geointa.HOJAS_SAN_LUIS[0]


def hoja(fid, uc, cap_uso, ip, geometria) -> dict:
    return {"type": "Feature", "id": f"villamercedes_v0.{fid}", "geometry": geometria,
            "properties": {"ogc_fid": fid, "uc": uc, "cap_uso": cap_uso, "ip": ip}}


def test_san_luis_capacidad_de_uso_de_la_hoja_1_100000():
    pedidos = []
    cliente = cliente_simulado({VILLA_MERCEDES.capa: [hoja(49, "Cr", "VIes", 50, caja(-66, -34, -65, -33))]}, pedidos)
    obs = por_variable(geointa.obtener_suelo("lote-7", SAN_LUIS, cliente))
    cu = obs["suelo_clase_capacidad_uso"]
    assert (cu.valor, cu.calidad, cu.resolucion_m, cu.fecha) == (6.0, "buena", 50, date(2025, 9, 22))
    assert "Unidad Cr" in cu.nota and "subclase es (erosión, limitaciones del suelo)" in cu.nota
    assert "escala 1:100.000" in cu.nota and "nodo 15 (La Pampa - San Luis)" in cu.nota
    detallado = obs["suelo_indice_productividad_detallado"]
    assert (detallado.valor, detallado.unidad, detallado.calidad) == (50.0, "IP 0-100", "buena")
    # va al WFS del nodo 15 y no pregunta por la carta de Buenos Aires
    hosts = {p.url.host for p in pedidos if p.url.params.get("typeName") == VILLA_MERCEDES.capa}
    assert hosts == {"geo-nodo15.inta.gob.ar"}
    assert not any(p.url.params.get("typeName") == geointa.BUENOS_AIRES.capa for p in pedidos)


def test_hoja_de_san_luis_sin_ip_valido():
    cliente = cliente_simulado({VILLA_MERCEDES.capa: [hoja(1, "Lag", "", 0, caja(-66, -34, -65, -33))]})
    obs = por_variable(geointa.obtener_suelo("l", SAN_LUIS, cliente))
    assert obs["suelo_clase_capacidad_uso"].valor is None and "legible" in obs["suelo_clase_capacidad_uso"].nota
    assert obs["suelo_indice_productividad_detallado"].calidad == "descartada"


def test_san_luis_sin_carta_detallada():
    cliente = cliente_simulado({geointa.ATLAS.capa: [atlas(4346, "EPtc-1", 50, caja(-66, -34, -65, -33),
                                                          provincia="SAN LUIS", sgrup_sue1="Ustortentes tipico",
                                                          text_sups1="Franco arenosa",
                                                          limit_ppal="Climatica", limit_secu="Erosion eolica actua")]})
    obs = por_variable(geointa.obtener_suelo("lote-7", SAN_LUIS, cliente))
    assert obs["suelo_indice_productividad"].valor == 50
    assert "Climatica, Erosion eolica actua" in obs["suelo_indice_productividad"].nota
    cu = obs["suelo_clase_capacidad_uso"]
    assert cu.valor is None and cu.calidad == "descartada" and "Sin carta de suelo detallada" in cu.nota


def test_unidad_que_solo_roza_el_borde_y_lote_fuera_de_la_carta():
    borde = OESTE + (ESTE - OESTE) * 0.05  # una franja angosta, sin puntos de muestreo
    corte = OESTE + (ESTE - OESTE) * 0.6   # la carta termina al 60 % del lote
    cliente = cliente_simulado({geointa.ATLAS.capa: [atlas(1, "A", 70, caja(OESTE - 1, SUR - 1, borde, NORTE + 1)),
                                                     atlas(2, "B", 60, caja(borde, SUR - 1, corte, NORTE + 1))]})
    ip = por_variable(geointa.obtener_suelo("l", LOTE, cliente))["suelo_indice_productividad"]
    assert ip.valor == 60 and ip.calidad == "buena"
    assert "cubre 60% del lote" in ip.nota and "A (borde)" in ip.nota and "40% del lote sin unidad" in ip.nota


def test_puntos_de_muestreo_dentro_del_lote():
    triangulo = poligono_desde_esquinas("-33.0, -60.0; -33.0, -59.9; -33.1, -60.0")
    puntos = geointa.puntos_de_muestreo(triangulo)
    assert 5 < len(puntos) < 25
    angosto = poligono_desde_esquinas("-33.0, -60.0; -33.0, -59.9; -33.00001, -59.9; -33.00001, -60.0")
    assert len(geointa.puntos_de_muestreo(angosto, lado=1)) == 1


def test_lote_mixto_queda_dudoso_y_toma_la_unidad_dominante():
    x = [OESTE - 1] + [OESTE + (ESTE - OESTE) * f for f in (0.4, 0.6, 0.8)] + [ESTE + 1]
    cliente = cliente_simulado({geointa.ATLAS.capa: [
        atlas(i, nombre, ip, caja(x[i], SUR - 1, x[i + 1], NORTE + 1))
        for i, (nombre, ip) in enumerate([("A", 80), ("B", 40), ("C", 60), ("D", 70)])]})
    ip = por_variable(geointa.obtener_suelo("l", LOTE, cliente))["suelo_indice_productividad"]
    assert ip.valor == 80 and ip.calidad == "dudosa" and "lote mixto" in ip.nota
    assert "cubre 40% del lote" in ip.nota and "B 20%, C 20%, D 20%" in ip.nota


@pytest.mark.parametrize("ip", [None, 0, 120])
def test_sin_indice_valido_se_descarta(ip):
    cliente = cliente_simulado({geointa.ATLAS.capa: [atlas(1, "Agua", ip, caja(-61, -34, -60, -33))]})
    obs = por_variable(geointa.obtener_suelo("l", LOTE, cliente))["suelo_indice_productividad"]
    assert obs.valor is None and obs.calidad == "descartada" and "índice de productividad válido" in obs.nota


def test_unidad_lejos_del_lote_no_cuenta():
    cliente = cliente_simulado({geointa.ATLAS.capa: [atlas(1, "X", 70, caja(-62, -35, -61.5, -34.5))]})
    obs = por_variable(geointa.obtener_suelo("l", LOTE, cliente))["suelo_indice_productividad"]
    assert obs.valor is None and "ninguna unidad" in obs.nota


def test_si_una_capa_falla_se_descarta_solo_esa():
    cliente = cliente_simulado({geointa.ATLAS.capa: [atlas(1, "MItc-1", 95, caja(-61, -34, -60, -33))],
                                geointa.BUENOS_AIRES.capa: 503})
    obs = por_variable(geointa.obtener_suelo("l", LOTE, cliente))
    assert obs["suelo_indice_productividad"].valor == 95
    cu = obs["suelo_clase_capacidad_uso"]
    assert cu.valor is None and cu.calidad == "descartada" and "GeoINTA no respondió" in cu.nota


def test_si_fallan_todas_las_capas_es_error():
    cliente = cliente_simulado({geointa.ATLAS.capa: 500, geointa.BUENOS_AIRES.capa: 500})
    with pytest.raises(geointa.ErrorGeoINTA, match="No se pudo consultar GeoINTA"):
        geointa.obtener_suelo("l", LOTE, cliente)


def test_respuesta_que_no_es_json():
    def responder(pedido):
        return httpx.Response(200, text="<ServiceExceptionReport/>", headers={"content-type": "text/xml"})
    with pytest.raises(geointa.ErrorGeoINTA):
        geointa.obtener_suelo("l", LOTE, httpx.Client(transport=httpx.MockTransport(responder)))


@pytest.mark.parametrize("texto, esperado", [("IVe", (4, "e")), ("I-2", (1, "")), ("IIIes", (3, "es")),
                                              ("VIIIw", (8, "w")), ("VI", (6, "")), ("", (None, "")),
                                              ("sin dato", (None, "")), ("IX", (None, ""))])
def test_clase_capacidad_uso(texto, esperado):
    assert geointa.clase_capacidad_uso(texto) == esperado


def test_clase_ilegible_se_descarta():
    cliente = cliente_simulado({geointa.BUENOS_AIRES.capa: [bsas(1, "Z", "", caja(-61, -34, -60, -33))],
                                geointa.ATLAS.capa: []})
    cu = por_variable(geointa.obtener_suelo("l", LOTE, cliente))["suelo_clase_capacidad_uso"]
    assert cu.valor is None and cu.calidad == "descartada" and "legible" in cu.nota


VERANO_2024 = next(c for c in geointa.CAMPANAS if c.nombre == "verano 2023/24")


@pytest.fixture(autouse=True)
def geosepa_sin_internet(monkeypatch):
    """Las campañas de GeoSEPA no salen a internet en los tests: por defecto no responden."""
    def no_responde(url, poligono):
        raise TimeoutError("GeoSEPA simulado sin respuesta")
    monkeypatch.setattr(geointa, "leer_geosepa", no_responde)
LEYENDA_VERANO = {10: "Maíz", 11: "Soja", 18: "Sorgo GR ", 21: "Barbecho", 22: "No agrícola"}


def test_cultivos_por_wcs_con_el_reparto_del_lote():
    pedidos = []
    corte = OESTE + (ESTE - OESTE) * 0.7  # soja en el 70 % oeste, maíz en el resto
    cliente = cliente_simulado({}, pedidos, rasters={VERANO_2024.capa: lambda lon, lat: 11 if lon < corte else 10},
                               leyendas={VERANO_2024.capa: LEYENDA_VERANO})
    obs = [o for o in geointa.obtener_suelo("l", LOTE, cliente) if o.variable.startswith("cultivo_mnc")]
    assert len(obs) == len(geointa.CAMPANAS)
    ultima = next(o for o in obs if o.fecha == date(2024, 1, 1))
    assert (ultima.variable, ultima.valor, ultima.calidad, ultima.resolucion_m) == ("cultivo_mnc_verano", 2.0, "buena", 30)
    assert "Soja (código 2) en el 7" in ultima.nota and "Maíz 3" in ultima.nota and "WCS del nodo Nacional" in ultima.nota
    # las demás campañas no respondieron: quedan descartadas, sin inventar nada
    assert all(o.valor is None and o.calidad == "descartada" for o in obs if o is not ultima)
    wcs = next(p for p in pedidos if p.url.params.get("request") == "GetCoverage")
    assert wcs.url.host == "geo-backend.inta.gob.ar" and wcs.url.params["format"] == "GeoTIFF"


def test_geotiff_sin_georreferencia_usa_la_grilla_pedida():
    corte = OESTE + (ESTE - OESTE) * 0.7
    cliente = cliente_simulado({}, rasters={VERANO_2024.capa: lambda lon, lat: 11 if lon < corte else 10},
                               leyendas={VERANO_2024.capa: LEYENDA_VERANO}, georreferenciado=False)
    ultima = next(o for o in geointa.obtener_suelo("l", LOTE, cliente) if o.fecha == date(2024, 1, 1))
    assert ultima.valor == 2.0 and "Soja (código 2) en el 7" in ultima.nota


def test_cultivo_fuera_de_la_leyenda_se_descarta():
    cliente = cliente_simulado({}, rasters={VERANO_2024.capa: lambda lon, lat: 255},
                               leyendas={VERANO_2024.capa: LEYENDA_VERANO})
    ultima = next(o for o in geointa.obtener_suelo("l", LOTE, cliente) if o.fecha == date(2024, 1, 1))
    assert ultima.valor is None and ultima.calidad == "descartada" and "código 255 fuera de la leyenda" in ultima.nota


def test_lote_mitad_y_mitad_queda_dudoso():
    medio = OESTE + (ESTE - OESTE) * 0.45
    cliente = cliente_simulado({}, rasters={VERANO_2024.capa: lambda lon, lat: 21 if lon < medio else (11 if lat < -33.89 else 22)},
                               leyendas={VERANO_2024.capa: LEYENDA_VERANO})
    ultima = next(o for o in geointa.obtener_suelo("l", LOTE, cliente) if o.fecha == date(2024, 1, 1))
    assert ultima.calidad == "dudosa" and "lote mixto" in ultima.nota and ultima.valor == 40.0


@pytest.mark.parametrize("etiqueta, codigo", [("Maíz", 1), ("Soja (Cultivo único)", 2), ("Sorgo GR ", 4),
                                               ("Girasol-CV ", 32), ("Cultivo de Invierno - Soja", 30),
                                               ("No agrícola ", 41), ("Vegetación natural leñosa", 43),
                                               ("Caña de azucar ", 9), ("Zonas Enmascaradas", None), ("Limite", None)])
def test_codigo_comun_de_cultivo(etiqueta, codigo):
    assert geointa.codigo_cultivo(etiqueta) == codigo


TEXTURA_0_15, TEXTURA_30_60 = geointa.TEXTURA[0], geointa.TEXTURA[2]
PH_0_30 = geointa.PH[0]


def test_textura_y_ph_por_wms_en_puntos_del_lote():
    pedidos = []
    medio = (OESTE + ESTE) / 2
    cliente = cliente_simulado({}, pedidos, pixeles={
        TEXTURA_0_15.capa: lambda lon, lat: 8.0,  # en esa leyenda el 8 es franco arenoso
        TEXTURA_30_60.capa: lambda lon, lat: 9.0,  # y en esta el 9
        PH_0_30.capa: lambda lon, lat: 8.4 if lon < medio else 8.7,
    }, leyendas={TEXTURA_0_15.capa: {3: "Franco (3)", 8: "Franco arenoso (8)", 9: "Limoso (9)", 100: "Miscelánea (100)"},
                 TEXTURA_30_60.capa: {4: "Franco/Franco limoso (4)", 9: "Franco arenoso (9)"}})
    obs = por_variable(geointa.obtener_suelo("l", LOTE, cliente))
    for variable in ("suelo_textura_0_15cm", "suelo_textura_30_60cm"):
        textura = obs[variable]
        assert (textura.valor, textura.calidad, textura.resolucion_m) == (3.0, "buena", 1000)
        assert "Franco arenoso" in textura.nota and "9 de 9 puntos" in textura.nota and "SUPUESTO 1 km" in textura.nota
    ph = obs["suelo_ph_0_30cm"]
    assert ph.unidad == "pH" and 8.4 < ph.valor < 8.7 and ph.calidad == "buena"
    assert "RMSE 0,84" in ph.nota and "no es una medición del lote" in ph.nota and "WMS GetFeatureInfo del nodo 05" in ph.nota
    # las capas que no respondieron quedan descartadas
    assert obs["suelo_textura_15_30cm"].valor is None and "no respondió" in obs["suelo_textura_15_30cm"].nota
    hosts = {p.url.host for p in pedidos if p.url.params.get("request") == "GetFeatureInfo"}
    assert hosts == {"geo-nodo05.inta.gob.ar"}


def test_ph_miscelanea_y_textura_sin_dato_se_descartan():
    cliente = cliente_simulado({}, pixeles={TEXTURA_0_15.capa: lambda lon, lat: 100.0, PH_0_30.capa: lambda lon, lat: 101.0},
                               leyendas={TEXTURA_0_15.capa: {8: "Franco arenoso (8)", 100: "Miscelánea (100)"}})
    obs = por_variable(geointa.obtener_suelo("l", LOTE, cliente))
    assert obs["suelo_ph_0_30cm"].valor is None and obs["suelo_ph_0_30cm"].calidad == "descartada"
    textura = obs["suelo_textura_0_15cm"]
    assert textura.valor is None and textura.calidad == "descartada" and "Miscelánea" in textura.nota


@pytest.mark.parametrize("etiqueta, codigo", [("Franco arenoso (8)", 3), ("Arcilloso (1)", 12), ("Areno franco (4)", 2),
                                               ("Franco/Franco limoso (4)", 13), ("Miscelánea (100)", None)])
def test_codigo_comun_de_textura(etiqueta, codigo):
    assert geointa.codigo_textura(etiqueta) == codigo


def test_se_anuncia_como_dato_fijo():
    (satelite,) = geointa.SATELITES
    assert satelite.nombre == "GeoINTA" and satelite.estatico and satelite.respaldo_de is None


def test_endpoint_rechaza_poligono_invalido():
    app = FastAPI()
    app.include_router(geointa.router)
    respuesta = TestClient(app).post("/suelo", json={"lote_id": "l", "poligono": {"type": "Point"}})
    assert respuesta.status_code == 422


def test_campana_2024_25_de_geosepa_con_la_leyenda_del_qml(monkeypatch):
    import numpy as np
    monkeypatch.setattr(geointa, "leer_geosepa", lambda url, poligono: np.array([10] * 60 + [22] * 35 + [31] * 5))
    cliente = cliente_simulado({})
    obs = [o for o in geointa.obtener_suelo("l", LOTE, cliente) if o.fecha == date(2025, 1, 1)]
    assert len(obs) == 1
    verano = obs[0]
    assert (verano.variable, verano.valor, verano.calidad) == ("cultivo_mnc_verano", 1.0, "buena")
    assert "GeoSEPA" in verano.nota and "MNC_verano_2024-2025.tif" in verano.nota and "CIRN-INTA" in verano.nota
    assert "sin clasificar 5%" in verano.nota  # la máscara (31) no es una clase


def test_verdeo_de_maiz_tiene_codigo_comun():
    assert geointa.codigo_cultivo("Verdeo de maíz") == 13


def test_carbono_organico_2023_por_wcs():
    pedidos = []
    medio = (OESTE + ESTE) / 2
    cliente = cliente_simulado({}, pedidos, rasters={geointa.COBERTURA_COS: lambda lon, lat: 30.5 if lon < medio else 40.25})
    obs = por_variable(geointa.obtener_suelo("lote-7", LOTE, cliente))
    cos = obs["suelo_carbono_organico_0_30cm_t_ha"]
    assert (cos.unidad, cos.fuente, cos.calidad, cos.resolucion_m, cos.fecha) == ("t/ha", "GeoINTA", "dudosa", 250,
                                                                                   date(2023, 10, 27))
    assert 30.5 < cos.valor < 40.25
    cantidad = int(re.search(r"Media de (\d+) píxeles", cos.nota).group(1))
    assert 10 <= cantidad <= 25  # lote de ~1,1 × 0,9 km con píxeles de ~250 m
    assert "de 30.50 a 40.25 t/ha" in cos.nota and "0-30 cm" in cos.nota and "recurso 487" in cos.nota
    assert "no es una medición del lote" in cos.nota and "CC BY-NC-SA" in cos.nota
    wcs = next(p for p in pedidos if p.url.params.get("coverage") == geointa.COBERTURA_COS)
    assert wcs.url.host == "geo-backend.inta.gob.ar" and wcs.url.params["format"] == "GeoTIFF"
    # se pide a la resolución nativa del ráster (el ancho en píxeles se redondea)
    oeste, _, este, _ = (float(x) for x in wcs.url.params["bbox"].split(","))
    assert abs((este - oeste) / int(wcs.url.params["width"]) / geointa.PIXEL_COS - 1) < 0.1


def test_carbono_con_pixeles_vacios_cuenta_solo_los_validos():
    medio = (OESTE + ESTE) / 2
    cliente = cliente_simulado({}, rasters={geointa.COBERTURA_COS: lambda lon, lat: 35.0 if lon < medio else float("nan")})
    cos = por_variable(geointa.obtener_suelo("l", LOTE, cliente))["suelo_carbono_organico_0_30cm_t_ha"]
    assert cos.valor == 35.0 and cos.calidad == "dudosa" and "píxeles sin dato" in cos.nota


@pytest.mark.parametrize("relleno", [0.0, float("nan"), -3.4028235e38])
def test_carbono_sin_pixeles_validos_se_descarta(relleno):
    cliente = cliente_simulado({}, rasters={geointa.COBERTURA_COS: lambda lon, lat: relleno})
    cos = por_variable(geointa.obtener_suelo("l", LOTE, cliente))["suelo_carbono_organico_0_30cm_t_ha"]
    assert cos.valor is None and cos.calidad == "descartada" and "no tienen dato" in cos.nota
    assert cos.unidad == "t/ha" and cos.resolucion_m == 250


def test_carbono_sin_ningun_pixel():
    cos = geointa.carbono_organico("l", [])
    assert cos.valor is None and cos.calidad == "descartada" and "ningún píxel" in cos.nota


def test_si_falla_el_wcs_de_carbono_el_resto_del_suelo_sigue():
    cliente = cliente_simulado({geointa.ATLAS.capa: [atlas(1, "MItc-1", 95, caja(-61, -34, -60, -33))]},
                               rasters={VERANO_2024.capa: lambda lon, lat: 11}, leyendas={VERANO_2024.capa: LEYENDA_VERANO})
    obs = geointa.obtener_suelo("l", LOTE, cliente)  # el carbono no está cargado: el WCS responde 500
    por = por_variable(obs)
    assert por["suelo_indice_productividad"].valor == 95
    assert any(o.variable == "cultivo_mnc_verano" and o.valor == 2.0 for o in obs)
    cos = por["suelo_carbono_organico_0_30cm_t_ha"]
    assert cos.valor is None and cos.calidad == "descartada"
    assert "GeoINTA no respondió" in cos.nota and "carbono orgánico 2023" in cos.nota


def test_geotiff_de_carbono_ilegible_se_descarta():
    def responder(pedido):
        if pedido.url.params.get("coverage") == geointa.COBERTURA_COS:
            return httpx.Response(200, content=b"no es un tif", headers={"content-type": "image/tiff"})
        return httpx.Response(500, text="caído")
    with pytest.raises(geointa.ErrorGeoINTA, match="ilegible"):
        geointa.carbono_del_lote(httpx.Client(transport=httpx.MockTransport(responder)), "l", LOTE)


def test_una_campana_de_geosepa_trabada_no_frena_el_suelo(monkeypatch):
    # 16/10/2026: la lectura de GeoSEPA quedó trabada más de una hora en dos parcelas reales de San Luis
    import time
    monkeypatch.setattr(geointa, "leer_geosepa", lambda url, poligono: time.sleep(3))
    cliente = cliente_simulado({}, rasters={VERANO_2024.capa: lambda lon, lat: 11},
                               leyendas={VERANO_2024.capa: LEYENDA_VERANO})
    inicio = time.monotonic()
    obs = geointa.cultivos_del_lote(cliente, "l", LOTE, tope=0.5)
    assert time.monotonic() - inicio < 2
    assert len(obs) == len(geointa.CAMPANAS)
    assert next(o for o in obs if o.fecha == date(2024, 1, 1)).valor == 2.0  # la que contestó se usa
    trabadas = [o for o in obs if o.fecha in (date(2024, 7, 1), date(2025, 1, 1))]
    assert all(o.valor is None and o.calidad == "descartada" and "no respondió en 0 s" in o.nota for o in trabadas)


# ---------- memoria del suelo y límite de pedidos al INTA (spec 044) ----------

@pytest.fixture
def inta_simulado(monkeypatch):
    """obtener_suelo sin cliente propio (como en la app), con los 5 pasos simulados: cuenta cuántas veces se le
    pide al INTA y deja elegir qué paso falla."""
    geointa._memoria.clear()
    pedidos, fallan = [], set()

    def paso(nombre, armar):
        def leer(*args, **kwargs):
            pedidos.append(nombre)
            if nombre in fallan:
                raise httpx.ConnectError("Connection reset by peer")
            return armar(args[1])  # args = (cliente, lote_id o carta, polígono)
        return leer

    monkeypatch.setattr(geointa, "cliente_inta", lambda: httpx.Client(transport=httpx.MockTransport(
        lambda pedido: httpx.Response(500))))
    monkeypatch.setattr(geointa, "unidades_en_el_lote", paso("atlas", lambda _: []))
    monkeypatch.setattr(geointa, "capacidad_del_lote", paso("cartas", lambda lote: [geointa.capacidad_uso(lote, [])]))
    monkeypatch.setattr(geointa, "cultivos_del_lote", paso("mnc", lambda _: []))
    monkeypatch.setattr(geointa, "textura_y_ph", paso("textura", lambda _: []))
    monkeypatch.setattr(geointa, "carbono_del_lote", paso("carbono", lambda lote: geointa.carbono_organico(lote, [])))
    yield pedidos, fallan
    geointa._memoria.clear()


def test_el_mismo_lote_se_le_pide_al_inta_una_sola_vez(inta_simulado):
    pedidos, _ = inta_simulado
    primera = geointa.obtener_suelo("lote-1", SAN_LUIS)
    assert len(pedidos) == 5
    segunda = geointa.obtener_suelo("lote-9", SAN_LUIS)
    assert len(pedidos) == 5  # salió de la memoria: no se le pidió nada al INTA
    assert [o.variable for o in segunda] == [o.variable for o in primera]
    assert all(o.lote_id == "lote-9" for o in segunda) and all(o.lote_id == "lote-1" for o in primera)
    hoy = date.today().isoformat()
    assert all(o.nota.endswith(f"· guardado en memoria: el INTA lo entregó el {hoy}") for o in segunda)
    assert [(o.valor, o.calidad) for o in segunda] == [(o.valor, o.calidad) for o in primera]
    assert not any("memoria" in o.nota for o in primera)


def test_el_mismo_poligono_con_ruido_de_redondeo_es_el_mismo_lote():
    corrido = {"type": "Polygon", "coordinates": [[[x + 1e-9, y - 1e-9] for x, y in SAN_LUIS["coordinates"][0]]]}
    assert geointa.llave_del_lote(corrido) == geointa.llave_del_lote(SAN_LUIS)
    assert geointa.llave_del_lote(LOTE) != geointa.llave_del_lote(SAN_LUIS)


def test_una_respuesta_con_errores_no_se_guarda(inta_simulado):
    pedidos, fallan = inta_simulado
    fallan.add("cartas")
    obs = por_variable(geointa.obtener_suelo("l", SAN_LUIS))
    assert obs["suelo_clase_capacidad_uso"].nota.startswith("GeoINTA no respondió")
    fallan.clear()
    geointa.obtener_suelo("l", SAN_LUIS)
    assert len(pedidos) == 10  # se volvió a pedir entero
    geointa.obtener_suelo("l", SAN_LUIS)
    assert len(pedidos) == 10  # ya completo, queda en memoria


def test_una_campana_que_no_llego_tampoco_se_guarda(inta_simulado, monkeypatch):
    pedidos, _ = inta_simulado
    monkeypatch.setattr(geointa, "cultivos_del_lote", lambda *a, **k: (
        pedidos.append("mnc"), [geointa._campana_descartada("l", geointa.CAMPANAS[0], "no respondió en 90 s")])[1])
    geointa.obtener_suelo("l", SAN_LUIS)
    geointa.obtener_suelo("l", SAN_LUIS)
    assert len(pedidos) == 10


def test_si_todo_falla_es_error_y_no_se_guarda(inta_simulado):
    pedidos, fallan = inta_simulado
    fallan.update({"atlas", "cartas", "mnc", "textura", "carbono"})
    with pytest.raises(geointa.ErrorGeoINTA):
        geointa.obtener_suelo("l", SAN_LUIS)
    assert not geointa._memoria


def test_pasados_30_dias_se_vuelve_a_pedir(inta_simulado, monkeypatch):
    pedidos, _ = inta_simulado
    ahora = [1_000_000.0]
    monkeypatch.setattr(geointa.time, "time", lambda: ahora[0])
    geointa.obtener_suelo("l", SAN_LUIS)
    ahora[0] += 29 * 24 * 3600
    geointa.obtener_suelo("l", SAN_LUIS)
    assert len(pedidos) == 5
    ahora[0] += 2 * 24 * 3600
    geointa.obtener_suelo("l", SAN_LUIS)
    assert len(pedidos) == 10


def test_con_mas_de_500_lotes_sale_el_que_se_uso_hace_mas_tiempo(inta_simulado, monkeypatch):
    monkeypatch.setattr(geointa, "MAX_LOTES_EN_MEMORIA", 3)
    obs = [geointa.carbono_organico("x", [])]
    for llave in "abc":
        geointa.a_la_memoria(llave, obs)
    assert geointa.de_la_memoria("a", "l") is not None  # "a" se usó recién: el más viejo pasa a ser "b"
    geointa.a_la_memoria("d", obs)
    assert list(geointa._memoria) == ["c", "a", "d"]
    assert geointa.MAX_LOTES_EN_MEMORIA == 3 and len(geointa._memoria) == 3


def test_con_cliente_propio_no_se_usa_la_memoria(inta_simulado):
    pedidos, _ = inta_simulado
    cliente = httpx.Client(transport=httpx.MockTransport(lambda pedido: httpx.Response(500)))
    geointa.obtener_suelo("l", SAN_LUIS, cliente)
    geointa.obtener_suelo("l", SAN_LUIS, cliente)
    assert len(pedidos) == 10 and not geointa._memoria


def test_nunca_hay_mas_de_3_pedidos_a_la_vez_al_inta():
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    candado, en_curso, maximo = threading.Lock(), [0], [0]

    def responder(pedido):
        with candado:
            en_curso[0] += 1
            maximo[0] = max(maximo[0], en_curso[0])
        time.sleep(0.05)
        with candado:
            en_curso[0] -= 1
        return httpx.Response(200, text="ok")

    # dos consultas de lotes distintos a la vez, cada una con su cliente y 5 hilos
    clientes = [httpx.Client(transport=geointa.TransporteConTurno(httpx.MockTransport(responder))) for _ in range(2)]
    with ThreadPoolExecutor(10) as hilos:
        respuestas = list(hilos.map(lambda i: clientes[i % 2].get("https://geo-backend.inta.gob.ar/x").text, range(20)))
    assert respuestas == ["ok"] * 20
    assert maximo[0] == geointa.MAX_PEDIDOS_INTA == 3


def test_un_pedido_que_falla_devuelve_el_turno():
    def responder(pedido):
        raise httpx.ConnectError("Connection reset by peer")
    cliente = httpx.Client(transport=geointa.TransporteConTurno(httpx.MockTransport(responder)))
    for _ in range(geointa.MAX_PEDIDOS_INTA + 2):
        with pytest.raises(httpx.ConnectError):
            cliente.get("https://geo-backend.inta.gob.ar/x")
    assert geointa._turnos_inta.acquire(blocking=False)  # quedan turnos libres
    geointa._turnos_inta.release()
