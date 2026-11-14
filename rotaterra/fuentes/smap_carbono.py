"""Conector SMAP L4 Carbono: productividad diaria de la vegetación alrededor del lote (spec 055).

SMAP L4C (NASA) combina la humedad del suelo de SMAP con la luz absorbida por las plantas y calcula, todos los
días y en celdas de 9 km, cuánto carbono fija la vegetación (GPP, productividad primaria bruta) y el balance
neto del ecosistema (NEE). Reemplaza la productividad de MODIS (MOD17), que deja de salir con el fin de MODIS.

Es un dato **regional**: una celda de 9 km tiene ~8.100 ha, y el lote de 25 ha cae dentro. Sirve para comparar
campañas y ver cómo viene la zona; no es el rinde del lote.

Cada archivo pesa ~140 MB. No se baja: se pide por OPeNDAP solo el valor de la celda del lote (un pedido por día).
"""

import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime

import httpx
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rotaterra.contrato import Observacion
from rotaterra.fuentes import earthdata
from rotaterra.fuentes.registro import Satelite
from rotaterra.geo import validar_poligono

PRODUCTO = "SPL4CMDL"         # se usa la versión más nueva en CMR (hoy la 008)
CAPAS = {"gpp_g_c_m2_dia": "GPP/gpp_mean", "nee_g_c_m2_dia": "NEE/nee_mean"}
# tipos de vegetación del modelo que importan para un lote agrícola (PFT 7 y 8 del producto)
CULTIVOS = {"cereales": "GPP/gpp_pft7_mean", "latifoliadas": "GPP/gpp_pft8_mean"}
RELLENO = -9999.0
GPP_MAX = 30.0                # g C/m²/día: más es imposible para un cultivo (supuesto, spec 055)
NEE_MAX = 30.0
UNIDAD = "g C/m²/día"
RESOLUCION_M = 9000
MAX_DIAS = 366
HILOS = 8
INTENTOS = 3
ESPERA_S = 2.0

# Grilla EASE-Grid 2.0 global de 9 km (EPSG:6933): 1624 filas × 3856 columnas
_X0, _Y0, _CELDA = -17367530.44516138, 7314540.830638585, 9008.055210146
_FILAS, _COLUMNAS = 1624, 3856


class ErrorSMAPCarbono(Exception):
    """La NASA no respondió o el archivo no se pudo leer."""


@dataclass
class Granulo:
    nombre: str
    fecha: date
    url: str


# ---------- cálculo puro (testeable sin internet) ----------

def validar_pedido(poligono: dict, desde: date, hasta: date) -> None:
    validar_poligono(poligono)
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise ValueError(f"El rango supera {MAX_DIAS} días")


