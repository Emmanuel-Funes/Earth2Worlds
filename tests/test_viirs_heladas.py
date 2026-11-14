"""VIIRS LST nocturna para alertar heladas (spec 030). Sin internet: CMR y OPeNDAP simulados."""

from datetime import date

import httpx
import numpy as np
import pytest

from rotaterra.fuentes import earthdata, viirs_heladas
from rotaterra.geo import poligono_desde_esquinas

# lote de prueba de ~50 ha alrededor de -33,7025; -65,2975 (el mismo de VIIRS NDVI)
POLIGONO = poligono_desde_esquinas("-33.699, -65.301; -33.699, -65.294; -33.706, -65.294; -33.706, -65.301")

GRUPO = "/HDFEOS/GRIDS/VIIRS_Grid_Daily_1km_LST/Data Fields"
RUTA_LST = f"{GRUPO}/LST_1KM"
DMR = """<?xml version="1.0" encoding="UTF-8"?>
<Dataset xmlns="http://xml.opendap.org/ns/DAP/4.0#" name="VJ121A1N.h5">
  <Group name="HDFEOS"><Group name="GRIDS"><Group name="VIIRS_Grid_Daily_1km_LST">
    <Group name="Data Fields">
      <UInt16 name="LST_1KM"/>
      <UInt8 name="QC_Night"/>
    </Group>
  </Group></Group></Group>
</Dataset>"""

# crudo * 0,02 = kelvin. -3,0 °C = 270,15 K ≈ crudo 13508; 2,0 °C = 275,15 K = crudo 13757,5
CRUDO_FRIO = 13508   # ≈ -3,0 °C
CRUDO_TEMPLADO = 13758  # = 2,0 °C


@pytest.fixture(autouse=True)
def sin_rutas_guardadas():
    viirs_heladas._RUTAS.clear()


@pytest.fixture
def credenciales(monkeypatch):
    monkeypatch.setenv("EARTHDATA_USERNAME", "usuario")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "clave")


def test_celda_del_lote_es_la_mitad_que_en_viirs_ndvi():
    # misma grilla sinusoidal que el VIIRS de NDVI (500 m → 888,1362) con píxeles del doble (1 km)
    assert viirs_heladas.celda(-33.7025, -65.2975) == (12, 12, 444, 681)


def test_coordenadas_vuelven_al_mismo_pixel():
    h, v, f0, f1, c0, c1 = viirs_heladas.ventana(POLIGONO)
    lat, lon = viirs_heladas.coordenadas(h, v, f0, f1, c0, c1)
    assert lat.shape == (f1 - f0 + 1, c1 - c0 + 1)
    assert viirs_heladas.celda(lat[0, 0], lon[0, 0]) == (h, v, f0, c0)
    assert viirs_heladas.celda(lat[-1, -1], lon[-1, -1]) == (h, v, f1, c1)


def test_ruta_lst_sale_de_los_metadatos():
    assert viirs_heladas.ruta_lst(DMR) == RUTA_LST


def test_metadatos_sin_lst_avisan():
    with pytest.raises(viirs_heladas.ErrorVIIRSHeladas, match="LST_1KM"):
        viirs_heladas.ruta_lst(DMR.replace("LST_1KM", "Emis_14"))


def ventana_sintetica(crudo=CRUDO_TEMPLADO, poligono=POLIGONO):
    h, v, f0, f1, c0, c1 = viirs_heladas.ventana(poligono)
    lat, lon = viirs_heladas.coordenadas(h, v, f0, f1, c0, c1)
    return np.full(lat.shape, float(crudo), dtype="float64"), lat, lon


def test_noche_limpia_es_buena_y_devuelve_celsius():
    lst, lat, lon = ventana_sintetica(CRUDO_TEMPLADO)
    o, pct = viirs_heladas.resumir("lote-7", POLIGONO, lst, lat, lon, date(2026, 9, 22), "NOAA-20", "VJ121A1N")
    assert (o.valor, o.calidad, o.fecha, o.fuente, o.resolucion_m, o.variable, o.unidad) == (
        2.0, "buena", date(2026, 9, 22), "VIIRS", 1000, "temp_sup_min_c", "°C")
    assert pct == 100 and "superficie, no del aire" in o.nota and "NOAA-20" in o.nota
    assert "riesgo de helada" not in o.nota


