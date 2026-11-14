"""Prueba real contra GLDAS (respaldo de humedad y ET). Actions → "Probar GLDAS (humedad y ET)". Necesita Earthdata."""

import sys
import time
from datetime import date

from rotaterra.fuentes import gldas
from rotaterra.geo import poligono_desde_esquinas

esquinas, desde, hasta = sys.argv[1], sys.argv[2], sys.argv[3]
poligono = poligono_desde_esquinas(esquinas)

from shapely.geometry import shape

centro = shape(poligono).centroid
lat, lon = round(centro.y, 6), round(centro.x, 6)

for titulo, funcion in (("Humedad del suelo", gldas.obtener_humedad), ("Evapotranspiración real", gldas.obtener_et)):
    print(f"\n=== {titulo} (GLDAS Noah 0,25 °, respaldo) · centro {lat}, {lon} · del {desde} al {hasta} ===")
    inicio = time.time()
    obs = funcion("lote-prueba", lat, lon, date.fromisoformat(desde), date.fromisoformat(hasta))
    print(f"({time.time() - inicio:.0f} s)\n")
    print(f"{'Fecha':<12}{'Variable':<22}{'Valor':>8}  {'Calidad':<11} Detalle")
    for o in obs:
        valor = "   —   " if o.valor is None else f"{o.valor:6.3f}"
        print(f"{o.fecha!s:<12}{o.variable:<22}{valor:>8}  {o.calidad:<11} {o.nota}")
    con_dato = [o for o in obs if o.valor is not None]
    print(f"\n{len(obs)} observaciones · {len(con_dato)} con dato · "
          f"fuente {obs[0].fuente if obs else '—'}, resolución {obs[0].resolucion_m if obs else '—'} m")
