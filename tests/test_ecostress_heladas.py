from datetime import date, datetime, timezone

import numpy as np
import pytest
from fastapi.testclient import TestClient

from rotaterra import api
from rotaterra.fuentes import ecostress_heladas as eh

LOTE = {"type": "Polygon", "coordinates": [[
    [-65.30, -33.70], [-65.295, -33.70], [-65.295, -33.705], [-65.30, -33.705], [-65.30, -33.70]]]}
NOMBRE = "ECOv003_L2T_LSTE_46826_026_20HKH_20261008T075400_01"


# ---------- hora y noche ----------

@pytest.mark.parametrize("hora_utc, noche, fecha", [
    (datetime(2026, 10, 8, 7, 54, tzinfo=timezone.utc), True, date(2026, 10, 8)),    # 03:32 solar
    (datetime(2026, 8, 1, 3, 3, tzinfo=timezone.utc), True, date(2026, 8, 1)),       # 22:42 solar del 31/7 → noche del 1/8
    (datetime(2026, 10, 18, 19, 55, tzinfo=timezone.utc), False, date(2026, 10, 18)),  # 15:34 solar: de día
    (datetime(2026, 10, 14, 21, 27, tzinfo=timezone.utc), False, date(2026, 10, 14)),  # 17:06 solar: todavía de día
])
def test_noche_y_fecha_de_la_madrugada(hora_utc, noche, fecha):
    solar = eh.hora_solar(hora_utc, -65.2975)
    assert eh.es_de_noche(solar) == noche
    if noche:
        assert eh.noche_de(solar) == fecha


def test_capas_del_granulo():
    base = f"https://data.lpdaac.earthdatacloud.nasa.gov/lp-prod-protected/ECO_L2T_LSTE.003/{NOMBRE}/{NOMBRE}"
    capas = eh.capas_del_granulo(NOMBRE, [f"{base}_LST.tif", f"{base}_cloud.tif", f"{base}_water.tif",
                                          f"s3://x/{NOMBRE}_QC.tif", f"{base}.json"])
    assert set(capas) == {"lst", "cloud", "water"}


# ---------- cálculo ----------

def test_validos_por_rango_nube_y_agua():
    kelvin = np.array([[273.0, np.nan, 200.0, 280.0, 281.0, 360.0]])
    nube = np.array([[0, 0, 0, 1, 0, 0]], dtype="uint8")
    agua = np.array([[0, 0, 0, 0, 1, 0]], dtype="uint8")
    assert eh.pixeles_validos(kelvin, {"cloud": nube, "water": agua}).tolist() == [[True, False, False, False, False, False]]


def test_mascara_fuera_de_franja_no_es_nube():
    # 255 = la franja no pasó por ahí: no se toma como nube, pero sin temperatura igual queda inválido
    kelvin = np.array([[275.0, np.nan]])
    nube = np.array([[255, 255]], dtype="uint8")
    assert eh.pixeles_validos(kelvin, {"cloud": nube}).tolist() == [[True, False]]


def test_zonas_minima_y_parte_helada():
    kelvin = np.array([[270.15, 273.15, 276.15, 280.15],
                       [277.15, 278.15, 279.15, 250.15]])
    dentro = np.array([[True, True, True, True], [True, True, True, False]])
    validos = np.ones_like(dentro)
    lat = np.full(kelvin.shape, -33.70)
    lon = np.array([[-65.300, -65.299, -65.298, -65.297]] * 2)
    z = eh.zonas(kelvin, dentro, validos, lat, lon)
    assert z.minima == pytest.approx(-3.0) and z.maxima == pytest.approx(7.0)
    assert z.helada_pct == pytest.approx(200 / 7)  # 2 de 7 píxeles a 0 °C o menos
    assert z.lugar_mas_frio == (-33.7, -65.3)      # el píxel de -23 °C está fuera del lote y no cuenta
    assert z.validos_pct == 100.0


def test_sin_validos_no_inventa():
    z = eh.zonas(np.array([[np.nan]]), np.array([[True]]), np.array([[False]]))
    obs = eh.a_observaciones("l", date(2026, 10, 8), z, "detalle")
    assert [o.variable for o in obs] == ["temp_sup_min_70m_c", "helada_superficie_pct"]
    assert all(o.valor is None and o.calidad == "descartada" for o in obs)


