"""Respaldo de la lluvia de IMERG con NASA POWER (spec 013). Sin internet: POWER simulado."""

import os
from datetime import date

import httpx
import pytest

from rotaterra import actualizar, base
from rotaterra.contrato import Observacion
from rotaterra.fuentes import power_lluvia
from rotaterra.fuentes.registro import Satelite
from rotaterra.geo import poligono_desde_esquinas

POLIGONO = poligono_desde_esquinas("-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300")
DESDE, HASTA = date(2026, 1, 12), date(2026, 1, 15)

# forma real de la respuesta de POWER (recortada): el 15/1 no viene, el 14/1 es relleno
RESPUESTA = {
    "header": {"fill_value": -999.0},
    "properties": {"parameter": {"PRECTOTCORR": {"20260112": 0.0, "20260113": 18.37, "20260114": -999.0}}},
}


def cliente_falso(cuerpo=RESPUESTA, estado=200):
    pedidos = []

    def responder(pedido):
        pedidos.append(pedido)
        return httpx.Response(estado, json=cuerpo)

    cliente = httpx.Client(transport=httpx.MockTransport(responder))
    cliente.pedidos = pedidos
    return cliente


def pedir(cliente, desde=DESDE, hasta=HASTA):
    return power_lluvia.obtener_lluvia("lote-7", -33.7025, -65.2975, desde, hasta, cliente)


def por_fecha(obs):
    return {o.fecha: o for o in obs}


def test_un_valor_por_dia_pedido_con_la_variable_de_imerg():
    obs = pedir(cliente_falso())
    assert [o.fecha for o in obs] == [date(2026, 1, d) for d in (12, 13, 14, 15)]
    assert all(o.variable == "lluvia_mm" and o.unidad == "mm/día" for o in obs)
    assert all(o.fuente == "POWER" and o.resolucion_m == 55000 for o in obs)


def test_valor_normal_es_buena_y_la_nota_dice_que_es_respaldo():
    dia = por_fecha(pedir(cliente_falso()))[date(2026, 1, 13)]
    assert (dia.valor, dia.calidad) == (18.37, "buena")
    assert dia.nota == "Respaldo de IMERG · NASA POWER (MERRA-2/IMERG corregido) · celda de 0,5°"


def test_cero_es_un_dato_real_no_un_faltante():
    dia = por_fecha(pedir(cliente_falso()))[date(2026, 1, 12)]
    assert (dia.valor, dia.calidad) == (0.0, "buena")


def test_relleno_menos_999_no_se_inventa():
    dia = por_fecha(pedir(cliente_falso()))[date(2026, 1, 14)]
    assert dia.valor is None and dia.calidad == "descartada"
    assert "-999" in dia.nota and "Respaldo de IMERG" in dia.nota


def test_dia_que_power_no_devuelve_queda_descartado():
    dia = por_fecha(pedir(cliente_falso()))[date(2026, 1, 15)]
    assert dia.valor is None and dia.calidad == "descartada"
    assert "no devolvió" in dia.nota


def test_fuera_de_rango_es_dudosa_sin_corregir():
    cuerpo = {"properties": {"parameter": {"PRECTOTCORR": {"20260112": 612.5}}}}
    (dia,) = pedir(cliente_falso(cuerpo), hasta=DESDE)
    assert (dia.valor, dia.calidad) == (612.5, "dudosa")


def test_pide_lo_correcto_a_power():
    cliente = cliente_falso()
    pedir(cliente)
    (pedido,) = cliente.pedidos
    assert str(pedido.url).startswith(power_lluvia.URL_POWER)
    params = pedido.url.params
    assert params["parameters"] == "PRECTOTCORR" and params["community"] == "AG"
    assert (params["start"], params["end"]) == ("20260112", "20260115")
    assert (float(params["latitude"]), float(params["longitude"])) == (-33.7025, -65.2975)
    assert params["time-standard"] == "UTC" and params["format"] == "JSON"


@pytest.mark.parametrize("lat, lon, desde, hasta", [
    (-95, -65, DESDE, HASTA),
    (-33, -190, DESDE, HASTA),
    (-33, -65, HASTA, DESDE),
    (-33, -65, date(2024, 1, 1), date(2026, 1, 1)),
])
def test_pedido_invalido_no_llama_a_power(lat, lon, desde, hasta):
    cliente = cliente_falso()
    with pytest.raises(ValueError):
        power_lluvia.obtener_lluvia("lote-7", lat, lon, desde, hasta, cliente)
    assert cliente.pedidos == []


@pytest.mark.parametrize("cuerpo, estado", [
    ({"messages": ["error"]}, 500),
    ({"messages": ["sin datos"]}, 200),
    ({"properties": {"parameter": {"T2M": {}}}}, 200),
])
def test_power_caido_o_ilegible_da_error_claro(cuerpo, estado):
    with pytest.raises(power_lluvia.ErrorPowerLluvia):
        pedir(cliente_falso(cuerpo, estado))


# ---------- conexión con el núcleo (specs 005 y 009) ----------

