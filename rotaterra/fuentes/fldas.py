"""Conector FLDAS: respaldo de humedad del suelo de la NASA (spec 036).

Respaldo final de SMAP (después de AppEEARS, SMAP L3 y GLDAS). La fuente es FLDAS Noah 0.1°
(`FLDAS_NOAH01_C_GL_M`), un modelo de superficie de la NASA (GES DISC), hermano de GLDAS pero con una
grilla más fina (~11 km) y paso **mensual**. Da la humedad del suelo por capas en m³/m³.

Es un dato REGIONAL de modelo y MENSUAL: el píxel cubre miles de hectáreas y el valor es el promedio del
mes. Por eso entra último (orden 4) y su calidad nunca pasa de `dudosa`. Se lee por OPeNDAP (`.dmr` para
los metadatos, `.dap.csv` para el recorte), solo el píxel del lote. No importa a ningún otro satélite
(spec 009): las ayudas de OPeNDAP están repetidas acá a propósito (vienen del patrón de GLDAS).
"""

import re
import xml.etree.ElementTree as XML
from datetime import date

import httpx
from fastapi import APIRouter, HTTPException

from rotaterra.contrato import Observacion
from rotaterra.fuentes import earthdata
from rotaterra.fuentes.registro import Satelite

PRODUCTO = "FLDAS_NOAH01_C_GL_M"
RESOLUCION_M = 11000          # celda de 0,1° (~11 km)
MAX_MESES = 24
RANGO = (0.0, 1.0)            # m³/m³ físicamente posible
NOTA_REGIONAL = "píxel de 0,1° (~11 km), dato REGIONAL y MENSUAL de modelo, no una medición del lote"
_FECHA = re.compile(r"\.A(\d{4})(\d{2})\.")
_ESQUEMA: dict[str, dict] = {}  # url -> dimensiones, coordenadas y tamaños del archivo

# capas de humedad del suelo de FLDAS (ya vienen en m³/m³, volumétrico) y su espesor en metros
CAPA_SUP = "SoilMoi00_10cm_tavg"
CAPAS_RAIZ = [("SoilMoi00_10cm_tavg", 0.10), ("SoilMoi10_40cm_tavg", 0.30), ("SoilMoi40_100cm_tavg", 0.60)]


class ErrorFLDAS(Exception):
    """La NASA no respondió o respondió algo ilegible."""


def validar_pedido(lat: float, lon: float, desde: date, hasta: date) -> None:
    if not -90 <= lat <= 90:
        raise ValueError(f"Latitud fuera de rango: {lat}")
    if not -180 <= lon <= 180:
        raise ValueError(f"Longitud fuera de rango: {lon}")
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    if (hasta.year - desde.year) * 12 + (hasta.month - desde.month) + 1 > MAX_MESES:
        raise ValueError(f"El rango supera {MAX_MESES} meses")


# ---------- metadatos del archivo (DAP4 .dmr), patrón de GLDAS ----------

def esquema(dmr: str) -> dict:
    """Dimensiones de cada variable y tamaño de cada dimensión, leídos del .dmr."""
    raiz = XML.fromstring(dmr)
    tamanos, variables = {}, {}
    for nodo in raiz.iter():
        etiqueta = nodo.tag.rsplit("}", 1)[-1]
        if etiqueta == "Dimension" and nodo.get("name"):
            tamanos[nodo.get("name").lstrip("/")] = int(nodo.get("size"))
        elif nodo.get("name") and any(h.tag.rsplit("}", 1)[-1] == "Dim" for h in nodo):
            variables[nodo.get("name")] = [h.get("name").lstrip("/").rsplit("/", 1)[-1] for h in nodo
                                           if h.tag.rsplit("}", 1)[-1] == "Dim"]
    return {"tamanos": tamanos, "variables": variables}


def preparar_esquema(cliente: httpx.Client, url: str) -> dict:
    if url not in _ESQUEMA:
        respuesta = cliente.get(f"{url}.dmr")
        if respuesta.status_code in (401, 403):
            raise earthdata.ErrorNASA("La NASA negó el acceso a los metadatos de FLDAS")
        respuesta.raise_for_status()
        _ESQUEMA[url] = esquema(respuesta.text)
    return _ESQUEMA[url]


