"""Conector ASTER GDEM v3 (NASA/METI): altura, pendiente y ambientes del lote, respaldo de NASADEM (spec 037).

Mismas 7 variables y mismas reglas que NASADEM (spec 008) y Copernicus DEM (spec 016), con el modelo global
de 30 m de la NASA y el METI de Japón (ASTGTM, colección v003). Es un segundo respaldo de relieve, después
de Copernicus DEM. Se baja el mosaico de 1° del lote por CMR + Earthdata y se lee con rasterio solo la
ventana del lote. No importa a ningún otro satélite (spec 009).

ASTER GDEM v3 es un COMPUESTO de tomas de 2000 a 2013 (publicado en 2019): es un dato fijo por lugar.
"""

import math
from datetime import date

import httpx
import numpy as np

from rotaterra.contrato import Observacion
from rotaterra.fuentes import earthdata
from rotaterra.fuentes.registro import Satelite
from rotaterra.geo import validar_poligono

PRODUCTO = "ASTGTM"
FECHA = date(2019, 8, 5)       # publicación de ASTER GDEM v3 (compuesto de tomas 2000–2013)
RESOLUCION_M = 30
INVALIDO = -9999               # valor de relleno de ASTER GDEM
ALTURA_MIN, ALTURA_MAX = -500, 9000
UMBRAL_AMBIENTE_M = 1.0        # SUPUESTO de arranque (el mismo de NASADEM): calibrar con asesores locales
MIN_PIXELES = 10
_R = 6371008.8
GDAL = {"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR", "GDAL_HTTP_MAX_RETRY": "3", "GDAL_HTTP_RETRY_DELAY": "2"}
VARIABLES = [("altura_media_m", "m"), ("altura_min_m", "m"), ("altura_max_m", "m"),
             ("pendiente_media_pct", "%"), ("superficie_bajo_ha", "ha"),
             ("superficie_media_loma_ha", "ha"), ("superficie_loma_ha", "ha")]


class ErrorASTER(Exception):
    """La NASA no respondió o respondió algo ilegible."""


# ---------- mosaicos de 1° × 1° (CMR + Earthdata) ----------

def urls_mosaicos(cliente: httpx.Client, caja: tuple[float, float, float, float]) -> list[str]:
    """URLs de los GeoTIFF de altura (_dem.tif) de los mosaicos que tocan la caja (oeste, sur, este, norte)."""
    coleccion = earthdata.coleccion_vigente(cliente, PRODUCTO)
    if coleccion is None:
        raise ErrorASTER(f"CMR no tiene {PRODUCTO}")
    respuesta = cliente.get(f"{earthdata.URL_CMR}/granules.umm_json",
                            params={"collection_concept_id": coleccion, "page_size": 20,
                                    "bounding_box": ",".join(str(c) for c in caja)})
    respuesta.raise_for_status()
    urls = []
    for item in respuesta.json()["items"]:
        for u in item["umm"].get("RelatedUrls", []):
            url = u.get("URL", "")
            if u.get("Type") == "GET DATA" and url.lower().endswith("_dem.tif") and url.startswith("https"):
                urls.append(url)
    return urls


def bajar_tif(cliente: httpx.Client, url: str) -> bytes:
    respuesta = cliente.get(url)
    if respuesta.status_code in (401, 403):
        raise ErrorASTER("La NASA negó el acceso: ¿está autorizada la aplicación LP DAAC en Earthdata?")
    respuesta.raise_for_status()
    return respuesta.content


def leer_grilla(tiles: list[bytes], caja: tuple[float, float, float, float]):
    """Alturas de la caja del lote (con un píxel de margen), uniendo los mosaicos que hagan falta.

    Devuelve (alturas en m con NaN donde no hay dato, latitud de cada fila, longitud de cada columna,
    tamaño del píxel en grados (x, y)).
    """
    import rasterio
    from rasterio.io import MemoryFile
    from rasterio.merge import merge

    oeste, sur, este, norte = caja
    memorias = [MemoryFile(t) for t in tiles]
    with rasterio.Env(**GDAL):
        fuentes = [m.open() for m in memorias]
        try:
            rx = min(abs(f.transform.a) for f in fuentes)
            ry = min(abs(f.transform.e) for f in fuentes)
            x0, y0 = fuentes[0].transform.c, fuentes[0].transform.f  # borde de la grilla del producto
            limites = (x0 + (math.floor((oeste - x0) / rx) - 1) * rx,
                       y0 - (math.ceil((y0 - sur) / ry) + 1) * ry,
                       x0 + (math.ceil((este - x0) / rx) + 1) * rx,
                       y0 - (math.floor((y0 - norte) / ry) - 1) * ry)
            datos, transformada = merge(fuentes, bounds=limites, res=(rx, ry), nodata=np.nan, dtype="float64")
        finally:
            for f in fuentes:
                f.close()
            for m in memorias:
                m.close()
    alturas = datos[0]
    alturas[(alturas == INVALIDO) | (alturas < ALTURA_MIN) | (alturas > ALTURA_MAX)] = np.nan
    lats = transformada.f + (np.arange(alturas.shape[0]) + 0.5) * transformada.e
    lons = transformada.c + (np.arange(alturas.shape[1]) + 0.5) * transformada.a
    return alturas, lats, lons, (abs(transformada.a), abs(transformada.e))


# ---------- cálculo (las mismas reglas que NASADEM, spec 008) ----------

