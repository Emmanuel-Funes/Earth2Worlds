import io
from datetime import date

import h5py
import httpx
import numpy as np
import pytest

from rotaterra.fuentes import smap_nrt

URL_DATOS = "https://data.nsidc.earthdatacloud.nasa.gov/nsidc-cumulus-prod-protected/SMAP/SPL2SMP_NRT/107/2026/10/16/"


@pytest.fixture
def credenciales(monkeypatch):
    monkeypatch.setenv("EARTHDATA_USERNAME", "usuario")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "clave")


def archivo_h5(celdas):
    """Pasada sintética con el formato real de SPL2SMP_NRT: (lat, lon, humedad, calidad, hora UTC) por celda."""
    buffer = io.BytesIO()
    with h5py.File(buffer, "w") as archivo:
        g = archivo.create_group(smap_nrt.GRUPO)
        g["latitude"] = np.array([c[0] for c in celdas], dtype="float32")
        g["longitude"] = np.array([c[1] for c in celdas], dtype="float32")
        g["soil_moisture"] = np.array([c[2] for c in celdas], dtype="float32")
        g["retrieval_qual_flag"] = np.array([c[3] for c in celdas], dtype="uint16")
        g["surface_flag"] = np.zeros(len(celdas), dtype="uint16")
        g["tb_time_utc"] = np.array([c[4].encode() for c in celdas], dtype="S24")
    return buffer.getvalue()


# en la pasada real del 16/10/2026 la celda del lote de San Luis tenía centro en -33,629; -65,166 (a 15 km)
CERCA = (-33.629246, -65.16598)
LEJOS = (-31.0, -63.0)


def test_lee_la_celda_mas_cercana():
    contenido = archivo_h5([(*LEJOS, 0.30, 0, "2026-10-16T10:04:00.000Z"),
                            (*CERCA, 0.1835, 8, "2026-10-16T10:05:19.819Z")])
    lectura = smap_nrt.leer_celda(contenido, -33.70, -65.30)
    assert lectura["humedad"] == pytest.approx(0.1835) and lectura["hora"] == "2026-10-16T10:05:19.819Z"
    assert 14 < lectura["distancia_km"] < 16


def test_pasada_que_no_cubre_el_lote():
    assert smap_nrt.leer_celda(archivo_h5([(*LEJOS, 0.3, 0, "2026-10-16T10:04:00.000Z")]), -33.70, -65.30) is None


def test_archivo_ilegible_da_error():
    with pytest.raises(smap_nrt.ErrorSMAPNRT):
        smap_nrt.leer_celda(b"<html>login</html>", -33.70, -65.30)


def test_dia_local_argentino():
    assert smap_nrt.dia_local("2026-10-16T10:05:19.819Z") == date(2026, 10, 16)
    assert smap_nrt.dia_local("2026-10-16T01:30:00.000Z") == date(2026, 10, 15)  # 22:30 del 15 en Argentina


def lectura(humedad, calidad=8, hora="2026-10-16T10:05:19.819Z"):
    return {"humedad": humedad, "calidad": calidad, "superficie": 0, "hora": hora, "distancia_km": 15.0}


def test_valor_recomendado_es_dudoso_y_regional():
    o = smap_nrt.a_observacion("lote-7", date(2026, 10, 16), [lectura(0.1835)])
    assert (o.valor, o.calidad, o.fuente, o.resolucion_m, o.unidad) == (0.1835, "dudosa", "SMAP_NRT", 36000, "m³/m³")
    assert "36 km" in o.nota and "10:05 UTC" in o.nota


def test_valor_no_recomendado_se_descarta():
    o = smap_nrt.a_observacion("lote-7", date(2026, 10, 15), [lectura(0.15, calidad=13)])
    assert o.valor is None and o.calidad == "descartada" and "no recomienda" in o.nota


def test_relleno_y_fuera_de_rango_no_cuentan():
    o = smap_nrt.a_observacion("lote-7", date(2026, 10, 16), [lectura(-9999.0), lectura(0.7)])
    assert o.valor is None and o.calidad == "descartada"


def test_dos_pasadas_se_promedian():
    o = smap_nrt.a_observacion("lote-7", date(2026, 10, 16),
                               [lectura(0.18), lectura(0.20, hora="2026-10-16T22:30:00.000Z")])
    assert o.valor == 0.19 and "2 de 2 pasadas" in o.nota


