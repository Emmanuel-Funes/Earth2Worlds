from datetime import date

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rotaterra.fuentes import smap_l3

AM, PM = "Soil_Moisture_Retrieval_Data_AM", "Soil_Moisture_Retrieval_Data_PM"
RUTAS = {
    "AM": {"humedad": f"/{AM}/soil_moisture", "bandera": f"/{AM}/retrieval_qual_flag",
           "lat": f"/{AM}/latitude", "lon": f"/{AM}/longitude"},
    "PM": {"humedad": f"/{PM}/soil_moisture_pm", "bandera": f"/{PM}/retrieval_qual_flag_pm",
           "lat": f"/{PM}/latitude_pm", "lon": f"/{PM}/longitude_pm"},
}
DMR = f"""<?xml version="1.0" encoding="ISO-8859-1"?>
<Dataset xmlns="http://xml.opendap.org/ns/DAP/4.0#" name="SMAP_L3_SM_P_E_20260101_R19240_001.h5">
  <Group name="Metadata"><Group name="DatasetIdentification"/></Group>
  <Group name="{AM}">
    <Float32 name="soil_moisture"/><Float32 name="soil_moisture_dca"/><UInt16 name="retrieval_qual_flag"/>
    <Float32 name="latitude"/><Float32 name="longitude"/><Float32 name="latitude_centroid"/>
  </Group>
  <Group name="{PM}">
    <Float32 name="soil_moisture_pm"/><UInt16 name="retrieval_qual_flag_pm"/>
    <Float32 name="latitude_pm"/><Float32 name="longitude_pm"/>
  </Group>
  <Group name="Soil_Moisture_Retrieval_Data_Polar_AM">
    <Float32 name="soil_moisture"/><UInt16 name="retrieval_qual_flag"/>
    <Float32 name="latitude"/><Float32 name="longitude"/>
  </Group>
</Dataset>"""

LAT, LON = -33.70, -65.30
CENTRO = (-33.67, -65.31)  # centro de la celda 1262, 1228 (spec 005)


@pytest.fixture(autouse=True)
def sin_rutas_guardadas():
    smap_l3._RUTAS.clear()


@pytest.fixture
def credenciales(monkeypatch):
    monkeypatch.setenv("EARTHDATA_USERNAME", "usuario")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "clave")


def pasada(humedad=None, bandera=None, lat=CENTRO[0], lon=CENTRO[1]):
    return {"humedad": humedad, "bandera": bandera, "lat": lat, "lon": lon}


# ---------- grilla ----------

def test_celda_del_lote_de_prueba_es_la_del_l4():
    assert smap_l3.celda_ease2(LAT, LON) == (1262, 1228)


def test_celda_en_los_bordes_deja_lugar_para_dos_columnas():
    fila, columna = smap_l3.celda_ease2(-89.9, 179.999)
    assert fila == smap_l3.FILAS - 1 and columna == smap_l3.COLUMNAS - 2


def test_distancia_km():
    assert smap_l3.distancia_km(LAT, LON, *CENTRO) == pytest.approx(3.4, abs=0.3)


# ---------- metadatos ----------

def test_rutas_de_capas_salen_de_los_metadatos_sin_los_grupos_polares():
    assert smap_l3.rutas_de_capas(DMR) == RUTAS


def test_metadatos_sin_pasada_pm_avisan():
    sin_pm = DMR.replace('name="soil_moisture_pm"', 'name="otra_cosa"')
    with pytest.raises(smap_l3.ErrorSMAPL3, match="PM"):
        smap_l3.rutas_de_capas(sin_pm)


# ---------- calidad ----------

def test_dos_pasadas_recomendadas_se_promedian():
    o = smap_l3.a_observacion("lote-7", date(2026, 1, 9), {"AM": pasada(0.11, 0), "PM": pasada(0.13, 0)})
    assert (o.valor, o.calidad, o.variable, o.unidad, o.fuente, o.resolucion_m) == \
        (0.12, "buena", "humedad_superficial", "m³/m³", "SMAP", 9000)
    assert "Promedio de AM y PM" in o.nota and "L3" in o.nota and "zona de raíces" in o.nota


def test_una_pasada_alcanza_y_la_otra_figura_sin_pasada():
    o = smap_l3.a_observacion("lote-7", date(2026, 1, 9), {"AM": pasada(0.118, 8), "PM": pasada()})
    assert (o.valor, o.calidad) == (0.118, "buena")  # bit 3 prendido no afecta: manda el bit 0
    assert "AM 0.118 (recomendada)" in o.nota and "PM sin pasada" in o.nota


def test_pasada_no_recomendada_no_se_mezcla_con_una_recomendada():
    o = smap_l3.a_observacion("lote-7", date(2026, 1, 9), {"AM": pasada(0.10, 0), "PM": pasada(0.30, 1)})
    assert (o.valor, o.calidad) == (0.10, "buena") and "no recomendada" in o.nota