def nombre_coordenada(esq: dict, opciones: tuple[str, ...]) -> str:
    nombre = next((n for n in opciones if n in esq["variables"]), None)
    if nombre is None:
        raise ErrorFLDAS(f"El archivo no tiene ninguna de las coordenadas {opciones}")
    return nombre


def indice_mas_cercano(valores: list[float], buscado: float) -> int:
    return min(range(len(valores)), key=lambda i: abs(valores[i] - buscado))


def leer_vector(cliente: httpx.Client, url: str, nombre: str) -> list[float]:
    crudo = earthdata.leer_csv(cliente, url, nombre)
    valores = [v for fila in (crudo.get(nombre) or []) for v in fila if v is not None]
    if not valores:
        raise ErrorFLDAS(f"OPeNDAP no devolvió la coordenada '{nombre}' de {url}")
    return valores


def celda(cliente: httpx.Client, url: str, esq: dict, lat: float, lon: float) -> tuple[str, int, str, int]:
    nombre_lat = nombre_coordenada(esq, ("Y", "lat", "latitude"))
    nombre_lon = nombre_coordenada(esq, ("X", "lon", "longitude"))
    lats, lons = leer_vector(cliente, url, nombre_lat), leer_vector(cliente, url, nombre_lon)
    buscada = lon % 360 if max(lons) > 180 else lon
    return nombre_lat, indice_mas_cercano(lats, lat), nombre_lon, indice_mas_cercano(lons, buscada)


def expresion(variable: str, esq: dict, fila: int, columna: int, nombre_lat: str, nombre_lon: str) -> str:
    """Recorte OPeNDAP del píxel. La última dimensión pide 2 celdas (la NASA devuelve vacío si pide una sola)."""
    dims = esq["variables"].get(variable)
    if not dims:
        raise ErrorFLDAS(f"El archivo no tiene la variable '{variable}'")
    indices = {nombre_lat: fila, nombre_lon: columna}
    partes = []
    for posicion, dim in enumerate(dims):
        inicio = indices.get(dim, 0)
        if posicion == len(dims) - 1:
            tamano = esq["tamanos"].get(dim, inicio + 2)
            inicio = min(inicio, tamano - 2)
            partes.append(f"[{inicio}:1:{inicio + 1}]")
        else:
            partes.append(f"[{inicio}:1:{inicio}]")
    return variable + "".join(partes)


def _limpio(valor: float | None) -> float | None:
    if valor is None or valor != valor or valor <= -9000 or abs(valor) > 1e14:  # relleno (-9999)
        return None
    return valor


def leer_capas(cliente: httpx.Client, url: str, esq: dict, nombre_lat: str, fila: int, nombre_lon: str,
               columna: int, capas: list[str]) -> dict[str, float | None]:
    ce = ";".join(expresion(c, esq, fila, columna, nombre_lat, nombre_lon) for c in capas)
    crudo = earthdata.leer_csv(cliente, url, ce)
    leidos = {}
    for capa in capas:
        filas = crudo.get(capa)
        leidos[capa] = _limpio(filas[0][0]) if filas and filas[0] else None
    return leidos


# ---------- archivos del período (uno por mes) ----------

def meses_del_periodo(cliente: httpx.Client, desde: date, hasta: date) -> dict[date, str]:
    """Primer día de cada mes -> URL OPeNDAP del archivo mensual de FLDAS en el período."""
    coleccion = earthdata.coleccion_vigente(cliente, PRODUCTO)
    if coleccion is None:
        return {}
    por_mes: dict[date, str] = {}
    for nombre, url in earthdata.archivos(cliente, coleccion, date(desde.year, desde.month, 1), hasta):
        hallado = _FECHA.search(nombre)
        if not hallado:
            continue
        mes = date(int(hallado[1]), int(hallado[2]), 1)
        if date(desde.year, desde.month, 1) <= mes <= hasta:
            por_mes[mes] = url
    return por_mes


