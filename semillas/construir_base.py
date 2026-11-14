"""Arma la base de fuentes de semillas de cultivos extensivos de Argentina (spec 049).

Entrada: la exportación CSV del Catálogo Nacional de Cultivares de INASE, guardada sin tocar.
Salida: tablas CSV (y un Excel si está openpyxl) separadas como pide el documento SSD:
cultivar, registro, evento OGM, obtentor, candidatos INTA, fuentes y controles de calidad.

Reglas: no se inventa ningún dato. Lo que la fuente no dice queda "sin dato verificado".
Una fila sin evento declarado NO es "convencional confirmada". Estar inscripto NO es tener stock.

Uso:
    python -m semillas.construir_base semillas/datos/raw/inase/catalogo_inase_2026-10-28.csv salida/ --fecha-corte 2026-10-28
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from semillas import ambiente, fichas, manejo
from semillas.fuentes import ENSAYOS_POR_PERFIL, FUENTES

SIN_DATO = "sin dato verificado"
COLUMNAS_INASE = ["numero", "cultivar", "especie", "condicion_genetica", "nombre_cientifico", "grupo",
                  "inscripcion_rnc", "inscripcion_rnpc", "validez_rnpc", "pais", "caracteristicas",
                  "evento_transgenico", "evento_transgenico_caracteristica", "solicitante_rnc",
                  "representante_rnc", "solicitante_rnpc", "representante_rnpc"]

# --- los 24 perfiles del documento SSD (sección 1.1) y las especies INASE que caen en cada uno ---
# (perfil, grupo SSD, especies INASE). Los tres porotos comparten especie: INASE no separa por color.
PERFILES = [
    ("Soja", "Granos y oleaginosas estivales", ["SOJA", "SOJA FORRAJERA"]),
    ("Maíz", "Granos y oleaginosas estivales", ["MAIZ", "MAIZ SUPERDULCE"]),
    ("Girasol", "Granos y oleaginosas estivales", ["GIRASOL", "GIRASOL CONFITURA", "GIRASOL HIBRIDO CON OFICIO JUDICIAL", "GIRASOL ORNAMENTAL"]),
    ("Sorgo", "Granos y oleaginosas estivales", ["SORGO", "SORGO AZUCARADO", "SORGO AZUCARADO SILERO", "SORGO DE ESCOBA", "SORGO SILERO", "SORGO SUDAN"]),
    ("Algodón", "Granos y oleaginosas estivales", ["ALGODONERO"]),
    ("Maní", "Granos y oleaginosas estivales", ["MANI"]),
    ("Arroz", "Granos y oleaginosas estivales", ["ARROZ"]),
    ("Trigo", "Cereales de invierno", ["TRIGO PAN", "TRIGO FIDEOS O CANDEAL", "TRIGO FIDEOS", "TRIGO BLANDO-GALLETITERO O SOFT", "TRIGO ESPELTA"]),
    ("Cebada", "Cereales de invierno", ["CEBADA CERVECERA", "CEBADA FORRAJERA"]),
    ("Avena", "Cereales de invierno", ["AVENA", "AVENA BLANCA", "AVENA AMARILLA", "AVENA SATIVA", "AVENA STRIGOSA"]),
    ("Centeno", "Cereales de invierno", ["CENTENO"]),
    ("Triticale", "Cereales de invierno", ["TRITICALE", "TRITICALE-PROHIBICION DE CONTRATAR"]),
    ("Garbanzo", "Legumbres", ["GARBANZO"]),
    ("Arveja", "Legumbres", ["ARVEJA"]),
    ("Porotos (negro, alubia, colorado)", "Legumbres", ["POROTO", "POROTO CHAUCHA", "POROTO MUNG"]),
    ("Lenteja", "Legumbres", ["LENTEJA"]),
    ("Lupino", "Legumbres", ["LUPINO AMARILLO"]),
    ("Colza/Canola", "Oleaginosas e industriales alternativas", ["COLZA", "COLZA-CANOLA", "CANOLA"]),
    ("Cártamo", "Oleaginosas e industriales alternativas", ["CARTAMO"]),
    ("Lino", "Oleaginosas e industriales alternativas", ["LINO"]),
    ("Caña de azúcar", "Industriales y tubérculos", ["CAÑA DE AZUCAR", "CAÑA DE AZÚCAR"]),
    ("Papa", "Industriales y tubérculos", ["PAPA"]),
]

# extensivos que no están entre los 24 perfiles y cuya cosecha se vende (Hernán, 28/10/2026: nada de pasturas
# ni forrajes de consumo en el campo; la alfalfa queda porque el motor la evalúa y el fardo y la semilla se venden)
COMPLEMENTARIOS = {  # especie INASE: (perfil, uso en la rotación)
    "ALFALFA": ("Alfalfa", "Pastura en rotación"),
    "VICIA FABA L.": ("Haba", "Legumbre / forraje"), "HABA": ("Haba", "Legumbre / forraje"),
    "CAUPI": ("Caupí", "Legumbre / forraje"),
    "CAMELINA SATIVA": ("Camelina", "Oleaginosa alternativa"), "MOSTAZA ETIOPE": ("Mostazas (carinata, juncea)", "Oleaginosa alternativa"),
    "MOSTAZA INDIA": ("Mostazas (carinata, juncea)", "Oleaginosa alternativa"),
    "SESAMO": ("Sésamo", "Oleaginosa alternativa"),
    "CHIA": ("Chía", "Granos especiales"), "QUINOA": ("Quinoa", "Granos especiales"),
    "TRIGO SARRACENO": ("Trigo sarraceno", "Granos especiales"), "MIJO": ("Mijo", "Granos especiales"),
    "ALPISTE": ("Alpiste", "Granos especiales"),
    "CAÑAMO": ("Cáñamo industrial", "Industrial (régimen legal propio)"),
    "AMARANTO": ("Amaranto", "Granos especiales"),
    "MOSTAZA": ("Mostazas (carinata, juncea)", "Oleaginosa alternativa"), "TARTAGO": ("Tártago", "Oleaginosa industrial"),
}

NOMBRE_CIENTIFICO_PERFIL = {
    "Soja": "Glycine max", "Maíz": "Zea mays", "Girasol": "Helianthus annuus", "Sorgo": "Sorghum spp.",
    "Algodón": "Gossypium hirsutum", "Maní": "Arachis hypogaea", "Arroz": "Oryza sativa", "Trigo": "Triticum aestivum / T. durum",
    "Cebada": "Hordeum vulgare", "Avena": "Avena sativa / A. byzantina / A. strigosa", "Centeno": "Secale cereale",
    "Triticale": "× Triticosecale", "Garbanzo": "Cicer arietinum", "Arveja": "Pisum sativum",
    "Porotos (negro, alubia, colorado)": "Phaseolus vulgaris", "Lenteja": "Lens culinaris",
    "Lupino": "Lupinus albus / L. luteus / L. angustifolius", "Colza/Canola": "Brassica napus",
    "Cártamo": "Carthamus tinctorius", "Lino": "Linum usitatissimum", "Caña de azúcar": "Saccharum spp.",
    "Papa": "Solanum tuberosum",
}

# instantánea del documento SSD, sección 4.6 (lista oficial consultada el 25/10/2026)
OGM_SEGUN_LISTADO_OFICIAL = {
    "Soja": "Sí", "Maíz": "Sí", "Algodón": "Sí", "Trigo": "Sí (HB4, IND-ØØ412-7)", "Papa": "Sí (TIC-AR233-5)",
}

# materiales que el documento SSD (sección 14.3) toma de páginas de INTA/INTeA, a conciliar con INASE
CANDIDATOS_INTA = {
    "Soja": ["INTA Paraná 5100", "INTA Paraná 6301", "INTA Paraná 6000", "Rosana INTA 3.9 STS", "MJ 42 STS"],
    "Maíz": ["Leales 25 Plus", "Bautista INTA"],
    "Girasol": ["Calchaquí INTA", "Chané CL INTA", "Febo 817 CL INTA", "SuryaINTA"],
    "Sorgo": ["Nehuen INTA Peman", "Silero INTA"],
    "Algodón": ["Guazuncho 4 INTA BGRR", "Guaraní INTA BGRR", "Porá 3 INTA BGRR", "Guazuncho 2000", "DP 1238 BGRR", "Nuopal RR"],
    "Maní": ["Florman INTA", "Manfredi 393 INTA", "ASEM 447 INTA", "ASEM 485 INTA", "ASEM 484 INTA", "ASEM 505 INTA",
             "Pepe ASEM INTA", "Víctor ASEM INTA", "ASEM 353 INTA", "ASEM 400 INTA", "ASEM 450-RS INTA",
             "ASEM 451-RC INTA", "ASEM 452-RC INTA", "Granoleico"],
    "Arroz": ["Camba INTA Proarroz", "Gurí INTA CL", "Puitá INTA CL", "Ñu Poty INTA CL", "Memby Porá", "Angirú INTA CL",
              "Kira INTA", "Alfredo INTA", "Vicente INTA"],
    "Trigo": ["BioINTA 1005", "BioINTA 1006", "BioINTA 1007", "BioINTA 2006", "BioINTA 3005", "BioINTA 3006",
              "MS INTA Bonaerense 514", "MS INTA 615", "MS INTA 415", "MS INTA 215", "MS INTA 815", "MS INTA 116"],
    "Cebada": ["7302 INTA", "Josefina INTA", "Lucía INTA", "Beatriz INTA", "Huilen INTA", "Rayen INTA", "Silera INTA",
               "Guadalupe INTA", "Trinidad INTA", "Nélida INTA", "Maricela INTA", "Nacira INTA"],
    "Avena": ["Carlota INTA", "Elizabet INTA", "Graciela INTA", "Julieta INTA", "Lucía INTA", "Marita INTA",
              "Violeta INTA", "Florencia INTA", "Liliana INTA"],
    "Centeno": ["Don Ewald INTA", "Don José INTA", "Don Norberto INTA", "Emilio INTA", "Fausto INTA", "Quehue INTA"],
    "Triticale": ["Espinillo INTA"],
    "Garbanzo": ["Felipe UNC INTA", "Kiara UNC INTA", "Norteño"],
    "Arveja": ["Primogénita FCA-INTA"],
    "Porotos (negro, alubia, colorado)": ["CEGRO INTA", "Anahí INTA", "Escarlata INTA", "Leales 15 INTA", "Leales 17 INTA",
                                          "Leales 22 INTA", "Leales 24 INTA", "Leales B40 INTA", "Leales C1 INTA",
                                          "Leales CR5 INTA", "Leales R4 INTA"],
    "Lenteja": ["Silvina", "Turca"],
    "Colza/Canola": ["Macacha INTA"],
    "Lino": ["Aguará INTA", "Caburé INTA", "Panambí INTA"],
    "Caña de azúcar": ["INTA TUC 03-663", "INTA TUC 03-617", "INTA CP 98-828", "L 91-281", "INTA NA 91-209", "INTA NA 89-686"],
    "Papa": ["Innovator", "Sagitta", "Kennebec", "Daisy", "Chieftain", "Shepody", "Russet Burbank", "Asterix",
             "Atlantic", "Cherie", "OLI INTA"],
}

ROMANOS = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"}
# códigos del campo "caracteristicas" de INASE. Solo se decodifican los que el propio archivo deja claros.
CODIGOS = {
    "TR": "transgénico declarado (coincide con evento declarado)",
    "CL": "Clearfield: tolerancia a imidazolinonas por mejoramiento, no es evento OGM",
    "AO": "alto oleico",
    "MO": "probablemente medio oleico (verificar en INASE)",
    "TT": "probablemente tolerancia a triazinas (verificar en INASE)",
}


def normalizar(texto: str) -> str:
    """Clave de búsqueda: mayúsculas, sin tildes, Ø→0, solo letras y números separados por un espacio."""
    t = unicodedata.normalize("NFKD", texto.replace("Ø", "0").replace("ø", "0").replace("Ñ", "N").replace("ñ", "n"))
    t = "".join(c for c in t if not unicodedata.combining(c)).upper()
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", t).split())


def es_inta(solicitante: str) -> bool:
    """INASE escribe al INTA de varias formas: 'INSTITUTO NACIONAL DE TECNOLOGIA AGROPECUARIA', 'INST. NAC.TEC.
    AGROPECUARIA', 'INTA E.E.A.SAN PEDRO'."""
    n = normalizar(solicitante)
    return bool(re.search(r"\bINTA\b|TEC(NOLOGIA)? AGROPECUARIA", n))


