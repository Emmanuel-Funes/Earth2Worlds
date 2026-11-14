"""Fichas por variedad de los cultivares del INTA (banco_inta): condiciones de cultivo que publica cada fuente oficial.

Hernán (29/10/2026): "trae lo de todos los cultivos, va a ser de suma utilidad para la aplicación".
Formato largo: una fila por (cultivar, atributo, valor, fuente). Solo se carga lo que la fuente dice; si una
fuente no trae un atributo, no hay fila (la app lo muestra como "sin dato verificado").
construir_base lo llama para armar la tabla fichas_inta. Para revisar a mano (falla si un nombre transcripto
no está en el banco): python -m semillas.fichas <banco_inta.csv> <salida.csv>
"""
import csv, re, sys, unicodedata
from pathlib import Path

DATOS = Path(__file__).resolve().parent / "datos"
RAW = DATOS / "raw" / "fichas"
URL_SOJA = "https://www.argentina.gob.ar/sites/default/files/descripciones_morfologicas_soja_24-06-2026.xlsx"


def clave(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]", "", t)


def soja_inase(banco: list[dict]) -> list[dict]:
    """Descriptores que el obtentor declara a INASE al inscribir (planilla pública de INASE, 24/06/2026).

    Se cruza por número de registro. 0 o vacío = no informado. Las escalas 1-9 se traducen con la hoja de niveles.
    """
    import openpyxl
    wb = openpyxl.load_workbook(RAW / "inase_descripciones_morfologicas_soja_2026-06-24.xlsx", read_only=True)
    niveles, cur = {}, None
    for r in wb.worksheets[2].iter_rows(values_only=True):
        s = " ".join(str(x) for x in r if x is not None)
        m = re.match(r"Item: [\d.]+:? ?(.*)\((\S+)\)\s*$", s.strip())
        if m:
            cur = m.group(2); niveles[cur] = {}; continue
        m = re.match(r"\s*(\d+)\s*:\s*(\S.*?)\s*(\{.*\})?\s*$", s)
        if cur and m and m.group(2).strip():
            niveles[cur].setdefault(int(m.group(1)), m.group(2).strip())
    filas = list(wb.worksheets[0].iter_rows(values_only=True))
    hdr = [str(h).strip() if h else "" for h in filas[0]]
    por_num = {int(float(r[0])): dict(zip(hdr, r)) for r in filas[1:] if r[0] and str(r[0]).replace(".0", "").isdigit()}
    escala = lambda cod, v: niveles.get(cod, {}).get(int(v), str(int(v)))
    TXT = {"SUSCEPTIBL": "susceptible", "MEDISUSCEP": "moderadamente susceptible", "MEDIRESIST": "moderadamente resistente",
           "MED.RESIST": "moderadamente resistente", "RESISTENTE": "resistente", "TOLERANTE": "tolerante",
           "MED.TOLERA": "moderadamente tolerante", "DETERMINAD": "determinado", "SEMIDETERM": "semideterminado",
           "INDETERMIN": "indeterminado"}
    ENF = {"ENFBACPUST": "pústula bacteriana", "ENFBACTIZO": "tizón bacteriano", "ENFMIANTRA": "antracnosis",
           "ENFMIPODMT": "podredumbre de la vaina y el tallo", "ENFMIDOMIL": "mildiu", "ENFMIMANPA": "mancha marrón",
           "ENFMIMANPU": "mancha púrpura", "ENFMIFUSAR": "fusariosis", "ENFMIOJDRA": "mancha ojo de rana",
           "ENFMIPOCAR": "podredumbre carbonosa", "ENFMIPODCU": "podredumbre del cuello", "ENFMIPOHDT": "podredumbre húmeda del tallo",
           "ENFMIPOHDR": "podredumbre de la raíz", "ENFMICADTA": "cancro del tallo (caulivora)",
           "ENFMICACRO": "cancro del tallo (meridionalis)", "ENFMITIDTV": "tizón de tallo y vaina",
           "ENFMIPHYMG": "Phytophthora (podredumbre de raíz y tallo)", "ROYASIATIC": "roya asiática",
           "ENFVIMOSAM": "mosaico amarillo del poroto", "ENFVIMOSAI": "virus del mosaico de la soja",
           "ENFVIMOTSE": "moteado de la semilla", "RESNEMELIN": "nematodo Meloidogyne incognita",
           "RESNEHETER": "nematodo del quiste (Heterodera glycines)", "RESNEMELJA": "nematodo Meloidogyne javanica"}
    salida = []
    for b in banco:
        if b["cultivo"] != "Soja":
            continue
        d = por_num.get(int(b["cultivar_id"].split("-")[1]))
        if not d:
            continue
        add = lambda a, v: salida.append(dict(cultivar_id=b["cultivar_id"], cultivar=b["cultivar"], cultivo="Soja", atributo=a, valor=v,
                                              fuente="INASE, descripciones morfológicas de soja (declaradas al inscribir)", fuente_url=URL_SOJA))
        n = lambda k: float(d.get(k) or 0)
        if n("GRUPOMADUR"): add("grupo_madurez", escala("GRUPOMADUR", n("GRUPOMADUR")))
        if n("PLTIPCRECI"): add("tipo_crecimiento", TXT.get(escala("PLTIPCRECI", n("PLTIPCRECI")), escala("PLTIPCRECI", n("PLTIPCRECI"))))
        if n("PLALTUMADU"): add("altura_madurez_cm", str(int(n("PLALTUMADU"))))
        if n("DIAFLORPRI"): add("dias_siembra_a_floracion_primera", str(int(n("DIAFLORPRI"))))
        if n("DIAFLORSEG"): add("dias_siembra_a_floracion_segunda", str(int(n("DIAFLORSEG"))))
        if n("DIASMADPRI"): add("dias_siembra_a_madurez_primera", str(int(n("DIASMADPRI"))))
        if n("DIASMADSEG"): add("dias_siembra_a_madurez_segunda", str(int(n("DIASMADSEG"))))
        if n("EPOSIEMBRA"):
            meses = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
            mes = int(n("EPOSIEMBRA"))
            periodo = escala("EPOSIEMPER", n("EPOSIEMPER")).lower() if n("EPOSIEMPER") else ""
            add("epoca_siembra", (f"{periodo} de " if periodo else "") + (meses[mes] if 1 <= mes <= 12 else str(mes)))
        if n("SEMPESOMIL"): add("peso_mil_semillas_g", str(int(n("SEMPESOMIL"))))
        for cod, nombre in ENF.items():
            if n(cod): add(f"sanidad: {nombre}", TXT.get(escala(cod, n(cod)), escala(cod, n(cod))))
        for col, nombre in (("SEQUÍA", "sequía"), ("GLIFOSATO", "glifosato"), ("SULFONUREA", "sulfonilureas"),
                            ("TOLDICAMBA", "dicamba"), ("GLUFOSINATO DE AMONIO", "glufosinato"), ("2,4 D", "2,4-D")):
            if n(col):
                cod = next((k for k in niveles if clave(col) in clave(k)), col)
                add(f"tolerancia: {nombre}", TXT.get(escala(cod, n(col)), escala(cod, n(col))))
        if n("CARTECPROT"): add("proteina_pct", f"{n('CARTECPROT'):g}")
        if n("CARTECACEI"): add("aceite_pct", f"{n('CARTECACEI'):g}")
    return salida


