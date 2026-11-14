"""Copernicus DEM sin internet: XML de la ESA simulado con httpx.MockTransport y mosaicos sintéticos en disco."""

import math
from datetime import date

import httpx
import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine

from rotaterra.fuentes import copdem
from rotaterra.geo import poligono_desde_esquinas

SEG = 1 / 3600
# el lote de prueba de NASADEM: 25,7 ha en -33,70; -65,30
LOTE = poligono_desde_esquinas("-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300")
# un lote que cruza el meridiano -65: mitad en el mosaico W066 y mitad en el W065
LOTE_CRUZA = poligono_desde_esquinas("-33.700, -65.003; -33.700, -64.997; -33.705, -64.997; -33.705, -65.003")


def xml(inicio="2011-01-17T09:40:48.507953Z", fin="2013-10-30T22:58:28.865215Z") -> str:
    return (f"<gmd:MD_Metadata><tsxx:temporalCoverage><tsxx:tsxx_startTime>{inicio}</tsxx:tsxx_startTime>"
            f"<tsxx:tsxx_stopTime>{fin}</tsxx:tsxx_stopTime></tsxx:temporalCoverage></gmd:MD_Metadata>")


def mosaico_sintetico(ruta, oeste, norte, filas, columnas, altura):
    """GeoTIFF con la grilla del producto: centros de píxel en múltiplos de 1".

    `oeste` y `norte` son el centro del píxel de arriba a la izquierda; `altura(lat, lon)` da cada valor.
    """
    lats = norte - np.arange(filas) * SEG
    lons = oeste + np.arange(columnas) * SEG
    lon_m, lat_m = np.meshgrid(lons, lats)
    datos = altura(lat_m, lon_m).astype("float32")
    transformada = Affine(SEG, 0, oeste - SEG / 2, 0, -SEG, norte + SEG / 2)
    with rasterio.open(ruta, "w", driver="GTiff", width=columnas, height=filas, count=1, dtype="float32",
                       crs="EPSG:4326", transform=transformada) as destino:
        destino.write(datos, 1)


@pytest.fixture
def bucket(tmp_path, monkeypatch):
    """Bucket simulado: XML por httpx y COG en disco. Devuelve (cliente, dict de XML por mosaico, carpeta)."""
    xmls: dict[str, str] = {}
    pedidos: list[str] = []

    def responder(pedido: httpx.Request) -> httpx.Response:
        nombre = pedido.url.path.rsplit("/", 1)[-1].removesuffix(".xml")
        pedidos.append(nombre)
        if nombre not in xmls:
            return httpx.Response(404, text="<Error><Code>NoSuchKey</Code></Error>")
        return httpx.Response(200, text=xmls[nombre])

    monkeypatch.setattr(copdem, "url_xml", lambda n: f"https://copernicus-dem-30m.prueba/{n}.xml")
    monkeypatch.setattr(copdem, "url_tif", lambda n: str(tmp_path / f"{n}.tif"))
    cliente = httpx.Client(transport=httpx.MockTransport(responder))
    return cliente, xmls, tmp_path, pedidos


PASO = 0.2  # m por píxel


def plano(lat, lon):
    """Relieve que sube 0,2 m por píxel hacia el este (pendiente conocida) sobre 480 m."""
    return 480 + PASO * np.round((lon + 66) * 3600)


# ---------- nombres y fechas ----------

def test_nombre_del_mosaico_por_su_esquina_suroeste():
    assert copdem.nombre_mosaico(-33.7, -65.3) == "S34_00_W066_00"
    assert copdem.nombre_mosaico(0.5, 10.2) == "N00_00_E010_00"
    assert copdem.carpeta("S34_00_W066_00") == "Copernicus_DSM_COG_10_S34_00_W066_00_DEM"


def test_url_real_del_bucket():
    assert copdem.url_tif("S34_00_W066_00") == (
        "https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_S34_00_W066_00_DEM/"
        "Copernicus_DSM_COG_10_S34_00_W066_00_DEM.tif")
    assert copdem.url_xml("S34_00_W066_00") == (
        "https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_S34_00_W066_00_DEM/"
        "Copernicus_DSM_10_S34_00_W066_00.xml")


