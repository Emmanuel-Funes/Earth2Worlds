"""Tests para la autenticación efímera de invitados (Básico y Avanzado) en Earth2Worlds."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_login_invitado_basico():
    res = client.post("/api/auth/guest", json={"modo": "basico"})
    assert res.status_code == 200
    datos = res.json()
    assert "access_token" in datos
    assert datos["token_type"] == "bearer"
    assert datos["usuario"]["id"] == 0
    assert datos["usuario"]["nombre"] == "Invitado"
    assert datos["usuario"]["apellido"] == "Básico"
    assert datos["usuario"]["rol"] == "propietario"

    # Verificar que /api/auth/me funciona con el token
    token = datos["access_token"]
    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    assert res_me.json()["email"] == "guest_basico@earth2worlds.local"


def test_login_invitado_avanzado():
    res = client.post("/api/auth/guest", json={"modo": "avanzado"})
    assert res.status_code == 200
    datos = res.json()
    assert datos["usuario"]["apellido"] == "Avanzado"

    token = datos["access_token"]
    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    assert res_me.json()["email"] == "guest_avanzado@earth2worlds.local"


def test_listar_campos_invitado_vacio():
    res = client.post("/api/auth/guest", json={"modo": "basico"})
    token = res.json()["access_token"]
    res_campos = client.get("/api/campos", headers={"Authorization": f"Bearer {token}"})
    assert res_campos.status_code == 200
    assert res_campos.json() == []
