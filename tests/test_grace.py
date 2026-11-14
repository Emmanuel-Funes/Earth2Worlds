from datetime import date

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rotaterra.fuentes import grace

LAT, LON = -33.7025, -65.2975

DMR_DA = """<?xml version="1.0" encoding="ISO-8859-1"?>
<Dataset xmlns="http://xml.opendap.org/ns/DAP/4.0#" name="GRACEDADM_CLSM025GL_7D.A20260105.030.nc4">
  <Dimension name="time" size="1"/><Dimension name="lat" size="600"/><Dimension name="lon" size="1440"/>
  <Float64 name="time"><Dim name="/time"/>
    <Attribute name="units" type="String"><Value>days since 1948-01-01 00:00:00</Value></Attribute></Float64>
  <Float32 name="lat"><Dim name="/lat"/></Float32>
  <Float32 name="lon"><Dim name="/lon"/></Float32>
  <Float32 name="gws_inst"><Dim name="/time"/><Dim name="/lat"/><Dim name="/lon"/></Float32>
  <Float32 name="rtzsm_inst"><Dim name="/time"/><Dim name="/lat"/><Dim name="/lon"/></Float32>
  <Float32 name="sfsm_inst"><Dim name="/time"/><Dim name="/lat"/><Dim name="/lon"/></Float32>
</Dataset>"""

LATS_DA = [-59.875 + 0.25 * i for i in range(600)]
LONS_DA = [-179.875 + 0.25 * i for i in range(1440)]


@pytest.fixture(autouse=True)
def sin_esquemas_guardados():
    grace._ESQUEMA.clear()


@pytest.fixture
def credenciales(monkeypatch):
    monkeypatch.setenv("EARTHDATA_USERNAME", "usuario")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "clave")


def csv(**variables) -> str:
    lineas = ["Dataset: prueba"]
    for nombre, filas in variables.items():
        for fila in filas:
            lineas.append(", ".join([nombre] + ["" if v is None else str(v) for v in fila]))
    return "\n".join(lineas)


# ---------- reglas sin NASA ----------

def test_categorias_de_la_escala_de_sequia():
    assert grace.categoria(1.5) == "sequía excepcional"
    assert grace.categoria(8) == "sequía severa"
    assert grace.categoria(25) == "anormalmente seco"
    assert grace.categoria(50) == "normal"
    assert grace.categoria(85) == "más húmedo que lo normal"


def test_lunes_del_periodo():
    assert grace.lunes(date(2026, 1, 1), date(2026, 1, 20)) == [date(2026, 1, 5), date(2026, 1, 12),
                                                                date(2026, 1, 19)]
    assert grace.lunes(date(2026, 1, 6), date(2026, 1, 9)) == []


def test_esquema_lee_dimensiones_y_unidades():
    esq = grace.esquema(DMR_DA)
    assert esq["variables"]["gws_inst"] == ["time", "lat", "lon"]
    assert esq["tamanos"] == {"time": 1, "lat": 600, "lon": 1440}
    assert esq["unidades"]["time"].startswith("days since 1948")


def test_expresion_pide_dos_celdas_en_la_ultima_dimension():
    esq = grace.esquema(DMR_DA)
    assert grace.expresion("gws_inst", esq, {"lat": (104, 104), "lon": (458, 458)}) == "gws_inst[0:1:0][104:1:104][458:1:459]"
    assert grace.expresion("gws_inst", esq, {"lat": (0, 0), "lon": (1439, 1439)}).endswith("[1438:1:1439]")


def test_tiempo_del_mascon_a_fechas():
    assert grace.fechas_del_tiempo([8780.0], "days since 2002-01-01T00:00:00Z") == [date(2026, 1, 15)]
    with pytest.raises(grace.ErrorGRACE):
        grace.fechas_del_tiempo([1.0], "seconds since 1970-01-01")


