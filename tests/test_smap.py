import re
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from rotaterra import api
from rotaterra.fuentes import smap

CAPA_SUP = "Geophysical_Data_sm_surface"
CAPA_RAIZ = "Geophysical_Data_sm_rootzone"


def csv_falso(filas):
    encabezado = f"ID,Latitude,Longitude,Date,SPL4SMGP_008_{CAPA_SUP},SPL4SMGP_008_{CAPA_RAIZ}"
    return "\n".join([encabezado] + [f"lote-7,-33.7,-65.3,{d},{s},{r}" for d, s, r in filas]) + "\n"


DIA_COMPLETO = [(f"2026-01-15T{h:02d}:30:00", 0.20, 0.25) for h in range(1, 24, 3)]


class AppEEARSFalso:
    """Imita la API de AppEEARS y registra lo que se le pide."""

    def __init__(self, csv_texto=None, estados=("processing", "done"), login_ok=True, existentes=()):
        self.csv = csv_texto if csv_texto is not None else csv_falso(DIA_COMPLETO)
        self.existentes = list(existentes)  # pedidos previos: dicts con task_id, task_name, status, lat, lon
        self.estados = list(estados)
        self.login_ok = login_ok
        self.pedido = None
        self.autorizacion = None

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        ruta = pedido.url.path.removeprefix("/api")
        if ruta == "/login":
            return httpx.Response(200 if self.login_ok else 401, json={"token": "tkn"})
        self.autorizacion = pedido.headers.get("Authorization")
        if ruta == "/product":
            return httpx.Response(200, json=[
                {"Product": "SPL4SMGP", "ProductAndVersion": "SPL4SMGP.007"},
                {"Product": "SPL4SMGP", "ProductAndVersion": "SPL4SMGP.008"},
                {"Product": "MOD13Q1", "ProductAndVersion": "MOD13Q1.061"}])
        if ruta == "/product/SPL4SMGP.008":
            return httpx.Response(200, json={CAPA_SUP: {}, CAPA_RAIZ: {}, "Geophysical_Data_sm_surface_wetness": {}})
        if ruta == "/task" and pedido.method == "GET":
            return httpx.Response(200, json=[{k: v for k, v in e.items() if k not in ("lat", "lon")}
                                             for e in self.existentes])
        previo = next((e for e in self.existentes if ruta == f"/task/{e['task_id']}"), None)
        if previo:
            puntos = [] if previo["lat"] is None else [{"latitude": previo["lat"], "longitude": previo["lon"]}]
            return httpx.Response(200, json={"status": previo["status"], "params": {"coordinates": puntos}})
        if ruta == "/task" and pedido.method == "POST":
            import json
            self.pedido = json.loads(pedido.content)
            return httpx.Response(202, json={"task_id": "t1", "status": "pending"})
        if ruta == "/task/t1":
            return httpx.Response(200, json={"status": self.estados.pop(0) if len(self.estados) > 1 else self.estados[0]})
        if ruta == "/bundle/t1":
            return httpx.Response(200, json={"files": [
                {"file_id": "f0", "file_name": "rotaterra-SPL4SMGP-008-granule-list.txt"},
                {"file_id": "f1", "file_name": "rotaterra-SPL4SMGP-008-results.csv"}]})
        if ruta == "/bundle/t1/f1":
            return httpx.Response(200, text=self.csv)
        return httpx.Response(404)


@pytest.fixture
def credenciales(monkeypatch):
    monkeypatch.setenv("EARTHDATA_USERNAME", "usuario")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "clave")


def pedir(falso, desde=date(2026, 1, 15), hasta=date(2026, 1, 15), **kwargs):
    cliente = httpx.Client(transport=httpx.MockTransport(falso))
    return smap.obtener_humedad("lote-7", -33.7, -65.3, desde, hasta,
                                cliente=cliente, dormir=lambda s: None, **kwargs)


