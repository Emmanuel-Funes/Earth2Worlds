"""El obtentor de cada variedad es el que dice el registro de INASE: nunca se completa con "INTA".

Auditoría del 14/11/2026: la pantalla mostraba "Obtentor: INTA" en todas las variedades (leía un campo
que la API no manda) y la base marcaba obtentor_inta = "SI" en las 547 del banco, incluidas las de la
EEAOC, universidades y CONICET.
"""

import json
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
BASE = RAIZ / "rotaterra" / "datos" / "semillas.sqlite"
PANTALLA = RAIZ / "static" / "js" / "rotaterra_modulos.js"


def _banco() -> list[dict]:
    with sqlite3.connect(f"file:{BASE}?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        return [dict(r) for r in db.execute("SELECT * FROM banco_inta")]


def test_solo_las_variedades_con_solicitante_inta_son_obtenidas_por_el_inta():
    banco = _banco()
    assert len(banco) == 547
    for c in banco:
        esperado = "SI" if c["vinculo_inta"] == "Solicitante INTA" else "NO"
        assert c["obtentor_inta"] == esperado, (c["cultivar"], c["vinculo_inta"], c["obtentor_inta"])
    assert sum(c["obtentor_inta"] == "SI" for c in banco) == 389


def test_una_variedad_de_la_eeaoc_no_figura_como_del_inta():
    tuc = next(c for c in _banco() if c["cultivar"] == "TUC ELITTE 17")
    assert tuc["obtentor_inta"] == "NO"
    assert "OBISPO COLOMBRES" in tuc["solicitante_rnc"]
    assert tuc["vinculo_inta"] == "Ente público: EEAOC (Tucumán)"


def test_el_banco_coincide_con_la_tabla_de_cultivares():
    with sqlite3.connect(f"file:{BASE}?mode=ro", uri=True) as db:
        distintos = db.execute("SELECT COUNT(*) FROM banco_inta b JOIN cultivares k USING (cultivar_id) "
                               "WHERE b.obtentor_inta <> k.obtentor_inta").fetchone()[0]
    assert distintos == 0


def test_la_pantalla_no_inventa_el_obtentor():
    texto = PANTALLA.read_text(encoding="utf-8")
    assert 'solicitante || "INTA"' not in texto
    assert "Obtentor: ${escapeHtml(obtentorCultivar(c))}" in texto
    assert "c.solicitante ||" not in texto


def _funcion_js(nombre: str) -> str:
    texto = PANTALLA.read_text(encoding="utf-8")
    inicio = texto.index(f"function {nombre}(")
    fin = texto.index("\n}\n", inicio) + 2
    return texto[inicio:fin]


@pytest.mark.skipif(shutil.which("node") is None, reason="hace falta Node.js para correr la función de la pantalla")
@pytest.mark.parametrize("cultivar, esperado", [
    ({"solicitante_rnc": "ESTACION EXPERIMENTAL AGRO INDUSTRIAL OBISPO COLOMBRES"},
     "ESTACION EXPERIMENTAL AGRO INDUSTRIAL OBISPO COLOMBRES"),
    ({"solicitante_rnc": "INSTITUTO NACIONAL DE TECNOLOGIA AGROPECUARIA"}, "INSTITUTO NACIONAL DE TECNOLOGIA AGROPECUARIA"),
    ({"solicitante_rnc": None}, "sin dato"),
    ({"solicitante_rnc": "   "}, "sin dato"),
    ({}, "sin dato"),
])
def test_la_funcion_de_la_pantalla_muestra_el_obtentor_real_o_sin_dato(cultivar, esperado):
    codigo = _funcion_js("obtentorCultivar") + f"\nprocess.stdout.write(obtentorCultivar({json.dumps(cultivar)}));"
    salida = subprocess.run(["node", "-e", codigo], capture_output=True, text=True, check=True, timeout=30)
    assert salida.stdout == esperado
