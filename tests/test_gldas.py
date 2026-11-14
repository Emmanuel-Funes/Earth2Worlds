"""GLDAS como respaldo de humedad del suelo y de ET (spec 032). Sin internet: CMR y OPeNDAP simulados."""

from datetime import date

import httpx
import pytest

from rotaterra.fuentes import earthdata, gldas

LAT, LON = -33.7025, -65.2975

DMR = """<?xml version="1.0" encoding="ISO-8859-1"?>
<Dataset xmlns="http://xml.opendap.org/ns/DAP/4.0#" name="GLDAS_NOAH025_3H.A20260922.0000.021.nc4">
  <Dimension name="time" size="1"/><Dimension name="lat" size="600"/><Dimension name="lon" size="1440"/>
  <Float32 name="lat"><Dim name="/lat"/></Float32>
  <Float32 name="lon"><Dim name="/lon"/></Float32>
  <Float32 name="SoilMoi0_10cm_inst"><Dim name="/time"/><Dim name="/lat"/><Dim name="/lon"/></Float32>
  <Float32 name="RootMoist_inst"><Dim name="/time"/><Dim name="/lat"/><Dim name="/lon"/></Float32>
  <Float32 name="Evap_tavg"><Dim name="/time"/><Dim name="/lat"/><Dim name="/lon"/></Float32>
</Dataset>"""

LATS = [-59.875 + 0.25 * i for i in range(600)]
LONS = [-179.875 + 0.25 * i for i in range(1440)]
HORAS = [f"{h:02d}00" for h in range(0, 24, 3)]  # 0000, 0300, ..., 2100


@pytest.fixture(autouse=True)
def sin_esquemas_guardados():
    gldas._ESQUEMA.clear()


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
    esq = gldas.esquema(DMR)
    assert esq["variables"]["Evap_tavg"] == ["time", "lat", "lon"]
    assert esq["tamanos"] == {"time": 1, "lat": 600, "lon": 1440}


def test_expresion_pide_dos_celdas_en_la_ultima_dimension():
    esq = gldas.esquema(DMR)
    ce = gldas.expresion("Evap_tavg", esq, 105, 458, "lat", "lon")
    assert ce == "Evap_tavg[0:1:0][105:1:105][458:1:459]"


def test_relleno_de_la_nasa_es_sin_dato():
    assert gldas._limpio(-9999.0) is None and gldas._limpio(float("nan")) is None
    assert gldas._limpio(9.999e20) is None and gldas._limpio(0.15) == 0.15


def test_dia_completo_es_buena_y_convierte_la_unidad():
    # ET: Evap_tavg 3.47e-6 kg/m²/s × 86400 ≈ 0,3 mm/día
    valores = [3.47e-6 * 86400] * 8
    o = gldas.a_observacion("lote-7", date(2026, 9, 22), "et_mm_dia", valores, gldas.ET["et_mm_dia"])
    assert (o.variable, o.unidad, o.fuente, o.resolucion_m, o.calidad) == (
        "et_mm_dia", "mm/día", "GLDAS", 25000, "buena")
    assert round(o.valor, 1) == 0.3 and "Respaldo" in o.nota and "REGIONAL" in o.nota


def test_humedad_convierte_a_m3_m3():
    o_sup = gldas.a_observacion("lote-7", date(2026, 9, 22), "humedad_superficial", [0.15] * 8,
                                gldas.HUMEDAD["humedad_superficial"])  # ya en la unidad del contrato
    assert o_sup.valor == 0.15 and o_sup.unidad == "m³/m³" and o_sup.calidad == "buena"


def test_dia_incompleto_es_dudoso():
    o = gldas.a_observacion("lote-7", date(2026, 9, 22), "humedad_superficial", [0.15, 0.16],
                            gldas.HUMEDAD["humedad_superficial"])
    assert o.calidad == "dudosa" and "2 de 8" in o.nota


def test_fuera_de_rango_es_dudoso():
    o = gldas.a_observacion("lote-7", date(2026, 9, 22), "humedad_superficial", [5.0] * 8,
                            gldas.HUMEDAD["humedad_superficial"])  # 5 m³/m³ es imposible
    assert o.calidad == "dudosa" and "rango físico" in o.nota


def test_dia_sin_dato_se_descarta():
    o = gldas.a_observacion("lote-7", date(2026, 9, 22), "et_mm_dia", [], gldas.ET["et_mm_dia"])
    assert o.valor is None and o.calidad == "descartada"


# ---------- NASA simulada ----------

def granulo(producto: str, dia: str, hora: str, url: str) -> dict:
    nombre = f"{producto}.021:{producto}.A{dia}.{hora}.021.nc4"
    return {"umm": {"GranuleUR": nombre, "RelatedUrls": [{"URL": url, "Type": "USE SERVICE API"}]}}


