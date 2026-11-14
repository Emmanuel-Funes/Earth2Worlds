"""Los tests de la API no mandan clave: la clave se prueba aparte en tests/test_clave.py (spec 022)."""

import pytest

from rotaterra import api


@pytest.fixture(autouse=True)
def sin_clave_en_los_tests(request):
    if request.node.get_closest_marker("con_clave"):
        yield
        return
    api.app.dependency_overrides[api.verificar_clave] = lambda: None
    yield
    api.app.dependency_overrides.pop(api.verificar_clave, None)


def pytest_configure(config):
    config.addinivalue_line("markers", "con_clave: el test prueba la clave de verdad, sin saltearla")
