"""Conector IMERG Early: lluvia del día, respaldo "del día" de IMERG (spec 043).

IMERG Late diario sale con 1 día de atraso. IMERG Early es la misma lluvia de la NASA (GPM) calculada más rápido y con
menos correcciones: el archivo de cada media hora sale unas 4 a 9 horas después. Solo completa los últimos días que
IMERG todavía no publicó: el núcleo lo pide con `al_dia=True` (spec 043, parte A).

Igual que IMERG, el día es el día UTC (de las 21 h del día anterior a las 21 h en Argentina).

Satélite independiente (spec 009): hace su propio pedido a la NASA y no importa a ningún otro satélite.
"""

import math
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import httpx
from fastapi import APIRouter, HTTPException

from rotaterra.contrato import Observacion
from rotaterra.fuentes import earthdata
from rotaterra.fuentes.registro import Satelite

DIARIO = "GPM_3IMERGDE"       # IMERG Early diario (mm/día), sale ~1 día después
MEDIA_HORA = "GPM_3IMERGHHE"  # IMERG Early de media hora (mm/h), sale ~4 a 9 h después
RESOLUCION_M = 10000
VALOR_RELLENO = -9999
RANGO = (0.0, 500.0)
MAX_DIAS = 366
DIAS_MEDIA_HORA = 3  # días como máximo que se arman con archivos de media hora (48 por día)
HILOS = 16
NOTA = "IMERG Early de la NASA (GPM), sin corregir con pluviómetros · celda de 0,1° · día UTC"
_HORA = re.compile(r"-S(\d{2})(\d{2})\d{2}-")


class ErrorIMERGEarly(Exception):
    """La NASA no respondió o respondió algo ilegible."""


def validar_pedido(lat: float, lon: float, desde: date, hasta: date) -> None:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Latitud o longitud fuera de rango")
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise ValueError(f"El rango supera {MAX_DIAS} días")


def celda(lat: float, lon: float) -> tuple[int, int]:
    """Índices (lon, lat) de la celda de 0,1° que contiene el punto. Grilla: 3600 × 1800."""
    i_lon = min(int(math.floor((lon + 180) / 0.1)), 3598)  # se piden 2 celdas, ver earthdata.leer_csv
    i_lat = min(int(math.floor((lat + 90) / 0.1)), 1798)
    return i_lon, i_lat


def leer(cliente: httpx.Client, url: str, variable: str, i_lon: int, i_lat: int) -> float | None:
    datos = earthdata.leer_csv(cliente, url, f"{variable}[0][{i_lon}][{i_lat}:1:{i_lat + 1}]")
    nombre = variable.rsplit("/", 1)[-1]
    try:
        valor = next(v for k, v in datos.items() if k.endswith(nombre))[0][0]
    except (StopIteration, IndexError):
        raise ErrorIMERGEarly(f"Respuesta OPeNDAP ilegible para {url}")
    return None if valor is None or valor <= VALOR_RELLENO else valor


def media_hora_por_dia(cliente: httpx.Client, coleccion: str, dias: list[date]) -> dict[date, list[tuple[str, str]]]:
    """(hora 'HH:MM', URL) de cada archivo de media hora, agrupados por día UTC."""
    por_dia: dict[date, list[tuple[str, str]]] = {}
    for nombre, url in earthdata.archivos(cliente, coleccion, min(dias), max(dias)):
        fecha, hora = re.search(r"\.(\d{8})-", nombre), _HORA.search(nombre)
        if not fecha or not hora:
            continue
        dia = date(int(fecha[1][:4]), int(fecha[1][4:6]), int(fecha[1][6:8]))
        if dia in dias:
            por_dia.setdefault(dia, []).append((f"{hora[1]}:{hora[2]}", url))
    return por_dia


def a_observacion(lote_id: str, dia: date, valor: float | None, motivo: str, medias_horas: int = 48,
                  hasta_hora: str = "") -> Observacion:
    base = dict(lote_id=lote_id, fecha=dia, variable="lluvia_mm", unidad="mm/día", fuente="IMERG_EARLY",
                resolucion_m=RESOLUCION_M)
    if valor is None:
        return Observacion(**base, valor=None, calidad="descartada", nota=f"{NOTA} · {motivo}")
    valor = round(valor, 2)
    if not RANGO[0] <= valor <= RANGO[1]:
        return Observacion(**base, valor=valor, calidad="dudosa", nota=f"{NOTA} · fuera del rango físico")
    if medias_horas < 48:
        return Observacion(**base, valor=valor, calidad="dudosa",
                           nota=f"{NOTA} · día en curso: lluvia hasta las {hasta_hora} UTC ({medias_horas} de 48 "
                                f"medias horas)")
    return Observacion(**base, valor=valor, calidad="buena", nota=f"{NOTA} · {motivo}")


