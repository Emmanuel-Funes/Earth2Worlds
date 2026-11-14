"""Conector Copernicus DEM GLO-30 (ESA): altura, pendiente y ambientes del lote, respaldo de NASADEM (spec 016).

Mismas 7 variables y mismas reglas que NASADEM (spec 008), con el modelo de la ESA hecho con TanDEM-X.
Se lee sin credenciales del bucket público de AWS Open Data que distribuye los archivos de la ESA.
"""

import math
import re
from datetime import date

import httpx
import numpy as np

from rotaterra.contrato import Observacion
from rotaterra.fuentes.registro import Satelite
from rotaterra.geo import validar_poligono

URL_BASE = "https://copernicus-dem-30m.s3.amazonaws.com"  # AWS Open Data: aloja los archivos de la ESA tal cual
RESOLUCION_M = 30
INVALIDO = -32767  # valor que la ESA usa para píxeles inválidos
ALTURA_MIN, ALTURA_MAX = -500, 9000
UMBRAL_AMBIENTE_M = 1.0  # SUPUESTO de arranque (el mismo de NASADEM): calibrar con asesores locales
MIN_PIXELES = 10
SEGUNDO = 1 / 3600  # 1 segundo de arco (~30 m); más al norte de 50° la grilla es más ancha en longitud
MARGEN = 10 * SEGUNDO  # margen para elegir mosaicos (cubre el píxel extra que pide la pendiente)
_R = 6371008.8
GDAL = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",  # no listar la carpeta del bucket al abrir el COG
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    "GDAL_HTTP_MAX_RETRY": "3",
    "GDAL_HTTP_RETRY_DELAY": "2",
}
VARIABLES = [("altura_media_m", "m"), ("altura_min_m", "m"), ("altura_max_m", "m"),
             ("pendiente_media_pct", "%"), ("superficie_bajo_ha", "ha"),
             ("superficie_media_loma_ha", "ha"), ("superficie_loma_ha", "ha")]


class ErrorCOPDEM(Exception):
    """El bucket de Copernicus DEM no respondió o respondió algo ilegible."""


# ---------- mosaicos de 1° × 1° ----------

def nombre_mosaico(lat: float, lon: float) -> str:
    """Mosaico que contiene el punto, por su esquina suroeste: (-33.7, -65.3) → 'S34_00_W066_00'."""
    sur, oeste = math.floor(lat), math.floor(lon)
    return f"{'N' if sur >= 0 else 'S'}{abs(sur):02d}_00_{'E' if oeste >= 0 else 'W'}{abs(oeste):03d}_00"


def mosaicos_de_la_caja(caja: tuple[float, float, float, float]) -> list[str]:
    """Todos los mosaicos que toca la caja (oeste, sur, este, norte), con un margen para la pendiente."""
    oeste, sur, este, norte = caja
    return [nombre_mosaico(lat + 0.5, lon + 0.5)
            for lat in range(math.floor(sur - MARGEN), math.floor(norte + MARGEN) + 1)
            for lon in range(math.floor(oeste - MARGEN), math.floor(este + MARGEN) + 1)]


def carpeta(nombre: str) -> str:
    return f"Copernicus_DSM_COG_10_{nombre}_DEM"


def url_tif(nombre: str) -> str:
    return f"{URL_BASE}/{carpeta(nombre)}/{carpeta(nombre)}.tif"


def url_xml(nombre: str) -> str:
    return f"{URL_BASE}/{carpeta(nombre)}/Copernicus_DSM_10_{nombre}.xml"


def periodo_de_toma(xml: str) -> tuple[date, date]:
    """Primer y último día en que TanDEM-X midió ese mosaico, según el XML de la ESA."""
    fechas = []
    for etiqueta in ("tsxx_startTime", "tsxx_stopTime"):
        hallado = re.search(rf"<(?:\w+:)?{etiqueta}>\s*(\d{{4}}-\d{{2}}-\d{{2}})", xml)
        if hallado is None:
            raise ErrorCOPDEM(f"El XML del mosaico no trae '{etiqueta}': no se inventa una fecha")
        fechas.append(date.fromisoformat(hallado.group(1)))
    return fechas[0], fechas[1]


