"""Conector MODIS NRT: NDVI del día de 250 m (LANCE, MOD13Q4N), respaldo del día de HLS (spec 043)."""

import math
import os
import re
import tempfile
from datetime import date, timedelta

import httpx
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rotaterra.contrato import Observacion
from rotaterra.fuentes import earthdata
from rotaterra.fuentes.registro import Satelite
from rotaterra.geo import validar_poligono

PRODUCTO = "MOD13Q4N"  # Terra, compuesto de 8 días que LANCE rehace todos los días; sin servicio OPeNDAP
CAPAS = {
    "ndvi": "250m 8 days NDVI",
    "confiabilidad": "250m 8 days pixel reliability",
    "dia": "250m 8 days composite day of the year",
}
ESCALA = 0.0001
RELLENO_NDVI = -3000
CONFIABLES = (0, 1)  # 0 = buena, 1 = marginal; 2 = nieve, 3 = nube, -1 = sin dato
RESOLUCION_M = 250
DIAS_COMPUESTO = 8   # cada archivo cubre su día y los 7 anteriores
UNIDAD = "índice (-1 a 1)"
UMBRAL_DESCARTADA = 20.0  # % de píxeles válidos del lote, como HLS y MODIS (spec 007)
URS = "urs.earthdata.nasa.gov"
NOTA = ("Dato del día de LANCE MODIS NRT (MOD13Q4N, Terra), píxel de 250 m: lee 0,07 a 0,14 distinto que HLS, "
        "sirve para la tendencia; completa los días que HLS todavía no tiene")

# Grilla sinusoidal de MODIS: mosaicos de 4800 × 4800 píxeles
_R = 6371007.181
_MOSAICO = 1111950.5197665
_PIXEL = _MOSAICO / 4800
_X0, _Y0 = -20015109.354, 10007554.677


class ErrorMODISNRT(Exception):
    """LANCE o CMR no respondieron o respondieron algo ilegible."""


def validar_pedido(poligono: dict, desde: date, hasta: date) -> None:
    validar_poligono(poligono)
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")


def celda(lat: float, lon: float) -> tuple[int, int, int, int]:
    """Mosaico (h, v) y píxel (fila, columna) de MODIS que contienen el punto."""
    x = _R * math.radians(lon) * math.cos(math.radians(lat))
    y = _R * math.radians(lat)
    h, v = math.floor((x - _X0) / _MOSAICO), math.floor((_Y0 - y) / _MOSAICO)
    columna = math.floor((x - _X0 - h * _MOSAICO) / _PIXEL)
    fila = math.floor((_Y0 - y - v * _MOSAICO) / _PIXEL)
    return h, v, fila, columna


def ventana(poligono: dict) -> tuple[int, int, int, int, int, int]:
    """Mosaico y ventana de píxeles (fila0, fila1, col0, col1) que cubren el lote, con un píxel de margen."""
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
    return h, v, f0, f1, c0, c1


def coordenadas(h: int, v: int, f0: int, f1: int, c0: int, c1: int) -> tuple[np.ndarray, np.ndarray]:
    """Latitud y longitud del centro de cada píxel de la ventana."""
    filas, columnas = np.arange(f0, f1 + 1), np.arange(c0, c1 + 1)
    y = _Y0 - v * _MOSAICO - (filas[:, None] + 0.5) * _PIXEL + 0 * columnas[None, :]
    x = _X0 + h * _MOSAICO + (columnas[None, :] + 0.5) * _PIXEL + 0 * filas[:, None]
    lat = np.degrees(y / _R)
    return lat, np.degrees(x / (_R * np.cos(np.radians(lat))))


def fecha_archivo(nombre: str) -> date:
    """MOD13Q4N.A2026289.h12v12... → 2026-10-16 (último día del compuesto)."""
    hallado = re.search(r"\.A(\d{4})(\d{3})\.", nombre)
    return date(int(hallado[1]), 1, 1) + timedelta(days=int(hallado[2]) - 1)