def obtener_lluvia(lote_id: str, lat: float, lon: float, desde: date, hasta: date,
                   cliente: httpx.Client | None = None, hilos: int = HILOS) -> list[Observacion]:
    """Lluvia de cada día: del archivo diario de IMERG Early si ya salió; si no, sumando las medias horas publicadas."""
    validar_pedido(lat, lon, desde, hasta)
    i_lon, i_lat = celda(lat, lon)
    dias = [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]
    try:
        cliente = earthdata.cliente_autorizado(cliente)
        diarios: dict[date, str] = {}
        coleccion = earthdata.coleccion_vigente(cliente, DIARIO)
        if coleccion:
            diarios = {d: urls[0] for d, urls in earthdata.archivos_por_dia(cliente, coleccion, desde, hasta).items()}
        faltan = [d for d in dias if d not in diarios][-DIAS_MEDIA_HORA:]
        medias: dict[date, list[tuple[str, str]]] = {}
        coleccion = earthdata.coleccion_vigente(cliente, MEDIA_HORA) if faltan else None
        if coleccion:
            medias = media_hora_por_dia(cliente, coleccion, faltan)
        tareas = [(d, "diario", "", u) for d, u in diarios.items()] + \
                 [(d, "media_hora", h, u) for d, archivos in medias.items() for h, u in archivos]

        def leer_tarea(tarea):
            _, tipo, _, url = tarea
            return leer(cliente, url, "/precipitation" if tipo == "diario" else "/Grid/precipitation", i_lon, i_lat)

        with ThreadPoolExecutor(max_workers=hilos) as grupo:
            leidos = list(grupo.map(leer_tarea, tareas))
    except earthdata.FaltanCredenciales:
        raise
    except (httpx.HTTPError, KeyError, ValueError, earthdata.ErrorNASA) as error:
        raise ErrorIMERGEarly(f"No se pudo obtener la lluvia de IMERG Early: {error}") from error

    diario = {t[0]: v for t, v in zip(tareas, leidos) if t[1] == "diario"}
    por_media: dict[date, list[tuple[str, float | None]]] = {}
    for t, v in zip(tareas, leidos):
        if t[1] == "media_hora":
            por_media.setdefault(t[0], []).append((t[2], v))
    observaciones = []
    for dia in dias:
        if dia in diario:
            motivo = "archivo diario" if diario[dia] is not None else "sin dato (relleno) en el archivo diario"
            observaciones.append(a_observacion(lote_id, dia, diario[dia], motivo))
        elif dia in por_media:
            validos = [(h, v) for h, v in sorted(por_media[dia]) if v is not None]
            if not validos:
                observaciones.append(a_observacion(lote_id, dia, None, "medias horas sin dato (relleno)"))
                continue
            hh, mm = map(int, validos[-1][0].split(":"))
            fin = f"{(hh * 60 + mm + 30) // 60:02d}:{(mm + 30) % 60:02d}"
            observaciones.append(a_observacion(lote_id, dia, sum(v * 0.5 for _, v in validos), "suma de medias horas",
                                               len(validos), fin))
        else:
            observaciones.append(a_observacion(lote_id, dia, None, "IMERG Early todavía no publicó este día"))
    return observaciones


SATELITES = [Satelite("IMERG:IMERG_EARLY",
                      lambda lote, desde, hasta: obtener_lluvia(lote["id"], lote["lat"], lote["lon"], desde, hasta),
                      respaldo_de="IMERG", al_dia=True)]


# ---------- endpoint de prueba (spec 009): sin respaldos ----------

router = APIRouter(tags=["IMERG Early (pruebas internas)"])


@router.get("/lluvia/imerg-early", response_model=list[Observacion])
def lluvia_del_dia(lote_id: str, lat: float, lon: float, desde: date, hasta: date) -> list[Observacion]:
    try:
        validar_pedido(lat, lon, desde, hasta)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener_lluvia(lote_id, lat, lon, desde, hasta)
    except earthdata.FaltanCredenciales as error:
        raise HTTPException(status_code=503, detail=str(error))
    except ErrorIMERGEarly as error:
        raise HTTPException(status_code=502, detail=str(error))