def test_semana_publicada_da_percentil_categoria_y_aviso_regional():
    obs = grace.a_observaciones("lote-7", date(2026, 1, 5),
                                {"gws_inst": 8.04, "rtzsm_inst": 45.0, "sfsm_inst": 71.2}, date(2026, 6, 29))
    napa, raices, superficie = obs
    assert (napa.variable, napa.valor, napa.unidad, napa.fuente, napa.resolucion_m, napa.calidad) == \
        ("napa_percentil", 8.0, "%", "GRACE", 25000, "buena")
    assert "sequía severa" in napa.nota and "REGIONAL" in napa.nota and "1948 a 2014" in napa.nota
    assert raices.variable == "humedad_raices_percentil" and "normal" in raices.nota
    assert superficie.variable == "humedad_superficial_percentil" and "más húmedo" in superficie.nota


def test_semana_no_publicada_todavia_dice_la_ultima_publicada():
    obs = grace.a_observaciones("lote-7", date(2026, 9, 7), None, date(2026, 6, 29))
    assert all(o.valor is None and o.calidad == "descartada" for o in obs)
    assert "todavía no publicó" in obs[0].nota and "2026-06-29" in obs[0].nota


def test_semana_vieja_faltante_no_habla_de_atraso():
    obs = grace.a_observaciones("lote-7", date(2026, 1, 5), None, date(2026, 6, 29))
    assert "no publicó esta semana" in obs[0].nota and "atraso" not in obs[0].nota


def test_pixel_sin_dato_y_valor_fuera_de_rango():
    sin, raro, _ = grace.a_observaciones("lote-7", date(2026, 1, 5),
                                         {"gws_inst": None, "rtzsm_inst": 130.0, "sfsm_inst": 50.0}, None)
    assert sin.valor is None and sin.calidad == "descartada" and "sin dato" in sin.nota
    assert raro.valor == 130.0 and raro.calidad == "dudosa"


def test_relleno_de_la_nasa_es_sin_dato():
    assert grace._limpio(-9999.0) is None and grace._limpio(float("nan")) is None and grace._limpio(12.5) == 12.5


def test_mascon_a_observaciones():
    obs = grace.observaciones_mascon("lote-7", {date(2026, 1, 15): -12.345, date(2026, 2, 14): None})
    assert (obs[0].variable, obs[0].valor, obs[0].unidad, obs[0].calidad, obs[0].resolucion_m) == \
        ("agua_total_anomalia_cm", -12.35, "cm", "buena", 55000)
    assert "menos agua" in obs[0].nota and "2004-2009" in obs[0].nota
    assert obs[1].valor is None and obs[1].calidad == "descartada"


# ---------- NASA simulada ----------

def granulo(nombre: str, url: str) -> dict:
    return {"umm": {"GranuleUR": nombre, "RelatedUrls": [{"URL": url, "Type": "USE SERVICE API"}]}}


