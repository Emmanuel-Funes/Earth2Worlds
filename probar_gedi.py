"""Prueba real de GEDI (cobertura de la vegetación de la zona) sobre el lote. Actions → "Probar GEDI (zona del lote)".
Necesita Earthdata."""

import sys
import time

from rotaterra.fuentes import gedi
from rotaterra.geo import poligono_desde_esquinas

poligono = poligono_desde_esquinas(sys.argv[1])
inicio = time.time()
obs = gedi.obtener("lote-prueba", poligono)
print(f"\nGEDI en el lote y {gedi.ZONA_KM:g} km alrededor, últimos {gedi.ANIOS} años · {time.time() - inicio:.0f} s\n")
for o in obs:
    valor = "—" if o.valor is None else f"{o.valor:g} {o.unidad}"
    print(f"· {o.variable}: {valor} · {o.calidad} · último disparo {o.fecha} · {o.nota}")
