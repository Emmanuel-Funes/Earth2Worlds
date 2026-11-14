"""Prueba real contra Sentinel-2 L2A de la ESA (primer respaldo de HLS, NDVI y NDMI).

Se usa desde GitHub (Actions → "Probar Sentinel-2 (NDVI y NDMI de respaldo)"). No necesita credenciales.
"""

import sys
import time
from datetime import date

from rotaterra.fuentes import sentinel2
from rotaterra.geo import poligono_desde_esquinas

esquinas, desde, hasta = sys.argv[1], date.fromisoformat(sys.argv[2]), date.fromisoformat(sys.argv[3])
poligono = poligono_desde_esquinas(esquinas)


def diagnostico() -> None:
    """Qué ve Earth Search para el lote: escenas, nubes y cómo viene la reflectancia (sin secretos: no hay)."""
    from pystac_client import Client
    from shapely.geometry import shape

    for coleccion in sentinel2.COLECCIONES:
        try:
            items = list(Client.open(sentinel2.URL_STAC).search(
                collections=[coleccion], bbox=list(shape(poligono).bounds),
                datetime=f"{desde}T00:00:00Z/{hasta}T23:59:59Z", max_items=50).items())
        except Exception as error:
            print(f"{coleccion}: la búsqueda falló: {type(error).__name__}: {error}")
            continue
        print(f"{coleccion}: {len(items)} escenas")
        for item in items[:3]:
            p = item.properties
            rojo = item.assets.get("red")
            bandas = rojo.extra_fields.get("raster:bands") if rojo else None
            print(f"   {item.id} · nubes {p.get('eo:cloud_cover')} · línea de base {p.get('s2:processing_baseline')} · "
                  f"offset aplicado {p.get('earthsearch:boa_offset_applied')} · raster:bands {bandas} · "
                  f"se usa escala/offset {sentinel2.escala_y_offset(p, bandas)}")
            if rojo:
                print(f"      {rojo.href}")


inicio = time.time()
try:
    obs = sentinel2.obtener_ndvi("lote-prueba", poligono, desde, hasta)
except sentinel2.ErrorSentinel2 as error:
    print(f"Error: {error}\n")
    diagnostico()
    raise

print(f"\nNDVI (10 m) y NDMI (20 m) del lote con Sentinel-2 L2A (ESA, vía Earth Search / AWS Open Data) "
      f"del {desde} al {hasta} · {time.time() - inicio:.0f} s\n")
diagnostico()
print(f"\n{'Fecha':<12}{'Variable':<9}{'Valor':>7}  {'Calidad':<11} Detalle")
for o in obs:
    valor = "  —  " if o.valor is None else f"{o.valor:5.2f}"
    print(f"{o.fecha!s:<12}{o.variable:<9}{valor:>7}  {o.calidad:<11} {o.nota}")
fechas = sorted({o.fecha for o in obs})
limpias = sorted({o.fecha for o in obs if o.variable == "ndvi" and o.calidad == "buena"})
print(f"\n{len(fechas)} fechas, {len(limpias)} con el lote despejado.")
if not obs:
    sys.exit("Sentinel-2 no devolvió ninguna escena para el lote en ese período.")
