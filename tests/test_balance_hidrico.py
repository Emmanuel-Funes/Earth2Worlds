"""Balance hídrico propio con NASA POWER (spec 024), sin internet."""

from datetime import date, timedelta

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rotaterra.fuentes import balance_hidrico as b

# ---------- ET0 y el paso diario ----------


def test_et0_ejemplo_18_de_fao56_bruselas():
    # Bruselas, 50°48' N, 100 m, 6 de julio: el manual da ET0 = 3,9 mm/día
    assert round(b.et0_fao56(21.5, 12.3, 1.409, 2.078, 22.07, 50 + 48 / 60, 187, 100), 1) == 3.9


def test_paso_diario_sin_estres_consume_todo_lo_que_pide_el_cultivo():
    agua, etr, excedente = b.paso_diario(agua=200, capacidad=260, lluvia=10, etc=4)
    assert (agua, etr, excedente) == (206, 4, 0)


def test_paso_diario_con_estres_reduce_la_etr_con_ks():
    # umbral = (1 - 0,7) × 200 = 60 mm; con 30 mm, Ks = 0,5 → ETR = 2 mm
    agua, etr, _ = b.paso_diario(agua=30, capacidad=200, lluvia=0, etc=4)
    assert etr == pytest.approx(2.0)
    assert agua == pytest.approx(28.0)


def test_paso_diario_lo_que_pasa_la_capacidad_es_excedente():
    agua, _, excedente = b.paso_diario(agua=250, capacidad=260, lluvia=30, etc=4)
    assert agua == 260
    assert excedente == pytest.approx(16.0)


def test_paso_diario_nunca_baja_de_cero():
    agua, etr, _ = b.paso_diario(agua=0.5, capacidad=160, lluvia=0, etc=8)
    assert agua >= 0
    assert etr <= 0.5


def test_decadas_como_sepa():
    assert b.decadas(date(2026, 2, 5), date(2026, 3, 10)) == [
        (date(2026, 2, 1), date(2026, 2, 10), 1), (date(2026, 2, 11), date(2026, 2, 20), 2),
        (date(2026, 2, 21), date(2026, 2, 28), 3), (date(2026, 3, 1), date(2026, 3, 10), 1)]


def test_textura_con_tildes_y_mayusculas():
    assert b.normalizar_textura(" Franco  Arenoso ") == "franco arenoso"
    assert b.normalizar_textura("Arcilloso") == "arcilloso"
    assert b.capacidad_mm("franco arenoso") == 182  # 0,13 × 2.000 mm × 70 % que exploran las raíces


def test_en_invierno_el_kc_baja_a_la_mitad():
    assert b.kc_del_dia(0.5, date(2026, 7, 1)) == 0.25
    assert b.kc_del_dia(0.5, date(2026, 10, 1)) == 0.5


# ---------- POWER → balance por década ----------

def series_constantes(desde: date, hasta: date, lluvia=0.0, faltan=()):
    """Clima de POWER parejo: T 25/10 °C, rocío 8 °C, viento 2 m/s, radiación 20 MJ/m²."""
    valores = dict(T2M_MAX=25.0, T2M_MIN=10.0, T2MDEW=8.0, RH2M=50.0, WS2M=2.0, ALLSKY_SFC_SW_DWN=20.0,
                   PRECTOTCORR=lluvia)
    series = {p: {} for p in b.PARAMETROS}
    dia = desde
    while dia <= hasta:
        clave = dia.strftime("%Y%m%d")
        for p, v in valores.items():
            series[p][clave] = b.VALOR_RELLENO if dia in faltan else v
        dia += timedelta(days=1)
    return series


def imerg_igual(lat, lon, dias):
    """IMERG simulado que no corrige nada: la lluvia queda igual a la de POWER."""
    return {d.strftime("%Y%m%d"): 1000.0 for d in dias}


def respuesta_power(desde, hasta, **cambios):
    inicio = desde - timedelta(days=b.ARRANQUE_DIAS)
    cuerpo = {"geometry": {"coordinates": [-65.3, -33.7, 600.0]},
              "properties": {"parameter": series_constantes(inicio, hasta, **cambios)}}
    pedidos = []

    def responder(pedido):
        pedidos.append(pedido)
        return httpx.Response(200, json=cuerpo)
    return httpx.Client(transport=httpx.MockTransport(responder)), pedidos


