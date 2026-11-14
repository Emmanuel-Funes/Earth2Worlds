"""Conector suelo desnudo: en qué meses del año el lote queda sin cobertura verde, con 5 años de MODIS (spec 060).

El desafío pide mostrar cuándo los lotes quedan típicamente desnudos: es cuando el suelo se vuela (erosión eólica en
los suelos arenosos de San Luis), pierde agua por evaporación y no suma carbono. Es el hueco donde entra un cultivo de
servicio o un verdeo.

Se usa el NDVI de 250 m de MODIS Terra (MOD13Q1, compuestos de 16 días) de los últimos 4 años (48 meses): es el NDVI
de la NASA con historia larga que se lee en pocos minutos. Cada compuesto se pide por OPeNDAP, solo la ventana del lote.
El OPeNDAP de la NASA sirve MOD13Q1 desde mediados de 2022 (los compuestos anteriores dan 404), por eso 4 años y no más.
Un mes cuenta como "desnudo" en un año si la mediana del NDVI del lote ese mes es menor a 0,25, y con "cobertura baja"
si es menor a 0,30.

Satélite independiente (spec 009): repite a propósito la lectura de MODIS del conector de NDVI y no lo importa.
"""

import math
import re
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import httpx
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rotaterra.contrato import Observacion
from rotaterra.fuentes import earthdata
from rotaterra.fuentes.registro import Satelite
from rotaterra.geo import validar_poligono

PRODUCTO = "MOD13Q1"
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
CONFIABLES = (0, 1)
MIN_VALIDOS_PCT = 50.0  # un compuesto con menos de la mitad del lote visible no cuenta
RESOLUCION_M = 250
HILOS = 4
MESES_PERIODO = 48  # el OPeNDAP de MOD13Q1 empieza a mediados de 2022
UMBRAL_DESNUDO = 0.25  # NDVI bajo el que el lote está desnudo o con rastrojo ralo (supuesto a validar)
UMBRAL_BAJA = 0.30     # NDVI bajo el que la cobertura es baja: el suelo se ve entre las plantas (supuesto a validar)
MESES_DESNUDO_PCT = 50.0  # un mes es "típicamente desnudo" si lo estuvo en la mitad de los años o más
MIN_ANIOS_MES = 3
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre")

_R = 6371007.181
_MOSAICO = 1111950.5197665
_PIXEL = _MOSAICO / 4800
_X0, _Y0 = -20015109.354, 10007554.677


class ErrorSueloDesnudo(Exception):
    """La NASA no respondió o respondió algo ilegible."""


def celda(lat: float, lon: float) -> tuple[int, int, int, int]:
    """Mosaico (h, v) y píxel (fila, columna) de la grilla sinusoidal de MODIS."""
    x = _R * math.radians(lon) * math.cos(math.radians(lat))
    y = _R * math.radians(lat)
    h, v = math.floor((x - _X0) / _MOSAICO), math.floor((_Y0 - y) / _MOSAICO)
    columna = math.floor((x - _X0 - h * _MOSAICO) / _PIXEL)
    fila = math.floor((_Y0 - y - v * _MOSAICO) / _PIXEL)
    return h, v, fila, columna


def ventana(poligono: dict) -> tuple[int, int, int, int, int, int]:
    """Mosaico y ventana de píxeles que cubren el lote, con un píxel de margen."""
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
        c1 = c0 + 1
    return h, v, f0, f1, c0, c1


