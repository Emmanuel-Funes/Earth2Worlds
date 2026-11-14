"""Prueba real contra SISINTA (perfiles de suelo del INTA). Actions → "Probar SISINTA (pH de perfiles medidos)".
Sin clave. Prueba el lote dado y, si no se da ninguno, el lote de prueba y las 3 parcelas del piloto."""

import sys
import time

from rotaterra.fuentes import sisinta
from rotaterra.geo import poligono_desde_esquinas


def cuadrado(lat, lon, m=0.0025):
    return f"{lat - m}, {lon - m}; {lat - m}, {lon + m}; {lat + m}, {lon + m}; {lat + m}, {lon - m}"


# centros tomados del Catastro (informe de pH del 19/10/2026)
LOTES = {"Lote de prueba": cuadrado(-33.700, -65.300), "Villa Mercedes 01-90230": cuadrado(-33.616, -65.353),
         "Justo Daract 06-924206": cuadrado(-33.898, -65.126), "Buena Esperanza 02-950571": cuadrado(-34.738, -65.262)}

lotes = {"Lote pedido": sys.argv[1]} if len(sys.argv) > 1 and sys.argv[1].strip() else LOTES
for nombre, esquinas in lotes.items():
    inicio = time.time()
    obs = sisinta.obtener_ph_perfiles("lote-prueba", poligono_desde_esquinas(esquinas))
    print(f"\n{nombre} · {time.time() - inicio:.1f} s")
    for o in obs:
        valor = "  —  " if o.valor is None else f"{o.valor:5.2f}"
        print(f"  {o.variable:<28}{valor}  {o.calidad:<10} {o.resolucion_m // 1000} km · {o.fecha} · {o.nota}")