ENTES_PUBLICOS = (
    (r"OBISPO COLOMBRES|\bEEAOC\b", "EEAOC (Tucumán)"),
    (r"CHACRA EXPERIMENTAL AGRICOLA SANTA ROSA", "Chacra Experimental Agrícola Santa Rosa (Tucumán)"),
    (r"UNIV(ERSIDAD)? DE BUENOS AIRES|UNIVERSIDAD NACIONAL|\bFAC(ULTAD)? (DE )?(CIENCIAS )?AGRARIAS?\b|FACULTAD DE AGRONOMIA|\bUN(R|C|LP|NE|S|SL|CUYO|CPBA|RC)\b",
     "Universidad nacional"),
    (r"CONSEJO NACIONAL DE INVESTIGACIONES|\bCONICET\b", "CONICET"),
    (r"MINISTERIO DE DESARROLLO AGRARIO|MINISTERIO DE (LA )?PRODUCCION", "Ministerio provincial"),
)


def ente_publico(solicitante: str) -> str:
    """Hernán (03/11/2026): entran al banco los entes públicos nacionales y provinciales (EEAOC, universidades
    nacionales, CONICET, chacras y ministerios provinciales), además del INTA. Devuelve el nombre del ente o ''."""
    n = normalizar(solicitante)
    for patron, nombre in ENTES_PUBLICOS:
        if re.search(patron, n):
            return nombre
    return ""


def eventos_de(campo: str) -> list[str]:
    """Separa una combinación declarada ('A x B × C y B x A') en códigos de evento únicos, en orden."""
    vistos = []
    for parte in re.split(r"\s+(?:x|×|X|y)\s+", campo.strip()):
        codigo = parte.strip().replace("Ø", "0").replace("ø", "0").upper()
        codigo = re.sub(r"^([A-Z]{3})(\d)", r"\1-\2", codigo)  # 'DAS4Ø278-9' → 'DAS-40278-9'
        if codigo and codigo not in vistos:
            vistos.append(codigo)
    return vistos


def clasificar(especie: str, grupo: str, condicion: str) -> tuple[str, str, str]:
    """Devuelve (subtipo, destino, extensivo) a partir de lo que dice INASE, sin adivinar por el nombre."""
    c = condicion.upper()
    if especie == "MAIZ":
        if grupo == "HT":
            if "PISINGALLO" in c:
                return "Maíz pisingallo", "Grano especial", "SI"
            return "Maíz choclo/dulce", "Hortícola", "NO"
        if grupo == "FO":
            return "Maíz forrajero", "Forraje / silo", "SI"
        if "CHOCLO" in c:
            return "Maíz choclo/dulce", "Hortícola", "NO"
        if "POLINIZADOR" in c:
            return "Maíz polinizador", "Línea para producción de semilla", "REVISAR"
        return "Maíz granífero", "Grano", "SI"
    if especie == "MAIZ SUPERDULCE":
        return "Maíz choclo/dulce", "Hortícola", "NO"
    if especie == "SORGO":
        if "FORRAJ" in c or grupo == "FO":
            return "Sorgo forrajero", "Forraje", "SI"
        return "Sorgo granífero", "Grano", "SI"
    especiales = {
        "SORGO SILERO": ("Sorgo silero", "Silo", "SI"), "SORGO AZUCARADO": ("Sorgo azucarado", "Forraje / bioenergía", "SI"),
        "SORGO AZUCARADO SILERO": ("Sorgo azucarado silero", "Silo", "SI"), "SORGO SUDAN": ("Sorgo sudán", "Forraje", "SI"),
        "SORGO DE ESCOBA": ("Sorgo de escoba", "Industrial (escobas)", "SI"),
        "GIRASOL": ("Girasol aceitero", "Aceite", "SI"), "GIRASOL CONFITURA": ("Girasol confitero", "Confitería", "SI"),
        "GIRASOL HIBRIDO CON OFICIO JUDICIAL": ("Girasol con oficio judicial", "Aceite", "REVISAR"),
        "GIRASOL ORNAMENTAL": ("Girasol ornamental", "Ornamental", "NO"),
        "SOJA": ("Soja", "Grano", "SI"), "SOJA FORRAJERA": ("Soja forrajera", "Forraje", "SI"),
        "TRIGO PAN": ("Trigo pan", "Grano (panificación)", "SI"), "TRIGO FIDEOS O CANDEAL": ("Trigo candeal", "Grano (fideos)", "SI"),
        "TRIGO FIDEOS": ("Trigo candeal", "Grano (fideos)", "SI"),
        "TRIGO BLANDO-GALLETITERO O SOFT": ("Trigo blando", "Grano (galletitas)", "SI"),
        "TRIGO ESPELTA": ("Trigo espelta", "Grano especial", "SI"),
        "CEBADA CERVECERA": ("Cebada cervecera", "Grano (maltería)", "SI"), "CEBADA FORRAJERA": ("Cebada forrajera", "Forraje / grano forrajero", "SI"),
        "AVENA": ("Avena", SIN_DATO, "SI"), "AVENA BLANCA": ("Avena blanca", "Grano / forraje", "SI"),
        "AVENA AMARILLA": ("Avena amarilla", "Forraje / grano", "SI"), "AVENA SATIVA": ("Avena forrajera", "Forraje", "SI"),
        "AVENA STRIGOSA": ("Avena negra (strigosa)", "Forraje / cobertura", "SI"),
        "TRITICALE-PROHIBICION DE CONTRATAR": ("Triticale con prohibición de contratar", SIN_DATO, "REVISAR"),
        "POROTO": ("Poroto seco (tipo comercial sin dato verificado)", "Grano", "SI"),
        "POROTO CHAUCHA": ("Poroto chaucha", "Hortícola", "NO"), "POROTO MUNG": ("Poroto mung (Vigna radiata)", "Grano", "SI"),
        "CANOLA": ("Canola", SIN_DATO, "SI" if grupo == "OL" else "REVISAR"),
        "PAPA": ("Papa", "Tubérculo (semilla = tubérculo)", "SI"),
    }
    if especie in especiales:
        return especiales[especie]
    return "", SIN_DATO, "SI"  # sin subtipo propio: quien llama usa el nombre del perfil


def tipo_material(condicion: str) -> str:
    c = condicion.upper()
    if "HIBRID" in c or "LINEAS" in c:
        return "Híbrido"
    if "VARIEDAD" in c:
        return "Variedad"
    if "LINEA" in c:
        return "Línea (parental de híbridos)"
    return SIN_DATO


def alerta_legal(especie: str, condicion: str) -> str:
    if "OFICIO JUDICIAL" in especie:
        return "Registro alcanzado por oficio judicial: consultar INASE antes de usar"
    if "PROHIBICION DE CONTRATAR" in especie:
        return "Registro con prohibición de contratar: consultar INASE antes de usar"
    if condicion.upper().startswith("COMERCIALIZACI"):
        return condicion
    return ""


