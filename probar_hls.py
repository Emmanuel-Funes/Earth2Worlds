"""Prueba real contra HLS. Se usa desde GitHub (Actions → "Probar HLS (NDVI)")."""

import sys
from datetime import date

import httpx

from rotaterra.fuentes import earthdata
from rotaterra.fuentes.hls import ErrorHLS, obtener_ndvi
from rotaterra.geo import poligono_desde_esquinas


def diagnosticar(error: ErrorHLS) -> None:
    """Muestra qué devuelve la NASA en lugar del GeoTIFF (sin mostrar el token)."""
    import rasterio

    url = str(error).split("/vsicurl/", 1)[-1].split("'", 1)[0]
    print(f"\nDiagnóstico — GDAL {rasterio.__gdal_version__}, rasterio {rasterio.__version__}")
    print(f"Archivo: {url}")
    for nombre, cliente in (("con token", earthdata.cliente_autorizado()),
                            ("sin token", httpx.Client(timeout=60, follow_redirects=True))):
        try:
            r = cliente.get(url, headers={"Range": "bytes=0-511"})
            saltos = " → ".join(str(h.url).split("?")[0] for h in r.history) or "sin redirecciones"
            print(f"- {nombre}: HTTP {r.status_code}, {r.headers.get('content-type')}, "
                  f"{len(r.content)} bytes, empieza con {r.content[:4]!r}; {saltos} → {str(r.url).split('?')[0]}")
            if not r.content.startswith((b"II*\x00", b"MM\x00*")):
                print("  " + r.text[:400].replace("\n", " "))
        except Exception as e:
            print(f"- {nombre}: {type(e).__name__}: {e}")


esquinas, desde, hasta = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    obs = obtener_ndvi("lote-prueba", poligono_desde_esquinas(esquinas),
                       date.fromisoformat(desde), date.fromisoformat(hasta))
except ErrorHLS as error:
    diagnosticar(error)
    raise

print(f"\nNDVI y NDMI del lote (HLS, 30 m) del {desde} al {hasta}\n")
por_fecha = {}
for o in obs:
    por_fecha.setdefault(o.fecha, {})[o.variable] = o
print(f"{'Fecha':<12}{'NDVI':>7}{'NDMI':>7}  {'Calidad':<11} NDVI gráfico")
for fecha, v in sorted(por_fecha.items()):
    ndvi, ndmi = v.get("ndvi"), v.get("ndmi")
    fmt = lambda o: "  —  " if o is None or o.valor is None else f"{o.valor:5.2f}"
    barra = "█" * round(max(ndvi.valor, 0) * 30) if ndvi and ndvi.valor is not None else ""
    print(f"{fecha!s:<12}{fmt(ndvi):>7}{fmt(ndmi):>7}  {ndvi.calidad if ndvi else '':<11} {barra}")
buenas = sum(1 for o in obs if o.variable == "ndvi" and o.calidad == "buena")
print(f"\n{len(por_fecha)} fechas con imagen, {buenas} con el lote despejado.")
