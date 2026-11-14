"""Prueba real contra IMERG Early (lluvia del día, respaldo de IMERG).

Se usa desde GitHub (Actions → "Probar IMERG Early (lluvia del día)").
"""

import sys
import time
from datetime import date, datetime, timedelta, timezone

from rotaterra.fuentes import earthdata
from rotaterra.fuentes.imerg_early import DIARIO, MEDIA_HORA, obtener_lluvia

lat, lon = float(sys.argv[1]), float(sys.argv[2])
hoy = datetime.now(timezone.utc).date()  # IMERG usa el día UTC
desde = date.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else hoy - timedelta(days=3)
hasta = date.fromisoformat(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] else hoy

cliente = earthdata.cliente_autorizado()
for producto in (DIARIO, MEDIA_HORA):
    coleccion = earthdata.coleccion_vigente(cliente, producto)
    hallados = earthdata.archivos(cliente, coleccion, hasta - timedelta(days=1), hasta) if coleccion else []
    print(f"{producto}: colección {coleccion} · {len(hallados)} archivos con OPeNDAP entre ayer y hoy"
          + (f" · último {hallados[-1][0]}" if hallados else ""))

inicio = time.time()
lluvia = obtener_lluvia("lote-prueba", lat, lon, desde, hasta)
print(f"\nIMERG Early en ({lat}, {lon}) del {desde} al {hasta} (días UTC) · {time.time() - inicio:.0f} s\n")
for o in lluvia:
    valor = "  —" if o.valor is None else f"{o.valor:.1f}"
    print(f"{o.fecha}  {valor:>6} mm  {o.calidad:<10} {o.nota}")
if not any(o.valor is not None for o in lluvia):
    sys.exit("IMERG Early no trajo ningún valor")
