from datetime import date

import httpx
import numpy as np
import pytest

from rotaterra.fuentes import modis
from rotaterra.geo import poligono_desde_esquinas

# lote de prueba de ~50 ha alrededor de -33,7025; -65,2975
POLIGONO = poligono_desde_esquinas("-33.699, -65.301; -33.699, -65.294; -33.706, -65.294; -33.706, -65.301")


@pytest.fixture
def credenciales(monkeypatch):
    monkeypatch.setenv("EARTHDATA_USERNAME", "usuario")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "clave")


def test_celda_del_lote_de_prueba():
    # verificado contra la NASA: mosaico h12v12, píxel (1777, 2724) con centro en -33,703; -65,298
    assert modis.celda(-33.7025, -65.2975) == (12, 12, 1777, 2724)


def ventana_sintetica(ndvi=6000, confiabilidad=0, dia=9):
    """Ventana de 6 × 6 píxeles centrada en el lote, con coordenadas reales de la grilla."""
    h, v, f0, f1, c0, c1 = modis.ventana(POLIGONO)
    filas, columnas = np.arange(f0, f1 + 1), np.arange(c0, c1 + 1)
    y = modis._Y0 - v * modis._MOSAICO - (filas[:, None] + 0.5) * modis._PIXEL + 0 * columnas[None, :]
    x = modis._X0 + h * modis._MOSAICO + (columnas[None, :] + 0.5) * modis._PIXEL + 0 * filas[:, None]
    lat = np.degrees(y / modis._R)
    lon = np.degrees(x / (modis._R * np.cos(np.radians(lat))))
    forma = lat.shape
    return {"ndvi": np.full(forma, ndvi, dtype=float), "confiabilidad": np.full(forma, confiabilidad, dtype=float),
            "dia": np.full(forma, dia, dtype=float), "lat": lat, "lon": lon}


def test_compuesto_limpio_es_bueno_y_usa_el_dia_de_adquisicion():
    o = modis.resumir("lote-7", POLIGONO, ventana_sintetica(), date(2026, 1, 1))
    assert (o.valor, o.calidad, o.fecha, o.fuente, o.resolucion_m) == (0.6, "buena", date(2026, 1, 9), "MODIS", 250)
    assert "Respaldo de HLS" in o.nota and "válidos 100%" in o.nota


def test_nubes_descartan_y_no_inventan():
    o = modis.resumir("lote-7", POLIGONO, ventana_sintetica(confiabilidad=3), date(2026, 1, 1))
    assert o.valor is None and o.calidad == "descartada"


def test_lote_parcialmente_nublado_es_dudoso():
    from shapely.geometry import Point, shape

    datos = ventana_sintetica()
    lote = shape(POLIGONO)
    adentro = [(i, j) for i in range(datos["lat"].shape[0]) for j in range(datos["lat"].shape[1])
               if lote.contains(Point(datos["lon"][i, j], datos["lat"][i, j]))]
    for i, j in adentro[: len(adentro) // 2]:  # la mitad del lote nublada
        datos["confiabilidad"][i, j] = 3
    o = modis.resumir("lote-7", POLIGONO, datos, date(2026, 1, 1))
    assert o.calidad == "dudosa" and o.valor == 0.6


def test_compuesto_que_cruza_el_anio():
    o = modis.resumir("lote-7", POLIGONO, ventana_sintetica(dia=2), date(2025, 12, 19))
    assert o.fecha == date(2026, 1, 2)


def test_lote_menor_a_un_pixel_usa_el_del_centro():
    chico = poligono_desde_esquinas("-33.7024, -65.2976; -33.7024, -65.2974; -33.7026, -65.2974; -33.7026, -65.2976")
    datos = ventana_sintetica()
    o = modis.resumir("lote-7", chico, datos, date(2026, 1, 1))
    assert o.valor == 0.6 and "menor a un píxel" in o.nota


class NASAFalsa:
    def __init__(self, datos):
        self.datos = datos

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        url = str(pedido.url)
        if "find_or_create_token" in url:
            return httpx.Response(200, json={"access_token": "tk"})
        if "/collections.umm_json" in url:
            return httpx.Response(200, json={"items": [{"meta": {"concept-id": "C-MOD"}, "umm": {"Version": "061"}}]})
        if "/granules.umm_json" in url:
            nombres = ["MOD13Q1.A2026001.h12v12.061.1", "MOD13Q1.A2026001.h12v13.061.1"]  # el segundo es otro mosaico
            return httpx.Response(200, json={"items": [{"umm": {"GranuleUR": n, "RelatedUrls": [
                {"URL": f"https://opendap.earthdata.nasa.gov/collections/C-MOD/granules/{n}"}]}} for n in nombres]})
        if ".dap.csv" in url:
            assert "h12v12" in url
            lineas = ["Dataset: x"]
            for nombre, ruta in modis.CAPAS.items():
                for i, fila in enumerate(self.datos[nombre]):
                    lineas.append(f"{ruta}[{i}], " + ", ".join(repr(float(v)) for v in fila))
            return httpx.Response(200, text="\n".join(lineas) + "\n")
        return httpx.Response(404)


def test_obtener_ndvi_de_punta_a_punta(credenciales):
    cliente = httpx.Client(transport=httpx.MockTransport(NASAFalsa(ventana_sintetica(ndvi=7300))))
    obs = modis.obtener_ndvi("lote-7", POLIGONO, date(2026, 1, 1), date(2026, 1, 31), cliente=cliente)
    assert [(o.fecha, o.valor, o.calidad) for o in obs] == [(date(2026, 1, 9), 0.73, "buena")]


def test_se_registra_como_tercer_respaldo_de_hls():
    (satelite,) = modis.SATELITES
    assert (satelite.nombre, satelite.respaldo_de, satelite.orden) == ("HLS:MODIS", "HLS", 3)
