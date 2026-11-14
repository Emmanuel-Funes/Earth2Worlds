"""Conector GRACE-FO: napa y agua profunda de la región (spec 026).

Principal: indicadores de sequía GRACE-DA de la NASA (GRACEDADM_CLSM025GL_7D, Goddard), un percentil
semanal de agua subterránea, de humedad en la zona de raíces y de humedad superficial, en una grilla
de 0,25°. Respaldo: anomalía mensual del agua total de los mascons de JPL (TELLUS_GRAC-GRFO_MASCON_CRI).
Las dos se leen por OPeNDAP de la NASA, solo en el píxel del centro del lote. Es un dato REGIONAL:
GRACE-FO mide la gravedad con una resolución real de unos 300 km.
"""

import math
import re
import tempfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException

from rotaterra.contrato import Observacion
from rotaterra.fuentes import earthdata
from rotaterra.fuentes.registro import Satelite

PRODUCTO = "GRACEDADM_CLSM025GL_7D"
PRODUCTO_MASCON = "TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4"
RESOLUCION_M = 25000
RESOLUCION_MASCON_M = 55000
MAX_DIAS = 366
HILOS = 6
# variable del archivo -> (variable del contrato, qué es)
VARIABLES = {
    "gws_inst": ("napa_percentil", "agua subterránea (napa)"),
    "rtzsm_inst": ("humedad_raices_percentil", "humedad de la zona de raíces"),
    "sfsm_inst": ("humedad_superficial_percentil", "humedad superficial"),
}
VARIABLE_MASCON = "lwe_thickness"
CARPETA_MASCON = Path(tempfile.gettempdir()) / "rotaterra-grace-mascon"
# escala de los mapas de sequía GRACE de la NASA; el corte de 70 es un supuesto nuestro (spec 026 §5)
CATEGORIAS = [(2, "sequía excepcional"), (5, "sequía extrema"), (10, "sequía severa"), (20, "sequía moderada"),
              (30, "anormalmente seco"), (70, "normal"), (100, "más húmedo que lo normal")]
REGIONAL = "dato REGIONAL, no del lote: GRACE-FO mide la gravedad con una resolución real de unos 300 km"
NOTA_DA = (f"GRACE-DA de la NASA ({PRODUCTO}), píxel de 0,25° · percentil frente a la misma semana de 1948 a 2014 "
           f"(50 = normal) · {REGIONAL}")
NOTA_MASCON = (f"Respaldo de GRACE-DA · mascons de JPL ({PRODUCTO_MASCON}), píxel de 0,5° · anomalía del agua total "
               f"(napa + suelo + lagunas) frente al promedio 2004-2009, en cm de agua · {REGIONAL}")
_FECHA = re.compile(r"\.A(\d{8})\.")
_ESQUEMA: dict[str, dict] = {}  # colección -> dimensiones, coordenadas y unidades del tiempo


class ErrorGRACE(Exception):
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


def categoria(percentil: float) -> str:
    return next(nombre for tope, nombre in CATEGORIAS if percentil <= tope)


