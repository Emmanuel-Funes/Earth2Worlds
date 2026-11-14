"""Conector MODIS: NDVI de 250 m del lote, respaldo de HLS (spec 007)."""

import math
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import httpx
import numpy as np

from rotaterra.contrato import Observacion
from rotaterra.fuentes import earthdata
from rotaterra.geo import validar_poligono
from rotaterra.fuentes.registro import Satelite

PRODUCTO = "MOD13Q1"  # Terra; Aqua (MYD13Q1) no tiene servicio OPeNDAP en la NASA
GRUPO = "/MODIS_Grid_16DAY_250m_500m_VI"
CAPAS = {
    "ndvi": f"{GRUPO}/Data_Fields/_250m_16_days_NDVI",
    "confiabilidad": f"{GRUPO}/Data_Fields/_250m_16_days_pixel_reliability",
    "dia": f"{GRUPO}/Data_Fields/_250m_16_days_composite_day_of_the_year",
    "lat": f"{GRUPO}/Latitude",
    "lon": f"{GRUPO}/Longitude",
}
ESCALA = 0.0001
RELLENO_NDVI = -3000
CONFIABLES = (0, 1)  # 0 = buena, 1 = marginal; 2 = nieve, 3 = nube, -1 = sin dato
RESOLUCION_M = 250
HILOS = 4
MAX_DIAS = 366
UNIDAD = "índice (-1 a 1)"
UMBRAL_BUENA = 60.0       # % de píxeles válidos: mismos umbrales que HLS (spec 007)
UMBRAL_DESCARTADA = 20.0

# Grilla sinusoidal de MODIS: mosaicos de 4800 × 4800 píxeles
_R = 6371007.181
_MOSAICO = 1111950.5197665
_PIXEL = _MOSAICO / 4800
_X0, _Y0 = -20015109.354, 10007554.677


class ErrorMODIS(Exception):
    """La NASA no respondió o respondió algo ilegible."""


def validar_pedido(poligono: dict, desde: date, hasta: date) -> None:
    validar_poligono(poligono)
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise ValueError(f"El rango supera {MAX_DIAS} días")


def celda(lat: float, lon: float) -> tuple[int, int, int, int]:
    """Mosaico (h, v) y píxel (fila, columna) de MODIS que contienen el punto."""
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
        filas.append(fila + (vv - v) * 4800)
        columnas.append(columna + (hh - h) * 4800)
    f0, f1 = max(min(filas) - 1, 0), min(max(filas) + 1, 4799)
    c0, c1 = max(min(columnas) - 1, 0), min(max(columnas) + 1, 4799)
    if c1 == c0:  # el servidor no devuelve recortes de una sola columna
        c0 = max(c0 - 1, 0) if c1 == 4799 else c0
        c1 = c0 + 1
    return h, v, f0, f1, c0, c1


def leer_ventana(cliente: httpx.Client, url: str, f0: int, f1: int, c0: int, c1: int) -> dict[str, np.ndarray]:
    expresion = ";".join(f"{ruta}[{f0}:1:{f1}][{c0}:1:{c1}]" for ruta in CAPAS.values())
    crudo = earthdata.leer_csv(cliente, url, expresion)
    datos = {}
    for nombre, ruta in CAPAS.items():
        filas = crudo.get(ruta.lstrip("/"))
        if filas is None:
            raise ErrorMODIS(f"OPeNDAP no devolvió '{nombre}' para {url}")
        datos[nombre] = np.array([[np.nan if v is None else v for v in fila] for fila in filas], dtype="float64")
    return datos


def inicio_compuesto(nombre_archivo: str) -> date:
    """MOD13Q1.A2026001.h12v12... → 2026-01-01."""
    hallado = re.search(r"\.A(\d{4})(\d{3})\.", nombre_archivo)
    return date(int(hallado[1]), 1, 1) + timedelta(days=int(hallado[2]) - 1)


