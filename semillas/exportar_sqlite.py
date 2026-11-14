"""Pasa el banco de semillas armado por construir_base a un solo archivo SQLite para la API (spec 057).

Hernán eligió (29/10/2026) un archivo SQLite que viaja con la API en Render: sin servidor de base de datos.
Cada CSV de la salida es una tabla con el mismo nombre. Las columnas que son números en todas las filas
quedan como INTEGER o REAL; el resto como TEXT, tal cual vino. El manifiesto va en la tabla `_manifiesto`.

Uso:
    python -m semillas.construir_base <catalogo_inase.csv> salida/ --fecha-corte 2026-10-28
    python -m semillas.exportar_sqlite salida/ semillas.sqlite
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
from pathlib import Path

# columnas por las que la API busca: se indexan si la tabla las tiene
INDICES = ["cultivar_id", "perfil_ssd", "especie", "ensayo_id", "cultivar", "hibrido", "campana", "referencia_san_luis",
           "obtentor_inta", "nombre_busqueda"]
ENTERO = re.compile(r"-?\d+")
REAL = re.compile(r"-?\d+\.\d+")


def _tipo(valores: list[str]) -> str:
    llenos = [v for v in valores if v != ""]
    # un cero adelante ("0357") es un nombre, no un número
    if llenos and all(ENTERO.fullmatch(v) and not (len(v) > 1 and v.lstrip("-").startswith("0")) for v in llenos):
        return "INTEGER"
    if llenos and all(ENTERO.fullmatch(v) or REAL.fullmatch(v) for v in llenos):
        return "REAL"
    return "TEXT"


def _valor(v: str, tipo: str):
    if v == "":
        return None
    return int(v) if tipo == "INTEGER" else float(v) if tipo == "REAL" else v


def exportar(carpeta: Path, destino: Path) -> dict[str, int]:
    """Escribe `destino` desde cero con una tabla por CSV de `carpeta`. Devuelve filas por tabla."""
    temporal = destino.with_suffix(".tmp")
    temporal.unlink(missing_ok=True)
    filas_por_tabla = {}
    db = sqlite3.connect(temporal)
    try:
        for ruta in sorted(carpeta.glob("*.csv")):
            with ruta.open(encoding="utf-8-sig", newline="") as f:
                lector = csv.reader(f)
                columnas = next(lector)
                filas = [r for r in lector if len(r) == len(columnas)]
            if columnas == ["sin_filas"]:
                continue
            tipos = [_tipo([r[i] for r in filas]) for i in range(len(columnas))]
            tabla = ruta.stem
            db.execute(f'CREATE TABLE "{tabla}" ({", ".join(f"{chr(34)}{c}{chr(34)} {t}" for c, t in zip(columnas, tipos))})')
            db.executemany(f'INSERT INTO "{tabla}" VALUES ({", ".join("?" * len(columnas))})',
                           [[_valor(v, t) for v, t in zip(r, tipos)] for r in filas])
            for c in INDICES:
                if c in columnas:
                    db.execute(f'CREATE INDEX "ix_{tabla}_{c}" ON "{tabla}" ("{c}")')
            filas_por_tabla[tabla] = len(filas)
        manifiesto = carpeta / "manifiesto.json"
        datos = json.loads(manifiesto.read_text(encoding="utf-8")) if manifiesto.exists() else {}
        db.execute("CREATE TABLE _manifiesto (clave TEXT PRIMARY KEY, valor TEXT)")
        db.executemany("INSERT INTO _manifiesto VALUES (?, ?)",
                       [(k, v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)) for k, v in datos.items()])
        db.commit()
        db.execute("VACUUM")
    finally:
        db.close()
    temporal.replace(destino)
    return filas_por_tabla


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("carpeta", type=Path, help="carpeta de salida de construir_base (CSV + manifiesto.json)")
    p.add_argument("destino", type=Path, help="archivo .sqlite a escribir")
    a = p.parse_args()
    filas = exportar(a.carpeta, a.destino)
    print(json.dumps({"tablas": len(filas), "filas": sum(filas.values()), "archivo": str(a.destino)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