def leer_periodo(lat: float, lon: float, desde: date, hasta: date,
                 cliente: httpx.Client | None = None) -> dict[date, dict[str, float | None]]:
    """Por mes, el valor del píxel del lote de cada capa de humedad (m³/m³), ya limpio."""
    validar_pedido(lat, lon, desde, hasta)
    capas = [c for c, _ in CAPAS_RAIZ]  # SoilMoi00_10cm ya está entre ellas (es también la superficial)
    try:
        cliente = earthdata.cliente_autorizado(cliente)
        por_mes = meses_del_periodo(cliente, desde, hasta)
        if not por_mes:
            return {}
        primera = por_mes[min(por_mes)]
        esq = preparar_esquema(cliente, primera)
        nombre_lat, fila, nombre_lon, columna = celda(cliente, primera, esq, lat, lon)
        salida = {}
        for mes, url in sorted(por_mes.items()):
            salida[mes] = leer_capas(cliente, url, esq, nombre_lat, fila, nombre_lon, columna, capas)
    except earthdata.FaltanCredenciales:
        raise
    except earthdata.ErrorNASA:
        raise
    except (httpx.HTTPError, KeyError, ValueError, XML.ParseError, ErrorFLDAS) as error:
        raise ErrorFLDAS(f"No se pudo leer FLDAS de la NASA: {type(error).__name__}: {error}") from error
    return salida


# ---------- observaciones ----------

def _obs(lote_id: str, mes: date, variable: str, valor: float | None, que_es: str) -> Observacion:
    base = dict(lote_id=lote_id, fecha=mes, variable=variable, unidad="m³/m³", fuente="FLDAS",
                resolucion_m=RESOLUCION_M)
    nota_fuente = f"Respaldo · {que_es} del modelo FLDAS Noah de la NASA (GES DISC) · promedio del mes · {NOTA_REGIONAL}"
    if valor is None:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"FLDAS no tiene dato para este mes · {nota_fuente}")
    if not RANGO[0] <= valor <= RANGO[1]:
        return Observacion(**base, valor=round(valor, 4), calidad="dudosa",
                           nota=f"Fuera del rango físico (0 a 1 m³/m³) · {nota_fuente}")
    # siempre 'dudosa': es un promedio mensual regional, nunca una medición del día ni del lote
    return Observacion(**base, valor=round(valor, 4), calidad="dudosa", nota=nota_fuente)


def a_observaciones(lote_id: str, mes: date, capas: dict[str, float | None]) -> list[Observacion]:
    superficial = capas.get(CAPA_SUP)
    pesos = [(capas.get(c), e) for c, e in CAPAS_RAIZ]
    if all(v is not None for v, _ in pesos):
        espesor = sum(e for _, e in pesos)
        raiz = sum(v * e for v, e in pesos) / espesor
    else:
        raiz = None
    return [
        _obs(lote_id, mes, "humedad_superficial", superficial, "humedad del suelo de 0 a 10 cm"),
        _obs(lote_id, mes, "humedad_zona_raiz", raiz, "humedad de la zona de raíces (0 a 100 cm)"),
    ]


def obtener_humedad(lote_id: str, lat: float, lon: float, desde: date, hasta: date,
                    cliente: httpx.Client | None = None) -> list[Observacion]:
    por_mes = leer_periodo(lat, lon, desde, hasta, cliente)
    if not por_mes:
        raise ErrorFLDAS(f"La NASA no publicó FLDAS entre {desde} y {hasta} (llega con ~1 mes de atraso)")
    salida = []
    for mes in sorted(por_mes):
        salida += a_observaciones(lote_id, mes, por_mes[mes])
    return salida


# ---------- conexión con el núcleo (spec 009) ----------

# Respaldo final de SMAP (humedad del suelo). orden=4: entra después de AppEEARS, SMAP L3 y GLDAS.
SATELITES = [Satelite("SMAP:FLDAS",
                      lambda lote, desde, hasta: obtener_humedad(lote["id"], lote["lat"], lote["lon"], desde, hasta),
                      respaldo_de="SMAP", orden=4)]

router = APIRouter(tags=["FLDAS (pruebas internas)"])


@router.get("/humedad-suelo/fldas", response_model=list[Observacion])
def humedad_fldas(lote_id: str, lat: float, lon: float, desde: date, hasta: date) -> list[Observacion]:
    try:
        validar_pedido(lat, lon, desde, hasta)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener_humedad(lote_id, lat, lon, desde, hasta)
    except earthdata.FaltanCredenciales as error:
        raise HTTPException(status_code=503, detail=str(error))
    except (ErrorFLDAS, earthdata.ErrorNASA) as error:
        raise HTTPException(status_code=502, detail=str(error))
