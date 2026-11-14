"""Conector SMAP L4: humedad del suelo diaria (spec 003).

Dos caminos al mismo producto de la NASA (SPL4SMGP):
- directo: CMR + OPeNDAP de la NASA, un píxel por archivo de 3 h. Rápido, sin fila de espera (principal).
- AppEEARS: la NASA arma el pedido y avisa cuando está; puede tardar de 5 a 40 minutos (respaldo, spec 005).
"""

import csv
import io
import math
import os
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import httpx

from rotaterra.contrato import Observacion
from rotaterra.fuentes.registro import Pendiente, Satelite
from fastapi import APIRouter, HTTPException

URL_APPEEARS = "https://appeears.earthdatacloud.nasa.gov/api"
PRODUCTO = "SPL4SMGP"
RESOLUCION_M = 9000
VALOR_RELLENO = -9999
MAX_DIAS = 366
VALORES_POR_DIA = 8  # un valor cada 3 horas (referencia de colección completa)
PASADAS_DIARIAS_REDUCIDAS = int(os.environ.get("SMAP_PASADAS_POR_DIA", "2"))
RANGO_FISICO = (0.0, 0.6)
NOTA_REGIONAL = "celda de 9 km: contexto regional, no dato del lote"

# capa SMAP (sufijo) -> variable Rotaterra
CAPAS = {
    "sm_surface": "humedad_superficial",
    "sm_rootzone": "humedad_zona_raiz",
}


class ErrorSMAP(Exception):
    """AppEEARS no respondió, rechazó el pedido o devolvió algo ilegible."""


class DemoraSMAP(ErrorSMAP, Pendiente):
    """AppEEARS no terminó el pedido dentro del tiempo máximo."""


class FaltanCredenciales(Exception):
    """No están EARTHDATA_USERNAME / EARTHDATA_PASSWORD."""


def validar_pedido(lat: float, lon: float, desde: date, hasta: date) -> None:
    if not -90 <= lat <= 90:
        raise ValueError(f"Latitud fuera de rango: {lat}")
    if not -180 <= lon <= 180:
        raise ValueError(f"Longitud fuera de rango: {lon}")
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise ValueError(f"El rango supera {MAX_DIAS} días")


# ---------- diálogo con AppEEARS ----------

def iniciar_sesion(cliente: httpx.Client) -> str:
    usuario = os.environ.get("EARTHDATA_USERNAME")
    clave = os.environ.get("EARTHDATA_PASSWORD")
    if not usuario or not clave:
        raise FaltanCredenciales("Faltan EARTHDATA_USERNAME y EARTHDATA_PASSWORD")
    respuesta = cliente.post(f"{URL_APPEEARS}/login", auth=(usuario, clave))
    if respuesta.status_code in (401, 403):
        raise ErrorSMAP("AppEEARS rechazó el usuario o la contraseña de Earthdata")
    respuesta.raise_for_status()
    return respuesta.json()["token"]


def version_vigente(cliente: httpx.Client) -> str:
    """Devuelve, por ejemplo, 'SPL4SMGP.008': la versión más nueva que ofrece AppEEARS."""
    productos = cliente.get(f"{URL_APPEEARS}/product").json()
    versiones = sorted(p["ProductAndVersion"] for p in productos if p.get("Product") == PRODUCTO)
    if not versiones:
        raise ErrorSMAP(f"AppEEARS no ofrece {PRODUCTO}")
    return versiones[-1]


def nombres_de_capas(cliente: httpx.Client, producto: str) -> dict[str, str]:
    """Sufijo ('sm_surface') -> nombre completo de la capa en AppEEARS."""
    capas = cliente.get(f"{URL_APPEEARS}/product/{producto}").json()
    elegidas = {}
    for sufijo in CAPAS:
        coincidencias = [nombre for nombre in capas if nombre.endswith(f"_{sufijo}") or nombre == sufijo]
        if len(coincidencias) != 1:
            raise ErrorSMAP(f"No se encontró una única capa '{sufijo}' en {producto}: {coincidencias}")
        elegidas[sufijo] = coincidencias[0]
    return elegidas


ESTADOS_DESCARTABLES = {"error", "expired", "deleted"}


