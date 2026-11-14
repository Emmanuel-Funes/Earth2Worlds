"""Prueba real contra Copernicus DEM de la ESA (respaldo de la altimetría de NASADEM).

Se usa desde GitHub (Actions → "Probar Copernicus DEM (altimetría de respaldo)"). No necesita credenciales.
"""

import sys
import time

import httpx
from shapely.geometry import shape

from rotaterra.fuentes import copdem
from rotaterra.geo import poligono_desde_esquinas

# NASADEM en el lote de ejemplo (spec 008), para comparar
NASADEM = {"altura_media_m": 488.4, "altura_min_m": 485, "altura_max_m": 492, "pendiente_media_pct": 2.76,
           "superficie_bajo_ha": 8.28, "superficie_media_loma_ha": 10.86, "superficie_loma_ha": 6.58}
EJEMPLO = "-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300"

esquinas = sys.argv[1]
poligono = poligono_desde_esquinas(esquinas)
mosaicos = copdem.mosaicos_de_la_caja(shape(poligono).bounds)
inicio = time.time()
try:
    obs = copdem.obtener_altimetria("lote-prueba", poligono)
except copdem.ErrorCOPDEM as error:
    # diagnóstico: qué responde el bucket para cada mosaico del lote (es público, no hay secretos)
    print(f"Error: {error}\n")
    with httpx.Client(timeout=60, follow_redirects=True) as cliente:
        for nombre in mosaicos:
            for url in (copdem.url_xml(nombre), copdem.url_tif(nombre)):
                print(f"{cliente.head(url).status_code}  {url}")
            listado = cliente.get(copdem.URL_BASE, params={"list-type": 2, "max-keys": 20,
                                                          "prefix": copdem.carpeta(nombre) + "/"})
            print(f"Listado de la carpeta ({listado.status_code}):\n{listado.text[:3000]}\n")
    raise

print(f"\nAltimetría del lote (Copernicus DEM GLO-30 de la ESA, 30 m, fecha {obs[0].fecha}) · "
      f"{time.time() - inicio:.0f} s · mosaicos {mosaicos}\n")
comparar = esquinas.strip() == EJEMPLO
print(f"{'Variable':<26}{'Valor':>9}  {'Unidad':<6} {'Calidad':<11}" + (" NASADEM" if comparar else ""))
for o in obs:
    valor = "—" if o.valor is None else f"{o.valor:g}"
    extra = f" {NASADEM[o.variable]:>7g}" if comparar else ""
    print(f"{o.variable:<26}{valor:>9}  {o.unidad:<6} {o.calidad:<11}{extra}")
print(f"\nDetalle: {obs[-1].nota}")
