"""Sentinel-3 SYN como respaldo del NDVI (spec 050). Sin internet: CMR y LAADS simulados con un .zip armado acá."""

import io
import zipfile
from datetime import date

import h5py
import httpx
import numpy as np
import pytest

from rotaterra.fuentes import earthdata, sentinel3
from rotaterra.fuentes.registro import Satelite
from rotaterra.geo import poligono_desde_esquinas

# mismo lote de prueba de ~50 ha alrededor de -33,7025; -65,2975
POLIGONO = poligono_desde_esquinas("-33.699, -65.301; -33.699, -65.294; -33.706, -65.294; -33.706, -65.301")
LAT0, LON0 = -33.7025, -65.2975
FILAS, COLUMNAS = 40, 129  # 3 columnas de puntos de enlace (0, 64 y 128), como en la pasada real cada 64
PASO_LAT, PASO_LON = 0.0027, 0.0032  # ~300 m

SYN_NOMBRES = ("SYN_high_error SYN_too_low SYN_negative_curvature SYN_success SYN_aerosol_filled SYN_border "
               "SYN_partly_water SYN_partly_cloudy SYN_no_slo SYN_no_sln SYN_no_olc SYN_land SYN_AOT_climato "
               "SYN_SDR_OOR SYN_snow_risk SYN_cloud")
SYN_MASCARAS = [32768, 16384, 8192, 4096, 2048, 1024, 512, 256, 128, 64, 32, 16, 8, 4, 2, 1]
SYN_TIERRA_DESPEJADA = 4096 + 256 + 128 + 16  # como el 20/9/2026 real: success, partly_cloudy, no_slo, land
SYN_NUBE = 128 + 16 + 1                       # como el 24/9/2026 real: no_slo, land, cloud


def grilla(desplazamiento_lon: float = 0.0):
    filas = np.arange(FILAS) - FILAS // 2
    columnas = np.arange(COLUMNAS) - 70
    lat = LAT0 - filas[:, None] * PASO_LAT + 0 * columnas[None, :]
    lon = LON0 + desplazamiento_lon + columnas[None, :] * PASO_LON + 0 * filas[:, None]
    return lat, lon


def netcdf(variables: dict) -> bytes:
    """HDF5 (como los NetCDF-4 de la ESA) con variables -> (datos, atributos)."""
    memoria = io.BytesIO()
    with h5py.File(memoria, "w") as archivo:
        for nombre, (datos, atributos) in variables.items():
            conjunto = archivo.create_dataset(nombre, data=datos, chunks=True, compression="gzip")
            for clave, valor in atributos.items():
                conjunto.attrs[clave] = valor
    return memoria.getvalue()


def pasada_zip(rojo=500, nir=2500, syn=SYN_TIERRA_DESPEJADA, nubes=0, desplazamiento_lon=0.0) -> bytes:
    lat, lon = grilla(desplazamiento_lon)
    enlace = [0, 64, 128]
    forma = (FILAS, COLUMNAS)
    archivos = {
        "geolocation.nc": {"lat": (np.round(lat * 1e6).astype("int32"), {}),
                           "lon": (np.round(lon * 1e6).astype("int32"), {})},
        # en la tira, primero todas las filas de la primera columna de enlace (como en la pasada real)
        "tiepoints_olci.nc": {"OLC_TP_lat": (np.round(lat[:, enlace].T.ravel() * 1e6).astype("int32"), {}),
                              "OLC_TP_lon": (np.round(lon[:, enlace].T.ravel() * 1e6).astype("int32"), {})},
        "flags.nc": {"SYN_flags": (np.full(forma, syn, dtype="uint16"),
                                   {"flag_meanings": SYN_NOMBRES.encode(),
                                    "flag_masks": np.array(SYN_MASCARAS, dtype="uint16")}),
                     "CLOUD_flags": (np.full(forma, nubes, dtype="uint8"), {})},
        "Syn_Oa08_reflectance.nc": {"SDR_Oa08": (np.full(forma, rojo, dtype="int16"), {})},
        "Syn_Oa17_reflectance.nc": {"SDR_Oa17": (np.full(forma, nir, dtype="int16"), {})},
    }
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w", compression=zipfile.ZIP_STORED) as z:
        for nombre, variables in archivos.items():
            z.writestr(f"S3A_SY_2_SYN____20260920.SEN3/{nombre}", netcdf(variables))
    return memoria.getvalue()


NOMBRE_A = "S3A_SY_2_SYN____20260920T133311_20260920T133611_20260922T103817_0179_144_138_3600_PS1_O_NT_003.zip"
NOMBRE_B = "S3B_SY_2_SYN____20260920T141000_20260920T141300_20260922T110000_0179_144_138_3600_PS1_O_NT_003.zip"
URL_A = f"https://data.laadsdaac.earthdatacloud.nasa.gov/prod-lads/S3A_SY_2_SYN/{NOMBRE_A}"
URL_B = f"https://data.laadsdaac.earthdatacloud.nasa.gov/prod-lads/S3B_SY_2_SYN/{NOMBRE_B}"


