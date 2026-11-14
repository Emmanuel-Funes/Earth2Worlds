"""Conector SMAP NRT: humedad superficial del día (SPL2SMP_NRT, 36 km), respaldo "del día" de SMAP (spec 043).

SMAP L4 (la principal) publica con unos 2 días de atraso. El producto de tiempo casi real SPL2SMP_NRT sale unas 2 horas
después de cada pasada (6 a 7 de la mañana o 19 a 20 en Argentina), en celdas EASE-2 de 36 km. Solo completa los últimos
días que SMAP todavía no publicó: el núcleo lo pide con `al_dia=True` (spec 043, parte A).

Satélite independiente (spec 009): busca en CMR y baja los archivos de NSIDC con la cuenta de Earthdata.
"""

import io
import math
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import httpx
import numpy as np
from fastapi import APIRouter, HTTPException

from rotaterra.contrato import Observacion
from rotaterra.fuentes import earthdata
from rotaterra.fuentes.registro import Satelite

PRODUCTO = "SPL2SMP_NRT"
GRUPO = "Soil_Moisture_Retrieval_Data"
RESOLUCION_M = 36000
RELLENO = -9999.0
RANGO = (0.02, 0.5)          # rango válido que declara el producto (m³/m³)
NO_RECOMENDADA = 1           # bit 0 de retrieval_qual_flag: 1 = la NASA no recomienda usar el valor
DISTANCIA_MAX_KM = 30.0      # el centro de una celda de 36 km queda a menos de ~26 km de cualquier punto de ella
HUSO = timedelta(hours=-3)   # día local argentino (UTC−3)
MAX_DIAS = 31
HILOS = 4
NOTA = ("Dato del día de NASA SMAP NRT (SPL2SMP_NRT, tiempo casi real), celda de 36 km (regional): "
        "completa los días que SMAP todavía no publicó")
_ORBITA = re.compile(r"SMAP_L2_SM_P_NRT_(\d+)_([AD])_\d{8}T\d{6}_([A-Z]\d+)_(\d{3})")


class ErrorSMAPNRT(Exception):
    """CMR o NSIDC no respondieron o respondieron algo ilegible."""


def validar_pedido(lat: float, lon: float, desde: date, hasta: date) -> None:
    if not -90 <= lat <= 90:
        raise ValueError(f"Latitud fuera de rango: {lat}")
    if not -180 <= lon <= 180:
        raise ValueError(f"Longitud fuera de rango: {lon}")
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise ValueError(f"El rango supera {MAX_DIAS} días")


def pasadas(cliente: httpx.Client, lat: float, lon: float, desde: date, hasta: date) -> list[tuple[str, str]]:
    """(nombre, URL) de cada pasada sobre el punto en los días locales pedidos. Si la NASA rehizo una pasada (_002),
    queda solo la versión más nueva."""
    inicio = datetime.combine(desde, datetime.min.time(), timezone.utc) - HUSO
    fin = datetime.combine(hasta + timedelta(days=1), datetime.min.time(), timezone.utc) - HUSO
    params = {"short_name": PRODUCTO, "page_size": 200, "sort_key": "start_date",
              "point": f"{lon},{lat}", "temporal": f"{inicio:%Y-%m-%dT%H:%M:%SZ},{fin:%Y-%m-%dT%H:%M:%SZ}"}
    respuesta = cliente.get(f"{earthdata.URL_CMR}/granules.umm_json", params=params)
    respuesta.raise_for_status()
    por_orbita: dict[tuple[str, str], tuple[str, str]] = {}
    for item in respuesta.json()["items"]:
        urls = [u["URL"] for u in item["umm"].get("RelatedUrls", [])
                if u["URL"].startswith("https://") and u["URL"].endswith(".h5")]
        hallado = _ORBITA.search(urls[0].rsplit("/", 1)[-1]) if urls else None
        if not hallado:
            continue
        nombre = urls[0].rsplit("/", 1)[-1]
        clave = (hallado[1], hallado[2])
        if clave not in por_orbita or nombre > por_orbita[clave][0]:
            por_orbita[clave] = (nombre, urls[0])
    return sorted(por_orbita.values())