def test_se_anuncia_como_unico_respaldo_de_imerg():
    (satelite,) = power_lluvia.SATELITES
    assert (satelite.nombre, satelite.respaldo_de, satelite.orden, satelite.estatico) == (
        "IMERG:POWER", "IMERG", 1, False)


def test_pide_con_el_centro_del_lote(monkeypatch):
    original = power_lluvia.obtener_lluvia
    cliente = cliente_falso()
    monkeypatch.setattr(power_lluvia, "obtener_lluvia", lambda *a: original(*a, cliente=cliente))
    lote = {"id": "lote-7", "poligono": POLIGONO, "lat": -33.7025, "lon": -65.2975}
    obs = power_lluvia.SATELITES[0].pedir(lote, DESDE, HASTA)
    assert {o.lote_id for o in obs} == {"lote-7"} and len(obs) == 4
    assert float(cliente.pedidos[0].url.params["latitude"]) == -33.7025


@pytest.fixture
def motor(tmp_path):
    """SQLite por defecto; PostgreSQL si TEST_DATABASE_URL está definida (lo hace CI)."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        return base.conectar(f"sqlite:///{tmp_path}/prueba.db")
    motor = base.conectar(url)
    base.metadata.drop_all(motor)
    base.metadata.create_all(motor)
    return motor


def imerg_falso(pedidos, falla=False):
    def pedir_imerg(lote, desde, hasta):
        pedidos.append(("IMERG", desde, hasta))
        if falla:
            raise RuntimeError("GES DISC no responde")
        return [Observacion(lote_id=lote["id"], fecha=desde, variable="lluvia_mm", valor=22.5, unidad="mm/día",
                            fuente="IMERG", resolucion_m=10000, calidad="buena")]
    return Satelite("IMERG", pedir_imerg)


def respaldo_espiado(monkeypatch, pedidos):
    original = power_lluvia.obtener_lluvia

    def espiar(lote_id, lat, lon, desde, hasta):
        pedidos.append(("IMERG:POWER", desde, hasta))
        cuerpo = {"properties": {"parameter": {"PRECTOTCORR": {
            f"{desde:%Y%m%d}": 18.37, f"{hasta:%Y%m%d}": 3.1}}}}
        return original(lote_id, lat, lon, desde, hasta, cliente=cliente_falso(cuerpo))

    monkeypatch.setattr(power_lluvia, "obtener_lluvia", espiar)
    return power_lluvia.SATELITES


def test_imerg_caido_entra_power_por_el_mismo_periodo(motor, monkeypatch):
    lote = base.guardar_lote(motor, "lote-7", "Lote 7", POLIGONO)
    pedidos = []
    satelites = [imerg_falso(pedidos, falla=True)] + respaldo_espiado(monkeypatch, pedidos)
    resultados = actualizar.actualizar_lote(motor, lote, hoy=date(2026, 1, 16), satelites=satelites)
    assert [(r.fuente, r.resultado) for r in resultados] == [("IMERG", "error"), ("IMERG:POWER", "ok")]
    assert pedidos[0][1:] == pedidos[1][1:]  # mismo período
    guardadas = base.leer_observaciones(motor, "lote-7", variable="lluvia_mm", fuente="POWER")
    assert guardadas and all(o.nota.startswith("Respaldo de IMERG") or o.valor is None for o in guardadas)


def test_imerg_ok_no_consulta_el_respaldo(motor, monkeypatch):
    lote = base.guardar_lote(motor, "lote-7", "Lote 7", POLIGONO)
    pedidos = []
    satelites = [imerg_falso(pedidos)] + respaldo_espiado(monkeypatch, pedidos)
    resultados = actualizar.actualizar_lote(motor, lote, hoy=date(2026, 1, 16), satelites=satelites)
    assert [r.fuente for r in resultados] == ["IMERG"]
    assert [p[0] for p in pedidos] == ["IMERG"]


def test_sin_imerg_unido_queda_en_espera(motor, monkeypatch):
    lote = base.guardar_lote(motor, "lote-7", "Lote 7", POLIGONO)
    pedidos = []
    resultados = actualizar.actualizar_lote(motor, lote, hoy=date(2026, 1, 16),
                                            satelites=respaldo_espiado(monkeypatch, pedidos))
    assert resultados == [] and pedidos == []


def test_combinar_prefiere_imerg_y_power_rellena_lo_que_falta():
    def lluvia(dia, fuente, valor):
        return Observacion(lote_id="lote-7", fecha=date(2026, 1, dia), variable="lluvia_mm", valor=valor,
                           unidad="mm/día", fuente=fuente, resolucion_m=55000 if fuente == "POWER" else 10000,
                           calidad="buena" if valor is not None else "descartada")
    serie = base.combinar_fuentes([lluvia(13, "IMERG", 22.5), lluvia(13, "POWER", 18.37),
                                   lluvia(14, "IMERG", None), lluvia(14, "POWER", 3.1)])
    assert [(o.fecha.day, o.fuente, o.valor) for o in serie] == [(13, "IMERG", 22.5), (14, "POWER", 3.1)]
