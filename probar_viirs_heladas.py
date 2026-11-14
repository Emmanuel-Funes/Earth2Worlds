"""Prueba real contra VIIRS LST nocturna (alerta de heladas). Actions → "Probar VIIRS (heladas)". Necesita Earthdata."""

import sys
import time
from collections import Counter
from datetime import date

from rotaterra.fuentes import earthdata, viirs_heladas
from rotaterra.geo import poligono_desde_esquinas

esquinas, desde, hasta = sys.argv[1], sys.argv[2], sys.argv[3]
poligono = poligono_desde_esquinas(esquinas)
inicio = time.time()
try:
    obs = viirs_heladas.obtener_heladas("lote-prueba", poligono, date.fromisoformat(desde), date.fromisoformat(hasta))
except viirs_heladas.ErrorVIIRSHeladas as error:
    # diagnóstico sin credenciales a la vista: qué productos y archivos ve CMR
    print(f"Error: {error}\n")
    cliente = earthdata.cliente_autorizado()
    for producto in viirs_heladas.PRODUCTOS:
        coleccion = earthdata.coleccion_vigente(cliente, producto)
        print(f"{producto}: colección {coleccion}")
    print("\nRutas leídas de los metadatos:", viirs_heladas._RUTAS)
    raise

h, v, f0, f1, c0, c1 = viirs_heladas.ventana(poligono)
print(f"\nTemperatura de superficie nocturna del lote (VIIRS NOAA-20/21, LST de 1 km) del {desde} al {hasta} · "
      f"mosaico h{h:02d}v{v:02d} · {time.time() - inicio:.0f} s")
print(f"Capas leídas: {viirs_heladas._RUTAS}\n")
print(f"{'Fecha':<12}{'T sup °C':>9}  {'Calidad':<11} Detalle")
for o in obs:
    valor = "   —   " if o.valor is None else f"{o.valor:6.1f}"
    print(f"{o.fecha!s:<12}{valor:>9}  {o.calidad:<11} {o.nota}")

con_dato = [o for o in obs if o.valor is not None]
heladas = [o for o in con_dato if o.valor <= viirs_heladas.UMBRAL_HELADA]
print(f"\n{len(obs)} noches · calidad {dict(Counter(o.calidad for o in obs))} · "
      f"{len(con_dato)} con dato · {len(heladas)} con riesgo de helada (≤ 0 °C)")
if con_dato:
    mas_fria = min(con_dato, key=lambda o: o.valor)
    print(f"Noche más fría: {mas_fria.fecha} con {mas_fria.valor:.1f} °C de superficie")
    print(f"Variable {con_dato[0].variable} en {con_dato[0].unidad}, fuente {con_dato[0].fuente}, "
          f"resolución {con_dato[0].resolucion_m} m")