def superficie_ha(poligono: dict) -> float:
    """Superficie del lote en hectáreas (proyección local; error menor a 0,5 % en lotes agrícolas)."""
    from shapely.geometry import Polygon

    anillo = poligono["coordinates"][0]
    lat0 = sum(lat for _, lat in anillo) / len(anillo)
    metros = [(math.radians(lon) * _R * math.cos(math.radians(lat0)), math.radians(lat) * _R) for lon, lat in anillo]
    return Polygon(metros).area / 10_000


def resumir(lote_id: str, poligono: dict, alturas: np.ndarray, lats: np.ndarray, lons: np.ndarray,
            paso: tuple[float, float]) -> list[Observacion]:
    """Las 7 variables de altimetría del lote a partir de la grilla de alturas."""
    import shapely
    from shapely.geometry import shape

    lon_m, lat_m = np.meshgrid(lons, lats)
    dentro = shapely.contains_xy(shape(poligono), lon_m, lat_m)
    validos = dentro & np.isfinite(alturas)
    total, n = int(dentro.sum()), int(validos.sum())
    lat_media = float(np.mean(lats))
    lado_y = _R * math.radians(paso[1])
    lado_x = _R * math.radians(paso[0]) * math.cos(math.radians(lat_media))
    dz_dy, dz_dx = np.gradient(alturas, lado_y, lado_x)
    pendiente = 100 * np.hypot(dz_dx, dz_dy)

    base = dict(lote_id=lote_id, fecha=FECHA, fuente="ASTER", resolucion_m=RESOLUCION_M)
    detalle = (f"ASTER GDEM v3 de la NASA y el METI (compuesto de tomas 2000–2013, publicado en 2019) · "
               f"modelo de superficie: incluye árboles y construcciones · "
               f"{n} de {total} píxeles de ~{lado_y:.0f} × {lado_x:.0f} m con dato · respaldo de NASADEM")
    if n == 0:
        nota = f"Sin píxeles con dato dentro del lote · {detalle}"
        return [Observacion(**base, variable=v, valor=None, unidad=u, calidad="descartada", nota=nota)
                for v, u in VARIABLES]

    h = alturas[validos]
    media = float(h.mean())
    p = pendiente[validos]
    hectareas = superficie_ha(poligono)
    bajo = float((h < media - UMBRAL_AMBIENTE_M).sum()) / n
    loma = float((h > media + UMBRAL_AMBIENTE_M).sum()) / n
    valores = {
        "altura_media_m": round(media, 1),
        "altura_min_m": round(float(h.min()), 1),
        "altura_max_m": round(float(h.max()), 1),
        "pendiente_media_pct": round(float(np.nanmean(p)), 2) if np.isfinite(p).any() else None,
        "superficie_bajo_ha": round(bajo * hectareas, 2),
        "superficie_loma_ha": round(loma * hectareas, 2),
    }
    valores["superficie_media_loma_ha"] = round(hectareas - valores["superficie_bajo_ha"]
                                                - valores["superficie_loma_ha"], 2)
    calidad = "dudosa" if n < MIN_PIXELES else "buena"
    aviso = f"menos de {MIN_PIXELES} píxeles (lote menor a ~1 ha) · " if calidad == "dudosa" else ""
    ambientes = (f"bajo / loma = más de {UMBRAL_AMBIENTE_M:g} m por debajo / por encima de la media del lote "
                 f"(umbral supuesto, a calibrar) · proporción de píxeles × {hectareas:.1f} ha del lote · ")
    observaciones = []
    for variable, unidad in VARIABLES:
        valor = valores[variable]
        nota = aviso + (ambientes if variable.startswith("superficie") else "") + detalle
        if valor is None:
            observaciones.append(Observacion(**base, variable=variable, valor=None, unidad=unidad,
                                             calidad="descartada", nota=f"Sin vecinos para calcular la pendiente · {nota}"))
        else:
            observaciones.append(Observacion(**base, variable=variable, valor=valor, unidad=unidad,
                                             calidad=calidad, nota=nota))
    return observaciones


def obtener_altimetria(lote_id: str, poligono: dict, cliente: httpx.Client | None = None) -> list[Observacion]:
    """Altura, pendiente y ambientes del lote con ASTER GDEM. Dato fijo: se pide una sola vez."""
    validar_poligono(poligono)
    from rasterio.errors import RasterioError
    from shapely.geometry import shape

    caja = shape(poligono).bounds
    try:
        cliente = earthdata.cliente_autorizado(cliente)
        urls = urls_mosaicos(cliente, caja)
        if not urls:
            raise ErrorASTER("ASTER GDEM no tiene datos para este lugar (¿lote en el mar?)")
        tiles = [bajar_tif(cliente, u) for u in urls]
    except earthdata.FaltanCredenciales:
        raise
    except (httpx.HTTPError, ValueError, earthdata.ErrorNASA) as error:
        raise ErrorASTER(f"No se pudo obtener la altimetría de ASTER GDEM: {error}") from error
    try:
        grilla = leer_grilla(tiles, caja)
    except (RasterioError, ValueError) as error:
        raise ErrorASTER(f"No se pudo leer el GeoTIFF de ASTER GDEM: {error}") from error
    return resumir(lote_id, poligono, *grilla)


# ---------- conexión con el núcleo (spec 009) ----------
# Sin endpoint propio: la app pide POST /altimetria (NASADEM) y el núcleo usa este respaldo si NASADEM falla.
# orden=2: entra después de Copernicus DEM (orden 1).

SATELITES = [Satelite("NASADEM:ASTER", lambda lote, desde, hasta: obtener_altimetria(lote["id"], lote["poligono"]),
                      respaldo_de="NASADEM", estatico=True, orden=2)]