def buscar_mosaicos(cliente: httpx.Client, caja: tuple[float, float, float, float]) -> dict[str, tuple[date, date]]:
    """Mosaico → período de toma, de los que existen (en el mar no hay mosaico: el XML da 404)."""
    existentes = {}
    for nombre in mosaicos_de_la_caja(caja):
        respuesta = cliente.get(url_xml(nombre))
        if respuesta.status_code == 404:
            continue
        respuesta.raise_for_status()
        existentes[nombre] = periodo_de_toma(respuesta.text)
    return existentes


# ---------- lectura de la ventana del lote ----------

def leer_grilla(rutas: list[str], caja: tuple[float, float, float, float]):
    """Alturas de la caja del lote (con un píxel de margen), uniendo los mosaicos que hagan falta.

    Lee con rasterio solo la ventana necesaria de cada COG, alineada a la grilla del producto.
    Devuelve (alturas en m con NaN donde no hay dato, latitud de cada fila, longitud de cada columna,
    tamaño del píxel en grados (x, y)).
    """
    import rasterio
    from rasterio.merge import merge

    oeste, sur, este, norte = caja
    with rasterio.Env(**GDAL):
        fuentes = [rasterio.open(r) for r in rutas]
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
            paso: tuple[float, float], toma: tuple[date, date]) -> list[Observacion]:
    """Las 7 variables de altimetría del lote a partir de la grilla de alturas."""
    import shapely
    from shapely.geometry import shape

    lon_m, lat_m = np.meshgrid(lons, lats)
    dentro = shapely.contains_xy(shape(poligono), lon_m, lat_m)
    validos = dentro & np.isfinite(alturas)
    total, n = int(dentro.sum()), int(validos.sum())
    lat_media = float(np.mean(lats))
    # pendiente con el tamaño real del píxel a esta latitud (norte-sur y este-oeste)
    lado_y = _R * math.radians(paso[1])
    lado_x = _R * math.radians(paso[0]) * math.cos(math.radians(lat_media))
    dz_dy, dz_dx = np.gradient(alturas, lado_y, lado_x)
    pendiente = 100 * np.hypot(dz_dx, dz_dy)

    inicio, fin = toma
    base = dict(lote_id=lote_id, fecha=fin, fuente="COPDEM", resolucion_m=RESOLUCION_M)
    detalle = (f"Copernicus DEM GLO-30 de la ESA (TanDEM-X, tomado del {inicio:%d/%m/%Y} al {fin:%d/%m/%Y}; "
               f"vía AWS Open Data) · modelo de superficie: incluye árboles y construcciones · "
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
    """Altura, pendiente y ambientes del lote con Copernicus DEM. Dato fijo: se pide una sola vez."""
    validar_poligono(poligono)
    from rasterio.errors import RasterioError
    from shapely.geometry import shape

    caja = shape(poligono).bounds
    propio = cliente is None
    cliente = cliente or httpx.Client(timeout=60, follow_redirects=True)
    try:
        mosaicos = buscar_mosaicos(cliente, caja)
        if not mosaicos:
            raise ErrorCOPDEM("Copernicus DEM no tiene datos para este lugar (¿lote en el mar?)")
        grilla = leer_grilla([url_tif(n) for n in mosaicos], caja)
    except (httpx.HTTPError, RasterioError, ValueError) as error:
        raise ErrorCOPDEM(f"No se pudo obtener la altimetría de Copernicus DEM: {error}") from error
    finally:
        if propio:
            cliente.close()
    periodos = list(mosaicos.values())
    toma = (min(i for i, _ in periodos), max(f for _, f in periodos))
    return resumir(lote_id, poligono, *grilla, toma)


# ---------- conexión con el núcleo (spec 009) ----------
# Sin endpoint propio: la app pide POST /altimetria (NASADEM) y el núcleo usa este respaldo si NASADEM falla.

SATELITES = [Satelite("NASADEM:COPDEM", lambda lote, desde, hasta: obtener_altimetria(lote["id"], lote["poligono"]),
                      respaldo_de="NASADEM", estatico=True)]
