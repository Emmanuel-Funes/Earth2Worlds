"""Prueba real del radar NISAR sobre el lote. Actions → "Probar NISAR (radar)". Necesita Earthdata."""

import sys
import time
from datetime import date

from rotaterra.fuentes import nisar
from rotaterra.geo import poligono_desde_esquinas

esquinas, desde, hasta = sys.argv[1], sys.argv[2], sys.argv[3]
poligono = poligono_desde_esquinas(esquinas)
inicio = time.time()
obs = nisar.obtener("lote-prueba", poligono, date.fromisoformat(desde), date.fromisoformat(hasta))
hv = {o.fecha: o.valor for o in obs if o.variable == "radar_hv_db"}
print(f"\nRadar NISAR (banda L, 20 m) del lote del {desde} al {hasta} · {time.time() - inicio:.0f} s\n")
print(f"{'Fecha':<12}{'HH dB':>8}{'HV dB':>8}  {'Calidad':<11} Detalle")
for o in obs:
    if o.variable != "radar_hh_db":
        continue
    hh = "   —  " if o.valor is None else f"{o.valor:6.2f}"
    v = "   —  " if hv.get(o.fecha) is None else f"{hv[o.fecha]:6.2f}"
    print(f"{o.fecha!s:<12}{hh:>8}{v:>8}  {o.calidad:<11} {o.nota}")
print(f"\n{sum(o.variable == 'radar_hh_db' for o in obs)} pasadas · "
      f"{sum(o.valor is not None for o in obs if o.variable == 'radar_hh_db')} con dato")