def transporte(zips: dict[str, bytes], pedidos: list | None = None):
    def responder(pedido: httpx.Request) -> httpx.Response:
        if pedidos is not None:
            pedidos.append(pedido)
        url = str(pedido.url)
        if "find_or_create_token" in url:
            return httpx.Response(200, json={"access_token": "token"})
        if "collections.umm_json" in url:
            nombre = pedido.url.params["short_name"]
            return httpx.Response(200, json={"items": [
                {"meta": {"concept-id": f"C-{nombre}"}, "umm": {"Version": "1"}}]})
        if "granules.umm_json" in url:
            coleccion = pedido.url.params["collection_concept_id"]
            nombre, enlace = (NOMBRE_A, URL_A) if "S3A" in coleccion else (NOMBRE_B, URL_B)
            if enlace not in zips:
                return httpx.Response(200, json={"items": []})
            return httpx.Response(200, json={"items": [{"umm": {"GranuleUR": f"LAADS:{nombre}", "RelatedUrls": [
                {"URL": enlace, "Type": "GET DATA"}, {"URL": f"s3://prod-lads/{nombre}", "Type": "GET DATA VIA DIRECT ACCESS"}]}}]})
        contenido = zips[url.split("?")[0]]
        inicio, fin = pedido.headers["Range"].removeprefix("bytes=").split("-")
        inicio, fin = int(inicio), min(int(fin), len(contenido) - 1)
        return httpx.Response(206, content=contenido[inicio:fin + 1],
                              headers={"content-range": f"bytes {inicio}-{fin}/{len(contenido)}"})
    return httpx.MockTransport(responder)


@pytest.fixture
def credenciales(monkeypatch):
    monkeypatch.setenv("EARTHDATA_USERNAME", "usuario")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "clave")


def cliente(zips, pedidos=None):
    return httpx.Client(transport=transporte(zips, pedidos))


# ---------- cálculo puro ----------

def test_puntos_de_enlace_se_ordenan_por_columna():
    lat, _ = grilla()
    tira = lat[:, [0, 64, 128]].T.ravel()
    assert np.array_equal(sentinel3.grilla_de_enlace(tira, FILAS), lat[:, [0, 64, 128]])


def test_ubicar_encuentra_la_columna_del_lote():
    lat, lon = grilla()
    fila, columna = sentinel3.ubicar(lat[:, [0, 64, 128]], lon[:, [0, 64, 128]], COLUMNAS, LAT0, LON0)
    assert fila == FILAS // 2 and columna == 64  # el lote está en la columna 70: el enlace más cercano es 64


def test_ubicar_lote_fuera_de_la_franja():
    lat, lon = grilla(desplazamiento_lon=2.0)  # franja 180 km al este
    assert sentinel3.ubicar(lat[:, [0, 64, 128]], lon[:, [0, 64, 128]], COLUMNAS, LAT0, LON0) is None


def test_bits_salen_de_los_atributos():
    bits = sentinel3.bits_de({"flag_meanings": SYN_NOMBRES.encode(), "flag_masks": np.array(SYN_MASCARAS)})
    assert bits["SYN_cloud"] == 1 and bits["SYN_land"] == 16 and bits["SYN_high_error"] == 32768


def test_ndvi_con_relleno_queda_vacio():
    resultado = sentinel3.ndvi(np.array([500, -10000]), np.array([2500, 2500]))
    assert resultado[0] == pytest.approx(2000 / 3000) and np.isnan(resultado[1])


def test_limpios_respeta_nubes_de_olci_y_de_synergy():
    bits = sentinel3.bits_de({"flag_meanings": SYN_NOMBRES.encode(), "flag_masks": np.array(SYN_MASCARAS)})
    syn = np.array([SYN_TIERRA_DESPEJADA, SYN_NUBE, SYN_TIERRA_DESPEJADA, 4096, SYN_TIERRA_DESPEJADA | 2])
    nubes = np.array([0, 0, 1, 0, 0])
    assert sentinel3.limpios(syn, bits, nubes).tolist() == [True, False, False, False, False]


def test_fecha_sale_del_nombre():
    assert sentinel3.fecha_de(NOMBRE_A) == date(2026, 9, 20)