def trigo_grupos_calidad(banco: list[dict]) -> list[dict]:
    """Grupo de calidad industrial y ciclo de cada trigo pan: planillas anuales del Comité de Cereales de Invierno
    (Comisión Nacional de Semillas, INASE), 2012 a 2025, pasadas a CSV. Se toma la planilla más reciente que lo nombra.
    """
    CIC = {"C": "corto", "I": "intermedio", "L": "largo", "CORTO": "corto", "INTERMEDIO": "intermedio", "LARGO": "largo"}
    idx = {clave(b["cultivar"]): b for b in banco if b["cultivo"] == "Trigo"}
    visto = {}
    for f in sorted((RAW / "trigo_grupos_calidad").glob("*.csv"), key=lambda f: re.search(r"(20\d\d)", f.name).group(1)):
        anio = re.search(r"(20\d\d)", f.name).group(1)
        filas = list(csv.reader(open(f, encoding="utf-8", errors="ignore")))
        cabezas = sorted({(j, f"grupo {m.group(1)}") for r in filas[:15] for j, x in enumerate(r)
                          if (m := re.search(r"GRUPO(?: DE CALIDAD)?\s*([123])\b", x.upper()))})
        for r in filas:
            usados = set()
            for j, x in enumerate(r):
                k = clave(x)
                b = idx.get(k) or idx.get(k.replace("BON", "BONAERENSE").replace("BONAERENSEAERENSE", "BONAERENSE"))
                if not b or b["cultivar_id"] in usados:
                    continue
                usados.add(b["cultivar_id"])  # la misma fila repite el nombre en "INASE declaradas"
                grupo = [c for c in cabezas if c[0] <= j + 1]
                ciclo = next((CIC[y.strip().upper()] for y in r[j + 1:j + 4] if y.strip().upper() in CIC), "")
                if not ciclo and anio != "2025":  # sin ciclo al lado es una lista al pie (testigos), no la tabla
                    continue
                previo = visto.get(b["cultivar_id"], {})
                visto[b["cultivar_id"]] = {"b": b, "anio": anio, "grupo": grupo[-1][1] if grupo else previo.get("grupo", ""),
                                           "ciclo": ciclo or previo.get("ciclo", "")}
    salida = []
    for v in visto.values():
        b = v["b"]
        for a, val in (("grupo_calidad_industrial", v["grupo"]), ("ciclo", v["ciclo"])):
            if val:
                salida.append(dict(cultivar_id=b["cultivar_id"], cultivar=b["cultivar"], cultivo="Trigo", atributo=a, valor=val,
                                   fuente=f"INASE, Comité de Cereales de Invierno: grupos de calidad de trigo pan ({v['anio']})",
                                   fuente_url="https://www.argentina.gob.ar/inase/red-de-ensayos-comparativos-de-variedades-de-trigo/grupo-de-calidad-de-trigo-pan"))
    return salida


