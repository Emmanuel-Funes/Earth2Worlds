import base64
from datetime import date

import httpx
import numpy as np
import pytest

from rotaterra.fuentes import modis_nrt
from rotaterra.geo import poligono_desde_esquinas

# lote de prueba de ~50 ha alrededor de -33,7025; -65,2975
POLIGONO = poligono_desde_esquinas("-33.699, -65.301; -33.699, -65.294; -33.706, -65.294; -33.706, -65.301")
NOMBRE = "MOD13Q4N.A2026289.h12v12.061.2026289213651.NRT.hdf"
URL = f"https://nrt3.modaps.eosdis.nasa.gov/api/v2/content/archives/allData/61/MOD13Q4N/2026/289/{NOMBRE}"


@pytest.fixture
def credenciales(monkeypatch):
    monkeypatch.setenv("EARTHDATA_USERNAME", "usuario")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "clave")


def ventana_sintetica(ndvi=6000, confiabilidad=0, dia=288):
    h, v, f0, f1, c0, c1 = modis_nrt.ventana(POLIGONO)
    lat, lon = modis_nrt.coordenadas(h, v, f0, f1, c0, c1)
    forma = lat.shape
    datos = {"ndvi": np.full(forma, ndvi, dtype=float), "confiabilidad": np.full(forma, confiabilidad, dtype=float),
             "dia": np.full(forma, dia, dtype=float)}
    return datos, lat, lon


def resumir(datos, lat, lon, desde=date(2026, 10, 9), hasta=date(2026, 10, 17)):
    return modis_nrt.resumir("lote-7", POLIGONO, datos, lat, lon, date(2026, 10, 16), NOMBRE, desde, hasta)


def adentro(lat, lon):
    from shapely.geometry import Point, shape

    lote = shape(POLIGONO)
    return [(i, j) for i in range(lat.shape[0]) for j in range(lat.shape[1])
            if lote.contains(Point(lon[i, j], lat[i, j]))]


def test_celda_del_lote_de_prueba():
    # misma grilla que el MOD13Q1 de la spec 007, verificada contra la NASA: mosaico h12v12, píxel (1777, 2724)
    assert modis_nrt.celda(-33.7025, -65.2975) == (12, 12, 1777, 2724)


def test_fecha_del_archivo_es_el_ultimo_dia_del_compuesto():
    assert modis_nrt.fecha_archivo(NOMBRE) == date(2026, 10, 16)


def test_dia_limpio_es_dudoso_y_usa_el_dia_de_adquisicion():
    [o] = resumir(*ventana_sintetica())
    assert (o.valor, o.calidad, o.fecha, o.fuente, o.resolucion_m) == (0.6, "dudosa", date(2026, 10, 15), "MODIS_NRT", 250)
    assert "0,07 a 0,14" in o.nota and "compuesto del 2026-10-09 al 2026-10-16" in o.nota


def test_nubes_descartan_y_no_inventan():
    [o] = resumir(*ventana_sintetica(confiabilidad=3))
    assert (o.valor, o.calidad, o.fecha) == (None, "descartada", date(2026, 10, 16))
    assert "Nubes" in o.nota


def test_nubes_fuera_del_periodo_no_devuelven_nada():
    assert resumir(*ventana_sintetica(confiabilidad=3), hasta=date(2026, 10, 15)) == []


