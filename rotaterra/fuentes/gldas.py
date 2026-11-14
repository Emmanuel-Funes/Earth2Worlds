"""Conector GLDAS: respaldo de humedad del suelo y de ET real de la NASA (spec 032).

Respaldo final de SMAP (humedad) y de la ET (después de ECOSTRESS). La fuente es GLDAS Noah 0.25°
(`GLDAS_NOAH025_3H`, con el producto temprano `_EP` para lo reciente), un modelo de superficie de la
NASA (GES DISC) que da humedad del suelo por capas y ET cada 3 horas, en una grilla de ~25 km, con ~1
mes de atraso. Es un dato REGIONAL de modelo: el píxel cubre miles de hectáreas.

Se lee por OPeNDAP (`.dmr` para los metadatos, `.dap.csv` para el recorte), solo el píxel del lote, y
los 8 pasos de 3 h de cada día se promedian. No importa a ningún otro satélite (spec 009): las ayudas de
OPeNDAP están repetidas acá a propósito.
"""

import re
import xml.etree.ElementTree as XML
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import httpx
from fastapi import APIRouter, HTTPException

from rotaterra.contrato import Observacion
from rotaterra.fuentes import earthdata
from rotaterra.fuentes.registro import Satelite

PRODUCTO_FINAL = "GLDAS_NOAH025_3H"
PRODUCTO_EP = "GLDAS_NOAH025_3H_EP"  # producto temprano: cubre los días más recientes
RESOLUCION_M = 25000
MAX_DIAS = 92
HILOS = 8
PASOS_POR_DIA = 8  # cada 3 h

# variable del contrato -> (variable del archivo, factor a la unidad del contrato, rango físico, unidad, qué es)
HUMEDAD = {
    "humedad_superficial": ("SoilMoi0_10cm_inst", 1 / 100, (0.0, 1.0), "m³/m³", "humedad del suelo de 0 a 10 cm"),
    "humedad_zona_raiz": ("RootMoist_inst", 1 / 1000, (0.0, 1.0), "m³/m³", "humedad de la zona de raíces (~0 a 100 cm)"),
}
ET = {
    "et_mm_dia": ("Evap_tavg", 86400, (0.0, 20.0), "mm/día", "evapotranspiración real"),
}
_FECHA = re.compile(r"\.A(\d{8})\.(\d{4})\.")
NOTA_REGIONAL = ("píxel de 0,25° (~25 km), dato REGIONAL de modelo, no una medición del lote")
_ESQUEMA: dict[str, dict] = {}  # url -> dimensiones, coordenadas y tamaños del archivo


class ErrorGLDAS(Exception):
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


# ---------- metadatos del archivo (DAP4 .dmr) ----------

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
            raise earthdata.ErrorNASA("La NASA negó el acceso a los metadatos de GLDAS")
        respuesta.raise_for_status()
        _ESQUEMA[url] = esquema(respuesta.text)
    return _ESQUEMA[url]


def nombre_coordenada(esq: dict, opciones: tuple[str, ...]) -> str:
    nombre = next((n for n in opciones if n in esq["variables"]), None)
    if nombre is None:
        raise ErrorGLDAS(f"El archivo no tiene ninguna de las coordenadas {opciones}")
    return nombre


def indice_mas_cercano(valores: list[float], buscado: float) -> int:
    return min(range(len(valores)), key=lambda i: abs(valores[i] - buscado))


def leer_vector(cliente: httpx.Client, url: str, nombre: str) -> list[float]:
    crudo = earthdata.leer_csv(cliente, url, nombre)
    valores = [v for fila in (crudo.get(nombre) or []) for v in fila if v is not None]
    if not valores:
        raise ErrorGLDAS(f"OPeNDAP no devolvió la coordenada '{nombre}' de {url}")
    return valores


def celda(cliente: httpx.Client, url: str, esq: dict, lat: float, lon: float) -> tuple[str, int, str, int]:
    nombre_lat = nombre_coordenada(esq, ("lat", "latitude"))
    nombre_lon = nombre_coordenada(esq, ("lon", "longitude"))
    lats, lons = leer_vector(cliente, url, nombre_lat), leer_vector(cliente, url, nombre_lon)
    buscada = lon % 360 if max(lons) > 180 else lon
    return nombre_lat, indice_mas_cercano(lats, lat), nombre_lon, indice_mas_cercano(lons, buscada)


