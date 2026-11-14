"""Arma las tablas de maíz de las redes del INTA más cercanas a San Luis (campañas 2024/25 y 2025/26).

Fuentes (todas en argentina.gob.ar, sin red nacional única de maíz):
- Red de híbridos de maíz siembra temprana INTA Marcos Juárez 2024/25 (Cuadro 3 es imagen: se leyó con OCR
  y cada fila se controló contra el promedio impreso; Anexo I = Canals y Laboulaye, fuera del análisis conjunto).
- Misma red 2025/26, informe preliminar (tabla en texto).
- La Carlota siembra tardía 2025/26 (AER La Carlota, INTA Marcos Juárez).
- Red de híbridos del norte de Buenos Aires 2024/25, sitio General Villegas temprana y tardía (tablas imagen,
  transcriptas; la media de cada una coincide con la impresa).
- Ensayos agrícolas en San Luis 2025/26 (INTA EEA San Luis + UNSL): Villa Mercedes a dos densidades y Tilisarao.
  Se leen de ../san_luis/san_luis_2025_26.csv, la misma transcripción que usa san_luis_final.py.
Uso: python maiz_final.py <carpeta_herramienta> <carpeta_salida>
"""
import collections, csv, hashlib, re, sys, unicodedata
from pathlib import Path

H, OUT = Path(sys.argv[1]), Path(sys.argv[2])
U = {
    "MJ25": "https://www.argentina.gob.ar/sites/default/files/2025/09/inta_crcordoba_aerjustinianoposse_pagnan_l_red.pdf",
    "MJ26": "https://www.argentina.gob.ar/sites/default/files/2026/05/red_maiz_temprano_inta_mj_2025-2026-inf_preliminar.pdf",
    "LC26": "https://www.argentina.gob.ar/sites/default/files/2026/09/inta_crcordoba_eeamarcosjuarez_allovatti_lacarlotasiembratardiamaiz.pdf",
    "BN25": "https://www.argentina.gob.ar/sites/default/files/2025/11/inta_crbanorte_galizia_luciana_informe_final_red_maiz_2025.pdf",
    "SL26": "https://repositorio.inta.gob.ar/xmlui/handle/20.500.12123/27891",
}
RED = {"MJ25": "Red INTA Marcos Juárez", "MJ26": "Red INTA Marcos Juárez", "LC26": "Red INTA Marcos Juárez",
       "BN25": "Red INTA norte de Buenos Aires", "SL26": "INTA EEA San Luis + UNSL"}
PROV = {"General Villegas": "Buenos Aires", "Villa Mercedes": "San Luis", "Tilisarao": "San Luis"}
VECINAS = {"Mattaldi": "SEMIARIDA_VECINA (sur de Córdoba)", "Laboulaye": "SEMIARIDA_VECINA (sur de Córdoba)",
           "Río Cuarto": "SEMIARIDA_VECINA (centro-sur de Córdoba, la más cercana a San Luis)",
           "General Villegas": "SEMIARIDA_VECINA (noroeste bonaerense)",
           "Villa Mercedes": "SAN_LUIS (ensayo en la provincia)", "Tilisarao": "SAN_LUIS (ensayo en la provincia)"}
A = lambda s: unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()
TEC = [("VIPTERA3", "VIP3"), ("VIPTERA", "VIP3"), ("VIPS", "VIP3"), ("CIP3", "VIP3"), ("TRECEPTA", "TRE"), ("VT3PRO", "VT3P"),
       ("PWUEN", "PWUE"), ("PWU", "PWUE"), ("PWUEE", "PWUE")]
SUF = ["VIP3CL", "VIP3", "TRE", "VT3P", "PWUE", "CL", "VIP", "EVO", "RE", "TDTGCL", "BTRRCL", "BTRR", "TIGRE", "PUMA"]
ALIAS = {"MARIODM2773": "DM2773", "DM2773": "DM2773", "KM13916": "S13916", "KWS13916": "S13916", "NXM1122": "NEXSEM1122",
         "EBC24121": "EBCPUMA", "EBC21123": "EBCTIGRE", "EBC211": "EBCTIGRE", "SYT4550": "SYT4550",
         "STINE9939": "ST9939", "LT302": "LT302", "BASF5575": "5575", "BASF7349": "7349", "BASF7344": "7344",
         "DK7373": "DK7373", "NS7626": "NS7626", "GENESIS152RRBT": "GEN152", "GEN152RRBT": "GEN152"}

