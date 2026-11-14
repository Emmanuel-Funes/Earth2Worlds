from datetime import date, datetime, timezone

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from rotaterra import api
from rotaterra.fuentes import ecostress

LOTE = {"type": "Polygon", "coordinates": [[
    [-65.30, -33.70], [-65.295, -33.70], [-65.295, -33.705], [-65.30, -33.705], [-65.30, -33.70]]]}
JET = "ECOv002_L3T_JET_41234_008_20HLC_20260113T174200_0713_01"
ESI = "ECOv002_L4T_ESI_41234_008_20HLC_20260113T174200_0713_01"
URL_DATOS = "https://data.lpdaac.earthdatacloud.nasa.gov/lp-prod-protected"


# ---------- fecha, hora y capas ----------

@pytest.mark.parametrize("hora_utc, dia", [
    (datetime(2026, 1, 13, 17, 42, tzinfo=timezone.utc), date(2026, 1, 13)),   # mediodía local
    (datetime(2026, 1, 14, 2, 0, tzinfo=timezone.utc), date(2026, 1, 13)),     # noche local del 13
    (datetime(2026, 1, 14, 4, 30, tzinfo=timezone.utc), date(2026, 1, 14)),    # madrugada local del 14
])
def test_fecha_es_el_dia_solar_local_de_la_pasada(hora_utc, dia):
    assert ecostress.fecha_local(hora_utc, -65.3) == dia