def leer(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f)
        faltan = [c for c in COLUMNAS_INASE if c not in (lector.fieldnames or [])]
        if faltan:
            raise ValueError(f"El CSV de INASE cambió de formato; faltan columnas: {faltan}")
        return list(lector)


OFERTA = Path(__file__).resolve().parent / "datos" / "oferta_comercial_2026_27.csv"
GIRASOL = Path(__file__).resolve().parent / "datos" / "girasol_inta_asagir_2023_2026"  # red nacional INTA-ASAGIR
MAIZ = Path(__file__).resolve().parent / "datos" / "maiz_inta_2024_2026"  # redes INTA Marcos Juárez y norte de Buenos Aires
SORGO = Path(__file__).resolve().parent / "datos" / "sorgo_inta_manfredi_2024_25"  # ensayo INTA EEA Manfredi
SAN_LUIS = Path(__file__).resolve().parent / "datos" / "inta_san_luis_2025_26"  # ensayos INTA EEA San Luis + UNSL en la provincia
RET = Path(__file__).resolve().parent / "datos" / "ret_trigo_2018_2026"  # red nacional de trigo (INASE), 8 campañas
RECSO = Path(__file__).resolve().parent / "datos" / "recso_soja_2025_26"  # prefijo de los tres CSV de la red nacional de soja
# planilla pública detrás de https://www.argentina.gob.ar/inta/variedades, guardada sin los contactos personales
CATALOGO_INTA = Path(__file__).resolve().parent / "datos" / "raw" / "inta" / "catalogo_inta_2026-10-28.csv"
GRUPOS_INTA_EXTENSIVOS = {"Cereales de invierno", "Cereales de verano", "Oleaginosas", "Legumbres", "Industriales", "Forrajeras"}


def construir(ruta_csv: Path, fecha_corte: date | None = None, ruta_oferta: Path | None = OFERTA,
              ruta_catalogo_inta: Path | None = CATALOGO_INTA, prefijo_recso: Path | None = RECSO,
              prefijo_ret: Path | None = RET, prefijo_girasol: Path | None = GIRASOL,
              prefijo_maiz: Path | None = MAIZ, prefijo_sorgo: Path | None = SORGO,
              prefijo_san_luis: Path | None = SAN_LUIS) -> dict[str, list[dict]]:
    filas = leer(ruta_csv)
    especie_a_perfil = {e: (p, g) for p, g, especies in PERFILES for e in especies}
    nota_fecha = "Fecha de descarga del archivo, indicada al construir la base."
    if fecha_corte is None:  # la fecha de inscripción más reciente del archivo: la exportación no es anterior
        fecha_corte = max(date.fromisoformat(f["inscripcion_rnc"]) for f in filas if f["inscripcion_rnc"])
        nota_fecha = ("Fecha de inscripción RNC más reciente del archivo; la exportación no es anterior. "
                      "La fecha exacta de descarga no consta.")

    cultivares, cultivar_evento = [], []
    for f in filas:
        especie = f["especie"].strip()
        if especie in especie_a_perfil:
            perfil, grupo_ssd = especie_a_perfil[especie]
            alcance = "24 perfiles SSD"
        elif especie in COMPLEMENTARIOS:
            nombre, grupo_ssd = COMPLEMENTARIOS[especie]
            perfil = f"Complementario: {nombre}"
            alcance = "Complementario"
        else:
            continue
        subtipo, destino, extensivo = clasificar(especie, f["grupo"], f["condicion_genetica"])
        if not f["inscripcion_rnc"].strip() and extensivo == "SI":
            extensivo = "REVISAR"  # solo RNPC: material protegido que no se vende como semilla (casi siempre una línea)
        if not subtipo:
            subtipo = perfil.removeprefix("Complementario: ")
        codigos = [c.strip() for c in f["caracteristicas"].split("-") if c.strip()]
        eventos = eventos_de(f["evento_transgenico"]) if f["evento_transgenico"].strip() else []
        validez = f["validez_rnpc"].strip()
        if not f["inscripcion_rnpc"].strip():
            rnpc = "Sin inscripción RNPC en el registro"
        elif validez and date.fromisoformat(validez) >= fecha_corte:
            rnpc = "RNPC_PROTEGIDO (vigente al corte)"
        else:
            rnpc = "Protección RNPC vencida al corte"
        cultivar_id = f"INASE-{f['numero']}"
        cultivares.append({
            "cultivar_id": cultivar_id, **{c: f[c] for c in COLUMNAS_INASE},
            "alcance": alcance, "perfil_ssd": perfil, "grupo_ssd": grupo_ssd, "subtipo": subtipo,
            "destino": destino, "extensivo": extensivo, "tipo_material": tipo_material(f["condicion_genetica"]),
            "grupo_madurez": next((c for c in codigos if c in ROMANOS), "") if especie.startswith("SOJA") or especie == "ALFALFA" else "",
            "tecnologias_no_ogm": "; ".join(CODIGOS[c] for c in codigos if c in CODIGOS and c != "TR"),
            "estado_ogm": "OGM: evento declarado en INASE" if eventos else "Sin evento declarado en este registro",
            "eventos_ogm": " + ".join(eventos),
            "obtentor_inta": "SI" if es_inta(f["solicitante_rnc"] + " " + f["solicitante_rnpc"]) else "NO",
            "estado_registral": ("RNC_INSCRIPTO (figura en el catálogo exportado)" if f["inscripcion_rnc"].strip()
                                 else "SOLO_RNPC: protegido como propiedad, sin inscripción en el RNC (no habilitado para vender semilla)"),
            "estado_rnpc": rnpc,
            "alerta_legal": alerta_legal(especie, f["condicion_genetica"]),
            "disponibilidad_comercial": SIN_DATO, "precio_semilla": SIN_DATO, "ensayos_vinculados": SIN_DATO,
            "nombre_busqueda": normalizar(f["cultivar"]), "fuente_id": "INASE_CNC", "fecha_corte": fecha_corte.isoformat(),
        })
        for orden, ev in enumerate(eventos, 1):
            cultivar_evento.append({"cultivar_id": cultivar_id, "cultivar": f["cultivar"], "especie": especie,
                                    "evento": ev, "orden_en_combinacion": orden, "fuente_id": "INASE_CNC"})

    tablas = {
        "cultivares": cultivares,
        "cultivar_evento": cultivar_evento,
        "eventos_ogm": _eventos(cultivares),
        "perfiles": _perfiles(cultivares),
        "obtentores": _obtentores(cultivares),
        "candidatos_inta": _candidatos_inta(cultivares),
        "fuentes": [dict(f, verificada_en_linea="NO") for f in FUENTES],
        "ensayos_por_perfil": [{"perfil_ssd": p, "fuente_id": fid,
                                "estado": "INGERIDA" if {"RECSO": prefijo_recso, "RET_TRIGO": prefijo_ret,
                                                          "GIRASOL_INTA_ASAGIR": prefijo_girasol,
                                                          "INTA_MJ_MAIZ": prefijo_maiz, "INTA_BN_MAIZ": prefijo_maiz,
                                                          "INTA_MANFREDI_SORGO": prefijo_sorgo,
                                                          "INTA_SAN_LUIS_2025_26": prefijo_san_luis}.get(fid) else "LOCALIZADA_NO_INGERIDA"}
                               for p, ids in ENSAYOS_POR_PERFIL.items() for fid in ids],
        "control_calidad": _controles(cultivares),
        **_inta(cultivares, ruta_catalogo_inta),
        "oferta_comercial": _oferta(cultivares, ruta_oferta) if ruta_oferta and ruta_oferta.exists() else [],
        **_recso(cultivares, prefijo_recso),
        **_ret(cultivares, prefijo_ret),
        **_girasol(cultivares, prefijo_girasol),
        **_maiz(cultivares, prefijo_maiz),
        **_sorgo(cultivares, prefijo_sorgo),
        **_san_luis(cultivares, prefijo_san_luis),
        "_meta": [{"fecha_corte": fecha_corte.isoformat(), "filas_fuente": len(filas), "nota_fecha": nota_fecha}],
    }
    tablas["banco_inta"] = _banco_inta(filas, especie_a_perfil, ruta_catalogo_inta, fecha_corte, tablas)
    tablas["fichas_inta"] = fichas.armar(tablas["banco_inta"])
    tablas["manejo_cultivos"] = manejo.armar([f["cultivo"] for f in tablas["banco_inta"]])
    tablas["requerimientos_ambientales"] = ambiente.armar()
    return tablas


def _eventos(cultivares: list[dict]) -> list[dict]:
    """Un renglón por evento único, con el rasgo que INASE le asigna cuando aparece solo."""
    por_evento = defaultdict(lambda: {"especies": set(), "cultivares": 0, "solo": Counter(), "combinaciones": set()})
    for c in cultivares:
        if not c["eventos_ogm"]:
            continue
        evs = c["eventos_ogm"].split(" + ")
        for ev in evs:
            d = por_evento[ev]
            d["especies"].add(c["especie"])
            d["cultivares"] += 1
            if len(evs) == 1:
                d["solo"][c["evento_transgenico_caracteristica"].strip()] += 1
            else:
                d["combinaciones"].add(c["eventos_ogm"])
    salida = []
    for ev, d in sorted(por_evento.items()):
        salida.append({
            "evento": ev, "especies": ", ".join(sorted(d["especies"])), "cultivares_que_lo_declaran": d["cultivares"],
            "rasgo_segun_inase": d["solo"].most_common(1)[0][0] if d["solo"] else "solo aparece apilado: ver combinaciones",
            "combinaciones_en_que_aparece": len(d["combinaciones"]),
            "autorizacion_comercial": "pendiente de contrastar con SAGYP_OGM_EVENTOS",
            "fuente_id": "INASE_CNC",
        })
    return salida


