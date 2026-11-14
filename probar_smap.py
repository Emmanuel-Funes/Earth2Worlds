"""Prueba real contra SMAP. Se usa desde GitHub (Actions → "Probar SMAP (humedad del suelo)").

camino = directo  → lee los archivos de la NASA (CMR + OPeNDAP): segundos o pocos minutos.
camino = appeears → pide a AppEEARS (respaldo): de 2 a 40 minutos según la fila.
"""

import sys
import time
from datetime import date

from rotaterra.fuentes.smap import DemoraSMAP, obtener_humedad, obtener_humedad_directo

lat, lon, desde, hasta = float(sys.argv[1]), float(sys.argv[2]), sys.argv[3], sys.argv[4]
camino = sys.argv[5] if len(sys.argv) > 5 else "directo"
desde, hasta = date.fromisoformat(desde), date.fromisoformat(hasta)
inicio = time.time()
if camino == "directo":
    print("Leyendo SMAP directo de los archivos de la NASA...", flush=True)
    obs = obtener_humedad_directo("lote-prueba", lat, lon, desde, hasta)
else:
    print("Pidiendo a AppEEARS (NASA). Puede tardar de 2 a 40 minutos según la fila...", flush=True)
    try:
        obs = obtener_humedad("lote-prueba", lat, lon, desde, hasta, espera_max_s=2400)
    except DemoraSMAP as error:
        print(f"\n{error}\nEl pedido sigue en la fila de la NASA. Volvé a correr esta prueba más tarde:"
              " retoma el mismo pedido en vez de empezar de cero.")
        sys.exit(1)

print(f"\nHumedad del suelo SMAP L4 en ({lat}, {lon}) del {desde} al {hasta} · camino {camino} · "
      f"{time.time() - inicio:.0f} s")
print("Celda de 9 km: contexto regional, no dato del lote. Unidad m³/m³ (0,25 = 25 % en volumen)\n")
por_fecha = {}
for o in obs:
    por_fecha.setdefault(o.fecha, {})[o.variable] = o
fmt = lambda o: "sin dato" if o is None or o.valor is None else f"{o.valor:.3f}"
print(f"{'Fecha':<12}{'0-5 cm':>9}{'0-100 cm':>10}  {'Calidad':<11} Zona de raíces")
for fecha, v in sorted(por_fecha.items()):
    raiz = v.get("humedad_zona_raiz")
    barra = "█" * round(raiz.valor * 80) if raiz and raiz.valor is not None else ""
    print(f"{fecha!s:<12}{fmt(v.get('humedad_superficial')):>9}{fmt(raiz):>10}  "
          f"{raiz.calidad if raiz else '':<11} {barra}")
buenas = sum(1 for o in obs if o.calidad == "buena")
print(f"\n{len(por_fecha)} días, {buenas} de {len(obs)} valores con calidad buena.")
