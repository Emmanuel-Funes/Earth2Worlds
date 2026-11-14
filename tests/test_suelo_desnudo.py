from datetime import date

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from rotaterra import api
from rotaterra.fuentes import suelo_desnudo as sd

LOTE = {"type": "Polygon", "coordinates": [[
    [-65.30, -33.70], [-65.295, -33.70], [-65.295, -33.705], [-65.30, -33.705], [-65.30, -33.70]]]}


def test_periodo_son_los_48_meses_completos():
    assert sd.periodo(date(2026, 10, 30)) == (date(2022, 10, 1), date(2026, 9, 30))
    assert sd.periodo(date(2026, 1, 5)) == (date(2022, 1, 1), date(2025, 12, 31))


def test_ventana_del_lote_de_prueba():
    h, v, f0, f1, c0, c1 = sd.ventana(LOTE)
    assert (h, v) == (12, 12) and f1 > f0 and c1 > c0


def _datos(ndvi, confiabilidad=0, dia=200):
    lat = np.array([[-33.701, -33.701], [-33.704, -33.704]])
    lon = np.array([[-65.299, -65.296], [-65.299, -65.296]])
    return {"ndvi": np.full((2, 2), ndvi * 10000.0), "confiabilidad": np.full((2, 2), float(confiabilidad)),
            "dia": np.full((2, 2), float(dia)), "lat": lat, "lon": lon}


def test_ndvi_del_lote_y_nubes():
    assert sd.ndvi_del_lote(LOTE, _datos(0.31), date(2025, 7, 12)) == (date(2025, 7, 19), pytest.approx(0.31))
    assert sd.ndvi_del_lote(LOTE, _datos(0.31, confiabilidad=3), date(2025, 7, 12)) is None  # nube
    assert sd.ndvi_del_lote(LOTE, _datos(0.31, dia=3), date(2025, 12, 19)) == (date(2026, 1, 3), pytest.approx(0.31))


def test_por_mes_y_observaciones():
    serie = [(date(a, 8, 5), v) for a, v in ((2023, 0.20), (2024, 0.27), (2025, 0.33))]
    serie += [(date(a, 8, 21), v) for a, v in ((2023, 0.22), (2024, 0.29), (2025, 0.35))]
    serie += [(date(a, 2, 10), 0.8) for a in (2023, 2024, 2025)]
    assert sd.por_mes(serie)[8] == {2023: pytest.approx(0.21), 2024: pytest.approx(0.28), 2025: pytest.approx(0.34)}
    obs = {o.variable: o for o in sd.a_observaciones("l", serie, date(2022, 10, 1), date(2026, 9, 30), 9)}
    agosto = obs["suelo_desnudo_mes_08_pct"]
    assert agosto.valor == 33 and agosto.fuente == "MODIS" and agosto.calidad == "buena"
    assert "cobertura baja en 67 %" in agosto.nota and "2023 0.21" in agosto.nota
    assert obs["suelo_desnudo_mes_02_pct"].valor == 0
    assert obs["suelo_desnudo_mes_05_pct"].valor is None and obs["suelo_desnudo_mes_05_pct"].calidad == "descartada"
    assert obs["meses_cobertura_baja"].valor == 1 and "agosto" in obs["meses_cobertura_baja"].nota
    assert obs["meses_suelo_desnudo"].valor == 0 and obs["meses_suelo_desnudo"].calidad == "dudosa"  # 2 de 12 meses


def test_sin_compuestos_no_inventa():
    obs = sd.a_observaciones("l", [], date(2022, 10, 1), date(2026, 9, 30), 0)
    assert all(o.valor is None and o.calidad == "descartada" for o in obs) and len(obs) == 14


def _preparar(monkeypatch, leer):
    monkeypatch.setattr(sd, "_MEMORIA", {})
    monkeypatch.setattr(sd.earthdata, "cliente_autorizado", lambda c=None: object())
    monkeypatch.setattr(sd.earthdata, "coleccion_vigente", lambda c, n: "C1-LPCLOUD")
    monkeypatch.setattr(sd.earthdata, "archivos", lambda c, col, d, h, caja=None: [
        ("MOD13Q1.A2025193.h12v12.061.x", "https://x/MOD13Q1.A2025193.h12v12.061.x"),
        ("MOD13Q1.A2025193.h13v12.061.x", "https://x/MOD13Q1.A2025193.h13v12.061.x")])
    monkeypatch.setattr(sd, "leer_ventana", leer)


def test_memoria_y_solo_el_mosaico_del_lote(monkeypatch):
    pedidos = []
    _preparar(monkeypatch, lambda c, u, *a: pedidos.append(u) or _datos(0.3))
    sd.obtener("a", LOTE, hoy=date(2026, 10, 30))
    otra = sd.obtener("b", LOTE, hoy=date(2026, 10, 30))
    assert pedidos == ["https://x/MOD13Q1.A2025193.h12v12.061.x"] and otra[0].lote_id == "b"


def test_si_ningun_compuesto_llega_es_error(monkeypatch):
    def corta(*a):
        raise httpx.HTTPStatusError("404", request=httpx.Request("GET", "https://x"), response=httpx.Response(404))

    _preparar(monkeypatch, corta)
    with pytest.raises(sd.ErrorSueloDesnudo):
        sd.obtener("a", LOTE, hoy=date(2026, 10, 30))


def test_ruta_valida_el_poligono():
    respuesta = TestClient(api.app).post("/suelo-desnudo", json={"lote_id": "x", "poligono": {"type": "Point"}})
    assert respuesta.status_code == 422