def test_dia_completo_da_dos_variables_buenas(credenciales):
    obs = pedir(AppEEARSFalso())
    assert {o.variable: o.valor for o in obs} == {"humedad_superficial": 0.2, "humedad_zona_raiz": 0.25}
    assert all(o.calidad == "buena" and o.fuente == "SMAP" and o.resolucion_m == 9000 for o in obs)
    assert all("9 km" in o.nota for o in obs)


def test_pide_version_mas_nueva_y_capas_exactas(credenciales):
    falso = AppEEARSFalso()
    pedir(falso)
    capas = {c["layer"] for c in falso.pedido["params"]["layers"]}
    assert capas == {CAPA_SUP, CAPA_RAIZ}  # no se confunde con sm_surface_wetness
    assert {c["product"] for c in falso.pedido["params"]["layers"]} == {"SPL4SMGP.008"}
    assert falso.pedido["params"]["dates"] == [{"startDate": "01-15-2026", "endDate": "01-15-2026"}]
    assert falso.autorizacion == "Bearer tkn"


def test_relleno_no_se_inventa(credenciales):
    filas = [(f"2026-01-15T{h:02d}:30:00", -9999, -9999) for h in range(1, 24, 3)]
    obs = pedir(AppEEARSFalso(csv_falso(filas)))
    assert all(o.valor is None and o.calidad == "descartada" for o in obs)


def test_dia_incompleto_es_dudoso(credenciales):
    filas = DIA_COMPLETO[:5] + [(d, -9999, -9999) for d, _, _ in DIA_COMPLETO[5:]]
    obs = pedir(AppEEARSFalso(csv_falso(filas)))
    assert all(o.calidad == "dudosa" and "5 de 8" in o.nota for o in obs)
    assert obs[0].valor == pytest.approx(0.2)


def test_fuera_de_rango_es_dudoso():
    obs = smap.a_observacion("lote-7", date(2026, 1, 15), "humedad_superficial", [0.8] * 8)
    assert obs.calidad == "dudosa" and obs.valor == 0.8


def test_varios_dias_se_separan(credenciales):
    filas = DIA_COMPLETO + [(f"2026-01-16T{h:02d}:30:00", 0.10, 0.30) for h in range(1, 24, 3)]
    obs = pedir(AppEEARSFalso(csv_falso(filas)), hasta=date(2026, 1, 16))
    assert sorted({o.fecha for o in obs}) == [date(2026, 1, 15), date(2026, 1, 16)]


def test_dia_sin_filas_queda_descartado_y_no_desaparece(credenciales):
    obs = pedir(AppEEARSFalso(), hasta=date(2026, 1, 16))  # el CSV solo trae el 15
    dia16 = [o for o in obs if o.fecha == date(2026, 1, 16)]
    assert len(dia16) == 2 and all(o.valor is None and o.calidad == "descartada" for o in dia16)


def test_incompleto_y_fuera_de_rango_dice_los_dos_motivos():
    obs = smap.a_observacion("lote-7", date(2026, 1, 15), "humedad_superficial", [0.8] * 5 + [None] * 3)
    assert obs.calidad == "dudosa" and "rango" in obs.nota and "5 de 8" in obs.nota


def test_sin_credenciales(monkeypatch):
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)
    with pytest.raises(smap.FaltanCredenciales):
        pedir(AppEEARSFalso())


def test_clave_rechazada(credenciales):
    with pytest.raises(smap.ErrorSMAP, match="rechazó"):
        pedir(AppEEARSFalso(login_ok=False))


def test_pedido_con_error(credenciales):
    with pytest.raises(smap.ErrorSMAP):
        pedir(AppEEARSFalso(estados=("error",)))


def test_pedido_que_no_termina(credenciales):
    with pytest.raises(smap.DemoraSMAP):
        pedir(AppEEARSFalso(estados=("processing",)), espera_max_s=60, intervalo_s=20)


