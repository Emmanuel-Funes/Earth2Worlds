"""Conector VIIRS: NDVI de 500 m del lote, primer respaldo de HLS y continuidad de MODIS (spec 011)."""

import math
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import httpx
import numpy as np

from rotaterra.contrato import Observacion
from rotaterra.fuentes import earthdata
from rotaterra.fuentes.registro import Satelite
from rotaterra.geo import validar_poligono

# VIIRS de NOAA-20 (VJ1) y NOAA-21 (VJ2): compuestos de 16 días desfasados, uno cada 8 días entre los dos.
# Suomi NPP (VNP13A1) queda afuera: deja de entregar datos el 1/11/2026.
PRODUCTOS = {"VJ113A1": "NOAA-20", "VJ213A1": "NOAA-21"}
ESCALA = 0.0001
NDVI_MIN, NDVI_MAX = -10000, 10000  # rango válido crudo; afuera es relleno
CONFIABLES = (0, 1)  # supuesto (spec 011): 0 = buena, 1 = aceptable; se verifica en la prueba real
RESOLUCION_M = 500
HILOS = 4
MAX_DIAS = 366
UNIDAD = "índice (-1 a 1)"
UMBRAL_BUENA = 60.0       # % de píxeles válidos: mismos umbrales que HLS y MODIS
UMBRAL_DESCARTADA = 20.0

# Grilla sinusoidal (la misma de MODIS): mosaicos de 2400 × 2400 píxeles de ~463 m
_R = 6371007.181
_MOSAICO = 1111950.5197665
_LADO = 2400
_PIXEL = _MOSAICO / _LADO
_X0, _Y0 = -20015109.354, 10007554.677

# qué capa buscar en cada archivo: el nombre exacto se lee de los metadatos (.dmr) de la NASA
_CAPAS = {
    "ndvi": re.compile(r"NDVI$"),
    "confiabilidad": re.compile(r"pixel_reliability$", re.I),
    "dia": re.compile(r"day_of_the_year$", re.I),
}
_RUTAS: dict[str, dict[str, str]] = {}  # producto -> capa -> ruta en el archivo


class ErrorVIIRS(Exception):
    """La NASA no respondió o respondió algo ilegible."""


def validar_pedido(poligono: dict, desde: date, hasta: date) -> None:
    validar_poligono(poligono)
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise ValueError(f"El rango supera {MAX_DIAS} días")


def celda(lat: float, lon: float) -> tuple[int, int, int, int]:
    """Mosaico (h, v) y píxel (fila, columna) de 500 m que contienen el punto."""
    x = _R * math.radians(lon) * math.cos(math.radians(lat))
    y = _R * math.radians(lat)
    h, v = math.floor((x - _X0) / _MOSAICO), math.floor((_Y0 - y) / _MOSAICO)
    columna = math.floor((x - _X0 - h * _MOSAICO) / _PIXEL)
    fila = math.floor((_Y0 - y - v * _MOSAICO) / _PIXEL)
    return h, v, fila, columna


def ventana(poligono: dict) -> tuple[int, int, int, int, int, int]:
    """Mosaico y ventana de píxeles (fila0, fila1, col0, col1) que cubren el lote, con un píxel de margen."""
    from shapely.geometry import shape

    centro = shape(poligono).centroid
    h, v, _, _ = celda(centro.y, centro.x)
    filas, columnas = [], []
    for lon, lat in poligono["coordinates"][0]:
        hh, vv, fila, columna = celda(lat, lon)
        filas.append(fila + (vv - v) * _LADO)
        columnas.append(columna + (hh - h) * _LADO)
    f0, f1 = max(min(filas) - 1, 0), min(max(filas) + 1, _LADO - 1)
    c0, c1 = max(min(columnas) - 1, 0), min(max(columnas) + 1, _LADO - 1)
    if c1 == c0:  # el servidor no devuelve recortes de una sola columna
        c0 = max(c0 - 1, 0) if c1 == _LADO - 1 else c0
        c1 = c0 + 1
    return h, v, f0, f1, c0, c1


