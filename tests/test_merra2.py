import re
from datetime import date

import httpx
import pytest

from rotaterra.fuentes import merra2


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
            if valor is None:  # la NASA lista el archivo pero OPeNDAP no lo entrega
                return httpx.Response(404)
            if producto.startswith("GPM"):
                return httpx.Response(200, text=f"Dataset: x\n/precipitation[0], {valor}, 99\n")
            if producto == "M2SDNXSLV":
                return httpx.Response(200, text=f"Dataset: x\n/T2MMAX[0], {valor[0]}, 1\n/T2MMIN[0], {valor[1]}, 1\n")
            filas = "".join(f"/SWGDN[{h}], {v}, 1\n" for h, v in enumerate(valor))
            return httpx.Response(200, text=f"Dataset: x\n{filas}")
        return httpx.Response(404)


def cliente(falsa):
    return httpx.Client(transport=httpx.MockTransport(falsa))


# ---------- MERRA-2 ----------

def test_merra2_convierte_unidades(credenciales):
    falsa = NASAFalsa({"M2SDNXSLV": {"20260105": (309.033, 287.824)},
                       "M2T1NXRAD": {"20260105": [0] * 10 + [800] * 14}})
    obs = merra2.obtener_clima("lote-7", -33.7, -65.3, date(2026, 1, 5), date(2026, 1, 5),
                               cliente=cliente(falsa), hilos=1)
    valores = {o.variable: o.valor for o in obs}
    assert valores == {"temp_max": pytest.approx(35.88), "temp_min": pytest.approx(14.67),
                       "radiacion": pytest.approx(800 * 14 / 24 * 0.0864, abs=0.01)}
    assert all(o.fuente == "MERRA2" and o.calidad == "buena" for o in obs)
    assert any("[0:1:23]" in e for e in falsa.expresiones)


def test_merra2_solo_devuelve_dias_publicados(credenciales):
    falsa = NASAFalsa({"M2SDNXSLV": {"20260105": (300, 290)}, "M2T1NXRAD": {}})
    obs = merra2.obtener_clima("lote-7", -33.7, -65.3, date(2026, 1, 5), date(2026, 1, 9),
                               cliente=cliente(falsa), hilos=1)
    assert {o.fecha for o in obs} == {date(2026, 1, 5)}
    assert {o.variable for o in obs} == {"temp_max", "temp_min"}


def test_merra2_relleno_no_se_inventa(credenciales):
    falsa = NASAFalsa({"M2SDNXSLV": {"20260105": (1e15, 290)}, "M2T1NXRAD": {"20260105": [1e15] + [500] * 23}})
    obs = {o.variable: o for o in merra2.obtener_clima("lote-7", -33.7, -65.3, date(2026, 1, 5), date(2026, 1, 5),
                                                         cliente=cliente(falsa), hilos=1)}
    assert obs["temp_max"].valor is None and obs["temp_max"].calidad == "descartada"
    assert obs["radiacion"].valor is None  # con una hora de relleno no se calcula el total del día


def test_celda_merra2_mas_cercana():
    # verificado contra la NASA: para -33,7; -65,3 la celda tiene centro en -33,5; -65,0
    i_lat, i_lon = merra2.celda(-33.7, -65.3)
    assert -90 + i_lat * 0.5 == -33.5 and -180 + i_lon * 0.625 == -65.0


def test_merra2_un_dia_no_entregado_no_tira_el_pedido(credenciales):
    # 15/10/2026: CMR listaba el 11/8/2026 pero OPeNDAP devolvía 404, y se caía todo el respaldo (spec 042)
    falsa = NASAFalsa({"M2SDNXSLV": {"20260810": (300, 290), "20260811": None},
                       "M2T1NXRAD": {"20260810": [500] * 24, "20260811": None}})
    obs = merra2.obtener_clima("lote-7", -33.7, -65.3, date(2026, 8, 10), date(2026, 8, 11),
                               cliente=cliente(falsa), hilos=1)
    dia_bueno = {o.variable: o for o in obs if o.fecha == date(2026, 8, 10)}
    dia_malo = {o.variable: o for o in obs if o.fecha == date(2026, 8, 11)}
    assert dia_bueno["temp_max"].valor == pytest.approx(26.85) and dia_bueno["radiacion"].valor is not None
    assert set(dia_malo) == {"temp_max", "temp_min", "radiacion"}
    assert all(o.valor is None and o.calidad == "descartada" and "404" in o.nota for o in dia_malo.values())


def test_merra2_otros_errores_siguen_cortando(credenciales):
    with pytest.raises(merra2.ErrorMERRA2):
        merra2.obtener_clima("lote-7", -33.7, -65.3, date(2026, 1, 5), date(2026, 1, 5),
                             cliente=cliente(NASAFalsa({"M2SDNXSLV": {"20260105": (300, 290)}, "M2T1NXRAD": {}},
                                                       acceso=False)), hilos=1)
