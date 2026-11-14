"""Sentinel-3 SLSTR LST nocturna como segundo respaldo de heladas (spec 051). Sin internet: Copernicus simulado."""

import io
from datetime import date, datetime
from urllib.parse import unquote

import h5py
import httpx
import numpy as np
import pytest

from rotaterra.fuentes import sentinel3_heladas as s3
from rotaterra.fuentes.registro import Satelite
from rotaterra.geo import poligono_desde_esquinas

# mismo lote de prueba de ~50 ha alrededor de -33,7025; -65,2975
POLIGONO = poligono_desde_esquinas("-33.699, -65.301; -33.699, -65.294; -33.706, -65.294; -33.706, -65.301")
LAT0, LON0 = -33.7025, -65.2975
CONFIANZA_NOMBRES = ("coastline ocean tidal land inland_water unfilled spare spare cosmetic duplicate day twilight "
                     "sun_glint snow summary_cloud summary_pointing")
CONFIANZA_MASCARAS = [1 << i for i in range(16)]
TIERRA, NUBE = 8, 16384

NOCHE_A = "S3A_SL_2_LST____20260922T021617_20260922T021917_20260923T105020_0179_144_131_3420_PS1_O_NT_004.SEN3"
NOCHE_A_NR = "S3A_SL_2_LST____20260922T021617_20260922T021917_20260922T041000_0179_144_131_3420_PS1_O_NR_004.SEN3"
NOCHE_B = "S3B_SL_2_LST____20260922T030500_20260922T030800_20260923T110000_0179_144_131_3420_PS1_O_NT_004.SEN3"
DIA_A = "S3A_SL_2_LST____20260922T133311_20260922T133611_20260923T190000_0179_144_138_3420_PS1_O_NT_004.SEN3"


def netcdf(variables: dict) -> bytes:
    memoria = io.BytesIO()
    with h5py.File(memoria, "w") as archivo:
        for nombre, (datos, atributos) in variables.items():
            conjunto = archivo.create_dataset(nombre, data=datos)
            for clave, valor in atributos.items():
                conjunto.attrs[clave] = valor
    return memoria.getvalue()


def archivos_del_producto(celsius=-3.0, confianza=TIERRA, desplazamiento_lon=0.0, frio_en_un_pixel=None):
    """Grilla de 20 × 20 píxeles de ~1 km centrada en el lote, con LST en kelvin como la guarda la ESA."""
    filas = np.arange(20) - 10
    lat = LAT0 - filas[:, None] * 0.009 + 0 * filas[None, :]
    lon = LON0 + desplazamiento_lon + filas[None, :] * 0.0108 + 0 * filas[:, None]
    # LST como entero con escala y desplazamiento, para probar que se aplican
    kelvin = np.full(lat.shape, celsius + 273.15)
    if frio_en_un_pixel is not None:
        kelvin[10, 10] = frio_en_un_pixel + 273.15
    crudo = np.round((kelvin - 290.0) / 0.002).astype("int16")
    crudo[0, 0] = -32768
    return {
        "LST_in.nc": netcdf({"LST": (crudo, {"scale_factor": np.float32(0.002), "add_offset": np.float32(290.0),
                                             "_FillValue": np.int16(-32768)})}),
        "geodetic_in.nc": netcdf({
            "latitude_in": (np.round(lat * 1e6).astype("int32"), {"scale_factor": 1e-6}),
            "longitude_in": (np.round(lon * 1e6).astype("int32"), {"scale_factor": 1e-6})}),
        "flags_in.nc": netcdf({"confidence_in": (np.full(lat.shape, confianza, dtype="uint16"),
                                                 {"flag_meanings": CONFIANZA_NOMBRES.encode(),
                                                  "flag_masks": np.array(CONFIANZA_MASCARAS, dtype="uint16")})}),
    }


