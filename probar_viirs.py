"""Prueba real contra VIIRS (primer respaldo del NDVI). Se usa desde GitHub (Actions → "Probar VIIRS (NDVI de respaldo)")."""

import sys
import time
from datetime import date

from rotaterra.fuentes import earthdata, viirs
from rotaterra.geo import poligono_desde_esquinas

esquinas, desde, hasta = sys.argv[1], sys.argv[2], sys.argv[3]
poligono = poligono_desde_esquinas(esquinas)
inicio = time.time()
try:
    obs = viirs.obtener_ndvi("lote-prueba", poligono, date.fromisoformat(desde), date.fromisoformat(hasta))
except viirs.ErrorVIIRS as error:
    # diagnóstico sin credenciales a la vista: qué productos y archivos ve CMR
    print(f"Error: {error}\n")
    cliente = earthdata.cliente_autorizado()
    for producto in viirs.PRODUCTOS:
        coleccion = earthdata.coleccion_vigente(cliente, producto)
        print(f"{producto}: colección {coleccion}")
        if coleccion:
            respuesta = cliente.get(f"{earthdata.URL_CMR}/granules.umm_json",
                                    params={"collection_concept_id": coleccion, "page_size": 2,
                                            "temporal": f"{desde}T00:00:00Z,{hasta}T23:59:59Z"})
            for item in respuesta.json().get("items", []):
                print("  ", item["umm"]["GranuleUR"])
                for u in item["umm"].get("RelatedUrls", []):
                    print("     ", u.get("Type"), u["URL"])
    print("\nRutas leídas de los metadatos:", viirs._RUTAS)
    raise

h, v, f0, f1, c0, c1 = viirs.ventana(poligono)
print(f"\nNDVI del lote (VIIRS NOAA-20/21, 500 m, compuestos de 16 días) del {desde} al {hasta} · "
      f"mosaico h{h:02d}v{v:02d} · {time.time() - inicio:.0f} s")
print(f"Capas leídas: {viirs._RUTAS}\n")
print(f"{'Fecha':<12}{'NDVI':>7}  {'Calidad':<11} Detalle")
for o in obs:
    valor = "  —  " if o.valor is None else f"{o.valor:5.2f}"
    print(f"{o.fecha!s:<12}{valor:>7}  {o.calidad:<11} {o.nota}")
print(f"\n{len(obs)} fechas, {sum(1 for o in obs if o.calidad == 'buena')} con el lote despejado.")