def expresion(variable: str, esq: dict, fila: int, columna: int, nombre_lat: str, nombre_lon: str) -> str:
    """Recorte OPeNDAP del píxel. La última dimensión pide 2 celdas (la NASA devuelve vacío si pide una sola)."""
    dims = esq["variables"].get(variable)
    if not dims:
        raise ErrorGLDAS(f"El archivo no tiene la variable '{variable}'")
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
    if valor is None or valor != valor or valor <= -9000 or abs(valor) > 1e14:  # relleno (-9999, 9.999e14)
        return None
    return valor


# ---------- archivos del período (final + temprano) ----------

def pasos_del_periodo(cliente: httpx.Client, desde: date, hasta: date) -> dict[tuple[date, str], str]:
    """(día, hora) -> URL OPeNDAP de cada paso de 3 h; si está en el final y en el temprano, gana el final."""
    pasos: dict[tuple[date, str], tuple[int, str]] = {}
    for prioridad, producto in ((1, PRODUCTO_EP), (0, PRODUCTO_FINAL)):  # el final (0) pisa al temprano (1)
        coleccion = earthdata.coleccion_vigente(cliente, producto)
        if coleccion is None:
            continue
        for nombre, url in earthdata.archivos(cliente, coleccion, desde, hasta):
            hallado = _FECHA.search(nombre)
            if not hallado:
                continue
            t, hora = hallado[1], hallado[2]
            dia = date(int(t[:4]), int(t[4:6]), int(t[6:]))
            if not desde <= dia <= hasta:
                continue
            clave = (dia, hora)
            if clave not in pasos or prioridad < pasos[clave][0]:
                pasos[clave] = (prioridad, url)
    return {clave: url for clave, (_, url) in pasos.items()}


def leer_paso(cliente: httpx.Client, url: str, esq: dict, nombre_lat: str, fila: int, nombre_lon: str,
              columna: int, variables: dict) -> dict[str, float | None]:
    ce = ";".join(expresion(v[0], esq, fila, columna, nombre_lat, nombre_lon) for v in variables.values())
    crudo = earthdata.leer_csv(cliente, url, ce)
    leidos = {}
    for destino, (variable_archivo, *_resto) in variables.items():
        filas = crudo.get(variable_archivo)
        leidos[destino] = _limpio(filas[0][0]) if filas and filas[0] else None
    return leidos


def leer_periodo(lat: float, lon: float, desde: date, hasta: date, variables: dict,
                 cliente: httpx.Client | None = None) -> dict[date, dict[str, list[float]]]:
    """Por día, la lista de valores (uno por paso de 3 h) de cada variable, ya convertidos a la unidad del contrato."""
    validar_pedido(lat, lon, desde, hasta)
    try:
        cliente = earthdata.cliente_autorizado(cliente)
        pasos = pasos_del_periodo(cliente, desde, hasta)
        if not pasos:
            return {}
        primera = next(iter(sorted(pasos.items())))[1]
        esq = preparar_esquema(cliente, primera)
        nombre_lat, fila, nombre_lon, columna = celda(cliente, primera, esq, lat, lon)
        tareas = sorted(pasos.items())
        with ThreadPoolExecutor(max_workers=HILOS) as grupo:
            leidos = list(grupo.map(
                lambda t: leer_paso(cliente, t[1], esq, nombre_lat, fila, nombre_lon, columna, variables), tareas))
    except earthdata.FaltanCredenciales:
        raise
    except earthdata.ErrorNASA:
        raise
    except (httpx.HTTPError, KeyError, ValueError, XML.ParseError, ErrorGLDAS) as error:
        raise ErrorGLDAS(f"No se pudo leer GLDAS de la NASA: {type(error).__name__}: {error}") from error
    por_dia: dict[date, dict[str, list[float]]] = {}
    for (dia, _hora), valores in zip((c for c, _ in tareas), leidos):
        destino_dia = por_dia.setdefault(dia, {v: [] for v in variables})
        for destino, (_archivo, factor, *_resto) in variables.items():
            crudo = valores.get(destino)
            if crudo is not None:
                destino_dia[destino].append(crudo * factor)
    return por_dia


# ---------- observaciones ----------