def test_un_valor_por_cada_dia_que_vio_el_satelite():
    datos, lat, lon = ventana_sintetica()
    celdas = adentro(lat, lon)
    for i, j in celdas[: len(celdas) // 2]:
        datos["dia"][i, j], datos["ndvi"][i, j] = 284, 4000
    viejo, nuevo = resumir(datos, lat, lon)
    assert (viejo.fecha, viejo.valor, nuevo.fecha, nuevo.valor) == (date(2026, 10, 11), 0.4, date(2026, 10, 15), 0.6)
    assert "píxeles vistos este día 44%" in viejo.nota


def test_dias_fuera_del_pedido_se_dejan_afuera():
    datos, lat, lon = ventana_sintetica()
    celdas = adentro(lat, lon)
    for i, j in celdas[: len(celdas) // 2]:
        datos["dia"][i, j] = 284
    [o] = resumir(datos, lat, lon, desde=date(2026, 10, 14))
    assert o.fecha == date(2026, 10, 15)


def test_compuesto_que_cruza_el_anio():
    datos, lat, lon = ventana_sintetica(dia=364)
    [o] = modis_nrt.resumir("lote-7", POLIGONO, datos, lat, lon, date(2027, 1, 2),
                            "MOD13Q4N.A2027002.h12v12.061.2027002213651.NRT.hdf", date(2026, 12, 25), date(2027, 1, 2))
    assert o.fecha == date(2026, 12, 30)


def test_relleno_no_cuenta_como_valido():
    [o] = resumir(*ventana_sintetica(ndvi=modis_nrt.RELLENO_NDVI))
    assert o.valor is None and o.calidad == "descartada"


def archivo_hdf(ruta, f0, f1, c0, c1, ndvi=5500, confiabilidad=0, dia=288):
    """HDF4 chico con las tres capas: la ventana del lote cae dentro (el resto queda en relleno)."""
    from pyhdf.SD import SD, SDC

    alto, ancho = f1 + 2, c1 + 2
    archivo = SD(str(ruta), SDC.WRITE | SDC.CREATE)
    for capa, tipo, valor, relleno in [(modis_nrt.CAPAS["ndvi"], SDC.INT16, ndvi, -3000),
                                       (modis_nrt.CAPAS["confiabilidad"], SDC.INT8, confiabilidad, -1),
                                       (modis_nrt.CAPAS["dia"], SDC.INT16, dia, -1)]:
        sds = archivo.create(capa, tipo, (alto, ancho))
        datos = np.full((alto, ancho), relleno, dtype={SDC.INT16: np.int16, SDC.INT8: np.int8}[tipo])
        datos[f0:f1 + 1, c0:c1 + 1] = valor
        sds[:] = datos
        sds.endaccess()
    archivo.end()


def test_leer_ventana_del_hdf(tmp_path):
    _, _, f0, f1, c0, c1 = modis_nrt.ventana(POLIGONO)
    archivo_hdf(tmp_path / "a.hdf", f0, f1, c0, c1)
    datos = modis_nrt.leer_ventana(str(tmp_path / "a.hdf"), f0, f1, c0, c1)
    assert datos["ndvi"].shape == (f1 - f0 + 1, c1 - c0 + 1) and (datos["ndvi"] == 5500).all()


def test_archivo_ilegible_da_error(tmp_path):
    (tmp_path / "a.hdf").write_text("<html>login</html>")
    with pytest.raises(modis_nrt.ErrorMODISNRT):
        modis_nrt.leer_ventana(str(tmp_path / "a.hdf"), 0, 1, 0, 1)


def nasa_simulada(tmp_path, pedidos, archivos=(NOMBRE,), html=False):
    _, _, f0, f1, c0, c1 = modis_nrt.ventana(POLIGONO)
    archivo_hdf(tmp_path / "lance.hdf", f0, f1, c0, c1)
    contenido = (tmp_path / "lance.hdf").read_bytes()

    def responder(request: httpx.Request) -> httpx.Response:
        pedidos.append(request)
        url = str(request.url)
        if "granules.umm_json" in url:
            items = [{"umm": {"RelatedUrls": [{"URL": URL.replace(NOMBRE, n)}, {"URL": "https://www.earthdata.nasa.gov/x"}]}}
                     for n in archivos]
            return httpx.Response(200, json={"items": items})
        if request.url.host == "nrt3.modaps.eosdis.nasa.gov" and "/api/v2/" in url:
            if "sesion=ok" in request.headers.get("cookie", ""):
                if html:
                    return httpx.Response(200, text="<html>Earthdata Login</html>", headers={"content-type": "text/html"})
                return httpx.Response(200, content=contenido, headers={"content-type": "application/octet-stream"})
            return httpx.Response(302, headers={"location": "/oauth/login?redirect=x"})
        if url.startswith("https://nrt3.modaps.eosdis.nasa.gov/oauth/login"):
            return httpx.Response(302, headers={"location": "https://urs.earthdata.nasa.gov/oauth/authorize?client_id=x"})
        if request.url.host == "urs.earthdata.nasa.gov":
            esperado = "Basic " + base64.b64encode(b"usuario:clave").decode()
            if request.headers.get("authorization") != esperado:
                return httpx.Response(401)
            return httpx.Response(302, headers={"location": "https://nrt3.modaps.eosdis.nasa.gov/oauth/callback?code=c"})
        if "/oauth/callback" in url:
            return httpx.Response(302, headers={"location": URL, "set-cookie": "sesion=ok; Path=/"})
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(responder))


def test_obtener_ndvi_inicia_sesion_en_lance_y_lee_el_lote(tmp_path, credenciales):
    pedidos = []
    cliente = nasa_simulada(tmp_path, pedidos)
    [o] = modis_nrt.obtener_ndvi("lote-7", POLIGONO, date(2026, 10, 9), date(2026, 10, 17), cliente)
    assert (o.fecha, o.valor, o.calidad, o.fuente) == (date(2026, 10, 15), 0.55, "dudosa", "MODIS_NRT")
    # el usuario y la contraseña van solo a Earthdata
    con_clave = {p.url.host for p in pedidos if p.headers.get("authorization", "").startswith("Basic")}
    assert con_clave == {"urs.earthdata.nasa.gov"}


def test_usa_el_archivo_mas_nuevo_hasta_la_fecha_pedida(tmp_path, credenciales):
    pedidos = []
    otros = ("MOD13Q4N.A2026288.h12v12.061.2026288211955.NRT.hdf", NOMBRE,
             "MOD13Q4N.A2026290.h12v12.061.2026290211955.NRT.hdf", "MOD13Q4N.A2026289.h12v13.061.2026289213651.NRT.hdf")
    cliente = nasa_simulada(tmp_path, pedidos, archivos=otros)
    modis_nrt.obtener_ndvi("lote-7", POLIGONO, date(2026, 10, 9), date(2026, 10, 16), cliente)
    bajados = [p.url.path for p in pedidos if p.url.path.endswith(".hdf")]
    assert bajados[-1].endswith(NOMBRE)


def test_sin_archivos_devuelve_vacio(tmp_path, credenciales):
    cliente = nasa_simulada(tmp_path, [], archivos=())
    assert modis_nrt.obtener_ndvi("lote-7", POLIGONO, date(2026, 10, 9), date(2026, 10, 16), cliente) == []


def test_pagina_en_vez_de_archivo_da_error(tmp_path, credenciales):
    cliente = nasa_simulada(tmp_path, [], html=True)
    with pytest.raises(modis_nrt.ErrorMODISNRT):
        modis_nrt.obtener_ndvi("lote-7", POLIGONO, date(2026, 10, 9), date(2026, 10, 16), cliente)


def test_sin_credenciales(monkeypatch, tmp_path):
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)
    with pytest.raises(modis_nrt.earthdata.FaltanCredenciales):
        modis_nrt.obtener_ndvi("lote-7", POLIGONO, date(2026, 10, 9), date(2026, 10, 16), nasa_simulada(tmp_path, []))


def test_se_declara_como_respaldo_del_dia_de_hls():
    [s] = modis_nrt.SATELITES
    assert (s.nombre, s.respaldo_de, s.al_dia) == ("HLS:MODIS_NRT", "HLS", True)


def test_endpoint_rechaza_fechas_al_reves():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(modis_nrt.router)
    r = TestClient(app).post("/ndvi/modis-nrt", json={"lote_id": "l", "poligono": POLIGONO,
                                                     "desde": "2026-10-16", "hasta": "2026-10-09"})
    assert r.status_code == 422
