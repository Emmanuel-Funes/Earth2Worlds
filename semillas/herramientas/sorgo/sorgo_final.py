"""Arma las tablas de sorgo granífero del ensayo comparativo de INTA EEA Manfredi, campaña 2024/25.

Fuente: Rosas, Senn, Ortiz y Maguire, Cartilla Digital Manfredi 2025/02 (repositorio INTA, handle 20.500.12123/22621).
El PDF lo bajó Hernán (el repositorio del INTA no abre desde la nube); el texto se sacó con pdftotext -layout.
Tabla 1 = empresa, tipo, ciclo y tanino; Tabla 2 = rinde, densidad, floración, altura y peso hectolítrico.
Uso: python sorgo_final.py <texto_del_pdf> <carpeta_salida>
"""
import csv, re, sys
from pathlib import Path

TXT, OUT = Path(sys.argv[1]), Path(sys.argv[2])
URL = "https://repositorio.inta.gob.ar/handle/20.500.12123/22621"
lineas = TXT.read_text(encoding="utf-8").splitlines()
# en la Tabla 2 algunos nombres van abreviados o sin el sufijo de la Tabla 1
ALIAS = {"TOB 1078": "TOB 1078 IG", "N 311 AB": "NUGRAIN 311 AB", "30 N 50 P": "NUGRAIN 30N50 P", "SYT 72-72GR": "SYT 70-72GR"}
EMPRESAS = ["Argenetics Semillas", "Gentos SA", "Origo", "Produsem", "Nufarm", "Peman", "ACA", "Radixagro", "Tecnosorgo",
            "Genesis", "Tobin", "SYT", "Quimarsem", "INTA"]
t1 = {}
for l in lineas:
    m = re.match(r"\s*(" + "|".join(EMPRESAS) + r")\s{1,}(.+?)(?:\s{2,}(granífero|Granífero|DP)\s+(\S+(?:\s\S+)?)(?:\s{2,}(alto|medio))?)?\s*$", l)
    if m and not m.group(2).startswith(("Hibrido",)):
        t1[m.group(2).strip()] = dict(empresa=m.group(1), tipo=(m.group(3) or "").lower().replace("dp", "doble propósito"),
                                      ciclo=(m.group(4) or "").replace("intem", "intermedio"), tanino=m.group(5) or "")
filas = []
for l in lineas:
    m = re.match(r"\s*(.+?)\s{2,}(\d{1,2}-ene)\s+(\d{6})\s+(\d{4})\s+(\d{3})\s+(\d{2})\s+([\d.]+)\s*$", l)
    if m and m.group(1).strip() != "Promedio":
        n = m.group(1).strip()
        oficial = ALIAS.get(n, n)
        a = t1.get(oficial, {})
        filas.append(dict(hibrido=oficial, nombre_en_planilla=n, empresa=a.get("empresa", ""), tipo=a.get("tipo", ""), ciclo=a.get("ciclo", ""),
                          tanino=a.get("tanino", ""), rinde_kg_ha=int(m.group(4)), floracion=m.group(2), dias_a_floracion=int(m.group(6)),
                          panojas_ha=int(m.group(3)), altura_cm=int(m.group(5)), peso_hectolitrico=float(m.group(7))))
media = sum(f["rinde_kg_ha"] for f in filas) / len(filas)
assert len(filas) == 40 and round(media) == 6798, (len(filas), media)  # 40 híbridos y media impresa 6798 kg/ha
assert all(f["empresa"] for f in filas), [f["hibrido"] for f in filas if not f["empresa"]]
eid = "SORGO-MANFREDI-2024-25"
for f in filas:
    f.update(ensayo_id=eid, campana="2024/25", sitio="Manfredi", rinde_relativo_pct=round(100 * f["rinde_kg_ha"] / media, 1),
             diferencia_con_el_mejor_kg_ha=max(x["rinde_kg_ha"] for x in filas) - f["rinde_kg_ha"],
             referencia_san_luis="SEMIARIDA_VECINA (centro de Córdoba)")
ensayo = [dict(ensayo_id=eid, campana="2024/25", sitio="Manfredi", provincia="Córdoba", siembra="30/10/2024", antecesor="soja",
               n_hibridos=len(filas), rinde_medio_kg_ha=round(media), dms_kg_ha=1344, cv_pct=12.2, lluvia_ciclo_mm=594,
               diseno="alfa látice, 3 repeticiones, 200 kg/ha de urea", referencia_san_luis="SEMIARIDA_VECINA (centro de Córdoba)",
               nota="Un solo sitio y una campaña. Diferencias menores a 1344 kg/ha no son significativas.", fuente_url=URL)]
orden = ["ensayo_id", "campana", "sitio", "hibrido", "empresa", "tipo", "ciclo", "tanino", "nombre_en_planilla", "rinde_kg_ha",
         "rinde_relativo_pct", "diferencia_con_el_mejor_kg_ha", "floracion", "dias_a_floracion", "panojas_ha", "altura_cm",
         "peso_hectolitrico", "referencia_san_luis"]
OUT.mkdir(parents=True, exist_ok=True)
for nombre, t, campos in (("ensayos", ensayo, list(ensayo[0])), ("rindes", filas, orden)):
    with open(OUT / f"sorgo_inta_manfredi_2024_25_{nombre}.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campos); w.writeheader(); w.writerows({k: r[k] for k in campos} for r in t)
print(len(filas), round(media))
