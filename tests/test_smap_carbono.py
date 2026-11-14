from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from rotaterra import api
from rotaterra.fuentes import earthdata
from rotaterra.fuentes import smap_carbono as sc

LOTE = {"type": "Polygon", "coordinates": [[
    [-65.30, -33.70], [-65.295, -33.70], [-65.295, -33.705], [-65.30, -33.705], [-65.30, -33.70]]]}
NOMBRE = "SMAP_L4_C_mdl_20261015T000000_Vv8043_001.h5_PpqDJbbz"


def test_celda_del_lote_de_prueba():
    # verificado contra GEO/latitude y GEO/longitude del archivo real: centro de celda -33,671; -65,306
    assert sc.celda(-33.7025, -65.2975) == (1262, 1228)
    with pytest.raises(ValueError):
        sc.celda(-89.9, 0.0)


def test_fecha_del_nombre():
    assert sc.fecha_del_granulo(NOMBRE) == date(2026, 10, 15)
    with pytest.raises(ValueError):
        sc.fecha_del_granulo("sin_fecha.h5")


def test_expresion_pide_todas_las_capas_con_dos_columnas():
    expr = sc.expresion(1262, 1228)
    assert expr.count(";") == 3 and "/GPP/gpp_mean[1262:1:1262][1228:1:1229]" in expr and "gpp_pft8_mean" in expr


def test_valores_de_toma_la_primera_columna():
    crudo = {"GPP/gpp_mean": [[2.037, 1.9]], "NEE/nee_mean": [[0.718, 0.7]],
             "GPP/gpp_pft7_mean": [[2.054, 2.0]], "GPP/gpp_pft8_mean": [[1.877, 1.8]]}
    valores, cultivos = sc.valores_de(crudo)
    assert valores == {"gpp_g_c_m2_dia": 2.037, "nee_g_c_m2_dia": 0.718}
    assert cultivos == {"cereales": 2.054, "latifoliadas": 1.877}


@pytest.mark.parametrize("valor, maximo, negativo, ok", [
    (2.0, 30, False, True), (-9999.0, 30, False, False), (-0.1, 30, False, False), (45.0, 30, False, False),
    (-3.0, 30, True, True), (None, 30, True, False), (float("nan"), 30, False, False)])
def test_valido(valor, maximo, negativo, ok):
    assert sc.valido(valor, maximo, negativo) == ok


def test_observaciones_y_relleno_no_inventa():
    obs = sc.a_observaciones("l", date(2026, 10, 15), {"gpp_g_c_m2_dia": 2.0372, "nee_g_c_m2_dia": -9999.0},
                             {"cereales": 2.054, "latifoliadas": -9999.0}, "detalle")
    gpp, nee = obs
    assert gpp.valor == 2.037 and gpp.calidad == "buena" and gpp.fuente == "SMAP" and gpp.resolucion_m == 9000
    assert gpp.unidad == "g C/m²/día" and "no del lote" in gpp.nota and "cereales 2.05" in gpp.nota
    assert "latifoliadas" not in gpp.nota
    assert nee.valor is None and nee.calidad == "descartada"


def test_reintenta_cuando_opendap_corta():
    llamadas = []

    def responder(pedido: httpx.Request) -> httpx.Response:
        llamadas.append(1)
        if len(llamadas) < 3:
            return httpx.Response(502)
        texto = "Dataset: x\n/GPP/gpp_mean[0][0], 2.037, 1.9\n/NEE/nee_mean[0][0], 0.718, 0.7\n"
        return httpx.Response(200, text=texto)

    cliente = httpx.Client(transport=httpx.MockTransport(responder))
    granulo = sc.Granulo(NOMBRE, date(2026, 10, 15), "https://opendap.earthdata.nasa.gov/x")
    sc.ESPERA_S, espera = 0.0, sc.ESPERA_S
    try:
        gpp, nee = sc.procesar("l", granulo, 1262, 1228, cliente)
    finally:
        sc.ESPERA_S = espera
    assert len(llamadas) == 3 and gpp.valor == 2.037 and nee.valor == 0.718


def test_obtener_con_cmr_y_opendap_simulados(monkeypatch):
    monkeypatch.setattr(earthdata, "cliente_autorizado", lambda c=None: c)
    monkeypatch.setattr(earthdata, "coleccion_vigente", lambda c, n: "C1-NSIDC")
    monkeypatch.setattr(earthdata, "archivos", lambda c, col, d, h: [
        (NOMBRE, "https://opendap/a"), (NOMBRE.replace("1015", "1016"), "https://opendap/b")])
    monkeypatch.setattr(earthdata, "leer_csv", lambda c, url, e: (
        {"GPP/gpp_mean": [[2.0, 0]], "NEE/nee_mean": [[0.5, 0]]} if url.endswith("a") else {"GPP/gpp_mean": [[-9999.0, 0]]}))
    obs = sc.obtener("l", LOTE, date(2026, 10, 15), date(2026, 10, 16), cliente=object(), hilos=1)
    assert [(o.fecha.day, o.variable, o.valor) for o in obs] == [
        (15, "gpp_g_c_m2_dia", 2.0), (15, "nee_g_c_m2_dia", 0.5),
        (16, "gpp_g_c_m2_dia", None), (16, "nee_g_c_m2_dia", None)]


def test_registrado_y_api_valida():
    assert [s.nombre for s in sc.SATELITES] == ["SMAP_L4C"] and sc.SATELITES[0].respaldo_de is None
    respuesta = TestClient(api.app).post("/productividad", json={"lote_id": "l", "poligono": LOTE,
                                                                 "desde": "2026-10-10", "hasta": "2026-10-01"})
    assert respuesta.status_code == 422
