"""Tercer respaldo de la lluvia de IMERG con NOAA PERSIANN-CDR (spec 038).

Satélite independiente (spec 009): baja sus propios archivos diarios de NOAA NCEI y no usa otros satélites.
NOAA es una de las agencias socias de la NASA permitidas (spec 008). Entra como tercer respaldo de la
lluvia, detrás de IMERG (principal), POWER (respaldo 1) y CPC (respaldo 2).

PERSIANN-CDR es una estimación por satélite (infrarrojo), calibrada con GPCP mensual: es un *Climate Data
Record* de NOAA. A diferencia de CPC (pluviómetros) estima la lluvia donde no hay estaciones, así que sirve
como última red de contención cuando IMERG y los dos primeros respaldos fallan o no traen el día.
"""

from __future__ import annotations

import re
import tempfile
from datetime import date, timedelta
from pathlib import Path

import httpx

from rotaterra.contrato import Observacion
from rotaterra.fuentes.registro import Satelite

URL_ANIO = "https://www.ncei.noaa.gov/data/precipitation-persiann/access/{anio}/"
VARIABLE = "precip"            # nombre esperado de la variable; si no está, se detecta sola (ver _elegir_precip)
# nombres de variables de coordenadas o auxiliares que NO son la lluvia
COORDS = {"lat", "lon", "latitude", "longitude", "time", "time_bnds", "lat_bnds", "lon_bnds", "nv", "crs"}
RESOLUCION_M = 27000          # celda de 0,25°: dato regional, no del lote
RANGO = (0.0, 500.0)          # el mismo rango físico que IMERG, POWER y CPC (spec 006)
MAX_DIAS = 186                # respaldo de último recurso: se baja un archivo por día (ver spec 038)
CARPETA = Path(tempfile.gettempdir()) / "rotaterra-persiann"
# nombre de cada archivo diario: PERSIANN-CDR_v01r01_YYYYMMDD_cYYYYMMDD.nc (la 'c' es la fecha de creación)
PATRON = re.compile(r'PERSIANN-CDR_v01r01_(\d{8})_c\d{8}\.nc')
NOTA = "Respaldo de IMERG · NOAA PERSIANN-CDR (estimación por satélite, calibrada con GPCP) · celda de 0,25°"

_LISTADO: dict[int, dict[date, str]] = {}  # {año: {fecha: nombre de archivo}}, en memoria del proceso


class ErrorPERSIANN(Exception):
    """PERSIANN no respondió o respondió algo que no se puede leer."""


def validar_pedido(lat: float, lon: float, desde: date, hasta: date) -> None:
    if not -90 <= lat <= 90:
        raise ValueError(f"Latitud fuera de rango: {lat}")
    if not -180 <= lon <= 180:
        raise ValueError(f"Longitud fuera de rango: {lon}")
    if not -60 <= lat <= 60:
        raise ValueError(f"PERSIANN-CDR solo cubre de 60°S a 60°N (lat {lat})")
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise ValueError(f"El rango supera {MAX_DIAS} días")


def listado_anual(cliente: httpx.Client, anio: int) -> dict[date, str]:
    """{fecha: nombre de archivo} de todos los días de PERSIANN-CDR de ese año (del índice HTML de NCEI)."""
    if anio not in _LISTADO:
        respuesta = cliente.get(URL_ANIO.format(anio=anio), timeout=120)
        respuesta.raise_for_status()
        # PATRON.finditer da el nombre completo (group 0) y el YYYYMMDD del día (group 1)
        _LISTADO[anio] = {date(int(d[:4]), int(d[4:6]), int(d[6:8])): m.group(0)
                          for m in PATRON.finditer(respuesta.text) for d in [m.group(1)]}
    return _LISTADO[anio]


def bajar_dia(cliente: httpx.Client, anio: int, nombre: str) -> Path:
    """Baja el NetCDF de un día (~1-2 MB) y lo deja en la carpeta temporal; lo reusa si ya está."""
    ruta = CARPETA / nombre
    if not ruta.exists():
        CARPETA.mkdir(parents=True, exist_ok=True)
        parcial = ruta.with_suffix(".parcial")
        with cliente.stream("GET", URL_ANIO.format(anio=anio) + nombre, timeout=120) as descarga:
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


def _elegir_precip(subdatasets: list[str]) -> str | None:
    """De los subdatasets de GDAL ('netcdf:archivo:variable') elige el de la lluvia.

    PERSIANN-CDR no siempre llama 'precip' a la variable, así que se detecta: se descartan las
    coordenadas y lo auxiliar, se prefiere la que tenga 'precip' en el nombre y, si queda una sola
    variable de datos, se usa esa.
    """
    nombre = lambda s: s.rsplit(":", 1)[-1].lower()
    datos = [s for s in subdatasets if nombre(s) not in COORDS]
    for s in datos:
        if "precip" in nombre(s):
            return s
    return datos[0] if len(datos) == 1 else None


def _leer_eje(ruta: Path, nombres: tuple[str, ...]):
    """Lee la variable de coordenada (lat o lon) abriéndola por nombre; None si ninguna existe.

    Las coordenadas 1-D no aparecen en los subdatasets de GDAL, pero se pueden abrir por nombre.
    """
    import numpy as np
    import rasterio

    for nombre in nombres:
        try:
            with rasterio.open(f"netcdf:{ruta}:{nombre}") as eje:
                return eje.read(1).astype("float64").ravel()
        except Exception:  # noqa: BLE001 — si una coordenada no se puede abrir, se prueba la siguiente
            continue
    return None


