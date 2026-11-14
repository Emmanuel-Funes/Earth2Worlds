"""Prueba real contra SMAP NRT (humedad del día, respaldo de SMAP). Se usa desde GitHub (Actions → "Probar SMAP NRT (humedad del día)")."""

import sys
import time
from datetime import date, datetime, timedelta, timezone

from rotaterra.fuentes.smap_nrt import obtener_humedad

lat, lon = float(sys.argv[1]), float(sys.argv[2])
hoy = (datetime.now(timezone.utc) - timedelta(hours=3)).date()  # día de hoy en Argentina
desde = date.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else hoy - timedelta(days=4)
hasta = date.fromisoformat(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] else hoy

inicio = time.time()
humedad = obtener_humedad("lote-prueba", lat, lon, desde, hasta)
print(f"SMAP NRT (humedad del día) en ({lat}, {lon}) del {desde} al {hasta} · {time.time() - inicio:.0f} s\n")
for o in humedad:
    valor = "  —" if o.valor is None else f"{o.valor:.3f}"
    print(f"{o.fecha!s:<12}{valor:>7} m³/m³  {o.calidad:<10}  {o.nota.split(' · ', 1)[-1]}")
if not [o for o in humedad if o.valor is not None]:
    sys.exit("SMAP NRT no trajo ningún valor de humedad")