def coordenadas(h: int, v: int, f0: int, f1: int, c0: int, c1: int) -> tuple[np.ndarray, np.ndarray]:
    """Latitud y longitud del centro de cada píxel de la ventana (se calculan: no dependen del archivo)."""
    filas, columnas = np.arange(f0, f1 + 1), np.arange(c0, c1 + 1)
    y = _Y0 - v * _MOSAICO - (filas[:, None] + 0.5) * _PIXEL + 0 * columnas[None, :]
    x = _X0 + h * _MOSAICO + (columnas[None, :] + 0.5) * _PIXEL + 0 * filas[:, None]
    lat = np.degrees(y / _R)
    lon = np.degrees(x / (_R * np.cos(np.radians(lat))))
    return lat, lon


def rutas_de_capas(dmr: str) -> dict[str, str]:
    """Busca en los metadatos DAP4 (.dmr) la ruta de NDVI, confiabilidad y día de adquisición de 500 m."""
    raiz = ET.fromstring(dmr)
    halladas: dict[str, str] = {}

    def recorrer(nodo, camino: str) -> None:
        for hijo in nodo:
            etiqueta = hijo.tag.rsplit("}", 1)[-1]
            nombre = hijo.get("name")
            if not nombre:
                continue
            ruta = f"{camino}/{nombre}"
            if etiqueta == "Group":
                recorrer(hijo, ruta)
            elif "500" in nombre or "500" in camino:
                plano = nombre.replace(" ", "_")
                for capa, patron in _CAPAS.items():
                    if capa not in halladas and patron.search(plano):
                        halladas[capa] = ruta

    recorrer(raiz, "")
    faltan = set(_CAPAS) - set(halladas)
    if faltan:
        raise ErrorVIIRS(f"El archivo no tiene las capas {sorted(faltan)} de 500 m")
    return halladas


def _plano(ruta: str) -> str:
    """Ruta comparable: los nombres de VIIRS llevan espacios ('500 m 16 days NDVI')."""
    return ruta.lstrip("/").replace("%20", " ").replace("_", " ")


def leer_ventana(cliente: httpx.Client, producto: str, url: str,
                 f0: int, f1: int, c0: int, c1: int) -> dict[str, np.ndarray]:
    if producto not in _RUTAS:
        respuesta = cliente.get(f"{url}.dmr")
        respuesta.raise_for_status()
        _RUTAS[producto] = rutas_de_capas(respuesta.text)
    rutas = _RUTAS[producto]
    # en DAP4 los espacios de un nombre se escriben %20 dentro de la expresión
    expresion = ";".join(f"{ruta.replace(' ', '%20')}[{f0}:1:{f1}][{c0}:1:{c1}]" for ruta in rutas.values())
    crudo = {_plano(nombre): filas for nombre, filas in earthdata.leer_csv(cliente, url, expresion).items()}
    datos = {}
    for capa, ruta in rutas.items():
        filas = crudo.get(_plano(ruta))
        if filas is None:
            raise ErrorVIIRS(f"OPeNDAP no devolvió '{capa}' ({ruta}) para {url}")
        datos[capa] = np.array([[np.nan if v is None else v for v in fila] for fila in filas], dtype="float64")
    return datos


def inicio_compuesto(nombre_archivo: str) -> date:
    """VJ113A1.A2026001.h12v12... → 2026-01-01."""
    hallado = re.search(r"\.A(\d{4})(\d{3})\.", nombre_archivo)
    return date(int(hallado[1]), 1, 1) + timedelta(days=int(hallado[2]) - 1)