def test_dia_sin_pasada_se_descarta():
    o = smap_nrt.a_observacion("lote-7", date(2026, 10, 17), [])
    assert o.valor is None and o.calidad == "descartada" and "no pasó" in o.nota


def nasa_simulada(pedidos, granulos):
    """granulos: nombre -> contenido h5."""

    def responder(request: httpx.Request) -> httpx.Response:
        pedidos.append(request)
        if "find_or_create_token" in str(request.url):
            return httpx.Response(200, json={"access_token": "token"})
        if "granules.umm_json" in str(request.url):
            items = [{"umm": {"RelatedUrls": [{"URL": URL_DATOS + n}, {"URL": URL_DATOS + n + ".iso.xml"},
                                              {"URL": "s3://bucket/" + n}]}} for n in granulos]
            return httpx.Response(200, json={"items": items})
        nombre = request.url.path.rsplit("/", 1)[-1]
        if nombre in granulos:
            return httpx.Response(200, content=granulos[nombre])
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(responder))


def test_obtener_humedad_un_valor_por_dia(credenciales):
    granulos = {
        "SMAP_L2_SM_P_NRT_62534_D_20261016T092826_N19241_001.h5":
            archivo_h5([(*CERCA, 0.1835, 8, "2026-10-16T10:05:19.819Z")]),
        "SMAP_L2_SM_P_NRT_62528_A_20261015T224825_N19241_001.h5":
            archivo_h5([(*LEJOS, 0.3, 0, "2026-10-15T23:00:00.000Z")]),
        # la NASA rehizo la pasada con más datos: se usa la _002
        "SMAP_L2_SM_P_NRT_62528_A_20261015T224825_N19241_002.h5":
            archivo_h5([(*CERCA, 0.21, 0, "2026-10-15T23:06:00.000Z")]),
    }
    pedidos = []
    obs = smap_nrt.obtener_humedad("lote-7", -33.70, -65.30, date(2026, 10, 15), date(2026, 10, 17),
                                   nasa_simulada(pedidos, granulos))
    assert [(o.fecha, o.valor, o.calidad) for o in obs] == [
        (date(2026, 10, 15), 0.21, "dudosa"), (date(2026, 10, 16), 0.1835, "dudosa"),
        (date(2026, 10, 17), None, "descartada")]
    bajados = sorted(p.url.path.rsplit("/", 1)[-1] for p in pedidos if p.url.path.endswith(".h5"))
    assert bajados == ["SMAP_L2_SM_P_NRT_62528_A_20261015T224825_N19241_002.h5",
                       "SMAP_L2_SM_P_NRT_62534_D_20261016T092826_N19241_001.h5"]
    cmr = next(p for p in pedidos if "granules" in str(p.url))
    # día local del 15 al 17 = 15 a las 03:00 UTC hasta el 18 a las 03:00 UTC
    assert cmr.url.params["temporal"] == "2026-10-15T03:00:00Z,2026-10-18T03:00:00Z"
    assert cmr.url.params["point"] == "-65.3,-33.7"


def test_falla_de_la_nasa_da_error(credenciales):
    def responder(request):
        if "find_or_create_token" in str(request.url):
            return httpx.Response(200, json={"access_token": "token"})
        return httpx.Response(503)

    with pytest.raises(smap_nrt.ErrorSMAPNRT):
        smap_nrt.obtener_humedad("lote-7", -33.70, -65.30, date(2026, 10, 15), date(2026, 10, 16),
                                 httpx.Client(transport=httpx.MockTransport(responder)))


def test_sin_credenciales(monkeypatch):
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)
    with pytest.raises(smap_nrt.earthdata.FaltanCredenciales):
        smap_nrt.obtener_humedad("lote-7", -33.70, -65.30, date(2026, 10, 15), date(2026, 10, 16),
                                 nasa_simulada([], {}))


def test_rango_de_fechas():
    with pytest.raises(ValueError):
        smap_nrt.validar_pedido(-33.7, -65.3, date(2026, 10, 16), date(2026, 10, 15))
    with pytest.raises(ValueError):
        smap_nrt.validar_pedido(-33.7, -65.3, date(2026, 1, 1), date(2026, 10, 15))


def test_se_declara_como_respaldo_del_dia_de_smap():
    [s] = smap_nrt.SATELITES
    assert (s.nombre, s.respaldo_de, s.al_dia) == ("SMAP:SMAP_NRT", "SMAP", True)