def inase_catalogo(banco: list[dict]) -> list[dict]:
    """Lo que el propio catálogo de INASE trae en "características": grupo de reposo invernal de la alfalfa y
    grupo de madurez de la soja (solo si la planilla de descriptores no lo trae)."""
    crudo = DATOS / "raw" / "inase" / "catalogo_inase_2026-10-28.csv"
    por_num = {f"INASE-{r['numero']}": r for r in csv.DictReader(open(crudo, encoding="utf-8-sig"))}
    romanos = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"}
    salida = []
    for b in banco:
        r = por_num.get(b["cultivar_id"])
        if not r or b["cultivo"] not in ("Alfalfa", "Soja"):
            continue
        grupo = next((c.strip() for c in r["caracteristicas"].split("-") if c.strip() in romanos), "")
        if grupo:
            salida.append(dict(cultivar_id=b["cultivar_id"], cultivar=b["cultivar"], cultivo=b["cultivo"],
                               atributo="grupo_reposo_invernal" if b["cultivo"] == "Alfalfa" else "grupo_madurez", valor=grupo,
                               fuente="INASE, Catálogo Nacional de Cultivares (28/10/2026), campo características",
                               fuente_url="https://www.argentina.gob.ar/inase"))
    return salida


def transcriptas(banco: list[dict], estricto: bool = True) -> list[dict]:
    """Datos leídos a mano de fichas e informes del INTA e INASE (fichas_transcriptas.csv), cada uno con su fuente."""
    idx = {(b["cultivo"], clave(b["cultivar"])): b for b in banco}
    salida = []
    for r in csv.DictReader(open(DATOS / "fichas_transcriptas.csv", encoding="utf-8")):
        b = idx.get((r["cultivo"], clave(r["cultivar"])))
        if not b and not estricto:
            continue
        if not b:
            raise ValueError(f"'{r['cultivar']}' ({r['cultivo']}) no está en banco_inta")
        salida.append(dict(r, cultivar_id=b["cultivar_id"], cultivar=b["cultivar"]))
    return salida


