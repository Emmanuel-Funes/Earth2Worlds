from datetime import date

import httpx
import numpy as np
import pytest

from rotaterra.fuentes import viirs
from rotaterra.geo import poligono_desde_esquinas

# lote de prueba de ~50 ha alrededor de -33,7025; -65,2975 (el mismo de MODIS)
POLIGONO = poligono_desde_esquinas("-33.699, -65.301; -33.699, -65.294; -33.706, -65.294; -33.706, -65.301")

GRUPO = "/HDFEOS/GRIDS/VIIRS_Grid_16Day_VI_500m/Data Fields"
RUTAS = {
    "ndvi": f"{GRUPO}/500 m 16 days NDVI",
    "confiabilidad": f"{GRUPO}/500 m 16 days pixel reliability",
    "dia": f"{GRUPO}/500 m 16 days composite day of the year",
}
DMR = """<?xml version="1.0" encoding="UTF-8"?>
<Dataset xmlns="http://xml.opendap.org/ns/DAP/4.0#" name="VJ113A1.h5">
  <Group name="HDFEOS"><Group name="GRIDS"><Group name="VIIRS_Grid_16Day_VI_500m">
    <Group name="Data Fields">
      <Int16 name="500 m 16 days EVI"/>
      <Int16 name="500 m 16 days NDVI"/>
      <UInt8 name="500 m 16 days pixel reliability"/>
      <Int16 name="500 m 16 days composite day of the year"/>
    </Group>
  </Group></Group></Group>
</Dataset>"""


@pytest.fixture(autouse=True)
def sin_rutas_guardadas():
    viirs._RUTAS.clear()


@pytest.fixture
def credenciales(monkeypatch):
    monkeypatch.setenv("EARTHDATA_USERNAME", "usuario")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "clave")


def test_celda_del_lote_de_prueba_es_la_mitad_que_en_modis():
    # misma grilla que MODIS con píxeles del doble: MODIS da (12, 12, 1777, 2724) a 250 m
    assert viirs.celda(-33.7025, -65.2975) == (12, 12, 888, 1362)


def test_coordenadas_vuelven_al_mismo_pixel():
    h, v, f0, f1, c0, c1 = viirs.ventana(POLIGONO)
    lat, lon = viirs.coordenadas(h, v, f0, f1, c0, c1)
    assert lat.shape == (f1 - f0 + 1, c1 - c0 + 1)
    assert viirs.celda(lat[0, 0], lon[0, 0]) == (h, v, f0, c0)
    assert viirs.celda(lat[-1, -1], lon[-1, -1]) == (h, v, f1, c1)


def test_rutas_de_capas_salen_de_los_metadatos():
    assert viirs.rutas_de_capas(DMR) == RUTAS


def test_metadatos_sin_ndvi_avisan():
    with pytest.raises(viirs.ErrorVIIRS, match="ndvi"):
        viirs.rutas_de_capas(DMR.replace("500 m 16 days NDVI", "500 m 16 days EVI2"))


def ventana_sintetica(ndvi=6000, confiabilidad=0, dia=9, poligono=POLIGONO):
    h, v, f0, f1, c0, c1 = viirs.ventana(poligono)
    lat, lon = viirs.coordenadas(h, v, f0, f1, c0, c1)
    forma = lat.shape
    return {"ndvi": np.full(forma, ndvi, dtype=float), "confiabilidad": np.full(forma, confiabilidad, dtype=float),
            "dia": np.full(forma, dia, dtype=float), "lat": lat, "lon": lon}


def test_compuesto_limpio_es_bueno_y_usa_el_dia_de_adquisicion():
    o, pct = viirs.resumir("lote-7", POLIGONO, ventana_sintetica(), date(2026, 1, 1))
    assert (o.valor, o.calidad, o.fecha, o.fuente, o.resolucion_m) == (0.6, "buena", date(2026, 1, 9), "VIIRS", 500)
    assert pct == 100 and "Respaldo de HLS" in o.nota and "NOAA-20" in o.nota


def test_nubes_descartan_y_no_inventan():
    o, pct = viirs.resumir("lote-7", POLIGONO, ventana_sintetica(confiabilidad=3), date(2026, 1, 1))
    assert o.valor is None and o.calidad == "descartada" and pct == 0


def test_relleno_no_cuenta_como_dato():
    o, _ = viirs.resumir("lote-7", POLIGONO, ventana_sintetica(ndvi=-15000), date(2026, 1, 1))
    assert o.valor is None and o.calidad == "descartada"