def ultimo_archivo(cliente: httpx.Client, poligono: dict, h: int, v: int, hasta: date) -> tuple[str, str] | None:
    """(nombre, URL) del archivo más nuevo del mosaico con fecha hasta 'hasta' (None si LANCE no tiene ninguno)."""
    from shapely.geometry import shape

    params = {"short_name": PRODUCTO, "page_size": 50, "sort_key": "-start_date",
              "bounding_box": ",".join(str(c) for c in shape(poligono).bounds),
              "temporal": f"{(hasta - timedelta(days=DIAS_COMPUESTO)).isoformat()}T00:00:00Z,"
                          f"{hasta.isoformat()}T23:59:59Z"}
    respuesta = cliente.get(f"{earthdata.URL_CMR}/granules.umm_json", params=params)
    respuesta.raise_for_status()
    mosaico = f".h{h:02d}v{v:02d}."
    hallados = []
    for item in respuesta.json()["items"]:
        for u in item["umm"].get("RelatedUrls", []):
            nombre = u["URL"].rsplit("/", 1)[-1]
            if mosaico in nombre and nombre.endswith(".hdf") and fecha_archivo(nombre) <= hasta:
                hallados.append((nombre, u["URL"]))
    return max(hallados, key=lambda a: (fecha_archivo(a[0]), a[0])) if hallados else None


def bajar(cliente: httpx.Client, url: str, destino: str) -> None:
    """Baja el archivo de LANCE. LANCE pide iniciar sesión con Earthdata (redirecciones y cookie); el usuario y la
    contraseña se mandan solo a urs.earthdata.nasa.gov."""
    usuario, clave = os.environ.get("EARTHDATA_USERNAME"), os.environ.get("EARTHDATA_PASSWORD")
    if not usuario or not clave:
        raise earthdata.FaltanCredenciales("Faltan EARTHDATA_USERNAME y EARTHDATA_PASSWORD")
    for _ in range(10):
        auth = (usuario, clave) if httpx.URL(url).host == URS else None
        with cliente.stream("GET", url, auth=auth, follow_redirects=False) as respuesta:
            if respuesta.is_redirect:
                url = str(httpx.URL(url).join(respuesta.headers["location"]))
                continue
            if respuesta.status_code in (401, 403):
                raise earthdata.ErrorNASA("Earthdata rechazó el usuario o la contraseña para LANCE")
            respuesta.raise_for_status()
            if "html" in respuesta.headers.get("content-type", ""):
                raise ErrorMODISNRT("LANCE devolvió una página en vez del archivo (falta iniciar sesión)")
            with open(destino, "wb") as archivo:
                for bloque in respuesta.iter_bytes(1 << 20):
                    archivo.write(bloque)
            return
    raise ErrorMODISNRT("LANCE redirigió demasiadas veces")


def leer_ventana(ruta: str, f0: int, f1: int, c0: int, c1: int) -> dict[str, np.ndarray]:
    """Recorte del lote de las tres capas del archivo HDF4."""
    from pyhdf.SD import SD, SDC
    from pyhdf.error import HDF4Error

    try:
        archivo = SD(ruta, SDC.READ)
    except HDF4Error as error:
        raise ErrorMODISNRT(f"El archivo de LANCE no es un HDF4 legible: {error}") from error
    try:
        return {nombre: np.asarray(archivo.select(capa)[f0:f1 + 1, c0:c1 + 1], dtype="float64")
                for nombre, capa in CAPAS.items()}
    except HDF4Error as error:
        raise ErrorMODISNRT(f"Al archivo de LANCE le falta una capa: {error}") from error
    finally:
        archivo.end()


