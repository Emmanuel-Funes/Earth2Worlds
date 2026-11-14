"""Prueba real de la ET de referencia FAO-56 con NASA POWER (spec 019).

Se usa desde GitHub (Actions → "Probar POWER (ET de referencia FAO-56)"). POWER es público: no usa credenciales.
"""

import sys
import time
from collections import Counter
from datetime import date

import httpx
from shapely.geometry import shape

from rotaterra.fuentes import et0_fao56 as fao
from rotaterra.geo import poligono_desde_esquinas

esquinas, desde, hasta = sys.argv[1], date.fromisoformat(sys.argv[2]), date.fromisoformat(sys.argv[3])
centro = shape(poligono_desde_esquinas(esquinas)).centroid  # el mismo punto que guarda la base
lat, lon = round(centro.y, 6), round(centro.x, 6)

inicio = time.time()
try:
    obs = fao.obtener_et0("lote-prueba", lat, lon, desde, hasta)
except fao.ErrorET0 as error:
    # diagnóstico: qué devuelve POWER (no hay secretos en juego)
    print(f"Error: {error}\n")
    respuesta = httpx.get(fao.URL_POWER, timeout=60, params={
        "parameters": ",".join(fao.PARAMETROS), "community": "AG", "latitude": lat, "longitude": lon,
        "start": desde.strftime("%Y%m%d"), "end": hasta.strftime("%Y%m%d"), "format": "JSON"})
    print(f"HTTP {respuesta.status_code}\n{respuesta.text[:2000]}")
    raise

print(f"\nET de referencia FAO-56 (Penman-Monteith) con NASA POWER en el centro del lote ({lat}, {lon}), "
      f"del {desde} al {hasta} · {time.time() - inicio:.1f} s")
print("Es la ET de un pasto de referencia, NO la ET real del cultivo (ET cultivo = Kc × ET0).\n")
print(f"{'Fecha':<12}{'ET0 mm/día':>11}  {'Calidad':<11} Detalle")
for o in obs:
    valor = "    —" if o.valor is None else f"{o.valor:5.2f}"
    print(f"{o.fecha!s:<12}{valor:>11}  {o.calidad:<11} {o.nota.split(' · ', 1)[-1]}")

validos = [o.valor for o in obs if o.valor is not None]
print(f"\n{len(obs)} días · calidad {dict(Counter(o.calidad for o in obs))}")
if validos:
    print(f"ET0 mínima {min(validos):.2f}, máxima {max(validos):.2f}, media {sum(validos) / len(validos):.2f} mm/día, "
          f"total {sum(validos):.1f} mm")
if not obs:
    sys.exit("POWER no devolvió ningún día")
