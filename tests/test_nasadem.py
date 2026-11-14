import dataclasses
import io
import math
import zipfile
from datetime import date, timedelta

import httpx
import numpy as np
import pytest

from rotaterra import actualizar, base
from rotaterra.fuentes import nasadem
from rotaterra.geo import poligono_desde_esquinas

# lote de prueba de ~50 ha alrededor de -33,7025; -65,2975 (mosaico s34w066)
POLIGONO = poligono_desde_esquinas("-33.699, -65.301; -33.699, -65.294; -33.706, -65.294; -33.706, -65.301")
SUBA_POR_PIXEL = 0.3  # m por píxel hacia el este


@pytest.fixture
def credenciales(monkeypatch):
    monkeypatch.setenv("EARTHDATA_USERNAME", "usuario")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "clave")


@pytest.fixture(autouse=True)
def cache_vacio():
    nasadem._CACHE.clear()


def a_zip(alturas: np.ndarray, nombre="s34w066.hgt") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archivo:
        archivo.writestr(nombre, np.asarray(alturas).astype(">i2").tobytes())
    return buffer.getvalue()


def test_nombre_del_mosaico():
    assert nasadem.mosaico(-33.7, -65.3) == "s34w066"
    assert nasadem.mosaico(10.2, 5.5) == "n10e005"
    assert nasadem.esquina("s34w066") == (-34, -66)


def test_leer_hgt_del_zip():
    alturas = np.arange(9, dtype=">i2").reshape(3, 3)
    assert (nasadem.leer_hgt(a_zip(alturas)) == alturas).all()


def test_lote_inclinado_da_altura_pendiente_y_ambientes():
    # mosaico en metros enteros (como el real), con 1 m de suba cada ~3 píxeles
    alturas = (500 + np.tile(np.arange(3601) * SUBA_POR_PIXEL, (3601, 1))).astype(">i2")
    caja = (-65.301, -33.706, -65.294, -33.699)
    obs = {o.variable: o for o in nasadem.resumir("lote-7", POLIGONO, *nasadem.armar_grilla({"s34w066": alturas}, caja))}
    assert len(obs) == 7 and {o.fuente for o in obs.values()} == {"NASADEM"}
    assert all(o.fecha == date(2000, 2, 11) and o.calidad == "buena" for o in obs.values())
    # el lote va de la columna 2517 a la 2541 del mosaico (-65,301 a -65,294): 500 + 0,3 × columna
    assert obs["altura_min_m"].valor == int(500 + 2517 * 0.3)
    assert obs["altura_max_m"].valor == int(500 + 2541 * 0.3)
    # pendiente esperada: 0,3 m por ~25,7 m de píxel a esta latitud = ~1,2 %
    esperada = 100 * SUBA_POR_PIXEL / (nasadem._LADO_M * math.cos(math.radians(-33.7025)))
    assert obs["pendiente_media_pct"].valor == pytest.approx(esperada, rel=0.15)
    superficies = [obs[v].valor for v in ("superficie_bajo_ha", "superficie_media_loma_ha", "superficie_loma_ha")]
    assert all(s > 0 for s in superficies)
    assert sum(superficies) == pytest.approx(nasadem.superficie_ha(POLIGONO), abs=0.02)
    assert "umbral supuesto" in obs["superficie_bajo_ha"].nota


def test_lote_plano_es_todo_media_loma():
    alturas = np.full((3601, 3601), 420, dtype=">i2")
    caja = (-65.301, -33.706, -65.294, -33.699)
    obs = {o.variable: o for o in nasadem.resumir("lote-7", POLIGONO, *nasadem.armar_grilla({"s34w066": alturas}, caja))}
    assert obs["pendiente_media_pct"].valor == 0
    assert obs["superficie_bajo_ha"].valor == 0 and obs["superficie_loma_ha"].valor == 0
    assert obs["superficie_media_loma_ha"].valor == pytest.approx(nasadem.superficie_ha(POLIGONO), abs=0.01)


def test_superficie_del_lote():
    # 0,007° × 0,007° a -33,7°: ~777 m × ~648 m = ~50,4 ha
    assert nasadem.superficie_ha(POLIGONO) == pytest.approx(50.4, abs=0.5)


def test_relleno_no_inventa():
    alturas = np.full((3601, 3601), nasadem.RELLENO, dtype=">i2")
    caja = (-65.301, -33.706, -65.294, -33.699)
    obs = nasadem.resumir("lote-7", POLIGONO, *nasadem.armar_grilla({"s34w066": alturas}, caja))
    assert len(obs) == 7 and all(o.valor is None and o.calidad == "descartada" for o in obs)