def clave(n):
    s = re.sub(r"[^A-Z0-9]", "", A(n))
    for a, b in TEC: s = s.replace(a, b)
    cambio = True
    while cambio:
        cambio = False
        for f in SUF:
            if s.endswith(f) and len(s) > len(f) + 2: s, cambio = s[:-len(f)], True
    if s.startswith("EBC") and "PUMA" in re.sub(r"[^A-Z]", "", A(n)): s = "EBCPUMA"
    if s.startswith("EBC") and "TIGRE" in re.sub(r"[^A-Z]", "", A(n)): s = "EBCTIGRE"
    return ALIAS.get(s, s)

filas, ensayos = [], []
def ensayo(fuente, campana, sitio, epoca, valores, nota=""):
    eid = "MAIZ-" + hashlib.sha1(f"{fuente}|{campana}|{sitio}|{epoca}".encode()).hexdigest()[:8]
    v = [x for x in valores if x[2] is not None]
    media = sum(x[2] for x in v) / len(v)
    ensayos.append(dict(ensayo_id=eid, campana=campana, sitio=sitio, provincia=PROV.get(sitio, "Córdoba"), red=RED[fuente],
                        epoca_siembra=epoca, n_hibridos=len(v), rinde_medio_kg_ha=round(media),
                        referencia_san_luis=VECINAS.get(sitio, "OTRA_REGION"), nota=nota, fuente_url=U[fuente]))
    for emp, nombre, r, hum in valores:
        filas.append(dict(ensayo_id=eid, campana=campana, sitio=sitio, epoca_siembra=epoca, empresa=emp.strip(),
                          nombre_en_planilla=nombre, clave_nombre=clave(nombre), rinde_kg_ha="" if r is None else round(r),
                          rinde_relativo_pct="" if r is None else round(100 * r / media, 1), humedad_pct=hum,
                          referencia_san_luis=VECINAS.get(sitio, "OTRA_REGION")))

# Marcos Juárez 2024/25, Cuadro 3 (OCR controlado)
c3 = collections.defaultdict(list)
for r in csv.DictReader(open(H / "mj_2024_25_cuadro3.csv", encoding="utf-8")):
    c3[r["sitio"]].append((r["empresa"], r["hibrido"].replace("Mario DM", "DM"), float(r["rinde_kg_ha"]) if r["rinde_kg_ha"] else None, ""))
for sitio, v in c3.items():
    ensayo("MJ25", "2024/25", sitio, "temprana", v,
           "Mattaldi sin dato para NK 835 VIP3 y BRV8421PWUE (celda vacía en el informe)" if sitio == "Mattaldi" else "")
# Anexo I: Canals y Laboulaye (quedaron fuera del análisis conjunto por vuelco y demora en la cosecha)
anexo, prev = {"Canals": [], "Laboulaye": []}, ""
for l in open(H / "mj_2024_25_anexo.txt", encoding="utf-8"):
    m = re.match(r"\s*(.+?)\s+(\d[\d.,]*)\s+(\d[\d.,]*)\s*$", l)
    if m and not m.group(1).strip().isdigit():
        nombre = (prev + " " + m.group(1)).strip() if prev else m.group(1).strip()
        prev = ""
        for s, x in zip(("Canals", "Laboulaye"), m.group(2, 3)):
            anexo[s].append(("", nombre, float(x.replace(".", "").replace(",", ".")) if "," in x else float(x), ""))
    elif l.strip().startswith("EBC"): prev = l.strip()
for s, v in anexo.items():
    ensayo("MJ25", "2024/25", s, "temprana", v, "Fuera del análisis conjunto de la red (vuelco y demora en la cosecha); Anexo I")