def lluvia_del_punto(ruta: Path, lat: float, lon: float) -> float | None:
    """Lluvia (mm/día) del píxel de 0,25° que contiene el punto, en el archivo de un día."""
    import numpy as np
    import rasterio

    with rasterio.open(ruta) as contenedor:  # abre el NetCDF y mira qué variables trae
        subdatasets = contenedor.subdatasets
    fuente = str(ruta) if not subdatasets else _elegir_precip(subdatasets)  # sin subdatasets: una sola variable
    if fuente is None:
        disponibles = [s.rsplit(":", 1)[-1] for s in subdatasets]
        raise ErrorPERSIANN(f"No encuentro la variable de lluvia en {ruta.name} · variables: {disponibles}")

    # Ubicar el píxel con los ejes de coordenadas (lat/lon): es lo más robusto, porque el NetCDF de
    # PERSIANN no siempre deja que GDAL arme el geotransform del subdataset (ni reporte bien su tamaño).
    lats = _leer_eje(ruta, ("lat", "latitude"))
    lons = _leer_eje(ruta, ("lon", "longitude"))
    with rasterio.open(fuente) as ds:
        banda = ds.read(1)  # un solo paso de tiempo por archivo diario: la grilla (lat, lon)
        relleno = ds.nodata
    if lats is not None and lons is not None and lats.size > 1 and lons.size > 1:
        x = lon % 360 if lons.max() > 180 else lon  # PERSIANN puede venir en 0-360 o en -180-180
        i_lat = int(np.argmin(np.abs(lats - lat)))
        i_lon = int(np.argmin(np.abs(lons - x)))
        # GDAL puede devolver la banda como (lat, lon) o transpuesta (lon, lat) según su versión:
        # se elige el orden por el que coincide con los tamaños de los ejes.
        if banda.shape == (lats.size, lons.size):
            valor = banda[i_lat, i_lon]
        elif banda.shape == (lons.size, lats.size):
            valor = banda[i_lon, i_lat]
        else:
            raise ErrorPERSIANN(f"La grilla de PERSIANN no coincide con los ejes: banda {banda.shape}, "
                                f"lat {lats.size}, lon {lons.size}")
    else:  # sin ejes legibles: último recurso con el geotransform
        from rasterio.windows import Window
        with rasterio.open(fuente) as ds:
            x = lon % 360 if ds.bounds.right > 180 else lon
            fila, columna = ds.index(x, lat)
            if not (0 <= fila < ds.height and 0 <= columna < ds.width):
                raise ErrorPERSIANN(f"El punto ({lat}, {lon}) cae fuera de la grilla de PERSIANN")
            valor = ds.read(1, window=Window(columna, fila, 1, 1))[0, 0]
    if relleno is not None and valor == relleno:
        return None
    return _limpio(float(valor))


def a_observacion(lote_id: str, dia: date, valor: float | None, devuelto: bool) -> Observacion:
    base = dict(lote_id=lote_id, fecha=dia, variable="lluvia_mm", unidad="mm/día",
                fuente="PERSIANN", resolucion_m=RESOLUCION_M)
    if not devuelto:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"PERSIANN todavía no tiene este día · {NOTA}")
    if valor is None:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"Píxel sin dato · {NOTA}")
    valor = round(float(valor), 2)
    minimo, maximo = RANGO
    if not minimo <= valor <= maximo:
        return Observacion(**base, valor=valor, calidad="dudosa",
                           nota=f"Fuera del rango físico ({minimo:.0f} a {maximo:.0f} mm/día) · {NOTA}")
    return Observacion(**base, valor=valor, calidad="buena", nota=NOTA)


def obtener_lluvia(lote_id: str, lat: float, lon: float, desde: date, hasta: date,
                   cliente: httpx.Client | None = None) -> list[Observacion]:
    """Lluvia diaria de PERSIANN-CDR en el punto, un valor por día pedido, en el contrato común."""
    validar_pedido(lat, lon, desde, hasta)
    cliente = cliente or httpx.Client(timeout=120, follow_redirects=True)
    dias = [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]
    por_dia: dict[date, float | None] = {}
    devueltos: set[date] = set()
    try:
        for anio in range(desde.year, hasta.year + 1):
            listado = listado_anual(cliente, anio)
            for dia in dias:
                if dia.year == anio and dia in listado:
                    por_dia[dia] = lluvia_del_punto(bajar_dia(cliente, anio, listado[dia]), lat, lon)
                    devueltos.add(dia)
    except ErrorPERSIANN:
        raise
    except Exception as error:  # red, NetCDF ilegible o índice raro: se informa y sigue el pipeline
        raise ErrorPERSIANN(f"No se pudo obtener la lluvia de NOAA PERSIANN-CDR: "
                            f"{type(error).__name__}: {error}") from error

    return [a_observacion(lote_id, dia, por_dia.get(dia), dia in devueltos) for dia in dias]


# ---------- conexión con el núcleo (spec 009) ----------

def pedir(lote: dict, desde: date, hasta: date) -> list[Observacion]:
    return obtener_lluvia(lote["id"], lote["lat"], lote["lon"], desde, hasta)


# Tercer respaldo de IMERG (orden 3): entra solo si IMERG, POWER (orden 1) y CPC (orden 2) fallan,
# quedan pendientes o no traen datos (specs 005 y 013).
SATELITES = [Satelite("IMERG:PERSIANN", pedir, respaldo_de="IMERG", orden=3)]
