from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from rotaterra import api
from rotaterra.fuentes import power

# Respuesta con la forma real de NASA POWER (recortada a 2 días)
RESPUESTA_POWER = {
    "properties": {
        "parameter": {
            "T2M_MAX": {"20260901": 21.4, "20260902": -999},
            "T2M_MIN": {"20260901": 4.2, "20260902": 6.0},
            "PRECTOTCORR": {"20260901": 0.0, "20260902": 12.5},
            "ALLSKY_SFC_SW_DWN": {"20260901": 17.8, "20260902": 9.1},
        }
    }
}


def cliente_falso(cuerpo=RESPUESTA_POWER, estado=200):
    pedidos = []

    def responder(pedido):
        pedidos.append(pedido)
        return httpx.Response(estado, json=cuerpo)

    cliente = httpx.Client(transport=httpx.MockTransport(responder))
    cliente.pedidos = pedidos
    return cliente


def pedir(cliente):
    return power.obtener_clima("lote-7", -33.68, -65.46, date(2026, 9, 1), date(2026, 9, 2), cliente)


def test_cuatro_variables_por_dia():
    obs = pedir(cliente_falso())
    assert len(obs) == 8
    assert {o.variable for o in obs} == {"temp_max", "temp_min", "lluvia_mm", "radiacion"}
    assert all(o.fuente == "POWER" and o.resolucion_m == 55000 for o in obs)


def test_valor_normal_es_buena():
    obs = pedir(cliente_falso())
    tmax = next(o for o in obs if o.variable == "temp_max" and o.fecha == date(2026, 9, 1))
    assert (tmax.valor, tmax.unidad, tmax.calidad) == (21.4, "°C", "buena")


def test_relleno_menos_999_no_se_inventa():
    obs = pedir(cliente_falso())
    tmax = next(o for o in obs if o.variable == "temp_max" and o.fecha == date(2026, 9, 2))
    assert tmax.valor is None
    assert tmax.calidad == "descartada"
    assert "-999" in tmax.nota


def test_fuera_de_rango_es_dudosa():
    cuerpo = {"properties": {"parameter": {"PRECTOTCORR": {"20260901": -3.0}}}}
    (lluvia,) = pedir(cliente_falso(cuerpo))
    assert lluvia.calidad == "dudosa" and lluvia.valor == -3.0


def test_pide_lo_correcto_a_power():
    cliente = cliente_falso()
    pedir(cliente)
    params = cliente.pedidos[0].url.params
    assert params["start"] == "20260901" and params["end"] == "20260902"
    assert params["community"] == "AG"
    assert set(params["parameters"].split(",")) == set(power.VARIABLES)


@pytest.mark.parametrize("lat, lon, desde, hasta", [
    (-95, -65, date(2026, 9, 1), date(2026, 9, 2)),
    (-33, -190, date(2026, 9, 1), date(2026, 9, 2)),
    (-33, -65, date(2026, 9, 5), date(2026, 9, 1)),
    (-33, -65, date(2024, 1, 1), date(2026, 1, 1)),
])
def test_pedido_invalido_no_llama_a_power(lat, lon, desde, hasta):
    cliente = cliente_falso()
    with pytest.raises(ValueError):
        power.obtener_clima("lote-7", lat, lon, desde, hasta, cliente)
    assert cliente.pedidos == []


def test_power_caido_da_error_claro():
    with pytest.raises(power.ErrorPower):
        pedir(cliente_falso({"error": "x"}, estado=500))


def test_api_devuelve_contrato(monkeypatch):
    original = power.obtener_clima
    monkeypatch.setattr(power, "obtener_clima",
                        lambda *a: original(*a, cliente=cliente_falso()))
    r = TestClient(api.app).get("/clima", params=dict(
        lote_id="lote-7", lat=-33.68, lon=-65.46, desde="2026-09-01", hasta="2026-09-02"))
    assert r.status_code == 200
    assert set(r.json()[0]) == {"lote_id", "fecha", "variable", "valor", "unidad",
                                "fuente", "resolucion_m", "calidad", "nota"}


def test_api_rechaza_fechas_invertidas():
    r = TestClient(api.app).get("/clima", params=dict(
        lote_id="lote-7", lat=-33.68, lon=-65.46, desde="2026-09-05", hasta="2026-09-01"))
    assert r.status_code == 422
