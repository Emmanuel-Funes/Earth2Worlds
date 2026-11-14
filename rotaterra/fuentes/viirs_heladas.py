"""Conector VIIRS LST nocturna: temperatura de la superficie de noche del lote, para alertar heladas (spec 030).

Satélite independiente (spec 009): hace su propio pedido a la NASA y no importa a ningún otro satélite,
aunque comparta con el VIIRS de NDVI la grilla sinusoidal (se repite acá a propósito).

NOAA es una de las agencias socias permitidas (spec 008). El producto da la temperatura de la **superficie**
(suelo/canopeo) de noche, no la del aire: una helada agronómica se decide con esto más el criterio del productor.
"""

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

# LST nocturna diaria de 1 km: NOAA-20 (VJ1) y NOAA-21 (VJ2). Suomi NPP (VNP21A1N) queda afuera: fin de datos 1/11/2026.
PRODUCTOS = {"VJ121A1N": "NOAA-20", "VJ221A1N": "NOAA-21"}
ESCALA = 0.02                 # factor del producto MODIS/VIIRS LST: crudo * 0,02 = kelvin
CERO_ABS = 273.15
KELVIN_MIN, KELVIN_MAX = 150.0, 400.0  # rango físico sano; afuera (o crudo 0) es relleno/nubes
RESOLUCION_M = 1000
HILOS = 4
MAX_DIAS = 366
UNIDAD = "°C"
UMBRAL_HELADA = 0.0           # a 0 °C o menos de superficie, se avisa riesgo de helada
UMBRAL_BUENA = 60.0           # % de píxeles válidos del lote (mismos umbrales que NDVI)
UMBRAL_DESCARTADA = 20.0

# Grilla sinusoidal de 1 km: mosaicos de 1200 × 1200 píxeles de ~926 m
_R = 6371007.181
_MOSAICO = 1111950.5197665
_LADO = 1200
_PIXEL = _MOSAICO / _LADO
_X0, _Y0 = -20015109.354, 10007554.677

_CAPA_LST = re.compile(r"LST_1KM$", re.I)


class ErrorVIIRSHeladas(Exception):
    """La NASA no respondió o respondió algo ilegible."""


def validar_pedido(poligono: dict, desde: date, hasta: date) -> None:
    validar_poligono(poligono)
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise ValueError(f"El rango supera {MAX_DIAS} días")


def celda(lat: float, lon: float) -> tuple[int, int, int, int]:
    """Mosaico (h, v) y píxel (fila, columna) de 1 km que contienen el punto."""
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


def ruta_lst(dmr: str) -> str:
    """Busca en los metadatos DAP4 (.dmr) la ruta de la capa LST_1KM (temperatura de superficie de 1 km)."""
    raiz = ET.fromstring(dmr)
    hallada = [None]

    def recorrer(nodo, camino: str) -> None:
        for hijo in nodo:
            etiqueta = hijo.tag.rsplit("}", 1)[-1]
            nombre = hijo.get("name")
            if not nombre:
                continue
            ruta = f"{camino}/{nombre}"
            if etiqueta == "Group":
                recorrer(hijo, ruta)
            elif hallada[0] is None and _CAPA_LST.search(nombre.replace(" ", "_")):
                hallada[0] = ruta

    recorrer(raiz, "")
    if hallada[0] is None:
        raise ErrorVIIRSHeladas("El archivo no tiene la capa LST_1KM")
    return hallada[0]


_RUTAS: dict[str, str] = {}  # producto -> ruta de LST_1KM en el archivo


def leer_ventana(cliente: httpx.Client, producto: str, url: str,
                 f0: int, f1: int, c0: int, c1: int) -> np.ndarray:
    if producto not in _RUTAS:
        respuesta = cliente.get(f"{url}.dmr")
        respuesta.raise_for_status()
        _RUTAS[producto] = ruta_lst(respuesta.text)
    ruta = _RUTAS[producto]
    expresion = f"{ruta.replace(' ', '%20')}[{f0}:1:{f1}][{c0}:1:{c1}]"
    crudo = earthdata.leer_csv(cliente, url, expresion)
    # la clave que devuelve OPeNDAP puede ser el nombre corto o la ruta entera; basta que termine en LST_1KM
    filas = next((f for nombre, f in crudo.items() if nombre.replace("%20", " ").rstrip("/").endswith("LST_1KM")), None)
    if filas is None:
        raise ErrorVIIRSHeladas(f"OPeNDAP no devolvió la capa LST_1KM para {url}")
    return np.array([[np.nan if v is None else v for v in fila] for fila in filas], dtype="float64")


def fecha_granulo(nombre_archivo: str) -> date:
    """VJ121A1N.A2026265.h12v12... → 2026-09-22 (producto diario)."""
    hallado = re.search(r"\.A(\d{4})(\d{3})\.", nombre_archivo)
    return date(int(hallado[1]), 1, 1) + timedelta(days=int(hallado[2]) - 1)


