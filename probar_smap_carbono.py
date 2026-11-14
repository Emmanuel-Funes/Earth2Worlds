"""Prueba real de SMAP L4 Carbono sobre el lote. Actions → "Probar SMAP (productividad)". Necesita Earthdata."""

import sys
import time
from datetime import date

from rotaterra.fuentes import smap_carbono
from rotaterra.geo import poligono_desde_esquinas

esquinas, desde, hasta = sys.argv[1], sys.argv[2], sys.argv[3]
poligono = poligono_desde_esquinas(esquinas)
inicio = time.time()
obs = smap_carbono.obtener("lote-prueba", poligono, date.fromisoformat(desde), date.fromisoformat(hasta))
nee = {o.fecha: o.valor for o in obs if o.variable == "nee_g_c_m2_dia"}
gpp = [o for o in obs if o.variable == "gpp_g_c_m2_dia"]
print(f"\nProductividad SMAP L4 Carbono (celda de 9 km del lote) del {desde} al {hasta} · {time.time() - inicio:.0f} s\n")
print(f"{'Fecha':<12}{'GPP':>7}{'NEE':>7}  {'Calidad':<11} Detalle")
for o in gpp:
    g = "   — " if o.valor is None else f"{o.valor:5.2f}"
    n = "   — " if nee.get(o.fecha) is None else f"{nee[o.fecha]:5.2f}"
    print(f"{o.fecha!s:<12}{g:>7}{n:>7}  {o.calidad:<11} {o.nota}")
con_dato = [o.valor for o in gpp if o.valor is not None]
if con_dato:
    print(f"\n{len(gpp)} días · {len(con_dato)} con dato · GPP media {sum(con_dato) / len(con_dato):.2f} "
          f"(mín {min(con_dato):.2f}, máx {max(con_dato):.2f}) g C/m²/día · suma {sum(con_dato):.0f} g C/m²")
