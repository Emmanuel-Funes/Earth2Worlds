"""Prueba real de la evapotranspiración del lote (spec 017). Se usa desde GitHub (Actions → "Probar MODIS (evapotranspiración)")."""

import sys
import time
from datetime import date

from rotaterra.fuentes import earthdata, et
from rotaterra.geo import poligono_desde_esquinas

# productos de ET de 500 m y 8 días que se revisan en CMR (los del conector más las versiones anuales "GF")
CANDIDATOS = list(et.PRODUCTOS) + ["VJ216A2", "VNP16A2", "VJ116A2GF", "VNP16A2GF", "MOD16A2GF", "MYD16A2GF"]


def buscar_viirs() -> None:
    """Por si la NASA publica la ET de VIIRS con otro nombre: busca por palabra clave en CMR."""
    cliente = earthdata.cliente_autorizado()
    items = cliente.get(f"{earthdata.URL_CMR}/collections.umm_json",
                        params={"keyword": "VIIRS evapotranspiration", "page_size": 50}).json().get("items", [])
    nombres = sorted({f"{i['umm'].get('ShortName')} v{i['umm'].get('Version')}" for i in items})
    print(f"Colecciones de CMR con 'VIIRS evapotranspiration': {', '.join(nombres) or 'ninguna'}\n")


def revisar_cmr(poligono: dict, desde: str, hasta: str) -> None:
    """Qué productos de ET tiene CMR, con qué versión, hasta qué fecha y si traen OPeNDAP (sin secretos)."""
    from shapely.geometry import shape

    h, v, *_ = et.ventana(poligono)
    mosaico = f".h{h:02d}v{v:02d}."
    cliente = earthdata.cliente_autorizado()
    print(f"Productos de ET en CMR (mosaico h{h:02d}v{v:02d}, {desde} a {hasta}):")
    for producto in CANDIDATOS:
        items = cliente.get(f"{earthdata.URL_CMR}/collections.umm_json",
                            params={"short_name": producto, "page_size": 20}).json().get("items", [])
        if not items:
            print(f"  {producto:<10} no está en CMR")
            continue
        for item in items:
            umm = item["umm"]
            rango = (umm.get("TemporalExtents") or [{}])[0].get("RangeDateTimes") or [{}]
            print(f"  {producto:<10} v{umm.get('Version')} {item['meta']['concept-id']} · "
                  f"{(rango[0].get('BeginningDateTime') or '?')[:10]} a {(rango[0].get('EndingDateTime') or 'hoy')[:10]}")
        vigente = earthdata.coleccion_vigente(cliente, producto)
        respuesta = cliente.get(f"{earthdata.URL_CMR}/granules.umm_json",
                                params={"collection_concept_id": vigente, "page_size": 50, "sort_key": "start_date",
                                        "temporal": f"{desde}T00:00:00Z,{hasta}T23:59:59Z",
                                        "bounding_box": ",".join(str(c) for c in shape(poligono).bounds)})
        granulos = [g for g in respuesta.json().get("items", []) if mosaico in g["umm"]["GranuleUR"]]
        con_opendap = [g for g in granulos if any("opendap" in u["URL"].lower()
                                                  for u in g["umm"].get("RelatedUrls", []))]
        print(f"     archivos del lote en el período: {len(granulos)}, con OPeNDAP: {len(con_opendap)}"
              + (f" · ej. {granulos[0]['umm']['GranuleUR']}" if granulos else ""))
        ultimo = cliente.get(f"{earthdata.URL_CMR}/granules.umm_json",
                             params={"collection_concept_id": vigente, "page_size": 1, "sort_key": "-start_date"})
        for g in ultimo.json().get("items", []):
            print(f"     último archivo publicado: {g['umm']['GranuleUR']}")
    print()


esquinas, desde, hasta = sys.argv[1], sys.argv[2], sys.argv[3]
poligono = poligono_desde_esquinas(esquinas)
try:
    revisar_cmr(poligono, desde, hasta)
    buscar_viirs()
except Exception as error:  # el diagnóstico no frena la prueba
    print(f"No se pudo revisar CMR: {type(error).__name__}: {error}\n")

inicio = time.time()
try:
    obs = et.obtener_et("lote-prueba", poligono, date.fromisoformat(desde), date.fromisoformat(hasta))
except et.ErrorET as error:
    print(f"Error: {error}\n")
    print("Rutas leídas de los metadatos:", et._RUTAS, et._ATRIBUTOS)
    raise

h, v, f0, f1, c0, c1 = et.ventana(poligono)
print(f"Evapotranspiración del lote (500 m, compuestos de 8 días) del {desde} al {hasta} · "
      f"mosaico h{h:02d}v{v:02d} · {time.time() - inicio:.0f} s")
print(f"Capas leídas: {et._RUTAS}\nAtributos: {et._ATRIBUTOS}\n")
print(f"{'Inicio':<12}{'Variable':<12}{'mm/día':>7}  {'Calidad':<11} Detalle")
for o in obs:
    valor = "  —  " if o.valor is None else f"{o.valor:6.2f}"
    print(f"{o.fecha!s:<12}{o.variable:<12}{valor:>7}  {o.calidad:<11} {o.fuente} · {o.nota}")
reales = [o for o in obs if o.variable == "et_mm_dia"]
print(f"\n{len(reales)} compuestos, {sum(1 for o in reales if o.valor is not None)} con ET válida.")
