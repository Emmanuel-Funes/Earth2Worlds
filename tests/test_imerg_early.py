"""IMERG Early, respaldo "del día" de IMERG (spec 043): tests sin internet con la NASA simulada."""

import re
from datetime import date

import httpx
import pytest

from rotaterra.fuentes import earthdata, imerg_early

DIARIO = imerg_early.DIARIO
MEDIA = imerg_early.MEDIA_HORA


@pytest.fixture
def credenciales(monkeypatch):
    monkeypatch.setenv("EARTHDATA_USERNAME", "usuario")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "clave")


def nombre_media_hora(dia: str, hora: str) -> str:
    return f"3B-HHR-E.MS.MRG.3IMERG.{dia}-S{hora}00-E{hora[:2]}2959.0840.V07C.HDF5"


class NASAFalsa:
    """diarios: AAAAMMDD -> mm/día. medias: AAAAMMDD -> {'HHMM': mm/h}."""

    def __init__(self, diarios=None, medias=None):
        self.diarios, self.medias = diarios or {}, medias or {}
        self.expresiones = []

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        url = str(pedido.url)
        if "find_or_create_token" in url:
            return httpx.Response(200, json={"access_token": "tk"})
        if "/collections.umm_json" in url:
            producto = pedido.url.params["short_name"]
            return httpx.Response(200, json={"items": [{"meta": {"concept-id": f"C-{producto}"},
                                                        "umm": {"Version": "07"}}]})
        if "/granules.umm_json" in url:
            producto = pedido.url.params["collection_concept_id"].removeprefix("C-")
            if producto == DIARIO:
                nombres = [f"3B-DAY-E.MS.MRG.3IMERG.{d}-S000000-E235959.V07C.nc4" for d in self.diarios]
            else:
                nombres = [nombre_media_hora(d, h) for d, horas in self.medias.items() for h in horas]
            return httpx.Response(200, json={"items": [
                {"umm": {"GranuleUR": n, "RelatedUrls": [{"URL": f"https://opendap.earthdata.nasa.gov/g/{n}"}]}}
                for n in nombres]})
        if ".dap.csv" in url:
            expresion = pedido.url.params["dap4.ce"]
            self.expresiones.append(expresion)
            dia = re.search(r"3IMERG\.(\d{8})-", url)[1]
            if "3B-DAY" in url:
                return httpx.Response(200, text=f"Dataset: x\n/precipitation[0], {self.diarios[dia]}, 99\n")
            hora = re.search(r"-S(\d{4})00-", url)[1]
            return httpx.Response(200, text=f"Dataset: x\n/Grid/precipitation[0], {self.medias[dia][hora]}, 99\n")
        return httpx.Response(404)


def cliente(falsa):
    return httpx.Client(transport=httpx.MockTransport(falsa))


def test_usa_el_diario_y_suma_las_medias_horas_de_hoy(credenciales):
    medias = {f"{h:02d}{m:02d}": 2.0 for h in range(10) for m in (0, 30)}  # 20 medias horas a 2 mm/h = 20 mm
    falsa = NASAFalsa(diarios={"20261014": 12.5}, medias={"20261015": medias})
    obs = imerg_early.obtener_lluvia("lote-7", -33.7, -65.3, date(2026, 10, 14), date(2026, 10, 16),
                                     cliente(falsa))
    ayer, hoy, manana = obs
    assert (ayer.valor, ayer.calidad, ayer.fuente) == (12.5, "buena", "IMERG_EARLY")
    assert (hoy.valor, hoy.calidad) == (20.0, "dudosa")
    assert "hasta las 10:00 UTC" in hoy.nota and "20 de 48" in hoy.nota
    assert (manana.valor, manana.calidad) == (None, "descartada") and "todavía no publicó" in manana.nota
    assert any(e.startswith("/Grid/precipitation") for e in falsa.expresiones)


def test_dia_entero_de_medias_horas_es_bueno(credenciales):
    medias = {f"{h:02d}{m:02d}": 1.0 for h in range(24) for m in (0, 30)}
    obs = imerg_early.obtener_lluvia("lote-7", -33.7, -65.3, date(2026, 10, 15), date(2026, 10, 15),
                                     cliente(NASAFalsa(medias={"20261015": medias})))
    assert (obs[0].valor, obs[0].calidad) == (24.0, "buena")


def test_relleno_no_inventa(credenciales):
    obs = imerg_early.obtener_lluvia("lote-7", -33.7, -65.3, date(2026, 10, 15), date(2026, 10, 15),
                                     cliente(NASAFalsa(medias={"20261015": {"0000": -9999.9}})))
    assert (obs[0].valor, obs[0].calidad) == (None, "descartada")


def test_sin_credenciales():
    with pytest.raises(earthdata.FaltanCredenciales):
        imerg_early.obtener_lluvia("lote-7", -33.7, -65.3, date(2026, 10, 15), date(2026, 10, 15))


def test_se_anuncia_como_respaldo_del_dia_de_imerg():
    s, = imerg_early.SATELITES
    assert (s.nombre, s.respaldo_de, s.al_dia) == ("IMERG:IMERG_EARLY", "IMERG", True)