@pytest.mark.parametrize("lat, lon, desde, hasta", [
    (-95, -65, date(2026, 1, 1), date(2026, 1, 2)),
    (-33, -65, date(2026, 1, 5), date(2026, 1, 1)),
    (-33, -65, date(2024, 1, 1), date(2026, 1, 1)),
])
def test_pedido_invalido(lat, lon, desde, hasta):
    with pytest.raises(ValueError):
        smap.validar_pedido(lat, lon, desde, hasta)


def test_api_sin_credenciales_responde_503(monkeypatch):
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)
    r = TestClient(api.app).get("/humedad-suelo", params=dict(
        lote_id="lote-7", lat=-33.7, lon=-65.3, desde="2026-01-01", hasta="2026-01-31"))
    assert r.status_code == 503


def test_api_fechas_invertidas_responde_422():
    r = TestClient(api.app).get("/humedad-suelo", params=dict(
        lote_id="lote-7", lat=-33.7, lon=-65.3, desde="2026-02-01", hasta="2026-01-01"))
    assert r.status_code == 422


NOMBRE = "rotaterra-lote-7-20260115-20260115"


def test_reusa_pedido_igual_en_vez_de_volver_a_la_fila(credenciales):
    falso = AppEEARSFalso(existentes=[
        {"task_id": "t1", "task_name": NOMBRE, "status": "done", "created": "2026-10-03", "lat": -33.7, "lon": -65.3}])
    obs = pedir(falso)
    assert falso.pedido is None  # no se creó uno nuevo
    assert len(obs) == 2


def test_reusa_pedido_pendiente_aunque_hoy_termine_un_dia_mas_tarde(credenciales):
    # anoche se pidió del 15 al 15 y quedó en la fila; hoy se pide del 15 al 16: se espera el mismo pedido
    falso = AppEEARSFalso(existentes=[
        {"task_id": "t1", "task_name": NOMBRE, "status": "done", "created": "2026-10-02", "lat": -33.7, "lon": -65.3}])
    pedir(falso, hasta=date(2026, 1, 16))
    assert falso.pedido is None


@pytest.mark.parametrize("previo", [
    {"task_id": "viejo", "task_name": NOMBRE, "status": "error", "created": "2026-10-01", "lat": -33.7, "lon": -65.3},
    {"task_id": "viejo", "task_name": NOMBRE, "status": "done", "created": "2026-10-01", "lat": -31.0, "lon": -64.0},
    {"task_id": "viejo", "task_name": "otro-pedido", "status": "done", "created": "2026-10-01", "lat": -33.7, "lon": -65.3},
    {"task_id": "viejo", "task_name": "rotaterra-lote-7-20260110-20260115", "status": "done", "created": "2026-10-01",
     "lat": -33.7, "lon": -65.3},  # empieza otro día
    {"task_id": "viejo", "task_name": NOMBRE, "status": "done", "created": "2026-10-01", "lat": None, "lon": None},
])
def test_no_reusa_pedidos_fallidos_de_otro_punto_o_de_otro_nombre(credenciales, previo):
    falso = AppEEARSFalso(existentes=[previo])
    pedir(falso)
    assert falso.pedido is not None  # se creó uno nuevo


# ---------- camino directo (CMR + OPeNDAP) ----------

def test_celda_del_lote_de_prueba():
    # verificado contra la NASA: la celda (1262, 1228) tiene centro en -33.6715, -65.306
    assert smap.celda_ease2(-33.70, -65.30) == (1262, 1228)


def granulo(nombre):
    return {"umm": {"GranuleUR": nombre + "_u9loH5HD", "RelatedUrls": [
        {"URL": f"https://data.nsidc.example/{nombre}"},
        {"URL": f"https://opendap.earthdata.nasa.gov/collections/C1-NSIDC_CPRD/granules/{nombre}"}]}}


