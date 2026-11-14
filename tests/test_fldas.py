"""FLDAS como respaldo final de humedad del suelo (spec 036). Sin internet: CMR y OPeNDAP simulados."""

from datetime import date

import httpx
import pytest

from rotaterra.fuentes import earthdata, fldas

LAT, LON = -33.7025, -65.2975

DMR = """<?xml version="1.0" encoding="ISO-8859-1"?>
<Dataset xmlns="http://xml.opendap.org/ns/DAP/4.0#" name="FLDAS_NOAH01_C_GL_M.A202602.001.nc">
  <Dimension name="time" size="1"/><Dimension name="Y" size="1500"/><Dimension name="X" size="3600"/>
  <Float32 name="Y"><Dim name="/Y"/></Float32>
  <Float32 name="X"><Dim name="/X"/></Float32>
  <Float32 name="SoilMoi00_10cm_tavg"><Dim name="/time"/><Dim name="/Y"/><Dim name="/X"/></Float32>
  <Float32 name="SoilMoi10_40cm_tavg"><Dim name="/time"/><Dim name="/Y"/><Dim name="/X"/></Float32>
  <Float32 name="SoilMoi40_100cm_tavg"><Dim name="/time"/><Dim name="/Y"/><Dim name="/X"/></Float32>
</Dataset>"""

YS = [-59.95 + 0.1 * i for i in range(1500)]
XS = [-179.95 + 0.1 * i for i in range(3600)]


@pytest.fixture(autouse=True)
def sin_esquemas_guardados():
    fldas._ESQUEMA.clear()


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

def test_esquema_lee_dimensiones():
    esq = fldas.esquema(DMR)
    assert esq["variables"]["SoilMoi00_10cm_tavg"] == ["time", "Y", "X"]
    assert esq["tamanos"] == {"time": 1, "Y": 1500, "X": 3600}


def test_expresion_pide_dos_celdas_en_la_ultima_dimension():
    esq = fldas.esquema(DMR)
    ce = fldas.expresion("SoilMoi00_10cm_tavg", esq, 262, 1146, "Y", "X")
    assert ce == "SoilMoi00_10cm_tavg[0:1:0][262:1:262][1146:1:1147]"


def test_relleno_es_sin_dato():
    assert fldas._limpio(-9999.0) is None and fldas._limpio(float("nan")) is None
    assert fldas._limpio(0.234) == 0.234


def test_zona_raiz_es_el_promedio_ponderado_por_espesor():
    # 0,20 (0-10cm) · 0,15 (10-40cm) · 0,10 (40-100cm) -> (0,1*0,20 + 0,3*0,15 + 0,6*0,10)/1,0 = 0,125
    capas = {"SoilMoi00_10cm_tavg": 0.20, "SoilMoi10_40cm_tavg": 0.15, "SoilMoi40_100cm_tavg": 0.10}
    obs = fldas.a_observaciones("lote-7", date(2026, 2, 1), capas)
    por_var = {o.variable: o for o in obs}
    assert por_var["humedad_superficial"].valor == 0.20
    assert por_var["humedad_zona_raiz"].valor == 0.125
    assert all(o.calidad == "dudosa" and o.unidad == "m³/m³" and o.fuente == "FLDAS" for o in obs)
    assert "REGIONAL y MENSUAL" in por_var["humedad_superficial"].nota


def test_capa_faltante_se_descarta_sin_inventar():
    capas = {"SoilMoi00_10cm_tavg": None, "SoilMoi10_40cm_tavg": 0.15, "SoilMoi40_100cm_tavg": 0.10}
    por_var = {o.variable: o for o in fldas.a_observaciones("lote-7", date(2026, 2, 1), capas)}
    assert por_var["humedad_superficial"].valor is None and por_var["humedad_superficial"].calidad == "descartada"
    assert por_var["humedad_zona_raiz"].valor is None  # falta una capa: no se promedia


def test_fuera_de_rango_es_dudoso():
    capas = {"SoilMoi00_10cm_tavg": 5.0, "SoilMoi10_40cm_tavg": 5.0, "SoilMoi40_100cm_tavg": 5.0}
    por_var = {o.variable: o for o in fldas.a_observaciones("lote-7", date(2026, 2, 1), capas)}
    assert por_var["humedad_superficial"].calidad == "dudosa" and "rango físico" in por_var["humedad_superficial"].nota


# ---------- NASA simulada ----------

