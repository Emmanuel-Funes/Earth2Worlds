"""Prueba real contra ASTER GDEM v3 de la NASA y el METI (respaldo de la altimetría de NASADEM).

Se usa desde GitHub (Actions → "Probar ASTER GDEM (altimetría de respaldo)"). Necesita las credenciales de
Earthdata (secrets EARTHDATA_USERNAME / EARTHDATA_PASSWORD), porque los mosaicos se bajan de LP DAAC.
"""

import sys
import time

from rotaterra.fuentes import aster
from rotaterra.geo import poligono_desde_esquinas

# NASADEM en el lote de ejemplo (spec 008) y Copernicus DEM (spec 016), para comparar los tres modelos
NASADEM = {"altura_media_m": 488.4, "altura_min_m": 485, "altura_max_m": 492, "pendiente_media_pct": 2.76,
           "superficie_bajo_ha": 8.28, "superficie_media_loma_ha": 10.86, "superficie_loma_ha": 6.58}
EJEMPLO = "-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300"

esquinas = sys.argv[1]
inicio = time.time()
obs = aster.obtener_altimetria("lote-prueba", poligono_desde_esquinas(esquinas))

print(f"\nAltimetría del lote (ASTER GDEM v3, NASA/METI, 30 m, fecha {obs[0].fecha}) · "
      f"{time.time() - inicio:.0f} s\n")
comparar = esquinas.strip() == EJEMPLO
print(f"{'Variable':<26}{'Valor':>9}  {'Unidad':<6} {'Calidad':<11}" + (" NASADEM" if comparar else ""))
for o in obs:
    valor = "—" if o.valor is None else f"{o.valor:g}"
    extra = f" {NASADEM[o.variable]:>7g}" if comparar else ""
    print(f"{o.variable:<26}{valor:>9}  {o.unidad:<6} {o.calidad:<11}{extra}")
print(f"\nDetalle: {obs[-1].nota}")