def _perfiles(cultivares: list[dict]) -> list[dict]:
    por_perfil = defaultdict(list)
    for c in cultivares:
        por_perfil[c["perfil_ssd"]].append(c)
    inta = {p: len(n) for p, n in CANDIDATOS_INTA.items()}
    salida = []
    orden = [p for p, _, _ in PERFILES] + sorted(p for p in por_perfil if p.startswith("Complementario"))
    for p in orden:
        filas = por_perfil.get(p, [])
        ext = [c for c in filas if c["extensivo"] == "SI"]
        fechas = sorted(c["inscripcion_rnc"] for c in filas if c["inscripcion_rnc"])
        salida.append({
            "perfil_ssd": p, "grupo_ssd": filas[0]["grupo_ssd"] if filas else "",
            "nombre_cientifico": NOMBRE_CIENTIFICO_PERFIL.get(p, filas[0]["nombre_cientifico"] if filas else ""),
            "especies_inase": ", ".join(sorted({c["especie"] for c in filas})),
            "registros_inase": len(filas), "registros_extensivos": len(ext),
            "hibridos": sum(c["tipo_material"] == "Híbrido" for c in ext),
            "variedades": sum(c["tipo_material"] == "Variedad" for c in ext),
            "con_evento_ogm": sum(bool(c["eventos_ogm"]) for c in ext),
            "rnpc_vigente": sum(c["estado_rnpc"].startswith("RNPC_PROTEGIDO") for c in ext),
            "obtenidos_por_inta": sum(c["obtentor_inta"] == "SI" for c in ext),
            "inscriptos_2022_2026": sum(c["inscripcion_rnc"] >= "2022-01-01" for c in ext),
            "primera_inscripcion": fechas[0] if fechas else "", "ultima_inscripcion": fechas[-1] if fechas else "",
            "obtentores_distintos": len({c["solicitante_rnc"] for c in ext if c["solicitante_rnc"]}),
            "ogm_segun_listado_oficial": OGM_SEGUN_LISTADO_OFICIAL.get(p, "No se identificó evento comercial" if not p.startswith("Complementario") else SIN_DATO),
            "candidatos_inta_documentados": inta.get(p, 0),
            "con_disponibilidad_comercial_verificada": 0,
            "fuentes_de_ensayos": ", ".join(ENSAYOS_POR_PERFIL.get(p, [])) or "ninguna localizada todavía",
            "nota": ("INASE no separa poroto negro, alubia y colorado: el tipo comercial queda sin dato verificado"
                     if p.startswith("Porotos") else ""),
        })
    return salida


def _obtentores(cultivares: list[dict]) -> list[dict]:
    cuenta = Counter((c["perfil_ssd"], c["solicitante_rnc"] or SIN_DATO) for c in cultivares if c["extensivo"] == "SI")
    ultimos = Counter((c["perfil_ssd"], c["solicitante_rnc"] or SIN_DATO) for c in cultivares
                      if c["extensivo"] == "SI" and c["inscripcion_rnc"] >= "2022-01-01")
    return [{"perfil_ssd": p, "obtentor_solicitante_rnc": o, "cultivares": n, "inscriptos_2022_2026": ultimos[(p, o)]}
            for (p, o), n in sorted(cuenta.items(), key=lambda x: (x[0][0], -x[1]))]


def _candidatos_inta(cultivares: list[dict]) -> list[dict]:
    """Concilia los nombres del documento SSD con INASE: exacto normalizado, si no a revisión. Nunca fusiona solo."""
    por_perfil = defaultdict(list)
    for c in cultivares:
        por_perfil[c["perfil_ssd"]].append(c)
    salida = []
    for perfil, nombres in CANDIDATOS_INTA.items():
        filas = por_perfil[perfil]
        for nombre in nombres:
            clave = normalizar(re.sub(r"(?<=[a-z])INTA\b", " INTA", nombre))  # 'SuryaINTA' → 'Surya INTA'
            exactos = [c for c in filas if c["nombre_busqueda"] == clave]
            sin_espacios = [c for c in filas if c["nombre_busqueda"].replace(" ", "") == clave.replace(" ", "")]
            palabras = [w for w in clave.split() if w not in {"INTA", "UNC", "FCA"} and len(w) > 2]
            parecidos = [c for c in filas if palabras and all(w in c["nombre_busqueda"].split() for w in palabras)]
            if len(exactos) == 1:
                estado, encontrados = "EXACTO", exactos
            elif len(exactos) > 1:
                estado, encontrados = "CONFLICTO (varios registros con el mismo nombre)", exactos
            elif sin_espacios:
                estado, encontrados = "EXACTO (difiere solo en espacios o signos)", sin_espacios
            elif parecidos:
                estado, encontrados = "PARA_REVISION (nombre parecido, no se vincula)", parecidos[:5]
            else:
                estado, encontrados = "NO_ENCONTRADO en el catálogo exportado", []
            salida.append({
                "perfil_ssd": perfil, "nombre_en_documento_ssd": nombre, "estado_conciliacion": estado,
                "cultivar_id_inase": "; ".join(c["cultivar_id"] for c in encontrados),
                "nombre_oficial_inase": "; ".join(c["cultivar"] for c in encontrados),
                "solicitante_rnc": "; ".join(sorted({c["solicitante_rnc"] for c in encontrados})),
                "inscripcion_rnc": "; ".join(c["inscripcion_rnc"] for c in encontrados),
                "estado_rnpc": "; ".join(c["estado_rnpc"] for c in encontrados),
                "fuente_del_nombre": "Documento SSD v1.4, sección 14.3 (páginas INTA/INTeA)",
            })
    return salida


def vinculo_inta(c: dict) -> str:
    """Cómo se vincula el cultivar con el INTA, según lo que dice el registro. Vacío si no hay vínculo."""
    if c["obtentor_inta"] == "SI":
        return "Solicitante INTA"
    sol = normalizar(c["solicitante_rnc"])
    if "BARROW" in sol:
        return "Chacra Experimental Integrada Barrow (convenio con INTA)"
    if re.search(r"\bINTA\b", c["nombre_busqueda"]):
        return ("INTA en la denominación; sin solicitante en el registro" if not sol
                else f"INTA en la denominación; solicitante: {c['solicitante_rnc']}")
    return ""


def _misma_especie(especie_catalogo: str, c: dict) -> bool:
    """'Trigo pan' sirve para TRIGO PAN y TRIGO FIDEOS; 'Brassica napus L.' para colza; 'Maíz variedad' para MAIZ."""
    primera = normalizar(especie_catalogo).split()[0] if especie_catalogo.strip() else ""
    primera = {"BRASSICA": "COLZA", "FIDEO": "TRIGO"}.get(primera, primera)
    return bool(primera) and (primera in normalizar(c["especie"]) or primera in normalizar(c["perfil_ssd"]))


def _sin_siglas(nombre: str) -> str:
    return " ".join(w for w in normalizar(nombre).split() if w not in {"INTA", "FCA", "MDA", "UNC", "BONAERENSE"})


def _inta(cultivares: list[dict], ruta_catalogo: Path | None) -> dict[str, list[dict]]:
    """Cultivares extensivos del INTA (o con INTA en el nombre), del más nuevo al más viejo, por cultivo.

    Si está la planilla del catálogo de variedades del INTA, le suma la unidad que lo obtuvo, el tipo de
    licencia y el licenciatario (quien multiplica y vende la semilla). Lo que no cruza va a revisión.
    """
    catalogo = []
    if ruta_catalogo and ruta_catalogo.exists():
        with ruta_catalogo.open(encoding="utf-8-sig", newline="") as f:
            for v in csv.DictReader(f):  # la planilla repite filas: se dejan las distintas
                if v not in catalogo:
                    catalogo.append(v)
    usados = set()
    salida = []
    for c in cultivares:
        if c["extensivo"] != "SI":
            continue
        clave = c["nombre_busqueda"]
        candidatos = [i for i, v in enumerate(catalogo) if _misma_especie(v["especie"], c)]
        exactos = [i for i in candidatos if normalizar(catalogo[i]["variedad"]).replace(" ", "") == clave.replace(" ", "")]
        parecidos = [i for i in candidatos if _sin_siglas(catalogo[i]["variedad"]) == _sin_siglas(c["cultivar"])] if not exactos else []
        elegidos = exactos or parecidos
        vinculo = vinculo_inta(c) or ("Variedad del catálogo INTA inscripta por otro solicitante (licenciatario)" if exactos else "")
        if not vinculo:
            continue
        fila = {k: c[k] for k in ["cultivar_id", "perfil_ssd", "subtipo", "cultivar", "especie", "tipo_material",
                                  "grupo_madurez", "tecnologias_no_ogm", "estado_ogm", "eventos_ogm",
                                  "inscripcion_rnc", "estado_rnpc", "validez_rnpc", "solicitante_rnc",
                                  "representante_rnc", "alerta_legal"]} | {"vinculo_inta": vinculo}
        if not catalogo:
            estado = "catálogo INTA no cargado"
        elif len({_sin_siglas(catalogo[i]["variedad"]) for i in elegidos}) == 1 and \
                len({(catalogo[i]["tipo_licencia"], catalogo[i]["licenciatario"]) for i in elegidos}) == 1:
            # la planilla trae una fila por registro (RNC y RNPC) de la misma variedad
            estado = "EXACTO" if exactos else "MISMO NOMBRE SIN SIGLAS (INTA, FCA, MDA…)"
        elif elegidos:
            estado = "CONFLICTO (varias filas en el catálogo INTA)"
        else:
            estado = "NO FIGURA en el catálogo de variedades del INTA"
        usados.update(elegidos)
        v = catalogo[elegidos[0]] if len(elegidos) == 1 else {}
        if len(elegidos) > 1:  # mismas variedad y especie con datos distintos: se muestran todos
            v = {k: " | ".join(dict.fromkeys(catalogo[i][k] for i in elegidos)) for k in catalogo[elegidos[0]]}
        licencia = v.get("tipo_licencia", "")
        fila |= {"en_catalogo_inta": estado, "unidad_inta": v.get("unidad", ""),
                 "situacion_registral_inta": v.get("situacion_registral", ""),
                 "tipo_licencia": licencia, "licenciatario": v.get("licenciatario", ""),
                 "disponibilidad_comercial": (f"licenciada a {v['licenciatario']}: consultar precio y stock"
                                              if "Licencia" in licencia and v.get("licenciatario", "") not in {"", "No"}
                                              else "sin licenciatario: consultar a INTA/INTeA" if licencia == "Sin licencia"
                                              else SIN_DATO)}
        salida.append(fila)
    orden = {p: i for i, (p, _, _) in enumerate(PERFILES)}
    salida.sort(key=lambda x: (orden.get(x["perfil_ssd"], 99), x["perfil_ssd"], -int(x["inscripcion_rnc"][:4] or 0)))
    faltantes = {}
    for i, v in enumerate(catalogo):
        if i in usados or v["grupo"] not in GRUPOS_INTA_EXTENSIVOS:
            continue
        clave = (normalizar(v["especie"]), normalizar(v["variedad"]))
        if clave in faltantes:  # misma variedad, otra fila de registro
            previo = faltantes[clave]
            previo["situacion_registral"] = " | ".join(dict.fromkeys([previo["situacion_registral"], v["situacion_registral"]]))
        else:
            faltantes[clave] = dict(v, motivo="variedad del catálogo INTA que no se encontró en el CSV de INASE con ese nombre")
    faltantes = list(faltantes.values())
    return {"cultivares_inta": salida, "catalogo_inta_sin_inase": faltantes}