def transporte(productos: dict[str, dict[str, bytes]], pedidos: list | None = None, token_vencido: bool = False):
    estado = {"tokens": 0}

    def responder(pedido: httpx.Request) -> httpx.Response:
        if pedidos is not None:
            pedidos.append(pedido)
        url = unquote(str(pedido.url))
        if url.startswith(s3.URL_TOKEN):
            estado["tokens"] += 1
            return httpx.Response(200, json={"access_token": f"token{estado['tokens']}"})
        if url.startswith(f"{s3.URL_CATALOGO}/Products?"):
            return httpx.Response(200, json={"value": [{"Id": f"id-{i}", "Name": nombre}
                                                       for i, nombre in enumerate(productos)]})
        if url.startswith(s3.URL_DESCARGA):
            # como Copernicus: la descarga redirige a otro servidor y el token tiene que seguir
            return httpx.Response(307, headers={"Location": url.replace("download.", "zipper.")})
        if "zipper.dataspace" in url:
            if token_vencido and pedido.headers["Authorization"] == "Bearer token1":
                return httpx.Response(401)
            if not pedido.headers.get("Authorization", "").startswith("Bearer token"):
                return httpx.Response(401)
            nombre = url.split("/Nodes(")[1].rstrip(")")
            archivo = url.split("/Nodes(")[2].split(")")[0]
            return httpx.Response(200, content=productos[nombre][archivo])
        return httpx.Response(404)
    return httpx.MockTransport(responder)


@pytest.fixture
def credenciales(monkeypatch):
    monkeypatch.setenv("COPERNICUS_USERNAME", "usuario@ejemplo.com")
    monkeypatch.setenv("COPERNICUS_PASSWORD", "clave")


def cliente(productos, pedidos=None, **kw):
    return httpx.Client(transport=transporte(productos, pedidos, **kw))


# ---------- cálculo puro ----------

def test_noche_y_fecha_de_la_madrugada():
    # 02:16 UTC = 21:55 hora solar del 21/9 en San Luis: es de noche y es la noche del 22/9 (como VIIRS y MODIS)
    paso = datetime(2026, 9, 22, 2, 16)
    assert s3.es_de_noche(paso, LON0) and s3.noche_de(paso, LON0) == date(2026, 9, 22)
    assert not s3.es_de_noche(datetime(2026, 9, 22, 13, 33), LON0)  # paso de día, ~09:10 hora solar
    assert s3.noche_de(datetime(2026, 9, 22, 9, 0), LON0) == date(2026, 9, 22)  # 04:40 hora solar


def test_elige_noches_y_prefiere_la_version_definitiva():
    productos = [{"Name": n, "Id": n} for n in (DIA_A, NOCHE_A_NR, NOCHE_B, NOCHE_A)]
    assert [p["Name"] for p in s3.elegir_productos(productos, LON0)] == [NOCHE_A, NOCHE_B]


def test_escalar_aplica_relleno_escala_y_desplazamiento():
    archivo = h5py.File(io.BytesIO(archivos_del_producto(celsius=-3.0)["LST_in.nc"]), "r")
    kelvin = s3.escalar(archivo["LST"])
    assert np.isnan(kelvin[0, 0]) and kelvin[5, 5] == pytest.approx(270.15, abs=0.002)


def test_limpios_pide_tierra_y_sin_nube():
    bits = s3.bits_de({"flag_meanings": CONFIANZA_NOMBRES.encode(), "flag_masks": np.array(CONFIANZA_MASCARAS)})
    confianza = np.array([TIERRA, TIERRA | NUBE, 2, TIERRA | 1024])  # 1024 = "day", no descarta
    assert s3.limpios(confianza, bits).tolist() == [True, False, False, True]


def test_rango_largo_rechazado():
    with pytest.raises(ValueError, match="366"):
        s3.validar_pedido(POLIGONO, date(2025, 1, 1), date(2026, 6, 1))


# ---------- de punta a punta con Copernicus simulado ----------

def test_noche_fria_da_celsius_y_riesgo_de_helada(credenciales):
    pedidos = []
    obs = s3.obtener_heladas("lote-7", POLIGONO, date(2026, 9, 15), date(2026, 9, 30),
                             cliente=cliente({NOCHE_A: archivos_del_producto()}, pedidos))
    assert len(obs) == 1
    o = obs[0]
    assert (o.fecha, o.valor, o.calidad, o.variable, o.fuente, o.resolucion_m) == \
        (date(2026, 9, 22), -3.0, "buena", "temp_sup_min_c", "SENTINEL3", 1000)
    assert "riesgo de helada" in o.nota and "no del aire" in o.nota and "Sentinel-3A" in o.nota
    assert "madrugada suele ser más fría" in o.nota
    # el token sigue al servidor de descarga y solo se bajan los 3 NetCDF, no el producto entero
    descargas = [p for p in pedidos if "zipper.dataspace" in str(p.url)]
    assert len(descargas) == 3 and all(p.headers["Authorization"] == "Bearer token1" for p in descargas)