def test_balance_por_decada_con_las_cuatro_variables(monkeypatch):
    monkeypatch.setattr(b, "CALIBRADO", True)
    desde, hasta = date(2026, 9, 1), date(2026, 9, 20)
    cliente, pedidos = respuesta_power(desde, hasta, lluvia=1.0)
    obs = b.obtener_balance("lote-1", -33.7, -65.3, desde, hasta, textura="franco arenoso", cliente=cliente,
                            leer_imerg=imerg_igual)
    assert pedidos[0].url.params["start"] == "20250901"  # un año de arranque
    assert {o.fecha for o in obs} == {date(2026, 9, 10), date(2026, 9, 20)}
    por = {(o.variable, o.fecha): o for o in obs}
    agua = por["agua_disponible_2m", date(2026, 9, 20)]
    assert agua.unidad == "mm" and agua.fuente == "POWER" and agua.calidad == "buena"
    assert 0 <= agua.valor <= 182
    assert por["agua_suelo_porcentaje", date(2026, 9, 20)].valor == pytest.approx(100 * agua.valor / 182, abs=0.1)
    assert "franco arenoso, 182 mm de agua útil en 2 m" in agua.nota and "Kc 0,5" in agua.nota
    assert "la menor entre POWER" in agua.nota and "calibrado contra 87 décadas de SEPA" in agua.nota
    # un año con 1 mm/día y ET mucho mayor: el suelo está seco y la planta transpira menos de lo que pide
    assert por["confort_hidrico_balance", date(2026, 9, 20)].valor < 100
    assert por["excedente_balance_mm", date(2026, 9, 20)].valor == 0


def test_mucha_lluvia_llena_el_suelo_y_da_excedente():
    desde, hasta = date(2026, 1, 1), date(2026, 1, 10)
    cliente, _ = respuesta_power(desde, hasta, lluvia=20.0)
    obs = b.obtener_balance("lote-1", -33.7, -65.3, desde, hasta, textura="arenoso", cliente=cliente,
                            leer_imerg=imerg_igual)
    por = {o.variable: o for o in obs}
    assert por["agua_disponible_2m"].valor == 112
    assert por["agua_suelo_porcentaje"].valor == 100
    assert por["excedente_balance_mm"].valor > 0
    assert por["confort_hidrico_balance"].valor == 100


def test_sin_textura_usa_franco_y_queda_dudosa():
    desde, hasta = date(2026, 1, 1), date(2026, 1, 10)
    cliente, _ = respuesta_power(desde, hasta, lluvia=2.0)
    obs = b.obtener_balance("lote-1", -33.7, -65.3, desde, hasta, cliente=cliente, leer_imerg=imerg_igual)
    assert all(o.calidad == "dudosa" for o in obs)
    assert "se supuso franco, 217 mm" in obs[0].nota


def test_un_dia_sin_dato_de_power_corta_el_balance_desde_ahi():
    desde, hasta = date(2026, 9, 1), date(2026, 9, 30)
    cliente, _ = respuesta_power(desde, hasta, lluvia=2.0, faltan={date(2026, 9, 15)})
    obs = b.obtener_balance("lote-1", -33.7, -65.3, desde, hasta, textura="franco", cliente=cliente,
                            leer_imerg=imerg_igual)
    primera = [o for o in obs if o.fecha == date(2026, 9, 10)]
    despues = [o for o in obs if o.fecha > date(2026, 9, 10)]
    assert all(o.valor is not None for o in primera)
    assert despues and all(o.valor is None and o.calidad == "descartada" for o in despues)
    assert "15/09/2026" in despues[0].nota


def test_pedidos_invalidos_no_llaman_a_la_nasa():
    cliente, pedidos = respuesta_power(date(2026, 1, 1), date(2026, 1, 10))
    with pytest.raises(ValueError, match="Textura desconocida"):
        b.obtener_balance("l", -33.7, -65.3, date(2026, 1, 1), date(2026, 1, 10), textura="turba", cliente=cliente)
    with pytest.raises(ValueError, match="Kc"):
        b.obtener_balance("l", -33.7, -65.3, date(2026, 1, 1), date(2026, 1, 10), kc=2.0, cliente=cliente)
    with pytest.raises(ValueError, match="366"):
        b.obtener_balance("l", -33.7, -65.3, date(2024, 1, 1), date(2026, 1, 10), cliente=cliente)
    assert pedidos == []