def lunes(desde: date, hasta: date) -> list[date]:
    """Los lunes del período: GRACE-DA publica un dato por semana, con fecha del lunes."""
    primero = desde + timedelta(days=(7 - desde.weekday()) % 7)
    return [primero + timedelta(weeks=i) for i in range((hasta - primero).days // 7 + 1)] if primero <= hasta else []


# ---------- metadatos del archivo (DAP4 .dmr) ----------

def esquema(dmr: str) -> dict:
    """Dimensiones de cada variable, tamaño de cada dimensión y unidades del tiempo, leídos del .dmr."""
    raiz = ET.fromstring(dmr)
    tamanos, variables, unidades = {}, {}, {}
    for nodo in raiz.iter():
        etiqueta = nodo.tag.rsplit("}", 1)[-1]
        if etiqueta == "Dimension" and nodo.get("name"):
            tamanos[nodo.get("name").lstrip("/")] = int(nodo.get("size"))
        elif nodo.get("name") and any(h.tag.rsplit("}", 1)[-1] == "Dim" for h in nodo):
            nombre = nodo.get("name")
            variables[nombre] = [h.get("name").lstrip("/").rsplit("/", 1)[-1] for h in nodo
                                 if h.tag.rsplit("}", 1)[-1] == "Dim"]
            for atributo in nodo:
                if atributo.tag.rsplit("}", 1)[-1] == "Attribute" and atributo.get("name") == "units":
                    valor = next((v.text for v in atributo.iter() if v.tag.rsplit("}", 1)[-1] == "Value"), None)
                    unidades[nombre] = valor or ""
    return {"tamanos": tamanos, "variables": variables, "unidades": unidades}


def preparar_esquema(cliente: httpx.Client, coleccion_id: str, url: str) -> dict:
    if coleccion_id not in _ESQUEMA:
        respuesta = cliente.get(f"{url}.dmr")
        if respuesta.status_code in (401, 403):
            raise earthdata.ErrorNASA("La NASA negó el acceso a los metadatos del archivo GRACE")
        respuesta.raise_for_status()
        _ESQUEMA[coleccion_id] = esquema(respuesta.text)
    return _ESQUEMA[coleccion_id]


def nombre_coordenada(esq: dict, opciones: tuple[str, ...]) -> str:
    nombre = next((n for n in opciones if n in esq["variables"]), None)
    if nombre is None:
        raise ErrorGRACE(f"El archivo no tiene ninguna de las coordenadas {opciones}")
    return nombre


def indice_mas_cercano(valores: list[float], buscado: float) -> int:
    return min(range(len(valores)), key=lambda i: abs(valores[i] - buscado))


def leer_vector(cliente: httpx.Client, url: str, nombre: str) -> list[float]:
    """Una coordenada entera (latitud, longitud o tiempo): son vectores chicos."""
    crudo = earthdata.leer_csv(cliente, url, nombre)
    filas = crudo.get(nombre)
    valores = [v for fila in (filas or []) for v in fila if v is not None]
    if not valores:
        raise ErrorGRACE(f"OPeNDAP no devolvió la coordenada '{nombre}' de {url}")
    return valores


def celda(cliente: httpx.Client, url: str, esq: dict, lat: float, lon: float) -> tuple[str, int, str, int]:
    """Nombre e índice de la latitud y la longitud del píxel que contiene el punto."""
    nombre_lat = nombre_coordenada(esq, ("lat", "latitude"))
    nombre_lon = nombre_coordenada(esq, ("lon", "longitude"))
    lats, lons = leer_vector(cliente, url, nombre_lat), leer_vector(cliente, url, nombre_lon)
    buscada = lon % 360 if max(lons) > 180 else lon  # los mascons usan longitudes de 0 a 360
    return nombre_lat, indice_mas_cercano(lats, lat), nombre_lon, indice_mas_cercano(lons, buscada)


def expresion(variable: str, esq: dict, indices: dict[str, tuple[int, int]]) -> str:
    """Recorte OPeNDAP. La última dimensión pide 2 celdas: la NASA devuelve vacío si se pide un solo valor."""
    dims = esq["variables"].get(variable)
    if not dims:
        raise ErrorGRACE(f"El archivo no tiene la variable '{variable}'")
    partes = []
    for posicion, dim in enumerate(dims):
        inicio, fin = indices.get(dim, (0, 0))
        if posicion == len(dims) - 1:
            tamano = esq["tamanos"].get(dim, fin + 2)
            inicio = min(inicio, tamano - 2)
            fin = inicio + 1
        partes.append(f"[{inicio}:1:{fin}]")
    return variable + "".join(partes)


def _limpio(valor: float | None) -> float | None:
    if valor is None or math.isnan(valor) or valor <= -9000 or abs(valor) > 1e5:  # relleno (-9999, 9.96e36)
        return None
    return valor


# ---------- principal: GRACE-DA semanal ----------

def archivos_semanales(cliente: httpx.Client, coleccion_id: str, desde: date, hasta: date) -> dict[date, str]:
    semanas = {}
    for nombre, url in earthdata.archivos(cliente, coleccion_id, desde, hasta):
        hallado = _FECHA.search(nombre)
        if hallado:
            t = hallado[1]
            dia = date(int(t[:4]), int(t[4:6]), int(t[6:]))
            if desde <= dia <= hasta:
                semanas[dia] = url
    return semanas


def ultima_semana(cliente: httpx.Client, coleccion_id: str) -> date | None:
    """La semana más nueva que publicó la NASA (para explicar el atraso)."""
    respuesta = cliente.get(f"{earthdata.URL_CMR}/granules.umm_json",
                            params={"collection_concept_id": coleccion_id, "sort_key": "-start_date",
                                    "page_size": 1})
    respuesta.raise_for_status()
    items = respuesta.json().get("items", [])
    hallado = _FECHA.search(items[0]["umm"]["GranuleUR"]) if items else None
    if not hallado:
        return None
    t = hallado[1]
    return date(int(t[:4]), int(t[4:6]), int(t[6:]))


def leer_semana(cliente: httpx.Client, url: str, esq: dict, nombre_lat: str, fila: int,
                nombre_lon: str, columna: int) -> dict[str, float | None]:
    indices = {nombre_lat: (fila, fila), nombre_lon: (columna, columna)}
    crudo = earthdata.leer_csv(cliente, url, ";".join(expresion(v, esq, indices) for v in VARIABLES))
    leidos = {}
    for variable in VARIABLES:
        filas = crudo.get(variable)
        leidos[variable] = _limpio(filas[0][0]) if filas and filas[0] else None
    return leidos


def leer_periodo(lat: float, lon: float, desde: date, hasta: date, cliente: httpx.Client | None = None,
                 hilos: int = HILOS) -> tuple[dict[date, dict[str, float | None]], date | None]:
    """Los tres percentiles del píxel para cada semana publicada, y la última semana publicada."""
    validar_pedido(lat, lon, desde, hasta)
    try:
        cliente = earthdata.cliente_autorizado(cliente)
        coleccion_id = earthdata.coleccion_vigente(cliente, PRODUCTO)
        if coleccion_id is None:
            raise ErrorGRACE(f"CMR no tiene la colección {PRODUCTO}")
        semanas = archivos_semanales(cliente, coleccion_id, desde, hasta)
        ultima = ultima_semana(cliente, coleccion_id)
        if not semanas:
            return {}, ultima
        primera = next(iter(semanas.values()))
        esq = preparar_esquema(cliente, coleccion_id, primera)
        nombre_lat, fila, nombre_lon, columna = celda(cliente, primera, esq, lat, lon)
        tareas = sorted(semanas.items())
        with ThreadPoolExecutor(max_workers=hilos) as grupo:
            leidas = list(grupo.map(lambda t: leer_semana(cliente, t[1], esq, nombre_lat, fila, nombre_lon, columna),
                                    tareas))
    except earthdata.FaltanCredenciales:
        raise
    except (httpx.HTTPError, KeyError, ValueError, ET.ParseError, earthdata.ErrorNASA) as error:
        raise ErrorGRACE(f"No se pudo leer GRACE-DA de la NASA: {error}") from error
    return {dia: valores for (dia, _), valores in zip(tareas, leidas)}, ultima


def a_observaciones(lote_id: str, dia: date, valores: dict[str, float | None] | None,
                    ultima: date | None) -> list[Observacion]:
    salida = []
    for variable_archivo, (variable, que_es) in VARIABLES.items():
        base = dict(lote_id=lote_id, fecha=dia, variable=variable, unidad="%", fuente="GRACE",
                    resolucion_m=RESOLUCION_M)
        if valores is None:
            if ultima is None or dia > ultima:
                motivo = (f"La NASA todavía no publicó esta semana (llega con 3 a 6 meses de atraso; la última "
                          f"publicada es la del {ultima})" if ultima else "La NASA todavía no publicó esta semana")
            else:
                motivo = "La NASA no publicó esta semana"
            salida.append(Observacion(**base, valor=None, calidad="descartada", nota=f"{motivo} · {NOTA_DA}"))
            continue
        valor = valores.get(variable_archivo)
        if valor is None:
            salida.append(Observacion(**base, valor=None, calidad="descartada",
                                      nota=f"Píxel sin dato (mar, hielo o fuera de la grilla) · {NOTA_DA}"))
            continue
        valor = round(valor, 1)
        if 0 <= valor <= 100:
            salida.append(Observacion(**base, valor=valor, calidad="buena",
                                      nota=f"Percentil de {que_es}: {valor:g} = {categoria(valor)} · {NOTA_DA}"))
        else:
            salida.append(Observacion(**base, valor=valor, calidad="dudosa",
                                      nota=f"Percentil de {que_es} fuera de 0 a 100 · {NOTA_DA}"))
    return salida


def observaciones(lote_id: str, desde: date, hasta: date, leidos: dict[date, dict[str, float | None]],
                  ultima: date | None) -> list[Observacion]:
    """Tres observaciones por semana del período, aunque la semana no esté publicada (queda descartada)."""
    semanas = sorted(set(lunes(desde, hasta)) | set(leidos))
    return [o for dia in semanas for o in a_observaciones(lote_id, dia, leidos.get(dia), ultima)]


def obtener_napa(lote_id: str, lat: float, lon: float, desde: date, hasta: date,
                 cliente: httpx.Client | None = None) -> list[Observacion]:
    leidos, ultima = leer_periodo(lat, lon, desde, hasta, cliente)
    if not leidos:  # ninguna semana publicada: se avisa y la consulta prueba el respaldo mensual
        raise ErrorGRACE(f"La NASA no publicó semanas de GRACE-DA entre {desde} y {hasta} (llega con 3 a 6 meses "
                         f"de atraso; la última publicada es la del {ultima})")
    return observaciones(lote_id, desde, hasta, leidos, ultima)


# ---------- respaldo: mascons de JPL, mensual ----------

def fechas_del_tiempo(valores: list[float], unidades: str) -> list[date]:
    """Convierte el tiempo del archivo ('days since 2002-01-01...') en fechas."""
    hallado = re.match(r"\s*(days|hours)\s+since\s+(\d{4}-\d{2}-\d{2})", unidades or "")
    if not hallado:
        raise ErrorGRACE(f"Unidades del tiempo desconocidas: '{unidades}'")
    origen = datetime.strptime(hallado[2], "%Y-%m-%d").date()
    por_dia = 1 if hallado[1] == "days" else 24
    return [origen + timedelta(days=math.floor(v / por_dia)) for v in valores]


def archivo_mascon(cliente: httpx.Client, coleccion_id: str) -> Path:
    """El archivo de mascons más nuevo (un solo NetCDF de ~44 MB con todos los meses), bajado una vez.

    PO.DAAC no lo sirve por OPeNDAP (la NASA responde 404), así que se baja entero de su archivo en la nube y se
    guarda en la carpeta temporal: se vuelve a bajar solo cuando JPL publica un archivo nuevo (una vez por mes).
    """
    respuesta = cliente.get(f"{earthdata.URL_CMR}/granules.umm_json",
                            params={"collection_concept_id": coleccion_id, "sort_key": "-start_date", "page_size": 1})
    respuesta.raise_for_status()
    items = respuesta.json().get("items", [])
    if not items:
        raise ErrorGRACE(f"CMR no tiene archivos de {PRODUCTO_MASCON}")
    url = next((u["URL"] for u in items[0]["umm"].get("RelatedUrls", [])
                if u.get("Type") == "GET DATA" and u["URL"].startswith("https") and u["URL"].endswith(".nc")), None)
    if url is None:
        raise ErrorGRACE(f"CMR no da el enlace de descarga del archivo {items[0]['umm'].get('GranuleUR')}")
    ruta = CARPETA_MASCON / url.rsplit("/", 1)[-1]
    if not ruta.exists():
        CARPETA_MASCON.mkdir(parents=True, exist_ok=True)
        parcial = ruta.with_suffix(".parcial")
        with cliente.stream("GET", url, timeout=300) as descarga:
            if descarga.status_code in (401, 403):
                raise earthdata.ErrorNASA("La NASA negó la descarga de los mascons de JPL")
            descarga.raise_for_status()
            with open(parcial, "wb") as destino:
                for pedazo in descarga.iter_bytes():
                    destino.write(pedazo)
        for viejo in CARPETA_MASCON.glob("*.nc"):  # el archivo anterior ya no hace falta
            viejo.unlink()
        parcial.rename(ruta)
    return ruta


def pixel_por_mes(ruta: Path, lat: float, lon: float) -> dict[date, float | None]:
    """Anomalía (cm) del píxel de 0,5° que contiene el punto, en cada mes del archivo."""
    import rasterio
    from rasterio.windows import Window

    with rasterio.open(f"netcdf:{ruta}:{VARIABLE_MASCON}") as ds:
        unidades = ds.tags().get("time#units", "")
        x = lon % 360 if ds.bounds.right > 180 else lon  # los mascons usan longitudes de 0 a 360
        fila, columna = ds.index(x, lat)
        if not (0 <= fila < ds.height and 0 <= columna < ds.width):
            raise ErrorGRACE(f"El punto ({lat}, {lon}) cae fuera de la grilla de los mascons")
        valores = ds.read(window=Window(columna, fila, 1, 1))[:, 0, 0]
        tiempos = [float(ds.tags(banda)["NETCDF_DIM_time"]) for banda in range(1, ds.count + 1)]
    fechas = fechas_del_tiempo(tiempos, unidades)
    return {dia: _limpio(float(valor)) for dia, valor in zip(fechas, valores)}


def leer_mascon(lat: float, lon: float, desde: date, hasta: date,
                cliente: httpx.Client | None = None) -> dict[date, float | None]:
    """Anomalía del agua total (cm) del píxel para cada mes del período."""
    validar_pedido(lat, lon, desde, hasta)
    try:
        cliente = earthdata.cliente_autorizado(cliente)
        coleccion_id = earthdata.coleccion_vigente(cliente, PRODUCTO_MASCON)
        if coleccion_id is None:
            raise ErrorGRACE(f"CMR no tiene la colección {PRODUCTO_MASCON}")
        meses = pixel_por_mes(archivo_mascon(cliente, coleccion_id), lat, lon)
    except earthdata.FaltanCredenciales:
        raise
    except ErrorGRACE:
        raise
    except Exception as error:  # red, NetCDF ilegible o metadatos raros: se informa y entra el siguiente respaldo
        raise ErrorGRACE(f"No se pudo leer los mascons de JPL: {type(error).__name__}: {error}") from error
    return {dia: valor for dia, valor in meses.items() if desde <= dia <= hasta}


def observaciones_mascon(lote_id: str, leidos: dict[date, float | None]) -> list[Observacion]:
    salida = []
    for dia, valor in sorted(leidos.items()):
        base = dict(lote_id=lote_id, fecha=dia, variable="agua_total_anomalia_cm", unidad="cm", fuente="GRACE",
                    resolucion_m=RESOLUCION_MASCON_M)
        if valor is None:
            salida.append(Observacion(**base, valor=None, calidad="descartada", nota=f"Píxel sin dato · {NOTA_MASCON}"))
            continue
        valor = round(valor, 2)
        signo = "más agua" if valor > 0 else "menos agua"
        calidad = "buena" if abs(valor) <= 200 else "dudosa"
        salida.append(Observacion(**base, valor=valor, calidad=calidad,
                                  nota=f"{abs(valor):g} cm de {signo} que el promedio · {NOTA_MASCON}"))
    return salida


def obtener_mascon(lote_id: str, lat: float, lon: float, desde: date, hasta: date,
                   cliente: httpx.Client | None = None) -> list[Observacion]:
    leidos = leer_mascon(lat, lon, desde, hasta, cliente)
    if not leidos:
        raise ErrorGRACE(f"JPL no publicó meses de GRACE-FO entre {desde} y {hasta}")
    return observaciones_mascon(lote_id, leidos)


# ---------- conexión con el núcleo (spec 009) ----------

SATELITES = [
    Satelite("GRACE", lambda lote, desde, hasta: obtener_napa(lote["id"], lote["lat"], lote["lon"], desde, hasta)),
    Satelite("GRACE:MASCON", lambda lote, desde, hasta: obtener_mascon(lote["id"], lote["lat"], lote["lon"],
                                                                       desde, hasta),
             respaldo_de="GRACE"),
]

router = APIRouter(tags=["GRACE-FO (pruebas internas)"])


def _responder(funcion, lote_id: str, lat: float, lon: float, desde: date, hasta: date) -> list[Observacion]:
    try:
        validar_pedido(lat, lon, desde, hasta)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return funcion(lote_id, lat, lon, desde, hasta)
    except earthdata.FaltanCredenciales as error:
        raise HTTPException(status_code=503, detail=str(error))
    except ErrorGRACE as error:
        raise HTTPException(status_code=502, detail=str(error))


@router.get("/napa", response_model=list[Observacion])
def napa(lote_id: str, lat: float, lon: float, desde: date, hasta: date) -> list[Observacion]:
    return _responder(obtener_napa, lote_id, lat, lon, desde, hasta)


@router.get("/napa/mascon", response_model=list[Observacion])
def napa_mascon(lote_id: str, lat: float, lon: float, desde: date, hasta: date) -> list[Observacion]:
    return _responder(obtener_mascon, lote_id, lat, lon, desde, hasta)
