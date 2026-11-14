"""Conector de evapotranspiración: ET real y potencial de 500 m y 8 días de la NASA, fuente principal de ET (spec 017)."""

import math
import re
import xml.etree.ElementTree as XML
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import httpx
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rotaterra.contrato import Observacion
from rotaterra.fuentes import earthdata
from rotaterra.fuentes.earthdata import FaltanCredenciales
from rotaterra.fuentes.registro import Satelite
from rotaterra.geo import validar_poligono

# Productos en orden de preferencia (spec 017). Todos usan el algoritmo MOD16, la misma grilla y el mismo
# calendario de compuestos, así que para cada compuesto vale el primero de la lista que tenga dato.
# Verificado en CMR: MOD16A2 y MYD16A2 v061 tienen OPeNDAP; VIIRS (VJ116A2, VNP16A2) no está publicado.
PRODUCTOS = {  # producto -> (fuente del contrato, satélite)
    "MOD16A2": ("MODIS", "Terra"),
    "MYD16A2": ("MODIS", "Aqua"),
    "VJ116A2": ("VIIRS", "NOAA-20"),  # continuidad: se usa solo si la NASA lo publica y a MODIS le falta el dato
}
ESCALA = 0.1             # kg/m² = mm; supuesto si el archivo no trae scale_factor
VALIDO_MAX = 32700       # supuesto si el archivo no trae valid_range; de 32761 en adelante es relleno
RELLENO = {32761: "sin clasificar", 32762: "urbano", 32763: "humedal permanente", 32764: "nieve o hielo permanente",
           32765: "suelo desnudo", 32766: "agua", 32767: "sin dato"}
PRINCIPAL = (0, 1)       # supuesto (spec 017): bits 5-7 del QC; 0-1 = algoritmo principal, 2-3 = de respaldo
RESOLUCION_M = 500
DIAS_COMPUESTO = 8
HILOS = 4
MAX_DIAS = 366
UNIDAD = "mm/día"
UMBRAL_BUENA = 60.0      # % de píxeles válidos: mismos umbrales que el NDVI
UMBRAL_DESCARTADA = 20.0
VARIABLES = {"et": "et_mm_dia", "pet": "pet_mm_dia"}

# Grilla sinusoidal (la de MODIS): mosaicos de 2400 × 2400 píxeles de ~463 m
_R = 6371007.181
_MOSAICO = 1111950.5197665
_LADO = 2400
_PIXEL = _MOSAICO / _LADO
_X0, _Y0 = -20015109.354, 10007554.677

# qué capa buscar en cada archivo: el nombre exacto se lee de los metadatos (.dmr) de la NASA
_CAPAS = {
    "et": re.compile(r"(^|_)ET(_500_?m)?$", re.I),
    "pet": re.compile(r"(^|_)PET(_500_?m)?$", re.I),
    "qc": re.compile(r"(^|_)ET_QC(_500_?m)?$", re.I),
}
_RUTAS: dict[str, dict[str, str]] = {}      # producto -> capa -> ruta en el archivo
_ATRIBUTOS: dict[str, dict[str, dict]] = {}  # producto -> capa -> {"escala", "valido_max"}


class ErrorET(Exception):
    """La NASA no respondió, respondió algo ilegible o no tiene ningún dato para el lote."""


def validar_pedido(poligono: dict, desde: date, hasta: date) -> None:
    validar_poligono(poligono)
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise ValueError(f"El rango supera {MAX_DIAS} días")


# ---------- grilla ----------

def celda(lat: float, lon: float) -> tuple[int, int, int, int]:
    """Mosaico (h, v) y píxel (fila, columna) de 500 m que contienen el punto."""
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
        filas.append(fila + (vv - v) * _LADO)
        columnas.append(columna + (hh - h) * _LADO)
    f0, f1 = max(min(filas) - 1, 0), min(max(filas) + 1, _LADO - 1)
    c0, c1 = max(min(columnas) - 1, 0), min(max(columnas) + 1, _LADO - 1)
    if c1 == c0:  # el servidor no devuelve recortes de una sola columna
        c0 = max(c0 - 1, 0) if c1 == _LADO - 1 else c0
        c1 = c0 + 1
    return h, v, f0, f1, c0, c1


