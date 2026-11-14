"""Ficha técnica completa por variedad INTA (Hernán, 01/11/2026: "necesito la ficha técnica completa").

Junta en una planilla, para cada una de las 460 variedades de banco_inta:
  1. Registro oficial (INASE + catálogo INTA): especie, tipo, inscripción, propiedad, obtentor, licenciatario.
  2. Datos de la variedad (fichas_inta), ordenados por sección, cada uno con su fuente.
  3. Resultados de ensayos donde participó (RET trigo, RECSO soja, girasol, maíz, sorgo, INTA San Luis).
El manejo y el ambiente son del CULTIVO (no de la variedad) y van en hojas aparte.
Uso: python -m semillas.ficha_tecnica <semillas.sqlite> <salida.xlsx>
"""
import re, sqlite3, sys
from collections import defaultdict

SECCIONES = [  # (sección, regex sobre el atributo); la primera que coincide gana
    ("Tipo y uso", r"^(tipo|aptitud|uso|grano|destino|porte|tipo_crecimiento|planta)"),
    ("Ciclo y fenología", r"ciclo|madurez|floraci|espigaz|reposo|dias|días|fenolog|vernaliz|hábito|habito"),
    ("Zona, siembra y manejo", r"zona|siembra|densidad|surco|suelo|profundidad|adaptaci|cosecha|manejo|nitr|fertiliz|riego|lluvia|san luis|estabilidad|vuelco"),
    ("Rendimiento", r"rinde|rendimiento|forraje|produc|biomasa|materia seca|kg"),
    ("Sanidad y plagas", r"sanidad|roya|mancha|virus|mildiu|oídio|sclerotinia|orobanche|phoma|polilla|gorgojo|marchitez|enfermedad|plaga|pulg|mosca|carbón|bacteri|fusari"),
    ("Tolerancias", r"toleran|sequ|helada|frío|frio|alcalin|salin|estrés|invernal|herbicid|glifosato|sulfonil"),
    ("Calidad del grano", r"calidad|prote|aceite|ácido|acido|yodo|peso|hectol|gluten|fibra|azúcar|azucar|brix"),
    ("Planta", r"altura|macoll|espiga|granos por|tallo"),
    ("Comercial", r"licenciat|obtentor|semillero"),
]


PRINCIPALES = ["Tipo y uso", "Ciclo y fenología", "Zona, siembra y manejo", "Rendimiento", "Sanidad y plagas", "Calidad del grano"]


def seccion(atributo: str) -> str:
    a = atributo.lower().replace("usda grin: ", "")
    if "índice de cosecha" in a or "indice de cosecha" in a:
        return "Rendimiento"
    for nombre, rx in SECCIONES:
        if re.search(rx, a):
            return nombre
    return "Otros datos"


def etiqueta(atributo: str) -> str:
    a = atributo.replace("registro: ", "").replace("_", " ")
    return a[:1].upper() + a[1:]


def ensayos(c, cid):
    filas = []
    q = [
        ("RET trigo (red nacional)", "select * from ret_resumen_cultivar where cultivar_id_inase=?",
         lambda r: f"{r['ensayos_pais']} ensayos en el país, rinde {r['rinde_relativo_pais_pct']} % del promedio; región semiárida: {r['ensayos_semiarida_8_9_10'] or 0} ensayos, {r['rinde_relativo_semiarida_pct'] or 's/d'} %; última campaña {r['ultima_campana']}"),
        ("RECSO soja (red nacional)", "select * from recso_resumen_cultivar where cultivar_id_inase=?",
         lambda r: f"{r['ensayos_pais']} ensayos, rinde {r['rinde_relativo_pais_pct']} % del promedio; San Luis y vecinas: {r['ensayos_san_luis_y_vecinos'] or 0} ensayos, {r['rinde_relativo_san_luis_y_vecinos_pct'] or 's/d'} %"),
        ("Red de girasol", "select * from girasol_resumen_cultivar where cultivar_id_inase=?",
         lambda r: f"{r['ensayos_pais']} ensayos, rinde {r['rinde_relativo_pais_pct']} % del promedio; provincias vecinas a San Luis: {r['ensayos_vecinas_san_luis'] or 0} ensayos, {r['rinde_relativo_vecinas_pct'] or 's/d'} %"),
        ("Red de maíz", "select * from maiz_resumen_hibrido where cultivar_id_inase=?",
         lambda r: f"{r['ensayos_total']} ensayos, rinde {r['rinde_relativo_total_pct']} % del promedio; en San Luis: {r['ensayos_en_san_luis'] or 0} ensayos"),
        ("Ensayos de sorgo", "select * from sorgo_rindes where cultivar_id_inase=?",
         lambda r: f"{r['campana']} {r['sitio']}: {r['rinde_kg_ha']} kg/ha ({r['rinde_relativo_pct']} %)"),
        ("INTA EEA San Luis", "select * from san_luis_rindes where cultivar_id_inase=?",
         lambda r: f"{r['campana']} {r['sitio']} {r['tratamiento'] or ''}: {r['rinde_kg_ha']} kg/ha ({r['rinde_relativo_pct']} %)"),
    ]
    for red, sql, fmt in q:
        try:
            rs = c.execute(sql, (cid,)).fetchall()
        except sqlite3.OperationalError:
            continue
        for r in rs:
            url = r["fuente_url"] if "fuente_url" in r.keys() else ""
            filas.append(("Ensayos", red, fmt(r), red, url))
    return filas


