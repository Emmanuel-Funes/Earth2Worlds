"""Banco de semillas para la app: consultas de solo lectura sobre un archivo SQLite que viaja con la API (spec 057).

El archivo se arma en la rama de semillas (`semillas/construir_base.py` + `semillas/exportar_sqlite.py`, spec 049)
y se copia en `rotaterra/datos/semillas.sqlite`. Acá no se escribe nada: se abre en modo solo lectura.
Lo que la fuente no dice viene como "sin dato verificado"; estar inscripto en INASE no es tener stock.
Hernán: en esta etapa solo semillas del INTA, de todo el país. Por eso todo sale del INTA por defecto
(tabla `banco_inta`, solo cultivos extensivos) y lo de empresas privadas solo aparece con `incluir_privadas=true`, para más adelante.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

ARCHIVO = Path(__file__).resolve().parent / "datos" / "semillas.sqlite"

# cultivo de la app → tablas de ensayos (resumen y rindes) y la columna con el nombre del material
ENSAYOS = {
    "soja": ("recso_resumen_cultivar", "recso_rindes", "cultivar", "RECSO 2025/26 (INTA)"),
    "trigo": ("ret_resumen_cultivar", "ret_rindes", "cultivar", "RET de INASE, 2018/19 a 2025/26"),
    "girasol": ("girasol_resumen_cultivar", "girasol_rindes", "cultivar", "Red INTA-ASAGIR, 2023/24 a 2025/26"),
    "maiz": ("maiz_resumen_hibrido", "maiz_rindes", "hibrido", "Redes INTA Marcos Juárez y norte de Buenos Aires, 2024/25 y 2025/26"),
    "sorgo": ("sorgo_rindes", "sorgo_rindes", "hibrido", "Ensayo INTA EEA Manfredi 2024/25"),
    "san_luis": ("san_luis_rindes", "san_luis_rindes", "cultivar", "Ensayos INTA EEA San Luis + UNSL en la provincia, 2025/26"),
}
LEJOS = "OTRA_REGION"
SIN_FICHA = "sin dato verificado: ninguna fuente oficial (INTA, INASE) publica las condiciones de cultivo de esta variedad"

rutas = APIRouter(prefix="/semillas", tags=["semillas"])


def _abrir() -> sqlite3.Connection:
    ruta = Path(os.environ.get("ROTATERRA_SEMILLAS_DB", ARCHIVO))
    if not ruta.exists():
        raise HTTPException(status_code=503, detail="El banco de semillas no está cargado en esta API")
    db = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True, check_same_thread=False)
    db.row_factory = sqlite3.Row
    return db


def _filas(sql: str, parametros: tuple = ()) -> list[dict]:
    with closing(_abrir()) as db:
        return [dict(r) for r in db.execute(sql, parametros)]


def _ids_inta() -> set[str]:
    return {r["cultivar_id"] for r in _filas("SELECT cultivar_id FROM banco_inta")}


def _es_inta(fila: dict, ids: set[str]) -> bool:
    return fila.get("obtentor_inta") == "SI" or any(i.strip() in ids for i in str(fila.get("cultivar_id_inase") or "").split(";"))


def _cultivo(cultivo: str) -> tuple[str, str, str, str]:
    if cultivo not in ENSAYOS:
        raise HTTPException(status_code=404, detail=f"Sin ensayos cargados para '{cultivo}'. Hay: {', '.join(ENSAYOS)}")
    return ENSAYOS[cultivo]


@rutas.get("")
def resumen() -> dict:
    """Qué hay en el banco del INTA: fecha de corte de INASE, cultivares por grupo y por cultivo, y redes de ensayo."""
    manifiesto = {r["clave"]: r["valor"] for r in _filas("SELECT clave, valor FROM _manifiesto")}
    por_grupo = _filas("SELECT grupo, COUNT(*) AS cultivares FROM banco_inta GROUP BY grupo ORDER BY cultivares DESC")
    por_cultivo = _filas("SELECT grupo, cultivo, COUNT(*) AS cultivares, SUM(ensayos <> '') AS con_ensayos "
                         "FROM banco_inta GROUP BY grupo, cultivo ORDER BY cultivares DESC")
    return {"fecha_corte_inase": manifiesto.get("fecha_corte"), "solo_inta": True,
            "cultivares": sum(c["cultivares"] for c in por_grupo), "por_grupo": por_grupo,
            "por_cultivo": por_cultivo, "cultivos_con_ensayos": {k: v[3] for k, v in ENSAYOS.items()},
            "aviso": "Estar inscripto en INASE no es tener stock: disponibilidad y precio quedan sin dato verificado."}


@rutas.get("/cultivares")
def cultivares(cultivo: str | None = Query(None, description="Como en `por_cultivo` de /semillas, por ejemplo Maíz o Caña de azúcar"),
               grupo: str | None = Query(None, description="Como en `por_grupo` de /semillas, por ejemplo Cereales de invierno o Legumbres"),
               texto: str | None = Query(None, description="Parte del nombre del cultivar"),
               incluir_privadas: bool = Query(False, description="También los de empresas privadas (catálogo INASE completo, para más adelante)"),
               limite: int = Query(50, ge=1, le=500), desde: int = Query(0, ge=0)) -> dict:
    """Cultivares del INTA de cultivos extensivos inscriptos en INASE, de todo el país. Con `incluir_privadas`, el catálogo completo."""
    tabla, col_cultivo = ("cultivares", "perfil_ssd") if incluir_privadas else ("banco_inta", "cultivo")
    donde, parametros = [], []
    if cultivo:
        donde.append(f"{col_cultivo} = ?"); parametros.append(cultivo)
    if grupo and not incluir_privadas:
        donde.append("grupo = ?"); parametros.append(grupo)
    if texto:
        donde.append("(cultivar LIKE ? OR nombre_busqueda LIKE ?)"); parametros += [f"%{texto}%", f"%{texto.upper()}%"]
    filtro = f"WHERE {' AND '.join(donde)}" if donde else ""
    total = _filas(f"SELECT COUNT(*) AS n FROM {tabla} {filtro}", tuple(parametros))[0]["n"]
    filas = _filas(f"SELECT * FROM {tabla} {filtro} ORDER BY cultivar LIMIT ? OFFSET ?", (*parametros, limite, desde))
    return {"total": total, "desde": desde, "cultivares": filas}


@rutas.get("/cultivares/{cultivar_id}")
def cultivar(cultivar_id: str) -> dict:
    """Un cultivar con su registro en INASE, su ficha de cultivo (si alguna fuente oficial la publica) y,
    si se ensayó, cómo rindió (resumen de cada red)."""
    filas = _filas("SELECT * FROM banco_inta WHERE cultivar_id = ?", (cultivar_id,)) or \
        _filas("SELECT * FROM cultivares WHERE cultivar_id = ?", (cultivar_id,))
    if not filas:
        raise HTTPException(status_code=404, detail=f"No hay un cultivar con id '{cultivar_id}'")
    ensayos = {}
    hay = {r["name"] for r in _filas("SELECT name FROM sqlite_master WHERE type = 'table'")}
    ficha = _filas("SELECT atributo, valor, fuente, fuente_url FROM fichas_inta WHERE cultivar_id = ?",
                   (cultivar_id,)) if "fichas_inta" in hay else []
    for nombre, (tabla, _, _, red) in ENSAYOS.items():
        if tabla not in hay:
            continue
        # cultivar_id_inase puede traer varios ids separados por "; "
        encontrados = _filas(f'SELECT * FROM "{tabla}" WHERE "; " || cultivar_id_inase || ";" LIKE ?', (f"%; {cultivar_id};%",))
        if encontrados:
            ensayos[nombre] = {"red": red, "resultados": encontrados}
    return {"cultivar": filas[0], "ficha": ficha or SIN_FICHA, "ensayos": ensayos}


@rutas.get("/fichas")
def fichas(cultivo: str | None = Query(None, description="Como en `por_cultivo` de /semillas, por ejemplo Avena"),
           atributo: str | None = Query(None, description="Por ejemplo ciclo, epoca_siembra, zona_recomendada o tolerancia: sequía"),
           cultivar_id: str | None = Query(None, description="Solo la ficha de un cultivar")) -> dict:
    """Condiciones de cultivo por variedad del INTA: una fila por dato (ciclo, siembra, zona, sanidad, tolerancias...),
    cada una con la fuente oficial de donde sale. Un dato que ninguna fuente publica no tiene fila."""
    donde, parametros = [], []
    for col, val in (("cultivo", cultivo), ("cultivar_id", cultivar_id)):
        if val:
            donde.append(f"{col} = ?"); parametros.append(val)
    if atributo:
        donde.append("atributo LIKE ?"); parametros.append(f"{atributo}%")
    filtro = f"WHERE {' AND '.join(donde)}" if donde else ""
    filas = _filas(f"SELECT * FROM fichas_inta {filtro} ORDER BY cultivo, cultivar, atributo", tuple(parametros))
    por_cultivo = _filas("SELECT b.cultivo, COUNT(DISTINCT b.cultivar_id) AS cultivares, COUNT(DISTINCT f.cultivar_id) AS con_ficha "
                         "FROM banco_inta b LEFT JOIN fichas_inta f ON f.cultivar_id = b.cultivar_id GROUP BY b.cultivo ORDER BY cultivares DESC")
    return {"filas": filas, "cobertura": por_cultivo,
            "aviso": "Una variedad sin filas no tiene ficha publicada en fuentes oficiales: mostrarla como sin dato verificado."}


@rutas.get("/manejo")
def manejo(cultivo: str | None = Query(None, description="Como en `por_cultivo` de /semillas, por ejemplo Maní"),
           tema: str | None = Query(None, description="Por ejemplo epoca_siembra, densidad, ph, fertilizacion o cosecha"),
           solo_con_dato: bool = Query(False, description="Ocultar los temas que dicen sin dato verificado")) -> dict:
    """Buenas prácticas de manejo por cultivo (la guía práctica de maní adaptada a cada cultivo extensivo):
    clima, siembra, suelo, pH, densidad, fertilización, plagas, malezas, enfermedades, cosecha y secado.
    Cada dato trae su fuente argentina (INTA, SENASA, normas) y cómo se verificó; lo que falta dice sin dato verificado."""
    donde, parametros = [], []
    if cultivo:
        donde.append("cultivo = ?"); parametros.append(cultivo)
    if tema:
        donde.append("tema LIKE ?"); parametros.append(f"{tema}%")
    if solo_con_dato:
        donde.append("valor <> 'sin dato verificado'")
    filtro = f"WHERE {' AND '.join(donde)}" if donde else ""
    filas = _filas(f"SELECT * FROM manejo_cultivos {filtro}", tuple(parametros))
    if cultivo and not filas:
        raise HTTPException(status_code=404, detail=f"No hay datos de manejo para '{cultivo}'")
    return {"filas": filas,
            "aviso": "Son pautas generales y regionales; las de ensayos o de otra zona hay que ajustarlas al lote. "
                     "verificacion dice si se leyó el texto de la fuente o solo un resumen del buscador."}


NIVELES = ("San Luis", "Argentina", "global")


@rutas.get("/ambiente")
def ambiente(cultivo: str | None = Query(None, description="Como en `por_cultivo` de /semillas, por ejemplo Lenteja"),
             variable: str | None = Query(None, description="Parte del nombre, por ejemplo helada, ECe, Kc o agua útil"),
             nivel: str | None = Query(None, description="San Luis, Argentina o global (FAO y otros países)"),
             capa: str | None = Query(None, description="especie, ensayo, zona o criterio")) -> dict:
    """Lo que necesita cada especie del ambiente (spec 061): heladas y calor por etapa, temperatura de suelo, suelo,
    sales, sodio, pH, Kc, raíces y nutrientes, más ensayos y el clima y los suelos medidos en San Luis.
    Sale del dossier de investigación; cada dato trae fuente, sitio y nivel de evidencia."""
    if nivel and nivel not in NIVELES:
        raise HTTPException(status_code=400, detail=f"nivel debe ser uno de {', '.join(NIVELES)}")
    donde, parametros = [], []
    for columna, valor in (("cultivo_banco", cultivo), ("nivel", nivel), ("capa", capa)):
        if valor:
            donde.append(f"{columna} = ?"); parametros.append(valor)
    if variable:
        donde.append("variable LIKE ?"); parametros.append(f"%{variable}%")
    filtro = f"WHERE {' AND '.join(donde)}" if donde else ""
    filas = _filas(f"SELECT * FROM requerimientos_ambientales {filtro}", tuple(parametros))
    if cultivo and not filas:
        raise HTTPException(status_code=404, detail=f"No hay datos de ambiente para '{cultivo}'")
    por_nivel = {n: sum(1 for f in filas if f["nivel"] == n) for n in NIVELES}
    return {"filas": filas, "por_nivel": por_nivel,
            "aviso": "Referencia por especie, no por variedad ni por lote: no sirve para descartar un cultivo. "
                     "Los datos 'global' (FAO, EcoCrop, otros países) pesan poco; el pH óptimo de FAO no es un límite. "
                     "verificacion dice si se cotejó con el documento original."}


@rutas.get("/ensayos/{cultivo}")
def ensayos(cultivo: str, incluir_privadas: bool = Query(False, description="También los materiales de empresas privadas")) -> dict:
    """Resumen por cultivar de la red de ensayos del cultivo, solo los del INTA salvo `incluir_privadas`.

    El rinde relativo es contra la media de cada ensayo, que incluye a los privados: así se ve cómo le fue al INTA.
    """
    tabla, _, _, red = _cultivo(cultivo)
    filas = _filas(f'SELECT * FROM "{tabla}"')
    if not incluir_privadas:
        ids = _ids_inta()
        filas = [f for f in filas if _es_inta(f, ids)]
    return {"cultivo": cultivo, "red": red, "solo_inta": not incluir_privadas, "resultados": filas}


@rutas.get("/ensayos/{cultivo}/rindes")
def rindes(cultivo: str, cultivar: str | None = Query(None, description="Parte del nombre del cultivar o híbrido"),
           cerca_de_san_luis: bool = Query(True, description="Solo ensayos en San Luis o en zonas vecinas parecidas"),
           incluir_privadas: bool = Query(False, description="También los materiales de empresas privadas")) -> dict:
    """Cada cultivar en cada ensayo: kg/ha y rinde relativo a la media del ensayo. Solo los del INTA salvo `incluir_privadas`."""
    resumen, tabla, columna, red = _cultivo(cultivo)
    donde, parametros = [], []
    if cerca_de_san_luis:
        donde.append("referencia_san_luis <> ?"); parametros.append(LEJOS)
    if cultivar:
        donde.append(f'"{columna}" LIKE ?'); parametros.append(f"%{cultivar}%")
    filtro = f"WHERE {' AND '.join(donde)}" if donde else ""
    filas = _filas(f'SELECT * FROM "{tabla}" {filtro}', tuple(parametros))
    if not incluir_privadas:
        ids = _ids_inta()
        del_inta = {f[columna] for f in _filas(f'SELECT * FROM "{resumen}"') if _es_inta(f, ids)}
        filas = [f for f in filas if f[columna] in del_inta]
    return {"cultivo": cultivo, "red": red, "solo_inta": not incluir_privadas, "rindes": filas}


@rutas.get("/fuentes")
def fuentes() -> list[dict]:
    """De dónde sale cada dato del banco y en qué estado está (cargada, solo localizada)."""
    return _filas("SELECT * FROM fuentes")
