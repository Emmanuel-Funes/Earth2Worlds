"""Prueba real de los meses de suelo desnudo del lote (MODIS, 5 años). Actions → "Probar suelo desnudo".
Necesita Earthdata."""

import sys
import time

from rotaterra.fuentes import suelo_desnudo
from rotaterra.geo import poligono_desde_esquinas

poligono = poligono_desde_esquinas(sys.argv[1])
inicio = time.time()
obs = suelo_desnudo.obtener("lote-prueba", poligono)
print(f"\nSuelo desnudo del lote con MODIS, últimos {suelo_desnudo.MESES_PERIODO} meses · {time.time() - inicio:.0f} s\n")
for o in obs:
    valor = "—" if o.valor is None else f"{o.valor:g} {o.unidad}"
    print(f"· {o.variable}: {valor} · {o.calidad} · {o.nota}")