def armar(db: str, salida: str):
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    c = sqlite3.connect(db); c.row_factory = sqlite3.Row
    banco = c.execute("select b.*, c.nombre_cientifico, c.inscripcion_rnpc, c.validez_rnpc from banco_inta b "
                      "left join cultivares c using(cultivar_id) order by b.cultivo, b.cultivar").fetchall()
    datos = defaultdict(list)
    for f in c.execute("select * from fichas_inta"):
        datos[f["cultivar_id"]].append(f)
    wb = openpyxl.Workbook()
    ind = wb.active; ind.title = "Índice"
    ft = wb.create_sheet("Ficha técnica")
    bold, head = Font(bold=True), PatternFill("solid", fgColor="E8EEF4")
    ind.append(["Cultivo", "Variedad", "Nivel de ficha", "Datos propios", "Ensayos", "Ciclo", "Aptitud / tipo", "Zona", "Época de siembra", "Inscripta", "Obtentor", "Licenciatario"])
    ft.append(["Cultivo", "Variedad", "Sección", "Dato", "Valor", "Fuente", "Enlace"])
    ORDEN = ["Registro oficial"] + [s for s, _ in SECCIONES] + ["Otros datos", "Ensayos"]
    for b in banco:
        cid = b["cultivar_id"]
        reg = [("Registro oficial", "Especie", f"{b['especie'].capitalize()} ({b['nombre_cientifico'] or ''})".replace(" ()", "")),
               ("Registro oficial", "Tipo de material", (b["condicion_genetica"] or "").capitalize()),
               ("Registro oficial", "Inscripta en el registro (RNC)", b["inscripcion_rnc"] or ""),
               ("Registro oficial", "Propiedad (RNPC)", f"desde {b['inscripcion_rnpc']} hasta {b['validez_rnpc']}" if b["inscripcion_rnpc"] else "sin título de propiedad en el catálogo"),
               ("Registro oficial", "Obtentor / solicitante", b["solicitante_rnc"] or ""),
               ("Registro oficial", "Unidad INTA", b["unidad_inta"] or ""),
               ("Registro oficial", "Licenciatario", b["licenciatario"] or "")]
        filas = [(s, d, v, "INASE, Catálogo Nacional de Cultivares (28/10/2026) y catálogo de variedades INTA", "https://www.argentina.gob.ar/inase") for s, d, v in reg if v]
        propios = [f for f in datos[cid] if not f["atributo"].startswith("registro: ")]
        for f in propios:
            filas.append((seccion(f["atributo"]), etiqueta(f["atributo"]), f["valor"], f["fuente"], f["fuente_url"]))
        en = ensayos(c, cid); filas += en
        filas.sort(key=lambda x: ORDEN.index(x[0]))
        for s, d, v, fu, u in filas:
            ft.append([b["cultivo"], b["cultivar"], s, d, v, fu, u])
        if propios:  # ficha completa: cada sección principal aparece, con dato o con el aviso de que no hay dato publicado
            tiene = {f[0] for f in filas} | ({"Rendimiento"} if en else set())
            for s in PRINCIPALES:
                if s not in tiene:
                    ft.append([b["cultivo"], b["cultivar"], s, "Sin dato publicado", "No se encontró una fuente reconocida que lo publique; pedir al INTA", "", ""])
        if not propios and not en:
            ft.append([b["cultivo"], b["cultivar"], "Aviso", "Sin datos publicados", "Solo hay datos del registro oficial; pedir la ficha al INTA", "", ""])
        get = lambda *ks: next((f["valor"] for f in propios for k in ks if f["atributo"] == k), "")
        nivel = "Completa" if propios else ("Solo ensayos" if en else "Básica (registro)")
        ind.append([b["cultivo"], b["cultivar"], nivel, len(propios), len(en), get("ciclo"), get("aptitud", "tipo"),
                    get("zona_recomendada"), get("epoca_siembra"), b["inscripcion_rnc"], b["solicitante_rnc"], b["licenciatario"] or get("licenciatario")])
    fu = wb.create_sheet("Fuentes por variedad")
    fu.append(["Cultivo", "Variedad", "N.º", "Fuente", "Enlace", "Datos que aporta"])
    por_var = defaultdict(lambda: defaultdict(int))
    for row in ft.iter_rows(min_row=2, values_only=True):
        if row[5]:
            por_var[(row[0], row[1])][(row[5], row[6] or "")] += 1
    for (cu, va), fuentes in por_var.items():
        for i, ((nombre, url), cant) in enumerate(sorted(fuentes.items(), key=lambda x: -x[1]), 1):
            fu.append([cu, va, i, nombre, url, cant])
    man = wb.create_sheet("Manejo por cultivo")
    man.append(["Cultivo", "Tema", "Valor", "Fuente", "Enlace", "Verificación"])
    for r in c.execute("select * from manejo_cultivos order by cultivo, tema"):
        man.append([r["cultivo"], r["tema"], r["valor"], r["fuente"], r["fuente_url"], r["verificacion"]])
    amb = wb.create_sheet("Ambiente por cultivo")
    amb.append(["Cultivo", "Variable", "Valor", "Unidad", "Etapa", "Sitio", "Nivel", "Fuente", "Enlace", "Advertencia"])
    for r in c.execute("select * from requerimientos_ambientales where cultivo_banco is not null and cultivo_banco<>'' order by cultivo_banco, variable"):
        amb.append([r["cultivo_banco"], r["variable"], r["valor"], r["unidad"], r["etapa"], r["sitio"], r["nivel"], r["fuente"], r["fuente_url"], r["advertencia"]])
    lee = wb.create_sheet("Cómo leer", 0)
    for linea in [
        ["Ficha técnica completa de las variedades INTA (Rotaterra, corte 28/10/2026, armada 01/11/2026)"], [],
        ["Índice: una fila por variedad con lo principal. Nivel de ficha: Completa = hay datos publicados de la variedad; Básica = solo el registro oficial."],
        ["Ficha técnica: todos los datos de cada variedad, por sección, cada uno con su fuente y enlace."],
        ["Fuentes por variedad: la lista de todas las fuentes de cada variedad y cuántos datos aporta cada una."],
        ["Manejo por cultivo y Ambiente por cultivo: valen para la especie (por ejemplo, todo el maíz), no para una variedad en particular."],
        ["Los datos marcados 'USDA GRIN' fueron medidos en EE.UU.; los 'No oficial' vienen de prensa o revistas técnicas que citan al INTA."],
        ["Nada fue inventado: si un dato no figura, es porque no hay fuente publicada que lo diga."]]:
        lee.append(linea)
    lee["A1"].font = Font(bold=True, size=13); lee.column_dimensions["A"].width = 140
    for ws, anchos in [(ind, [14, 28, 16, 12, 9, 22, 30, 30, 24, 12, 40, 30]), (ft, [14, 28, 18, 34, 60, 60, 40]), (fu, [14, 28, 6, 80, 50, 10]),
                       (man, [16, 24, 60, 50, 40, 20]), (amb, [16, 30, 12, 10, 16, 18, 10, 50, 40, 40])]:
        for i, w in enumerate(anchos):
            ws.column_dimensions[openpyxl.utils.get_column_letter(i + 1)].width = w
        for cell in ws[1]:
            cell.font, cell.fill = bold, head
        ws.freeze_panes = "C2" if ws in (ind, ft, fu) else "B2"
        ws.auto_filter.ref = ws.dimensions
    for row in ft.iter_rows(min_row=2, min_col=5, max_col=6):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    wb.save(salida)
    return ind.max_row - 1, ft.max_row - 1


if __name__ == "__main__":
    print(armar(sys.argv[1], sys.argv[2]))
