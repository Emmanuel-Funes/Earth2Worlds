"""Prueba real contra SMAP L3 (segundo respaldo de la humedad). Se usa desde GitHub
(Actions → "Probar SMAP L3 (humedad de respaldo)")."""

import sys
import time
from datetime import date

from rotaterra.fuentes import earthdata, smap_l3

# SMAP L4 0-5 cm en el lote de prueba (specs 003 y 005), para comparar
L4_REFERENCIA = {date(2026, 1, 1): 0.049, date(2026, 1, 8): 0.098, date(2026, 1, 9): 0.120,
                 date(2026, 1, 14): 0.127}

lat, lon = float(sys.argv[1]), float(sys.argv[2])
desde, hasta = date.fromisoformat(sys.argv[3]), date.fromisoformat(sys.argv[4])
fila, columna = smap_l3.celda_ease2(lat, lon)
inicio = time.time()
print(f"Leyendo SMAP L3 ({smap_l3.PRODUCTO}) de la NASA para ({lat}, {lon}), celda EASE-Grid 2.0 de 9 km "
      f"fila {fila}, columna {columna}...", flush=True)
try:
    leidos = smap_l3.leer_periodo(lat, lon, desde, hasta)
except smap_l3.ErrorSMAPL3 as error:
    # diagnóstico sin credenciales a la vista: qué colecciones, archivos y capas ve la NASA
    print(f"Error: {error}\n")
    cliente = earthdata.cliente_autorizado()
    items = cliente.get(f"{earthdata.URL_CMR}/collections.umm_json",
                        params={"short_name": smap_l3.PRODUCTO, "page_size": 20}).json().get("items", [])
    for item in items:
        print(f"Colección {item['meta']['concept-id']} · proveedor {item['meta'].get('provider-id')} · "
              f"versión {item['umm'].get('Version')}")
    try:
        coleccion = smap_l3.coleccion(cliente)
        respuesta = cliente.get(f"{earthdata.URL_CMR}/granules.umm_json",
                                params={"collection_concept_id": coleccion, "page_size": 3,
                                        "temporal": f"{desde}T00:00:00Z,{hasta}T23:59:59Z"})
        for item in respuesta.json().get("items", []):
            print("  ", item["umm"]["GranuleUR"])
            for u in item["umm"].get("RelatedUrls", []):
                print("     ", u.get("Type"), u["URL"])
        archivos = earthdata.archivos(cliente, coleccion, desde, hasta)
        if archivos:
            dmr = cliente.get(f"{archivos[0][1]}.dmr")
            print(f"\nMetadatos de {archivos[0][0]}: HTTP {dmr.status_code}")
            print("\n".join(linea for linea in dmr.text.splitlines() if "<Group" in linea)[:3000])
    except Exception as otro:
        print(f"(el diagnóstico también falló: {type(otro).__name__}: {otro})")
    raise

obs = smap_l3.observaciones("lote-prueba", desde, hasta, leidos)
print(f"\nHumedad de superficie SMAP L3 del {desde} al {hasta} · {len(leidos)} archivos diarios · "
      f"{time.time() - inicio:.0f} s")
print(f"Capas leídas: {smap_l3._RUTAS}")
print("Unidad m³/m³ (0,10 = 10 % en volumen). Bandera = retrieval_qual_flag (bit 0 en 0 = calidad recomendada)\n")

# verificación de la grilla: la latitud y longitud que trae el archivo para la celda calculada
centros = {(round(p["lat"], 4), round(p["lon"], 4)) for pasadas in leidos.values() for p in pasadas.values()
           if p["lat"] is not None and p["lon"] is not None}
for c_lat, c_lon in sorted(centros):
    d = smap_l3.distancia_km(lat, lon, c_lat, c_lon)
    veredicto = "OK: el punto está en la celda" if d < 6.5 else "ATENCIÓN: la celda no parece la del punto"
    print(f"Centro de la celda según el archivo: ({c_lat}, {c_lon}) · a {d:.1f} km del punto · {veredicto}")
if not centros:
    print("Ningún día trajo la latitud y longitud de la celda: no se pudo verificar la grilla.")

fmt = lambda v: "   —  " if v is None else f"{v:6.3f}"
bandera = lambda v: "  —  " if v is None else f"{int(v):5d}"
print(f"\n{'Fecha':<12}{'AM':>7}{'band.':>6}{'PM':>8}{'band.':>6}{'Día':>8}  {'Calidad':<11}{'L4 0-5 cm':>10}")
for o in obs:
    p = leidos.get(o.fecha) or {}
    am, pm = p.get("AM") or {}, p.get("PM") or {}
    l4 = L4_REFERENCIA.get(o.fecha)
    print(f"{o.fecha!s:<12}{fmt(am.get('humedad')):>7}{bandera(am.get('bandera')):>6}"
          f"{fmt(pm.get('humedad')):>8}{bandera(pm.get('bandera')):>6}{fmt(o.valor):>8}  {o.calidad:<11}"
          f"{'' if l4 is None else f'{l4:.3f}':>10}")
buenas = sum(1 for o in obs if o.calidad == "buena")
print(f"\n{len(obs)} días: {buenas} buenos, {sum(1 for o in obs if o.calidad == 'dudosa')} dudosos, "
      f"{sum(1 for o in obs if o.calidad == 'descartada')} descartados (sin pasada o sin archivo).")
print(f"Ejemplo de nota: {next((o.nota for o in obs if o.valor is not None), obs[0].nota)}")