def resumir(lote_id: str, poligono: dict, lst_crudo: np.ndarray, lat: np.ndarray, lon: np.ndarray,
            fecha: date, satelite: str, producto: str) -> tuple[Observacion, float]:
    """Observación del lote para una noche: la temperatura de superficie MÍNIMA de los píxeles del lote, y su % válido."""
    from shapely.geometry import Point, shape

    lote = shape(poligono)
    dentro = np.array([[lote.contains(Point(x, y)) for y, x in zip(fila_lat, fila_lon)]
                       for fila_lat, fila_lon in zip(lat, lon)])
    aviso = ""
    if not dentro.any():  # lote más chico que un píxel de 1 km: se usa el píxel que contiene su centro
        centro = lote.centroid
        distancia = (lat - centro.y) ** 2 + (lon - centro.x) ** 2
        dentro = distancia == np.nanmin(distancia)
        aviso = "lote menor a un píxel de 1 km: se usa el píxel del centro · "
    kelvin = lst_crudo * ESCALA
    validos = dentro & np.isfinite(kelvin) & (lst_crudo > 0) & (kelvin >= KELVIN_MIN) & (kelvin <= KELVIN_MAX)
    total, n_validos = int(dentro.sum()), int(validos.sum())
    pct = 100.0 * n_validos / total if total else 0.0
    base = dict(lote_id=lote_id, fecha=fecha, variable="temp_sup_min_c", unidad=UNIDAD,
                fuente="VIIRS", resolucion_m=RESOLUCION_M)
    detalle = (f"VIIRS LST nocturna (temperatura de superficie, no del aire) · {aviso}{producto} ({satelite}) · "
               f"noche del {fecha} · {total} píxeles de 1 km · válidos {pct:.0f}%")
    if pct < UMBRAL_DESCARTADA:
        return Observacion(**base, valor=None, calidad="descartada", nota=f"Nubes o sin dato · {detalle}"), pct
    valor = round(float(np.min(kelvin[validos]) - CERO_ABS), 1)
    riesgo = " · riesgo de helada (≤ 0 °C de superficie)" if valor <= UMBRAL_HELADA else ""
    calidad = "buena" if pct >= UMBRAL_BUENA else "dudosa"
    return Observacion(**base, valor=valor, calidad=calidad, nota=f"{detalle}{riesgo}"), pct


def obtener_heladas(lote_id: str, poligono: dict, desde: date, hasta: date,
                    cliente: httpx.Client | None = None, hilos: int = HILOS) -> list[Observacion]:
    """Temperatura de superficie nocturna mínima del lote por noche (NOAA-20 y NOAA-21); por día gana el más limpio."""
    validar_pedido(poligono, desde, hasta)
    h, v, f0, f1, c0, c1 = ventana(poligono)
    lat, lon = coordenadas(h, v, f0, f1, c0, c1)
    mosaico = f".h{h:02d}v{v:02d}."
    pedidos: list[tuple[str, str, str, str]] = []  # (producto, satélite, nombre, url)
    try:
        cliente = earthdata.cliente_autorizado(cliente)
        from shapely.geometry import shape

        for producto, satelite in PRODUCTOS.items():
            coleccion = earthdata.coleccion_vigente(cliente, producto)
            if coleccion is None:  # un satélite que la NASA todavía no publica no frena al otro
                continue
            pedidos += [(producto, satelite, nombre, url) for nombre, url in
                        earthdata.archivos(cliente, coleccion, desde, hasta, caja=shape(poligono).bounds)
                        if mosaico in nombre]
        if not pedidos:
            raise ErrorVIIRSHeladas(f"CMR no tiene archivos de {', '.join(PRODUCTOS)} con OPeNDAP para el lote")
        with ThreadPoolExecutor(max_workers=hilos) as grupo:
            ventanas = list(grupo.map(lambda p: leer_ventana(cliente, p[0], p[3], f0, f1, c0, c1), pedidos))
    except earthdata.FaltanCredenciales:
        raise
    except (httpx.HTTPError, KeyError, ValueError, ET.ParseError, earthdata.ErrorNASA) as error:
        raise ErrorVIIRSHeladas(f"No se pudo obtener la LST de VIIRS: {error}") from error

    mejores: dict[date, tuple[Observacion, float]] = {}
    for (producto, satelite, nombre, _), lst_crudo in zip(pedidos, ventanas):
        fecha = fecha_granulo(nombre)
        if not desde <= fecha <= hasta:
            continue
        obs, pct = resumir(lote_id, poligono, lst_crudo, lat, lon, fecha, satelite, producto)
        if fecha not in mejores or pct > mejores[fecha][1]:
            mejores[fecha] = (obs, pct)
    return [obs for _, (obs, _) in sorted(mejores.items())]


# ---------- conexión con el núcleo (spec 009) ----------

# Fuente nueva de temperatura de superficie nocturna (variable temp_sup_min_c). No es respaldo de nadie:
# es una señal propia para alertar heladas. Todavía sin respaldo (MODIS MOD11A1 podría serlo cuando se sume).
SATELITES = [Satelite("VIIRS_LST", lambda lote, desde, hasta: obtener_heladas(lote["id"], lote["poligono"], desde, hasta))]