@pytest.mark.parametrize("pct, calidad", [(98, "buena"), (60, "buena"), (31, "dudosa"), (10, "descartada")])
def test_calidad_por_pixeles_validos(pct, calidad):
    z = eh.Zonas(-0.2, 3.2, 4.0, 2.0, pct, (-33.70465, -65.2958))
    minima, helada = eh.a_observaciones("l", date(2026, 10, 8), z, "detalle")
    assert minima.calidad == helada.calidad == calidad
    assert minima.fuente == "ECOSTRESS" and minima.resolucion_m == 70 and minima.unidad == "°C"
    assert helada.unidad == "%"
    if calidad != "descartada":
        assert minima.valor == -0.2 and helada.valor == 2.0
        assert "riesgo de helada" in minima.nota and "no del aire" in minima.nota and "-33.70465" in minima.nota


def test_dos_pasadas_la_misma_noche_queda_la_mas_limpia():
    def par(valor, pct, dia=24):
        z = eh.Zonas(valor, valor, valor, 0.0, pct, None) if valor is not None else eh.Zonas(None, None, None, None, pct, None)
        return eh.a_observaciones("l", date(2026, 10, dia), z, "d"), pct
    elegidas = eh.quedarse_con_la_mejor([par(None, 0), par(3.4, 31), par(5.0, 25), par(6.7, 100, dia=1)])
    assert [(o.fecha.day, o.variable, o.valor) for o in elegidas] == [
        (1, "temp_sup_min_70m_c", 6.7), (1, "helada_superficie_pct", 0.0),
        (24, "temp_sup_min_70m_c", 3.4), (24, "helada_superficie_pct", 0.0)]
    assert "3 pasadas esa noche" in elegidas[2].nota


# ---------- lectura de archivos (GeoTIFF local, sin internet) ----------

def _tif(ruta, datos, dtype):
    import rasterio
    from rasterio.transform import from_origin

    # UTM 20S, píxeles de 70 m que cubren el lote de prueba con margen
    with rasterio.open(ruta, "w", driver="GTiff", height=datos.shape[0], width=datos.shape[1], count=1,
                       dtype=dtype, crs="EPSG:32720", transform=from_origin(286000, 6270000, 70, 70)) as d:
        d.write(datos.astype(dtype), 1)


def test_procesar_lee_lote_desde_archivos_locales(tmp_path):
    kelvin = np.full((40, 40), 276.15, dtype="float32")
    kelvin[25:, :] = 272.15  # la mitad sur del recorte, más fría
    nube = np.zeros((40, 40), dtype="uint8")
    _tif(tmp_path / "lst.tif", kelvin, "float32")
    _tif(tmp_path / "cloud.tif", nube, "uint8")
    granulo = eh.Granulo(NOMBRE, datetime(2026, 10, 8, 7, 54, tzinfo=timezone.utc),
                         {"lst": str(tmp_path / "lst.tif"), "cloud": str(tmp_path / "cloud.tif")})
    from rasterio.warp import transform
    xs, ys = transform("EPSG:4326", "EPSG:32720", [-65.30, -65.295], [-33.70, -33.705])
    assert 286000 < min(xs) and max(xs) < 286000 + 40 * 70 and 6270000 - 40 * 70 < min(ys) and max(ys) < 6270000
    (minima, helada), pct = eh.procesar("l", LOTE, -65.2975, granulo)
    assert pct == 100.0 and minima.fecha == date(2026, 10, 8)
    assert minima.valor in (-1.0, 3.0)
    assert 0.0 <= helada.valor <= 100.0


# ---------- API ----------

def test_api_rechaza_fechas_invertidas():
    cliente = TestClient(api.app)
    respuesta = cliente.post("/heladas-por-zona", json={"lote_id": "l", "poligono": LOTE,
                                                        "desde": "2026-10-10", "hasta": "2026-10-01"})
    assert respuesta.status_code == 422


def test_registrado_como_fuente_propia():
    assert [s.nombre for s in eh.SATELITES] == ["ECOSTRESS_LST"] and eh.SATELITES[0].respaldo_de is None