def test_lote_chico_es_dudoso():
    chico = poligono_desde_esquinas("-33.7024, -65.2976; -33.7024, -65.2970; -33.7030, -65.2970; -33.7030, -65.2976")
    alturas = np.full((3601, 3601), 420, dtype=">i2")
    from shapely.geometry import shape

    obs = nasadem.resumir("lote-7", chico, *nasadem.armar_grilla({"s34w066": alturas}, shape(chico).bounds))
    assert all(o.calidad == "dudosa" for o in obs) and "menos de 10 píxeles" in obs[0].nota


def test_lote_que_cruza_dos_mosaicos():
    # lote sobre el meridiano -65: mitad en s34w066 (300 m) y mitad en s34w065 (310 m)
    cruzado = poligono_desde_esquinas("-33.700, -65.003; -33.700, -64.997; -33.703, -64.997; -33.703, -65.003")
    from shapely.geometry import shape

    mosaicos = {"s34w066": np.full((3601, 3601), 300, dtype=">i2"), "s34w065": np.full((3601, 3601), 310, dtype=">i2")}
    alturas, lats, lons = nasadem.armar_grilla(mosaicos, shape(cruzado).bounds)
    assert np.isfinite(alturas).all()
    obs = {o.variable: o for o in nasadem.resumir("lote-7", cruzado, alturas, lats, lons)}
    assert obs["altura_min_m"].valor == 300 and obs["altura_max_m"].valor == 310


class NASAFalsa:
    def __init__(self, contenido):
        self.contenido, self.descargas = contenido, 0

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        url = str(pedido.url)
        if "find_or_create_token" in url:
            return httpx.Response(200, json={"access_token": "token"})
        if "collections.umm_json" in url:
            return httpx.Response(200, json={"items": [{"meta": {"concept-id": "C1-LPCLOUD"}, "umm": {"Version": "001"}}]})
        if "granules.umm_json" in url:
            assert pedido.url.params["bounding_box"].startswith("-65.301")
            return httpx.Response(200, json={"items": [{"umm": {"GranuleUR": "NASADEM_HGT_s34w066", "RelatedUrls": [
                {"Type": "GET DATA", "URL": "https://data.lpdaac/NASADEM_HGT_s34w066.zip"},
                {"Type": "GET DATA", "URL": "s3://lp-prod-protected/NASADEM_HGT_s34w066.zip"}]}}]})
        if url.endswith(".zip"):
            assert pedido.headers["Authorization"] == "Bearer token"
            self.descargas += 1
            return httpx.Response(200, content=self.contenido)
        return httpx.Response(404)


def test_obtener_altimetria_de_punta_a_punta(credenciales):
    nasa = NASAFalsa(a_zip(np.full((3601, 3601), 420, dtype=">i2")))
    cliente = httpx.Client(transport=httpx.MockTransport(nasa))
    obs = nasadem.obtener_altimetria("lote-7", POLIGONO, cliente=cliente)
    assert {o.variable: o.valor for o in obs}["altura_media_m"] == 420
    # el segundo lote del mismo mosaico no lo vuelve a bajar
    nasadem.obtener_altimetria("lote-8", POLIGONO, cliente=cliente)
    assert nasa.descargas == 1


def test_acceso_negado_explica_que_hacer(credenciales):
    def negar(pedido):
        if str(pedido.url).endswith(".zip"):
            return httpx.Response(403)
        return NASAFalsa(b"")(pedido)

    with pytest.raises(nasadem.ErrorNASADEM, match="LP DAAC"):
        nasadem.obtener_altimetria("lote-7", POLIGONO, cliente=httpx.Client(transport=httpx.MockTransport(negar)))


def test_sin_credenciales(monkeypatch):
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    with pytest.raises(nasadem.earthdata.FaltanCredenciales):
        nasadem.obtener_altimetria("lote-7", POLIGONO)


def test_actualizacion_nocturna_lo_pide_una_sola_vez():
    motor = base.conectar("sqlite://")
    lote = base.guardar_lote(motor, "lote-7", "Lote 7", POLIGONO)
    pedidos = []

    def pedir(lote, desde, hasta):
        pedidos.append("NASADEM")
        alturas = np.full((3601, 3601), 420, dtype=">i2")
        return nasadem.resumir(lote["id"], lote["poligono"],
                               *nasadem.armar_grilla({"s34w066": alturas}, (-65.301, -33.706, -65.294, -33.699)))

    # el satélite tal como se anuncia al núcleo, con la descarga reemplazada por un mosaico sintético
    satelite = dataclasses.replace(nasadem.SATELITES[0], pedir=pedir)
    assert satelite.estatico
    hoy = date(2026, 3, 1)
    (r,) = actualizar.actualizar_lote(motor, lote, hoy, satelites=[satelite])
    assert r.resultado == "ok" and r.filas == 7
    (r,) = actualizar.actualizar_lote(motor, lote, hoy + timedelta(days=1), satelites=[satelite])
    assert r.resultado == "al_dia" and pedidos == ["NASADEM"]