def test_hora_de_pasada_de_cmr_o_del_nombre():
    umm = {"TemporalExtent": {"RangeDateTime": {"BeginningDateTime": "2026-01-13T17:42:00.000Z"}}}
    assert ecostress.hora_de_pasada(umm, "x") == datetime(2026, 1, 13, 17, 42, tzinfo=timezone.utc)
    assert ecostress.hora_de_pasada({}, JET) == datetime(2026, 1, 13, 17, 42, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        ecostress.hora_de_pasada({}, "sin_fecha")


def test_capas_del_granulo_solo_https_y_tif():
    urls = [f"{URL_DATOS}/ECO_L3T_JET.002/{JET}/{JET}_ETdaily.tif",
            f"{URL_DATOS}/ECO_L3T_JET.002/{JET}/{JET}_cloud.tif",
            f"{URL_DATOS}/ECO_L3T_JET.002/{JET}/{JET}_ETinstUncertainty.tif",
            f"s3://lp-prod-protected/ECO_L3T_JET.002/{JET}/{JET}_water.tif",
            f"{URL_DATOS}/ECO_L3T_JET.002/{JET}/{JET}.json"]
    capas = ecostress.capas_del_granulo(JET, urls)
    assert set(capas) == {"etdaily", "cloud", "etinstuncertainty"}
    assert capas["etdaily"].endswith("_ETdaily.tif")


# ---------- cálculo ----------

def test_pixeles_validos_rango_nube_y_agua():
    dato = np.array([[4.0, np.nan, -1.0, 25.0, 5.0, 6.0]])
    nube = np.array([[0, 0, 0, 0, 1, 0]], dtype="uint8")
    agua = np.array([[0, 0, 0, 0, 0, 1]], dtype="uint8")
    validos = ecostress.pixeles_validos(dato, ecostress.PRODUCTOS["et_mm_dia"], {"cloud": nube, "water": agua})
    assert validos.tolist() == [[True, False, False, False, False, False]]


def test_esi_admite_apenas_mas_de_uno():
    dato = np.array([[0.0, 0.6, 1.1, 3.0]])
    assert ecostress.pixeles_validos(dato, ecostress.PRODUCTOS["esi"], {}).tolist() == [[True, True, True, False]]


def test_mascara_del_lote_por_centro_y_lote_chico():
    from affine import Affine
    from shapely.geometry import box

    transformada = Affine(70, 0, 0, 0, -70, 280)  # 4 × 4 píxeles de 70 m
    dentro, tocado = ecostress.mascara_del_lote(box(0, 140, 140, 280), (4, 4), transformada)
    assert not tocado and dentro.sum() == 4 and dentro[:2, :2].all()
    chico, tocado = ecostress.mascara_del_lote(box(60, 150, 80, 200), (4, 4), transformada)  # 20 × 50 m, entre dos píxeles
    assert tocado and chico.sum() == 2 and chico[1, 0] and chico[1, 1]


def test_resumen_solo_cuenta_pixeles_del_lote():
    dato = np.array([[2.0, 4.0, 6.0, 8.0]])
    dentro = np.array([[True, True, True, False]])
    validos = np.array([[True, True, False, True]])
    r = ecostress.resumir(dato, dentro, validos)
    assert r.validos_pct == pytest.approx(200 / 3)
    assert r.mediana == pytest.approx(3.0)


@pytest.mark.parametrize("pct, calidad", [(96, "buena"), (60, "buena"), (45, "dudosa"), (10, "descartada")])
def test_calidad_segun_pixeles_validos(pct, calidad):
    r = ecostress.Resumen(4.8, 4.75, 4.1, 5.3, pct)
    obs = ecostress.a_observacion("lote-7", date(2026, 1, 13), "et_mm_dia", r, "detalle")
    assert obs.calidad == calidad
    assert obs.fuente == "ECOSTRESS" and obs.resolucion_m == 70 and obs.unidad == "mm/día"
    assert (obs.valor is None) == (calidad == "descartada")


def test_sin_pixeles_validos_no_inventa():
    r = ecostress.resumir(np.array([[0.5]]), np.array([[True]]), np.array([[False]]))
    obs = ecostress.a_observacion("lote-7", date(2026, 1, 13), "esi", r, "detalle")
    assert obs.valor is None and obs.calidad == "descartada" and "nube" in obs.nota
    assert obs.unidad == "índice (0 a 1)"


@pytest.mark.parametrize("hora_utc, calidad", [(14, "buena"), (10, "dudosa"), (21, "dudosa")])
def test_pasada_con_poco_sol_queda_a_lo_sumo_dudosa(hora_utc, calidad):
    # 14 UTC = 09:39 solar en San Luis; 10 UTC = 05:39 (madrugada); 21 UTC = 16:39 (tarde)
    r = ecostress.Resumen(2.9, 3.5, 2.4, 4.8, 100)
    obs = ecostress.a_observacion("lote-7", date(2026, 1, 11), "et_mm_dia", r, "detalle")
    solar = ecostress.hora_solar(datetime(2026, 1, 11, hora_utc, 0, tzinfo=timezone.utc), -65.3)
    obs = ecostress.con_poco_sol(obs, solar)
    assert obs.calidad == calidad and obs.valor == 2.9
    assert ("poco sol" in obs.nota) == (calidad == "dudosa")


def test_dos_pasadas_el_mismo_dia_queda_la_mas_limpia():
    def obs(valor, nota):
        return ecostress.Observacion(lote_id="l", fecha=date(2026, 1, 13), variable="esi", valor=valor,
                                     unidad="índice (0 a 1)", fuente="ECOSTRESS", resolucion_m=70,
                                     calidad="buena" if valor else "descartada", nota=nota)
    otra = obs(0.4, "otro día").model_copy(update={"fecha": date(2026, 1, 14)})
    elegidas = ecostress.quedarse_con_la_mejor([(obs(0.6, "a"), 70.0), (obs(0.5, "b"), 95.0),
                                                (obs(None, "c"), 0.0), (otra, 80.0)])
    assert [(o.fecha.day, o.valor) for o in elegidas] == [(13, 0.5), (14, 0.4)]
    assert "3 pasadas ese día" in elegidas[0].nota
    assert "pasadas" not in elegidas[1].nota


@pytest.mark.parametrize("poligono, desde, hasta", [
    ({"type": "Point", "coordinates": [-65.3, -33.7]}, date(2026, 1, 1), date(2026, 2, 1)),
    (LOTE, date(2026, 2, 1), date(2026, 1, 1)),
    (LOTE, date(2024, 1, 1), date(2026, 1, 1)),
])
def test_pedido_invalido(poligono, desde, hasta):
    with pytest.raises(ValueError):
        ecostress.validar_pedido(poligono, desde, hasta)


# ---------- enlace firmado y CMR ----------

def test_enlace_firmado_sigue_la_redireccion_de_lp_daac():
    def nasa(pedido):
        assert pedido.headers["Authorization"] == "Bearer abc123"
        return httpx.Response(307, headers={"location": "https://d1.cloudfront.net/ETdaily.tif?Signature=x"})
    cliente = httpx.Client(transport=httpx.MockTransport(nasa), headers={"Authorization": "Bearer abc123"})
    assert ecostress.enlace_firmado(cliente, f"{URL_DATOS}/x_ETdaily.tif") == \
        "https://d1.cloudfront.net/ETdaily.tif?Signature=x"


def test_enlace_firmado_sin_redireccion_usa_el_original_y_acceso_negado_es_error():
    cliente = httpx.Client(transport=httpx.MockTransport(lambda p: httpx.Response(206, content=b"II*\x00")))
    assert ecostress.enlace_firmado(cliente, "https://otro/x.tif") == "https://otro/x.tif"
    negado = httpx.Client(transport=httpx.MockTransport(lambda p: httpx.Response(403)))
    with pytest.raises(httpx.HTTPStatusError):
        ecostress.enlace_firmado(negado, f"{URL_DATOS}/x.tif")


def test_los_errores_no_muestran_la_firma_del_enlace():
    texto = "RasterioIOError: 'https://d1.cloudfront.net/x_ETdaily.tif?Policy=abc&Signature=xyz' not recognized"
    assert ecostress.sin_firma(texto) == "RasterioIOError: 'https://d1.cloudfront.net/x_ETdaily.tif' not recognized"


def item_cmr(nombre, hora, capas, carpeta="ECO_L3T_JET.002"):
    return {"umm": {"GranuleUR": nombre,
                    "TemporalExtent": {"RangeDateTime": {"BeginningDateTime": hora}},
                    "RelatedUrls": [{"Type": "GET DATA", "URL": f"{URL_DATOS}/{carpeta}/{nombre}/{nombre}_{c}.tif"}
                                    for c in capas]}}


def test_buscar_granulos_pagina_y_usa_el_rectangulo_del_lote():
    pedidos = []

    def nasa(pedido):
        pedidos.append(pedido)
        if pedido.url.path.endswith("collections.umm_json"):
            return httpx.Response(200, json={"items": [{"meta": {"concept-id": "C1"}, "umm": {"Version": "002"}}]})
        if "CMR-Search-After" not in pedido.headers:
            return httpx.Response(200, headers={"CMR-Search-After": "pag2"}, json={
                "items": [item_cmr(f"G{i}_20260113T174200_", "2026-01-13T17:42:00Z", ["ETdaily"])
                          for i in range(500)]})
        return httpx.Response(200, json={"items": [item_cmr(JET, "2026-01-13T17:42:00Z", ["ETdaily", "cloud"])]})

    cliente = httpx.Client(transport=httpx.MockTransport(nasa))
    granulos = ecostress.buscar_granulos(cliente, "ECO_L3T_JET", date(2026, 1, 1), date(2026, 1, 31),
                                         (-65.3, -33.705, -65.295, -33.7))
    assert len(granulos) == 501
    assert granulos[-1].capas.keys() == {"etdaily", "cloud"}
    assert pedidos[1].url.params["bounding_box"] == "-65.3,-33.705,-65.295,-33.7"


def test_coleccion_que_no_esta_en_cmr_es_error():
    cliente = httpx.Client(transport=httpx.MockTransport(lambda p: httpx.Response(200, json={"items": []})))
    with pytest.raises(ecostress.ErrorECOSTRESS, match="ECO_L4T_ESI"):
        ecostress.buscar_granulos(cliente, "ECO_L4T_ESI", date(2026, 1, 1), date(2026, 1, 2), (0, 0, 1, 1))


# ---------- lectura de los COG (archivos locales sintéticos, en UTM como los mosaicos) ----------

def escribir(carpeta, nombre, capa, valores, dtype="float32", nodata=np.nan):
    """GeoTIFF de 70 m en UTM 20S que cubre el lote con margen; devuelve la ruta."""
    import rasterio
    from rasterio.transform import from_origin
    from rasterio.warp import transform

    xs, ys = transform("EPSG:4326", "EPSG:32720", [-65.301], [-33.699])
    ruta = carpeta / f"{nombre}_{capa}.tif"
    datos = np.full((14, 14), valores, dtype=dtype) if np.isscalar(valores) else np.asarray(valores, dtype=dtype)
    with rasterio.open(ruta, "w", driver="GTiff", width=14, height=14, count=1, dtype=dtype,
                       crs="EPSG:32720", transform=from_origin(xs[0], ys[0], 70, 70), nodata=nodata) as f:
        f.write(datos, 1)
    return str(ruta)


def test_lee_la_ventana_del_lote_y_da_la_mediana(tmp_path):
    et = np.full((14, 14), 4.0)
    et[:7] = 6.0  # mitad norte más húmeda
    granulo = ecostress.Granulo(JET, "ECO_L3T_JET", datetime(2026, 1, 13, 17, 42, tzinfo=timezone.utc), {
        "etdaily": escribir(tmp_path, JET, "ETdaily", et),
        "cloud": escribir(tmp_path, JET, "cloud", 0, "uint8", 255),
        "water": escribir(tmp_path, JET, "water", 0, "uint8", 255)})
    obs, pct = ecostress.procesar("lote-7", LOTE, -65.2975, "et_mm_dia", granulo)
    assert pct == 100.0 and obs.calidad == "buena"
    assert 4.0 <= obs.valor <= 6.0
    assert obs.fecha == date(2026, 1, 13)
    assert "ETdaily" in obs.nota and "cloud, water" in obs.nota and "17:42 UTC" in obs.nota


def test_nube_sobre_el_lote_queda_descartada(tmp_path):
    granulo = ecostress.Granulo(ESI, "ECO_L4T_ESI", datetime(2026, 1, 13, 17, 42, tzinfo=timezone.utc), {
        "esi": escribir(tmp_path, ESI, "ESI", 0.6),
        "cloud": escribir(tmp_path, ESI, "cloud", 1, "uint8", 255)})
    obs, pct = ecostress.procesar("lote-7", LOTE, -65.2975, "esi", granulo)
    assert pct == 0 and obs.valor is None and obs.calidad == "descartada"


def test_nube_ya_en_blanco_sin_capa_de_mascara(tmp_path):
    esi = np.full((14, 14), 0.6)
    esi[:, :] = np.nan
    granulo = ecostress.Granulo(ESI, "ECO_L4T_ESI", datetime(2026, 1, 13, 17, 42, tzinfo=timezone.utc),
                                {"esi": escribir(tmp_path, ESI, "ESI", esi)})
    obs, _ = ecostress.procesar("lote-7", LOTE, -65.2975, "esi", granulo)
    assert obs.valor is None and "nube ya en blanco" in obs.nota


# ---------- de punta a punta con la NASA simulada ----------

def nasa_simulada(tmp_path, granulos_jet, granulos_esi, archivos_rotos=False):
    """Token, CMR y LP DAAC simulados: los archivos redirigen a GeoTIFF locales (como el enlace firmado)."""
    def responder(pedido):
        ruta = pedido.url.path
        if "find_or_create_token" in ruta:
            return httpx.Response(200, json={"access_token": "abc123"})
        if ruta.endswith("collections.umm_json"):
            nombre = pedido.url.params["short_name"]
            return httpx.Response(200, json={"items": [{"meta": {"concept-id": f"C-{nombre}"},
                                                        "umm": {"Version": "002"}}]})
        if ruta.endswith("granules.umm_json"):
            items = granulos_jet if pedido.url.params["collection_concept_id"] == "C-ECO_L3T_JET" else granulos_esi
            return httpx.Response(200, json={"items": items})
        assert pedido.headers["Authorization"] == "Bearer abc123"
        if archivos_rotos:
            return httpx.Response(500)
        archivo = ruta.rsplit("/", 1)[-1]
        return httpx.Response(307, headers={"location": str(tmp_path / archivo)})
    return httpx.Client(transport=httpx.MockTransport(responder))


@pytest.fixture
def credenciales(monkeypatch):
    monkeypatch.setenv("EARTHDATA_USERNAME", "usuario")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "clave")


