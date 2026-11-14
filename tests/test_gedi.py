import io
from datetime import date

import h5py
import numpy as np
import pytest
from fastapi.testclient import TestClient

from rotaterra import api
from rotaterra.fuentes import gedi

LOTE = {"type": "Polygon", "coordinates": [[
    [-65.30, -33.70], [-65.295, -33.70], [-65.295, -33.705], [-65.30, -33.705], [-65.30, -33.70]]]}


def test_caja_de_la_zona_agranda_2_km():
    oeste, sur, este, norte = gedi.caja_zona(LOTE)
    assert sur == pytest.approx(-33.705 - 0.018, abs=1e-3) and norte == pytest.approx(-33.70 + 0.018, abs=1e-3)
    assert oeste < -65.30 - 0.02 and este > -65.295 + 0.02


def test_fuera_de_la_orbita():
    lejos = {"type": "Polygon", "coordinates": [[[-65, -60], [-64.9, -60], [-64.9, -60.1], [-65, -60]]]}
    with pytest.raises(ValueError):
        gedi.validar_poligono(lejos)


def test_variables_van_codificadas():
    texto = gedi.variables()
    assert texto.count(",") == len(gedi.HACES) * len(gedi.CAMPOS) - 1
    assert "%2FBEAM0000%2Fgeolocation%2Fdelta_time" in texto and "/" not in texto


def _recorte(filas):
    memoria = io.BytesIO()
    with h5py.File(memoria, "w") as f:
        g = f.create_group("BEAM0101")
        for i, campo in enumerate(gedi.CAMPOS):
            g.create_dataset(campo, data=np.array([fila[i] for fila in filas]))
        f.create_group("BEAM0000")  # haz sin disparos en la zona
    return memoria.getvalue()


def test_leer_recorte_y_fecha():
    segundos = (date(2025, 9, 9) - date(2018, 1, 1)).days * 86400 + 3600
    disparos = gedi.leer_recorte(_recorte([(-33.702, -65.297, 0.03, 0.06, 1, segundos)]))
    assert disparos == [{"lat": pytest.approx(-33.702), "lon": pytest.approx(-65.297), "cover": pytest.approx(0.03),
                         "pai": pytest.approx(0.06), "buena": True, "fecha": date(2025, 9, 9)}]


def _d(lat, lon, cover, buena=True, pai=0.1, fecha=date(2025, 9, 9)):
    return {"lat": lat, "lon": lon, "cover": cover, "pai": pai, "buena": buena, "fecha": fecha}


def test_observaciones_zona_lote_y_no_inventa():
    disparos = ([_d(-33.71, -65.31, 0.02) for _ in range(28)] + [_d(-33.71, -65.31, 0.50) for _ in range(4)]
                + [_d(-33.702, -65.297, 0.04) for _ in range(3)] + [_d(-33.71, -65.31, -9999.0, pai=-9999.0)]
                + [_d(-33.71, -65.31, 0.9, buena=False)])
    obs = {o.variable: o for o in gedi.a_observaciones("l", LOTE, disparos, date(2023, 10, 1), date(2026, 10, 30))}
    zona = obs["gedi_cobertura_zona_pct"]
    assert zona.valor == 2.0 and zona.calidad == "buena" and zona.fuente == "GEDI" and "35 disparos" in zona.nota
    assert obs["gedi_monte_zona_pct"].valor == pytest.approx(11.4, abs=0.1)
    lote = obs["gedi_cobertura_lote_pct"]
    assert lote.valor == 4.0 and lote.calidad == "dudosa" and "(< 5)" in lote.nota


def test_sin_disparos_buenos_queda_descartado():
    obs = gedi.a_observaciones("l", LOTE, [_d(-33.702, -65.297, 0.04, buena=False)], date(2023, 10, 1),
                               date(2026, 10, 30))
    assert all(o.valor is None and o.calidad == "descartada" for o in obs) and len(obs) == 5


def test_memoria_por_lote(monkeypatch):
    llamadas = []
    monkeypatch.setattr(gedi, "_MEMORIA", {})
    monkeypatch.setattr(gedi.earthdata, "cliente_autorizado", lambda c=None: object())
    monkeypatch.setattr(gedi.earthdata, "coleccion_vigente", lambda c, n: "C1-LPCLOUD")
    monkeypatch.setattr(gedi, "pedir_recorte", lambda *a: llamadas.append(a) or "trabajo")
    monkeypatch.setattr(gedi, "esperar", lambda c, t: [])
    gedi.obtener("a", LOTE, hoy=date(2026, 10, 30))
    gedi.obtener("b", LOTE, hoy=date(2026, 10, 30))
    assert len(llamadas) == 1


def test_ruta_valida_el_poligono():
    respuesta = TestClient(api.app).post("/vegetacion-gedi", json={"lote_id": "x", "poligono": {"type": "Polygon",
                                                                                               "coordinates": []}})
    assert respuesta.status_code == 422
