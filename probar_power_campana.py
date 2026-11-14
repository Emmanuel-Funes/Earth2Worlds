"""Prueba real del clima de la campaña: NASA POWER y su respaldo MERRA-2 (spec 034). Se usa desde GitHub
(Actions → "Probar POWER (clima de la campaña)")."""

import sys
import time
from datetime import date

from rotaterra.fuentes import earthdata, power_campana as pc

lat, lon = float(sys.argv[1]), float(sys.argv[2])
fallas = 0


def mostrar(observaciones) -> None:
    for o in observaciones:
        valor = "sin dato" if o.valor is None else f"{o.valor:g} {o.unidad}"
        if o.valor is not None and o.unidad == pc.DIA_DEL_ANIO:
            valor += f" ({pc.dd_mm(o.valor)})"
        print(f"  {o.variable:30} {valor:24} {o.fuente:7} {o.calidad:10} {o.fecha}\n      {o.nota}")


print(f"1) Principal: NASA POWER para ({lat}, {lon}), período {pc.periodo()}", flush=True)
inicio = time.time()
principal = []
try:
    principal = pc.obtener_clima_campana("prueba", lat, lon)
    mostrar(principal)
except Exception as error:
    fallas += 1
    print(f"  ✗ {type(error).__name__}: {error}")
print(f"  ({time.time() - inicio:.1f} s)\n", flush=True)

print(f"2) Diagnóstico del respaldo: dos días de {pc.VARIABLE_MERRA2} en el servicio de series de Giovanni", flush=True)
try:
    cliente = earthdata.cliente_autorizado()
    respuesta = cliente.get(pc.URL_SERIES, params={
        "data": pc.VARIABLE_MERRA2, "location": f"[{lat},{lon}]",
        "time": "2025-01-01T00:00:00/2025-01-02T23:59:59"})
    print(f"  HTTP {respuesta.status_code} · {respuesta.headers.get('content-type')} · {len(respuesta.text)} caracteres")
    lineas = respuesta.text.splitlines()
    print("  " + "\n  ".join(lineas[:15]))
    print("  ...\n  " + "\n  ".join(lineas[-3:]))
except Exception as error:
    print(f"  ✗ {type(error).__name__}: {error}")

print("\n3) Respaldo completo: MERRA-2", flush=True)
inicio = time.time()
try:
    respaldo = pc.obtener_clima_campana_merra2("prueba", lat, lon)
    mostrar(respaldo)
    a = {o.variable: o.valor for o in principal}
    for o in respaldo:
        if o.valor is not None and a.get(o.variable) is not None:
            print(f"  diferencia con POWER en {o.variable}: {o.valor - a[o.variable]:+g}")
except Exception as error:
    fallas += 1
    print(f"  ✗ {type(error).__name__}: {error}")
print(f"  ({time.time() - inicio:.1f} s)")

if principal:
    v = {o.variable: o for o in principal}
    print(f"\nCriterios: días libres {v['dias_libres_heladas'].valor} (esperado 257), lluvia mediana "
          f"{v['lluvia_campana_mm_p50'].valor} y año seco {v['lluvia_campana_mm_p20'].valor} (esperado 597 y 507) · "
          f"hoy {date.today()}")
sys.exit(1 if fallas else 0)