def coordenadas(h: int, v: int, f0: int, f1: int, c0: int, c1: int) -> tuple[np.ndarray, np.ndarray]:
    """Latitud y longitud del centro de cada píxel de la ventana (se calculan: no dependen del archivo)."""
    filas, columnas = np.arange(f0, f1 + 1), np.arange(c0, c1 + 1)
    y = _Y0 - v * _MOSAICO - (filas[:, None] + 0.5) * _PIXEL + 0 * columnas[None, :]
    x = _X0 + h * _MOSAICO + (columnas[None, :] + 0.5) * _PIXEL + 0 * filas[:, None]
    lat = np.degrees(y / _R)
    lon = np.degrees(x / (_R * np.cos(np.radians(lat))))
    return lat, lon


# ---------- calendario de compuestos ----------

def inicio_compuesto(nombre_archivo: str) -> date:
    """MOD16A2.A2026009.h12v12... → 2026-01-09."""
    hallado = re.search(r"\.A(\d{4})(\d{3})\.", nombre_archivo)
    return date(int(hallado[1]), 1, 1) + timedelta(days=int(hallado[2]) - 1)


def dias_del_compuesto(inicio: date) -> int:
    """8 días, salvo el último del año, que termina el 31 de diciembre (5 días, o 6 en año bisiesto)."""
    return min(DIAS_COMPUESTO, (date(inicio.year, 12, 31) - inicio).days + 1)


def compuestos(desde: date, hasta: date) -> list[date]:
    """Inicio de cada compuesto de 8 días (días 1, 9, 17, … del año) que se superpone con el período."""
    inicios = []
    for anio in range(desde.year - 1, hasta.year + 1):
        dia = date(anio, 1, 1)
        while dia.year == anio:
            if dia <= hasta and dia + timedelta(days=dias_del_compuesto(dia) - 1) >= desde:
                inicios.append(dia)
            dia += timedelta(days=DIAS_COMPUESTO)
    return inicios


# ---------- lectura por OPeNDAP ----------

def _valor_atributo(nodo, nombre: str) -> list[float] | None:
    for atributo in nodo:
        if atributo.tag.rsplit("}", 1)[-1] == "Attribute" and atributo.get("name") == nombre:
            valores = []
            for valor in atributo:
                for parte in (valor.text or "").replace(",", " ").split():
                    try:
                        valores.append(float(parte))
                    except ValueError:
                        pass
            return valores or None
    return None


def rutas_de_capas(dmr: str) -> tuple[dict[str, str], dict[str, dict]]:
    """Busca en los metadatos DAP4 (.dmr) la ruta de ET, PET y QC, con la escala y el rango válido de cada una."""
    raiz = XML.fromstring(dmr)
    halladas: dict[str, str] = {}
    atributos: dict[str, dict] = {}

    def recorrer(nodo, camino: str) -> None:
        for hijo in nodo:
            etiqueta = hijo.tag.rsplit("}", 1)[-1]
            nombre = hijo.get("name")
            if not nombre or etiqueta in ("Attribute", "Dimension", "Dim", "Map"):
                continue
            ruta = f"{camino}/{nombre}"
            if etiqueta == "Group":
                recorrer(hijo, ruta)
                continue
            plano = nombre.replace(" ", "_")
            for capa, patron in _CAPAS.items():
                if capa not in halladas and patron.search(plano):
                    halladas[capa] = ruta
                    escala = _valor_atributo(hijo, "scale_factor")
                    rango = _valor_atributo(hijo, "valid_range")
                    atributos[capa] = {"escala": escala[0] if escala else ESCALA,
                                       "valido_max": rango[-1] if rango and len(rango) >= 2 else VALIDO_MAX}

    recorrer(raiz, "")
    faltan = set(_CAPAS) - set(halladas)
    if faltan:
        raise ErrorET(f"El archivo no tiene las capas {sorted(faltan)} de evapotranspiración")
    return halladas, atributos


def _plano(ruta: str) -> str:
    return ruta.lstrip("/").replace("%20", " ").replace("_", " ")