def test_resumen_limpio_es_bueno():
    datos = {"ndvi": np.full((3, 3), 0.4), "validos": np.ones((3, 3), bool), "dentro": np.ones((3, 3), bool)}
    o, pct = sentinel3.resumir("lote-7", date(2026, 9, 20), datos, "Sentinel-3A")
    assert (o.valor, o.calidad, o.fuente, o.resolucion_m, pct) == (0.4, "buena", "SENTINEL3", 300, 100)
    assert "Respaldo de HLS" in o.nota and "Sentinel-3A" in o.nota and "LAADS" in o.nota


def test_resumen_nublado_se_descarta_sin_inventar():
    datos = {"ndvi": np.full((3, 3), 0.4), "validos": np.zeros((3, 3), bool), "dentro": np.ones((3, 3), bool)}
    o, pct = sentinel3.resumir("lote-7", date(2026, 9, 20), datos, "Sentinel-3A")
    assert (o.valor, o.calidad, pct) == (None, "descartada", 0)


def test_resumen_parcial_es_dudoso():
    validos = np.zeros((3, 3), bool)
    validos[0, :] = True
    datos = {"ndvi": np.full((3, 3), 0.4), "validos": validos, "dentro": np.ones((3, 3), bool)}
    o, _ = sentinel3.resumir("lote-7", date(2026, 9, 20), datos, "Sentinel-3A")
    assert o.calidad == "dudosa" and "parcialmente" in o.nota


def test_rango_largo_rechazado():
    with pytest.raises(ValueError, match="366"):
        sentinel3.validar_pedido(POLIGONO, date(2025, 1, 1), date(2026, 6, 1))


# ---------- de punta a punta con LAADS simulado ----------

def test_pasada_despejada_da_ndvi_del_lote(credenciales):
    pedidos = []
    obs = sentinel3.obtener_ndvi("lote-7", POLIGONO, date(2026, 9, 15), date(2026, 9, 30),
                                 cliente=cliente({URL_A: pasada_zip()}, pedidos))
    assert len(obs) == 1
    o = obs[0]
    assert (o.fecha, o.valor, o.calidad, o.variable, o.fuente) == (date(2026, 9, 20), 0.667, "buena", "ndvi", "SENTINEL3")
    # se lee por pedazos con el token de Earthdata, nunca el .zip entero
    lecturas = [p for p in pedidos if "Range" in p.headers]
    assert lecturas and all(p.headers["Authorization"] == "Bearer token" for p in lecturas)


def test_pasada_nublada_queda_descartada(credenciales):
    obs = sentinel3.obtener_ndvi("lote-7", POLIGONO, date(2026, 9, 15), date(2026, 9, 30),
                                 cliente=cliente({URL_A: pasada_zip(syn=SYN_NUBE)}))
    assert [(o.valor, o.calidad) for o in obs] == [(None, "descartada")]


def test_mismo_dia_gana_la_pasada_mas_limpia(credenciales):
    zips = {URL_A: pasada_zip(nubes=1), URL_B: pasada_zip(rojo=1000, nir=2000)}
    obs = sentinel3.obtener_ndvi("lote-7", POLIGONO, date(2026, 9, 15), date(2026, 9, 30), cliente=cliente(zips))
    assert len(obs) == 1 and obs[0].valor == pytest.approx(0.333, abs=1e-3) and "Sentinel-3B" in obs[0].nota


def test_pasada_que_no_cubre_el_lote_se_saltea(credenciales):
    obs = sentinel3.obtener_ndvi("lote-7", POLIGONO, date(2026, 9, 15), date(2026, 9, 30),
                                 cliente=cliente({URL_A: pasada_zip(desplazamiento_lon=2.0)}))
    assert obs == []


def test_sin_pasadas_avisa(credenciales):
    with pytest.raises(sentinel3.ErrorSentinel3, match="CMR no tiene"):
        sentinel3.obtener_ndvi("lote-7", POLIGONO, date(2026, 9, 15), date(2026, 9, 30), cliente=cliente({}))


def test_sin_credenciales(monkeypatch):
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)
    with pytest.raises(earthdata.FaltanCredenciales):
        sentinel3.obtener_ndvi("lote-7", POLIGONO, date(2026, 9, 15), date(2026, 9, 30))


# ---------- lugar en la cadena de respaldos ----------

def test_entra_entre_sentinel2_y_viirs():
    def nada(lote, desde, hasta):
        return []
    satelites = [Satelite("HLS", nada), Satelite("HLS:MODIS", nada, respaldo_de="HLS", orden=3),
                 Satelite("HLS:VIIRS", nada, respaldo_de="HLS", orden=2),
                 Satelite("HLS:SENTINEL2", nada, respaldo_de="HLS", orden=1)] + sentinel3.SATELITES
    en_orden = sorted((s for s in satelites if s.respaldo_de), key=lambda s: (s.orden, s.nombre))
    assert [s.nombre for s in en_orden] == ["HLS:SENTINEL2", "HLS:SENTINEL3", "HLS:VIIRS", "HLS:MODIS"]

