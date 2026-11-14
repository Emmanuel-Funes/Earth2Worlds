"""Prueba real contra MODIS (respaldo del NDVI). Se usa desde GitHub (Actions → "Probar MODIS (NDVI de respaldo)")."""

import sys
import time
from datetime import date

from rotaterra.fuentes.modis import obtener_ndvi
from rotaterra.geo import poligono_desde_esquinas

esquinas, desde, hasta = sys.argv[1], sys.argv[2], sys.argv[3]
inicio = time.time()
obs = obtener_ndvi("lote-prueba", poligono_desde_esquinas(esquinas),
                   date.fromisoformat(desde), date.fromisoformat(hasta))

print(f"\nNDVI del lote (MODIS Terra, 250 m, compuestos de 16 días) del {desde} al {hasta} · "
      f"{time.time() - inicio:.0f} s\n")
print(f"{'Fecha':<12}{'NDVI':>7}  {'Calidad':<11} Detalle")
for o in obs:
    valor = "  —  " if o.valor is None else f"{o.valor:5.2f}"
    print(f"{o.fecha!s:<12}{valor:>7}  {o.calidad:<11} {o.nota}")
print(f"\n{len(obs)} compuestos, {sum(1 for o in obs if o.calidad == 'buena')} con el lote despejado.")