def resumir(lote_id: str, poligono: dict, datos: dict[str, np.ndarray], inicio: date) -> Observacion:
    from shapely.geometry import Point, shape

    lote = shape(poligono)
    dentro = np.array([[lote.contains(Point(lon, lat)) for lat, lon in zip(fila_lat, fila_lon)]
                       for fila_lat, fila_lon in zip(datos["lat"], datos["lon"])])
    aviso = ""
    if not dentro.any():  # lote más chico que un píxel de 6 ha: se usa el píxel que contiene su centro
        centro = lote.centroid
        distancia = (datos["lat"] - centro.y) ** 2 + (datos["lon"] - centro.x) ** 2
        dentro = distancia == np.nanmin(distancia)
        aviso = "lote menor a un píxel: se usa el píxel del centro · "
    validos = dentro & np.isin(datos["confiabilidad"], CONFIABLES) & (datos["ndvi"] != RELLENO_NDVI) \
        & np.isfinite(datos["ndvi"])
    total, n_validos = int(dentro.sum()), int(validos.sum())
    pct = 100.0 * n_validos / total
    base = dict(lote_id=lote_id, variable="ndvi", unidad=UNIDAD, fuente="MODIS", resolucion_m=RESOLUCION_M)
    detalle = (f"Respaldo de HLS · {aviso}MOD13Q1 compuesto del {inicio} · {total} píxeles de 250 m · "
               f"válidos {pct:.0f}%")
    if pct < UMBRAL_DESCARTADA:
        return Observacion(**base, fecha=inicio, valor=None, calidad="descartada",
                           nota=f"Nubes, nieve o sin dato · {detalle}")
    dias = datos["dia"][validos]
    dia_del_anio = int(np.median(dias))
    anio = inicio.year + (1 if dia_del_anio < inicio.timetuple().tm_yday else 0)  # compuesto que cruza el año
    fecha = date(anio, 1, 1) + timedelta(days=dia_del_anio - 1)
    valor = round(float(np.median(datos["ndvi"][validos] * ESCALA)), 3)
    if not -1 <= valor <= 1:
        return Observacion(**base, fecha=fecha, valor=None, calidad="descartada", nota=f"NDVI fuera de -1 a 1 · {detalle}")
    calidad = "buena" if pct >= UMBRAL_BUENA else "dudosa"
    return Observacion(**base, fecha=fecha, valor=valor, calidad=calidad, nota=detalle)


def obtener_ndvi(lote_id: str, poligono: dict, desde: date, hasta: date,
                 cliente: httpx.Client | None = None, hilos: int = HILOS) -> list[Observacion]:
    """NDVI MODIS del lote, uno por compuesto de 16 días, en el contrato común."""
    validar_pedido(poligono, desde, hasta)
    h, v, f0, f1, c0, c1 = ventana(poligono)
    mosaico = f".h{h:02d}v{v:02d}."
    try:
        cliente = earthdata.cliente_autorizado(cliente)
        coleccion = earthdata.coleccion_vigente(cliente, PRODUCTO)
        if coleccion is None:
            raise ErrorMODIS(f"CMR no tiene {PRODUCTO}")
        from shapely.geometry import shape

        # un compuesto que empezó hasta 15 días antes de 'desde' puede tener fechas de adquisición dentro
        urls = sorted(url for nombre, url in earthdata.archivos(cliente, coleccion, desde - timedelta(days=15),
                                                                hasta, caja=shape(poligono).bounds)
                      if mosaico in nombre)
        with ThreadPoolExecutor(max_workers=hilos) as grupo:
            ventanas = list(grupo.map(lambda u: leer_ventana(cliente, u, f0, f1, c0, c1), urls))
    except earthdata.FaltanCredenciales:
        raise
    except (httpx.HTTPError, KeyError, ValueError, earthdata.ErrorNASA) as error:
        raise ErrorMODIS(f"No se pudo obtener el NDVI de MODIS: {error}") from error
    observaciones = [resumir(lote_id, poligono, datos, inicio_compuesto(url.rsplit("/", 1)[-1]))
                     for url, datos in zip(urls, ventanas)]
    return sorted((o for o in observaciones if desde <= o.fecha <= hasta), key=lambda o: o.fecha)


# ---------- conexión con el núcleo (spec 009) ----------

# tercer respaldo de HLS: entra si HLS, Sentinel-2 y VIIRS no traen datos (specs 005, 007, 011 y 014)
SATELITES = [Satelite("HLS:MODIS", lambda lote, desde, hasta: obtener_ndvi(lote["id"], lote["poligono"], desde, hasta),
                      respaldo_de="HLS", orden=3)]
