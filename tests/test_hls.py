import os
from datetime import date

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from rotaterra import api
from rotaterra.fuentes import hls

LOTE = {"type": "Polygon", "coordinates": [[
    [-65.30, -33.70], [-65.295, -33.70], [-65.295, -33.705], [-65.30, -33.705], [-65.30, -33.70]]]}


def test_ndvi_de_cultivo_verde():
    rojo = np.array([[400]])   # 0.04 de reflectancia
    nir = np.array([[3600]])   # 0.36
    assert hls.diferencia_normalizada(nir, rojo)[0, 0] == pytest.approx(0.8)


def test_division_por_cero_y_relleno_no_dan_numero():
    a = np.array([[0, -9999]])
    b = np.array([[0, 500]])
    assert np.isnan(hls.diferencia_normalizada(a, b)).all()


@pytest.mark.parametrize("valor, limpio", [
    (0, True),            # despejado
    (1, True),            # bit 0 (cirrus) no invalida
    (1 << 1, False),      # nube
    (1 << 2, False),      # nube adyacente
    (1 << 3, False),      # sombra
    (1 << 4, False),      # nieve
    (1 << 5, False),      # agua
    (1 << 6, True),       # aerosol bajo/medio: se conserva
    (255, False),         # relleno
])
def test_mascara_fmask(valor, limpio):
    assert hls.mascara_valida(np.array([[valor]]))[0, 0] == limpio


def test_resumen_solo_cuenta_pixeles_del_lote():
    indice = np.array([[0.2, 0.4, 0.6, 0.8]])
    dentro = np.array([[True, True, True, False]])
    validos = np.array([[True, True, False, True]])
    r = hls.resumir(indice, dentro, validos)
    assert r.validos_pct == pytest.approx(200 / 3)
    assert r.mediana == pytest.approx(0.3)


@pytest.mark.parametrize("pct, calidad", [(96, "buena"), (60, "buena"), (45, "dudosa"), (10, "descartada")])
def test_calidad_segun_pixeles_validos(pct, calidad):
    r = hls.Resumen(0.81, 0.8, 0.7, 0.9, pct)
    obs = hls.a_observacion("lote-7", date(2026, 1, 15), "ndvi", r, "HLSS30")
    assert obs.calidad == calidad
    assert obs.fuente == "HLS" and obs.resolucion_m == 30
    if calidad == "descartada":
        assert obs.valor is None
    else:
        assert obs.valor == 0.81


def test_sin_pixeles_validos_no_inventa():
    r = hls.resumir(np.array([[0.5]]), np.array([[True]]), np.array([[False]]))
    obs = hls.a_observacion("lote-7", date(2026, 1, 15), "ndvi", r, "HLSL30")
    assert obs.valor is None and obs.calidad == "descartada"


@pytest.mark.parametrize("poligono, desde, hasta", [
    ({"type": "Point", "coordinates": [-65.3, -33.7]}, date(2026, 1, 1), date(2026, 2, 1)),
    ({"type": "Polygon", "coordinates": [[[-65.3, -33.7], [-65.3, -33.7], [-65.3, -33.7], [-65.3, -33.7]]]},
     date(2026, 1, 1), date(2026, 2, 1)),
    (LOTE, date(2026, 2, 1), date(2026, 1, 1)),
    (LOTE, date(2024, 1, 1), date(2026, 1, 1)),
])
def test_pedido_invalido(poligono, desde, hasta):
    with pytest.raises(ValueError):
        hls.validar_pedido(poligono, desde, hasta)


def test_sin_credenciales_avisa(monkeypatch):
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)
    with pytest.raises(hls.FaltanCredenciales):
        hls.configurar_credenciales()


def test_credenciales_usan_el_token_de_earthdata(monkeypatch):
    monkeypatch.setenv("EARTHDATA_USERNAME", "usuario")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "clave")
    nasa = httpx.MockTransport(lambda pedido: httpx.Response(200, json={"access_token": "abc123"}))
    cliente = hls.configurar_credenciales(httpx.Client(transport=nasa))
    assert cliente.headers["Authorization"] == "Bearer abc123"
    assert "abc123" not in os.environ.get("GDAL_HTTP_HEADERS", "")  # GDAL no recibe el token


def test_enlace_firmado_sigue_la_redireccion_de_lp_daac():
    def nasa(pedido):
        assert pedido.headers["Authorization"] == "Bearer abc123"
        return httpx.Response(307, headers={"location": "https://d1.cloudfront.net/B04.tif?Signature=x"})
    cliente = httpx.Client(transport=httpx.MockTransport(nasa), headers={"Authorization": "Bearer abc123"})
    assert hls.enlace_firmado(cliente, "https://data.lpdaac.earthdatacloud.nasa.gov/B04.tif") == \
        "https://d1.cloudfront.net/B04.tif?Signature=x"


def test_enlace_firmado_sin_redireccion_usa_el_original():
    cliente = httpx.Client(transport=httpx.MockTransport(lambda pedido: httpx.Response(206, content=b"II*\x00")))
    assert hls.enlace_firmado(cliente, "https://otro/B04.tif") == "https://otro/B04.tif"