FUENTE_REGISTRO = "INASE, Catálogo Nacional de Cultivares (28/10/2026): ficha básica del registro, sin datos de ensayo publicados"
PREFIJO_REGISTRO = "registro: "


def registro_basico(banco: list[dict], con_ficha: set[str]) -> list[dict]:
    """Ficha básica para las variedades sin ningún dato publicado (Hernán, 01/11/2026, eligió esta opción).

    Solo copia lo que dice el registro oficial de INASE (y el catálogo INTA para el licenciatario): especie,
    tipo de material, año de inscripción, propiedad, obtentor. No dice nada de cómo rinde ni dónde conviene:
    los atributos llevan el prefijo "registro: " para que la app los muestre aparte de las fichas con ensayos.
    """
    crudo = DATOS / "raw" / "inase" / "catalogo_inase_2026-10-28.csv"
    por_num = {f"INASE-{r['numero']}": r for r in csv.DictReader(open(crudo, encoding="utf-8-sig"))}
    salida = []
    for b in banco:
        r = por_num.get(b["cultivar_id"])
        if b["cultivar_id"] in con_ficha or not r:
            continue
        cond = (r["condicion_genetica"] or "").strip().lower()
        datos = [
            ("especie", f"{r['especie'].strip().capitalize()} ({r['nombre_cientifico'].strip()})"),
            ("tipo de material", cond.capitalize() if cond else ""),
            ("inscripto en el registro (RNC)", r["inscripcion_rnc"]),
            ("propiedad (RNPC)", f"protegida desde {r['inscripcion_rnpc']} hasta {r['validez_rnpc']}" if r["inscripcion_rnpc"] else "sin título de propiedad (RNPC) en el catálogo"),
            ("obtentor / solicitante", r["solicitante_rnc"].strip() or r["solicitante_rnpc"].strip()),
            ("licenciatario (catálogo INTA)", (b.get("licenciatario") or "").strip()),
            ("aviso", "Sin ensayos ni descripción publicados que se puedan leer; pedir datos al INTA"),
        ]
        for atributo, valor in datos:
            if valor:
                salida.append(dict(cultivar_id=b["cultivar_id"], cultivar=b["cultivar"], cultivo=b["cultivo"],
                                   atributo=PREFIJO_REGISTRO + atributo, valor=valor, fuente=FUENTE_REGISTRO,
                                   fuente_url="https://www.argentina.gob.ar/inase"))
    return salida


def unir(filas: list[dict]) -> list[dict]:
    """Un valor por (cultivar, atributo): la planilla de descriptores de soja gana al campo del catálogo."""
    vistos, salida = set(), []
    for f in filas:
        k = (f["cultivar_id"], f["atributo"])
        if k not in vistos:
            vistos.add(k); salida.append(f)
    return salida


COLUMNAS = ["cultivar_id", "cultivar", "cultivo", "atributo", "valor", "fuente", "fuente_url"]


def armar(banco: list[dict], estricto: bool = False) -> list[dict]:
    """Todas las fuentes juntas, en orden de prioridad (la primera que trae un atributo gana)."""
    filas = soja_inase(banco) + trigo_grupos_calidad(banco) + inase_catalogo(banco) + transcriptas(banco, estricto)
    filas += registro_basico(banco, {f["cultivar_id"] for f in filas})
    return [{k: f[k] for k in COLUMNAS} for f in unir(filas)]


if __name__ == "__main__":
    banco = list(csv.DictReader(open(sys.argv[1], encoding="utf-8-sig")))
    filas = armar(banco, estricto=True)
    with open(sys.argv[2], "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        w.writeheader(); w.writerows(filas)
    print(len(filas), len({f["cultivar_id"] for f in filas}))
