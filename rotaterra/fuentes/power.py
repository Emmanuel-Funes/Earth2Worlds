"""Conector NASA POWER: clima diario por punto (spec 001)."""

from datetime import date

import httpx

from rotaterra.contrato import Observacion
from rotaterra.fuentes.registro import Satelite
from fastapi import APIRouter, HTTPException

URL_POWER = "https://power.larc.nasa.gov/api/temporal/daily/point"
RESOLUCION_M = 55000  # grilla de ~0,5°: dato regional, no del lote
VALOR_RELLENO = -999
MAX_DIAS = 366

# parámetro POWER -> (variable Rotaterra, unidad, rango físico válido)
VARIABLES = {
    "T2M_MAX": ("temp_max", "°C", (-40.0, 60.0)),
    "T2M_MIN": ("temp_min", "°C", (-40.0, 60.0)),
    "PRECTOTCORR": ("lluvia_mm", "mm/día", (0.0, 500.0)),
    "ALLSKY_SFC_SW_DWN": ("radiacion", "MJ/m²/día", (0.0, 50.0)),
}


class ErrorPower(Exception):
    """POWER no respondió o respondió algo que no se puede leer."""


def validar_pedido(lat: float, lon: float, desde: date, hasta: date) -> None:
    if not -90 <= lat <= 90:
        raise ValueError(f"Latitud fuera de rango: {lat}")
    if not -180 <= lon <= 180:
        raise ValueError(f"Longitud fuera de rango: {lon}")
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise ValueError(f"El rango supera {MAX_DIAS} días")


def _a_observacion(lote_id: str, parametro: str, dia: str, valor: float) -> Observacion:
    variable, unidad, (minimo, maximo) = VARIABLES[parametro]
    fecha = date(int(dia[:4]), int(dia[4:6]), int(dia[6:8]))
    base = dict(lote_id=lote_id, fecha=fecha, variable=variable, unidad=unidad,
                fuente="POWER", resolucion_m=RESOLUCION_M)

    if valor is None or valor == VALOR_RELLENO:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota="POWER no tiene dato para esta fecha (valor de relleno -999)")
    if not minimo <= valor <= maximo:
        return Observacion(**base, valor=valor, calidad="dudosa",
                           nota=f"Valor fuera del rango físico esperado ({minimo} a {maximo} {unidad})")
    return Observacion(**base, valor=valor, calidad="buena")


def obtener_clima(lote_id: str, lat: float, lon: float, desde: date, hasta: date,
                  cliente: httpx.Client | None = None) -> list[Observacion]:
    """Pide a POWER el clima diario del punto y lo devuelve en el contrato común."""
    validar_pedido(lat, lon, desde, hasta)
    params = {
        "parameters": ",".join(VARIABLES),
        "community": "AG",
        "latitude": lat,
        "longitude": lon,
        "start": desde.strftime("%Y%m%d"),
        "end": hasta.strftime("%Y%m%d"),
        "format": "JSON",
    }
    cliente = cliente or httpx.Client(timeout=60)
    try:
        respuesta = cliente.get(URL_POWER, params=params)
        respuesta.raise_for_status()
        series = respuesta.json()["properties"]["parameter"]
    except (httpx.HTTPError, KeyError, ValueError) as error:
        raise ErrorPower(f"No se pudo obtener el clima de NASA POWER: {error}") from error

    observaciones = []
    for parametro in VARIABLES:
        for dia, valor in sorted(series.get(parametro, {}).items()):
            observaciones.append(_a_observacion(lote_id, parametro, dia, valor))
    return observaciones


# ---------- conexión con el núcleo (spec 009) ----------

SATELITES = [Satelite("POWER", lambda lote, desde, hasta: obtener_clima(lote["id"], lote["lat"], lote["lon"], desde, hasta))]

router = APIRouter(tags=["POWER (pruebas internas)"])


@router.get("/clima", response_model=list[Observacion])
def clima(lote_id: str, lat: float, lon: float, desde: date, hasta: date) -> list[Observacion]:
    try:
        validar_pedido(lat, lon, desde, hasta)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener_clima(lote_id, lat, lon, desde, hasta)
    except ErrorPower as error:
        raise HTTPException(status_code=502, detail=str(error))