def test_enlace_firmado_acceso_negado_es_error():
    cliente = httpx.Client(transport=httpx.MockTransport(lambda pedido: httpx.Response(403)))
    with pytest.raises(httpx.HTTPStatusError):
        hls.enlace_firmado(cliente, "https://data.lpdaac.earthdatacloud.nasa.gov/B04.tif")


def test_credenciales_rechazadas_es_error_de_hls(monkeypatch):
    monkeypatch.setenv("EARTHDATA_USERNAME", "usuario")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "mal")
    nasa = httpx.MockTransport(lambda pedido: httpx.Response(401))
    with pytest.raises(hls.ErrorHLS, match="token"):
        hls.configurar_credenciales(httpx.Client(transport=nasa))


def test_api_ndvi_sin_credenciales_responde_503(monkeypatch):
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)
    r = TestClient(api.app).post("/ndvi", json=dict(
        lote_id="lote-7", poligono=LOTE, desde="2026-01-01", hasta="2026-02-01"))
    assert r.status_code == 503


def test_api_ndvi_poligono_invalido_responde_422():
    r = TestClient(api.app).post("/ndvi", json=dict(
        lote_id="lote-7", poligono={"type": "Point", "coordinates": [0, 0]},
        desde="2026-01-01", hasta="2026-02-01"))
    assert r.status_code == 422


class EscenaFalsa:
    """Imita un item STAC de HLS con bandas guardadas en GeoTIFF locales."""

    def __init__(self, carpeta, coleccion, valores):
        import rasterio
        from rasterio.transform import from_origin
        from rasterio.warp import transform

        self.id = "falsa"
        self.collection_id = f"{coleccion}_2.0"
        self.datetime = __import__("datetime").datetime(2026, 1, 15, 14, 0)
        self.assets = {}
        # grilla UTM 20S de 40x40 píxeles de 30 m que cubre el lote
        xs, ys = transform("EPSG:4326", "EPSG:32720", [-65.302], [-33.698])
        perfil = dict(driver="GTiff", width=40, height=40, count=1, crs="EPSG:32720",
                      transform=from_origin(xs[0], ys[0], 30, 30))
        for asset, valor in valores.items():
            ruta = f"{carpeta}/{asset}.tif"
            dtype = "uint8" if asset == "Fmask" else "int16"
            with rasterio.open(ruta, "w", dtype=dtype, **perfil) as destino:
                destino.write(np.full((40, 40), valor, dtype=dtype), 1)
            self.assets[asset] = type("Asset", (), {"href": ruta})()


def test_procesar_escena_s30_de_punta_a_punta(tmp_path):
    escena = EscenaFalsa(tmp_path, "HLSS30", {"B04": 400, "B8A": 3600, "B11": 1800, "Fmask": 64})
    resultado = hls.procesar_escena("lote-7", escena, LOTE)
    ndvi = next(o for o, _ in resultado if o.variable == "ndvi")
    ndmi = next(o for o, _ in resultado if o.variable == "ndmi")
    assert ndvi.valor == pytest.approx(0.8) and ndvi.calidad == "buena"
    assert ndmi.valor == pytest.approx(1 / 3, abs=1e-3)
    assert ndvi.fecha == date(2026, 1, 15)


def test_procesar_escena_nublada_se_descarta(tmp_path):
    escena = EscenaFalsa(tmp_path, "HLSL30", {"B04": 400, "B05": 3600, "B06": 1800, "Fmask": 2})
    resultado = hls.procesar_escena("lote-7", escena, LOTE)
    assert all(o.valor is None and o.calidad == "descartada" for o, _ in resultado)


def test_busqueda_por_bbox_con_reintento(monkeypatch):
    import pystac_client

    llamadas = []

    class Busqueda:
        def __init__(self, coleccion):
            self.coleccion = coleccion

        def items(self):
            nubes = 10 if self.coleccion == "HLSL30_2.0" else 90
            return [type("Item", (), {"properties": {"eo:cloud_cover": nubes}})()]

    class Cliente:
        def search(self, **kwargs):
            llamadas.append(kwargs)
            if len(llamadas) == 1:
                raise RuntimeError("Oops! Something has gone wrong")
            return Busqueda(kwargs["collections"][0])

    monkeypatch.setattr(pystac_client.Client, "open", staticmethod(lambda url: Cliente()))
    monkeypatch.setattr("time.sleep", lambda s: None)
    escenas = hls.buscar_escenas(LOTE, date(2026, 1, 1), date(2026, 2, 1), nubosidad_max=70)
    assert len(escenas) == 1  # la de 90 % de nubes se filtra
    assert "intersects" not in llamadas[0]
    assert llamadas[0]["bbox"] == pytest.approx([-65.30, -33.705, -65.295, -33.70])
    assert len(llamadas) == 3  # falla, reintento ok, segunda colección


def test_busqueda_que_siempre_falla_da_error_claro(monkeypatch):
    import pystac_client

    class Cliente:
        def search(self, **kwargs):
            raise RuntimeError("caído")

    monkeypatch.setattr(pystac_client.Client, "open", staticmethod(lambda url: Cliente()))
    monkeypatch.setattr("time.sleep", lambda s: None)
    with pytest.raises(hls.ErrorHLS):
        hls.buscar_escenas(LOTE, date(2026, 1, 1), date(2026, 2, 1), nubosidad_max=70)
