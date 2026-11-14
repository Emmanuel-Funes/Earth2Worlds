"""Prueba real contra GEOS-FP (clima y evapotranspiración del día, respaldos de POWER y de ET). Se usa desde GitHub (Actions → "Probar GEOS-FP (clima del día)")."""

import sys
import time
from datetime import date, datetime, timedelta, timezone

import httpx

from rotaterra.fuentes.geos_fp import BASE, PEDIDO_ET, celda, obtener_clima, obtener_et, ultima_hora

lat, lon = float(sys.argv[1]), float(sys.argv[2])
hoy = (datetime.now(timezone.utc) - timedelta(hours=3)).date()  # día de hoy en Argentina
desde = date.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else hoy - timedelta(days=4)
hasta = date.fromisoformat(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] else hoy

# muestra cruda de 3 horas, para ver el formato que devuelve el servidor
with httpx.Client(timeout=120) as c:
    ultimo, largo = ultima_hora(c, "tavg1_2d_slv_Nx")
    i_lat, i_lon = celda(lat, lon)
    crudo = c.get(f"{BASE}/tavg1_2d_slv_Nx.ascii?t2m[{largo - 3}:{largo - 1}][{i_lat}][{i_lon}]").text
    print(f"Última hora publicada: {ultimo:%d/%m/%Y %H:%M} UTC · {largo} horas en la serie\n{crudo[:400]}")

inicio = time.time()
clima = obtener_clima("lote-prueba", lat, lon, desde, hasta)
print(f"\nGEOS-FP (clima del día) en ({lat}, {lon}) del {desde} al {hasta} · {time.time() - inicio:.0f} s\n")
por_fecha = {}
for o in clima:
    por_fecha.setdefault(o.fecha, {})[o.variable] = o
print(f"{'Fecha':<12}{'Máx °C':>8}{'Mín °C':>8}{'MJ/m²':>8}{'Lluvia mm':>11}  Calidad de la máxima")
fmt = lambda o: "  —" if o is None or o.valor is None else f"{o.valor:.1f}"
for fecha, v in sorted(por_fecha.items()):
    print(f"{fecha!s:<12}{fmt(v.get('temp_max')):>8}{fmt(v.get('temp_min')):>8}{fmt(v.get('radiacion')):>8}"
          f"{fmt(v.get('lluvia_mm')):>11}  {v['temp_max'].calidad}")
print()
for o in clima:
    if o.fecha == hasta and o.variable in ("temp_max", "radiacion"):
        print(f"Nota {o.variable} {o.fecha}: {o.nota}")

# evapotranspiración del día (respaldo de ET): muestra cruda y valores
with httpx.Client(timeout=120) as c:
    ultimo, largo = ultima_hora(c, PEDIDO_ET[0])
    crudo = c.get(f"{BASE}/{PEDIDO_ET[0]}.ascii?{PEDIDO_ET[1]}[{largo - 3}:{largo - 1}][{i_lat}][{i_lon}]").text
    print(f"\nEvapotranspiración · última hora publicada: {ultimo:%d/%m/%Y %H:%M} UTC\n{crudo[:300]}")
inicio = time.time()
et = obtener_et("lote-prueba", lat, lon, desde, hasta)
print(f"GEOS-FP (evapotranspiración del día) · {time.time() - inicio:.0f} s")
for o in et:
    print(f"{o.fecha!s:<12}{fmt(o):>8} mm/día  {o.calidad}  {o.nota.split(' · ', 1)[-1] if o.valor is None else ''}")

utiles = [o for o in clima if o.valor is not None]
if not utiles:
    sys.exit("GEOS-FP no trajo ningún valor de clima")
if not [o for o in et if o.valor is not None]:
    sys.exit("GEOS-FP no trajo ningún valor de evapotranspiración")
