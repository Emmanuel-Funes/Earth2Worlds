"""ASTER GDEM sin internet: CMR + Earthdata simulados con httpx.MockTransport y mosaicos GeoTIFF sintéticos en memoria."""

import math
from datetime import date

import httpx
import numpy as np
import pytest
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import Affine

from rotaterra.fuentes import aster
from rotaterra.geo import poligono_desde_esquinas

SEG = 1 / 3600
PASO = 0.2  # m por píxel hacia el este (pendiente conocida)
# el mismo lote de prueba de NASADEM/COPDEM: 25,7 ha en -33,70; -65,30
LOTE = poligono_desde_esquinas("-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300")


@pytest.fixture
def credenciales(monkeypatch):
    monkeypatch.setenv("EARTHDATA_USERNAME", "usuario")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "clave")


def plano(lat, lon):
    """Relieve que sube 0,2 m por píxel hacia el este, sobre 480 m."""
    return 480 + PASO * np.round((lon + 66) * 3600)


def tif_bytes(oeste, norte, filas, columnas, altura) -> bytes:
    """GeoTIFF de 1 banda en memoria; `oeste`/`norte` = centro del píxel de arriba a la izquierda."""
    lats = norte - np.arange(filas) * SEG
    lons = oeste + np.arange(columnas) * SEG
    lon_m, lat_m = np.meshgrid(lons, lats)
    datos = altura(lat_m, lon_m).astype("float32")
    transformada = Affine(SEG, 0, oeste - SEG / 2, 0, -SEG, norte + SEG / 2)
    with MemoryFile() as memoria:
        with memoria.open(driver="GTiff", width=columnas, height=filas, count=1, dtype="float32",
                          crs="EPSG:4326", transform=transformada) as destino:
            destino.write(datos, 1)
        return memoria.read()


class NASAFalsa:
    """CMR + descarga de Earthdata simulados. `tiles` = dict {sufijo_url: bytes del GeoTIFF}."""

    def __init__(self, tiles):
        self.tiles, self.descargas, self.pedidos = tiles, 0, []

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        url = str(pedido.url)
        if "find_or_create_token" in url:
            return httpx.Response(200, json={"access_token": "token"})
        if "collections.umm_json" in url:
            return httpx.Response(200, json={"items": [
                {"meta": {"concept-id": "C-ASTGTM"}, "umm": {"Version": "003"}}]})
        if "granules.umm_json" in url:
            self.pedidos.append(pedido.url.params["bounding_box"])
            items = [{"umm": {"RelatedUrls": [
                {"Type": "GET DATA", "URL": f"https://data.lpdaac/ASTGTMV003_{s}_dem.tif"},
                {"Type": "GET DATA", "URL": f"https://data.lpdaac/ASTGTMV003_{s}_num.tif"},
                {"Type": "USE SERVICE API", "URL": f"https://opendap/{s}"}]}}
                     for s in self.tiles]
            return httpx.Response(200, json={"items": items})
        if url.endswith("_dem.tif"):
            assert pedido.headers["Authorization"] == "Bearer token"
            self.descargas += 1
            nombre = url.rsplit("/", 1)[-1].removeprefix("ASTGTMV003_").removesuffix("_dem.tif")
            return httpx.Response(200, content=self.tiles[nombre])
        return httpx.Response(404)


def cliente_de(nasa: NASAFalsa) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(nasa))


# ---------- cálculo de punta a punta ----------

def test_lote_de_prueba_da_las_7_variables(credenciales):
    nasa = NASAFalsa({"S34W066": tif_bytes(-65.31, -33.69, 80, 80, plano)})
    obs = aster.obtener_altimetria("lote-7", LOTE, cliente=cliente_de(nasa))
    valores = {o.variable: o.valor for o in obs}
    assert [o.variable for o in obs] == [v for v, _ in aster.VARIABLES]
    assert {o.fuente for o in obs} == {"ASTER"}
    assert {o.fecha for o in obs} == {date(2019, 8, 5)}  # publicación de ASTER GDEM v3 (dato fijo)
    assert {o.resolucion_m for o in obs} == {30}
    assert {o.calidad for o in obs} == {"buena"}
    # 17 columnas de 0,2 m dentro del lote: 480 + 0,2 × columna desde el borde oeste
    oeste = round((-65.3 + 66) * 3600)
    assert valores["altura_min_m"] == round(480 + PASO * (oeste + 1), 1)
    assert valores["altura_max_m"] == round(480 + PASO * (oeste + 17), 1)
    lado_x = aster._R * math.radians(SEG) * math.cos(math.radians(-33.7025))
    assert valores["pendiente_media_pct"] == pytest.approx(100 * PASO / lado_x, abs=0.02)
    ha = aster.superficie_ha(LOTE)
    assert ha == pytest.approx(25.7, abs=0.1)
    suma = valores["superficie_bajo_ha"] + valores["superficie_media_loma_ha"] + valores["superficie_loma_ha"]
    assert suma == pytest.approx(ha, abs=0.02)
    assert valores["superficie_bajo_ha"] > 0 and valores["superficie_loma_ha"] > 0
    assert "289 de 289 píxeles" in obs[0].nota
    assert "ASTER GDEM v3" in obs[0].nota and "modelo de superficie" in obs[0].nota
    assert "2000–2013" in obs[0].nota and "respaldo de NASADEM" in obs[0].nota
    assert "umbral supuesto" in obs[4].nota