def nasa_da(pedidos: list[str]):
    semanas = {date(2026, 1, 5): (8.0, 40.0, 60.0), date(2026, 1, 12): (7.5, 35.0, 20.0)}

    def responder(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        pedidos.append(url)
        if "find_or_create_token" in url:
            return httpx.Response(200, json={"access_token": "token"})
        if "collections.umm_json" in url:
            return httpx.Response(200, json={"items": [{"meta": {"concept-id": "C-DA"}, "umm": {"Version": "3.0"}}]})
        if "granules.umm_json" in url:
            if request.url.params.get("sort_key") == "-start_date":
                return httpx.Response(200, json={"items": [granulo("GRACEDADM_CLSM025GL_7D.3.0:"
                                                                   "GRACEDADM_CLSM025GL_7D.A20260629.030.nc4", "x")]})
            return httpx.Response(200, json={"items": [
                granulo(f"GRACEDADM_CLSM025GL_7D.3.0:GRACEDADM_CLSM025GL_7D.A{d:%Y%m%d}.030.nc4",
                        f"https://opendap.earthdata.nasa.gov/da/{d:%Y%m%d}") for d in semanas]})
        if url.endswith(".dmr"):
            return httpx.Response(200, text=DMR_DA)
        if ".dap.csv" in url:
            pedido = request.url.params.get("dap4.ce")
            if pedido == "lat":
                return httpx.Response(200, text=csv(lat=[LATS_DA]))
            if pedido == "lon":
                return httpx.Response(200, text=csv(lon=[LONS_DA]))
            dia = date.fromisoformat(f"{url.split('/da/')[1][:4]}-{url.split('/da/')[1][4:6]}-"
                                     f"{url.split('/da/')[1][6:8]}")
            gws, rtz, sfs = semanas[dia]
            return httpx.Response(200, text=csv(gws_inst=[[gws, 99]], rtzsm_inst=[[rtz, 99]], sfsm_inst=[[sfs, 99]]))
        return httpx.Response(404)

    return responder


def test_napa_de_punta_a_punta_con_la_nasa_simulada(credenciales):
    pedidos = []
    cliente = httpx.Client(transport=httpx.MockTransport(nasa_da(pedidos)))
    obs = grace.obtener_napa("lote-7", LAT, LON, date(2026, 1, 1), date(2026, 1, 20), cliente=cliente)
    assert len(obs) == 9  # 3 lunes × 3 variables
    por_fecha = {(o.fecha, o.variable): o for o in obs}
    assert por_fecha[(date(2026, 1, 5), "napa_percentil")].valor == 8.0
    assert por_fecha[(date(2026, 1, 12), "humedad_superficial_percentil")].valor == 20.0
    assert por_fecha[(date(2026, 1, 19), "napa_percentil")].calidad == "descartada"
    recortes = [p for p in pedidos if "gws_inst" in p]
    # píxel del lote: latitud -33,625 (fila 105) y longitud -65,375 (columna 458)
    assert recortes and all("%5B105%3A1%3A105%5D%5B458%3A1%3A459%5D" in p or "[105:1:105][458:1:459]" in p
                            for p in recortes)


def test_sin_semanas_publicadas_avisa_para_que_entre_el_respaldo(credenciales):
    cliente = httpx.Client(transport=httpx.MockTransport(nasa_da([])))
    with pytest.raises(grace.ErrorGRACE, match="2026-06-29"):
        grace.obtener_napa("lote-7", LAT, LON, date(2026, 9, 1), date(2026, 9, 30), cliente=cliente)


def test_sin_credenciales_no_llama_a_la_nasa(monkeypatch):
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)
    with pytest.raises(grace.earthdata.FaltanCredenciales):
        grace.obtener_napa("lote-7", LAT, LON, date(2026, 1, 1), date(2026, 1, 20))


def test_pedido_invalido():
    with pytest.raises(ValueError):
        grace.validar_pedido(-95, LON, date(2026, 1, 1), date(2026, 1, 2))
    with pytest.raises(ValueError):
        grace.validar_pedido(LAT, LON, date(2025, 1, 1), date(2026, 6, 1))


def test_satelites_y_endpoint_de_prueba():
    nombres = {(s.nombre, s.respaldo_de) for s in grace.SATELITES}
    assert nombres == {("GRACE", None), ("GRACE:MASCON", "GRACE")}
    app = FastAPI()
    app.include_router(grace.router)
    r = TestClient(app).get("/napa", params={"lote_id": "x", "lat": -95, "lon": LON, "desde": "2026-01-01",
                                             "hasta": "2026-01-02"})
    assert r.status_code == 422



# ---------- respaldo: mascons de JPL (archivo entero, guardado una vez) ----------

ARCHIVO = "GRCTellus.JPL.200204_202607.GLO.RL06.3M.MSCNv04CRI.nc"


