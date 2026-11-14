"""Conector SISINTA: pH medido en los perfiles de suelo del INTA cerca del lote (spec 048).

SISINTA es la base nacional de perfiles de suelo del INTA. GeoINTA la publica como capa de puntos (id 702,
dominio público) y se lee por WFS del nodo 05 sin clave. Cada feature es un HORIZONTE de un perfil, con su
profundidad y su pH en agua. Casi todos los campos llegan como texto y el faltante es el texto "NA".

Para cada perfil se calcula el pH en agua de 0-30 y de 30-100 cm, pesado por el espesor de cada horizonte, y se
entrega la mediana de los perfiles a 10 km del lote (o a 25 km si no hay ninguno). Es una referencia regional:
mediciones puntuales, casi todas de 1975-1988, de lotes vecinos. Nunca reemplaza al análisis del productor.
No importa a ningún otro satélite (spec 009).
"""

import math
import statistics
import threading
import time
from dataclasses import dataclass
from datetime import date

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rotaterra.contrato import Observacion
from rotaterra.fuentes.registro import Satelite
from rotaterra.geo import validar_poligono

URL_WFS = "https://geo-nodo05.inta.gob.ar/geoserver/wfs"
CAPA = "geonode:rehecho"
ESPERA_S = 60
RADIOS_KM = (10, 25)              # primero 10 km; si no hay perfiles, 25 km
KM_POR_GRADO_LAT = 111.32
TRAMOS = [(0, 30, "suelo_ph_perfiles_0_30cm", "0-30 cm"), (30, 100, "suelo_ph_perfiles_30_100cm", "30-100 cm")]
PH_MIN, PH_MAX = 3.0, 11.0
FALTANTES = {"", "NA", "NAN", "NULL"}
REFERENCIA = "solo de referencia: la última palabra la tiene el análisis de suelo del productor"
SUPUESTO = "pH en agua (relación 1:2,5 supuesta, la capa no la dice)"
FECHA_SIN_PERFILES = date(2025, 4, 3)  # alta de la capa en el catálogo de GeoINTA
DURACION_MEMORIA = 30 * 24 * 3600
MAX_LOTES_EN_MEMORIA = 500


class ErrorSISINTA(Exception):
    """El WFS del INTA no respondió o respondió algo ilegible."""


@dataclass
class Perfil:
    id: int
    lat: float
    lon: float
    fecha: date | None
    serie: str
    horizontes: list[tuple[float, float, float]]  # (superior, inferior, pH en agua), en cm


# ---------- lectura de la capa ----------

def numero(texto) -> float | None:
    """Los números llegan como texto ("7.7") y el faltante como "NA" o null."""
    if texto is None:
        return None
    if isinstance(texto, (int, float)):
        return float(texto)
    texto = str(texto).strip()
    if texto.upper() in FALTANTES:
        return None
    try:
        return float(texto.replace(",", "."))
    except ValueError:
        return None


def _fecha(texto) -> date | None:
    try:
        return date.fromisoformat(str(texto)[:10])
    except (TypeError, ValueError):
        return None


def perfiles_de(geojson: dict) -> list[Perfil]:
    """Agrupa los horizontes por perfil. Descarta perfiles no públicos y horizontes sin profundidad o con pH fuera de
    rango; un perfil sin ningún horizonte útil no entra."""
    perfiles: dict[int, Perfil] = {}
    for feature in geojson.get("features", []):
        p = feature.get("properties") or {}
        if p.get("s_publico") != 1 or p.get("id perfil") is None:
            continue
        lon, lat = (feature.get("geometry") or {}).get("coordinates", (None, None))[:2]
        if lon is None or lat is None:
            continue
        perfil = perfiles.setdefault(int(p["id perfil"]), Perfil(
            id=int(p["id perfil"]), lat=float(lat), lon=float(lon), fecha=_fecha(p.get("fecha")),
            serie=str(p.get("nombre de serie") or "sin serie").strip(), horizontes=[]))
        sup, inf, ph = numero(p.get("profundiad sup.")), numero(p.get("profundiad inf.")), numero(p.get("ph h2o"))
        if sup is None or inf is None or inf <= sup or ph is None or not PH_MIN <= ph <= PH_MAX:
            continue
        perfil.horizontes.append((sup, inf, ph))
    return [perfil for perfil in perfiles.values() if perfil.horizontes]


