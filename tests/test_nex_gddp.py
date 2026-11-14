from datetime import date, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from rotaterra import api
from rotaterra.fuentes import nex_gddp as nx


def test_celda_del_lote_de_prueba():
    # verificado contra la respuesta real de NCSS: GridPointRequestedAt[33.700S_65.300W] → -33.625, -65.375
    assert nx.celda(-33.7025, -65.2975) == (-33.625, 294.625)
    assert nx.celda(-33.70, -65.40) == (-33.625, 294.625)
    with pytest.raises(ValueError):
        nx.validar_punto(-70.0, -65.0)


def test_elegir_archivos_toma_la_version_mas_nueva():
    catalogo = ('name="pr_day_X_ssp245_r1i1p1f1_gn_2050.nc" name="pr_day_X_ssp245_r1i1p1f1_gn_2050_v1.1.nc" '
                'name="pr_day_X_ssp245_r1i1p1f1_gn_2050_v2.0.nc" name="pr_day_X_ssp245_r1i1p1f1_gn_2051.nc"')
    assert nx.elegir_archivos(catalogo) == {2050: "pr_day_X_ssp245_r1i1p1f1_gn_2050_v2.0.nc",
                                           2051: "pr_day_X_ssp245_r1i1p1f1_gn_2051.nc"}


def test_leer_csv_pasa_a_celsius_y_mm():
    texto = ('time,station,latitude[unit="degrees_north"],longitude[unit="degrees_east"],tasmax[unit="K"]\n'
             '2050-01-01T12:00:00Z,GridPointRequestedAt[33.700S_65.300W],-33.625,294.625,299.96124\n'
             '2050-01-02T12:00:00Z,GridPointRequestedAt[33.700S_65.300W],-33.625,294.625,NaN\n')
    valores, punto = nx.leer_csv(texto, "tasmax")
    assert valores == {date(2050, 1, 1): pytest.approx(26.81124)} and punto == (-33.625, 294.625)
    lluvia, _ = nx.leer_csv(texto.replace("299.96124", "0.0005"), "pr")
    assert lluvia[date(2050, 1, 1)] == pytest.approx(43.2)


def _serie(primero, ultimo, tx, tn, pr):
    dias = [date(primero, 1, 1) + timedelta(days=i) for i in range((date(ultimo, 12, 31) - date(primero, 1, 1)).days + 1)]
    return {"tasmax": {d: tx(d) for d in dias}, "tasmin": {d: tn(d) for d in dias}, "pr": {d: pr(d) for d in dias}}


def test_indicadores_por_anio():
    serie = _serie(2001, 2002, tx=lambda d: 36.0 if d.month == 1 and d.day <= 10 else 25.0,
                   tn=lambda d: -1.0 if d.month == 7 and d.day <= 5 else 8.0,
                   pr=lambda d: 60.0 if d.day == 15 and d.month == 2 else (2.0 if d.day % 10 == 0 else 0.0))
    r = nx.indicadores_por_anio(serie, 2001, 2002)
    assert r["dias_calor_35"] == [10, 10] and r["dias_helada_aire"] == [5, 5]
    assert r["dias_lluvia_extrema_50"] == [1, 1]
    assert len(r["lluvia_campana_mm"]) == 1 and len(r["tmax_verano_c"]) == 1  # la campaña 2002/03 queda afuera
    assert r["racha_seca_campana_dias"] == [17]  # 21/2 al 9/3


def test_un_hueco_no_achica_las_sumas():
    serie = _serie(2001, 2002, tx=lambda d: 25.0, tn=lambda d: 8.0, pr=lambda d: 1.0)
    del serie["pr"][date(2001, 11, 5)]
    r = nx.indicadores_por_anio(serie, 2001, 2002)
    assert r["lluvia_campana_mm"] == [] and len(r["lluvia_anual_mm"]) == 1  # 2001 queda afuera, 2002 cuenta


def test_resumen_modelo_pide_casi_todos_los_anios():
    completo = {k: [1.0] * 20 for k in nx.INDICADORES}
    assert nx.resumen_modelo(completo, 20)["dias_calor_35"] == 1.0
    assert nx.resumen_modelo({k: [1.0] * 17 for k in nx.INDICADORES}, 20) is None


def test_observaciones_mediana_cambio_y_modelo_faltante():
    hist = {m: {"dias_calor_35": v} for m, v in zip(nx.MODELOS, (5.0, 6.0, 7.0))}
    fut = {"ACCESS-CM2": {"dias_calor_35": 12.0}, "MPI-ESM1-2-HR": {"dias_calor_35": 9.0}, "MRI-ESM2-0": None}
    obs = nx.a_observaciones("l", {"historico": hist, "ssp245": fut, "ssp585": {m: None for m in nx.MODELOS}},
                             (-33.625, 294.625))
    por = {o.variable: o for o in obs}
    assert len(obs) == len(nx.INDICADORES) * 3
    h = por["dias_calor_35_historico"]
    assert h.valor == 6.0 and h.calidad == "dudosa" and h.fuente == "NEX_GDDP" and h.fecha == date(2014, 12, 31)
    f = por["dias_calor_35_ssp245"]
    assert f.valor == 10.5 and "+5.0 (de +3.0 a +7.0)" in f.nota and "sin MRI-ESM2-0" in f.nota and "-65.375" in f.nota
    assert "no pronóstico" in f.nota and f.resolucion_m == 25000
    assert por["dias_calor_35_ssp585"].valor is None and por["dias_calor_35_ssp585"].calidad == "descartada"
    assert por["lluvia_anual_mm_historico"].calidad == "descartada"  # ningún modelo trajo ese indicador


def test_calcula_una_vez_por_celda(monkeypatch):
    llamadas = []

    def falso(lat, lon360, cliente, hilos=nx.HILOS):
        llamadas.append((lat, lon360))
        return {p: {m: {"dias_calor_35": 1.0} for m in nx.MODELOS} for p in nx.PERIODOS}, (lat, lon360)

    monkeypatch.setattr(nx, "_MEMORIA", {})
    monkeypatch.setattr(nx, "calcular_celda", falso)
    nx.obtener_clima_futuro("a", -33.7025, -65.2975, cliente=object())
    nx.obtener_clima_futuro("b", -33.70, -65.30, cliente=object())
    assert llamadas == [(-33.625, 294.625)]


def test_sin_ningun_anio_no_inventa(monkeypatch):
    monkeypatch.setattr(nx, "archivos", lambda c, m, e, v: ("r1i1p1f1", {a: "x.nc" for a in range(1995, 2061)}))

    def corta(*a, **k):
        raise httpx.ConnectError("reset")

    monkeypatch.setattr(nx, "pedir_anio", corta)
    with pytest.raises(nx.ErrorNEXGDDP):
        nx.calcular_celda(-33.625, 294.625, cliente=object(), hilos=2)


def test_ruta_valida_el_punto():
    respuesta = TestClient(api.app).get("/clima-futuro", params={"lat": -75, "lon": -65})
    assert respuesta.status_code == 422
