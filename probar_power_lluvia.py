"""Prueba real contra NASA POWER como respaldo de la lluvia de IMERG.

Se usa desde GitHub (Actions → "Probar POWER (lluvia de respaldo)"). No necesita credenciales.
"""

import sys
import time
from collections import Counter
from datetime import date

from shapely.geometry import shape

from rotaterra.fuentes import power_lluvia
from rotaterra.geo import poligono_desde_esquinas

# IMERG en el lote de prueba, 1 al 14 de enero de 2026 (spec 006): 32,0 mm en total, 22,5 mm el 13/1
IMERG_TOTAL, IMERG_13 = 32.0, 22.5

esquinas, desde, hasta = sys.argv[1], date.fromisoformat(sys.argv[2]), date.fromisoformat(sys.argv[3])
centro = shape(poligono_desde_esquinas(esquinas)).centroid
lat, lon = round(centro.y, 6), round(centro.x, 6)
lote = {"id": "lote-prueba", "lat": lat, "lon": lon}

(satelite,) = power_lluvia.SATELITES
inicio = time.time()
try:
    obs = satelite.pedir(lote, desde, hasta)
except power_lluvia.ErrorPowerLluvia as error:
    print(f"Error: {error}")
    causa = error.__cause__
    if getattr(causa, "response", None) is not None:  # diagnóstico: qué dijo POWER (no hay secretos en juego)
        print(f"POWER respondió {causa.response.status_code}: {causa.response.text[:800]}")
    raise

print(f"\nLluvia NASA POWER ({power_lluvia.PARAMETRO}, día UTC) como respaldo de IMERG · "
      f"satélite {satelite.nombre} (respaldo de {satelite.respaldo_de}, orden {satelite.orden})")
print(f"Centro del lote ({lat}, {lon}) · del {desde} al {hasta} · {time.time() - inicio:.1f} s\n")
print(f"{'Fecha':<12}{'Lluvia mm':>10}  {'Calidad':<11} Nota")
for o in obs:
    valor = "—" if o.valor is None else f"{o.valor:.2f}"
    print(f"{o.fecha!s:<12}{valor:>10}  {o.calidad:<11} {o.nota}")

total = sum(o.valor for o in obs if o.valor is not None)
print(f"\n{len(obs)} días · calidad {dict(Counter(o.calidad for o in obs))} · total {total:.1f} mm")
print(f"Variable {obs[0].variable} en {obs[0].unidad}, fuente {obs[0].fuente}, resolución {obs[0].resolucion_m} m")

if (desde, hasta) == (date(2026, 1, 1), date(2026, 1, 14)):
    dia13 = next((o.valor for o in obs if o.fecha == date(2026, 1, 13)), None)
    print(f"\nComparación con IMERG en el mismo período: POWER {total:.1f} mm contra IMERG {IMERG_TOTAL:.1f} mm; "
          f"13/1: POWER {'sin dato' if dia13 is None else f'{dia13:.1f} mm'} contra IMERG {IMERG_13:.1f} mm")

if len(obs) != (hasta - desde).days + 1:
    sys.exit("Error: no vino un valor por cada día pedido")
