"""ET de referencia FAO-56 con NASA POWER (spec 019), sin internet."""

from datetime import date

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rotaterra.fuentes import et0_fao56 as fao

# ---------- el cálculo contra los ejemplos resueltos del manual FAO-56 ----------


def test_ejemplo_18_de_fao56_bruselas_6_de_julio():
    # Bruselas, 50°48' N, 100 m, 6 de julio (día 187): T 21,5/12,3 °C, ea 1,409 kPa (ej. 18),
    # viento 10 km/h a 10 m → u2 2,078 m/s, Rs 22,07 MJ/m²/día. Resultado del manual: ET0 = 3,9 mm/día.
    r = fao.et0_fao56(21.5, 12.3, 1.409, 2.078, 22.07, 50 + 48 / 60, 187, 100)
    assert r["es"] == pytest.approx(1.997, abs=0.001)
    assert r["delta"] == pytest.approx(0.122, abs=0.001)
    assert r["gamma"] == pytest.approx(0.0666, abs=0.0001)
    assert r["ra"] == pytest.approx(41.09, abs=0.02)
    assert r["rso"] == pytest.approx(30.90, abs=0.02)
    assert r["rns"] == pytest.approx(17.00, abs=0.01)
    assert r["rnl"] == pytest.approx(3.71, abs=0.01)
    assert r["rn"] == pytest.approx(13.28, abs=0.02)
    assert round(r["et0"], 1) == 3.9


def test_ejemplo_2_presion_y_psicrometrica_a_1800_m():
    assert fao.presion(1800) == pytest.approx(81.8, abs=0.05)
    assert fao.psicrometrica(fao.presion(1800)) == pytest.approx(0.054, abs=0.0005)


def test_ejemplo_8_radiacion_extraterrestre_20_sur_3_de_septiembre():
    assert fao.radiacion_extraterrestre(-20, 246) == pytest.approx(32.2, abs=0.05)


def test_ejemplo_11_onda_larga_neta():
    assert fao.onda_larga_neta(25.1, 19.1, 2.1, 14.5, 18.8) == pytest.approx(3.5, abs=0.05)


def test_ejemplo_5_ea_con_humedad_media_y_tabla_de_rocio():
    assert fao.ea_humedad_media(68, 25, 18) == pytest.approx(1.78, abs=0.005)
    assert fao.ea_rocio(17.0) == pytest.approx(1.938, abs=0.001)  # tabla 2.3 del manual


def test_rs_mayor_que_rso_se_limita_a_uno():
    assert fao.onda_larga_neta(30, 15, 1.2, 40, 30) == pytest.approx(fao.onda_larga_neta(30, 15, 1.2, 30, 30))


# ---------- NASA POWER → contrato común ----------

# forma real de la respuesta de POWER (recortada): la elevación viene en geometry.coordinates[2]
def respuesta(**cambios):
    parametros = {
        "T2M_MAX": {"20260113": 31.2, "20260114": 28.0},
        "T2M_MIN": {"20260113": 16.4, "20260114": 15.0},
        "T2MDEW": {"20260113": 9.8, "20260114": 11.0},
        "RH2M": {"20260113": 45.0, "20260114": 55.0},
        "WS2M": {"20260113": 3.1, "20260114": 2.5},
        "ALLSKY_SFC_SW_DWN": {"20260113": 28.4, "20260114": 25.0},
    }
    for parametro, dias in cambios.items():
        parametros[parametro] = {**parametros[parametro], **dias}
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-65.2975, -33.7025, 470.3]},
            "properties": {"parameter": parametros}, "header": {"fill_value": -999}}


def cliente_falso(cuerpo=None, estado=200):
    pedidos = []

    def responder(pedido):
        pedidos.append(pedido)
        return httpx.Response(estado, json=respuesta() if cuerpo is None else cuerpo)

    cliente = httpx.Client(transport=httpx.MockTransport(responder))
    cliente.pedidos = pedidos
    return cliente


def pedir(cliente, desde=date(2026, 1, 13), hasta=date(2026, 1, 14)):
    return fao.obtener_et0("lote-7", -33.7025, -65.2975, desde, hasta, cliente)


def test_pide_a_power_los_insumos_de_fao56_en_el_centro_del_lote():
    cliente = cliente_falso()
    pedir(cliente)
    params = cliente.pedidos[0].url.params
    assert str(cliente.pedidos[0].url).startswith(fao.URL_POWER)
    assert set(params["parameters"].split(",")) == {"T2M_MAX", "T2M_MIN", "T2MDEW", "RH2M", "WS2M", "ALLSKY_SFC_SW_DWN"}
    assert (params["community"], params["latitude"], params["longitude"]) == ("AG", "-33.7025", "-65.2975")
    assert (params["start"], params["end"]) == ("20260113", "20260114")


def test_un_valor_de_et0_por_dia_en_el_contrato_comun():
    obs = pedir(cliente_falso())
    assert [o.fecha for o in obs] == [date(2026, 1, 13), date(2026, 1, 14)]
    for o in obs:
        assert (o.variable, o.unidad, o.fuente, o.resolucion_m, o.calidad) == (
            "et0_mm_dia", "mm/día", "POWER", 55000, "buena")
        assert 3 < o.valor < 12


def test_el_valor_es_el_de_la_ecuacion_6_con_la_altura_de_power():
    o = pedir(cliente_falso())[0]
    esperado = fao.et0_fao56(31.2, 16.4, fao.ea_rocio(9.8), 3.1, 28.4, -33.7025, 13, 470.3)["et0"]
    assert o.valor == round(esperado, 2)
    assert "altura 470 m" in o.nota and "rocío 9,8 °C" in o.nota