# Marcos Juárez 2025/26, informe preliminar
SIT26 = ["Justiniano Posse", "Arias", "Bell Ville", "Canals", "Camilo Aldao", "Marcos Juárez", "Inriville", "Río Cuarto", "Mattaldi"]
t26 = collections.defaultdict(list)
for l in open(H / "mj26.txt", encoding="utf-8"):
    m = re.match(r"\s*(\S+(?: CASAL)?)\s{2,}(.+?)\s{2,}((?:\d{4,5}\s+){9}\d{4,5})\s*$", l)
    if m and m.group(1) != "PROMEDIO":
        nums = [int(x) for x in m.group(3).split()]
        assert abs(sum(nums[:9]) / 9 - nums[9]) <= 2, l
        for s, x in zip(SIT26, nums): t26[s].append((m.group(1), m.group(2).strip(), float(x), ""))
for s, v in t26.items(): ensayo("MJ26", "2025/26", s, "temprana", v, "Informe preliminar")
# La Carlota tardía 2025/26
lc = [(m.group(1), m.group(2).strip(), float(m.group(3).replace(",", ".")), "")
      for l in open(H / "la_carlota_2025_26.txt", encoding="utf-8")
      if (m := re.match(r"\s*(\S+(?: Casal)?)\s{2,}(.+?)\s{2,}(\d{4},\d\d)", l))]
ensayo("LC26", "2025/26", "La Carlota", "tardía", lc)
# General Villegas 2024/25
gv = collections.defaultdict(list)
for r in csv.DictReader(open(H / "villegas_2024_25.csv", encoding="utf-8")):
    gv[r["epoca"]].append((r["empresa"], r["hibrido"], float(r["rinde_kg_ha"]), r["humedad_pct"]))
for e, v in gv.items(): ensayo("BN25", "2024/25", "General Villegas", "temprana" if e == "temprana" else "tardía", v)
# San Luis 2025/26: cada densidad de Villa Mercedes es un ensayo aparte
sl = collections.defaultdict(list)
for r in csv.DictReader(open(H.parent / "san_luis" / "san_luis_2025_26.csv", encoding="utf-8")):
    if r["cultivo"] == "Maíz":
        sl[(r["sitio"], r["tratamiento"])].append((r["empresa"], r["material"], float(r["valor_kg_ha"]), ""))
for (s, t), v in sl.items():
    ensayo("SL26", "2025/26", s, "tardía, " + t if s == "Villa Mercedes" else "tardía", v,
           "Siembra 17/12/2025, secano sin fertilizar" if s == "Villa Mercedes" else "Siembra 05/12/2025, secano; CV 9,7 %")

# nombre mostrado = la forma más frecuente de cada clave
formas = collections.defaultdict(collections.Counter)
for f in filas: formas[f["clave_nombre"]][f["nombre_en_planilla"]] += 1
for f in filas: f["hibrido"] = formas[f["clave_nombre"]].most_common(1)[0][0]
emp = collections.defaultdict(collections.Counter)
for f in filas:
    if f["empresa"]: emp[f["clave_nombre"]][f["empresa"].upper()] += 1
for f in filas: f["empresa"] = emp[f["clave_nombre"]].most_common(1)[0][0] if emp[f["clave_nombre"]] else ""
OUT.mkdir(parents=True, exist_ok=True)
orden = ["ensayo_id", "campana", "sitio", "epoca_siembra", "hibrido", "empresa", "clave_nombre", "nombre_en_planilla",
         "rinde_kg_ha", "rinde_relativo_pct", "humedad_pct", "referencia_san_luis"]
for nombre, t, campos in (("ensayos", ensayos, list(ensayos[0])), ("rindes", filas, orden)):
    with open(OUT / f"maiz_inta_2024_2026_{nombre}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos); w.writeheader(); w.writerows({k: r[k] for k in campos} for r in t)
print(len(ensayos), len(filas), len(formas), collections.Counter(e["referencia_san_luis"] for e in ensayos))