def test_lote_que_cruza_mosaicos_se_une_en_una_grilla(credenciales):
    # lote sobre el meridiano -65: un mosaico a cada lado, el plano continúa sin saltos
    cruza = poligono_desde_esquinas("-33.700, -65.003; -33.700, -64.997; -33.705, -64.997; -33.705, -65.003")
    nasa = NASAFalsa({"S34W066": tif_bytes(-65 - 30 * SEG, -33.69, 60, 30, plano),
                      "S34W065": tif_bytes(-65.0, -33.69, 60, 30, plano)})
    obs = aster.obtener_altimetria("lote-cruza", cruza, cliente=cliente_de(nasa))
    valores = {o.variable: o.valor for o in obs}
    assert nasa.descargas == 2
    lado_x = aster._R * math.radians(SEG) * math.cos(math.radians(-33.7025))
    assert valores["pendiente_media_pct"] == pytest.approx(100 * PASO / lado_x, abs=0.02)
    assert valores["altura_min_m"] < 480 + PASO * 3600 < valores["altura_max_m"]
    assert {o.calidad for o in obs} == {"buena"}


def test_pixeles_invalidos_no_cuentan(credenciales):
    def con_huecos(lat, lon):
        h = plano(lat, lon)
        h[40:45, 40:45] = aster.INVALIDO  # un hueco de 5 × 5 dentro del lote
        return h

    nasa = NASAFalsa({"S34W066": tif_bytes(-65.31, -33.69, 80, 80, con_huecos)})
    obs = aster.obtener_altimetria("lote-7", LOTE, cliente=cliente_de(nasa))
    assert all(o.valor is not None for o in obs)
    assert "264 de 289 píxeles" in obs[0].nota


def test_sin_pixeles_validos_todo_descartado(credenciales):
    nasa = NASAFalsa({"S34W066": tif_bytes(-65.31, -33.69, 80, 80,
                                           lambda lat, lon: np.full(lat.shape, aster.INVALIDO))})
    obs = aster.obtener_altimetria("lote-7", LOTE, cliente=cliente_de(nasa))
    assert len(obs) == 7 and all(o.valor is None and o.calidad == "descartada" for o in obs)
    assert "Sin píxeles con dato" in obs[0].nota


def test_lote_chico_es_dudoso(credenciales):
    nasa = NASAFalsa({"S34W066": tif_bytes(-65.31, -33.69, 80, 80, plano)})
    chico = poligono_desde_esquinas("-33.7000, -65.3000; -33.7000, -65.2995; -33.7005, -65.2995; -33.7005, -65.3000")
    obs = aster.obtener_altimetria("lote-chico", chico, cliente=cliente_de(nasa))
    assert {o.calidad for o in obs if o.valor is not None} == {"dudosa"}
    assert "menos de 10 píxeles" in obs[0].nota


def test_superficie_del_lote():
    assert aster.superficie_ha(LOTE) == pytest.approx(25.7, abs=0.1)


# ---------- errores ----------

def test_lote_sin_datos_falla_con_mensaje_claro(credenciales):
    nasa = NASAFalsa({})  # CMR no devuelve granules
    with pytest.raises(aster.ErrorASTER, match="no tiene datos"):
        aster.obtener_altimetria("lote-mar", LOTE, cliente=cliente_de(nasa))


def test_acceso_negado_explica_que_hacer(credenciales):
    def negar(pedido):
        if str(pedido.url).endswith("_dem.tif"):
            return httpx.Response(403)
        return NASAFalsa({"S34W066": b"x"})(pedido)

    with pytest.raises(aster.ErrorASTER, match="LP DAAC"):
        aster.obtener_altimetria("lote-7", LOTE, cliente=httpx.Client(transport=httpx.MockTransport(negar)))


def test_cmr_caido_es_error_del_respaldo(credenciales):
    cliente = httpx.Client(transport=httpx.MockTransport(
        lambda p: httpx.Response(200, json={"access_token": "t"}) if "find_or_create_token" in str(p.url)
        else httpx.Response(503)))
    with pytest.raises(aster.ErrorASTER, match="No se pudo obtener"):
        aster.obtener_altimetria("lote-7", LOTE, cliente=cliente)


def test_sin_credenciales(monkeypatch):
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    with pytest.raises(aster.earthdata.FaltanCredenciales):
        aster.obtener_altimetria("lote-7", LOTE)


def test_poligono_invalido():
    with pytest.raises(ValueError):
        aster.obtener_altimetria("lote-7", {"type": "Point", "coordinates": [0, 0]})


# ---------- registro (spec 009) ----------

def test_se_anuncia_como_respaldo_estatico_de_nasadem():
    [satelite] = aster.SATELITES
    assert satelite.nombre == "NASADEM:ASTER"
    assert satelite.respaldo_de == "NASADEM"
    assert satelite.estatico is True
    assert satelite.orden == 2  # después de Copernicus DEM (orden 1)


def test_pedir_usa_id_y_poligono_del_lote(monkeypatch):
    llamados = []
    monkeypatch.setattr(aster, "obtener_altimetria", lambda lote_id, poligono: llamados.append((lote_id, poligono)))
    aster.SATELITES[0].pedir({"id": "lote-7", "poligono": LOTE}, date(2026, 1, 1), date(2026, 1, 31))
    assert llamados == [("lote-7", LOTE)]