def a_observacion(lote_id: str, dia: date, destino: str, valores: list[float], meta: tuple) -> Observacion:
    _archivo, _factor, (minimo, maximo), unidad, que_es = meta
    base = dict(lote_id=lote_id, fecha=dia, variable=destino, unidad=unidad, fuente="GLDAS",
                resolucion_m=RESOLUCION_M)
    if not valores:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"GLDAS no tiene dato para este día · Respaldo · {NOTA_REGIONAL}")
    valor = round(sum(valores) / len(valores), 4)
    motivos = []
    if not minimo <= valor <= maximo:
        motivos.append(f"Fuera del rango físico ({minimo} a {maximo} {unidad})")
    if len(valores) < PASOS_POR_DIA:
        motivos.append(f"Promedio de solo {len(valores)} de {PASOS_POR_DIA} pasos de 3 h")
    nota_fuente = f"Respaldo · {que_es} del modelo GLDAS Noah de la NASA (GES DISC) · {NOTA_REGIONAL}"
    if motivos:
        return Observacion(**base, valor=valor, calidad="dudosa", nota=f"{' · '.join(motivos)} · {nota_fuente}")
    return Observacion(**base, valor=valor, calidad="buena",
                       nota=f"Promedio de {PASOS_POR_DIA} pasos de 3 h · {nota_fuente}")


def observaciones(lote_id: str, desde: date, hasta: date, por_dia: dict, variables: dict) -> list[Observacion]:
    """Una observación por día y variable del período, aunque la NASA no haya publicado ese día (descartada)."""
    salida = []
    for i in range((hasta - desde).days + 1):
        dia = desde + timedelta(days=i)
        valores_dia = por_dia.get(dia, {})
        for destino, meta in variables.items():
            salida.append(a_observacion(lote_id, dia, destino, valores_dia.get(destino, []), meta))
    return salida


def obtener(lote_id: str, lat: float, lon: float, desde: date, hasta: date, variables: dict,
            cliente: httpx.Client | None = None) -> list[Observacion]:
    por_dia = leer_periodo(lat, lon, desde, hasta, variables, cliente)
    if not por_dia:
        raise ErrorGLDAS(f"La NASA no publicó pasos de GLDAS entre {desde} y {hasta} (llega con ~1 mes de atraso)")
    return observaciones(lote_id, desde, hasta, por_dia, variables)


def obtener_humedad(lote_id: str, lat: float, lon: float, desde: date, hasta: date,
                    cliente: httpx.Client | None = None) -> list[Observacion]:
    return obtener(lote_id, lat, lon, desde, hasta, HUMEDAD, cliente)


def obtener_et(lote_id: str, lat: float, lon: float, desde: date, hasta: date,
               cliente: httpx.Client | None = None) -> list[Observacion]:
    return obtener(lote_id, lat, lon, desde, hasta, ET, cliente)


# ---------- conexión con el núcleo (spec 009) ----------

SATELITES = [
    Satelite("SMAP:GLDAS", lambda lote, desde, hasta: obtener_humedad(lote["id"], lote["lat"], lote["lon"],
                                                                      desde, hasta),
             respaldo_de="SMAP", orden=3),
    Satelite("ET:GLDAS", lambda lote, desde, hasta: obtener_et(lote["id"], lote["lat"], lote["lon"], desde, hasta),
             respaldo_de="ET", orden=3),
]

router = APIRouter(tags=["GLDAS (pruebas internas)"])


def _responder(funcion, lote_id: str, lat: float, lon: float, desde: date, hasta: date) -> list[Observacion]:
    try:
        validar_pedido(lat, lon, desde, hasta)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return funcion(lote_id, lat, lon, desde, hasta)
    except earthdata.FaltanCredenciales as error:
        raise HTTPException(status_code=503, detail=str(error))
    except (ErrorGLDAS, earthdata.ErrorNASA) as error:
        raise HTTPException(status_code=502, detail=str(error))


@router.get("/humedad-suelo/gldas", response_model=list[Observacion])
def humedad_gldas(lote_id: str, lat: float, lon: float, desde: date, hasta: date) -> list[Observacion]:
    return _responder(obtener_humedad, lote_id, lat, lon, desde, hasta)


@router.get("/et/gldas", response_model=list[Observacion])
def et_gldas(lote_id: str, lat: float, lon: float, desde: date, hasta: date) -> list[Observacion]:
    return _responder(obtener_et, lote_id, lat, lon, desde, hasta)
