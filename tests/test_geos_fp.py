"""GEOS-FP, respaldo "del día" de POWER (spec 043): tests sin internet con un servidor OPeNDAP simulado."""

import re
from urllib.parse import unquote
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest

from rotaterra.fuentes import geos_fp

ULTIMA = datetime(2026, 10, 15, 14, 30, tzinfo=timezone.utc)  # como la medición del 15/10/2026: 9 h de atraso
LARGO = 110_000
LAT, LON = -33.7025, -65.2975


def valor(variable: str, hora: datetime) -> float:
    if variable == "t2m":
        return 273.15 + 10 + hora.hour  # en °C: 10 + hora UTC
    if variable == "swgdn":
        return 500.0
    if variable == "evland":
        return 0.1 / 3600  # 0,1 mm por hora
    return 1 / 3600  # prectot: 1 mm por hora


def servidor(pedidos: list, relleno_en: datetime | None = None):
    def responder(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        pedidos.append(url)
        if url.endswith(".das"):
            maximo = f"{ULTIMA:%H:%Mz%d}{ULTIMA:%b}".lower() + f"{ULTIMA:%Y}"
            return httpx.Response(200, text=f'Attributes {{\n time {{\n String units "days since 1-1-1";\n'
                                            f'  String maximum "{maximo}";\n }}\n}}')
        if url.endswith(".dds"):
            return httpx.Response(200, text=f"Dataset {{\n Grid {{\n  Float32 t2m[time = {LARGO}][lat = 721]"
                                            f"[lon = 1152];\n }} t2m;\n}} x;")
        m = re.search(r"\.ascii\?(\w+)\[(\d+):(\d+)\]\[(\d+)\]\[(\d+)\]", unquote(url))
        variable, i_ini, i_fin = m.group(1), int(m.group(2)), int(m.group(3))
        lineas = [f"{variable}, [{i_fin - i_ini + 1}][1][1]"]
        for i in range(i_ini, i_fin + 1):
            hora = ULTIMA - timedelta(hours=LARGO - 1 - i)
            v = 9.999e14 if hora == relleno_en else valor(variable, hora)
            lineas += [f"[{i - i_ini}][0], {v}", ""]  # el servidor deja una línea en blanco entre horas
        lineas += ["", f"time, [{i_fin - i_ini + 1}]", "739000.5, 739000.54", "lat, [1]", "-33.75", "lon, [1]",
                   "-65.3125"]
        return httpx.Response(200, text="\n".join(lineas))
    return httpx.Client(transport=httpx.MockTransport(responder))


def por_dia(observaciones):
    return {(o.fecha, o.variable): o for o in observaciones}


def test_celda_del_lote_de_san_luis():
    assert geos_fp.celda(LAT, LON) == (225, 367)


def test_lee_solo_la_variable_y_no_las_coordenadas():
    texto = "t2m, [2][1][1]\n[0][0], 288.5\n\n[1][0], 9.999E14\n\ntime, [2]\n739000.5, 739000.54\nlon, [1]\n-65.31"
    assert geos_fp.leer_ascii(texto) == [288.5, None]


def test_dia_completo_y_dia_en_curso():
    pedidos = []
    obs = por_dia(geos_fp.obtener_clima("lote-7", LAT, LON, date(2026, 10, 14), date(2026, 10, 15),
                                        servidor(pedidos)))
    ayer = obs[(date(2026, 10, 14), "temp_max")]
    assert ayer.calidad == "buena" and ayer.fuente == "GEOS_FP" and ayer.unidad == "°C"
    # día local 14/10 = de las 03:30 UTC del 14 a las 02:30 UTC del 15 → máx 10 + 23, mín 10 + 0
    assert ayer.valor == pytest.approx(33.0) and obs[(date(2026, 10, 14), "temp_min")].valor == pytest.approx(10.0)
    assert obs[(date(2026, 10, 14), "radiacion")].valor == pytest.approx(500 * 3600 * 24 / 1e6)
    assert obs[(date(2026, 10, 14), "lluvia_mm")].valor == pytest.approx(24.0)
    assert obs[(date(2026, 10, 14), "lluvia_mm")].calidad == "dudosa"  # la lluvia de un modelo es orientativa
    # hoy: de 03:30 a 14:30 UTC = 12 horas
    hoy_max = obs[(date(2026, 10, 15), "temp_max")]
    assert hoy_max.calidad == "dudosa" and hoy_max.valor == pytest.approx(24.0)
    assert "12 de 24 horas" in hoy_max.nota and "15:00 UTC" in hoy_max.nota
    radiacion_hoy = obs[(date(2026, 10, 15), "radiacion")]
    assert radiacion_hoy.valor is None and radiacion_hoy.calidad == "descartada"  # la suma quedaría corta
    assert obs[(date(2026, 10, 15), "lluvia_mm")].valor == pytest.approx(12.0)
    assert sum(".ascii" in p for p in pedidos) == 9  # 36 horas en bloques de 12, por cada una de las 3 variables


def test_dia_que_todavia_no_se_publico():
    obs = geos_fp.obtener_clima("lote-7", LAT, LON, date(2026, 10, 16), date(2026, 10, 16), servidor([]))
    assert {o.calidad for o in obs} == {"descartada"} and all(o.valor is None for o in obs)
    assert "todavía no publicó" in obs[0].nota


def test_hora_con_relleno_no_inventa():
    hueco = datetime(2026, 10, 14, 10, 30, tzinfo=timezone.utc)
    obs = por_dia(geos_fp.obtener_clima("lote-7", LAT, LON, date(2026, 10, 14), date(2026, 10, 14),
                                        servidor([], relleno_en=hueco)))
    assert obs[(date(2026, 10, 14), "radiacion")].valor is None  # falta una hora: no se suma
    assert obs[(date(2026, 10, 14), "temp_max")].calidad == "dudosa"


def test_servidor_caido():
    def caido(request):
        return httpx.Response(503)
    with pytest.raises(geos_fp.ErrorGEOSFP):
        geos_fp.obtener_clima("lote-7", LAT, LON, date(2026, 10, 14), date(2026, 10, 14),
                              httpx.Client(transport=httpx.MockTransport(caido)))


def test_se_anuncia_como_respaldo_del_dia_de_power_y_de_et():
    clima, et = geos_fp.SATELITES
    assert (clima.nombre, clima.respaldo_de, clima.al_dia) == ("POWER:GEOS_FP", "POWER", True)
    assert (et.nombre, et.respaldo_de, et.al_dia) == ("ET:GEOS_FP", "ET", True)


def test_evapotranspiracion_del_dia():
    pedidos = []
    obs = por_dia(geos_fp.obtener_et("lote-7", LAT, LON, date(2026, 10, 14), date(2026, 10, 15), servidor(pedidos)))
    ayer = obs[(date(2026, 10, 14), "et_mm_dia")]
    assert ayer.valor == pytest.approx(2.4) and ayer.unidad == "mm/día" and ayer.fuente == "GEOS_FP"
    assert ayer.calidad == "dudosa" and "MODIS" in ayer.nota and "orientativa" in ayer.nota  # modelo de 28 km
    hoy = obs[(date(2026, 10, 15), "et_mm_dia")]
    assert hoy.valor is None and hoy.calidad == "descartada" and "12 de 24 horas" in hoy.nota  # suma corta
    assert all("tavg1_2d_lnd_Nx" in p for p in pedidos)


def test_evapotranspiracion_con_una_hora_sin_dato_no_inventa():
    hueco = datetime(2026, 10, 14, 10, 30, tzinfo=timezone.utc)
    obs = geos_fp.obtener_et("lote-7", LAT, LON, date(2026, 10, 14), date(2026, 10, 14),
                             servidor([], relleno_en=hueco))
    assert obs[0].valor is None and obs[0].calidad == "descartada" and "23 de 24 horas" in obs[0].nota


def test_ruta_de_prueba_de_evapotranspiracion():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.include_router(geos_fp.router)
    r = TestClient(app).get("/et/geos-fp", params={"lote_id": "x", "lat": 95, "lon": 0, "desde": "2026-10-14",
                                                     "hasta": "2026-10-14"})
    assert r.status_code == 422


def test_reintenta_si_el_servidor_tarda_demasiado():
    pedidos, fallados = [], []
    normal = servidor(pedidos)

    def a_veces_504(request):
        if ".ascii" in str(request.url) and not fallados:
            fallados.append(request.url)
            return httpx.Response(504)
        return normal.get(str(request.url))

    obs = geos_fp.obtener_clima("lote-7", LAT, LON, date(2026, 10, 14), date(2026, 10, 14),
                                httpx.Client(transport=httpx.MockTransport(a_veces_504)))
    assert fallados and obs[0].valor == pytest.approx(33.0)