def leer_ventana(cliente: httpx.Client, producto: str, url: str,
                 f0: int, f1: int, c0: int, c1: int) -> dict[str, np.ndarray]:
    if producto not in _RUTAS:
        respuesta = cliente.get(f"{url}.dmr")
        respuesta.raise_for_status()
        _RUTAS[producto], _ATRIBUTOS[producto] = rutas_de_capas(respuesta.text)
    rutas = _RUTAS[producto]
    # en DAP4 los espacios de un nombre se escriben %20 dentro de la expresión
    expresion = ";".join(f"{ruta.replace(' ', '%20')}[{f0}:1:{f1}][{c0}:1:{c1}]" for ruta in rutas.values())
    crudo = {_plano(nombre): filas for nombre, filas in earthdata.leer_csv(cliente, url, expresion).items()}
    datos = {}
    for capa, ruta in rutas.items():
        filas = crudo.get(_plano(ruta))
        if filas is None:
            raise ErrorET(f"OPeNDAP no devolvió '{capa}' ({ruta}) para {url}")
        datos[capa] = np.array([[np.nan if v is None else v for v in fila] for fila in filas], dtype="float64")
    return datos


# ---------- resumen del lote ----------

def _motivo_relleno(crudo: np.ndarray) -> str:
    codigos = [int(c) for c in crudo[np.isfinite(crudo)] if int(c) in RELLENO]
    if not codigos:
        return "sin dato"
    mas_comun = max(set(codigos), key=codigos.count)
    return f"código de relleno {mas_comun} ({RELLENO[mas_comun]})"


def resumir(lote_id: str, poligono: dict, datos: dict[str, np.ndarray], inicio: date,
            producto: str = "MOD16A2", atributos: dict[str, dict] | None = None) -> list[Observacion]:
    """ET y PET del lote (promedio diario) para un compuesto de 8 días."""
    from shapely.geometry import Point, shape

    fuente, satelite = PRODUCTOS.get(producto, ("MODIS", "?"))
    atributos = atributos or {}
    lote = shape(poligono)
    dentro = np.array([[lote.contains(Point(lon, lat)) for lat, lon in zip(fila_lat, fila_lon)]
                       for fila_lat, fila_lon in zip(datos["lat"], datos["lon"])])
    aviso = ""
    if not dentro.any():  # lote más chico que un píxel de ~21 ha: se usa el píxel que contiene su centro
        centro = lote.centroid
        distancia = (datos["lat"] - centro.y) ** 2 + (datos["lon"] - centro.x) ** 2
        dentro = distancia == np.nanmin(distancia)
        aviso = "lote menor a un píxel: se usa el píxel del centro · "
    dias = dias_del_compuesto(inicio)
    fin = inicio + timedelta(days=dias - 1)
    algoritmo = (np.nan_to_num(datos["qc"], nan=255).astype(int) >> 5) & 0b111
    total = int(dentro.sum())
    observaciones = []
    for capa, variable in VARIABLES.items():
        escala = atributos.get(capa, {}).get("escala", ESCALA)
        valido_max = atributos.get(capa, {}).get("valido_max", VALIDO_MAX)
        crudo = datos[capa]
        validos = dentro & np.isfinite(crudo) & (crudo <= valido_max) & (crudo < min(RELLENO))
        n_validos = int(validos.sum())
        pct = 100.0 * n_validos / total
        detalle = (f"{aviso}{producto} ({fuente} {satelite}) · fecha = inicio del compuesto de {dias} días "
                   f"({inicio} al {fin})")
        base = dict(lote_id=lote_id, fecha=inicio, variable=variable, unidad=UNIDAD, fuente=fuente,
                    resolucion_m=RESOLUCION_M)
        if pct < UMBRAL_DESCARTADA:
            observaciones.append(Observacion(**base, valor=None, calidad="descartada", nota=(
                f"Sin dato: {_motivo_relleno(crudo[dentro])} · {detalle} · {total} píxeles de 500 m · "
                f"válidos {pct:.0f}%")))
            continue
        suma = float(np.mean(crudo[validos])) * escala
        pct_principal = 100.0 * int((validos & np.isin(algoritmo, PRINCIPAL)).sum()) / n_validos
        calidad = "buena" if pct >= UMBRAL_BUENA and pct_principal >= 50 else "dudosa"
        observaciones.append(Observacion(**base, valor=round(suma / dias, 2), calidad=calidad, nota=(
            f"{detalle} · promedio diario = suma {suma:.1f} mm / {dias} días · {total} píxeles de 500 m · "
            f"válidos {pct:.0f}% · algoritmo principal {pct_principal:.0f}% · escala {escala:g}")))
    return observaciones


# ---------- pedido completo ----------

