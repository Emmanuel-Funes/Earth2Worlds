"""Segundo respaldo de la lluvia de IMERG con NOAA CPC Global Unified gauge-based (spec 029).

Satélite independiente (spec 009): baja su propio archivo anual de NOAA y no usa otros satélites.
NOAA es una de las agencias socias de la NASA permitidas (spec 008). A diferencia de POWER (modelo),
CPC es un análisis de **pluviómetros**: desde que la NASA dejó de publicar IMERG Final (30/9/2025)
toda la lluvia de IMERG es "Late", sin corrección por estaciones, así que un respaldo basado en
pluviómetros gana valor.
"""

from __future__ import annotations

import re
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx

from rotaterra.contrato import Observacion
from rotaterra.fuentes.registro import Satelite

URL_CPC = "https://downloads.psl.noaa.gov/Datasets/cpc_global_precip/precip.{anio}.nc"
VARIABLE = "precip"
RESOLUCION_M = 55000          # celda de 0,5°: dato regional, no del lote (igual que POWER)
RANGO = (0.0, 500.0)          # el mismo rango físico que IMERG y POWER (spec 006)
MAX_DIAS = 366
CARPETA = Path(tempfile.gettempdir()) / "rotaterra-cpc"
NOTA = "Respaldo de IMERG · NOAA CPC Global Unified (pluviómetros) · celda de 0,5°"


class ErrorCPC(Exception):
    """CPC no respondió o respondió algo que no se puede leer."""


def validar_pedido(lat: float, lon: float, desde: date, hasta: date) -> None:
    if not -90 <= lat <= 90:
        raise ValueError(f"Latitud fuera de rango: {lat}")
    if not -180 <= lon <= 180:
        raise ValueError(f"Longitud fuera de rango: {lon}")
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise ValueError(f"El rango supera {MAX_DIAS} días")


def fechas_del_tiempo(valores: list[float], unidades: str) -> list[date]:
    """Convierte el eje 'time' del NetCDF en fechas.

    CPC lo declara como 'hours since 1900-01-01' (así lo expone GDAL); se aceptan también
    'days', 'minutes' y 'seconds' por si NOAA cambia la unidad.
    """
    m = re.search(r"(days|hours|minutes|seconds) since (\d{4})-(\d{1,2})-(\d{1,2})", unidades)
    if not m:
        raise ErrorCPC(f"No se entiende el eje de tiempo de CPC: {unidades!r}")
    unidad, origen = m[1], datetime(int(m[2]), int(m[3]), int(m[4]))
    return [(origen + timedelta(**{unidad: v})).date() for v in valores]


def archivo_anual(cliente: httpx.Client, anio: int) -> Path:
    """Baja el NetCDF anual de CPC (~49 MB) y lo deja en la carpeta temporal.

    CPC agrega los días nuevos al mismo archivo del año, así que se vuelve a bajar si el que está
    guardado es de un día anterior; dentro del mismo día se reusa el que ya se bajó.
    """
    ruta = CARPETA / f"precip.{anio}.nc"
    vigente = ruta.exists() and date.fromtimestamp(ruta.stat().st_mtime) >= date.today()
    if not vigente:
        CARPETA.mkdir(parents=True, exist_ok=True)
        parcial = ruta.with_suffix(".parcial")
        with cliente.stream("GET", URL_CPC.format(anio=anio), timeout=300) as descarga:
            descarga.raise_for_status()
            with open(parcial, "wb") as destino:
                for pedazo in descarga.iter_bytes():
                    destino.write(pedazo)
        parcial.replace(ruta)
    return ruta


def _limpio(valor: float) -> float | None:
    """Descarta rellenos: NaN, el relleno gigante del NetCDF o valores imposibles."""
    if valor != valor:  # NaN
        return None
    if valor < -900 or valor > 1e19:
        return None
    return float(valor)


def dias_del_punto(ruta: Path, lat: float, lon: float) -> dict[date, float | None]:
    """{fecha: lluvia_mm o None} del píxel de 0,5° que contiene el punto, por cada día del archivo."""
    import rasterio
    from rasterio.windows import Window

    with rasterio.open(f"netcdf:{ruta}:{VARIABLE}") as ds:
        unidades = ds.tags().get("time#units", "")
        x = lon % 360 if ds.bounds.right > 180 else lon  # CPC usa longitudes de 0 a 360
        fila, columna = ds.index(x, lat)
        if not (0 <= fila < ds.height and 0 <= columna < ds.width):
            raise ErrorCPC(f"El punto ({lat}, {lon}) cae fuera de la grilla de CPC")
        valores = ds.read(window=Window(columna, fila, 1, 1))[:, 0, 0]
        tiempos = [float(ds.tags(banda)["NETCDF_DIM_time"]) for banda in range(1, ds.count + 1)]
        relleno = ds.nodata
    fechas = fechas_del_tiempo(tiempos, unidades)
    def limpio(valor: float) -> float | None:
        if relleno is not None and valor == relleno:
            return None
        return _limpio(valor)
    return {dia: limpio(float(valor)) for dia, valor in zip(fechas, valores)}


def a_observacion(lote_id: str, dia: date, valor: float | None, devuelto: bool) -> Observacion:
    base = dict(lote_id=lote_id, fecha=dia, variable="lluvia_mm", unidad="mm/día",
                fuente="CPC", resolucion_m=RESOLUCION_M)
    if not devuelto:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"CPC todavía no tiene este día · {NOTA}")
    if valor is None:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"Píxel sin dato (mar o sin pluviómetro cercano) · {NOTA}")
    valor = round(float(valor), 2)
    minimo, maximo = RANGO
    if not minimo <= valor <= maximo:
        return Observacion(**base, valor=valor, calidad="dudosa",
                           nota=f"Fuera del rango físico ({minimo:.0f} a {maximo:.0f} mm/día) · {NOTA}")
    return Observacion(**base, valor=valor, calidad="buena", nota=NOTA)


def obtener_lluvia(lote_id: str, lat: float, lon: float, desde: date, hasta: date,
                   cliente: httpx.Client | None = None) -> list[Observacion]:
    """Lluvia diaria de CPC en el punto, un valor por día pedido, en el contrato común."""
    validar_pedido(lat, lon, desde, hasta)
    cliente = cliente or httpx.Client(timeout=300, follow_redirects=True)
    por_dia: dict[date, float | None] = {}
    try:
        for anio in range(desde.year, hasta.year + 1):
            por_dia.update(dias_del_punto(archivo_anual(cliente, anio), lat, lon))
    except ErrorCPC:
        raise
    except Exception as error:  # red, NetCDF ilegible o metadatos raros: se informa y sigue el pipeline
        raise ErrorCPC(f"No se pudo obtener la lluvia de NOAA CPC: {type(error).__name__}: {error}") from error

    dias = [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]
    return [a_observacion(lote_id, dia, por_dia.get(dia), dia in por_dia) for dia in dias]


# ---------- conexión con el núcleo (spec 009) ----------

def pedir(lote: dict, desde: date, hasta: date) -> list[Observacion]:
    return obtener_lluvia(lote["id"], lote["lat"], lote["lon"], desde, hasta)


# Segundo respaldo de IMERG (orden 2): entra solo si IMERG y el primer respaldo (POWER) fallan,
# quedan pendientes o no traen datos (specs 005 y 013). Al ser de pluviómetros, se puede promover
# a orden 1 por delante de POWER si Hernán lo decide (ver spec 029).
SATELITES = [Satelite("IMERG:CPC", pedir, respaldo_de="IMERG", orden=2)]
