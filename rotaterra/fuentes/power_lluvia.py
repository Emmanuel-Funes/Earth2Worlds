"""Respaldo de la lluvia de IMERG con NASA POWER: lluvia diaria del punto del lote (spec 013).

Satélite independiente (spec 009): hace su propio pedido a POWER y no usa el conector `power.py`.
"""

from datetime import date, timedelta

import httpx

from rotaterra.contrato import Observacion
from rotaterra.fuentes.registro import Satelite

URL_POWER = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMETRO = "PRECTOTCORR"     # lluvia total corregida, mm/día
RESOLUCION_M = 55000          # celda de 0,5° × 0,625°: dato regional, no del lote
VALOR_RELLENO = -999
RANGO = (0.0, 500.0)          # el mismo rango físico que IMERG (spec 006)
MAX_DIAS = 366
NOTA = "Respaldo de IMERG · NASA POWER (MERRA-2/IMERG corregido) · celda de 0,5°"


class ErrorPowerLluvia(Exception):
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


def a_observacion(lote_id: str, dia: date, valor: float | None, devuelto: bool) -> Observacion:
    base = dict(lote_id=lote_id, fecha=dia, variable="lluvia_mm", unidad="mm/día",
                fuente="POWER", resolucion_m=RESOLUCION_M)
    if not devuelto:
        return Observacion(**base, valor=None, calidad="descartada", nota=f"POWER no devolvió este día · {NOTA}")
    if valor is None or valor <= VALOR_RELLENO:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"POWER todavía no tiene dato (relleno {VALOR_RELLENO}) · {NOTA}")
    valor = round(float(valor), 2)
    minimo, maximo = RANGO
    if not minimo <= valor <= maximo:
        return Observacion(**base, valor=valor, calidad="dudosa",
                           nota=f"Fuera del rango físico ({minimo:.0f} a {maximo:.0f} mm/día) · {NOTA}")
    return Observacion(**base, valor=valor, calidad="buena", nota=NOTA)


def obtener_lluvia(lote_id: str, lat: float, lon: float, desde: date, hasta: date,
                   cliente: httpx.Client | None = None) -> list[Observacion]:
    """Lluvia diaria de POWER en el punto, un valor por día pedido, en el contrato común."""
    validar_pedido(lat, lon, desde, hasta)
    params = {
        "parameters": PARAMETRO,
        "community": "AG",
        "latitude": lat,
        "longitude": lon,
        "start": desde.strftime("%Y%m%d"),
        "end": hasta.strftime("%Y%m%d"),
        "format": "JSON",
        "time-standard": "UTC",  # día UTC, igual que IMERG
    }
    cliente = cliente or httpx.Client(timeout=60)
    try:
        respuesta = cliente.get(URL_POWER, params=params)
        respuesta.raise_for_status()
        serie = respuesta.json()["properties"]["parameter"][PARAMETRO]
        por_dia = {date(int(d[:4]), int(d[4:6]), int(d[6:8])): v for d, v in serie.items()}
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as error:
        raise ErrorPowerLluvia(f"No se pudo obtener la lluvia de NASA POWER: {error}") from error

    dias = [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]
    return [a_observacion(lote_id, dia, por_dia.get(dia), dia in por_dia) for dia in dias]


# ---------- conexión con el núcleo (spec 009) ----------

def pedir(lote: dict, desde: date, hasta: date) -> list[Observacion]:
    return obtener_lluvia(lote["id"], lote["lat"], lote["lon"], desde, hasta)


# único respaldo de IMERG: entra solo si IMERG falla, queda pendiente o no trae datos (specs 005 y 013)
SATELITES = [Satelite("IMERG:POWER", pedir, respaldo_de="IMERG")]
