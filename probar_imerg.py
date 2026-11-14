"""Prueba real contra IMERG (lluvia). Se usa desde GitHub (Actions → "Probar IMERG (lluvia)")."""

import sys
import time
from datetime import date

from rotaterra.fuentes.imerg import obtener_lluvia

lat, lon = float(sys.argv[1]), float(sys.argv[2])
desde, hasta = date.fromisoformat(sys.argv[3]), date.fromisoformat(sys.argv[4])

inicio = time.time()
lluvia = obtener_lluvia("lote-prueba", lat, lon, desde, hasta)
print(f"\nLluvia GPM IMERG en ({lat}, {lon}) del {desde} al {hasta} · {time.time() - inicio:.0f} s\n")
print(f"{'Fecha':<12}{'mm':>7}  {'Calidad':<11} Producto")
for o in lluvia:
    mm = "sin dato" if o.valor is None else f"{o.valor:.1f}"
    print(f"{o.fecha!s:<12}{mm:>7}  {o.calidad:<11} {o.nota}")
total = sum(o.valor for o in lluvia if o.valor is not None)
print(f"\nLluvia acumulada: {total:.1f} mm en {len(lluvia)} días.")