def test_lote_parcialmente_nublado_es_dudoso():
    from shapely.geometry import Point, shape

    grande = poligono_desde_esquinas("-33.69, -65.31; -33.69, -65.29; -33.71, -65.29; -33.71, -65.31")  # ~400 ha
    datos = ventana_sintetica(poligono=grande)
    lote = shape(grande)
    adentro = [(i, j) for i in range(datos["lat"].shape[0]) for j in range(datos["lat"].shape[1])
               if lote.contains(Point(datos["lon"][i, j], datos["lat"][i, j]))]
    for i, j in adentro[: len(adentro) // 2]:  # la mitad del lote nublada
        datos["confiabilidad"][i, j] = 3
    o, pct = viirs.resumir("lote-7", grande, datos, date(2026, 1, 1))
    assert o.calidad == "dudosa" and o.valor == 0.6 and 40 <= pct <= 60


def test_compuesto_que_cruza_el_anio():
    o, _ = viirs.resumir("lote-7", POLIGONO, ventana_sintetica(dia=2), date(2025, 12, 19))
    assert o.fecha == date(2026, 1, 2)


def test_lote_menor_a_un_pixel_usa_el_del_centro():
    chico = poligono_desde_esquinas("-33.7024, -65.2976; -33.7024, -65.2974; -33.7026, -65.2974; -33.7026, -65.2976")
    o, _ = viirs.resumir("lote-7", chico, ventana_sintetica(), date(2026, 1, 1))
    assert o.valor == 0.6 and "menor a un píxel" in o.nota


def test_inicio_compuesto():
    assert viirs.inicio_compuesto("VJ213A1.A2026009.h12v12.002.2026026") == date(2026, 1, 9)


class NASAFalsa:
    """CMR y OPeNDAP simulados: NOAA-20 y NOAA-21 traen un compuesto cada uno."""

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
            assert "h12v12" in url and "%20" in pedido.url.params["dap4.ce"]
            producto = url.split("/granules/")[1].split(".")[0]
            datos = self.por_producto[producto][1]
            lineas = ["Dataset: x"]
            for capa, ruta in RUTAS.items():
                for i, fila in enumerate(datos[capa]):
                    lineas.append(f"{ruta}[{i}], " + ", ".join(repr(float(v)) for v in fila))
            return httpx.Response(200, text="\n".join(lineas) + "\n")
        return httpx.Response(404)


def test_obtener_ndvi_junta_noaa20_y_noaa21(credenciales):
    nasa = NASAFalsa({"VJ113A1": (1, ventana_sintetica(ndvi=7300, dia=9)),
                      "VJ213A1": (9, ventana_sintetica(ndvi=7500, dia=17))})
    cliente = httpx.Client(transport=httpx.MockTransport(nasa))
    obs = viirs.obtener_ndvi("lote-7", POLIGONO, date(2026, 1, 1), date(2026, 1, 31), cliente=cliente)
    assert [(o.fecha, o.valor, o.calidad) for o in obs] == [(date(2026, 1, 9), 0.73, "buena"),
                                                           (date(2026, 1, 17), 0.75, "buena")]
    assert "NOAA-20" in obs[0].nota and "NOAA-21" in obs[1].nota


def test_mismo_dia_gana_el_compuesto_mas_limpio(credenciales):
    nublado = ventana_sintetica(ndvi=5000, dia=9, confiabilidad=3)
    nasa = NASAFalsa({"VJ113A1": (1, nublado), "VJ213A1": (1, ventana_sintetica(ndvi=7500, dia=9))})
    # el nublado cae en la fecha de inicio (descartado); el limpio, en su día de adquisición
    obs = viirs.obtener_ndvi("lote-7", POLIGONO, date(2026, 1, 1), date(2026, 1, 31),
                             cliente=httpx.Client(transport=httpx.MockTransport(nasa)))
    limpio = [o for o in obs if o.fecha == date(2026, 1, 9)]
    assert [(o.valor, o.calidad) for o in limpio] == [(0.75, "buena")]


def test_si_falta_un_satelite_usa_el_otro(credenciales):
    nasa = NASAFalsa({"VJ213A1": (9, ventana_sintetica(ndvi=7500, dia=17))})
    obs = viirs.obtener_ndvi("lote-7", POLIGONO, date(2026, 1, 1), date(2026, 1, 31),
                             cliente=httpx.Client(transport=httpx.MockTransport(nasa)))
    assert [(o.fecha, o.valor) for o in obs] == [(date(2026, 1, 17), 0.75)]


def test_sin_archivos_es_error_y_no_lista_vacia(credenciales):
    nasa = NASAFalsa({})
    with pytest.raises(viirs.ErrorVIIRS, match="CMR no tiene"):
        viirs.obtener_ndvi("lote-7", POLIGONO, date(2026, 1, 1), date(2026, 1, 31),
                           cliente=httpx.Client(transport=httpx.MockTransport(nasa)))


def test_pedido_invalido():
    with pytest.raises(ValueError):
        viirs.obtener_ndvi("lote-7", POLIGONO, date(2026, 2, 1), date(2026, 1, 1))


def test_se_registra_como_segundo_respaldo_de_hls():
    (satelite,) = viirs.SATELITES
    assert (satelite.nombre, satelite.respaldo_de, satelite.orden) == ("HLS:VIIRS", "HLS", 2)
