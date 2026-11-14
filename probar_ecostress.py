"""Prueba real contra ECOSTRESS. Se usa desde GitHub (Actions → "Probar ECOSTRESS (evapotranspiración y estrés)")."""

import sys
import time
from datetime import date

import httpx

from rotaterra.fuentes import earthdata, ecostress
from rotaterra.geo import poligono_desde_esquinas


def mostrar_catalogo(cliente: httpx.Client, poligono: dict, desde: date, hasta: date) -> None:
    """Qué gránulos y qué capas ve CMR para el lote (para verificar los nombres reales; sin credenciales)."""
    from shapely.geometry import shape

    for variable, producto in ecostress.PRODUCTOS.items():
        coleccion = earthdata.coleccion_vigente(cliente, producto.nombre)
        print(f"{producto.nombre} ({variable}): colección {coleccion}")
        if coleccion is None:
            continue
        granulos = ecostress.buscar_granulos(cliente, producto.nombre, desde, hasta, shape(poligono).bounds)
        mosaicos = sorted({g.nombre.split("_")[5] for g in granulos if len(g.nombre.split("_")) > 5})
        print(f"  {len(granulos)} gránulos que tocan el lote del {desde} al {hasta}; mosaicos {mosaicos}")
        if granulos:
            print(f"  capas del primero ({granulos[0].nombre}): {sorted(granulos[0].capas)}")


def diagnosticar(cliente: httpx.Client, error: Exception) -> None:
    """Muestra qué devuelve LP DAAC en lugar del GeoTIFF (sin mostrar el token ni el enlace firmado)."""
    import rasterio

    print(f"\nDiagnóstico — GDAL {rasterio.__gdal_version__}, rasterio {rasterio.__version__}")
    texto = str(error)
    url = next((p for p in texto.replace("'", " ").split() if p.startswith("https://data.lpdaac")), None)
    if not url:
        return
    print(f"Archivo: {url}")
    try:
        r = cliente.get(url, headers={"Range": "bytes=0-511"})
        saltos = " → ".join(str(h.url).split("?")[0] for h in r.history) or "sin redirecciones"
        print(f"- con token: HTTP {r.status_code}, {r.headers.get('content-type')}, {len(r.content)} bytes, "
              f"empieza con {r.content[:4]!r}; {saltos} → {str(r.url).split('?')[0]}")
    except Exception as e:
        print(f"- con token: {type(e).__name__}: {e}")


def pedir(poligono: dict, desde: date, hasta: date) -> list:
    inicio = time.time()
    obs = ecostress.obtener("lote-prueba", poligono, desde, hasta)
    print(f"\nECOSTRESS del {desde} al {hasta}: {len(obs)} observaciones en {time.time() - inicio:.0f} s")
    return obs


esquinas, desde, hasta = sys.argv[1], date.fromisoformat(sys.argv[2]), date.fromisoformat(sys.argv[3])
poligono = poligono_desde_esquinas(esquinas)
cliente = earthdata.cliente_autorizado()
mostrar_catalogo(cliente, poligono, desde, hasta)
try:
    obs = pedir(poligono, desde, hasta)
    if not obs:
        # la Estación Espacial pasa de forma irregular: si en el período no pasó, se mira el verano entero
        desde, hasta = min(desde, date(2025, 12, 1)), max(hasta, date(2026, 2, 28))
        print(f"Sin pasadas en el período pedido: se amplía al {desde} – {hasta}.\n")
        mostrar_catalogo(cliente, poligono, desde, hasta)
        obs = pedir(poligono, desde, hasta)
except ecostress.ErrorECOSTRESS as error:
    print(f"Error: {error}")
    diagnosticar(cliente, error)
    raise

por_fecha: dict[date, dict] = {}
for o in obs:
    por_fecha.setdefault(o.fecha, {})[o.variable] = o
print("\nEvapotranspiración (mm/día) y estrés hídrico (ESI: 0 = estrés máximo, 1 = sin estrés), 70 m\n")
print(f"{'Fecha':<12}{'ET':>7}{'ESI':>7}  {'Calidad ET':<11}{'Calidad ESI':<12} Detalle")
for fecha, v in sorted(por_fecha.items()):
    et, esi = v.get("et_mm_dia"), v.get("esi")
    fmt = lambda o: "  —  " if o is None or o.valor is None else f"{o.valor:5.2f}"
    nota = (et or esi).nota
    print(f"{fecha!s:<12}{fmt(et):>7}{fmt(esi):>7}  {et.calidad if et else '—':<11}"
          f"{esi.calidad if esi else '—':<12} {nota}")
con_valor = [o for o in obs if o.valor is not None]
print(f"\n{len(por_fecha)} fechas con pasada, {len(con_valor)} valores con dato "
      f"({sum(1 for o in obs if o.calidad == 'buena')} con el lote despejado).")
if not obs:
    sys.exit("ECOSTRESS no tiene pasadas sobre el lote en todo el período: no se pudo verificar con datos reales.")