def test_de_punta_a_punta_dos_pasadas_y_esi(tmp_path, credenciales):
    tarde = JET.replace("T174200", "T190500")
    escribir(tmp_path, JET, "ETdaily", 5.0)
    escribir(tmp_path, JET, "cloud", 1, "uint8", 255)      # la primera pasada vino nublada
    escribir(tmp_path, tarde, "ETdaily", 4.2)
    escribir(tmp_path, tarde, "cloud", 0, "uint8", 255)    # la segunda, despejada
    escribir(tmp_path, ESI, "ESI", 0.55)
    fuera = JET.replace("20260113", "20260201")             # fecha fuera del período: no se lee
    cliente = nasa_simulada(tmp_path, [
        item_cmr(JET, "2026-01-13T17:42:00Z", ["ETdaily", "cloud"]),
        item_cmr(tarde, "2026-01-13T19:05:00Z", ["ETdaily", "cloud"]),
        item_cmr(fuera, "2026-02-01T17:00:00Z", ["ETdaily"]),
    ], [item_cmr(ESI, "2026-01-13T17:42:00Z", ["ESI"], "ECO_L4T_ESI.002")])
    obs = ecostress.obtener("lote-7", LOTE, date(2026, 1, 1), date(2026, 1, 31), cliente=cliente)
    assert [(o.variable, o.fecha, o.valor, o.calidad) for o in obs] == [
        ("esi", date(2026, 1, 13), 0.55, "buena"),
        ("et_mm_dia", date(2026, 1, 13), 4.2, "buena"),
    ]
    assert "2 pasadas ese día" in obs[1].nota and "19:05 UTC" in obs[1].nota


