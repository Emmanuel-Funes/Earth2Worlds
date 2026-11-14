"""Prueba real contra Sentinel-3 SLSTR LST nocturna (segundo respaldo de heladas).
Actions → "Probar Sentinel-3 (heladas)". Necesita COPERNICUS_USERNAME / COPERNICUS_PASSWORD."""

import sys
import time
from collections import Counter
from datetime import date

from rotaterra.fuentes import sentinel3_heladas as s3
from rotaterra.geo import poligono_desde_esquinas

esquinas, desde, hasta = sys.argv[1], sys.argv[2], sys.argv[3]
poligono = poligono_desde_esquinas(esquinas)
inicio = time.time()
try:
    obs = s3.obtener_heladas("lote-prueba", poligono, date.fromisoformat(desde), date.fromisoformat(hasta))
except s3.ErrorSentinel3Heladas as error:
    # diagnóstico sin credenciales a la vista: qué productos ve el catálogo público
    print(f"Error: {error}\n")
    import httpx
    for p in s3.buscar_productos(httpx.Client(timeout=120), poligono, date.fromisoformat(desde),
                                 date.fromisoformat(hasta))[:6]:
        print("  ", p.get("Id"), p.get("Name"), p.get("Online"))
    raise

print(f"\nTemperatura de superficie nocturna del lote (Sentinel-3A/3B SLSTR SL_2_LST, 1 km, RESPALDO de VIIRS "
      f"después de MODIS) del {desde} al {hasta} · {time.time() - inicio:.0f} s\n")
print(f"{'Fecha':<12}{'T sup °C':>9}  {'Calidad':<11} Detalle")
for o in obs:
    valor = "   —   " if o.valor is None else f"{o.valor:6.1f}"
    print(f"{o.fecha!s:<12}{valor:>9}  {o.calidad:<11} {o.nota}")

con_dato = [o for o in obs if o.valor is not None]
heladas = [o for o in con_dato if o.valor <= s3.UMBRAL_HELADA]
print(f"\n{len(obs)} noches · calidad {dict(Counter(o.calidad for o in obs))} · "
      f"{len(con_dato)} con dato · {len(heladas)} con riesgo de helada (≤ 0 °C)")
if con_dato:
    mas_fria = min(con_dato, key=lambda o: o.valor)
    print(f"Noche más fría: {mas_fria.fecha} con {mas_fria.valor:.1f} °C de superficie")
