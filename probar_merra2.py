"""Prueba real contra MERRA-2 (respaldo de POWER). Se usa desde GitHub (Actions → "Probar MERRA-2 (respaldo del clima)")."""

import sys
import time
from datetime import date

from rotaterra.fuentes.merra2 import obtener_clima

lat, lon = float(sys.argv[1]), float(sys.argv[2])
desde, hasta = date.fromisoformat(sys.argv[3]), date.fromisoformat(sys.argv[4])

inicio = time.time()
clima = obtener_clima("lote-prueba", lat, lon, desde, hasta)
print(f"\nRespaldo MERRA-2 (temperatura y radiación) en ({lat}, {lon}) del {desde} al {hasta} · {time.time() - inicio:.0f} s\n")
por_fecha = {}
for o in clima:
    por_fecha.setdefault(o.fecha, {})[o.variable] = o.valor
print(f"{'Fecha':<12}{'Máx °C':>8}{'Mín °C':>8}{'MJ/m²':>8}")
fmt = lambda v: "  —" if v is None else f"{v:.1f}"
for fecha, v in sorted(por_fecha.items()):
    print(f"{fecha!s:<12}{fmt(v.get('temp_max')):>8}{fmt(v.get('temp_min')):>8}{fmt(v.get('radiacion')):>8}")
if not por_fecha:
    print("MERRA-2 todavía no publicó esas fechas (sale con ~1 mes de retraso).")