def test_sin_pasadas_en_el_periodo_devuelve_lista_vacia(tmp_path, credenciales):
    cliente = nasa_simulada(tmp_path, [], [])
    assert ecostress.obtener("lote-7", LOTE, date(2026, 1, 1), date(2026, 1, 31), cliente=cliente) == []


def test_ningun_archivo_legible_es_error(tmp_path, credenciales):
    cliente = nasa_simulada(tmp_path, [item_cmr(JET, "2026-01-13T17:42:00Z", ["ETdaily"])], [],
                            archivos_rotos=True)
    with pytest.raises(ecostress.ErrorECOSTRESS, match="ningún archivo"):
        ecostress.obtener("lote-7", LOTE, date(2026, 1, 1), date(2026, 1, 31), cliente=cliente)


def test_un_archivo_ilegible_entre_varios_queda_descartado_sin_inventar(tmp_path, credenciales):
    escribir(tmp_path, ESI, "ESI", 0.55)
    otro = JET.replace("20260113", "20260120")  # su archivo no existe en disco
    cliente = nasa_simulada(tmp_path, [item_cmr(otro, "2026-01-20T17:00:00Z", ["ETdaily"])],
                            [item_cmr(ESI, "2026-01-13T17:42:00Z", ["ESI"], "ECO_L4T_ESI.002")])
    obs = ecostress.obtener("lote-7", LOTE, date(2026, 1, 1), date(2026, 1, 31), cliente=cliente)
    roto = [o for o in obs if o.variable == "et_mm_dia"][0]
    assert roto.valor is None and roto.calidad == "descartada" and "No se pudo leer" in roto.nota


# ---------- núcleo y API ----------

def test_se_anuncia_como_primer_respaldo_de_la_et():
    (satelite,) = ecostress.SATELITES
    assert (satelite.nombre, satelite.respaldo_de, satelite.orden) == ("ET:ECOSTRESS", "ET", 1)


def test_sin_credenciales_avisa(monkeypatch):
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)
    with pytest.raises(ecostress.earthdata.FaltanCredenciales):
        ecostress.obtener("lote-7", LOTE, date(2026, 1, 1), date(2026, 1, 31))
    r = TestClient(api.app).post("/estres-hidrico", json=dict(
        lote_id="lote-7", poligono=LOTE, desde="2026-01-01", hasta="2026-01-31"))
    assert r.status_code == 503


def test_api_poligono_invalido_responde_422():
    r = TestClient(api.app).post("/estres-hidrico", json=dict(
        lote_id="lote-7", poligono={"type": "Point", "coordinates": [0, 0]}, desde="2026-01-01", hasta="2026-01-31"))
    assert r.status_code == 422