def nombre_pedido(lote_id: str, desde: date, hasta: date) -> str:
    return f"rotaterra-{lote_id}-{desde:%Y%m%d}-{hasta:%Y%m%d}"


def buscar_pedido_existente(cliente: httpx.Client, nombre: str, lat: float, lon: float) -> str | None:
    """Reusa un pedido del mismo lote, punto y fecha de inicio que ya esté en la fila o terminado.

    Se compara sin la fecha final: de una noche a la otra 'hasta' avanza un día, pero el pedido
    viejo sigue sirviendo (el día que le falta se baja en la corrida siguiente, por el solape).
    """
    prefijo = nombre.rsplit("-", 1)[0] + "-"
    pedidos = cliente.get(f"{URL_APPEEARS}/task").json()
    candidatos = sorted((p for p in pedidos if str(p.get("task_name", "")).startswith(prefijo)
                         and p.get("status") not in ESTADOS_DESCARTABLES),
                        key=lambda p: p.get("created", ""), reverse=True)
    for pedido in candidatos:
        detalle = cliente.get(f"{URL_APPEEARS}/task/{pedido['task_id']}").json()
        puntos = (detalle.get("params") or {}).get("coordinates") or []
        if any(abs(float(c["latitude"]) - lat) < 1e-4 and abs(float(c["longitude"]) - lon) < 1e-4
               for c in puntos):
            return pedido["task_id"]
    return None


def crear_pedido(cliente: httpx.Client, producto: str, capas: dict[str, str], lote_id: str,
                 lat: float, lon: float, desde: date, hasta: date) -> str:
    cuerpo = {
        "task_type": "point",
        "task_name": nombre_pedido(lote_id, desde, hasta),
        "params": {
            "dates": [{"startDate": desde.strftime("%m-%d-%Y"), "endDate": hasta.strftime("%m-%d-%Y")}],
            "layers": [{"product": producto, "layer": nombre} for nombre in capas.values()],
            "coordinates": [{"id": lote_id, "latitude": lat, "longitude": lon}],
        },
    }
    respuesta = cliente.post(f"{URL_APPEEARS}/task", json=cuerpo)
    respuesta.raise_for_status()
    return respuesta.json()["task_id"]


def esperar_pedido(cliente: httpx.Client, task_id: str, espera_max_s: float, intervalo_s: float,
                   dormir=time.sleep) -> None:
    transcurrido = 0.0
    while True:
        estado = cliente.get(f"{URL_APPEEARS}/task/{task_id}").json().get("status")
        if estado == "done":
            return
        if estado == "error":
            raise ErrorSMAP(f"AppEEARS no pudo procesar el pedido {task_id}")
        if transcurrido >= espera_max_s:
            raise DemoraSMAP(f"AppEEARS no terminó el pedido {task_id} en {espera_max_s:.0f} s (estado: {estado})")
        dormir(intervalo_s)
        transcurrido += intervalo_s


def bajar_resultados(cliente: httpx.Client, task_id: str) -> str:
    archivos = cliente.get(f"{URL_APPEEARS}/bundle/{task_id}").json()["files"]
    csvs = [a for a in archivos if a["file_name"].endswith("results.csv")]
    if not csvs:
        raise ErrorSMAP(f"El pedido {task_id} no trajo un CSV de resultados")
    respuesta = cliente.get(f"{URL_APPEEARS}/bundle/{task_id}/{csvs[0]['file_id']}", follow_redirects=True)
    respuesta.raise_for_status()
    return respuesta.text


# ---------- conversión al contrato (testeable sin internet) ----------

def leer_csv(texto: str, capas: dict[str, str]) -> dict[tuple[date, str], list[float | None]]:
    """Agrupa los valores de 3 h por (día, variable). None = relleno."""
    lector = csv.DictReader(io.StringIO(texto))
    columnas = {}
    for sufijo, nombre in capas.items():
        candidatas = [c for c in lector.fieldnames or [] if c.endswith(nombre)]
        if not candidatas:
            raise ErrorSMAP(f"El CSV de AppEEARS no tiene la columna de '{nombre}'")
        columnas[sufijo] = candidatas[0]

    valores = defaultdict(list)
    for fila in lector:
        dia = date.fromisoformat(fila["Date"][:10])
        for sufijo, columna in columnas.items():
            crudo = (fila.get(columna) or "").strip()
            valor = float(crudo) if crudo else None
            valores[(dia, CAPAS[sufijo])].append(None if valor is None or valor <= VALOR_RELLENO else valor)
    return valores


