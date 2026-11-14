"""Prueba real contra HWSD (respaldo de suelo). Actions → "Probar HWSD (suelo)". Necesita Earthdata."""

import sys
import time

from rotaterra.fuentes import hwsd_suelo
from rotaterra.geo import poligono_desde_esquinas

esquinas = sys.argv[1]
poligono = poligono_desde_esquinas(esquinas)
inicio = time.time()
obs = hwsd_suelo.obtener_suelo("lote-prueba", poligono)

from shapely.geometry import shape

centro = shape(poligono).centroid
print(f"\nSuelo del lote según HWSD (respaldo de GeoINTA) · centro {centro.y:.4f}, {centro.x:.4f} · "
      f"{time.time() - inicio:.0f} s\n")
print(f"{'Variable':<22}{'Valor':>8}  {'Calidad':<11} Detalle")
for o in obs:
    valor = "   —   " if o.valor is None else f"{o.valor:6.2f}"
    print(f"{o.variable:<22}{valor:>8}  {o.calidad:<11} {o.nota}")

con_dato = [o for o in obs if o.valor is not None]
print(f"\n{len(obs)} variables · {len(con_dato)} con dato · fuente {obs[0].fuente if obs else '—'}, "
      f"resolución {obs[0].resolucion_m if obs else '—'} m")