def test_toma_el_pixel_mas_frio_del_lote(credenciales):
    obs = s3.obtener_heladas("lote-7", POLIGONO, date(2026, 9, 15), date(2026, 9, 30),
                             cliente=cliente({NOCHE_A: archivos_del_producto(celsius=4.0, frio_en_un_pixel=-1.5)}))
    assert obs[0].valor == -1.5


def test_nubes_descartan_sin_inventar(credenciales):
    obs = s3.obtener_heladas("lote-7", POLIGONO, date(2026, 9, 15), date(2026, 9, 30),
                             cliente=cliente({NOCHE_A: archivos_del_producto(confianza=TIERRA | NUBE)}))
    assert [(o.valor, o.calidad) for o in obs] == [(None, "descartada")]


def test_misma_noche_gana_la_mas_limpia(credenciales):
    productos = {NOCHE_A: archivos_del_producto(confianza=TIERRA | NUBE), NOCHE_B: archivos_del_producto(celsius=1.0)}
    obs = s3.obtener_heladas("lote-7", POLIGONO, date(2026, 9, 15), date(2026, 9, 30), cliente=cliente(productos))
    assert len(obs) == 1 and obs[0].valor == 1.0 and "Sentinel-3B" in obs[0].nota and "riesgo" not in obs[0].nota


def test_paso_que_no_cubre_el_lote_se_saltea(credenciales):
    obs = s3.obtener_heladas("lote-7", POLIGONO, date(2026, 9, 15), date(2026, 9, 30),
                             cliente=cliente({NOCHE_A: archivos_del_producto(desplazamiento_lon=3.0)}))
    assert obs == []


def test_paso_de_dia_no_se_baja(credenciales):
    pedidos = []
    obs = s3.obtener_heladas("lote-7", POLIGONO, date(2026, 9, 15), date(2026, 9, 30),
                             cliente=cliente({DIA_A: archivos_del_producto()}, pedidos))
    assert obs == [] and not [p for p in pedidos if "dataspace" in str(p.url) and "Nodes" in str(p.url)]


def test_token_vencido_se_renueva(credenciales):
    obs = s3.obtener_heladas("lote-7", POLIGONO, date(2026, 9, 15), date(2026, 9, 30),
                             cliente=cliente({NOCHE_A: archivos_del_producto()}, token_vencido=True))
    assert obs[0].valor == -3.0


def test_sin_credenciales(monkeypatch):
    monkeypatch.delenv("COPERNICUS_USERNAME", raising=False)
    monkeypatch.delenv("COPERNICUS_PASSWORD", raising=False)
    with pytest.raises(s3.FaltanCredencialesCopernicus):
        s3.obtener_heladas("lote-7", POLIGONO, date(2026, 9, 15), date(2026, 9, 30))


def test_filtro_del_catalogo_pide_sl_2_lst_sobre_el_lote():
    filtro = s3.filtro_odata(POLIGONO, date(2026, 9, 15), date(2026, 9, 30))
    assert "SENTINEL-3" in filtro and "SL_2_LST" in filtro and "-65.301 -33.706" in filtro
    assert "2026-09-14T12:00:00.000Z" in filtro  # la noche del 15 arranca la tarde del 14


# ---------- lugar en la cadena de respaldos ----------

def test_entra_despues_de_modis():
    def nada(lote, desde, hasta):
        return []
    satelites = [Satelite("VIIRS_LST", nada), Satelite("VIIRS_LST:MODIS", nada, respaldo_de="VIIRS_LST", orden=1)]
    satelites += s3.SATELITES
    en_orden = sorted((s for s in satelites if s.respaldo_de), key=lambda s: (s.orden, s.nombre))
    assert [s.nombre for s in en_orden] == ["VIIRS_LST:MODIS", "VIIRS_LST:SENTINEL3"]
