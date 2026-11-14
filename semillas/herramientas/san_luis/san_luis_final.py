"""Arma las tablas del informe "Ensayos agrícolas en la provincia de San Luis, campaña 2025-2026" (INTA EEA San Luis + UNSL).

Información Técnica N.º 213, septiembre 2026, 81 págs. Es el único informe con ensayos hechos dentro de la provincia.
Transcripción a mano en san_luis_2025_26.csv (tablas en texto; trigo y sorgo salen de los rótulos de las figuras 7 y 2).
Cada ensayo se controla contra el promedio impreso. Los sorgos vienen sin nombre en el informe (solo empresa y número).
La soja de Comandante Granville ya está en la RECSO; Villa Mercedes se perdió.
Uso: python san_luis_final.py <carpeta_herramienta> <carpeta_salida>
"""
import collections, csv, sys
from pathlib import Path

H, OUT = Path(sys.argv[1]), Path(sys.argv[2])
URL = "https://repositorio.inta.gob.ar/xmlui/handle/20.500.12123/27891"
ENSAYOS = {
    "MAIZ-DENSIDADES-VM": dict(cultivo="Maíz", sitio="Villa Mercedes", lugar="EEA INTA San Luis", suelo="Ustipsament típico, areno franco (serie Cramer)",
                               siembra="17/12/2025", manejo="Secano, sin fertilizar, antecesor alfalfa 5 años", paginas="7-10",
                               nota="Dos densidades. Una sola campaña y sitio: el informe aclara que no es extrapolable."),
    "MAIZ-HIBRIDOS-TILISARAO": dict(cultivo="Maíz", sitio="Tilisarao", lugar="Campo Don Andrés (UNSL-productor)", suelo="Haplustol éntico, franco (serie Naschel)",
                                    siembra="05/12/2025", manejo="Secano, siembra directa sobre soja, 46.819 sem/ha", paginas="19-27",
                                    nota="Testigos apareados (BASF 7344 VT3P); CV 9,7 %. La fila TESTIGO no se carga."),
    "TRIGO-KLEIN-VM": dict(cultivo="Trigo", sitio="Villa Mercedes", lugar="Campo experimental FICA-UNSL", suelo="Haplustol ácuico, franco arenoso (serie Villa Reynolds)",
                           siembra="19/06/2025", manejo="Sin limitaciones hídricas ni nutricionales", paginas="62-69",
                           nota="Seis variedades Klein; sin diferencias significativas entre ellas (DGC 0,05). Valores leídos del rótulo de la figura 7."),
    "SORGO-VM": dict(cultivo="Sorgo", sitio="Villa Mercedes", lugar="EEA INTA San Luis", suelo="Ustipsament típico, areno franco (serie Cramer)",
                     siembra="02/12/2025", manejo="Secano, sin fertilizar, antecesor alfalfa", paginas="43-48",
                     nota="El informe no da el nombre de los híbridos, solo empresa y número de material."),
    "ALGODON-TILISARAO": dict(cultivo="Algodón", sitio="Tilisarao", lugar="Campo Don Andrés (UNSL-productor)", suelo="Haplustol éntico, franco (serie Naschel)",
                              siembra="11/11/2025", manejo="Dos distancias entre surcos; granizo 14/12/2025 con 60 % de plantas perdidas", paginas="74-80",
                              nota="Un solo cultivar del INTA; el ensayo compara distancias, no cultivares."),
}
# promedio impreso de cada ensayo (tratamiento, variable) para controlar la transcripción
IMPRESO = {("MAIZ-DENSIDADES-VM", "densidad alta 8.5 pl/m²"): 7408, ("MAIZ-DENSIDADES-VM", "densidad baja 5.0 pl/m²"): 5825,
           ("MAIZ-HIBRIDOS-TILISARAO", "secano"): 8522, ("TRIGO-KLEIN-VM", "riego sin limitaciones"): 6357}

filas = list(csv.DictReader(open(H / "san_luis_2025_26.csv", encoding="utf-8")))
grupos = collections.defaultdict(list)
for f in filas:
    grupos[(f["ensayo"], f["tratamiento"], f["variable"])].append(float(f["valor_kg_ha"]))
media = {k: sum(v) / len(v) for k, v in grupos.items()}
for (e, t), m in IMPRESO.items():
    assert abs(media[(e, t, "grano")] - m) <= 2, (e, t, media[(e, t, "grano")])
sorgo_grano = [float(f["valor_kg_ha"]) for f in filas if f["ensayo"] == "SORGO-VM" and f["variable"] == "grano"]
assert round(sum(sorgo_grano) / len(sorgo_grano)) == 3912  # "Promedio ensay." de la figura 3

rindes = []
for f in filas:
    m = media[(f["ensayo"], f["tratamiento"], f["variable"])]
    rindes.append(dict(ensayo_id=f["ensayo"], campana="2025/26", cultivo=f["cultivo"], sitio=f["sitio"], tratamiento=f["tratamiento"],
                       cultivar=f["material"], empresa=f["empresa"], variable=f["variable"], rinde_kg_ha=round(float(f["valor_kg_ha"])),
                       rinde_relativo_pct=round(100 * float(f["valor_kg_ha"]) / m, 1) if len(grupos[(f["ensayo"], f["tratamiento"], f["variable"])]) > 1 else "",
                       referencia_san_luis="SAN_LUIS (ensayo en la provincia)"))
ensayos = [dict(ensayo_id=e, campana="2025/26", provincia="San Luis", **d,
                n_materiales=len({f["material"] for f in filas if f["ensayo"] == e}), referencia_san_luis="SAN_LUIS (ensayo en la provincia)",
                fuente="INTA EEA San Luis + FICA-UNSL, Información Técnica N.º 213 (sep. 2026)", fuente_url=URL)
           for e, d in ENSAYOS.items()]
OUT.mkdir(parents=True, exist_ok=True)
for nombre, t in (("ensayos", ensayos), ("rindes", rindes)):
    with open(OUT / f"inta_san_luis_2025_26_{nombre}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(t[0])); w.writeheader(); w.writerows(t)
print(len(ensayos), len(rindes))