class NASAFalsa:
    """Imita Earthdata (token), CMR y OPeNDAP para SMAP L4."""

    def __init__(self, valores=None, faltan=(), token_ok=True):
        self.valores = valores or {}  # hora -> (superficial, raíz)
        self.faltan = set(faltan)    # nombres de archivo que la NASA no tiene
        self.token_ok = token_ok
        self.pedidos_pixel = []

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        url = str(pedido.url)
        if "find_or_create_token" in url:
            return httpx.Response(200 if self.token_ok else 401, json={"access_token": "tk"})
        if "/collections.umm_json" in url:
            return httpx.Response(200, json={"items": [
                {"meta": {"concept-id": "C0-NSIDC_CPRD"}, "umm": {"Version": "007"}},
                {"meta": {"concept-id": "C1-NSIDC_CPRD"}, "umm": {"Version": "008"}}]})
        if "/granules.umm_json" in url:
            assert pedido.url.params["collection_concept_id"] == "C1-NSIDC_CPRD"
            nombres = ["SMAP_L4_SM_gph_20260114T223000_Vv8011_001.h5"]  # del día anterior: se ignora
            nombres += [f"SMAP_L4_SM_gph_20260115T{h:02d}3000_Vv8011_001.h5" for h in range(1, 24, 3)]
            return httpx.Response(200, json={"items": [granulo(n) for n in nombres if n not in self.faltan]})
        if url.split("?")[0].endswith(".dap.csv"):
            assert pedido.headers["Authorization"] == "Bearer tk"
            self.pedidos_pixel.append(pedido.url.params["dap4.ce"])
            hora = int(re.search(r"T(\d\d)3000", url)[1])
            sup, raiz = self.valores.get(hora, (0.05, 0.06))
            texto = (f"Dataset: x.h5\n/Geophysical_Data/sm_surface[0], {sup}, 0.9\n"
                     f"/Geophysical_Data/sm_rootzone[0], {raiz}, 0.9\n")
            return httpx.Response(200, text=texto)
        return httpx.Response(404)


def directo(falsa, **kw):
    cliente = httpx.Client(transport=httpx.MockTransport(falsa))
    return smap.obtener_humedad_directo("lote-7", -33.7, -65.3, date(2026, 1, 15), date(2026, 1, 15),
                                        cliente=cliente, hilos=2, **kw)


def test_directo_promedia_los_8_archivos_del_dia(credenciales):
    falsa = NASAFalsa(valores={1: (0.04, 0.05), 4: (0.06, 0.07)})
    obs = directo(falsa)
    assert len(falsa.pedidos_pixel) == 8  # no lee el archivo de las 22:30 del día anterior
    assert "[1262][1228:1:1229]" in falsa.pedidos_pixel[0]
    sup = next(o for o in obs if o.variable == "humedad_superficial")
    assert sup.valor == pytest.approx((0.04 + 0.06 + 6 * 0.05) / 8, abs=1e-4)
    assert all(o.calidad == "buena" and o.fuente == "SMAP" and "NASA directo" in o.nota for o in obs)


def test_directo_relleno_y_archivos_faltantes(credenciales):
    falsa = NASAFalsa(valores={1: (-9999.0, -9999.0)},
                      faltan={"SMAP_L4_SM_gph_20260115T043000_Vv8011_001.h5"})
    obs = directo(falsa)
    assert all(o.calidad == "dudosa" and "6 de 8" in o.nota for o in obs)


def test_directo_dia_sin_archivos_queda_descartado(credenciales):
    falsa = NASAFalsa()
    cliente = httpx.Client(transport=httpx.MockTransport(falsa))
    obs = smap.obtener_humedad_directo("lote-7", -33.7, -65.3, date(2026, 1, 15), date(2026, 1, 16),
                                       cliente=cliente, hilos=2)
    assert {(o.fecha.day, o.calidad) for o in obs} == {(15, "buena"), (16, "descartada")}


def test_directo_sin_credenciales(monkeypatch):
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    with pytest.raises(smap.FaltanCredenciales):
        directo(NASAFalsa())


def test_directo_clave_rechazada(credenciales):
    with pytest.raises(smap.ErrorSMAP, match="rechazó"):
        directo(NASAFalsa(token_ok=False))