def distancia_km(lat1: float, lon1: float, lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    p1, p2 = math.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def leer_celda(contenido: bytes, lat: float, lon: float) -> dict | None:
    """Valor de la celda de 36 km cuyo centro está más cerca del lote (None si la pasada no lo cubre)."""
    import h5py

    try:
        with h5py.File(io.BytesIO(contenido), "r") as archivo:
            g = archivo[GRUPO]
            lats, lons = g["latitude"][:], g["longitude"][:]
            if lats.size == 0:
                return None
            distancias = distancia_km(lat, lon, lats, lons)
            i = int(np.argmin(distancias))
            if distancias[i] > DISTANCIA_MAX_KM:
                return None
            return {"humedad": float(g["soil_moisture"][i]), "calidad": int(g["retrieval_qual_flag"][i]),
                    "superficie": int(g["surface_flag"][i]), "hora": g["tb_time_utc"][i].decode().rstrip("\x00"),
                    "distancia_km": float(distancias[i])}
    except (OSError, KeyError) as error:
        raise ErrorSMAPNRT(f"El archivo de SMAP NRT no se pudo leer: {error}") from error


def dia_local(hora_utc: str) -> date:
    """'2026-10-16T10:05:19.819Z' → día argentino de esa pasada."""
    momento = datetime.fromisoformat(hora_utc.replace("Z", "+00:00"))
    return (momento + HUSO).date()


def a_observacion(lote_id: str, dia: date, lecturas: list[dict]) -> Observacion:
    base = dict(lote_id=lote_id, fecha=dia, variable="humedad_superficial", unidad="m³/m³", fuente="SMAP_NRT",
                resolucion_m=RESOLUCION_M)
    if not lecturas:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"{NOTA} · SMAP no pasó sobre el lote este día o todavía no se publicó")
    minimo, maximo = RANGO
    utiles = [l for l in lecturas if l["humedad"] != RELLENO and minimo <= l["humedad"] <= maximo
              and not l["calidad"] & NO_RECOMENDADA]
    horas = ", ".join(f"{l['hora'][11:16]} UTC" for l in lecturas)
    if not utiles:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"{NOTA} · la NASA no recomienda el valor de ninguna pasada ({horas})")
    valor = round(sum(l["humedad"] for l in utiles) / len(utiles), 4)
    return Observacion(**base, valor=valor, calidad="dudosa",
                       nota=f"{NOTA} · promedio de {len(utiles)} de {len(lecturas)} pasadas ({horas}) · "
                            f"centro de la celda a {utiles[0]['distancia_km']:.0f} km del lote")


def obtener_humedad(lote_id: str, lat: float, lon: float, desde: date, hasta: date,
                    cliente: httpx.Client | None = None, hilos: int = HILOS) -> list[Observacion]:
    """Humedad superficial del día, una observación por día local argentino (descartada si no hubo pasada útil)."""
    validar_pedido(lat, lon, desde, hasta)
    try:
        cliente = earthdata.cliente_autorizado(cliente)
        hallados = pasadas(cliente, lat, lon, desde, hasta)

        def bajar(url: str) -> bytes:
            respuesta = cliente.get(url)
            respuesta.raise_for_status()
            return respuesta.content

        with ThreadPoolExecutor(max_workers=hilos) as grupo:
            contenidos = list(grupo.map(bajar, [url for _, url in hallados]))
    except earthdata.FaltanCredenciales:
        raise
    except (httpx.HTTPError, KeyError, ValueError, earthdata.ErrorNASA) as error:
        raise ErrorSMAPNRT(f"No se pudo obtener la humedad del día de SMAP NRT: {error}") from error
    por_dia: dict[date, list[dict]] = {}
    for contenido in contenidos:
        lectura = leer_celda(contenido, lat, lon)
        if lectura:
            por_dia.setdefault(dia_local(lectura["hora"]), []).append(lectura)
    dias = [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]
    return [a_observacion(lote_id, dia, por_dia.get(dia, [])) for dia in dias]


# ---------- conexión con el núcleo (spec 009) ----------

# respaldo del día de SMAP: completa los últimos días que SMAP L4 todavía no publicó (spec 043)
SATELITES = [Satelite("SMAP:SMAP_NRT",
                      lambda lote, desde, hasta: obtener_humedad(lote["id"], lote["lat"], lote["lon"], desde, hasta),
                      respaldo_de="SMAP", al_dia=True)]


# ---------- endpoint de prueba (spec 009): sin respaldos ----------

router = APIRouter(tags=["SMAP NRT (pruebas internas)"])


@router.get("/humedad-suelo/smap-nrt", response_model=list[Observacion])
def humedad_del_dia(lote_id: str, lat: float, lon: float, desde: date, hasta: date) -> list[Observacion]:
    try:
        validar_pedido(lat, lon, desde, hasta)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener_humedad(lote_id, lat, lon, desde, hasta)
    except earthdata.FaltanCredenciales as error:
        raise HTTPException(status_code=503, detail=str(error))
    except ErrorSMAPNRT as error:
        raise HTTPException(status_code=502, detail=str(error))