def _granulos(cliente: httpx.Client, producto: str, poligono: dict, desde: date, hasta: date,
              mosaico: str, pendientes: set[date]) -> list[tuple[date, str]]:
    from shapely.geometry import shape

    coleccion = earthdata.coleccion_vigente(cliente, producto)
    if coleccion is None:
        return []
    elegidos: dict[date, str] = {}
    for nombre, url in earthdata.archivos(cliente, coleccion, desde - timedelta(days=DIAS_COMPUESTO - 1), hasta,
                                          caja=shape(poligono).bounds):
        if mosaico in nombre:
            inicio = inicio_compuesto(nombre)
            if inicio in pendientes and inicio not in elegidos:  # un archivo por compuesto
                elegidos[inicio] = url
    return sorted(elegidos.items())


def obtener_et(lote_id: str, poligono: dict, desde: date, hasta: date,
               cliente: httpx.Client | None = None, hilos: int = HILOS) -> list[Observacion]:
    """ET real y potencial del lote por compuesto de 8 días; cada compuesto sale del primer producto con dato."""
    validar_pedido(poligono, desde, hasta)
    h, v, f0, f1, c0, c1 = ventana(poligono)
    lat, lon = coordenadas(h, v, f0, f1, c0, c1)
    mosaico = f".h{h:02d}v{v:02d}."
    pendientes = set(compuestos(desde, hasta))
    elegidas: dict[date, list[Observacion]] = {}
    consultados = []
    try:
        cliente = earthdata.cliente_autorizado(cliente)
        for producto in PRODUCTOS:
            if not pendientes:
                break
            granulos = _granulos(cliente, producto, poligono, desde, hasta, mosaico, pendientes)
            consultados.append(f"{producto}: {len(granulos)}")
            if not granulos:
                continue
            with ThreadPoolExecutor(max_workers=hilos) as grupo:
                ventanas = list(grupo.map(lambda g: leer_ventana(cliente, producto, g[1], f0, f1, c0, c1), granulos))
            for (inicio, _), datos in zip(granulos, ventanas):
                obs = resumir(lote_id, poligono, {**datos, "lat": lat, "lon": lon}, inicio, producto,
                              _ATRIBUTOS.get(producto))
                if any(o.variable == VARIABLES["et"] and o.valor is not None for o in obs):
                    elegidas[inicio] = obs
                    pendientes.discard(inicio)
                else:
                    elegidas.setdefault(inicio, obs)  # descartado: queda si ningún otro producto lo cubre
    except FaltanCredenciales:
        raise
    except (httpx.HTTPError, KeyError, ValueError, XML.ParseError, earthdata.ErrorNASA) as error:
        raise ErrorET(f"No se pudo obtener la evapotranspiración: {error}") from error
    if not elegidas:
        raise ErrorET(f"CMR no tiene compuestos de ET con OPeNDAP para el lote (h{h:02d}v{v:02d}) del {desde} al "
                      f"{hasta} · archivos por producto: {', '.join(consultados)}")
    salida = [o for inicio in sorted(elegidas) for o in elegidas[inicio]]
    if all(o.valor is None for o in salida if o.variable == VARIABLES["et"]):
        motivos = sorted({o.nota.split(" · ")[0] for o in salida if o.variable == VARIABLES["et"]})
        raise ErrorET(f"Ninguno de los {len(elegidas)} compuestos trae ET válida para el lote: {'; '.join(motivos)}")
    return salida


# ---------- conexión con el núcleo (spec 009) ----------

# principal de ET; si falla, entran ET:ECOSTRESS (orden 1) y ET:FAO56 (orden 2), cada uno en su rama
SATELITES = [Satelite("ET", lambda lote, desde, hasta: obtener_et(lote["id"], lote["poligono"], desde, hasta))]

router = APIRouter(tags=["ET (pruebas internas)"])


class PedidoET(BaseModel):
    lote_id: str
    poligono: dict
    desde: date
    hasta: date


@router.post("/evapotranspiracion", response_model=list[Observacion])
def evapotranspiracion(pedido: PedidoET) -> list[Observacion]:
    try:
        validar_pedido(pedido.poligono, pedido.desde, pedido.hasta)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener_et(pedido.lote_id, pedido.poligono, pedido.desde, pedido.hasta)
    except FaltanCredenciales as error:
        raise HTTPException(status_code=503, detail=str(error))
    except ErrorET as error:
        raise HTTPException(status_code=502, detail=str(error))