def test_helada_lleva_el_aviso_en_la_nota():
    lst, lat, lon = ventana_sintetica(CRUDO_FRIO)
    o, _ = viirs_heladas.resumir("lote-7", POLIGONO, lst, lat, lon, date(2026, 9, 22), "NOAA-20", "VJ121A1N")
    assert o.valor == -3.0 and o.calidad == "buena" and "riesgo de helada" in o.nota


def test_nubes_crudo_cero_descartan_sin_inventar():
    lst, lat, lon = ventana_sintetica(0)
    o, pct = viirs_heladas.resumir("lote-7", POLIGONO, lst, lat, lon, date(2026, 9, 22), "NOAA-20", "VJ121A1N")
    assert o.valor is None and o.calidad == "descartada" and pct == 0


def test_valor_fuera_del_rango_fisico_no_cuenta():
    lst, lat, lon = ventana_sintetica(60000)  # 60000*0,02 = 1200 K, imposible
    o, _ = viirs_heladas.resumir("lote-7", POLIGONO, lst, lat, lon, date(2026, 9, 22), "NOAA-20", "VJ121A1N")
    assert o.valor is None and o.calidad == "descartada"


def test_toma_el_pixel_mas_frio_del_lote():
    grande = poligono_desde_esquinas("-33.69, -65.31; -33.69, -65.29; -33.71, -65.29; -33.71, -65.31")  # ~400 ha
    lst, lat, lon = ventana_sintetica(CRUDO_TEMPLADO, poligono=grande)
    from shapely.geometry import Point, shape
    lote = shape(grande)
    adentro = [(i, j) for i in range(lat.shape[0]) for j in range(lat.shape[1])
               if lote.contains(Point(lon[i, j], lat[i, j]))]
    i, j = adentro[0]
    lst[i, j] = CRUDO_FRIO  # un píxel del lote más frío
    o, _ = viirs_heladas.resumir("lote-7", grande, lst, lat, lon, date(2026, 9, 22), "NOAA-20", "VJ121A1N")
    assert o.valor == -3.0  # gana el más frío


def test_lote_menor_a_un_pixel_usa_el_del_centro():
    chico = poligono_desde_esquinas("-33.7024, -65.2976; -33.7024, -65.2974; -33.7026, -65.2974; -33.7026, -65.2976")
    lst, lat, lon = ventana_sintetica(CRUDO_TEMPLADO, poligono=chico)
    o, _ = viirs_heladas.resumir("lote-7", chico, lst, lat, lon, date(2026, 9, 22), "NOAA-20", "VJ121A1N")
    assert o.valor == 2.0 and "menor a un píxel" in o.nota


def test_fecha_granulo():
    assert viirs_heladas.fecha_granulo("VJ121A1N.A2026265.h12v12.002.2026266") == date(2026, 9, 22)


class NASAFalsa:
    """CMR y OPeNDAP simulados: NOAA-20 y NOAA-21 traen una noche cada uno."""

    def __init__(self, por_producto):
        self.por_producto = por_producto
        self.pedidos = []

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        url = str(pedido.url)
        self.pedidos.append(pedido)
        if "find_or_create_token" in url:
            return httpx.Response(200, json={"access_token": "tk"})
        if "/collections.umm_json" in url:
            nombre = pedido.url.params["short_name"]
            if nombre not in self.por_producto:
                return httpx.Response(200, json={"items": []})
            return httpx.Response(200, json={"items": [{"meta": {"concept-id": f"C-{nombre}"},
                                                        "umm": {"Version": "002"}}]})
        if "/granules.umm_json" in url:
            producto = pedido.url.params["collection_concept_id"][2:]
            dia = self.por_producto[producto][0]
            nombres = [f"{producto}.A2026{dia:03d}.h12v12.002.1", f"{producto}.A2026{dia:03d}.h12v13.002.1"]
            return httpx.Response(200, json={"items": [{"umm": {"GranuleUR": n, "RelatedUrls": [
                {"URL": f"https://opendap.earthdata.nasa.gov/collections/C-{producto}/granules/{n}.h5"}]}}
                for n in nombres]})
        if url.endswith(".dmr"):
            return httpx.Response(200, text=DMR)
        if ".dap.csv" in url:
            assert "h12v12" in url
            producto = url.split("/granules/")[1].split(".")[0]
            crudo = self.por_producto[producto][1]
            lineas = ["Dataset: x"]
            for i, fila in enumerate(crudo):
                lineas.append(f"{RUTA_LST}[{i}], " + ", ".join(repr(float(v)) for v in fila))
            return httpx.Response(200, text="\n".join(lineas) + "\n")
        return httpx.Response(404)


