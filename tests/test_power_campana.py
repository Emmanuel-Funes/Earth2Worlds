import statistics
from datetime import date, timedelta

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rotaterra.fuentes import power_campana as pc

LAT, LON = -33.7025, -65.2975
HOY = date(2026, 10, 15)
DESDE, HASTA = date(1991, 1, 1), date(2025, 12, 31)


def dias(desde: date, hasta: date) -> list[date]:
    return [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]


def tmin_sintetica(desde: date = DESDE, hasta: date = HASTA) -> dict[date, float]:
    """5 °C todo el año, con una helada el 28/8 (primavera) y otra el 5/6 (otoño) de cada año."""
    serie = {}
    for d in dias(desde, hasta):
        serie[d] = -1.0 if (d.month, d.day) in ((8, 28), (6, 5)) else 5.0
    return serie


def clave(d: date) -> str:
    return d.strftime("%Y%m%d")


def respuesta_power(parametros: list[str], desde: date, hasta: date, faltantes: set[date] = frozenset()) -> dict:
    tmin = tmin_sintetica(desde, hasta)
    valores = {
        "T2M_MIN": lambda d: tmin[d],
        "T2M_MAX": lambda d: 25.0,
        "PRECTOTCORR": lambda d: 3.0,
        "TSOIL1": lambda d: 15.0 if (d.month, d.day) >= (10, 5) or d.month <= 3 else 8.0,
    }
    return {"properties": {"parameter": {
        p: {clave(d): (-999.0 if d in faltantes else valores[p](d)) for d in dias(desde, hasta)} for p in parametros}}}


def transporte_power(faltantes: set[date] = frozenset(), suelo_roto: bool = False) -> httpx.MockTransport:
    def responder(pedido: httpx.Request) -> httpx.Response:
        assert pedido.url.host == "power.larc.nasa.gov"
        q = pedido.url.params
        parametros = q["parameters"].split(",")
        assert q["community"] == "AG"
        if parametros == ["TSOIL1"] and suelo_roto:
            return httpx.Response(500, text="error")
        desde = date(int(q["start"][:4]), int(q["start"][4:6]), int(q["start"][6:]))
        hasta = date(int(q["end"][:4]), int(q["end"][4:6]), int(q["end"][6:]))
        return httpx.Response(200, json=respuesta_power(parametros, desde, hasta, faltantes))
    return httpx.MockTransport(responder)


def por_variable(observaciones) -> dict:
    return {o.variable: o for o in observaciones}


# ---------- reglas sin red ----------

def test_periodo_son_los_35_anios_completos_mas_recientes():
    assert pc.periodo(HOY) == (DESDE, HASTA)


def test_percentil_interpola_como_la_investigacion():
    assert pc.percentil([1, 2, 3, 4, 5], 20) == pytest.approx(1.8)
    assert pc.percentil([10], 80) == 10


def test_dd_mm_usa_un_anio_no_bisiesto():
    assert pc.dd_mm(250) == "07/09"
    assert pc.dd_mm(278) == "05/10"


def test_heladas_con_fechas_conocidas():
    h = pc.heladas(tmin_sintetica(), 1991, 2025, 0.0)
    assert len(h["libres"]) == 34
    esperado = [(date(a + 1, 6, 5) - date(a, 8, 28)).days - 1 for a in range(1991, 2025)]
    assert h["libres"] == esperado
    assert set(h["ultimas"]) <= {240, 241}  # 28/8 (241 en bisiesto)
    assert set(h["primeras"]) == {156, 157}  # 5/6
    assert h["sin_helada"] == 0


def test_sin_helada_se_usa_el_borde_de_la_temporada():
    serie = {d: 5.0 for d in dias(date(2000, 7, 1), date(2001, 6, 30))}
    h = pc.heladas(serie, 2000, 2001, 0.0)
    assert h["ultimas"] == [pc.dia_del_anio(date(2000, 7, 1))]
    assert h["primeras"] == [pc.dia_del_anio(date(2001, 6, 30))]
    assert h["sin_helada"] == 2