def a_observacion(lote_id: str, dia: date, variable: str, crudos: list[float | None],
                  via: str = "AppEEARS", esperados: int | None = None) -> Observacion:
    base = dict(lote_id=lote_id, fecha=dia, variable=variable, unidad="m³/m³",
                fuente="SMAP", resolucion_m=RESOLUCION_M)
    validos = [v for v in crudos if v is not None]
    if not validos:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"SMAP no tiene dato para este día · {NOTA_REGIONAL} · vía {via}")
    valor = round(sum(validos) / len(validos), 4)
    minimo, maximo = RANGO_FISICO
    motivos = []
    if not minimo <= valor <= maximo:
        motivos.append(f"Fuera del rango físico ({minimo} a {maximo} m³/m³)")
    esperados_num = esperados if esperados is not None else (VALORES_POR_DIA if via == "AppEEARS" else len(crudos))
    if esperados_num and len(validos) < esperados_num:
        motivos.append(f"Promedio de solo {len(validos)} de {esperados_num} valores de 3 h")
    if motivos:
        return Observacion(**base, valor=valor, calidad="dudosa",
                           nota=f"{' · '.join(motivos)} · {NOTA_REGIONAL} · vía {via}")
    return Observacion(**base, valor=valor, calidad="buena",
                       nota=f"Promedio de {len(validos)} valores de 3 h · {NOTA_REGIONAL} · vía {via}")


def por_dia(lote_id: str, desde: date, hasta: date, valores: dict, via: str,
            esperados: int | None = None) -> list[Observacion]:
    """Una observación por día y variable, aunque la NASA no haya mandado nada ese día (queda descartada)."""
    dias = [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]
    return [a_observacion(lote_id, dia, variable, valores.get((dia, variable), []), via, esperados=esperados)
            for dia in dias for variable in sorted(CAPAS.values())]


def obtener_humedad(lote_id: str, lat: float, lon: float, desde: date, hasta: date,
                    cliente: httpx.Client | None = None, espera_max_s: float = 1200,
                    intervalo_s: float = 20, dormir=time.sleep) -> list[Observacion]:
    """Pide a AppEEARS la humedad SMAP del punto y la devuelve por día en el contrato común."""
    validar_pedido(lat, lon, desde, hasta)
    cliente = cliente or httpx.Client(timeout=120)
    try:
        token = iniciar_sesion(cliente)
        cliente.headers["Authorization"] = f"Bearer {token}"
        producto = version_vigente(cliente)
        capas = nombres_de_capas(cliente, producto)
        task_id = (buscar_pedido_existente(cliente, nombre_pedido(lote_id, desde, hasta), lat, lon)
                   or crear_pedido(cliente, producto, capas, lote_id, lat, lon, desde, hasta))
        esperar_pedido(cliente, task_id, espera_max_s, intervalo_s, dormir)
        valores = leer_csv(bajar_resultados(cliente, task_id), capas)
    except (httpx.HTTPError, KeyError, ValueError) as error:
        raise ErrorSMAP(f"No se pudo obtener la humedad de SMAP: {error}") from error

    return por_dia(lote_id, desde, hasta, valores, "AppEEARS")


# ---------- camino directo: CMR + OPeNDAP de la NASA ----------

URL_CMR = "https://cmr.earthdata.nasa.gov/search"
URL_TOKEN = "https://urs.earthdata.nasa.gov/api/users/find_or_create_token"
PROVEEDOR = "NSIDC_CPRD"
HILOS = 8

# Grilla EASE-Grid 2.0 global de 9 km (EPSG:6933), la misma de los archivos SMAP L4
_A, _E2 = 6378137.0, 0.0066943799901413165
_E = math.sqrt(_E2)
_K0 = math.cos(math.radians(30)) / math.sqrt(1 - _E2 * math.sin(math.radians(30)) ** 2)
_X0, _Y0, _CELDA = -17363027.2924805, 7310037.17138672, 9008.055210146
FILAS, COLUMNAS = 1624, 3856