def test_la_nota_aclara_que_no_es_la_et_real_del_cultivo():
    for o in pedir(cliente_falso()):
        assert "NO es la ET real del cultivo" in o.nota and "Kc" in o.nota


@pytest.mark.parametrize("parametro", ["T2M_MAX", "T2M_MIN", "WS2M", "ALLSKY_SFC_SW_DWN"])
def test_un_insumo_con_relleno_descarta_el_dia_y_dice_cual(parametro):
    obs = pedir(cliente_falso(respuesta(**{parametro: {"20260114": -999}})))
    assert obs[0].calidad == "buena"
    assert (obs[1].valor, obs[1].calidad) == (None, "descartada")
    assert parametro in obs[1].nota and "-999" in obs[1].nota
    assert "NO es la ET real del cultivo" in obs[1].nota


def test_sin_punto_de_rocio_usa_la_humedad_media_y_lo_dice():
    o = pedir(cliente_falso(respuesta(T2MDEW={"20260113": -999})))[0]
    esperado = fao.et0_fao56(31.2, 16.4, fao.ea_humedad_media(45, 31.2, 16.4), 3.1, 28.4, -33.7025, 13, 470.3)["et0"]
    assert (o.valor, o.calidad) == (round(esperado, 2), "buena")
    assert "HR media 45 %" in o.nota


def test_sin_rocio_ni_humedad_se_descarta():
    o = pedir(cliente_falso(respuesta(T2MDEW={"20260113": -999}, RH2M={"20260113": -999})))[0]
    assert (o.valor, o.calidad) == (None, "descartada")
    assert "T2MDEW y RH2M" in o.nota


def test_parametro_ausente_en_la_respuesta_cuenta_como_faltante():
    cuerpo = respuesta()
    del cuerpo["properties"]["parameter"]["WS2M"]
    assert all(o.calidad == "descartada" and "WS2M" in o.nota for o in pedir(cliente_falso(cuerpo)))


def test_sin_elevacion_no_se_inventa_la_altura():
    cuerpo = respuesta()
    cuerpo["geometry"]["coordinates"] = [-65.2975, -33.7025]
    obs = pedir(cliente_falso(cuerpo))
    assert all(o.valor is None and o.calidad == "descartada" and "elevación" in o.nota for o in obs)


def test_tmax_menor_que_tmin_se_descarta():
    o = pedir(cliente_falso(respuesta(T2M_MAX={"20260113": 10.0})))[0]
    assert (o.valor, o.calidad) == (None, "descartada")
    assert "incoherentes" in o.nota


def test_et0_fuera_de_rango_es_dudosa():
    o = fao.calcular_dia("lote-7", date(2026, 1, 13), {"T2M_MAX": 45.0, "T2M_MIN": 30.0, "T2MDEW": -20.0,
                                                       "RH2M": 5.0, "WS2M": 15.0, "ALLSKY_SFC_SW_DWN": 33.0},
                         -33.7, 470)
    assert o.valor > 15 and o.calidad == "dudosa" and "fuera del rango" in o.nota


def test_rocio_por_encima_de_la_temperatura_es_dudosa():
    o = fao.calcular_dia("lote-7", date(2026, 1, 13), {"T2M_MAX": 20.0, "T2M_MIN": 10.0, "T2MDEW": 19.0,
                                                       "RH2M": 99.0, "WS2M": 2.0, "ALLSKY_SFC_SW_DWN": 20.0},
                         -33.7, 470)
    assert o.valor is not None and o.calidad == "dudosa" and "Humedad incoherente" in o.nota


def test_solo_devuelve_dias_del_periodo_pedido():
    assert [o.fecha for o in pedir(cliente_falso(), hasta=date(2026, 1, 13))] == [date(2026, 1, 13)]


def test_power_caido_es_un_error_claro():
    with pytest.raises(fao.ErrorET0, match="NASA POWER"):
        pedir(cliente_falso({"messages": ["error"]}, estado=500))
    with pytest.raises(fao.ErrorET0):
        pedir(cliente_falso({"algo": "raro"}))


@pytest.mark.parametrize("lat, lon, desde, hasta", [
    (-95, -65, date(2026, 1, 1), date(2026, 1, 2)),
    (-33, -190, date(2026, 1, 1), date(2026, 1, 2)),
    (-33, -65, date(2026, 1, 3), date(2026, 1, 2)),
    (-33, -65, date(2025, 1, 1), date(2026, 1, 2)),
])
def test_pedidos_invalidos(lat, lon, desde, hasta):
    with pytest.raises(ValueError):
        fao.validar_pedido(lat, lon, desde, hasta)


# ---------- conexión con el núcleo ----------

def test_se_anuncia_como_ultimo_respaldo_de_la_et():
    [s] = fao.SATELITES
    assert (s.nombre, s.respaldo_de, s.orden, s.estatico) == ("ET:FAO56", "ET", 2, False)


def test_pedir_usa_el_centro_del_lote(monkeypatch):
    pedidos = []
    monkeypatch.setattr(fao, "obtener_et0", lambda *args: pedidos.append(args) or [])
    fao.SATELITES[0].pedir({"id": "lote-7", "lat": -33.7025, "lon": -65.2975, "poligono": {}},
                           date(2026, 1, 1), date(2026, 1, 14))
    assert pedidos == [("lote-7", -33.7025, -65.2975, date(2026, 1, 1), date(2026, 1, 14))]


def test_endpoint_de_prueba():
    app = FastAPI()
    app.include_router(fao.router)
    cliente = TestClient(app)
    assert cliente.get("/et0", params=dict(lote_id="l", lat=-95, lon=-65, desde="2026-01-01",
                                           hasta="2026-01-02")).status_code == 422