def test_campana_con_mas_del_5_por_ciento_sin_dato_no_cuenta():
    serie = tmin_sintetica(date(2000, 1, 1), date(2002, 12, 31))
    for d in dias(date(2000, 9, 1), date(2000, 10, 31)):  # 61 días > 5 % de 365
        serie[d] = None
    h = pc.heladas(serie, 2000, 2002, 0.0)
    assert len(h["libres"]) == 1  # solo 2001/02


def test_el_umbral_de_menos_dos_no_cuenta_una_minima_de_menos_uno():
    h = pc.heladas(tmin_sintetica(date(2000, 1, 1), date(2001, 12, 31)), 2000, 2001, -2.0)
    assert h["sin_helada"] == 2


def test_sumas_de_campana_piden_la_campana_completa():
    serie = {d: 3.0 for d in dias(date(2000, 10, 1), date(2002, 3, 31))}
    calor = {d: 20.0 for d in serie}
    frio = {d: 10.0 for d in serie}
    lluvia = dict(serie)
    lluvia[date(2001, 1, 10)] = None
    s = pc.sumas_de_campana(frio, calor, lluvia, 2000, 2002)
    assert s["lluvias"] == [pytest.approx(3.0 * 182)]  # 2000/01 queda afuera por un día sin dato
    assert s["grados"] == [pytest.approx(5.0 * 182), pytest.approx(5.0 * 182)]


def test_fecha_de_suelo_pide_diez_dias_seguidos():
    serie = {d: 8.0 for d in dias(date(2010, 7, 1), date(2010, 12, 31))}
    for d in dias(date(2010, 9, 1), date(2010, 9, 5)):  # cinco días calientes no alcanzan
        serie[d] = 16.0
    for d in dias(date(2010, 10, 5), date(2010, 12, 31)):
        serie[d] = 16.0
    assert pc.fechas_de_suelo(serie, 2010, 2010, 14.0) == [pc.dia_del_anio(date(2010, 10, 5))]
    serie[date(2010, 10, 8)] = None  # un día sin dato corta la racha
    assert pc.fechas_de_suelo(serie, 2010, 2010, 14.0) == [pc.dia_del_anio(date(2010, 10, 9))]


def test_extremos_calor_lluvia_y_racha():
    tmax = {d: (36.0 if d.month == 1 and d.day <= 4 else 30.0) for d in dias(date(2001, 1, 1), date(2002, 12, 31))}
    lluvia = {d: (60.0 if (d.month, d.day) == (2, 1) else (0.0 if d.month == 11 else 5.0)) for d in tmax}
    ext = pc.extremos(tmax, lluvia, 2001, 2002)
    assert ext["calor"] == [(2001, 4), (2002, 4)] and ext["extrema"] == [(2001, 1), (2002, 1)]
    assert ext["racha"] == [(2001, 30)]  # noviembre entero seco; la campaña 2002/03 no está completa
    tmax[date(2001, 3, 1)] = None  # un día sin dato no suma ni descarta el año
    assert pc.extremos(tmax, None, 2001, 2001)["calor"] == [(2001, 4)]
    for d in dias(date(2002, 1, 1), date(2002, 1, 31)):  # más del 5 % sin dato: el año no cuenta
        tmax[d] = None
    assert pc.extremos(tmax, None, 2001, 2002)["calor"] == [(2001, 4)]