def celda(lat: float, lon: float) -> tuple[int, int]:
    """Fila y columna de la celda de 9 km que contiene el punto."""
    from rasterio.warp import transform

    xs, ys = transform("EPSG:4326", "EPSG:6933", [lon], [lat])
    fila, columna = int((_Y0 - ys[0]) // _CELDA), int((xs[0] - _X0) // _CELDA)
    if not (0 <= fila < _FILAS and 0 <= columna < _COLUMNAS):
        raise ValueError("El lote cae fuera de la grilla de SMAP")
    return fila, columna


def valido(valor: float | None, maximo: float, puede_ser_negativo: bool) -> bool:
    if valor is None or not np.isfinite(valor) or valor <= RELLENO + 1:
        return False
    return abs(valor) <= maximo if puede_ser_negativo else 0 <= valor <= maximo


def gpp_valido(valor: float | None) -> bool:
    return valido(valor, GPP_MAX, False)


def a_observaciones(lote_id: str, fecha: date, valores: dict[str, float | None],
                    cultivos: dict[str, float | None], detalle: str) -> list[Observacion]:
    base = dict(lote_id=lote_id, fecha=fecha, unidad=UNIDAD, fuente="SMAP", resolucion_m=RESOLUCION_M)
    por_cultivo = " · ".join(f"{k} {v:.2f}" for k, v in cultivos.items() if gpp_valido(v))
    if por_cultivo:
        por_cultivo = f"GPP del modelo para {por_cultivo} · "
    observaciones = []
    for variable, valor in valores.items():
        es_nee = variable.startswith("nee")
        if not valido(valor, NEE_MAX if es_nee else GPP_MAX, es_nee):
            observaciones.append(Observacion(**base, variable=variable, valor=None, calidad="descartada",
                                             nota=f"Sin dato en la celda del lote · {detalle}"))
            continue
        explicacion = ("balance neto de carbono (negativo = la vegetación fija más de lo que respira)" if es_nee
                       else "productividad primaria bruta (carbono que fija la vegetación)")
        observaciones.append(Observacion(**base, variable=variable, valor=round(float(valor), 3), calidad="buena",
                                         nota=f"SMAP L4 Carbono · {explicacion} · dato regional de la celda de 9 km, "
                                              f"no del lote · {por_cultivo}{detalle}"))
    return observaciones


_FECHA = re.compile(r"_(\d{8})T\d{6}_")


def fecha_del_granulo(nombre: str) -> date:
    """SMAP_L4_C_mdl_20261012T000000_Vv8043_001.h5 → 2026-10-12."""
    hallado = _FECHA.search(nombre)
    if not hallado:
        raise ValueError(f"No se sabe la fecha del archivo {nombre}")
    return datetime.strptime(hallado[1], "%Y%m%d").date()


def expresion(fila: int, columna: int) -> str:
    """Recorte OPeNDAP de todas las capas en un solo pedido (2 columnas: el servidor no devuelve un solo valor)."""
    rutas = [*CAPAS.values(), *CULTIVOS.values()]
    return ";".join(f"/{r}[{fila}:1:{fila}][{columna}:1:{columna + 1}]" for r in rutas)


def valores_de(crudo: dict[str, list[list[float | None]]]) -> tuple[dict[str, float | None], dict[str, float | None]]:
    """Primer valor de cada capa (la segunda columna es solo para que el servidor responda)."""
    def uno(ruta: str) -> float | None:
        filas = next((f for nombre, f in crudo.items() if nombre.endswith(ruta)), None)
        return filas[0][0] if filas and filas[0] else None
    return {v: uno(r) for v, r in CAPAS.items()}, {k: uno(r) for k, r in CULTIVOS.items()}


# ---------- acceso a la NASA ----------

def buscar_granulos(cliente: httpx.Client, desde: date, hasta: date) -> list[Granulo]:
    coleccion = earthdata.coleccion_vigente(cliente, PRODUCTO)
    if coleccion is None:
        raise ErrorSMAPCarbono(f"CMR no tiene la colección {PRODUCTO}")
    return [Granulo(nombre, fecha_del_granulo(nombre), url)
            for nombre, url in earthdata.archivos(cliente, coleccion, desde, hasta)]


def procesar(lote_id: str, granulo: Granulo, fila: int, columna: int, cliente: httpx.Client,
             intentos: int = INTENTOS) -> list[Observacion]:
    for intento in range(intentos):
        try:
            crudo = earthdata.leer_csv(cliente, granulo.url, expresion(fila, columna))
            break
        except httpx.HTTPError:  # OPeNDAP a veces corta un pedido (502 o conexión cerrada): se reintenta
            if intento == intentos - 1:
                raise
            time.sleep(ESPERA_S * (intento + 1))
    valores, cultivos = valores_de(crudo)
    detalle = f"celda fila {fila}, columna {columna} · {granulo.nombre}"
    return a_observaciones(lote_id, granulo.fecha, valores, cultivos, detalle)


def obtener(lote_id: str, poligono: dict, desde: date, hasta: date, cliente: httpx.Client | None = None,
            hilos: int = HILOS) -> list[Observacion]:
    """GPP y NEE diarios de la celda de 9 km que contiene el centro del lote."""
    from shapely.geometry import shape

    validar_pedido(poligono, desde, hasta)
    centro = shape(poligono).centroid
    fila, columna = celda(centro.y, centro.x)
    try:
        cliente = earthdata.cliente_autorizado(cliente)
        granulos = [g for g in buscar_granulos(cliente, desde, hasta) if desde <= g.fecha <= hasta]
    except earthdata.FaltanCredenciales:
        raise
    except (httpx.HTTPError, KeyError, ValueError, earthdata.ErrorNASA) as error:
        raise ErrorSMAPCarbono(f"No se pudo buscar SMAP L4 Carbono en CMR: {error}") from error

    def uno(granulo):
        try:
            return procesar(lote_id, granulo, fila, columna, cliente), None
        except Exception as error:  # un archivo ilegible no inventa nada: queda descartado con el motivo
            return None, f"{type(error).__name__}: {str(error).split('?')[0]}"

    with ThreadPoolExecutor(max_workers=hilos) as grupo:
        resultados = list(grupo.map(uno, granulos))
    errores = [e for _, e in resultados if e]
    if granulos and len(errores) == len(granulos):
        raise ErrorSMAPCarbono(f"No se pudo leer ningún archivo de SMAP L4 Carbono: {errores[0]}")
    observaciones = []
    for granulo, (hecho, error) in zip(granulos, resultados):
        observaciones += hecho or a_observaciones(lote_id, granulo.fecha, dict.fromkeys(CAPAS), {},
                                                  f"No se pudo leer el archivo: {error} · {granulo.nombre}")
    return sorted(observaciones, key=lambda o: (o.fecha, o.variable))


# ---------- conexión con el núcleo (spec 009) ----------

# Fuente propia de dos variables nuevas (gpp_g_c_m2_dia y nee_g_c_m2_dia). No es respaldo de nadie: MOD17 de
# MODIS nunca se conectó, y cuando MODIS se apague esta es la productividad diaria que queda.
SATELITES = [Satelite("SMAP_L4C", lambda lote, desde, hasta: obtener(lote["id"], lote["poligono"], desde, hasta))]

router = APIRouter(tags=["SMAP Carbono (pruebas internas)"])


class PedidoCarbono(BaseModel):
    lote_id: str
    poligono: dict
    desde: date
    hasta: date


@router.post("/productividad", response_model=list[Observacion])
def productividad(pedido: PedidoCarbono) -> list[Observacion]:
    """GPP y NEE diarios (g C/m²/día) de SMAP L4 Carbono en la celda de 9 km del lote."""
    try:
        validar_pedido(pedido.poligono, pedido.desde, pedido.hasta)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener(pedido.lote_id, pedido.poligono, pedido.desde, pedido.hasta)
    except earthdata.FaltanCredenciales as error:
        raise HTTPException(status_code=503, detail=str(error))
    except ErrorSMAPCarbono as error:
        raise HTTPException(status_code=502, detail=str(error))