def test_power_caido_es_un_error_claro():
    cliente = httpx.Client(transport=httpx.MockTransport(lambda p: httpx.Response(503)))
    with pytest.raises(b.ErrorBalance, match="NASA POWER"):
        b.obtener_balance("l", -33.7, -65.3, date(2026, 1, 1), date(2026, 1, 10), cliente=cliente)


def test_se_anuncia_como_respaldo_de_sepa():
    (satelite,) = b.SATELITES
    assert satelite.nombre == "SEPA_INTA:BALANCE"
    assert satelite.respaldo_de == "SEPA_INTA"


def test_endpoint_rechaza_textura_desconocida():
    app = FastAPI()
    app.include_router(b.router)
    r = TestClient(app).get("/balance-hidrico", params=dict(lote_id="l", lat=-33.7, lon=-65.3, desde="2026-01-01",
                                                           hasta="2026-01-10", textura="turba"))
    assert r.status_code == 422


def test_sin_radiacion_se_estima_con_hargreaves_y_la_decada_queda_dudosa(monkeypatch):
    monkeypatch.setattr(b, "CALIBRADO", True)
    desde, hasta = date(2026, 9, 1), date(2026, 9, 20)
    series = series_constantes(desde - timedelta(days=b.ARRANQUE_DIAS), hasta, lluvia=2.0)
    series["ALLSKY_SFC_SW_DWN"]["20260907"] = b.VALOR_RELLENO
    series["WS2M"]["20260907"] = b.VALOR_RELLENO
    cuerpo = {"geometry": {"coordinates": [-65.3, -33.7, 600.0]}, "properties": {"parameter": series}}
    cliente = httpx.Client(transport=httpx.MockTransport(lambda p: httpx.Response(200, json=cuerpo)))
    obs = b.obtener_balance("lote-1", -33.7, -65.3, desde, hasta, textura="franco", cliente=cliente,
                            leer_imerg=imerg_igual)
    primera = [o for o in obs if o.fecha == date(2026, 9, 10)]
    segunda = [o for o in obs if o.fecha == date(2026, 9, 20)]
    assert all(o.valor is not None and o.calidad == "dudosa" for o in primera)
    assert "Hargreaves" in primera[0].nota and "viento" in primera[0].nota and "07/09/2026" in primera[0].nota
    assert all(o.valor is not None and o.calidad == "buena" for o in segunda)


def test_sin_temperatura_no_hay_et0():
    et0, faltan, _ = b.et0_del_dia({"T2M_MAX": b.VALOR_RELLENO, "T2M_MIN": 10.0}, -33.7, date(2026, 9, 7), 600)
    assert et0 is None and faltan == ["T2M_MAX"]


def test_mientras_no_este_calibrado_todo_sale_dudosa_y_lo_dice(monkeypatch):
    monkeypatch.setattr(b, "CALIBRADO", False)
    desde, hasta = date(2026, 1, 1), date(2026, 1, 10)
    cliente, _ = respuesta_power(desde, hasta, lluvia=2.0)
    obs = b.obtener_balance("lote-1", -33.7, -65.3, desde, hasta, textura="franco", cliente=cliente,
                            leer_imerg=imerg_igual)
    assert all(o.calidad == "dudosa" and "sin calibrar" in o.nota for o in obs)


# ---------- lluvia: la menor entre POWER e IMERG ----------

def test_imerg_baja_las_lluvias_de_power_que_no_existieron():
    desde, hasta = date(2026, 1, 1), date(2026, 1, 10)
    cliente, _ = respuesta_power(desde, hasta, lluvia=5.0)
    pedidos = []

    def imerg_seco(lat, lon, dias):
        pedidos.append(dias)
        return {d.strftime("%Y%m%d"): 0.0 for d in dias}
    con_power = b.obtener_balance("l", -33.7, -65.3, desde, hasta, textura="franco", cliente=cliente,
                                  leer_imerg=imerg_igual)
    con_imerg = b.obtener_balance("l", -33.7, -65.3, desde, hasta, textura="franco", cliente=cliente,
                                  leer_imerg=imerg_seco)
    agua = {o.variable: o.valor for o in con_power}["agua_disponible_2m"]
    assert {o.variable: o.valor for o in con_imerg}["agua_disponible_2m"] < agua
    assert len(pedidos[0]) == (hasta - desde).days + 1 + b.ARRANQUE_DIAS  # todos los días tenían lluvia en POWER