def test_tendencia_primeros_contra_ultimos_diez():
    serie = [(1991 + i, float(i // 10)) for i in range(35)]
    assert pc.tendencia(serie) == "; promedio 1991-2000: 0.0, 2016-2025: 2.5"
    assert pc.tendencia(serie[:15]) == ""


# ---------- con POWER simulado ----------

def test_clima_de_la_campana_completo():
    cliente = httpx.Client(transport=transporte_power())
    obs = pc.obtener_clima_campana("lote-7", LAT, LON, cliente, HOY)
    v = por_variable(obs)
    assert set(v) == {"dias_libres_heladas", "ultima_helada_primavera_p80", "primera_helada_otono_p20",
                      "lluvia_campana_mm_p50", "lluvia_campana_mm_p20", "grados_dia_campana",
                      "suelo_14c_fecha_mediana", "dias_calor_35_anio", "dias_lluvia_extrema_50_anio",
                      "racha_seca_campana_dias"}
    for o in obs:
        assert o.fuente == "POWER" and o.resolucion_m == 55000 and o.fecha == HASTA and o.calidad == "buena"
        assert o.lote_id == "lote-7" and "REGIONAL" in o.nota
    libres = [(date(a + 1, 6, 5) - date(a, 8, 28)).days - 1 for a in range(1991, 2025)]
    assert v["dias_libres_heladas"].valor == round(pc.percentil(libres, 20))
    assert v["dias_libres_heladas"].unidad == "días"
    assert f"mediana {statistics.median(libres):.0f} días" in v["dias_libres_heladas"].nota and "34 campañas" in v["dias_libres_heladas"].nota
    assert v["ultima_helada_primavera_p80"].unidad == "día del año"
    assert v["lluvia_campana_mm_p50"].valor == pytest.approx(round(3.0 * 182), abs=3)
    assert v["grados_dia_campana"].valor == pytest.approx(round(5.0 * 182), abs=5)
    assert v["suelo_14c_fecha_mediana"].valor in (278, 279)
    assert "≥ 10 °C: mediana 05/10" in v["suelo_14c_fecha_mediana"].nota  # el suelo sintético salta de 8 a 15 °C
    assert v["dias_calor_35_anio"].valor == 0 and v["racha_seca_campana_dias"].valor == 0  # 25 °C y 3 mm todos los días
    assert "35 años (1991-2025)" in v["dias_calor_35_anio"].nota and "piso" in v["dias_lluvia_extrema_50_anio"].nota


def test_dias_sin_dato_de_power_dejan_el_dato_dudoso():
    faltantes = {d for d in dias(date(1991, 1, 1), date(2010, 12, 31)) if d.month in (9, 10)}
    cliente = httpx.Client(transport=transporte_power(faltantes))
    v = por_variable(pc.obtener_clima_campana("lote-7", LAT, LON, cliente, HOY))
    assert v["dias_libres_heladas"].calidad == "dudosa"
    assert "solo 14 campañas"  # 1991/92 a 2010/11 quedan afuera in v["dias_libres_heladas"].nota
    assert v["lluvia_campana_mm_p50"].calidad == "dudosa"


def test_si_falla_el_suelo_el_resto_sale_igual():
    cliente = httpx.Client(transport=transporte_power(suelo_roto=True))
    v = por_variable(pc.obtener_clima_campana("lote-7", LAT, LON, cliente, HOY))
    assert v["dias_libres_heladas"].calidad == "buena"
    suelo = v["suelo_14c_fecha_mediana"]
    assert suelo.valor is None and suelo.calidad == "descartada"
    assert "no devolvió la temperatura del suelo" in suelo.nota


def test_power_caido_es_un_error_para_que_entre_el_respaldo():
    cliente = httpx.Client(transport=httpx.MockTransport(lambda p: httpx.Response(503, text="caído")))
    with pytest.raises(pc.ErrorClimaCampana):
        pc.obtener_clima_campana("lote-7", LAT, LON, cliente, HOY)


def test_latitud_imposible():
    with pytest.raises(ValueError):
        pc.obtener_clima_campana("lote-7", 95, LON, httpx.Client(), HOY)


# ---------- respaldo MERRA-2 simulado ----------

def texto_merra2(desde: date, hasta: date) -> str:
    lineas = ["Title:,MERRA-2 T2M", "User Start Date:,1991-01-01T00:00:00", "", "Timestamp (UTC),Data"]
    for d in dias(desde, hasta):
        helada = (d.month, d.day) in ((8, 28), (6, 5))
        for hora in range(24):
            kelvin = (272.15 if helada and hora == 9 else 278.15) if hora < 12 else 298.15
            lineas.append(f"{d.isoformat()}T{hora:02d}:30:00,{kelvin}")
    lineas.append("2000-01-01T00:30:00,-9999.0")
    return "\n".join(lineas)


def transporte_merra2(pedidos: list) -> httpx.MockTransport:
    def responder(pedido: httpx.Request) -> httpx.Response:
        if pedido.url.host == "urs.earthdata.nasa.gov":
            return httpx.Response(200, json={"access_token": "token-de-prueba"})
        assert pedido.url.host == "api.giovanni.earthdata.nasa.gov"
        assert pedido.headers["Authorization"] == "Bearer token-de-prueba"
        q = pedido.url.params
        assert q["data"] == pc.VARIABLE_MERRA2 and q["location"] == f"[{LAT},{LON}]"
        inicio, fin = q["time"].split("/")
        pedidos.append(inicio)
        desde, hasta = date.fromisoformat(inicio[:10]), date.fromisoformat(fin[:10])
        return httpx.Response(200, text=texto_merra2(desde, hasta))
    return httpx.MockTransport(responder)


def test_leer_serie_horaria_ignora_encabezados_y_relleno():
    horas = pc.leer_serie_horaria("Timestamp (UTC),Data\n2020-01-01T00:30:00,280.5\n2020-01-01T01:30:00,-9999\n"
                                  "2020-01-01T02:30:00\t281.0\nfin")
    assert horas == {date(2020, 1, 1): [280.5, 281.0]}


def test_respaldo_merra2_da_heladas_y_grados_sin_lluvia(monkeypatch):
    monkeypatch.setenv("EARTHDATA_USERNAME", "usuario")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "clave")
    pedidos = []
    cliente = httpx.Client(transport=transporte_merra2(pedidos))
    v = por_variable(pc.obtener_clima_campana_merra2("lote-7", LAT, LON, cliente, HOY))
    assert len(pedidos) == 7  # 35 años en tramos de 5
    libres = [(date(a + 1, 6, 5) - date(a, 8, 28)).days - 1 for a in range(1991, 2025)]
    assert v["dias_libres_heladas"].valor == round(pc.percentil(libres, 20))
    assert v["dias_libres_heladas"].fuente == "MERRA2" and v["dias_libres_heladas"].calidad == "buena"
    assert v["grados_dia_campana"].valor == pytest.approx(round(5.0 * 182), abs=5)  # (25 + 5) / 2 - 10
    assert v["dias_calor_35_anio"].fuente == "MERRA2" and v["dias_calor_35_anio"].valor == 0
    for variable in ("lluvia_campana_mm_p50", "lluvia_campana_mm_p20", "suelo_14c_fecha_mediana",
                     "dias_lluvia_extrema_50_anio", "racha_seca_campana_dias"):
        assert v[variable].valor is None and v[variable].calidad == "descartada"
        assert "no trae lluvia" in v[variable].nota


def test_respaldo_sin_credenciales(monkeypatch):
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)
    with pytest.raises(pc.earthdata.FaltanCredenciales):
        pc.obtener_clima_campana_merra2("lote-7", LAT, LON, httpx.Client(), HOY)


# ---------- conexión con el núcleo y endpoint de prueba ----------

def test_satelites_declarados():
    nombres = {s.nombre: s for s in pc.SATELITES}
    assert set(nombres) == {"POWER_CAMPANA", "POWER_CAMPANA:MERRA2"}
    assert nombres["POWER_CAMPANA:MERRA2"].respaldo_de == "POWER_CAMPANA"


def test_endpoint_rechaza_latitud_imposible():
    app = FastAPI()
    app.include_router(pc.router)
    respuesta = TestClient(app).get("/clima-campana", params={"lat": 95, "lon": LON})
    assert respuesta.status_code == 422


def test_endpoint_con_power_caido_responde_502(monkeypatch):
    def caido(*args, **kwargs):
        raise pc.ErrorClimaCampana("POWER caído")
    monkeypatch.setattr(pc, "obtener_clima_campana", caido)
    app = FastAPI()
    app.include_router(pc.router)
    respuesta = TestClient(app).get("/clima-campana", params={"lat": LAT, "lon": LON})
    assert respuesta.status_code == 502 and "POWER caído" in respuesta.json()["detail"]