def nasa(pedidos, et_por_hora, finales=HORAS, ep=()):
    """Simula CMR y OPeNDAP: el producto final trae las horas `finales`, el temprano las `ep`."""
    def responder(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        pedidos.append(url)
        if "find_or_create_token" in url:
            return httpx.Response(200, json={"access_token": "token"})
        if "collections.umm_json" in url:
            nombre = request.url.params["short_name"]
            cid = "C-FINAL" if nombre == gldas.PRODUCTO_FINAL else "C-EP"
            return httpx.Response(200, json={"items": [{"meta": {"concept-id": cid}, "umm": {"Version": "2.1"}}]})
        if "granules.umm_json" in url:
            cid = request.url.params["collection_concept_id"]
            producto, horas = (gldas.PRODUCTO_FINAL, finales) if cid == "C-FINAL" else (gldas.PRODUCTO_EP, ep)
            return httpx.Response(200, json={"items": [
                granulo(producto, "20260922", h, f"https://opendap.earthdata.nasa.gov/g/{producto}/{h}")
                for h in horas]})
        if url.endswith(".dmr"):
            return httpx.Response(200, text=DMR)
        if ".dap.csv" in url:
            ce = request.url.params.get("dap4.ce")
            if ce == "lat":
                return httpx.Response(200, text=csv(lat=[LATS]))
            if ce == "lon":
                return httpx.Response(200, text=csv(lon=[LONS]))
            hora = url.split("/g/")[1].split("/")[1].split(".")[0]
            producto = url.split("/g/")[1].split("/")[0]
            et = et_por_hora.get((producto, hora), 3.47e-6)
            return httpx.Response(200, text=csv(**{
                "SoilMoi0_10cm_inst": [[15.0, 99]], "RootMoist_inst": [[250.0, 99]], "Evap_tavg": [[et, 99]]}))
        return httpx.Response(404)

    return responder


def test_humedad_de_punta_a_punta(credenciales):
    pedidos = []
    cliente = httpx.Client(transport=httpx.MockTransport(nasa(pedidos, {})))
    obs = gldas.obtener_humedad("lote-7", LAT, LON, date(2026, 9, 22), date(2026, 9, 22), cliente=cliente)
    por_variable = {o.variable: o for o in obs}
    assert set(por_variable) == {"humedad_superficial", "humedad_zona_raiz"}
    assert por_variable["humedad_superficial"].valor == 0.15   # 15 / 100
    assert por_variable["humedad_zona_raiz"].valor == 0.25     # 250 / 1000
    assert all(o.calidad == "buena" and o.fuente == "GLDAS" for o in obs)
    recortes = [p for p in pedidos if "SoilMoi0_10cm_inst" in p]
    # píxel del lote: latitud -33,625 (fila 105) y longitud -65,375 (columna 458)
    assert recortes and all("%5B105%3A1%3A105%5D%5B458%3A1%3A459%5D" in p or "[105:1:105][458:1:459]" in p
                            for p in recortes)


def test_et_de_punta_a_punta(credenciales):
    cliente = httpx.Client(transport=httpx.MockTransport(nasa([], {})))
    obs = gldas.obtener_et("lote-7", LAT, LON, date(2026, 9, 22), date(2026, 9, 22), cliente=cliente)
    assert [o.variable for o in obs] == ["et_mm_dia"]
    assert round(obs[0].valor, 1) == 0.3 and obs[0].calidad == "buena"


def test_el_producto_final_pisa_al_temprano(credenciales):
    # el final trae solo 0000 (ET baja); el temprano trae las 8 horas (ET alta). El final debe ganar en 0000.
    et = {(gldas.PRODUCTO_FINAL, "0000"): 1.0e-6, (gldas.PRODUCTO_EP, "0000"): 9.0e-6}
    for h in HORAS[1:]:
        et[(gldas.PRODUCTO_EP, h)] = 9.0e-6
    cliente = httpx.Client(transport=httpx.MockTransport(nasa([], et, finales=("0000",), ep=HORAS)))
    por_dia = gldas.leer_periodo(LAT, LON, date(2026, 9, 22), date(2026, 9, 22), gldas.ET, cliente=cliente)
    valores = por_dia[date(2026, 9, 22)]["et_mm_dia"]
    assert len(valores) == 8  # 8 horas: 0000 del final + las otras 7 del temprano
    # el valor de 0000 es el del final (1.0e-6 × 86400), no el del temprano
    assert round(min(valores), 4) == round(1.0e-6 * 86400, 4)


def test_sin_pasos_publicados_avisa_para_que_entre_el_respaldo_siguiente(credenciales):
    cliente = httpx.Client(transport=httpx.MockTransport(nasa([], {}, finales=(), ep=())))
    with pytest.raises(gldas.ErrorGLDAS, match="no publicó pasos"):
        gldas.obtener_et("lote-7", LAT, LON, date(2026, 9, 22), date(2026, 9, 22), cliente=cliente)


def test_pedido_invalido_no_llama_a_la_nasa(credenciales):
    with pytest.raises(ValueError):
        gldas.obtener_humedad("lote-7", -95, LON, date(2026, 9, 1), date(2026, 9, 2),
                              cliente=httpx.Client(transport=httpx.MockTransport(lambda p: httpx.Response(500))))
    with pytest.raises(ValueError):  # supera MAX_DIAS
        gldas.validar_pedido(LAT, LON, date(2026, 1, 1), date(2026, 12, 1))


def test_sin_credenciales_pide_credenciales(monkeypatch):
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)
    with pytest.raises(earthdata.FaltanCredenciales):
        gldas.obtener_humedad("lote-7", LAT, LON, date(2026, 9, 22), date(2026, 9, 22))


def test_se_anuncia_como_respaldo_de_smap_y_de_et():
    nombres = {(s.nombre, s.respaldo_de, s.orden) for s in gldas.SATELITES}
    assert nombres == {("SMAP:GLDAS", "SMAP", 3), ("ET:GLDAS", "ET", 3)}