def nasa(pedidos, por_mes):
    """CMR da un archivo por mes; OPeNDAP da las 3 capas en el píxel del lote."""
    def responder(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        pedidos.append(url)
        if "find_or_create_token" in url:
            return httpx.Response(200, json={"access_token": "token"})
        if "collections.umm_json" in url:
            return httpx.Response(200, json={"items": [{"meta": {"concept-id": "C-FLDAS"}, "umm": {"Version": "001"}}]})
        if "granules.umm_json" in url:
            items = [{"umm": {"GranuleUR": f"{fldas.PRODUCTO}.A{aaaamm}.001.nc", "RelatedUrls": [
                {"URL": f"https://opendap.earthdata.nasa.gov/g/{aaaamm}"}]}} for aaaamm in por_mes]
            return httpx.Response(200, json={"items": items})
        if url.endswith(".dmr"):
            return httpx.Response(200, text=DMR)
        if ".dap.csv" in url:
            ce = request.url.params.get("dap4.ce")
            if ce == "Y":
                return httpx.Response(200, text=csv(Y=[YS]))
            if ce == "X":
                return httpx.Response(200, text=csv(X=[XS]))
            aaaamm = url.split("/g/")[1].split(".")[0]
            capas = por_mes[aaaamm]
            return httpx.Response(200, text=csv(**{c: [[v, v]] for c, v in capas.items()}))
        return httpx.Response(404)

    return responder


def test_humedad_de_punta_a_punta(credenciales):
    pedidos = []
    capas = {"SoilMoi00_10cm_tavg": 0.234, "SoilMoi10_40cm_tavg": 0.20, "SoilMoi40_100cm_tavg": 0.14}
    cliente = httpx.Client(transport=httpx.MockTransport(nasa(pedidos, {"202602": capas})))
    obs = fldas.obtener_humedad("lote-7", LAT, LON, date(2026, 2, 1), date(2026, 2, 28), cliente=cliente)
    por_var = {o.variable: o for o in obs}
    assert set(por_var) == {"humedad_superficial", "humedad_zona_raiz"}
    assert por_var["humedad_superficial"].valor == 0.234
    assert por_var["humedad_zona_raiz"].valor == round((0.1 * 0.234 + 0.3 * 0.20 + 0.6 * 0.14) / 1.0, 4)
    assert all(o.fecha == date(2026, 2, 1) and o.calidad == "dudosa" for o in obs)
    recortes = [p for p in pedidos if "SoilMoi00_10cm_tavg" in p]
    assert recortes and all("1147" in p or "[1146:1:1147]" in p for p in recortes)


def test_dos_meses_dan_dos_observaciones_por_variable(credenciales):
    c1 = {"SoilMoi00_10cm_tavg": 0.20, "SoilMoi10_40cm_tavg": 0.20, "SoilMoi40_100cm_tavg": 0.20}
    c2 = {"SoilMoi00_10cm_tavg": 0.10, "SoilMoi10_40cm_tavg": 0.10, "SoilMoi40_100cm_tavg": 0.10}
    cliente = httpx.Client(transport=httpx.MockTransport(nasa([], {"202601": c1, "202602": c2})))
    obs = fldas.obtener_humedad("lote-7", LAT, LON, date(2026, 1, 1), date(2026, 2, 28), cliente=cliente)
    assert [o.fecha for o in obs] == [date(2026, 1, 1), date(2026, 1, 1), date(2026, 2, 1), date(2026, 2, 1)]


def test_sin_meses_publicados_avisa_para_el_siguiente_respaldo(credenciales):
    cliente = httpx.Client(transport=httpx.MockTransport(nasa([], {})))
    with pytest.raises(fldas.ErrorFLDAS, match="no publicó"):
        fldas.obtener_humedad("lote-7", LAT, LON, date(2026, 2, 1), date(2026, 2, 28), cliente=cliente)


def test_pedido_invalido_no_llama_a_la_nasa(credenciales):
    with pytest.raises(ValueError):
        fldas.obtener_humedad("lote-7", -95, LON, date(2026, 1, 1), date(2026, 1, 31),
                              cliente=httpx.Client(transport=httpx.MockTransport(lambda p: httpx.Response(500))))
    with pytest.raises(ValueError):  # supera MAX_MESES
        fldas.validar_pedido(LAT, LON, date(2024, 1, 1), date(2026, 12, 1))


def test_sin_credenciales_pide_credenciales(monkeypatch):
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)
    with pytest.raises(earthdata.FaltanCredenciales):
        fldas.obtener_humedad("lote-7", LAT, LON, date(2026, 2, 1), date(2026, 2, 28))


def test_se_anuncia_como_respaldo_de_smap():
    (satelite,) = fldas.SATELITES
    assert (satelite.nombre, satelite.respaldo_de, satelite.orden) == ("SMAP:FLDAS", "SMAP", 4)