def ph_del_tramo(perfil: Perfil, desde: float, hasta: float) -> float | None:
    """pH promedio del tramo, pesado por el espesor de cada horizonte. Solo si hay dato en al menos la mitad."""
    cubierto = suma = 0.0
    for sup, inf, ph in perfil.horizontes:
        espesor = min(inf, hasta) - max(sup, desde)
        if espesor > 0:
            cubierto += espesor
            suma += ph * espesor
    if cubierto < (hasta - desde) / 2:
        return None
    return suma / cubierto


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia de gran círculo (haversine), radio terrestre medio de 6371 km."""
    f1, f2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((f2 - f1) / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(a))


def centro(poligono: dict) -> tuple[float, float]:
    """(lat, lon) del centroide del lote."""
    from shapely.geometry import shape

    c = shape(poligono).centroid
    return c.y, c.x


def recuadro(lat: float, lon: float, km: float) -> str:
    """bbox del WFS 1.0.0: lon_min,lat_min,lon_max,lat_max (con 1.1.0 el INTA espera lat/lon y devuelve 0 sin error)."""
    dlat = km / KM_POR_GRADO_LAT
    dlon = km / (KM_POR_GRADO_LAT * math.cos(math.radians(lat)))
    return f"{lon - dlon:.6f},{lat - dlat:.6f},{lon + dlon:.6f},{lat + dlat:.6f}"


def pedir_horizontes(cliente: httpx.Client, lat: float, lon: float) -> dict:
    params = {"service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": CAPA,
              "outputFormat": "application/json", "srsName": "EPSG:4326", "bbox": recuadro(lat, lon, max(RADIOS_KM))}
    try:
        respuesta = cliente.get(URL_WFS, params=params, timeout=ESPERA_S)
        respuesta.raise_for_status()
        datos = respuesta.json()
    except (httpx.HTTPError, ValueError) as error:
        raise ErrorSISINTA(f"El WFS de SISINTA (INTA) no respondió bien: {type(error).__name__}: {error}") from error
    if not isinstance(datos, dict) or "features" not in datos:
        raise ErrorSISINTA("El WFS de SISINTA (INTA) respondió algo que no es GeoJSON")
    return datos


# ---------- de los perfiles a las observaciones ----------

def _f(valor: float) -> str:
    return f"{valor:.2f}"


def observacion_del_tramo(lote_id: str, lat: float, lon: float, perfiles: list[Perfil],
                          desde: float, hasta: float, variable: str, rotulo: str) -> Observacion:
    cercanos = sorted(((distancia_km(lat, lon, p.lat, p.lon), p) for p in perfiles), key=lambda x: x[0])
    for radio in RADIOS_KM:
        con_dato = [(d, p, ph) for d, p in cercanos if d <= radio and (ph := ph_del_tramo(p, desde, hasta)) is not None]
        if con_dato:
            break
    else:
        return Observacion(lote_id=lote_id, fecha=FECHA_SIN_PERFILES, variable=variable, valor=None, unidad="pH",
                           fuente="SISINTA", resolucion_m=max(RADIOS_KM) * 1000, calidad="descartada",
                           nota=f"No hay perfiles medidos del INTA con pH en agua de {rotulo} a {max(RADIOS_KM)} km "
                                f"o menos del lote · SISINTA (GeoINTA, capa 702)")
    valores = [ph for _, _, ph in con_dato]
    fechas = [p.fecha for _, p, _ in con_dato if p.fecha]
    primero, ultimo = (min(fechas).year, max(fechas).year) if fechas else (None, None)
    anios = "año sin dato" if primero is None else f"año {primero}" if primero == ultimo else f"años {primero}-{ultimo}"
    d, mas_cercano, ph_cercano = con_dato[0]
    cuantos = (f"Mediana de {len(valores)} perfiles medidos del INTA a {radio} km o menos, {rotulo} "
               f"(de {_f(min(valores))} a {_f(max(valores))})" if len(valores) > 1 else
               f"Un solo perfil medido del INTA a {radio} km o menos, {rotulo}")
    nota = (f"{cuantos}, {anios} · "
            f"más cercano: perfil {mas_cercano.id}, serie {mas_cercano.serie}, a {d:.1f} km, {_f(ph_cercano)} · "
            f"{SUPUESTO} · SISINTA (GeoINTA, capa 702) · {REFERENCIA}")
    return Observacion(lote_id=lote_id, fecha=max(fechas) if fechas else FECHA_SIN_PERFILES, variable=variable,
                       valor=round(statistics.median(valores), 2), unidad="pH", fuente="SISINTA",
                       resolucion_m=radio * 1000, calidad="dudosa", nota=nota)


# ---------- memoria: los perfiles no cambian (como el suelo de GeoINTA, spec 044) ----------

_memoria: dict[tuple[float, float], tuple[float, list[Observacion]]] = {}
_candado = threading.Lock()


def _llave(lat: float, lon: float) -> tuple[float, float]:
    return round(lat, 4), round(lon, 4)


def _de_la_memoria(llave, lote_id: str, ahora: float) -> list[Observacion] | None:
    with _candado:
        guardado = _memoria.get(llave)
        if guardado is None or ahora - guardado[0] > DURACION_MEMORIA:
            _memoria.pop(llave, None)
            return None
        return [o.model_copy(update={"lote_id": lote_id}) for o in guardado[1]]


def _a_la_memoria(llave, observaciones: list[Observacion], ahora: float) -> None:
    with _candado:
        if len(_memoria) >= MAX_LOTES_EN_MEMORIA:
            _memoria.pop(min(_memoria, key=lambda k: _memoria[k][0]))
        _memoria[llave] = (ahora, observaciones)


def obtener_ph_perfiles(lote_id: str, poligono: dict, cliente: httpx.Client | None = None) -> list[Observacion]:
    """pH en agua de 0-30 y 30-100 cm de los perfiles medidos del INTA cerca del lote."""
    lat, lon = centro(poligono)
    llave, ahora = _llave(lat, lon), time.time()
    if cliente is None and (guardado := _de_la_memoria(llave, lote_id, ahora)) is not None:
        return guardado
    if cliente is None:
        with httpx.Client(headers={"User-Agent": "Rotaterra (NASA Space Apps, Earth2Worlds)"}) as propio:
            datos = pedir_horizontes(propio, lat, lon)
    else:
        datos = pedir_horizontes(cliente, lat, lon)
    perfiles = perfiles_de(datos)
    observaciones = [observacion_del_tramo(lote_id, lat, lon, perfiles, desde, hasta, variable, rotulo)
                     for desde, hasta, variable, rotulo in TRAMOS]
    if cliente is None:
        _a_la_memoria(llave, observaciones, ahora)
    return observaciones


# ---------- conexión con el núcleo (spec 009) ----------

SATELITES = [Satelite("SISINTA", lambda lote, desde, hasta: obtener_ph_perfiles(lote["id"], lote["poligono"]),
                      estatico=True)]

router = APIRouter(tags=["SISINTA (pruebas internas)"])


class PedidoPerfiles(BaseModel):
    lote_id: str = "lote"
    poligono: dict


@router.post("/suelo/ph-perfiles", response_model=list[Observacion])
def ph_perfiles(pedido: PedidoPerfiles) -> list[Observacion]:
    """pH medido en los perfiles del INTA cerca del lote. Solo referencia: nunca reemplaza al análisis del productor."""
    try:
        validar_poligono(pedido.poligono)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener_ph_perfiles(pedido.lote_id, pedido.poligono)
    except ErrorSISINTA as error:
        raise HTTPException(status_code=502, detail=str(error))