def test_solo_pasadas_no_recomendadas_son_dudosas():
    o = smap_l3.a_observacion("lote-7", date(2026, 1, 9), {"AM": pasada(0.10, 1), "PM": pasada(0.14, None)})
    assert (o.valor, o.calidad) == (0.12, "dudosa") and "retrieval_qual_flag" in o.nota


def test_fuera_del_rango_fisico_es_dudoso():
    o = smap_l3.a_observacion("lote-7", date(2026, 1, 9), {"AM": pasada(0.7, 0), "PM": pasada()})
    assert o.calidad == "dudosa" and "rango físico" in o.nota


def test_dia_sin_pasada_se_descarta_y_no_inventa():
    o = smap_l3.a_observacion("lote-7", date(2026, 1, 9), {"AM": pasada(), "PM": pasada()})
    assert o.valor is None and o.calidad == "descartada" and "no pasó" in o.nota


def test_dia_sin_archivo_se_descarta_con_el_motivo():
    o = smap_l3.a_observacion("lote-7", date(2026, 1, 9), None)
    assert o.valor is None and o.calidad == "descartada" and "no publicó" in o.nota


# ---------- NASA simulada ----------

class NASAFalsa:
    """CMR y OPeNDAP simulados. 'dias' = fecha -> {pasada: (humedad, bandera)} con -9999 como relleno."""

    def __init__(self, dias, colecciones_cloud=True):
        self.dias = dias
        self.colecciones_cloud = colecciones_cloud
        self.pedidos = []

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        url = str(pedido.url)
        self.pedidos.append(pedido)
        if "find_or_create_token" in url:
            return httpx.Response(200, json={"access_token": "tk"})
        if "/collections.umm_json" in url:
            if pedido.url.params.get("provider") == "NSIDC_CPRD" and not self.colecciones_cloud:
                return httpx.Response(200, json={"items": []})
            return httpx.Response(200, json={"items": [
                {"meta": {"concept-id": "C-viejo"}, "umm": {"Version": "005"}},
                {"meta": {"concept-id": "C-L3"}, "umm": {"Version": "006"}}]})
        if "/granules.umm_json" in url:
            assert pedido.url.params["collection_concept_id"] == "C-L3"
            items = []
            for dia in self.dias:
                for version in ("001", "002") if dia.day == 5 else ("001",):  # el 5/1 se reprocesó
                    nombre = f"SMAP_L3_SM_P_E_{dia:%Y%m%d}_R19240_{version}.h5"
                    items.append({"umm": {"GranuleUR": nombre, "RelatedUrls": [
                        {"URL": f"https://data.nsidc.earthdatacloud.nasa.gov/{nombre}"},
                        {"URL": f"https://opendap.earthdata.nasa.gov/collections/C-L3/granules/{nombre}"}]}})
            return httpx.Response(200, json={"items": items})
        if url.endswith(".dmr"):
            return httpx.Response(200, text=DMR)
        if ".dap.csv" in url:
            nombre = url.split("/granules/")[1].split(".dap.csv")[0]
            texto = nombre.split("_")[5]
            dia = date(int(texto[:4]), int(texto[4:6]), int(texto[6:]))
            expresion = pedido.url.params["dap4.ce"]
            assert "[1262][1228:1:1229]" in expresion and "Polar" not in expresion
            lineas = ["Dataset: x"]
            for nombre_pasada, campos in RUTAS.items():
                humedad, bandera = self.dias[dia].get(nombre_pasada, (-9999.0, 65534))
                if "_002" in nombre:
                    humedad = 0.2  # el reprocesado es el que vale
                valores = {"humedad": humedad, "bandera": bandera,
                           "lat": CENTRO[0] if humedad > -9999 else -9999.0,
                           "lon": CENTRO[1] if humedad > -9999 else -9999.0}
                for campo, ruta in campos.items():
                    lineas.append(f"{ruta}[0], {valores[campo]}, -9999")
            return httpx.Response(200, text="\n".join(lineas) + "\n")
        return httpx.Response(404)


def cliente(nasa):
    return httpx.Client(transport=httpx.MockTransport(nasa))


def test_obtener_humedad_l3_un_valor_por_dia(credenciales):
    nasa = NASAFalsa({date(2026, 1, 1): {"AM": (0.05, 0)},
                      date(2026, 1, 3): {"AM": (0.08, 0), "PM": (0.10, 0)},
                      date(2026, 1, 4): {},
                      date(2026, 1, 5): {"PM": (0.11, 0)}})
    obs = smap_l3.obtener_humedad_l3("lote-7", LAT, LON, date(2026, 1, 1), date(2026, 1, 5), cliente=cliente(nasa))
    assert [(o.fecha.day, o.valor, o.calidad) for o in obs] == [
        (1, 0.05, "buena"), (2, None, "descartada"), (3, 0.09, "buena"), (4, None, "descartada"), (5, 0.2, "buena")]
    assert "no publicó" in obs[1].nota and "no pasó" in obs[3].nota
    assert sum(1 for p in nasa.pedidos if str(p.url).endswith(".dmr")) == 1  # metadatos una sola vez
    assert all(p.headers.get("Authorization") == "Bearer tk" for p in nasa.pedidos if ".dap.csv" in str(p.url))


