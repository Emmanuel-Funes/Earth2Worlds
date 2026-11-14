"""Núcleo independiente de los satélites (spec 009)."""

import ast
import sys
from pathlib import Path

import pytest

from rotaterra.fuentes import registro

FUENTES = Path(__file__).resolve().parent.parent / "rotaterra" / "fuentes"
# lo único de rotaterra que un satélite puede usar: el núcleo compartido
PERMITIDOS = {"rotaterra.contrato", "rotaterra.geo", "rotaterra.fuentes.earthdata", "rotaterra.fuentes.registro"}


def satelites_en_esta_rama() -> list[Path]:
    return [p for p in sorted(FUENTES.glob("*.py"))
            if p.stem not in registro.NUCLEO and not p.stem.startswith("_")]


def importados(archivo: Path) -> set[str]:
    nombres = set()
    for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Import):
            nombres |= {a.name for a in nodo.names}
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            nombres.add(nodo.module)
            if nodo.module == "rotaterra.fuentes":  # from rotaterra.fuentes import earthdata
                nombres |= {f"rotaterra.fuentes.{a.name}" for a in nodo.names}
    return nombres


@pytest.mark.parametrize("archivo", satelites_en_esta_rama(), ids=lambda p: p.stem)
def test_ningun_satelite_depende_de_otro(archivo):
    ajenos = {n for n in importados(archivo) if n.startswith("rotaterra")} - PERMITIDOS - {"rotaterra.fuentes"}
    assert not ajenos, f"{archivo.name} usa código de otro satélite: {sorted(ajenos)}"


@pytest.mark.parametrize("archivo", [FUENTES.parent / n for n in ("contrato.py", "base.py", "geo.py", "actualizar.py",
                                                                   "api.py", "consulta.py")] + [FUENTES / "registro.py",
                                                                                 FUENTES / "earthdata.py"],
                         ids=lambda p: p.stem)
def test_el_nucleo_no_nombra_ningun_satelite(archivo):
    nombres = {p.stem for p in satelites_en_esta_rama()} | {"power", "hls", "smap", "imerg", "merra2", "modis",
                                                             "nasadem"}
    usados = {n.rsplit(".", 1)[-1] for n in importados(archivo) if n.startswith("rotaterra.fuentes.")}
    assert not usados & nombres


def test_cada_satelite_de_esta_rama_se_anuncia():
    conectados = registro.descubrir()
    assert not conectados.rotos
    assert len({s.nombre for s in conectados.satelites}) == len(conectados.satelites)  # sin nombres repetidos
    for s in conectados.satelites:
        assert s.respaldo_de is None or ":" in s.nombre  # un respaldo se llama "PRINCIPAL:camino"


@pytest.fixture
def paquete_de_prueba(tmp_path, monkeypatch):
    """Un paquete con un satélite sano, uno roto y un módulo del núcleo."""
    raiz = tmp_path / "satelites_prueba"
    raiz.mkdir()
    (raiz / "__init__.py").write_text("")
    (raiz / "sano.py").write_text(
        "from rotaterra.fuentes.registro import Satelite\n"
        "SATELITES = [Satelite('SANO', lambda lote, desde, hasta: [])]\n")
    (raiz / "roto.py").write_text("import modulo_que_no_existe\n")
    (raiz / "earthdata.py").write_text("raise RuntimeError('el núcleo no se carga como satélite')\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    yield "satelites_prueba"
    for nombre in [m for m in sys.modules if m.startswith("satelites_prueba")]:
        del sys.modules[nombre]


def test_un_satelite_roto_queda_aislado(paquete_de_prueba):
    conectados = registro.descubrir(paquete_de_prueba)
    assert [s.nombre for s in conectados.satelites] == ["ROTO", "SANO"]
    assert "modulo_que_no_existe" in conectados.rotos["roto"]
    with pytest.raises(RuntimeError, match="no carga"):
        conectados.satelites[0].pedir({}, None, None)
