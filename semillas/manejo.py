"""Buenas prácticas de manejo (BPM) por cultivo: la guía del maní adaptada a cada cultivo extensivo de Argentina.

Hernán (30/10/2026) subió una guía práctica de maní (Colombia, variedad Tatuí 76) y pidió "adaptar esto para
Argentina" en todos los cultivos del banco. Se usan sus temas como plantilla (clima, siembra, suelo, densidad,
fertilización, plagas, cosecha...) y se llenan solo con datos del INTA, SENASA o normas argentinas, transcriptos
en datos/manejo_cultivos.csv con su fuente y cómo se verificó. Lo que no tiene fuente queda como "sin dato verificado".
"""
import csv
from pathlib import Path

CSV = Path(__file__).resolve().parent / "datos" / "manejo_cultivos.csv"
COLUMNAS = ["cultivo", "tema", "valor", "fuente", "fuente_url", "verificacion"]
SIN_DATO = "sin dato verificado"
TEMAS = [  # (tema, título) en el orden de la guía de maní
    ("clima", "Clima"), ("agua", "Agua y lluvias"), ("epoca_siembra", "Época de siembra"), ("suelo", "Suelo"),
    ("ph", "pH del suelo"), ("rotacion", "Rotación"), ("preparacion_suelo", "Preparación del suelo"),
    ("distancia_surcos", "Distancia entre surcos"), ("densidad", "Densidad de siembra"),
    ("profundidad", "Profundidad de siembra"), ("ciclo", "Ciclo"), ("fertilizacion", "Fertilización"),
    ("plagas", "Plagas"), ("malezas", "Malezas"), ("enfermedades", "Enfermedades"), ("cosecha", "Cosecha"),
    ("poscosecha", "Secado y almacenaje"),
]


def leer() -> list[dict]:
    with CSV.open(encoding="utf-8") as f:
        return [{k: r[k] for k in COLUMNAS} for r in csv.DictReader(f)]


def armar(cultivos: list[str]) -> list[dict]:
    """Datos transcriptos más una fila "sin dato verificado" por cada tema de la guía que falte en cada cultivo."""
    filas = leer()
    tiene = {(f["cultivo"], f["tema"].split(" (")[0]) for f in filas}
    for cultivo in sorted(set(cultivos)):
        for tema, _ in TEMAS:
            if (cultivo, tema) not in tiene:
                filas.append({"cultivo": cultivo, "tema": tema, "valor": SIN_DATO, "fuente": "", "fuente_url": "",
                              "verificacion": "falta fuente"})
    orden = {t: i for i, (t, _) in enumerate(TEMAS)}
    return sorted(filas, key=lambda f: (f["cultivo"], orden.get(f["tema"].split(" (")[0], 99), f["tema"]))