def celda_ease2(lat: float, lon: float) -> tuple[int, int]:
    """Fila y columna de la celda de 9 km que contiene el punto."""
    s = math.sin(math.radians(lat))
    q = (1 - _E2) * (s / (1 - _E2 * s * s) - (1 / (2 * _E)) * math.log((1 - _E * s) / (1 + _E * s)))
    x, y = _A * _K0 * math.radians(lon), _A * q / (2 * _K0)
    fila, columna = round((_Y0 - y) / _CELDA), round((x - _X0) / _CELDA)
    return min(max(fila, 0), FILAS - 1), min(max(columna, 0), COLUMNAS - 2)


def token_earthdata(cliente: httpx.Client) -> str:
    usuario = os.environ.get("EARTHDATA_USERNAME")
    clave = os.environ.get("EARTHDATA_PASSWORD")
    if not usuario or not clave:
        raise FaltanCredenciales("Faltan EARTHDATA_USERNAME y EARTHDATA_PASSWORD")
    respuesta = cliente.post(URL_TOKEN, auth=(usuario, clave))
    if respuesta.status_code in (401, 403):
        raise ErrorSMAP("Earthdata rechazó el usuario o la contraseña")
    respuesta.raise_for_status()
    return respuesta.json()["access_token"]


def coleccion_vigente(cliente: httpx.Client) -> str:
    """Id de CMR de la versión más nueva de SPL4SMGP."""
    items = cliente.get(f"{URL_CMR}/collections.umm_json",
                        params={"short_name": PRODUCTO, "provider": PROVEEDOR, "page_size": 20}).json()["items"]
    if not items:
        raise ErrorSMAP(f"CMR no tiene la colección {PRODUCTO}")
    return max(items, key=lambda i: i["umm"].get("Version", ""))["meta"]["concept-id"]


_FECHA_ARCHIVO = re.compile(r"_(\d{8})T\d{6}_")


_CACHE_PIXEL_SMAP: dict[tuple[str, int, int], dict[str, float | None]] = {}


def limpiar_cache() -> None:
    """Limpia el caché de píxeles OPeNDAP en memoria."""
    _CACHE_PIXEL_SMAP.clear()


def archivos_por_dia(cliente: httpx.Client, coleccion: str, desde: date, hasta: date,
                     pasadas_por_dia: int | None = None) -> dict[date, list[str]]:
    """URL OPeNDAP de cada archivo de 3 h, agrupadas por el día (UTC) de su hora central.
    Por defecto muestrea 2 pasadas homogéneas diarias para máxima velocidad y eficiencia."""
    params = {"collection_concept_id": coleccion, "page_size": 2000, "sort_key": "start_date",
              "temporal": f"{desde.isoformat()}T00:00:00Z,{hasta.isoformat()}T23:59:59Z"}
    por_dia_ = defaultdict(list)
    encabezados = {}
    limite_pasadas = pasadas_por_dia if pasadas_por_dia is not None else PASADAS_DIARIAS_REDUCIDAS

    def _filtrar_pasadas(brutos: dict[date, list[str]]) -> dict[date, list[str]]:
        if not limite_pasadas:
            return brutos
        reducido = defaultdict(list)
        for d, urls in brutos.items():
            if len(urls) > limite_pasadas:
                paso = len(urls) // limite_pasadas
                reducido[d] = [urls[i * paso] for i in range(limite_pasadas)]
            else:
                reducido[d] = urls
        return reducido

    while True:
        respuesta = cliente.get(f"{URL_CMR}/granules.umm_json", params=params, headers=encabezados)
        respuesta.raise_for_status()
        items = respuesta.json()["items"]
        for item in items:
            hallado = _FECHA_ARCHIVO.search(item["umm"]["GranuleUR"])
            urls = [u["URL"] for u in item["umm"].get("RelatedUrls", []) if "opendap" in u["URL"].lower()]
            if hallado and urls:
                dia = date(int(hallado[1][:4]), int(hallado[1][4:6]), int(hallado[1][6:]))
                if desde <= dia <= hasta:
                    por_dia_[dia].append(urls[0])
        siguiente = respuesta.headers.get("CMR-Search-After")
        if not siguiente or len(items) < params["page_size"]:
            return _filtrar_pasadas(por_dia_)
        encabezados = {"CMR-Search-After": siguiente}


