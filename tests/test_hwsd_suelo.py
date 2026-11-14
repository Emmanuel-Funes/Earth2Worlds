"""HWSD como respaldo de suelo de GeoINTA (spec 031). Sin internet: CMR, descarga y NetCDF simulados."""

from pathlib import Path

import httpx
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from rotaterra.fuentes import earthdata, hwsd_suelo
from rotaterra.geo import poligono_desde_esquinas

# lote de prueba de ~50 ha alrededor de -33,7025; -65,2975 (el mismo de San Luis)
POLIGONO = poligono_desde_esquinas("-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300")


@pytest.fixture
def credenciales(monkeypatch):
    monkeypatch.setenv("EARTHDATA_USERNAME", "usuario")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "clave")


# ---------- triángulo textural del USDA ----------

@pytest.mark.parametrize("arena, arcilla, codigo", [
    (83, 6, 2),    # areno franco: el lote de San Luis (investigación 028)
    (90, 3, 1),    # arenoso
    (60, 10, 3),   # franco arenoso
    (40, 15, 4),   # franco
    (45, 5, 5),    # franco limoso
    (5, 5, 6),     # limoso
    (65, 20, 7),   # franco arcillo arenoso
    (30, 35, 8),   # franco arcilloso
    (15, 30, 9),   # franco arcillo limoso
    (50, 40, 10),  # arcillo arenoso
    (10, 45, 11),  # arcillo limoso
    (10, 60, 12),  # arcilloso
])
def test_triangulo_textural_del_usda(arena, arcilla, codigo):
    assert hwsd_suelo.clase_textural(arena, arcilla) == codigo


def test_el_lote_de_san_luis_es_areno_franco():
    # 83 % arena, 6 % arcilla (HWSD en la investigación 028) -> areno franco, clase común 2
    assert hwsd_suelo.clase_textural(83, 6) == 2
    assert hwsd_suelo.NOMBRE_CLASE[2] == "areno franco"


# ---------- lectura de la celda del NetCDF (con un ráster real de prueba) ----------

def escribir_raster(ruta: Path, valor: float, nodata: float = -1.0) -> Path:
    """Un ráster de 0,05° que cubre el lote; rasterio lo lee igual que un NetCDF de HWSD."""
    datos = np.full((4, 4), float(valor), dtype="float32")
    datos[0, 0] = nodata  # una esquina sin dato
    transform = from_origin(-65.40, -33.60, 0.05, 0.05)  # oeste, norte, paso en x, paso en y
    with rasterio.open(ruta, "w", driver="GTiff", height=4, width=4, count=1, dtype="float32",
                       crs="EPSG:4326", transform=transform, nodata=nodata) as destino:
        destino.write(datos, 1)
    return ruta


def test_valor_de_celda_lee_el_punto(tmp_path):
    ruta = escribir_raster(tmp_path / "t_sand.tif", 83.0)
    valor, resolucion = hwsd_suelo.valor_de_celda(ruta, -33.7025, -65.2975)
    assert valor == 83.0
    assert 4000 < resolucion < 6000  # 0,05° en esa latitud ≈ 4,6 km


def test_valor_de_celda_descarta_el_relleno(tmp_path):
    ruta = escribir_raster(tmp_path / "t_clay.tif", 6.0, nodata=-1.0)
    valor, _ = hwsd_suelo.valor_de_celda(ruta, -33.625, -65.375)  # cae en la esquina (0,0) = relleno
    assert valor is None


def test_valor_de_celda_fuera_de_la_grilla_avisa(tmp_path):
    ruta = escribir_raster(tmp_path / "t_sand.tif", 83.0)
    with pytest.raises(hwsd_suelo.ErrorHWSD, match="fuera de la grilla"):
        hwsd_suelo.valor_de_celda(ruta, 10.0, 10.0)


# ---------- armado de observaciones ----------

def test_observacion_textura_buena_es_dudosa_y_lleva_la_clase():
    o = hwsd_suelo.observacion_textura("lote-7", "suelo_textura_0_15cm", "0–30 cm usada para 0–15 cm",
                                       83.0, 11.0, 6.0, 4600)
    assert (o.valor, o.variable, o.fuente, o.calidad, o.unidad) == (
        2.0, "suelo_textura_0_15cm", "HWSD", "dudosa", hwsd_suelo.UNIDAD_TEXTURA)
    assert "areno franco" in o.nota and "Respaldo de GeoINTA" in o.nota and "0–15 cm" in o.nota
    assert o.calidad != "buena"  # HWSD es un modelo regional, nunca `buena`


def test_observacion_textura_fuera_de_rango_no_inventa():
    o = hwsd_suelo.observacion_textura("lote-7", "suelo_textura_0_15cm", "x", 83.0, None, 6.0, 4600)
    assert o.valor is None and o.calidad == "descartada"
    o2 = hwsd_suelo.observacion_textura("lote-7", "suelo_textura_0_15cm", "x", 120.0, 0.0, 6.0, 4600)
    assert o2.valor is None and o2.calidad == "descartada"