def test_solo_se_le_pregunta_a_imerg_por_los_dias_con_lluvia():
    desde, hasta = date(2026, 1, 1), date(2026, 1, 10)
    cliente, _ = respuesta_power(desde, hasta, lluvia=0.0)
    pedidos = []
    b.obtener_balance("l", -33.7, -65.3, desde, hasta, textura="franco", cliente=cliente,
                      leer_imerg=lambda lat, lon, dias: pedidos.append(dias) or {})
    assert pedidos == [[]]


def test_sin_imerg_usa_power_y_queda_dudosa():
    desde, hasta = date(2026, 1, 1), date(2026, 1, 10)
    cliente, _ = respuesta_power(desde, hasta, lluvia=2.0)
    obs = b.obtener_balance("l", -33.7, -65.3, desde, hasta, textura="franco", cliente=cliente,
                            leer_imerg=lambda lat, lon, dias: None)
    assert all(o.calidad == "dudosa" and "IMERG no respondió" in o.nota for o in obs)


def test_un_dia_que_imerg_no_tiene_deja_dudosa_su_decada():
    desde, hasta = date(2026, 1, 1), date(2026, 1, 20)
    cliente, _ = respuesta_power(desde, hasta, lluvia=2.0)

    def imerg_con_hueco(lat, lon, dias):
        return {d.strftime("%Y%m%d"): 2.0 for d in dias if d != date(2026, 1, 15)}
    obs = b.obtener_balance("l", -33.7, -65.3, desde, hasta, textura="franco", cliente=cliente,
                            leer_imerg=imerg_con_hueco)
    assert all(o.calidad == "buena" for o in obs if o.fecha == date(2026, 1, 10) and o.valor is not None)
    segunda = [o for o in obs if o.fecha == date(2026, 1, 20) and o.valor is not None]
    assert segunda and all(o.calidad == "dudosa" and "IMERG no los tenía" in o.nota for o in segunda)


def test_imerg_sin_credenciales_devuelve_none(monkeypatch):
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)
    assert b.lluvia_imerg(-33.7, -65.3, [date(2026, 1, 1)]) is None
    assert b.lluvia_imerg(-33.7, -65.3, []) == {}


def test_agua_relativa_equipara_contra_el_ultimo_anio():
    dia = date(2026, 9, 30)
    por_dia = {dia - timedelta(days=i): (100.0 + i % 50, 0, 0, 0, 0) for i in range(b.DIAS_RELATIVA)}
    por_dia[dia] = (100.0, 0, 0, 0, 0)  # el día más seco del año
    assert b.agua_relativa(por_dia, dia) == 0
    por_dia[dia] = (149.0, 0, 0, 0, 0)  # el más húmedo
    assert b.agua_relativa(por_dia, dia) == 100
    del por_dia[dia - timedelta(days=200)]  # sin un año completo no se calcula
    assert b.agua_relativa(por_dia, dia) is None


def test_el_balance_trae_el_porcentaje_relativo():
    desde, hasta = date(2026, 9, 1), date(2026, 9, 10)
    series = series_constantes(desde - timedelta(days=b.ARRANQUE_DIAS), hasta, lluvia=0.0)
    for i, clave in enumerate(sorted(series["PRECTOTCORR"])):
        series["PRECTOTCORR"][clave] = 15.0 if i % 30 == 0 else 0.0  # lluvias cada 30 días: el agua sube y baja
    cuerpo = {"geometry": {"coordinates": [-65.3, -33.7, 600.0]}, "properties": {"parameter": series}}
    cliente = httpx.Client(transport=httpx.MockTransport(lambda p: httpx.Response(200, json=cuerpo)))
    obs = b.obtener_balance("lote-1", -33.7, -65.3, desde, hasta, textura="franco", cliente=cliente,
                            leer_imerg=imerg_igual)
    (relativa,) = [o for o in obs if o.variable == "agua_relativa_balance"]
    assert relativa.unidad == "%" and 0 <= relativa.valor <= 100
