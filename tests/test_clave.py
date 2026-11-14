"""La API solo responde a quien manda una clave válida, y solo a los orígenes permitidos (spec 022)."""

import pytest
from fastapi.testclient import TestClient

from rotaterra import api

pytestmark = pytest.mark.con_clave

CLAVE, OTRA = "clave-de-prueba-1", "clave-de-prueba-2"
DANIEL = "https://frontend.ejemplo.com"


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("ROTATERRA_API_KEYS", f"{CLAVE}, {OTRA}")
    monkeypatch.setenv("ROTATERRA_ORIGENES", DANIEL)
    return TestClient(api.app)


def test_sin_clave_responde_401(cliente):
    r = cliente.get("/satelites")
    assert r.status_code == 401
    assert "X-API-Key" in r.json()["detail"]


def test_clave_equivocada_responde_401_y_no_la_repite(cliente):
    r = cliente.get("/satelites", headers={"X-API-Key": "clave-inventada"})
    assert r.status_code == 401
    assert "clave-inventada" not in r.text


def test_las_dos_claves_configuradas_funcionan(cliente):
    for clave in (CLAVE, OTRA):
        assert cliente.get("/satelites", headers={"X-API-Key": clave}).status_code == 200


def test_la_clave_protege_tambien_la_consulta(cliente):
    assert cliente.post("/consulta", json={}).status_code == 401


def test_sin_claves_configuradas_rechaza_todo_salvo_salud(monkeypatch):
    monkeypatch.delenv("ROTATERRA_API_KEYS", raising=False)
    cliente = TestClient(api.app)
    r = cliente.get("/satelites", headers={"X-API-Key": "cualquiera"})
    assert r.status_code == 503
    assert cliente.get("/salud").json() == {"ok": True}


def test_salud_no_pide_clave(cliente):
    assert cliente.get("/salud").status_code == 200


def test_cors_permite_al_frontend_autorizado(cliente):
    r = cliente.options("/consulta", headers={"Origin": DANIEL, "Access-Control-Request-Method": "POST",
                                              "Access-Control-Request-Headers": "X-API-Key, Content-Type"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == DANIEL
    r = cliente.get("/satelites", headers={"Origin": DANIEL, "X-API-Key": CLAVE})
    assert r.headers["access-control-allow-origin"] == DANIEL


def test_cors_no_permite_otro_origen(cliente):
    r = cliente.options("/consulta", headers={"Origin": "https://otro.ejemplo.com",
                                              "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in r.headers
    r = cliente.get("/satelites", headers={"Origin": "https://otro.ejemplo.com", "X-API-Key": CLAVE})
    assert "access-control-allow-origin" not in r.headers


def test_sin_origenes_configurados_no_hay_cors(cliente, monkeypatch):
    monkeypatch.delenv("ROTATERRA_ORIGENES")
    r = cliente.get("/satelites", headers={"Origin": DANIEL, "X-API-Key": CLAVE})
    assert "access-control-allow-origin" not in r.headers


def test_la_documentacion_ofrece_cargar_la_clave(cliente):
    esquema = cliente.get("/openapi.json")
    assert esquema.status_code == 200
    assert esquema.json()["components"]["securitySchemes"]["APIKeyHeader"]["name"] == "X-API-Key"
