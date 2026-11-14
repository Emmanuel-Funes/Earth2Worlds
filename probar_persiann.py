"""Prueba real contra NOAA PERSIANN-CDR como tercer respaldo de la lluvia de IMERG.

Se usa desde GitHub (Actions → "Probar PERSIANN (lluvia de respaldo)"). No necesita credenciales:
los archivos diarios de PERSIANN-CDR son públicos (NOAA NCEI).
"""

import sys
import time
from collections import Counter
from datetime import date

from shapely.geometry import shape

from rotaterra.fuentes import persiann
from rotaterra.geo import poligono_desde_esquinas


esquinas, desde, hasta = sys.argv[1], date.fromisoformat(sys.argv[2]), date.fromisoformat(sys.argv[3])
centro = shape(poligono_desde_esquinas(esquinas)).centroid
lat, lon = round(centro.y, 6), round(centro.x, 6)
lote = {"id": "lote-prueba", "lat": lat, "lon": lon}

(satelite,) = persiann.SATELITES
inicio = time.time()
try:
    obs = satelite.pedir(lote, desde, hasta)
except persiann.ErrorPERSIANN as error:
    print(f"Error: {error}")
    causa = error.__cause__
    if getattr(causa, "response", None) is not None:  # diagnóstico: qué dijo NOAA (no hay secretos en juego)
        print(f"NOAA respondió {causa.response.status_code}: {causa.response.text[:800]}")
    # diagnóstico de estructura: mostrar cómo viene el NetCDF de NCEI (variables, dimensiones, coordenadas)
    import rasterio
    for nc in sorted(persiann.CARPETA.glob("*.nc")):
        print(f"\n--- estructura de {nc.name} ---")
        with rasterio.open(nc) as cont:
            print("subdatasets:", cont.subdatasets)
            dims = {k: v for k, v in cont.tags().items() if "DIM" in k or "dimension" in k.lower()}
            print("tags de dimensiones:", dims)
        for sub in cont.subdatasets:
            try:
                with rasterio.open(sub) as ds:
                    print(f"  {sub.rsplit(':',1)[-1]}: shape={ds.shape} bandas={ds.count} transform={tuple(ds.transform)[:6]}")
            except Exception as e:
                print(f"  {sub}: {type(e).__name__} {e}")
        for nombre in ("lat", "latitude", "lon", "longitude", "y", "x", "nlat", "nlon"):
            try:
                with rasterio.open(f"netcdf:{nc}:{nombre}") as eje:
                    arr = eje.read(1).ravel()
                    print(f"  eje {nombre}: len={arr.size} rango {arr.min():.3f}..{arr.max():.3f}")
            except Exception:
                pass
        break
    raise

print(f"\nLluvia NOAA PERSIANN-CDR (estimación por satélite, {persiann.VARIABLE}) como respaldo de IMERG · "
      f"satélite {satelite.nombre} (respaldo de {satelite.respaldo_de}, orden {satelite.orden})")
print(f"Centro del lote ({lat}, {lon}) · del {desde} al {hasta} · {time.time() - inicio:.1f} s\n")
print(f"{'Fecha':<12}{'Lluvia mm':>10}  {'Calidad':<11} Nota")
for o in obs:
    valor = "—" if o.valor is None else f"{o.valor:.2f}"
    print(f"{o.fecha!s:<12}{valor:>10}  {o.calidad:<11} {o.nota}")

total = sum(o.valor for o in obs if o.valor is not None)
print(f"\n{len(obs)} días · calidad {dict(Counter(o.calidad for o in obs))} · total {total:.1f} mm")
print(f"Variable {obs[0].variable} en {obs[0].unidad}, fuente {obs[0].fuente}, resolución {obs[0].resolucion_m} m")


if len(obs) != (hasta - desde).days + 1:
    sys.exit("Error: no vino un valor por cada día pedido")
