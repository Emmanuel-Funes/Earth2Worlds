"""Prueba real contra LANCE MODIS NRT (NDVI del día, respaldo de HLS). Se usa desde GitHub (Actions → "Probar MODIS NRT (NDVI del día)")."""

import sys
import time
from datetime import date, datetime, timedelta, timezone

from rotaterra.fuentes.modis_nrt import obtener_ndvi
from rotaterra.geo import poligono_desde_esquinas

lat, lon = float(sys.argv[1]), float(sys.argv[2])
hoy = (datetime.now(timezone.utc) - timedelta(hours=3)).date()  # día de hoy en Argentina
desde = date.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else hoy - timedelta(days=8)
hasta = date.fromisoformat(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] else hoy
lado = float(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[5] else 0.01  # ~1 km de lado, ~100 ha

poligono = poligono_desde_esquinas(f"{lat + lado / 2}, {lon - lado / 2}; {lat + lado / 2}, {lon + lado / 2}; "
                                   f"{lat - lado / 2}, {lon + lado / 2}; {lat - lado / 2}, {lon - lado / 2}")
inicio = time.time()
ndvi = obtener_ndvi("lote-prueba", poligono, desde, hasta)
print(f"MODIS NRT (NDVI del día) en ({lat}, {lon}), lado {lado}°, del {desde} al {hasta} · {time.time() - inicio:.0f} s\n")
for o in ndvi:
    valor = "  —" if o.valor is None else f"{o.valor:.3f}"
    print(f"{o.fecha!s:<12}{valor:>7}  {o.calidad:<10}  {o.nota.split(' · ', 1)[-1]}")
if not ndvi:
    sys.exit("LANCE no tiene ningún archivo MOD13Q4N del lote en el período")