def test_leer_periodo_trae_la_celda_del_archivo_para_verificar_la_grilla(credenciales):
    nasa = NASAFalsa({date(2026, 1, 1): {"AM": (0.05, 0)}})
    leidos = smap_l3.leer_periodo(LAT, LON, date(2026, 1, 1), date(2026, 1, 1), cliente=cliente(nasa))
    am, pm = leidos[date(2026, 1, 1)]["AM"], leidos[date(2026, 1, 1)]["PM"]
    assert (am["lat"], am["lon"]) == CENTRO and pm["lat"] is None and pm["humedad"] is None
    assert pm["bandera"] == 65534  # la bandera no se limpia: el relleno lo resuelve la humedad


def test_si_la_nube_de_nsidc_no_tiene_la_coleccion_usa_la_vigente_de_cmr(credenciales):
    nasa = NASAFalsa({date(2026, 1, 1): {"AM": (0.05, 0)}}, colecciones_cloud=False)
    obs = smap_l3.obtener_humedad_l3("lote-7", LAT, LON, date(2026, 1, 1), date(2026, 1, 1), cliente=cliente(nasa))
    assert obs[0].valor == 0.05


def test_sin_archivos_es_error_y_no_lista_de_descartes(credenciales):
    with pytest.raises(smap_l3.ErrorSMAPL3, match="CMR no tiene archivos"):
        smap_l3.obtener_humedad_l3("lote-7", LAT, LON, date(2026, 1, 1), date(2026, 1, 3), cliente=cliente(NASAFalsa({})))


def test_acceso_negado_es_error_claro(credenciales):
    def negado(pedido):
        if ".dap.csv" in str(pedido.url):
            return httpx.Response(401)
        return NASAFalsa({date(2026, 1, 1): {"AM": (0.05, 0)}})(pedido)
    with pytest.raises(smap_l3.ErrorSMAPL3, match="negó el acceso"):
        smap_l3.obtener_humedad_l3("lote-7", LAT, LON, date(2026, 1, 1), date(2026, 1, 1),
                                   cliente=httpx.Client(transport=httpx.MockTransport(negado)))


def test_faltan_credenciales(monkeypatch):
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)
    from rotaterra.fuentes import earthdata
    with pytest.raises(earthdata.FaltanCredenciales):
        smap_l3.obtener_humedad_l3("lote-7", LAT, LON, date(2026, 1, 1), date(2026, 1, 1),
                                   cliente=cliente(NASAFalsa({})))


@pytest.mark.parametrize("lat, lon, desde, hasta", [
    (-95, LON, date(2026, 1, 1), date(2026, 1, 2)), (LAT, 200, date(2026, 1, 1), date(2026, 1, 2)),
    (LAT, LON, date(2026, 1, 2), date(2026, 1, 1)), (LAT, LON, date(2025, 1, 1), date(2026, 1, 2))])
def test_pedido_invalido(lat, lon, desde, hasta):
    with pytest.raises(ValueError):
        smap_l3.obtener_humedad_l3("lote-7", lat, lon, desde, hasta)


# ---------- conexión con el núcleo ----------

def test_se_registra_como_segundo_respaldo_de_smap():
    (satelite,) = smap_l3.SATELITES
    assert (satelite.nombre, satelite.respaldo_de, satelite.orden) == ("SMAP:L3", "SMAP", 2)


def test_pedir_usa_el_centro_del_lote(monkeypatch):
    pedidos = []
    monkeypatch.setattr(smap_l3, "obtener_humedad_l3", lambda *a: pedidos.append(a) or [])
    smap_l3.SATELITES[0].pedir({"id": "lote-7", "lat": LAT, "lon": LON}, date(2026, 1, 1), date(2026, 1, 2))
    assert pedidos == [("lote-7", LAT, LON, date(2026, 1, 1), date(2026, 1, 2))]


def test_endpoint_de_prueba(monkeypatch):
    app = FastAPI()
    app.include_router(smap_l3.router)
    web = TestClient(app)
    monkeypatch.setattr(smap_l3, "obtener_humedad_l3", lambda *a: [smap_l3.a_observacion(a[0], a[3], None)])
    r = web.get("/humedad-suelo/l3", params={"lote_id": "lote-7", "lat": LAT, "lon": LON,
                                             "desde": "2026-01-01", "hasta": "2026-01-01"})
    assert r.status_code == 200 and r.json()[0]["calidad"] == "descartada"
    r = web.get("/humedad-suelo/l3", params={"lote_id": "lote-7", "lat": LAT, "lon": LON,
                                             "desde": "2026-01-02", "hasta": "2026-01-01"})
    assert r.status_code == 422

    def caida(*a):
        raise smap_l3.ErrorSMAPL3("la NASA no respondió")
    monkeypatch.setattr(smap_l3, "obtener_humedad_l3", caida)
    r = web.get("/humedad-suelo/l3", params={"lote_id": "lote-7", "lat": LAT, "lon": LON,
                                             "desde": "2026-01-01", "hasta": "2026-01-01"})
    assert r.status_code == 502