def resumir(lote_id: str, poligono: dict, datos: dict[str, np.ndarray], lat: np.ndarray, lon: np.ndarray,
            fin: date, nombre: str, desde: date, hasta: date) -> list[Observacion]:
    """Una observación por día de adquisición del compuesto (el día que vio cada píxel), dentro de desde–hasta."""
    from shapely.geometry import Point, shape

    lote = shape(poligono)
    dentro = np.array([[lote.contains(Point(x, y)) for y, x in zip(fila_lat, fila_lon)]
                       for fila_lat, fila_lon in zip(lat, lon)])
    aviso = ""
    if not dentro.any():  # lote más chico que un píxel de 6 ha: se usa el píxel que contiene su centro
        centro = lote.centroid
        distancia = (lat - centro.y) ** 2 + (lon - centro.x) ** 2
        dentro = distancia == np.nanmin(distancia)
        aviso = "lote menor a un píxel: se usa el píxel del centro · "
    validos = dentro & np.isin(datos["confiabilidad"], CONFIABLES) & (datos["ndvi"] != RELLENO_NDVI) \
        & np.isfinite(datos["ndvi"]) & (datos["dia"] >= 1)
    total, n_validos = int(dentro.sum()), int(validos.sum())
    inicio = fin - timedelta(days=DIAS_COMPUESTO - 1)
    detalle = f"{aviso}{nombre.split('.NRT')[0]}, compuesto del {inicio} al {fin} · {total} píxeles de 250 m"
    base = dict(lote_id=lote_id, variable="ndvi", unidad=UNIDAD, fuente="MODIS_NRT", resolucion_m=RESOLUCION_M)
    pct = 100.0 * n_validos / total
    if pct < UMBRAL_DESCARTADA:
        if not desde <= fin <= hasta:
            return []
        return [Observacion(**base, fecha=fin, valor=None, calidad="descartada",
                            nota=f"{NOTA} · Nubes, nieve o sin dato en el lote (válidos {pct:.0f}%) · {detalle}")]
    observaciones = []
    for dia_del_anio in sorted({int(d) for d in datos["dia"][validos]}):
        anio = fin.year - (1 if dia_del_anio > fin.timetuple().tm_yday else 0)  # compuesto que cruza el año
        fecha = date(anio, 1, 1) + timedelta(days=dia_del_anio - 1)
        if not desde <= fecha <= hasta:
            continue
        del_dia = validos & (datos["dia"] == dia_del_anio)
        valor = round(float(np.median(datos["ndvi"][del_dia] * ESCALA)), 3)
        if not -1 <= valor <= 1:
            observaciones.append(Observacion(**base, fecha=fecha, valor=None, calidad="descartada",
                                             nota=f"{NOTA} · NDVI fuera de -1 a 1 · {detalle}"))
            continue
        pct_dia = 100.0 * int(del_dia.sum()) / total
        observaciones.append(Observacion(**base, fecha=fecha, valor=valor, calidad="dudosa",
                                         nota=f"{NOTA} · {detalle} · píxeles vistos este día {pct_dia:.0f}%"))
    return observaciones


def obtener_ndvi(lote_id: str, poligono: dict, desde: date, hasta: date,
                 cliente: httpx.Client | None = None) -> list[Observacion]:
    """NDVI del día del lote desde el compuesto más nuevo de LANCE: cubre a lo sumo los últimos 8 días hasta 'hasta'.
    Los días anteriores quedan para los respaldos comunes de HLS (un archivo pesa ~215 MB)."""
    validar_pedido(poligono, desde, hasta)
    h, v, f0, f1, c0, c1 = ventana(poligono)
    cliente = cliente or httpx.Client(timeout=600)
    with tempfile.TemporaryDirectory() as carpeta:
        try:
            hallado = ultimo_archivo(cliente, poligono, h, v, hasta)
            if hallado is None:
                return []
            nombre, url = hallado
            ruta = os.path.join(carpeta, "mod13q4n.hdf")
            bajar(cliente, url, ruta)
        except earthdata.FaltanCredenciales:
            raise
        except (httpx.HTTPError, KeyError, ValueError, earthdata.ErrorNASA) as error:
            raise ErrorMODISNRT(f"No se pudo obtener el NDVI del día de LANCE: {error}") from error
        datos = leer_ventana(ruta, f0, f1, c0, c1)
    lat, lon = coordenadas(h, v, f0, f1, c0, c1)
    return resumir(lote_id, poligono, datos, lat, lon, fecha_archivo(nombre), nombre, desde, hasta)


# ---------- conexión con el núcleo (spec 009) ----------

# respaldo del día de HLS: completa los últimos días que HLS todavía no tiene (spec 043)
SATELITES = [Satelite("HLS:MODIS_NRT",
                      lambda lote, desde, hasta: obtener_ndvi(lote["id"], lote["poligono"], desde, hasta),
                      respaldo_de="HLS", al_dia=True)]


# ---------- endpoint de prueba (spec 009): sin respaldos ----------

router = APIRouter(tags=["MODIS NRT (pruebas internas)"])


class PedidoNdviDelDia(BaseModel):
    lote_id: str
    poligono: dict
    desde: date
    hasta: date


@router.post("/ndvi/modis-nrt", response_model=list[Observacion])
def ndvi_del_dia(pedido: PedidoNdviDelDia) -> list[Observacion]:
    try:
        validar_pedido(pedido.poligono, pedido.desde, pedido.hasta)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener_ndvi(pedido.lote_id, pedido.poligono, pedido.desde, pedido.hasta)
    except earthdata.FaltanCredenciales as error:
        raise HTTPException(status_code=503, detail=str(error))
    except ErrorMODISNRT as error:
        raise HTTPException(status_code=502, detail=str(error))
