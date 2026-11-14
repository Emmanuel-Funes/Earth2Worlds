"""Conector GPM IMERG: lluvia diaria del punto del lote (spec 006)."""

import math
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import httpx

from rotaterra.contrato import Observacion
from rotaterra.fuentes import earthdata
from rotaterra.fuentes.registro import Satelite
from fastapi import APIRouter, HTTPException

# del más confiable al más rápido: Final está corregido con pluviómetros pero sale ~3,5 meses después
PRODUCTOS = {
    "GPM_3IMERGDF": "IMERG Final, corregido con pluviómetros",
    "GPM_3IMERGDL": "IMERG Late, sin corregir con pluviómetros",
}
RESOLUCION_M = 10000
VALOR_RELLENO = -9999
RANGO = (0.0, 500.0)
MAX_DIAS = 366
HILOS = 8


class ErrorIMERG(Exception):
    """La NASA no respondió o respondió algo ilegible."""


def validar_pedido(lat: float, lon: float, desde: date, hasta: date) -> None:
    if not -90 <= lat <= 90:
        raise ValueError(f"Latitud fuera de rango: {lat}")
    if not -180 <= lon <= 180:
        raise ValueError(f"Longitud fuera de rango: {lon}")
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise ValueError(f"El rango supera {MAX_DIAS} días")


def celda(lat: float, lon: float) -> tuple[int, int]:
    """Índices (lon, lat) de la celda de 0,1° que contiene el punto. Grilla: 3600 × 1800."""
    i_lon = min(int(math.floor((lon + 180) / 0.1)), 3598)  # 3598: se piden 2 celdas, ver earthdata.leer_csv
    i_lat = min(int(math.floor((lat + 90) / 0.1)), 1798)
    return i_lon, i_lat


def leer_dia(cliente: httpx.Client, url: str, i_lon: int, i_lat: int) -> float | None:
    datos = earthdata.leer_csv(cliente, url, f"/precipitation[0][{i_lon}][{i_lat}:1:{i_lat + 1}]")
    try:
        valor = datos["precipitation"][0][0]
    except (KeyError, IndexError):
        raise ErrorIMERG(f"Respuesta OPeNDAP ilegible para {url}")
    return None if valor is None or valor <= VALOR_RELLENO else valor


def a_observacion(lote_id: str, dia: date, valor: float | None, producto: str | None) -> Observacion:
    base = dict(lote_id=lote_id, fecha=dia, variable="lluvia_mm", unidad="mm/día",
                fuente="IMERG", resolucion_m=RESOLUCION_M)
    if producto is None:
        return Observacion(**base, valor=None, calidad="descartada", nota="IMERG todavía no publicó este día")
    detalle = f"{PRODUCTOS[producto]} · celda de 0,1°"
    if valor is None:
        return Observacion(**base, valor=None, calidad="descartada", nota=f"Sin dato (relleno) · {detalle}")
    valor = round(valor, 2)
    minimo, maximo = RANGO
    if not minimo <= valor <= maximo:
        return Observacion(**base, valor=valor, calidad="dudosa",
                           nota=f"Fuera del rango físico ({minimo:.0f} a {maximo:.0f} mm/día) · {detalle}")
    return Observacion(**base, valor=valor, calidad="buena", nota=detalle)


def obtener_lluvia(lote_id: str, lat: float, lon: float, desde: date, hasta: date,
                   cliente: httpx.Client | None = None, hilos: int = HILOS) -> list[Observacion]:
    """Lluvia diaria de IMERG para el punto, un valor por día pedido, en el contrato común."""
    validar_pedido(lat, lon, desde, hasta)
    i_lon, i_lat = celda(lat, lon)
    try:
        cliente = earthdata.cliente_autorizado(cliente)
        elegido: dict[date, tuple[str, str]] = {}  # día -> (producto, url)
        for producto in PRODUCTOS:
            coleccion = earthdata.coleccion_vigente(cliente, producto)
            if coleccion is None:
                continue
            for dia, urls in earthdata.archivos_por_dia(cliente, coleccion, desde, hasta).items():
                elegido.setdefault(dia, (producto, urls[0]))
        with ThreadPoolExecutor(max_workers=hilos) as grupo:
            leidos = dict(zip(elegido, grupo.map(lambda d: leer_dia(cliente, elegido[d][1], i_lon, i_lat), elegido)))
    except earthdata.FaltanCredenciales:
        raise
    except (httpx.HTTPError, KeyError, ValueError, earthdata.ErrorNASA) as error:
        raise ErrorIMERG(f"No se pudo obtener la lluvia de IMERG: {error}") from error

    dias = [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]
    return [a_observacion(lote_id, dia, leidos.get(dia), elegido.get(dia, (None,))[0]) for dia in dias]


# ---------- conexión con el núcleo (spec 009) ----------

SATELITES = [Satelite("IMERG", lambda lote, desde, hasta: obtener_lluvia(lote["id"], lote["lat"], lote["lon"], desde, hasta))]

router = APIRouter(tags=["IMERG (pruebas internas)"])


@router.get("/lluvia", response_model=list[Observacion])
def lluvia(lote_id: str, lat: float, lon: float, desde: date, hasta: date) -> list[Observacion]:
    try:
        validar_pedido(lat, lon, desde, hasta)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener_lluvia(lote_id, lat, lon, desde, hasta)
    except earthdata.FaltanCredenciales as error:
        raise HTTPException(status_code=503, detail=str(error))
    except ErrorIMERG as error:
        raise HTTPException(status_code=502, detail=str(error))