def resumir(lote_id: str, poligono: dict, datos: dict[str, np.ndarray], inicio: date,
            satelite: str = "NOAA-20", producto: str = "VJ113A1") -> tuple[Observacion, float]:
    """Observación del lote para un compuesto y su % de píxeles válidos."""
    from shapely.geometry import Point, shape

    lote = shape(poligono)
    dentro = np.array([[lote.contains(Point(lon, lat)) for lat, lon in zip(fila_lat, fila_lon)]
                       for fila_lat, fila_lon in zip(datos["lat"], datos["lon"])])
    aviso = ""
    if not dentro.any():  # lote más chico que un píxel de ~21 ha: se usa el píxel que contiene su centro
        centro = lote.centroid
        distancia = (datos["lat"] - centro.y) ** 2 + (datos["lon"] - centro.x) ** 2
        dentro = distancia == np.nanmin(distancia)
        aviso = "lote menor a un píxel: se usa el píxel del centro · "
    ndvi = datos["ndvi"]
    validos = dentro & np.isin(datos["confiabilidad"], CONFIABLES) & np.isfinite(ndvi) \
        & (ndvi >= NDVI_MIN) & (ndvi <= NDVI_MAX)
    total, n_validos = int(dentro.sum()), int(validos.sum())
    pct = 100.0 * n_validos / total
    base = dict(lote_id=lote_id, variable="ndvi", unidad=UNIDAD, fuente="VIIRS", resolucion_m=RESOLUCION_M)
    detalle = (f"Respaldo de HLS · {aviso}{producto} ({satelite}) compuesto del {inicio} · "
               f"{total} píxeles de 500 m · válidos {pct:.0f}%")
    if pct < UMBRAL_DESCARTADA:
        return Observacion(**base, fecha=inicio, valor=None, calidad="descartada",
                           nota=f"Nubes o sin dato · {detalle}"), pct
    dia_del_anio = int(np.median(datos["dia"][validos]))
    anio = inicio.year + (1 if dia_del_anio < inicio.timetuple().tm_yday else 0)  # compuesto que cruza el año
    fecha = date(anio, 1, 1) + timedelta(days=dia_del_anio - 1)
    valor = round(float(np.median(ndvi[validos] * ESCALA)), 3)
    calidad = "buena" if pct >= UMBRAL_BUENA else "dudosa"
    return Observacion(**base, fecha=fecha, valor=valor, calidad=calidad, nota=detalle), pct


def obtener_ndvi(lote_id: str, poligono: dict, desde: date, hasta: date,
                 cliente: httpx.Client | None = None, hilos: int = HILOS) -> list[Observacion]:
    """NDVI VIIRS del lote (NOAA-20 y NOAA-21); si dos compuestos caen el mismo día, gana el más limpio."""
    validar_pedido(poligono, desde, hasta)
    h, v, f0, f1, c0, c1 = ventana(poligono)
    lat, lon = coordenadas(h, v, f0, f1, c0, c1)
    mosaico = f".h{h:02d}v{v:02d}."
    pedidos: list[tuple[str, str, str, str]] = []  # (producto, satélite, archivo, url)
    try:
        cliente = earthdata.cliente_autorizado(cliente)
        from shapely.geometry import shape

        for producto, satelite in PRODUCTOS.items():
            coleccion = earthdata.coleccion_vigente(cliente, producto)
            if coleccion is None:
                continue
            # un compuesto que empezó hasta 15 días antes de 'desde' puede tener fechas de adquisición dentro
            pedidos += [(producto, satelite, nombre, url) for nombre, url in
                        earthdata.archivos(cliente, coleccion, desde - timedelta(days=15), hasta,
                                           caja=shape(poligono).bounds) if mosaico in nombre]
        if not pedidos:
            raise ErrorVIIRS(f"CMR no tiene compuestos de {', '.join(PRODUCTOS)} con OPeNDAP para el lote")
        with ThreadPoolExecutor(max_workers=hilos) as grupo:
            ventanas = list(grupo.map(lambda p: leer_ventana(cliente, p[0], p[3], f0, f1, c0, c1), pedidos))
    except earthdata.FaltanCredenciales:
        raise
    except (httpx.HTTPError, KeyError, ValueError, ET.ParseError, earthdata.ErrorNASA) as error:
        raise ErrorVIIRS(f"No se pudo obtener el NDVI de VIIRS: {error}") from error
    mejores: dict[date, tuple[Observacion, float]] = {}
    for (producto, satelite, nombre, _), datos in zip(pedidos, ventanas):
        obs, pct = resumir(lote_id, poligono, {**datos, "lat": lat, "lon": lon},
                           inicio_compuesto(nombre), satelite, producto)
        if desde <= obs.fecha <= hasta and (obs.fecha not in mejores or pct > mejores[obs.fecha][1]):
            mejores[obs.fecha] = (obs, pct)
    return [obs for _, (obs, _) in sorted(mejores.items())]


# ---------- conexión con el núcleo (spec 009) ----------

# segundo respaldo de HLS, después de Sentinel-2 (spec 014); si VIIRS tampoco tiene datos, entra MODIS (specs 005 y 011)
SATELITES = [Satelite("HLS:VIIRS", lambda lote, desde, hasta: obtener_ndvi(lote["id"], lote["poligono"], desde, hasta),
                      respaldo_de="HLS", orden=2)]