# tablas de ensayos que traen cultivar_id_inase, con el nombre de la red
REDES = {"recso_resumen_cultivar": "RECSO soja", "ret_resumen_cultivar": "RET trigo", "girasol_resumen_cultivar": "Red girasol INTA-ASAGIR",
         "maiz_resumen_hibrido": "Maíz redes INTA", "sorgo_rindes": "Sorgo INTA Manfredi", "san_luis_rindes": "Ensayos en San Luis 2025/26"}


def _banco_inta(filas: list[dict], especie_a_perfil: dict, ruta_catalogo: Path | None, fecha_corte: date,
                tablas: dict[str, list[dict]]) -> list[dict]:
    """Los cultivares del INTA de cultivos extensivos inscriptos en INASE, de todo el país.

    Hernán (29/10/2026): en esta etapa solo semillas del INTA y de todo el país, sin filtrar por San Luis, y solo
    cultivos extensivos (nada de rosas, frutales, hortalizas ni forestales); lo de empresas privadas queda en las
    otras tablas para más adelante. Es del INTA si el solicitante es el INTA, si es
    Barrow (convenio), si lleva INTA en el nombre o si la variedad figura en el catálogo de variedades del INTA
    (inscripta por su licenciatario). A cada uno se le suman unidad, licencia y licenciatario del catálogo y las
    redes de ensayo donde aparece.
    """
    catalogo = []
    if ruta_catalogo and ruta_catalogo.exists():
        with ruta_catalogo.open(encoding="utf-8-sig", newline="") as f:
            catalogo = [dict(t) for t in dict.fromkeys(tuple(v.items()) for v in csv.DictReader(f))]
    ensayado = defaultdict(set)
    for tabla, red in REDES.items():
        for r in tablas.get(tabla, []):
            for cid in str(r.get("cultivar_id_inase", "")).split(";"):
                if cid.strip():
                    ensayado[cid.strip()].add(red)
    extensivos = {c["cultivar_id"]: c for c in tablas["cultivares"] if c["extensivo"] != "NO"}
    salida = []
    for f in filas:
        if f"INASE-{f['numero']}" not in extensivos:
            continue
        especie = f["especie"].strip()
        perfil = extensivos[f"INASE-{f['numero']}"]["perfil_ssd"].removeprefix("Complementario: ")
        nombre = normalizar(f["cultivar"])
        c = {"especie": especie, "perfil_ssd": perfil}
        en_catalogo = [v for v in catalogo if _misma_especie(v["especie"], c) and
                       (normalizar(v["variedad"]).replace(" ", "") == nombre.replace(" ", "") or _sin_siglas(v["variedad"]) == _sin_siglas(f["cultivar"]))]
        solicitante = f["solicitante_rnc"] + " " + f["solicitante_rnpc"]
        vinculo = ("Solicitante INTA" if es_inta(solicitante) else
                   "Chacra Experimental Integrada Barrow (convenio con INTA)" if "BARROW" in normalizar(solicitante) else
                   "INTA en la denominación" if re.search(r"\bINTA\b", nombre) else
                   f"Ente público: {ente_publico(solicitante)}" if ente_publico(solicitante) else
                   "Variedad del catálogo INTA inscripta por su licenciatario" if en_catalogo else "")
        if not vinculo:
            continue
        v = {k: " | ".join(dict.fromkeys(x[k] for x in en_catalogo if x[k])) for k in ("grupo", "unidad", "tipo_licencia", "licenciatario")}
        validez = f["validez_rnpc"].strip()
        salida.append({
            "cultivar_id": f"INASE-{f['numero']}", "cultivar": f["cultivar"], "cultivo": perfil, "especie": especie,
            "grupo": extensivos[f"INASE-{f['numero']}"]["grupo_ssd"], "subtipo": extensivos[f"INASE-{f['numero']}"]["subtipo"],
            "grupo_catalogo_inta": v["grupo"],
            "condicion_genetica": f["condicion_genetica"], "inscripcion_rnc": f["inscripcion_rnc"],
            "estado_registral": "RNC_INSCRIPTO" if f["inscripcion_rnc"].strip() else "SOLO_RNPC (no habilitado para vender semilla)",
            "proteccion_rnpc": ("vigente al corte" if validez and date.fromisoformat(validez) >= fecha_corte else
                                "vencida" if f["inscripcion_rnpc"].strip() else "sin inscripción RNPC"),
            "solicitante_rnc": f["solicitante_rnc"], "vinculo_inta": vinculo,
            "unidad_inta": v["unidad"], "tipo_licencia": v["tipo_licencia"], "licenciatario": v["licenciatario"],
            "evento_transgenico": f["evento_transgenico"], "ensayos": "; ".join(sorted(ensayado.get(f"INASE-{f['numero']}", []))),
            "obtentor_inta": "SI" if es_inta(solicitante) else "NO", "nombre_busqueda": nombre, "fecha_corte": fecha_corte.isoformat(),
        })
    salida.sort(key=lambda x: (x["grupo"], x["cultivo"], -int(x["inscripcion_rnc"][:4] or 0), x["cultivar"]))
    return salida


def nucleo(nombre: str) -> tuple[str, str] | None:
    """Prefijo de marca + código numérico, sin las siglas de tecnología: 'LT 722 VT3 PRO' y 'LT722VT3P' → ('LT', '722')."""
    compacto = nombre.replace(" ", "")
    m = re.search(r"\d+(?:[A-Z]\d+)?", compacto)
    return (compacto[:m.start()], m.group()) if m else None


def _oferta(cultivares: list[dict], ruta: Path) -> list[dict]:
    """Cruza lo que las empresas dicen ofrecer (relevado en prensa y catálogos) con el catálogo INASE.

    Ofrecido no es comprado: sirve para saber qué materiales están en el mercado, no precio ni stock.
    El nombre comercial puede diferir del inscripto, así que lo parecido va a revisión y nunca se une solo.
    """
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        filas = list(csv.DictReader(f))
    por_perfil = defaultdict(list)
    for c in cultivares:
        por_perfil[c["perfil_ssd"]].append(c)
    salida = []
    for o in filas:
        clave = normalizar(o["material"])
        grupo = por_perfil.get(o["perfil_ssd"], []) if not clave.startswith("SIN NOMBRE") else []
        exactos = [c for c in grupo if c["nombre_busqueda"] == clave
                   or c["nombre_busqueda"].replace(" ", "") == clave.replace(" ", "")]
        codigos = {w for w in clave.split() if any(ch.isdigit() for ch in w)}
        parecidos = [c for c in grupo if codigos and codigos <= set(c["nombre_busqueda"].split())] if not exactos else []
        if not parecidos and not exactos and not codigos:
            palabras = [w for w in clave.split() if w not in {"DM", "INTA", "NK"} and len(w) > 3]
            parecidos = [c for c in grupo if palabras and all(w in c["nombre_busqueda"].split() for w in palabras)]
        if not exactos and not parecidos and nucleo(clave):
            parecidos = [c for c in grupo if nucleo(c["nombre_busqueda"]) == nucleo(clave)]
        if exactos:
            estado, encontrados = "INSCRIPTO (mismo nombre en INASE)", exactos
        elif parecidos:
            estado, encontrados = "PARA_REVISION (nombre parecido en INASE)", parecidos[:3]
        else:
            estado, encontrados = "NO_ENCONTRADO con ese nombre (puede ser nombre comercial o inscripción en trámite)", []
        salida.append({**o, "estado_en_inase": estado,
                       "cultivar_id_inase": "; ".join(c["cultivar_id"] for c in encontrados),
                       "nombre_oficial_inase": "; ".join(c["cultivar"] for c in encontrados),
                       "eventos_ogm_inase": "; ".join(c["eventos_ogm"] or "sin evento declarado" for c in encontrados),
                       "inscripcion_rnc": "; ".join(c["inscripcion_rnc"] for c in encontrados),
                       "disponibilidad_comercial": "OFERTA_DECLARADA (sin precio ni stock verificados)"
                       if o["tipo_evidencia"] in {"LANZAMIENTO_DECLARADO", "CATALOGO_EMPRESA"} else SIN_DATO})
    return salida


