"""Prueba real contra NASADEM (altimetría). Se usa desde GitHub (Actions → "Probar NASADEM (altimetría)")."""

import sys
import time

from rotaterra.fuentes.nasadem import obtener_altimetria
from rotaterra.geo import poligono_desde_esquinas

inicio = time.time()
obs = obtener_altimetria("lote-prueba", poligono_desde_esquinas(sys.argv[1]))

print(f"\nAltimetría del lote (NASADEM, 30 m, febrero de 2000) · {time.time() - inicio:.0f} s\n")
print(f"{'Variable':<26}{'Valor':>9}  {'Unidad':<6} {'Calidad':<11}")
for o in obs:
    valor = "—" if o.valor is None else f"{o.valor:g}"
    print(f"{o.variable:<26}{valor:>9}  {o.unidad:<6} {o.calidad:<11}")
print(f"\nDetalle: {obs[-1].nota}")
