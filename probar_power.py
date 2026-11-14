"""Prueba real contra NASA POWER. Se usa desde GitHub (Actions → "Probar NASA POWER")."""

import sys
from collections import Counter
from datetime import date

from rotaterra.fuentes.power import obtener_clima

lat, lon, desde, hasta = float(sys.argv[1]), float(sys.argv[2]), sys.argv[3], sys.argv[4]
obs = obtener_clima("lote-prueba", lat, lon, date.fromisoformat(desde), date.fromisoformat(hasta))

print(f"\nClima NASA POWER en ({lat}, {lon}) del {desde} al {hasta}\n")
print(f"{'Fecha':<12}{'T máx °C':>10}{'T mín °C':>10}{'Lluvia mm':>11}{'Radiación MJ/m²':>17}")
por_fecha = {}
for o in obs:
    por_fecha.setdefault(o.fecha, {})[o.variable] = o.valor
fmt = lambda v: "sin dato" if v is None else f"{v:.1f}"
for fecha, v in sorted(por_fecha.items()):
    print(f"{fecha!s:<12}{fmt(v.get('temp_max')):>10}{fmt(v.get('temp_min')):>10}"
          f"{fmt(v.get('lluvia_mm')):>11}{fmt(v.get('radiacion')):>17}")
print(f"\nCalidad de los {len(obs)} valores: {dict(Counter(o.calidad for o in obs))}")
