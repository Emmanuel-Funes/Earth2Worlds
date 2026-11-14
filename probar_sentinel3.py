"""Prueba real contra Sentinel-3 (respaldo del NDVI). Actions → "Probar Sentinel-3 (NDVI de respaldo)". Necesita Earthdata."""

import sys
import time
from collections import Counter
from datetime import date

from rotaterra.fuentes import earthdata, sentinel3
from rotaterra.geo import poligono_desde_esquinas

esquinas, desde, hasta = sys.argv[1], sys.argv[2], sys.argv[3]
poligono = poligono_desde_esquinas(esquinas)
inicio = time.time()
try:
    obs = sentinel3.obtener_ndvi("lote-prueba", poligono, date.fromisoformat(desde), date.fromisoformat(hasta))
except sentinel3.ErrorSentinel3 as error:
    # diagnóstico sin credenciales a la vista: qué productos y pasadas ve CMR
    print(f"Error: {error}\n")
    cliente = earthdata.cliente_autorizado()
    for producto in sentinel3.PRODUCTOS:
        coleccion = earthdata.coleccion_vigente(cliente, producto)
        print(f"{producto}: colección {coleccion}")
        if coleccion:
            from shapely.geometry import shape
            for nombre, url in sentinel3.granulos(cliente, coleccion, date.fromisoformat(desde),
                                                  date.fromisoformat(hasta), shape(poligono).bounds)[:3]:
                print("  ", nombre, url)
    raise

print(f"\nNDVI del lote (Sentinel-3A/3B SYN L2, 300 m, una pasada por día) del {desde} al {hasta} · "
      f"{time.time() - inicio:.0f} s\n")
print(f"{'Fecha':<12}{'NDVI':>7}  {'Calidad':<11} Detalle")
for o in obs:
    valor = "  —  " if o.valor is None else f"{o.valor:5.2f}"
    print(f"{o.fecha!s:<12}{valor:>7}  {o.calidad:<11} {o.nota}")
con_dato = [o for o in obs if o.valor is not None]
print(f"\n{len(obs)} días con pasada · calidad {dict(Counter(o.calidad for o in obs))} · {len(con_dato)} con dato")
if con_dato:
    print(f"NDVI de {min(o.valor for o in con_dato):.2f} a {max(o.valor for o in con_dato):.2f} · "
          f"fuente {con_dato[0].fuente}, resolución {con_dato[0].resolucion_m} m")