def test_mosaicos_que_toca_la_caja():
    assert copdem.mosaicos_de_la_caja((-65.3, -33.705, -65.295, -33.7)) == ["S34_00_W066_00"]
    assert sorted(copdem.mosaicos_de_la_caja((-65.003, -33.705, -64.997, -33.7))) == ["S34_00_W065_00",
                                                                                     "S34_00_W066_00"]
    assert len(copdem.mosaicos_de_la_caja((-65.003, -34.001, -64.997, -33.999))) == 4


def test_periodo_de_toma_sale_del_xml_de_la_esa():
    assert copdem.periodo_de_toma(xml()) == (date(2011, 1, 17), date(2013, 10, 30))


def test_sin_fecha_en_el_xml_no_se_inventa():
    with pytest.raises(copdem.ErrorCOPDEM, match="no se inventa"):
        copdem.periodo_de_toma("<gmd:MD_Metadata/>")


# ---------- cálculo ----------

def test_lote_de_prueba_da_las_7_variables(bucket):
    cliente, xmls, carpeta, _ = bucket
    xmls["S34_00_W066_00"] = xml()
    mosaico_sintetico(carpeta / "S34_00_W066_00.tif", -65.31, -33.69, 80, 80, plano)

    obs = copdem.obtener_altimetria("lote-7", LOTE, cliente)
    valores = {o.variable: o.valor for o in obs}
    assert [o.variable for o in obs] == [v for v, _ in copdem.VARIABLES]
    assert {o.fuente for o in obs} == {"COPDEM"}
    assert {o.fecha for o in obs} == {date(2013, 10, 30)}  # último día de toma del mosaico
    assert {o.resolucion_m for o in obs} == {30}
    assert {o.calidad for o in obs} == {"buena"}
    # 17 columnas de 0,2 m: de 480 + 0,2 × columna del borde oeste al este
    oeste = round((-65.3 + 66) * 3600)
    assert valores["altura_min_m"] == round(480 + PASO * (oeste + 1), 1)
    assert valores["altura_max_m"] == round(480 + PASO * (oeste + 17), 1)
    # pendiente del plano: 0,2 m por píxel este-oeste de ~25,7 m a esta latitud
    lado_x = copdem._R * math.radians(SEG) * math.cos(math.radians(-33.7025))
    assert valores["pendiente_media_pct"] == pytest.approx(100 * PASO / lado_x, abs=0.02)
    ha = copdem.superficie_ha(LOTE)
    assert ha == pytest.approx(25.7, abs=0.1)
    suma = valores["superficie_bajo_ha"] + valores["superficie_media_loma_ha"] + valores["superficie_loma_ha"]
    assert suma == pytest.approx(ha, abs=0.02)
    assert valores["superficie_bajo_ha"] > 0 and valores["superficie_loma_ha"] > 0
    assert "289 de 289 píxeles" in obs[0].nota
    assert "modelo de superficie" in obs[0].nota and "17/01/2011 al 30/10/2013" in obs[0].nota
    assert "umbral supuesto" in obs[4].nota


def test_lote_que_cruza_mosaicos_se_une_en_una_grilla(bucket):
    cliente, xmls, carpeta, pedidos = bucket
    xmls["S34_00_W066_00"] = xml(fin="2013-10-30T00:00:00Z")
    xmls["S34_00_W065_00"] = xml(fin="2014-02-17T00:00:00Z")
    # cada mosaico tiene su parte del plano: W066 hasta -65,00028 y W065 desde -65,0
    mosaico_sintetico(carpeta / "S34_00_W066_00.tif", -65 - 30 * SEG, -33.69, 60, 30, plano)
    mosaico_sintetico(carpeta / "S34_00_W065_00.tif", -65.0, -33.69, 60, 30, plano)

    obs = copdem.obtener_altimetria("lote-cruza", LOTE_CRUZA, cliente)
    valores = {o.variable: o.valor for o in obs}
    assert set(pedidos) == {"S34_00_W066_00", "S34_00_W065_00"}
    assert {o.fecha for o in obs} == {date(2014, 2, 17)}  # la toma más reciente de los dos
    lado_x = copdem._R * math.radians(SEG) * math.cos(math.radians(-33.7025))
    # sin saltos en la unión: la pendiente es la del plano
    assert valores["pendiente_media_pct"] == pytest.approx(100 * PASO / lado_x, abs=0.02)
    # hay píxeles de los dos lados del meridiano -65
    assert valores["altura_min_m"] < 480 + PASO * 3600 < valores["altura_max_m"]
    assert "con dato" in obs[0].nota and {o.calidad for o in obs} == {"buena"}