def _leer_recso(prefijo: Path, tabla: str) -> list[dict]:
    with prefijo.with_name(f"{prefijo.name}_{tabla}.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _recso(cultivares: list[dict], prefijo: Path | None) -> dict[str, list[dict]]:
    """Red nacional de soja del INTA (RECSO 2025/26): ensayos, rindes y un resumen por cultivar.

    Los rindes se leyeron de las planillas del informe; cada ensayo trae el control de que el promedio
    de lo leído coincide con la MEDIA impresa. El resumen separa lo medido en San Luis y en las
    subregiones vecinas (II-3 y II-5) del resto del país: rendir bien en Pergamino no dice nada de Granville.
    """
    if not prefijo or not prefijo.with_name(f"{prefijo.name}_ensayos.csv").exists():
        return {}
    ensayos, rindes, fichas = (_leer_recso(prefijo, t) for t in ("ensayos", "rindes", "cultivares"))
    # Tablas 1 a 9 del informe: rinde relativo al testigo por subregión en 1, 2 y 3 campañas
    multianual = _leer_recso(prefijo, "multianual") if prefijo.with_name(f"{prefijo.name}_multianual.csv").exists() else []
    varios_anios = {(m["cultivar"], m["subregion"], m["periodo"][:7]): m for m in multianual}
    soja = [c for c in cultivares if c["perfil_ssd"] == "Soja"]
    por_nucleo = defaultdict(list)
    for c in soja:
        if nucleo(c["nombre_busqueda"]):
            por_nucleo[nucleo(c["nombre_busqueda"])].append(c)
    resumen = []
    for ficha in fichas:
        clave = normalizar(ficha["cultivar"])
        inase = [c for c in soja if c["nombre_busqueda"].replace(" ", "") == clave.replace(" ", "")] \
            or por_nucleo.get(nucleo(clave), [])
        sin_marca = False
        if not inase and nucleo(clave):  # INASE suele inscribir sin la marca: 'CZ 4021 STS' figura como '4021'
            inase = por_nucleo.get(("", nucleo(clave)[1]), [])
            sin_marca = bool(inase)
        suyos = [r for r in rindes if r["cultivar"] == ficha["cultivar"] and r["en_analisis_conjunto"] == "SI"]
        cerca = [r for r in suyos if not r["referencia_san_luis"].startswith("OTRA")]
        en_sl = [r for r in suyos if r["referencia_san_luis"].startswith("SAN_LUIS")]
        media = lambda filas: round(sum(float(r["rinde_relativo_pct"]) for r in filas) / len(filas), 1) if filas else ""
        resumen.append({
            "cultivar": ficha["cultivar"], "empresa": ficha["empresa"], "grupo_madurez_recso": ficha["grupo_madurez_recso"],
            "ensayos_pais": len(suyos), "rinde_relativo_pais_pct": media(suyos),
            "ensayos_san_luis_y_vecinos": len(cerca), "rinde_relativo_san_luis_y_vecinos_pct": media(cerca),
            "en_grupo_superior_san_luis_y_vecinos": sum(1 for r in cerca if r["grupo_estadistico"] in {"+", "a"}),
            "ensayos_en_san_luis": len(en_sl), "rinde_kg_ha_en_san_luis": "; ".join(r["rinde_kg_ha"] for r in en_sl),
            **{f"{sr}_{etiqueta}_pct_testigo": (lambda m: f"{m['rinde_relativo_al_testigo_pct']} ({m['ensayos_en_el_periodo']} ensayos)" if m else "")(
                varios_anios.get((ficha["cultivar"], sr, desde)))
               for sr in ("II-3", "II-5") for desde, etiqueta in (("2023/24", "3_campanas"), ("2024/25", "2_campanas"))},
            "estado_en_inase": ("PARA_REVISION (mismo código inscripto sin la marca; confirmar con el solicitante)" if sin_marca
                                else "INSCRIPTO (mismo nombre o mismo código en INASE)" if len(inase) == 1
                                else "PARA_REVISION (más de un registro con ese código)" if inase else "NO_ENCONTRADO con ese nombre"),
            "cultivar_id_inase": "; ".join(c["cultivar_id"] for c in inase[:3]),
            "nombre_oficial_inase": "; ".join(c["cultivar"] for c in inase[:3]),
            "eventos_ogm_inase": "; ".join(c["eventos_ogm"] or "sin evento declarado" for c in inase[:3]),
            "solicitante_inase": "; ".join(c["solicitante_rnc"] for c in inase[:3]),
            "fuente_url": ficha["fuente_url"],
        })
    resumen.sort(key=lambda r: (r["ensayos_san_luis_y_vecinos"] < 3, -(r["rinde_relativo_san_luis_y_vecinos_pct"] or 0)))
    return {"recso_resumen_cultivar": resumen, "recso_ensayos": ensayos, "recso_rindes": rindes,
            **({"recso_multianual": multianual} if multianual else {})}


def _ret(cultivares: list[dict], prefijo: Path | None) -> dict[str, list[dict]]:
    """Red de ensayos de trigo de INASE (RET), campañas 2018/19 a 2025/26, con un resumen por cultivar.

    San Luis triguero (el este) cae en la subregión 9, Pampa semiárida central (mapa INASE 2021), la misma de Anguil.
    El oeste es Llanos cuyanos y Valles serranos, sin ensayos RET. Las subregiones semiáridas vecinas son la 8 y la 10.
    """
    if not prefijo or not prefijo.with_name(f"{prefijo.name}_ensayos.csv").exists():
        return {}
    ensayos, rindes = (_leer_recso(prefijo, t) for t in ("ensayos", "rindes"))
    trigo = [c for c in cultivares if c["perfil_ssd"] == "Trigo"]
    compacto = lambda t: re.sub(r"[^A-Z0-9]", "", normalizar(t))
    chicos = {e["ensayo_id"] for e in ensayos if int(e.get("n_cultivares") or 99) < 5}  # con 2 o 3 cultivares la media no sirve de base
    por_cultivar = defaultdict(list)
    for r in rindes:
        if r["ensayo_id"] not in chicos:
            por_cultivar[r["cultivar"]].append(r)
    media = lambda filas: round(sum(float(r["rinde_relativo_pct"]) for r in filas) / len(filas), 1) if filas else ""
    resumen = []
    for nombre, filas in por_cultivar.items():
        clave = filas[0]["clave_nombre"]
        exactos = [c for c in trigo if compacto(c["cultivar"]) == compacto(nombre)]
        parecidos = [c for c in trigo if len(clave) >= 3 and compacto(c["cultivar"]).endswith(clave)] if not exactos else []
        psc = [r for r in filas if r["referencia_san_luis"].startswith("SAN_LUIS")]
        semiarida = [r for r in filas if not r["referencia_san_luis"].startswith("OTRA")]
        recientes = [r for r in semiarida if r["campana"] >= "2023/24"]  # las 3 últimas: lo que hoy se siembra
        inase = exactos or parecidos[:3]
        resumen.append({
            "cultivar": nombre, "ensayos_pais": len(filas), "rinde_relativo_pais_pct": media(filas),
            "ensayos_pampa_semiarida_central": len(psc), "rinde_relativo_pampa_semiarida_central_pct": media(psc),
            "ensayos_semiarida_8_9_10": len(semiarida), "rinde_relativo_semiarida_pct": media(semiarida),
            "ensayos_semiarida_desde_2023": len(recientes), "rinde_relativo_semiarida_desde_2023_pct": media(recientes),
            "campanas_en_semiarida": ", ".join(sorted({r["campana"] for r in semiarida})),
            "ultima_campana": max(r["campana"] for r in filas),
            "estado_en_inase": ("INSCRIPTO (mismo nombre en INASE)" if exactos else
                                "PARA_REVISION (nombre parecido en INASE)" if parecidos else "NO_ENCONTRADO con ese nombre"),
            "cultivar_id_inase": "; ".join(c["cultivar_id"] for c in inase),
            "nombre_oficial_inase": "; ".join(c["cultivar"] for c in inase),
            "obtentor_inta": "SI" if any(c["obtentor_inta"] == "SI" for c in inase) else "NO" if inase else SIN_DATO,
            "nombres_en_planillas": "; ".join(sorted({n for r in filas for n in r["nombre_en_planilla"].split("; ")}))[:300],
        })
    resumen.sort(key=lambda r: (r["ensayos_semiarida_8_9_10"] < 3, -(r["rinde_relativo_semiarida_pct"] or 0)))
    return {"ret_resumen_cultivar": resumen, "ret_ensayos": ensayos, "ret_rindes": rindes}


def _girasol(cultivares: list[dict], prefijo: Path | None) -> dict[str, list[dict]]:
    """Red nacional de girasol INTA-ASAGIR, campañas 2023/24 a 2025/26, con un resumen por cultivar.

    No hay ensayo en San Luis. Las vecinas semiáridas son Anguil y General Pico (La Pampa) y Laboulaye (sur de Córdoba).
    Los "Testigo N" son anónimos: cuentan para la media del ensayo pero no tienen fila en el resumen.
    """
    if not prefijo or not prefijo.with_name(f"{prefijo.name}_ensayos.csv").exists():
        return {}
    ensayos, rindes = (_leer_recso(prefijo, t) for t in ("ensayos", "rindes"))
    girasol = [c for c in cultivares if c["perfil_ssd"] == "Girasol"]
    compacto = lambda t: re.sub(r"[^A-Z0-9]", "", normalizar(t))
    por_cultivar = defaultdict(list)
    for r in rindes:
        if r["es_testigo_anonimo"] == "NO":
            por_cultivar[r["cultivar"]].append(r)
    media = lambda filas, col="rinde_relativo_pct": (
        round(sum(float(r[col]) for r in filas if r[col]) / len([r for r in filas if r[col]]), 1) if [r for r in filas if r[col]] else "")
    resumen = []
    for nombre, filas in por_cultivar.items():
        exactos = [c for c in girasol if compacto(c["cultivar"]) == compacto(nombre)]
        vecinas = [r for r in filas if r["referencia_san_luis"].startswith("SEMIARIDA")]
        oeste = [r for r in filas if r["referencia_san_luis"].startswith("OESTE")]
        resumen.append({
            "cultivar": nombre, "empresa": filas[0]["empresa"], "ensayos_pais": len(filas), "rinde_relativo_pais_pct": media(filas),
            "ensayos_vecinas_san_luis": len(vecinas), "rinde_relativo_vecinas_pct": media(vecinas),
            "aceite_vecinas_pct": media(vecinas, "aceite_pct"),
            "ensayos_oeste_bonaerense": len(oeste), "rinde_relativo_oeste_bonaerense_pct": media(oeste),
            "campanas": ", ".join(sorted({r["campana"] for r in filas})),
            "estado_en_inase": "INSCRIPTO (mismo nombre en INASE)" if exactos else "NO_ENCONTRADO con ese nombre (puede ser experimental o nombre comercial)",
            "cultivar_id_inase": "; ".join(c["cultivar_id"] for c in exactos),
            "obtentor_inta": "SI" if any(c["obtentor_inta"] == "SI" for c in exactos) else "NO" if exactos else SIN_DATO,
        })
    resumen.sort(key=lambda r: (r["ensayos_vecinas_san_luis"] < 2, -(r["rinde_relativo_vecinas_pct"] or 0)))
    return {"girasol_resumen_cultivar": resumen, "girasol_ensayos": ensayos, "girasol_rindes": rindes}


def _maiz(cultivares: list[dict], prefijo: Path | None) -> dict[str, list[dict]]:
    """Maíz de las redes del INTA más cercanas a San Luis, campañas 2024/25 y 2025/26, con un resumen por híbrido.

    No hay red nacional única de maíz. Dentro de San Luis están Villa Mercedes y Tilisarao (INTA EEA San Luis + UNSL,
    2025/26); las vecinas semiáridas son Mattaldi, Laboulaye y Río Cuarto (sur de Córdoba) y General Villegas
    (noroeste bonaerense). "vecinas_san_luis" cuenta San Luis y sus vecinas.
    """
    if not prefijo or not prefijo.with_name(f"{prefijo.name}_ensayos.csv").exists():
        return {}
    ensayos, rindes = (_leer_recso(prefijo, t) for t in ("ensayos", "rindes"))
    maiz = [c for c in cultivares if c["perfil_ssd"] == "Maíz"]
    compacto = lambda t: re.sub(r"[^A-Z0-9]", "", normalizar(t))
    por_hibrido = defaultdict(list)
    for r in rindes:
        if r["rinde_relativo_pct"]:
            por_hibrido[r["hibrido"]].append(r)
    media = lambda filas: round(sum(float(r["rinde_relativo_pct"]) for r in filas) / len(filas), 1) if filas else ""
    resumen = []
    for nombre, filas in por_hibrido.items():
        exactos = [c for c in maiz if compacto(c["cultivar"]) in {compacto(r["nombre_en_planilla"]) for r in filas}]
        vecinas = [r for r in filas if r["referencia_san_luis"].startswith(("SEMIARIDA", "SAN_LUIS"))]
        en_san_luis = [r for r in filas if r["referencia_san_luis"].startswith("SAN_LUIS")]
        resumen.append({
            "hibrido": nombre, "empresa": filas[0]["empresa"], "ensayos_total": len(filas), "rinde_relativo_total_pct": media(filas),
            "ensayos_en_san_luis": len(en_san_luis), "rinde_relativo_en_san_luis_pct": media(en_san_luis),
            "ensayos_vecinas_san_luis": len(vecinas), "rinde_relativo_vecinas_pct": media(vecinas),
            "sitios_vecinos": ", ".join(sorted({r["sitio"] for r in vecinas})),
            "campanas": ", ".join(sorted({r["campana"] for r in filas})),
            "estado_en_inase": "INSCRIPTO (mismo nombre en INASE)" if exactos else "NO_ENCONTRADO con ese nombre (puede ser nombre comercial)",
            "cultivar_id_inase": "; ".join(sorted({c["cultivar_id"] for c in exactos})),
            "obtentor_inta": "SI" if any(c["obtentor_inta"] == "SI" for c in exactos) else "NO" if exactos else SIN_DATO,
        })
    resumen.sort(key=lambda r: (r["ensayos_vecinas_san_luis"] < 2, -(r["rinde_relativo_vecinas_pct"] or 0)))
    return {"maiz_resumen_hibrido": resumen, "maiz_ensayos": ensayos, "maiz_rindes": rindes}


def _sorgo(cultivares: list[dict], prefijo: Path | None) -> dict[str, list[dict]]:
    """Sorgo granífero del ensayo de INTA EEA Manfredi 2024/25 (40 híbridos), cruzado con INASE.

    Es un solo sitio y una campaña: sirve para ver qué materiales hay y cuáles se destacan, no para elegir.
    Las diferencias menores a la DMS del ensayo (1344 kg/ha) no son significativas.
    """
    if not prefijo or not prefijo.with_name(f"{prefijo.name}_ensayos.csv").exists():
        return {}
    ensayos, rindes = (_leer_recso(prefijo, t) for t in ("ensayos", "rindes"))
    sorgo = [c for c in cultivares if c["perfil_ssd"] == "Sorgo"]
    compacto = lambda t: re.sub(r"[^A-Z0-9]", "", normalizar(t))
    dms = {e["ensayo_id"]: int(e["dms_kg_ha"]) for e in ensayos}
    for r in rindes:
        exactos = [c for c in sorgo if compacto(c["cultivar"]) == compacto(r["hibrido"])]
        r["sin_diferencia_con_el_mejor"] = "SI" if int(r["diferencia_con_el_mejor_kg_ha"]) < dms[r["ensayo_id"]] else "NO"
        r["estado_en_inase"] = ("INSCRIPTO (mismo nombre en INASE)" if exactos else
                                "EXPERIMENTAL (todavía no inscripto)" if "EXP" in r["hibrido"].upper() else "NO_ENCONTRADO con ese nombre")
        r["cultivar_id_inase"] = "; ".join(c["cultivar_id"] for c in exactos)
        r["obtentor_inta"] = "SI" if r["empresa"] == "INTA" or any(c["obtentor_inta"] == "SI" for c in exactos) else "NO"
    return {"sorgo_ensayos": ensayos, "sorgo_rindes": rindes}


def _san_luis(cultivares: list[dict], prefijo: Path | None) -> dict[str, list[dict]]:
    """Ensayos hechos dentro de San Luis en 2025/26 (INTA EEA San Luis + UNSL), todos los cultivos, cruzados con INASE.

    Son una campaña y un sitio por ensayo: el informe aclara que no se extrapolan. Los sorgos vienen sin nombre.
    El maíz también está en las tablas de maíz, para compararlo con las redes de las vecinas.
    """
    if not prefijo or not prefijo.with_name(f"{prefijo.name}_ensayos.csv").exists():
        return {}
    ensayos, rindes = (_leer_recso(prefijo, t) for t in ("ensayos", "rindes"))
    compacto = lambda t: re.sub(r"[^A-Z0-9]", "", normalizar(t).replace("VT3 PRO", "VT3P").replace("VT3PRO", "VT3P"))
    por_perfil = defaultdict(lambda: defaultdict(list))
    for c in cultivares:
        por_perfil[c["perfil_ssd"]][compacto(c["cultivar"])].append(c)
    for r in rindes:
        exactos = por_perfil[r["cultivo"]].get(compacto(r["cultivar"]), [])
        r["estado_en_inase"] = ("INSCRIPTO (mismo nombre en INASE)" if exactos else
                                "SIN_NOMBRE en el informe" if r["cultivar"].startswith("material ") else "NO_ENCONTRADO con ese nombre")
        r["cultivar_id_inase"] = "; ".join(c["cultivar_id"] for c in exactos)
        r["obtentor_inta"] = "SI" if any(c["obtentor_inta"] == "SI" for c in exactos) else "NO" if exactos else SIN_DATO
    return {"san_luis_ensayos": ensayos, "san_luis_rindes": rindes}


def _controles(cultivares: list[dict]) -> list[dict]:
    salida = []
    repetidos = Counter((c["especie"], c["nombre_busqueda"]) for c in cultivares)
    for c in cultivares:
        problemas = []
        if repetidos[(c["especie"], c["nombre_busqueda"])] > 1:
            problemas.append("Mismo nombre y especie en más de un registro: no fusionar sin revisar")
        if c["alerta_legal"]:
            problemas.append(c["alerta_legal"])
        if c["extensivo"] == "REVISAR":
            problemas.append(f"Destino a confirmar ({c['subtipo']}, grupo INASE {c['grupo']})")
        if not c["inscripcion_rnc"].strip():
            problemas.append("Solo RNPC: sin inscripción en el RNC, no se puede vender como semilla")
        elif not c["solicitante_rnc"].strip():
            problemas.append("Sin solicitante RNC en el registro")
        if "TR" in c["caracteristicas"].split(" - ") and not c["eventos_ogm"]:
            problemas.append("Marcado TR sin evento declarado")
        if c["eventos_ogm"] and "TR" not in [x.strip() for x in c["caracteristicas"].split("-")] and c["caracteristicas"]:
            problemas.append("Evento declarado sin marca TR en características")
        for p in problemas:
            salida.append({"cultivar_id": c["cultivar_id"], "cultivar": c["cultivar"], "especie": c["especie"], "control": p})
    return salida


def guardar(tablas: dict[str, list[dict]], salida: Path, ruta_csv: Path) -> dict:
    salida.mkdir(parents=True, exist_ok=True)
    meta = tablas.pop("_meta")[0]
    for nombre, filas in tablas.items():
        with (salida / f"{nombre}.csv").open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(filas[0].keys()) if filas else ["sin_filas"])
            w.writeheader()
            w.writerows(filas)
    manifiesto = {
        "spec": "049-base-de-semillas-extensivas",
        "fuente_principal": "INASE_CNC",
        "archivo_fuente": ruta_csv.name,
        "sha256": hashlib.sha256(ruta_csv.read_bytes()).hexdigest(),
        "filas_fuente": meta["filas_fuente"],
        "fecha_corte": meta["fecha_corte"],
        "nota_fecha": meta["nota_fecha"],
        "generado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tablas": {n: len(f) for n, f in tablas.items()},
    }
    (salida / "manifiesto.json").write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifiesto


