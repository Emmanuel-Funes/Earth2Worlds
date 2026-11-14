import re
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from rotaterra import api
from rotaterra.fuentes import earthdata, imerg


@pytest.fixture
def credenciales(monkeypatch):
    monkeypatch.setenv("EARTHDATA_USERNAME", "usuario")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "clave")


def granulo(nombre):
    return {"umm": {"GranuleUR": nombre, "RelatedUrls": [
        {"URL": f"https://data.gesdisc.example/{nombre}"},
        {"URL": f"https://opendap.earthdata.nasa.gov/collections/C/granules/{nombre}"}]}}


class NASAFalsa:
    """Imita Earthdata, CMR y OPeNDAP de GES DISC.

    archivos: producto -> {AAAAMMDD: valores}. IMERG: mm del día. MERRA-2 temperatura: (Kmax, Kmin).
    MERRA-2 radiación: lista de 24 valores W/m².
    """

    def __init__(self, archivos, acceso=True):
        self.archivos, self.acceso = archivos, acceso
        self.expresiones = []

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        url = str(pedido.url)
        if "find_or_create_token" in url:
            return httpx.Response(200, json={"access_token": "tk"})
        if "/collections.umm_json" in url:
            producto = pedido.url.params["short_name"]
            if producto not in self.archivos:
                return httpx.Response(200, json={"items": []})
            return httpx.Response(200, json={"items": [{"meta": {"concept-id": f"C-{producto}"}, "umm": {"Version": "07"}}]})
        if "/granules.umm_json" in url:
            producto = pedido.url.params["collection_concept_id"].removeprefix("C-")
            return httpx.Response(200, json={"items": [granulo(f"{producto}.x.{dia}.nc4") for dia in self.archivos[producto]]})
        if ".dap.csv" in url:
            if not self.acceso:
                return httpx.Response(403)
            assert pedido.headers["Authorization"] == "Bearer tk"
            expresion = pedido.url.params["dap4.ce"]
            self.expresiones.append(expresion)
            producto, dia = re.search(r"granules/(\w+)\.x\.(\d{8})", url).groups()
            valor = self.archivos[producto][dia]
            if producto.startswith("GPM"):
                return httpx.Response(200, text=f"Dataset: x\n/precipitation[0], {valor}, 99\n")
            if producto == "M2SDNXSLV":
                return httpx.Response(200, text=f"Dataset: x\n/T2MMAX[0], {valor[0]}, 1\n/T2MMIN[0], {valor[1]}, 1\n")
            filas = "".join(f"/SWGDN[{h}], {v}, 1\n" for h, v in enumerate(valor))
            return httpx.Response(200, text=f"Dataset: x\n{filas}")
        return httpx.Response(404)


def cliente(falsa):
    return httpx.Client(transport=httpx.MockTransport(falsa))


# ---------- IMERG ----------

def test_celda_del_lote_de_prueba():
    # la celda elegida tiene que contener al punto
    i_lon, i_lat = imerg.celda(-33.70, -65.30)
    assert -180 + i_lon * 0.1 <= -65.30 < -180 + (i_lon + 1) * 0.1
    assert -90 + i_lat * 0.1 <= -33.70 < -90 + (i_lat + 1) * 0.1


def test_imerg_usa_final_y_si_no_late(credenciales):
    falsa = NASAFalsa({"GPM_3IMERGDF": {"20260105": 1.5},
                       "GPM_3IMERGDL": {"20260105": 9.9, "20260106": 22.27}})
    obs = imerg.obtener_lluvia("lote-7", -33.7, -65.3, date(2026, 1, 5), date(2026, 1, 7),
                               cliente=cliente(falsa), hilos=2)
    assert [(o.fecha.day, o.valor, o.calidad) for o in obs] == [
        (5, 1.5, "buena"), (6, 22.27, "buena"), (7, None, "descartada")]
    assert "Final" in obs[0].nota and "Late" in obs[1].nota and "no publicó" in obs[2].nota
    assert all(o.fuente == "IMERG" and o.unidad == "mm/día" for o in obs)


def test_imerg_relleno_y_rango(credenciales):
    falsa = NASAFalsa({"GPM_3IMERGDL": {"20260105": -9999.9, "20260106": 700}})
    obs = imerg.obtener_lluvia("lote-7", -33.7, -65.3, date(2026, 1, 5), date(2026, 1, 6),
                               cliente=cliente(falsa), hilos=1)
    assert [(o.valor, o.calidad) for o in obs] == [(None, "descartada"), (700, "dudosa")]


def test_imerg_sin_autorizacion_de_ges_disc(credenciales):
    falsa = NASAFalsa({"GPM_3IMERGDL": {"20260105": 1.0}}, acceso=False)
    with pytest.raises(imerg.ErrorIMERG, match="autorizada"):
        imerg.obtener_lluvia("lote-7", -33.7, -65.3, date(2026, 1, 5), date(2026, 1, 5), cliente=cliente(falsa))


def test_imerg_sin_credenciales(monkeypatch):
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    with pytest.raises(earthdata.FaltanCredenciales):
        imerg.obtener_lluvia("lote-7", -33.7, -65.3, date(2026, 1, 5), date(2026, 1, 5),
                             cliente=cliente(NASAFalsa({})))


def test_api_lluvia(monkeypatch):
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    r = TestClient(api.app).get("/lluvia", params=dict(lote_id="l", lat=-33.7, lon=-65.3,
                                                       desde="2026-01-05", hasta="2026-01-06"))
    assert r.status_code == 503
    r = TestClient(api.app).get("/lluvia", params=dict(lote_id="l", lat=-33.7, lon=-65.3,
                                                       desde="2026-01-06", hasta="2026-01-05"))
    assert r.status_code == 422