def test_obtener_heladas_junta_noaa20_y_noaa21(credenciales):
    frio = ventana_sintetica(CRUDO_FRIO)[0]
    templado = ventana_sintetica(CRUDO_TEMPLADO)[0]
    nasa = NASAFalsa({"VJ121A1N": (265, frio), "VJ221A1N": (266, templado)})
    cliente = httpx.Client(transport=httpx.MockTransport(nasa))
    obs = viirs_heladas.obtener_heladas("lote-7", POLIGONO, date(2026, 9, 22), date(2026, 9, 23), cliente=cliente)
    assert [(o.fecha, o.valor, o.calidad) for o in obs] == [(date(2026, 9, 22), -3.0, "buena"),
                                                            (date(2026, 9, 23), 2.0, "buena")]
    assert "NOAA-20" in obs[0].nota and "riesgo de helada" in obs[0].nota


def test_mismo_dia_gana_la_noche_mas_limpia(credenciales):
    nublada = ventana_sintetica(0)[0]          # NOAA-20: todo nubes el día 265
    limpia = ventana_sintetica(CRUDO_FRIO)[0]  # NOAA-21: dato el día 265
    nasa = NASAFalsa({"VJ121A1N": (265, nublada), "VJ221A1N": (265, limpia)})
    cliente = httpx.Client(transport=httpx.MockTransport(nasa))
    obs = viirs_heladas.obtener_heladas("lote-7", POLIGONO, date(2026, 9, 22), date(2026, 9, 22), cliente=cliente)
    assert len(obs) == 1 and obs[0].valor == -3.0 and obs[0].calidad == "buena"


def test_un_satelite_sin_coleccion_no_frena_al_otro(credenciales):
    nasa = NASAFalsa({"VJ121A1N": (265, ventana_sintetica(CRUDO_FRIO)[0])})  # NOAA-21 no publicado
    cliente = httpx.Client(transport=httpx.MockTransport(nasa))
    obs = viirs_heladas.obtener_heladas("lote-7", POLIGONO, date(2026, 9, 22), date(2026, 9, 22), cliente=cliente)
    assert [(o.fecha, o.valor) for o in obs] == [(date(2026, 9, 22), -3.0)]


@pytest.mark.parametrize("desde, hasta", [
    (date(2026, 9, 22), date(2026, 9, 21)),
    (date(2024, 1, 1), date(2026, 1, 1)),
])
def test_pedido_invalido_no_llama_a_la_nasa(desde, hasta, credenciales):
    with pytest.raises(ValueError):
        viirs_heladas.obtener_heladas("lote-7", POLIGONO, desde, hasta,
                                      cliente=httpx.Client(transport=httpx.MockTransport(lambda p: httpx.Response(500))))


def test_sin_credenciales_pide_credenciales(monkeypatch):
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)
    with pytest.raises(earthdata.FaltanCredenciales):
        viirs_heladas.obtener_heladas("lote-7", POLIGONO, date(2026, 9, 22), date(2026, 9, 22))


def test_se_anuncia_como_fuente_propia_sin_respaldo():
    (satelite,) = viirs_heladas.SATELITES
    assert (satelite.nombre, satelite.respaldo_de, satelite.orden, satelite.estatico) == (
        "VIIRS_LST", None, 1, False)
