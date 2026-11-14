"""Prueba real contra GOES-19 (heladas del día, respaldo de VIIRS).

Se usa desde GitHub (Actions → "Probar GOES-19 (heladas del día)").
"""

import sys
import time
from datetime import date, datetime, timedelta, timezone

from rotaterra.fuentes.goes_heladas import obtener_heladas

lat, lon = float(sys.argv[1]), float(sys.argv[2])
hoy = (datetime.now(timezone.utc) - timedelta(hours=3)).date()
desde = date.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else hoy - timedelta(days=4)
hasta = date.fromisoformat(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] else hoy

inicio = time.time()
heladas = obtener_heladas("lote-prueba", lat, lon, desde, hasta)
print(f"\nGOES-19, mínima de la madrugada en ({lat}, {lon}) del {desde} al {hasta} · {time.time() - inicio:.0f} s\n")
for o in heladas:
    valor = "  —" if o.valor is None else f"{o.valor:.1f}"
    print(f"{o.fecha}  {valor:>6} °C  {o.calidad:<10} {o.nota.split(' · ', 2)[-1]}")
if not any(o.valor is not None for o in heladas):
    sys.exit("GOES-19 no trajo ningún valor (puede ser nubes todos los días: revisar las notas)")