def test_pixeles_invalidos_no_cuentan(bucket):
    cliente, xmls, carpeta, _ = bucket
    xmls["S34_00_W066_00"] = xml()

    def con_huecos(lat, lon):
        h = plano(lat, lon)
        h[40:45, 40:45] = copdem.INVALIDO  # un hueco de 5 × 5 píxeles dentro del lote
        return h

    mosaico_sintetico(carpeta / "S34_00_W066_00.tif", -65.31, -33.69, 80, 80, con_huecos)
    obs = copdem.obtener_altimetria("lote-7", LOTE, cliente)
    assert all(o.valor is not None for o in obs)
    assert "264 de 289 píxeles" in obs[0].nota


def test_sin_pixeles_validos_todo_descartado(bucket):
    cliente, xmls, carpeta, _ = bucket
    xmls["S34_00_W066_00"] = xml()
    mosaico_sintetico(carpeta / "S34_00_W066_00.tif", -65.31, -33.69, 80, 80,
                      lambda lat, lon: np.full(lat.shape, copdem.INVALIDO))
    obs = copdem.obtener_altimetria("lote-7", LOTE, cliente)
    assert len(obs) == 7
    assert all(o.valor is None and o.calidad == "descartada" for o in obs)
    assert "Sin píxeles con dato" in obs[0].nota


def test_lote_chico_es_dudoso(bucket):
    cliente, xmls, carpeta, _ = bucket
    xmls["S34_00_W066_00"] = xml()
    mosaico_sintetico(carpeta / "S34_00_W066_00.tif", -65.31, -33.69, 80, 80, plano)
    chico = poligono_desde_esquinas("-33.7000, -65.3000; -33.7000, -65.2995; -33.7005, -65.2995; -33.7005, -65.3000")
    obs = copdem.obtener_altimetria("lote-chico", chico, cliente)
    assert {o.calidad for o in obs if o.valor is not None} == {"dudosa"}
    assert "menos de 10 píxeles" in obs[0].nota


def test_lote_en_el_mar_falla_con_mensaje_claro(bucket):
    cliente, _, _, _ = bucket
    with pytest.raises(copdem.ErrorCOPDEM, match="en el mar"):
        copdem.obtener_altimetria("lote-mar", LOTE, cliente)


def test_bucket_caido_es_error_del_respaldo(monkeypatch):
    cliente = httpx.Client(transport=httpx.MockTransport(lambda pedido: httpx.Response(503)))
    with pytest.raises(copdem.ErrorCOPDEM, match="No se pudo obtener"):
        copdem.obtener_altimetria("lote-7", LOTE, cliente)


def test_poligono_invalido():
    with pytest.raises(ValueError):
        copdem.obtener_altimetria("lote-7", {"type": "Point", "coordinates": [0, 0]})


# ---------- registro (spec 009) ----------

def test_se_anuncia_como_respaldo_estatico_de_nasadem():
    [satelite] = copdem.SATELITES
    assert satelite.nombre == "NASADEM:COPDEM"
    assert satelite.respaldo_de == "NASADEM"
    assert satelite.estatico is True


def test_pedir_usa_id_y_poligono_del_lote(monkeypatch):
    llamados = []
    monkeypatch.setattr(copdem, "obtener_altimetria", lambda lote_id, poligono: llamados.append((lote_id, poligono)))
    copdem.SATELITES[0].pedir({"id": "lote-7", "poligono": LOTE}, date(2026, 1, 1), date(2026, 1, 31))
    assert llamados == [("lote-7", LOTE)]
