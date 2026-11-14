"""Prueba real de heladas por zona con ECOSTRESS 70 m. Actions → "Probar ECOSTRESS (heladas por zona)". Necesita Earthdata."""

import sys
import time
from collections import Counter
from datetime import date

from rotaterra.fuentes import ecostress_heladas
from rotaterra.geo import poligono_desde_esquinas

esquinas, desde, hasta = sys.argv[1], sys.argv[2], sys.argv[3]
poligono = poligono_desde_esquinas(esquinas)
inicio = time.time()
obs = ecostress_heladas.obtener("lote-prueba", poligono, date.fromisoformat(desde), date.fromisoformat(hasta))
minimas = [o for o in obs if o.variable == "temp_sup_min_70m_c"]
helada = {o.fecha: o.valor for o in obs if o.variable == "helada_superficie_pct"}
print(f"\nHeladas por zona del lote (ECOSTRESS LST nocturna, 70 m) del {desde} al {hasta} · {time.time() - inicio:.0f} s\n")
print(f"{'Noche':<12}{'Mín °C':>8}{'% ≤0 °C':>9}  {'Calidad':<11} Detalle")
for o in minimas:
    valor = "   —  " if o.valor is None else f"{o.valor:6.1f}"
    pct = "   —  " if helada.get(o.fecha) is None else f"{helada[o.fecha]:6.0f}"
    print(f"{o.fecha!s:<12}{valor:>8}{pct:>9}  {o.calidad:<11} {o.nota}")
con_dato = [o for o in minimas if o.valor is not None]
print(f"\n{len(minimas)} noches con pasada · calidad {dict(Counter(o.calidad for o in minimas))} · "
      f"{len(con_dato)} con dato · {sum(o.valor <= 0 for o in con_dato)} con riesgo de helada")
