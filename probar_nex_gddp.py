"""Prueba real de NEX-GDDP-CMIP6 (clima futuro) sobre el lote. Actions → "Probar NEX-GDDP (clima futuro)". Sin cuenta."""

import sys
import time

from rotaterra.fuentes import nex_gddp

lat, lon = float(sys.argv[1]), float(sys.argv[2])
inicio = time.time()
obs = nex_gddp.obtener_clima_futuro("lote-prueba", lat, lon)
print(f"\nClima futuro NEX-GDDP-CMIP6 en la celda de ~25 km de {lat}, {lon} · {time.time() - inicio:.0f} s\n")
por_variable = {o.variable: o for o in obs}
print(f"{'Indicador':<26}{'1995-2014':>11}{'SSP2-4.5':>11}{'SSP5-8.5':>11}  Unidad")
for indicador, (unidad, _, _) in nex_gddp.INDICADORES.items():
    celdas = []
    for periodo in nex_gddp.PERIODOS:
        o = por_variable[f"{indicador}_{periodo}"]
        celdas.append("—" if o.valor is None else f"{o.valor:g}")
    print(f"{indicador:<26}{celdas[0]:>11}{celdas[1]:>11}{celdas[2]:>11}  {unidad}")
print("\nDetalle:")
for o in obs:
    print(f"· {o.variable}: {o.valor} {o.unidad} · {o.calidad} · {o.nota}")