def leer_pixel(cliente: httpx.Client, url: str, fila: int, columna: int) -> dict[str, float | None]:
    """Humedad de un píxel en un archivo de 3 h. Devuelve {'sm_surface': v, 'sm_rootzone': v}."""
    clave = (url, fila, columna)
    if clave in _CACHE_PIXEL_SMAP:
        return _CACHE_PIXEL_SMAP[clave]

    # El servidor OPeNDAP devuelve vacío si se pide un único valor: se piden 2 columnas y se usa la primera.
    ce = ";".join(f"/Geophysical_Data/{capa}[{fila}][{columna}:1:{columna + 1}]" for capa in CAPAS)
    respuesta = cliente.get(f"{url}.dap.csv", params={"dap4.ce": ce})
    respuesta.raise_for_status()
    valores = {}
    for linea in respuesta.text.splitlines():
        for capa in CAPAS:
            if linea.startswith(f"/Geophysical_Data/{capa}["):
                crudo = linea.split(",")[1].strip()
                valor = float(crudo) if crudo else None
                valores[capa] = None if valor is None or valor <= VALOR_RELLENO else valor
    if set(valores) != set(CAPAS):
        raise ErrorSMAP(f"Respuesta OPeNDAP ilegible para {url}")
    _CACHE_PIXEL_SMAP[clave] = valores
    return valores


def obtener_humedad_directo(lote_id: str, lat: float, lon: float, desde: date, hasta: date,
                            cliente: httpx.Client | None = None, hilos: int = HILOS,
                            pasadas_por_dia: int | None = None) -> list[Observacion]:
    """Humedad SMAP del punto leída directo de los archivos de la NASA, por día, en el contrato común."""
    validar_pedido(lat, lon, desde, hasta)
    cliente = cliente or httpx.Client(timeout=120, follow_redirects=True)
    fila, columna = celda_ease2(lat, lon)
    try:
        cliente.headers["Authorization"] = f"Bearer {token_earthdata(cliente)}"
        archivos = archivos_por_dia(cliente, coleccion_vigente(cliente), desde, hasta, pasadas_por_dia=pasadas_por_dia)
        tareas = [(dia, url) for dia, urls in sorted(archivos.items()) for url in urls]
        with ThreadPoolExecutor(max_workers=hilos) as grupo:
            leidos = list(grupo.map(lambda t: (t[0], leer_pixel(cliente, t[1], fila, columna)), tareas))
    except (httpx.HTTPError, KeyError, ValueError) as error:
        raise ErrorSMAP(f"No se pudo leer SMAP directo de la NASA: {error}") from error

    valores = defaultdict(list)
    for dia, pixel in leidos:
        for capa, variable in CAPAS.items():
            valores[(dia, variable)].append(pixel[capa])
    esperados_dia = pasadas_por_dia if pasadas_por_dia is not None else PASADAS_DIARIAS_REDUCIDAS
    return por_dia(lote_id, desde, hasta, valores, "NASA directo", esperados=esperados_dia)


# ---------- conexión con el núcleo (spec 009) ----------

ESPERA_APPEEARS_MIN = float(os.environ.get("SMAP_ESPERA_MIN", 10))

SATELITES = [
    Satelite("SMAP", lambda lote, desde, hasta: obtener_humedad_directo(lote["id"], lote["lat"], lote["lon"],
                                                                         desde, hasta)),
    # mismo producto pedido a AppEEARS: entra solo si el camino directo falla (spec 005)
    Satelite("SMAP:AppEEARS", lambda lote, desde, hasta: obtener_humedad(lote["id"], lote["lat"], lote["lon"],
                                                                          desde, hasta,
                                                                          espera_max_s=ESPERA_APPEEARS_MIN * 60),
             respaldo_de="SMAP"),
]

router = APIRouter(tags=["SMAP (pruebas internas)"])


@router.get("/humedad-suelo", response_model=list[Observacion])
def humedad_suelo(lote_id: str, lat: float, lon: float, desde: date, hasta: date) -> list[Observacion]:
    try:
        validar_pedido(lat, lon, desde, hasta)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener_humedad_directo(lote_id, lat, lon, desde, hasta)
    except FaltanCredenciales as error:
        raise HTTPException(status_code=503, detail=str(error))
    except ErrorSMAP as error:
        raise HTTPException(status_code=502, detail=str(error))