HOJAS = [  # (tabla, nombre de la hoja, para qué sirve)
    ("banco_inta", "Banco INTA", "Los cultivares del INTA de cultivos extensivos inscriptos en INASE, de todo el país, con licencia y ensayos donde aparecen"),
    ("fichas_inta", "Fichas INTA", "Condiciones de cultivo de cada variedad del INTA (ciclo, siembra, zona, sanidad, tolerancias), una fila por dato con su fuente oficial"),
    ("manejo_cultivos", "Manejo por cultivo", "Buenas prácticas de cada cultivo extensivo (clima, siembra, suelo, densidad, fertilización, sanidad, cosecha) con fuente oficial argentina; lo que falta dice sin dato verificado"),
    ("requerimientos_ambientales", "Ambiente por especie", "Lo que necesita cada especie del ambiente (heladas, calor, suelo, sales, sodio, pH, Kc, raíces, nutrientes), ensayos y ambiente de San Luis, del dossier del 31/10/2026; nivel San Luis, Argentina o global (FAO); no descarta cultivos"),
    ("cultivares_inta", "Cultivares INTA", "Los cultivares extensivos del INTA inscriptos en INASE, con unidad, licencia y licenciatario del catálogo INTA"),
    ("catalogo_inta_sin_inase", "INTA sin cruzar", "Variedades del catálogo INTA que no se encontraron en INASE con el mismo nombre"),
    ("perfiles", "Resumen por cultivo", "Un renglón por cultivo: cuántos cultivares hay, cuántos OGM, protegidos, del INTA y nuevos"),
    ("cultivares", "Cultivares", "Todos los cultivares inscriptos de los cultivos extensivos, con las columnas originales de INASE"),
    ("eventos_ogm", "Eventos OGM", "Cada evento transgénico declarado en INASE, en cuántos cultivares aparece y su rasgo"),
    ("cultivar_evento", "Cultivar-evento", "Qué evento lleva cada cultivar (una fila por par)"),
    ("obtentores", "Obtentores", "Quién inscribió cada cultivar, por cultivo"),
    ("candidatos_inta", "Conciliación INTA", "Materiales INTA del documento SSD buscados en el catálogo de INASE"),
    ("fuentes", "Fuentes", "Registro de todas las fuentes oficiales: qué aportan, dónde están y en qué estado"),
    ("ensayos_por_perfil", "Ensayos por cultivo", "Redes y ensayos localizados para cada cultivo"),
    ("girasol_resumen_cultivar", "Girasol por cultivar", "Red nacional de girasol 2023/24 a 2025/26: rinde relativo y aceite en el país y en las vecinas semiáridas de San Luis"),
    ("girasol_ensayos", "Girasol ensayos", "Cada ensayo de girasol: sitio, campaña, fecha de siembra y media"),
    ("san_luis_rindes", "Ensayos en San Luis", "Ensayos INTA EEA San Luis + UNSL 2025/26 dentro de la provincia: maíz, trigo, sorgo y algodón, con su cruce con INASE"),
    ("san_luis_ensayos", "San Luis ensayos", "Cada ensayo en San Luis 2025/26: sitio, suelo, siembra, manejo y páginas del informe"),
    ("maiz_resumen_hibrido", "Maíz por híbrido", "Maíz 2024/25 y 2025/26 (redes INTA y ensayos en San Luis): rinde relativo en total, en San Luis y en sus vecinas semiáridas"),
    ("maiz_ensayos", "Maíz ensayos", "Cada ensayo de maíz: red, sitio, campaña, época de siembra y media"),
    ("maiz_rindes", "Maíz rindes", "Cada híbrido en cada ensayo: kg/ha y rinde relativo a la media del ensayo"),
    ("sorgo_rindes", "Sorgo Manfredi", "Sorgo granífero, ensayo INTA EEA Manfredi 2024/25: rinde, ciclo, tanino y si está inscripto en INASE"),
    ("sorgo_ensayos", "Sorgo ensayo", "Datos del ensayo de sorgo de Manfredi: siembra, lluvia, media y diferencia mínima significativa"),
    ("girasol_rindes", "Girasol rindes", "Cada híbrido en cada ensayo: kg/ha, aceite, rinde ajustado por aceite y rinde relativo"),
    ("ret_resumen_cultivar", "Trigo RET por cultivar", "Red de trigo de INASE 2018/19 a 2025/26: cómo rindió cada cultivar en el país, en la Pampa semiárida central (San Luis) y en las semiáridas vecinas"),
    ("ret_ensayos", "Trigo RET ensayos", "Cada ensayo de trigo: sitio, subregión triguera 2021, época, con o sin fungicida, media y repeticiones"),
    ("ret_rindes", "Trigo RET rindes", "Cada cultivar en cada ensayo de trigo: kg/ha, rinde relativo a la media y el nombre como vino en la planilla"),
    ("recso_resumen_cultivar", "Soja RECSO por cultivar", "Red nacional de soja del INTA 2025/26: cómo rindió cada cultivar en el país y en San Luis y sus vecinas"),
    ("recso_ensayos", "Soja RECSO ensayos", "Los 351 ensayos: sitio, subregión, suelo (MO, pH), fechas, media, CV y si el INTA lo usó"),
    ("recso_multianual", "Soja RECSO 3 campañas", "Tablas 1 a 9 del informe: rinde relativo al testigo por subregión en 1, 2 y 3 campañas (2023/24 a 2025/26)"),
    ("recso_rindes", "Soja RECSO rindes", "Cada cultivar en cada ensayo: kg/ha, rinde relativo a la media y grupo estadístico"),
    ("oferta_comercial", "Privados (referencia)", "Lo que las empresas dicen ofrecer, lo más sembrado (SISA) y los ensayos, cruzado con INASE"),
    ("control_calidad", "Control de calidad", "Registros que hay que revisar antes de usar"),
]


