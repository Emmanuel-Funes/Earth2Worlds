"""Conector GOES-19 heladas: temperatura de superficie mínima de la madrugada, respaldo "del día" de VIIRS (spec 043).

VIIRS publica la temperatura nocturna con 1 a 2 días de atraso. GOES-19, el satélite geoestacionario de la NOAA (socia
de la NASA), mira la Argentina todo el tiempo y publica la temperatura de superficie cada hora con menos de 1 hora de
atraso, en píxeles de 10 km. Se toma la mínima entre las 4 y las 7 de la mañana, cerca del mínimo térmico, como en los
visores de heladas de SEPA (spec 023). Solo completa los últimos días que VIIRS todavía no publicó: el núcleo lo pide
con `al_dia=True` (spec 043, parte A).

Satélite independiente (spec 009): no importa a ningún otro satélite. El archivo de la NOAA en AWS es abierto: no usa
cuenta.
"""

import os
import re
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, HTTPException

from rotaterra.contrato import Observacion
from rotaterra.fuentes.registro import Satelite

CUBO = "https://noaa-goes19.s3.amazonaws.com"  # GOES-19 es el GOES-Este operativo desde el 7/4/2025
PRODUCTO = "ABI-L2-LSTF"                        # temperatura de superficie, disco completo, cada hora
DESDE_GOES19 = date(2025, 4, 7)
HORAS = (7, 8, 9, 10)                           # UTC = 4 a 7 h de la Argentina
RESOLUCION_M = 10000
CALIDAD_DQF = {0: "buena", 1: "buena", 2: "dudosa"}  # bandera de calidad del producto; 3 o más = nube o sin dato
UMBRAL_HELADA = 0.0
MAX_DIAS = 10
HILOS = 8
AGENTE = "Rotaterra/0.1 (+https://github.com/hernanfirmapaz-ops/N4-4-1.2)"
CANDADO_NETCDF = threading.Lock()  # la biblioteca netCDF no admite dos lecturas a la vez
NOTA = ("Dato del día de GOES-19 ABI-L2-LSTF (NOAA): temperatura de superficie (piel del suelo, no del aire), píxel de "
        "10 km · completa los días que VIIRS todavía no publicó")


def archivos(cliente: httpx.Client, momento: datetime) -> list[str]:
    prefijo = f"{PRODUCTO}/{momento:%Y}/{momento:%j}/{momento:%H}/"
    r = cliente.get(CUBO, params={"list-type": "2", "prefix": prefijo}, timeout=30)
    r.raise_for_status()
    return [f"{CUBO}/{k}" for k in re.findall(r"<Key>([^<]+)</Key>", r.text)]


def leer_pixel(url: str, lat: float, lon: float) -> tuple[float | None, int | None]:
    """Temperatura (K) y bandera de calidad DQF en el píxel del lote. El archivo (~0,6 MB) se baja entero."""
    import rasterio
    from rasterio.warp import transform
    from rasterio.windows import Window

    def pixel(origen: str, nombre: str):
        with rasterio.open(f"netcdf:{origen}:{nombre}") as ds:
            xs, ys = transform("EPSG:4326", ds.crs, [lon], [lat])
            fila, col = ds.index(xs[0], ys[0])
            crudo = ds.read(1, window=Window(col, fila, 1, 1), boundless=True)[0, 0]
            if ds.nodata is not None and crudo == ds.nodata:
                return None
            return float(crudo) * ds.scales[0] + ds.offsets[0]

    respuesta = httpx.get(url, timeout=60, headers={"User-Agent": AGENTE})
    respuesta.raise_for_status()
    descriptor, ruta = tempfile.mkstemp(suffix=".nc")
    try:
        with os.fdopen(descriptor, "wb") as archivo:
            archivo.write(respuesta.content)
        with CANDADO_NETCDF:
            valor = pixel(ruta, "LST")
            dqf = pixel(ruta, "DQF")
    finally:
        os.remove(ruta)
    return valor, (int(dqf) if dqf is not None else None)


