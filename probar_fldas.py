"""Prueba real contra FLDAS (respaldo de humedad del suelo). Actions → "Probar FLDAS (humedad)". Necesita Earthdata."""

import sys
import time
from collections import Counter
from datetime import date

from shapely.geometry import shape

from rotaterra.fuentes import earthdata, fldas
from rotaterra.geo import poligono_desde_esquinas

esquinas, desde, hasta = sys.argv[1], sys.argv[2], sys.argv[3]
centro = shape(poligono_desde_esquinas(esquinas)).centroid
inicio = time.time()
try:
    obs = fldas.obtener_humedad("lote-prueba", centro.y, centro.x, date.fromisoformat(desde), date.fromisoformat(hasta))
except fldas.ErrorFLDAS as error:
    print(f"Error: {error}\n")
    cliente = earthdata.cliente_autorizado()
    print("Colección FLDAS:", earthdata.coleccion_vigente(cliente, fldas.PRODUCTO))
    raise

print(f"\nHumedad del suelo del lote (FLDAS Noah 0,1°, RESPALDO de SMAP) del {desde} al {hasta} · "
      f"centro ({centro.y:.4f}, {centro.x:.4f}) · {time.time() - inicio:.0f} s\n")
print(f"{'Mes':<12}{'Variable':<22}{'m³/m³':>8}  {'Calidad':<11} Detalle")
for o in obs:
    valor = "   —  " if o.valor is None else f"{o.valor:6.3f}"
    print(f"{o.fecha!s:<12}{o.variable:<22}{valor:>8}  {o.calidad:<11} {o.nota}")

con_dato = [o for o in obs if o.valor is not None]
print(f"\n{len(obs)} observaciones · calidad {dict(Counter(o.calidad for o in obs))} · {len(con_dato)} con dato")
if con_dato:
    print(f"Fuente {con_dato[0].fuente}, resolución {con_dato[0].resolucion_m} m. "
          f"GLDAS dio ~0,267 y SMAP anda en ese orden: FLDAS tiene que quedar parecido.")