def nasa_mascon(pedidos: list[str]):
    def responder(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        pedidos.append(url)
        if "find_or_create_token" in url:
            return httpx.Response(200, json={"access_token": "token"})
        if "collections.umm_json" in url:
            return httpx.Response(200, json={"items": [{"meta": {"concept-id": "C-M"}, "umm": {"Version": "v4"}}]})
        if "granules.umm_json" in url:
            return httpx.Response(200, json={"items": [{"umm": {"GranuleUR": ARCHIVO[:-3], "RelatedUrls": [
                {"URL": f"https://archive.podaac.earthdata.nasa.gov/protegido/{ARCHIVO}", "Type": "GET DATA"},
                {"URL": f"s3://podaac/{ARCHIVO}", "Type": "GET DATA VIA DIRECT ACCESS"}]}}]})
        if url.endswith(ARCHIVO):
            return httpx.Response(200, content=b"NetCDF de prueba")
        return httpx.Response(404)

    return responder


def test_el_archivo_de_mascons_se_baja_una_sola_vez(credenciales, tmp_path, monkeypatch):
    monkeypatch.setattr(grace, "CARPETA_MASCON", tmp_path)
    pedidos = []
    cliente = grace.earthdata.cliente_autorizado(httpx.Client(transport=httpx.MockTransport(nasa_mascon(pedidos))))
    primera = grace.archivo_mascon(cliente, "C-M")
    segunda = grace.archivo_mascon(cliente, "C-M")
    assert primera == segunda == tmp_path / ARCHIVO and primera.read_bytes() == b"NetCDF de prueba"
    assert sum(1 for p in pedidos if p.endswith(ARCHIVO)) == 1
    assert not list(tmp_path.glob("*.parcial"))


def test_mascon_devuelve_solo_los_meses_del_periodo(credenciales, tmp_path, monkeypatch):
    monkeypatch.setattr(grace, "CARPETA_MASCON", tmp_path)
    leidos = []

    def pixel(ruta, lat, lon):
        leidos.append((ruta.name, lat, lon))
        return {date(2025, 12, 16): -9.0, date(2026, 1, 15): -10.5, date(2026, 2, 14): None, date(2026, 3, 16): -12.0}

    monkeypatch.setattr(grace, "pixel_por_mes", pixel)
    cliente = httpx.Client(transport=httpx.MockTransport(nasa_mascon([])))
    obs = grace.obtener_mascon("lote-7", LAT, LON, date(2026, 1, 1), date(2026, 2, 28), cliente=cliente)
    assert [(o.fecha, o.valor, o.calidad) for o in obs] == [(date(2026, 1, 15), -10.5, "buena"),
                                                           (date(2026, 2, 14), None, "descartada")]
    assert leidos == [(ARCHIVO, LAT, LON)]


def test_mascon_sin_meses_en_el_periodo_avisa(credenciales, tmp_path, monkeypatch):
    monkeypatch.setattr(grace, "CARPETA_MASCON", tmp_path)
    monkeypatch.setattr(grace, "pixel_por_mes", lambda ruta, lat, lon: {date(2026, 7, 16): -3.0})
    cliente = httpx.Client(transport=httpx.MockTransport(nasa_mascon([])))
    with pytest.raises(grace.ErrorGRACE, match="no publicó meses"):
        grace.obtener_mascon("lote-7", LAT, LON, date(2026, 9, 1), date(2026, 9, 30), cliente=cliente)


def test_mascon_ilegible_se_informa_como_error_de_grace(credenciales, tmp_path, monkeypatch):
    monkeypatch.setattr(grace, "CARPETA_MASCON", tmp_path)
    cliente = httpx.Client(transport=httpx.MockTransport(nasa_mascon([])))
    with pytest.raises(grace.ErrorGRACE, match="No se pudo leer los mascons"):
        grace.obtener_mascon("lote-7", LAT, LON, date(2026, 1, 1), date(2026, 2, 28), cliente=cliente)