def minima_del_dia(lote_id: str, dia: date, lat: float, lon: float, cliente: httpx.Client, leer,
                   ahora: datetime) -> Observacion:
    base = dict(lote_id=lote_id, fecha=dia, variable="temp_sup_min_c", unidad="°C", fuente="GOES",
                resolucion_m=RESOLUCION_M)
    if dia < DESDE_GOES19:
        return Observacion(**base, valor=None, calidad="descartada", nota=f"{NOTA} · GOES-19 opera desde el 7/4/2025")
    lecturas, errores = [], 0
    horas = [datetime(dia.year, dia.month, dia.day, h, tzinfo=timezone.utc) for h in HORAS]
    pasadas = [m for m in horas if m + timedelta(hours=1) <= ahora]
    for momento in pasadas:
        try:
            urls = archivos(cliente, momento)
            if not urls:
                continue
            valor, dqf = leer(urls[0], lat, lon)
        except Exception:
            errores += 1
            continue
        if valor is not None and dqf in CALIDAD_DQF:
            lecturas.append((valor - 273.15, dqf, momento.hour - 3))
    if pasadas and errores == len(pasadas):
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"{NOTA} · el archivo de la NOAA no respondió")
    if not pasadas:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"{NOTA} · todavía no pasó la madrugada de este día")
    if not lecturas:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"{NOTA} · sin temperatura válida en el lote entre las 4 y las 7 h (nubes o sin dato)")
    # una lectura dudosa (DQF 2) suele ser un borde de nube, que da temperaturas de helada falsas (prueba real del
    # 16/10/2026: −5,7 °C con el aire a 10 °C): solo se usa si no hay ninguna lectura buena esa madrugada
    buenas = [lectura for lectura in lecturas if CALIDAD_DQF[lectura[1]] == "buena"]
    elegidas = buenas or lecturas
    temp, dqf, hora = min(elegidas)
    calidad = CALIDAD_DQF[dqf] if len(pasadas) == len(HORAS) else "dudosa"
    parcial = "" if len(pasadas) == len(HORAS) else f" · madrugada en curso ({len(pasadas)} de {len(HORAS)} horas)"
    riesgo = " · riesgo de helada (≤ 0 °C de superficie)" if temp <= UMBRAL_HELADA else ""
    return Observacion(**base, valor=round(temp, 1), calidad=calidad,
                       nota=f"{NOTA} · mínima de {len(elegidas)} lectura{'s' if len(elegidas) > 1 else ''}"
                                f"{'' if buenas else ' dudosas (posible nube)'}, a las {hora} h"
                                f"{parcial}{riesgo}")


def obtener_heladas(lote_id: str, lat: float, lon: float, desde: date, hasta: date,
                    cliente: httpx.Client | None = None, leer=leer_pixel,
                    ahora: datetime | None = None) -> list[Observacion]:
    """Mínima de la madrugada de cada día (últimos 10 días del pedido como máximo)."""
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    ahora = ahora or datetime.now(timezone.utc)
    cliente = cliente or httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": AGENTE})
    dias = [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]
    viejos, dias = dias[:-MAX_DIAS], dias[-MAX_DIAS:]
    observaciones = [Observacion(lote_id=lote_id, fecha=d, variable="temp_sup_min_c", valor=None, unidad="°C",
                                 fuente="GOES", resolucion_m=RESOLUCION_M, calidad="descartada",
                                 nota=f"{NOTA} · se leen los últimos {MAX_DIAS} días del pedido") for d in viejos]
    with ThreadPoolExecutor(max_workers=HILOS) as grupo:
        observaciones += list(grupo.map(lambda d: minima_del_dia(lote_id, d, lat, lon, cliente, leer, ahora), dias))
    return observaciones


SATELITES = [Satelite("VIIRS_LST:GOES",
                      lambda lote, desde, hasta: obtener_heladas(lote["id"], lote["lat"], lote["lon"], desde, hasta),
                      respaldo_de="VIIRS_LST", al_dia=True)]


# ---------- endpoint de prueba (spec 009): sin respaldos ----------

router = APIRouter(tags=["GOES-19 heladas (pruebas internas)"])


@router.get("/heladas/goes", response_model=list[Observacion])
def heladas_del_dia(lote_id: str, lat: float, lon: float, desde: date, hasta: date) -> list[Observacion]:
    try:
        return obtener_heladas(lote_id, lat, lon, desde, hasta)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