def exportar_excel(salida: Path, manifiesto: dict) -> Path | None:
    """Junta las tablas en un Excel con una hoja de lectura. Si no está openpyxl, no hace nada."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:
        return None
    wb = Workbook()
    leeme = wb.active
    leeme.title = "LEEME"
    leeme.append(["Base de fuentes de semillas de cultivos extensivos de Argentina (spec 049)"])
    leeme.append([f"Fuente principal: Catálogo Nacional de Cultivares de INASE, archivo {manifiesto['archivo_fuente']}"])
    leeme.append([f"SHA-256: {manifiesto['sha256']}  ·  Filas de la fuente: {manifiesto['filas_fuente']}"])
    leeme.append([f"Fecha de corte: {manifiesto['fecha_corte']} (inscripción más reciente del archivo)  ·  Generado: {manifiesto['generado_utc']}"])
    leeme.append([])
    leeme.append(["Reglas: nada se inventa. 'sin dato verificado' = la fuente no lo dice. Sin evento declarado NO es "
                  "'convencional confirmada'. Inscripto en INASE NO es 'hay semilla para comprar'."])
    leeme.append([])
    leeme.append(["Hoja", "Para qué sirve"])
    for _, hoja, para in HOJAS:
        leeme.append([hoja, para])
    leeme["A1"].font = Font(bold=True, size=14)
    leeme.column_dimensions["A"].width = 28
    leeme.column_dimensions["B"].width = 110
    cabecera = PatternFill("solid", fgColor="2F5D3A")
    for tabla, hoja, _ in HOJAS:
        if not (salida / f"{tabla}.csv").exists():
            continue
        with (salida / f"{tabla}.csv").open(encoding="utf-8-sig", newline="") as f:
            filas = list(csv.reader(f))
        ws = wb.create_sheet(hoja)
        for fila in filas:
            ws.append(fila)
        for celda in ws[1]:
            celda.font = Font(bold=True, color="FFFFFF")
            celda.fill = cabecera
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for i, titulo in enumerate(filas[0], 1):
            largo = max(len(str(r[i - 1])) for r in filas[:200] if len(r) >= i)
            ws.column_dimensions[get_column_letter(i)].width = min(max(largo, len(titulo)) + 2, 60)
    ruta = salida / "base_semillas_extensivas.xlsx"
    wb.save(ruta)
    return ruta


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("csv_inase", type=Path)
    p.add_argument("salida", type=Path)
    p.add_argument("--fecha-corte", type=date.fromisoformat, default=None)
    a = p.parse_args()
    tablas = construir(a.csv_inase, a.fecha_corte)
    manifiesto = guardar(tablas, a.salida, a.csv_inase)
    exportar_excel(a.salida, manifiesto)
    print(json.dumps(manifiesto, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