def test_observacion_ph_buena_es_dudosa():
    o = hwsd_suelo.observacion_ph("lote-7", "suelo_ph_0_30cm", "0–30 cm", 8.1, 4600)
    assert (o.valor, o.variable, o.unidad, o.calidad, o.fuente) == (8.1, "suelo_ph_0_30cm", "pH", "dudosa", "HWSD")
    assert "pH 8.10" in o.nota


@pytest.mark.parametrize("ph", [None, 0.0, 15.0, -3.0])
def test_observacion_ph_fuera_de_rango_no_inventa(ph):
    o = hwsd_suelo.observacion_ph("lote-7", "suelo_ph_0_30cm", "0–30 cm", ph, 4600)
    assert o.valor is None and o.calidad == "descartada"


# ---------- consulta completa (CMR y descarga simulados) ----------

class NASAFalsa:
    """CMR y descarga simulados: cada capa de HWSD es un archivo con un valor fijo por celda."""

    def __init__(self, valores_por_capa):
        self.valores = valores_por_capa  # {'T_SAND': 83.0, ...}

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        url = str(pedido.url)
        if "find_or_create_token" in url:
            return httpx.Response(200, json={"access_token": "tk"})
        if "/collections.umm_json" in url:
            return httpx.Response(200, json={"items": [{"meta": {"concept-id": "C-HWSD"},
                                                        "umm": {"Version": "1"}}]})
        if "/granules.umm_json" in url:
            items = [{"umm": {"GranuleUR": capa, "RelatedUrls": [
                {"Type": "GET DATA", "URL": f"https://ornl.example/{capa}.nc4"}]}}
                for capa in self.valores]
            return httpx.Response(200, json={"items": items})
        return httpx.Response(404)


@pytest.fixture
def suelo_sintetico(monkeypatch, tmp_path):
    """Hace que la descarga y la lectura devuelvan valores fijos por capa, sin tocar la red ni archivos reales."""
    valores = {"T_SAND": 83.0, "T_SILT": 11.0, "T_CLAY": 6.0, "S_SAND": 84.0, "S_CLAY": 5.0,
               "T_PH_H2O": 8.1, "S_PH_H2O": 8.4}

    def archivo(cliente, coleccion_id, capa):
        return tmp_path / capa  # un path ficticio que codifica la capa en su nombre

    def celda(ruta, lat, lon):
        return valores.get(ruta.name), 4600

    monkeypatch.setattr(hwsd_suelo, "archivo_de_capa", archivo)
    monkeypatch.setattr(hwsd_suelo, "valor_de_celda", celda)
    return valores


def test_obtener_suelo_arma_textura_y_ph(credenciales, suelo_sintetico):
    cliente = httpx.Client(transport=httpx.MockTransport(NASAFalsa(suelo_sintetico)))
    obs = hwsd_suelo.obtener_suelo("lote-7", POLIGONO, cliente=cliente)
    por_variable = {o.variable: o for o in obs}
    assert set(por_variable) == {
        "suelo_textura_0_15cm", "suelo_textura_15_30cm", "suelo_textura_30_60cm", "suelo_textura_60_100cm",
        "suelo_ph_0_30cm", "suelo_ph_30_100cm"}
    # superficie (83/6) y subsuelo (84/5) dan los dos areno franco (clase 2)
    assert por_variable["suelo_textura_0_15cm"].valor == 2.0
    assert por_variable["suelo_textura_15_30cm"].valor == 2.0
    assert por_variable["suelo_textura_30_60cm"].valor == 2.0
    assert por_variable["suelo_ph_0_30cm"].valor == 8.1
    assert por_variable["suelo_ph_30_100cm"].valor == 8.4
    assert all(o.fuente == "HWSD" and o.calidad == "dudosa" for o in obs)


def test_obtener_suelo_subsuelo_calcula_el_limo(credenciales, suelo_sintetico):
    # el subsuelo trae arena (84) y arcilla (5); el limo es el resto (11) -> areno franco
    cliente = httpx.Client(transport=httpx.MockTransport(NASAFalsa(suelo_sintetico)))
    obs = {o.variable: o for o in hwsd_suelo.obtener_suelo("lote-7", POLIGONO, cliente=cliente)}
    assert obs["suelo_textura_60_100cm"].valor == 2.0


def test_pedido_invalido_no_llama_a_la_nasa(credenciales):
    malo = {"type": "Point", "coordinates": [0, 0]}
    with pytest.raises(ValueError):
        hwsd_suelo.obtener_suelo("lote-7", malo,
                                 cliente=httpx.Client(transport=httpx.MockTransport(lambda p: httpx.Response(500))))


def test_sin_credenciales_pide_credenciales(monkeypatch):
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)
    with pytest.raises(earthdata.FaltanCredenciales):
        hwsd_suelo.obtener_suelo("lote-7", POLIGONO)


def test_se_anuncia_como_respaldo_de_geointa():
    (satelite,) = hwsd_suelo.SATELITES
    assert (satelite.nombre, satelite.respaldo_de, satelite.estatico) == ("GeoINTA:HWSD", "GeoINTA", True)