def periodo(hoy: date | None = None) -> tuple[date, date]:
    """Los 48 meses completos más recientes: por ejemplo, si hoy es 30/10/2026: del 1/10/2022 al 30/9/2026."""
    hoy = hoy or date.today()
    hasta = date(hoy.year, hoy.month, 1) - timedelta(days=1)
    meses = hoy.year * 12 + hoy.month - 1 - MESES_PERIODO
    return date(meses // 12, meses % 12 + 1, 1), hasta


def leer_ventana(cliente: httpx.Client, url: str, f0: int, f1: int, c0: int, c1: int) -> dict[str, np.ndarray]:
    expresion = ";".join(f"{ruta}[{f0}:1:{f1}][{c0}:1:{c1}]" for ruta in CAPAS.values())
    crudo = earthdata.leer_csv(cliente, url, expresion)
    datos = {}
    for nombre, ruta in CAPAS.items():
        filas = crudo.get(ruta.lstrip("/"))
        if filas is None:
            raise ErrorSueloDesnudo(f"OPeNDAP no devolvió '{nombre}'")
        datos[nombre] = np.array([[np.nan if v is None else v for v in fila] for fila in filas], dtype="float64")
    return datos


def inicio_compuesto(nombre_archivo: str) -> date:
    """MOD13Q1.A2026001.h12v12... → 2026-01-01."""
    hallado = re.search(r"\.A(\d{4})(\d{3})\.", nombre_archivo)
    return date(int(hallado[1]), 1, 1) + timedelta(days=int(hallado[2]) - 1)


def ndvi_del_lote(poligono: dict, datos: dict[str, np.ndarray], inicio: date) -> tuple[date, float] | None:
    """(fecha, mediana del NDVI del lote) de un compuesto, o None si se ve menos de la mitad del lote."""
    from shapely.geometry import Point, shape

    lote = shape(poligono)
    dentro = np.array([[lote.contains(Point(lon, lat)) for lat, lon in zip(fila_lat, fila_lon)]
                       for fila_lat, fila_lon in zip(datos["lat"], datos["lon"])])
    if not dentro.any():  # lote menor a un píxel de 6 ha: el píxel del centro
        centro = lote.centroid
        distancia = (datos["lat"] - centro.y) ** 2 + (datos["lon"] - centro.x) ** 2
        dentro = distancia == np.nanmin(distancia)
    validos = dentro & np.isin(datos["confiabilidad"], CONFIABLES) & (datos["ndvi"] != RELLENO_NDVI) \
        & np.isfinite(datos["ndvi"])
    if 100.0 * validos.sum() / dentro.sum() < MIN_VALIDOS_PCT:
        return None
    valor = float(np.median(datos["ndvi"][validos] * ESCALA))
    if not -1 <= valor <= 1:
        return None
    dia = int(np.median(datos["dia"][validos]))
    anio = inicio.year + (1 if dia < inicio.timetuple().tm_yday else 0)  # compuesto que cruza el año
    return date(anio, 1, 1) + timedelta(days=dia - 1), valor


# ---------- cálculos (sin red) ----------

def por_mes(serie: list[tuple[date, float]]) -> dict[int, dict[int, float]]:
    """Mes -> año -> mediana del NDVI de los compuestos de ese mes."""
    agrupado: dict[int, dict[int, list[float]]] = {}
    for fecha, valor in serie:
        agrupado.setdefault(fecha.month, {}).setdefault(fecha.year, []).append(valor)
    return {mes: {anio: statistics.median(v) for anio, v in anios.items()} for mes, anios in agrupado.items()}


def a_observaciones(lote_id: str, serie: list[tuple[date, float]], desde: date, hasta: date,
                    total_compuestos: int) -> list[Observacion]:
    meses = por_mes(serie)
    contexto = (f"MODIS Terra MOD13Q1 (NASA), NDVI de 250 m, {desde:%m/%Y} a {hasta:%m/%Y} · {len(serie)} compuestos de "
                f"16 días con el lote visible de {total_compuestos} · desnudo = NDVI < {UMBRAL_DESNUDO:g} (suelo o "
                f"rastrojo ralo; un pastizal muy seco también puede caer abajo), cobertura baja = NDVI < {UMBRAL_BAJA:g} "
                f"· umbrales a validar")
    base = dict(lote_id=lote_id, fecha=hasta, fuente="MODIS", resolucion_m=RESOLUCION_M)
    observaciones, desnudos, bajos = [], [], []
    for mes in range(1, 13):
        anios = meses.get(mes, {})
        variable = f"suelo_desnudo_mes_{mes:02d}_pct"
        if len(anios) < MIN_ANIOS_MES:
            observaciones.append(Observacion(**base, variable=variable, unidad="% de los años", valor=None,
                                             calidad="descartada",
                                             nota=f"{MESES[mes - 1].capitalize()}: solo {len(anios)} años con el lote "
                                                  f"visible (< {MIN_ANIOS_MES}) · {contexto}"))
            continue
        pct = 100.0 * sum(v < UMBRAL_DESNUDO for v in anios.values()) / len(anios)
        pct_baja = 100.0 * sum(v < UMBRAL_BAJA for v in anios.values()) / len(anios)
        if pct >= MESES_DESNUDO_PCT:
            desnudos.append(MESES[mes - 1])
        if pct_baja >= MESES_DESNUDO_PCT:
            bajos.append(MESES[mes - 1])
        detalle = ", ".join(f"{a} {v:.2f}" for a, v in sorted(anios.items()))
        observaciones.append(Observacion(
            **base, variable=variable, unidad="% de los años", valor=round(pct), calidad="buena",
            nota=f"{MESES[mes - 1].capitalize()}: desnudo en {pct:.0f} % de los años y con cobertura baja en "
                 f"{pct_baja:.0f} % ({len(anios)} años); NDVI mediano {statistics.median(anios.values()):.2f} "
                 f"(por año: {detalle}) · {contexto}"))
    con_dato = sum(o.valor is not None for o in observaciones)
    resumen = []
    for variable, lista, que in (("meses_suelo_desnudo", desnudos, "suele quedar desnudo"),
                                 ("meses_cobertura_baja", bajos, "suele quedar con cobertura baja")):
        if not con_dato:
            resumen.append(Observacion(**base, variable=variable, unidad="meses", valor=None, calidad="descartada",
                                       nota=f"Ningún mes con años suficientes · {contexto}"))
            continue
        resumen.append(Observacion(
            **base, variable=variable, unidad="meses", valor=len(lista), calidad="buena" if con_dato == 12 else "dudosa",
            nota=f"Meses en que el lote {que} (la mitad de los años o más): {', '.join(lista) or 'ninguno'}"
                 + ("" if con_dato == 12 else f" · solo {con_dato} de 12 meses con dato") + f" · {contexto}"))
    return resumen + observaciones


# ---------- principal ----------

_MEMORIA: dict[tuple[str, str], list[Observacion]] = {}
_CANDADO = threading.Lock()


def obtener(lote_id: str, poligono: dict, hoy: date | None = None, cliente: httpx.Client | None = None,
            hilos: int = HILOS) -> list[Observacion]:
    """Meses de suelo desnudo del lote con los últimos 48 meses de MODIS. Queda en memoria hasta el mes que viene:
    los meses completos no cambian."""
    from shapely.geometry import shape

    validar_poligono(poligono)
    desde, hasta = periodo(hoy)
    clave = (",".join(f"{v:.5f}" for v in shape(poligono).bounds), hasta.isoformat())
    with _CANDADO:
        guardado = _MEMORIA.get(clave)
    if guardado is not None:
        return [o.model_copy(update={"lote_id": lote_id}) for o in guardado]
    h, v, f0, f1, c0, c1 = ventana(poligono)
    mosaico = f".h{h:02d}v{v:02d}."
    try:
        cliente = earthdata.cliente_autorizado(cliente)
        coleccion = earthdata.coleccion_vigente(cliente, PRODUCTO)
        if coleccion is None:
            raise ErrorSueloDesnudo(f"CMR no tiene {PRODUCTO}")
        urls = sorted(url for nombre, url in earthdata.archivos(cliente, coleccion, desde - timedelta(days=15), hasta,
                                                                caja=shape(poligono).bounds) if mosaico in nombre)
    except earthdata.FaltanCredenciales:
        raise
    except (httpx.HTTPError, KeyError, ValueError, earthdata.ErrorNASA) as error:
        raise ErrorSueloDesnudo(f"No se pudo buscar MODIS en CMR: {error}") from error

    def uno(url):
        try:
            return ndvi_del_lote(poligono, leer_ventana(cliente, url, f0, f1, c0, c1),
                                 inicio_compuesto(url.rsplit("/", 1)[-1]))
        except (httpx.HTTPError, ErrorSueloDesnudo, earthdata.ErrorNASA):  # un compuesto que no llega no cuenta
            return None

    with ThreadPoolExecutor(max_workers=hilos) as grupo:
        leidos = list(grupo.map(uno, urls))
    serie = sorted(x for x in leidos if x and desde <= x[0] <= hasta)
    if urls and not serie and all(x is None for x in leidos):
        raise ErrorSueloDesnudo("No se pudo leer ningún compuesto de MODIS")
    observaciones = a_observaciones(lote_id, serie, desde, hasta, len(urls))
    with _CANDADO:
        _MEMORIA[clave] = observaciones
    return observaciones


# ---------- conexión con el núcleo (spec 009) ----------
# Fuente propia (no es respaldo de nadie). No usa el período del pedido: siempre los últimos 48 meses completos.

SATELITES = [Satelite("SUELO_DESNUDO", lambda lote, desde, hasta: obtener(lote["id"], lote["poligono"]))]

router = APIRouter(tags=["Suelo desnudo (pruebas internas)"])


class PedidoSueloDesnudo(BaseModel):
    lote_id: str
    poligono: dict


@router.post("/suelo-desnudo", response_model=list[Observacion])
def suelo_desnudo(pedido: PedidoSueloDesnudo) -> list[Observacion]:
    """En qué meses el lote suele quedar sin cobertura verde (4 años de NDVI de MODIS). Unos minutos la primera vez."""
    try:
        validar_poligono(pedido.poligono)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener(pedido.lote_id, pedido.poligono)
    except earthdata.FaltanCredenciales as error:
        raise HTTPException(status_code=503, detail=str(error))
    except ErrorSueloDesnudo as error:
        raise HTTPException(status_code=502, detail=str(error))
