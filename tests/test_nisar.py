from datetime import date, datetime, timezone

import h5py
import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from rotaterra import api
from rotaterra.fuentes import nisar

LOTE = {"type": "Polygon", "coordinates": [[
    [-65.30, -33.70], [-65.295, -33.70], [-65.295, -33.705], [-65.30, -33.705], [-65.30, -33.70]]]}
NOMBRE = "NISAR_L2_PR_GCOV_032_140_D_105_2005_DHDH_A_20261009T222453_20261009T222527_P05023_N_F_J_001"


def _gcov(ruta, hh=0.15, hv=0.025, relleno_en=None):
    """Archivo GCOV chico: grilla UTM 20S de 20 m que cubre el lote de prueba con margen."""
    xs = 286500 + 20 * np.arange(60) + 10.0
    ys = 6269000 - 20 * np.arange(60) - 10.0
    with h5py.File(ruta, "w") as f:
        g = f.create_group(nisar.GRILLA)
        g["projection"] = np.uint32(32720)
        g["xCoordinates"], g["yCoordinates"] = xs, ys
        g["HHHH"] = np.full((60, 60), hh, dtype="float32")
        g["HVHV"] = np.full((60, 60), hv, dtype="float32")
        mascara = np.zeros((60, 60), dtype="uint8")
        if relleno_en is not None:
            mascara[relleno_en] = nisar.RELLENO_MASCARA
        g["mask"] = mascara
        i = f.create_group(nisar.IDENTIFICACION)
        i["orbitPassDirection"], i["trackNumber"] = b"Descending", np.uint32(140)


# ---------- cálculo ----------

def test_ventana_cubre_la_caja_y_afuera_da_none():
    xs, ys = np.arange(0, 200, 20) + 10.0, 200 - np.arange(0, 200, 20) - 10.0
    filas, columnas = nisar.ventana(xs, ys, (45, 45, 95, 95), margen=0)
    assert xs[columnas].min() <= 45 and xs[columnas].max() >= 95
    assert nisar.ventana(xs, ys, (1000, 1000, 1100, 1100)) is None


def test_resumen_en_db_sobre_la_potencia_del_lote():
    potencia = np.array([[0.1, 0.1, 1.0, np.nan, 0.0]])
    dentro = np.array([[True, True, False, True, True]])
    valor, pct = nisar.resumir_capa(potencia, dentro, None)
    assert valor == pytest.approx(-10.0) and pct == 50.0  # 2 de 4 píxeles del lote con dato; el de 1.0 está afuera


def test_relleno_de_mascara_no_cuenta():
    potencia = np.full((1, 3), 0.1)
    valor, pct = nisar.resumir_capa(potencia, np.ones((1, 3), bool), np.array([[0, 255, 255]]))
    assert valor == pytest.approx(-10.0) and pct == pytest.approx(100 / 3)


@pytest.mark.parametrize("pct, calidad", [(100, "dudosa"), (40, "dudosa"), (10, "descartada")])
def test_provisional_nunca_es_buena(pct, calidad):
    obs = nisar.a_observacion("l", date(2026, 10, 9), "radar_hh_db", -8.1, pct, "detalle")
    assert obs.calidad == calidad and obs.fuente == "NISAR" and obs.resolucion_m == 20 and obs.unidad == "dB"
    assert (obs.valor is None) == (calidad == "descartada")
    assert ("parcialmente" in obs.nota) == (pct == 40)


# ---------- lectura de archivo local ----------

def test_procesar_archivo_local(tmp_path):
    ruta = tmp_path / "gcov.h5"
    _gcov(ruta)
    granulo = nisar.Granulo(NOMBRE, "NISAR_L2_GCOV_PROVISIONAL_V1",
                            datetime(2026, 10, 9, 22, 24, tzinfo=timezone.utc), str(ruta))
    (hh, hv), pct = nisar.procesar("l", LOTE, -65.2975, granulo)
    assert pct == 100.0 and hh.fecha == date(2026, 10, 9)  # 22:24 UTC = 18:03 hora solar del mismo día
    assert hh.variable == "radar_hh_db" and hh.valor == pytest.approx(-8.24, abs=0.01)
    assert hv.variable == "radar_hv_db" and hv.valor == pytest.approx(-16.02, abs=0.01)
    assert "PROVISIONAL" in hh.nota and "descendente" in hh.nota and "traza 140" in hh.nota and "HV − HH -7.8" in hh.nota


def test_lote_fuera_de_la_imagen_queda_descartado(tmp_path):
    ruta = tmp_path / "gcov.h5"
    _gcov(ruta)
    lejos = {"type": "Polygon", "coordinates": [[[-60.0, -30.0], [-59.99, -30.0], [-59.99, -30.01], [-60.0, -30.0]]]}
    granulo = nisar.Granulo(NOMBRE, "NISAR_L2_GCOV_V1", datetime(2026, 10, 9, 22, 24, tzinfo=timezone.utc), str(ruta))
    par, pct = nisar.procesar("l", lejos, -60.0, granulo)
    assert pct == 0.0 and all(o.valor is None and o.calidad == "descartada" for o in par)
    assert "PROVISIONAL" not in par[0].nota


# ---------- lectura remota por pedazos ----------

def test_archivo_remoto_lee_por_rangos_y_sigue_la_redireccion(tmp_path):
    ruta = tmp_path / "gcov.h5"
    _gcov(ruta)
    contenido = ruta.read_bytes()
    pedidos = []

    def responder(pedido: httpx.Request) -> httpx.Response:
        if pedido.url.host == "nisar.asf.earthdatacloud.nasa.gov":
            assert pedido.headers["authorization"] == "Bearer t"
            return httpx.Response(303, headers={"location": "https://cdn.example/archivo.h5?Signature=x"})
        assert "authorization" not in pedido.headers  # el token no viaja a CloudFront
        inicio, fin = map(int, pedido.headers["range"].removeprefix("bytes=").split("-"))
        pedidos.append((inicio, fin))
        return httpx.Response(206, content=contenido[inicio:fin + 1],
                              headers={"content-range": f"bytes {inicio}-{fin}/{len(contenido)}"})

    transporte = httpx.MockTransport(responder)
    cliente = httpx.Client(transport=transporte, headers={"Authorization": "Bearer t"})
    archivo = nisar.ArchivoRemoto(cliente, "https://nisar.asf.earthdatacloud.nasa.gov/x.h5", bloque=4096,
                                  sin_token=httpx.Client(transport=transporte))
    datos = nisar.leer(archivo, LOTE)
    assert datos["dentro"].any() and datos["pasada"]["trackNumber"] == "140"
    assert archivo.tamano == len(contenido) and len(pedidos) >= 2


# ---------- registro y API ----------

def test_dos_imagenes_la_misma_fecha_queda_la_que_mas_cubre():
    def par(valor, pct):
        return [nisar.a_observacion("l", date(2026, 10, 9), v, valor, pct, "d") for v in nisar.CAPAS], pct
    elegidas = nisar.quedarse_con_la_mejor([par(None, 0), par(-9.0, 50), par(-8.0, 100)])
    assert [o.valor for o in elegidas] == [-8.0, -8.0]


def test_registrado_y_api_valida():
    assert [s.nombre for s in nisar.SATELITES] == ["NISAR"] and nisar.SATELITES[0].respaldo_de is None
    respuesta = TestClient(api.app).post("/radar", json={"lote_id": "l", "poligono": LOTE,
                                                         "desde": "2026-10-10", "hasta": "2026-10-01"})
    assert respuesta.status_code == 422
