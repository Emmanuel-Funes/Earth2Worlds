"""Conector SMAP L3: humedad de superficie observada por satélite, segundo respaldo de SMAP L4 (spec 015).

El L4 (SPL4SMGP) es un modelo que asimila SMAP; el L3 mejorado (SPL3SMP_E) es la observación del
radiómetro, sin modelo: una pasada AM y una PM por día cuando la órbita cruza la celda de 9 km.
Se lee solo la celda del lote por OPeNDAP de la NASA (CMR + Earthdata), como el camino directo del L4.
"""

import math
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import httpx
from fastapi import APIRouter, HTTPException

from rotaterra.contrato import Observacion
from rotaterra.fuentes import earthdata
from rotaterra.fuentes.registro import Satelite

PRODUCTO = "SPL3SMP_E"
PROVEEDOR = "NSIDC_CPRD"  # nube de NSIDC: la misma que usa el L4
RESOLUCION_M = 9000
VARIABLE = "humedad_superficial"  # la misma que el L4 usa para 0-5 cm (sm_surface)
UNIDAD = "m³/m³"
VALOR_RELLENO = -9999
RANGO_FISICO = (0.0, 0.6)  # el mismo del L4
BIT_RECOMENDADA = 1  # bit 0 de retrieval_qual_flag: 0 = calidad recomendada, 1 = no recomendada
MAX_DIAS = 366
HILOS = 6
PASADAS = ("AM", "PM")
NOTA_BASE = ("Respaldo de SMAP L4 · observación satelital SMAP L3 (SPL3SMP_E), celda de 9 km: contexto "
             "regional, no dato del lote · solo superficie 0-5 cm (el L3 no trae zona de raíces)")

# Grilla EASE-Grid 2.0 global de 9 km (EPSG:6933): la misma del L4 y del L3 mejorado
_A, _E2 = 6378137.0, 0.0066943799901413165
_E = math.sqrt(_E2)
_K0 = math.cos(math.radians(30)) / math.sqrt(1 - _E2 * math.sin(math.radians(30)) ** 2)
_X0, _Y0, _CELDA = -17363027.2924805, 7310037.17138672, 9008.055210146
FILAS, COLUMNAS = 1624, 3856

# qué leer de cada pasada (la PM lleva el sufijo _pm): nombre base -> campo
CAMPOS = {"soil_moisture": "humedad", "retrieval_qual_flag": "bandera", "latitude": "lat", "longitude": "lon"}
_RUTAS: dict[str, dict[str, dict[str, str]]] = {}  # colección -> pasada -> campo -> ruta en el archivo
_FECHA = re.compile(r"_(\d{8})_")


class ErrorSMAPL3(Exception):
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


def celda_ease2(lat: float, lon: float) -> tuple[int, int]:
    """Fila y columna de la celda de 9 km que contiene el punto."""
    s = math.sin(math.radians(lat))
    q = (1 - _E2) * (s / (1 - _E2 * s * s) - (1 / (2 * _E)) * math.log((1 - _E * s) / (1 + _E * s)))
    x, y = _A * _K0 * math.radians(lon), _A * q / (2 * _K0)
    fila, columna = round((_Y0 - y) / _CELDA), round((x - _X0) / _CELDA)  # _X0, _Y0: centro de la 1.ª celda
    # se piden 2 columnas (columna y columna + 1), por eso la última posible es COLUMNAS - 2
    return min(max(fila, 0), FILAS - 1), min(max(columna, 0), COLUMNAS - 2)


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia sobre la Tierra (para verificar que la celda del archivo es la del lote)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


# ---------- diálogo con la NASA ----------

def coleccion(cliente: httpx.Client) -> str:
    """Id de CMR de la versión más nueva de SPL3SMP_E en la nube de NSIDC (si no, la que tenga CMR)."""
    items = cliente.get(f"{earthdata.URL_CMR}/collections.umm_json",
                        params={"short_name": PRODUCTO, "provider": PROVEEDOR, "page_size": 20}).json()["items"]
    if items:
        return max(items, key=lambda i: i["umm"].get("Version", ""))["meta"]["concept-id"]
    vigente = earthdata.coleccion_vigente(cliente, PRODUCTO)
    if vigente is None:
        raise ErrorSMAPL3(f"CMR no tiene la colección {PRODUCTO}")
    return vigente


def archivos_por_dia(cliente: httpx.Client, coleccion_id: str, lat: float, lon: float,
                     desde: date, hasta: date) -> dict[date, str]:
    """URL OPeNDAP del archivo diario de cada fecha (SMAP_L3_SM_P_E_AAAAMMDD_…); si hay dos, el más nuevo."""
    caja = (lon - 0.01, lat - 0.01, lon + 0.01, lat + 0.01)
    elegidos: dict[date, tuple[str, str]] = {}
    for nombre, url in earthdata.archivos(cliente, coleccion_id, desde, hasta, caja=caja):
        hallado = _FECHA.search(nombre)
        if not hallado:
            continue
        texto = hallado[1]
        try:
            dia = date(int(texto[:4]), int(texto[4:6]), int(texto[6:]))
        except ValueError:
            continue
        if desde <= dia <= hasta and (dia not in elegidos or nombre > elegidos[dia][0]):
            elegidos[dia] = (nombre, url)
    return {dia: url for dia, (_, url) in elegidos.items()}


def rutas_de_capas(dmr: str) -> dict[str, dict[str, str]]:
    """Busca en los metadatos DAP4 (.dmr) las capas de las pasadas AM y PM (los grupos polares no)."""
    raiz = ET.fromstring(dmr)
    halladas: dict[str, dict[str, str]] = {p: {} for p in PASADAS}

    def recorrer(nodo, camino: str, pasada: str | None) -> None:
        for hijo in nodo:
            etiqueta = hijo.tag.rsplit("}", 1)[-1]
            nombre = hijo.get("name")
            if not nombre:
                continue
            ruta = f"{camino}/{nombre}"
            if etiqueta == "Group":
                grupo = None
                if nombre.startswith("Soil_Moisture_Retrieval_Data") and "polar" not in nombre.lower():
                    grupo = next((p for p in PASADAS if nombre.upper().endswith(f"_{p}")), None)
                recorrer(hijo, ruta, grupo or pasada)
            elif pasada:
                sufijo = "_pm" if pasada == "PM" else ""
                for base, campo in CAMPOS.items():
                    if nombre == f"{base}{sufijo}":
                        halladas[pasada][campo] = ruta

    recorrer(raiz, "", None)
    for pasada, campos in halladas.items():
        faltan = set(CAMPOS.values()) - set(campos)
        if faltan:
            raise ErrorSMAPL3(f"El archivo no tiene en la pasada {pasada} las capas {sorted(faltan)}")
    return halladas


def preparar_rutas(cliente: httpx.Client, coleccion_id: str, url: str) -> dict[str, dict[str, str]]:
    if coleccion_id not in _RUTAS:
        respuesta = cliente.get(f"{url}.dmr")
        if respuesta.status_code in (401, 403):
            raise earthdata.ErrorNASA("La NASA negó el acceso a los metadatos del archivo SMAP L3")
        respuesta.raise_for_status()
        _RUTAS[coleccion_id] = rutas_de_capas(respuesta.text)
    return _RUTAS[coleccion_id]


def _limpio(valor: float | None, relleno: bool = True) -> float | None:
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return None
    if relleno and valor <= VALOR_RELLENO:
        return None
    return valor


def leer_celda(cliente: httpx.Client, url: str, rutas: dict[str, dict[str, str]],
               fila: int, columna: int) -> dict[str, dict[str, float | None]]:
    """Humedad, bandera, latitud y longitud de la celda en las pasadas AM y PM de un archivo diario."""
    # el servidor devuelve vacío si se pide un único valor: se piden 2 columnas y se usa la primera
    expresion = ";".join(f"{ruta}[{fila}][{columna}:1:{columna + 1}]"
                         for campos in rutas.values() for ruta in campos.values())
    crudo = earthdata.leer_csv(cliente, url, expresion)
    pasadas: dict[str, dict[str, float | None]] = {}
    for pasada, campos in rutas.items():
        pasadas[pasada] = {}
        for campo, ruta in campos.items():
            filas = crudo.get(ruta.lstrip("/"))
            if not filas or not filas[0]:
                raise ErrorSMAPL3(f"OPeNDAP no devolvió '{ruta}' para {url}")
            valor = filas[0][0]
            pasadas[pasada][campo] = _limpio(valor, relleno=campo != "bandera")
    return pasadas


# ---------- conversión al contrato (testeable sin internet) ----------

def recomendada(pasada: dict[str, float | None]) -> bool:
    bandera = pasada.get("bandera")
    return bandera is not None and int(bandera) & BIT_RECOMENDADA == 0


def a_observacion(lote_id: str, dia: date, pasadas: dict[str, dict[str, float | None]] | None) -> Observacion:
    base = dict(lote_id=lote_id, fecha=dia, variable=VARIABLE, unidad=UNIDAD, fuente="SMAP",
                resolucion_m=RESOLUCION_M)
    if pasadas is None:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"La NASA no publicó el archivo L3 de este día · {NOTA_BASE}")
    detalle, buenas, malas = [], [], []
    for nombre in PASADAS:
        pasada = pasadas.get(nombre) or {}
        humedad = pasada.get("humedad")
        if humedad is None:
            detalle.append(f"{nombre} sin pasada")
        elif recomendada(pasada):
            buenas.append(humedad)
            detalle.append(f"{nombre} {humedad:.3f} (recomendada)")
        else:
            malas.append(humedad)
            bandera = pasada.get("bandera")
            detalle.append(f"{nombre} {humedad:.3f} (no recomendada, bandera "
                           f"{'sin dato' if bandera is None else int(bandera)})")
    resumen = f"{NOTA_BASE} · {' · '.join(detalle)}"
    if not buenas and not malas:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"Ese día SMAP no pasó sobre la celda o no pudo medir · {resumen}")
    usadas = buenas or malas
    valor = round(sum(usadas) / len(usadas), 4)
    minimo, maximo = RANGO_FISICO
    motivos = []
    if not buenas:
        motivos.append("Solo pasadas sin calidad recomendada (bit 0 de retrieval_qual_flag)")
    if not minimo <= valor <= maximo:
        motivos.append(f"Fuera del rango físico ({minimo} a {maximo} m³/m³)")
    if motivos:
        return Observacion(**base, valor=valor, calidad="dudosa", nota=f"{' · '.join(motivos)} · {resumen}")
    cuantas = "Promedio de AM y PM" if len(buenas) == 2 else "Una pasada"
    return Observacion(**base, valor=valor, calidad="buena", nota=f"{cuantas} · {resumen}")


def observaciones(lote_id: str, desde: date, hasta: date,
                  leidos: dict[date, dict[str, dict[str, float | None]]]) -> list[Observacion]:
    """Una observación por día del período, aunque no haya archivo ese día (queda descartada)."""
    dias = [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]
    return [a_observacion(lote_id, dia, leidos.get(dia)) for dia in dias]


# ---------- lectura del período ----------

def leer_periodo(lat: float, lon: float, desde: date, hasta: date, cliente: httpx.Client | None = None,
                 hilos: int = HILOS) -> dict[date, dict[str, dict[str, float | None]]]:
    """Pasadas AM y PM de la celda del punto para cada día con archivo de la NASA."""
    validar_pedido(lat, lon, desde, hasta)
    fila, columna = celda_ease2(lat, lon)
    try:
        cliente = earthdata.cliente_autorizado(cliente)
        coleccion_id = coleccion(cliente)
        por_dia = archivos_por_dia(cliente, coleccion_id, lat, lon, desde, hasta)
        if not por_dia:
            raise ErrorSMAPL3(f"CMR no tiene archivos {PRODUCTO} con OPeNDAP del {desde} al {hasta} para el punto")
        rutas = preparar_rutas(cliente, coleccion_id, next(iter(por_dia.values())))
        tareas = sorted(por_dia.items())
        with ThreadPoolExecutor(max_workers=hilos) as grupo:
            leidas = list(grupo.map(lambda t: leer_celda(cliente, t[1], rutas, fila, columna), tareas))
    except earthdata.FaltanCredenciales:
        raise
    except (httpx.HTTPError, KeyError, ValueError, ET.ParseError, earthdata.ErrorNASA) as error:
        raise ErrorSMAPL3(f"No se pudo leer SMAP L3 de la NASA: {error}") from error
    return {dia: pasadas for (dia, _), pasadas in zip(tareas, leidas)}


def obtener_humedad_l3(lote_id: str, lat: float, lon: float, desde: date, hasta: date,
                       cliente: httpx.Client | None = None, hilos: int = HILOS) -> list[Observacion]:
    """Humedad de superficie SMAP L3 del punto, una por día, en el contrato común."""
    return observaciones(lote_id, desde, hasta, leer_periodo(lat, lon, desde, hasta, cliente, hilos))


# ---------- conexión con el núcleo (spec 009) ----------

# segundo respaldo de SMAP: entra si fallan el L4 directo y el L4 vía AppEEARS (orden 1), specs 005 y 015
SATELITES = [Satelite("SMAP:L3", lambda lote, desde, hasta: obtener_humedad_l3(lote["id"], lote["lat"], lote["lon"],
                                                                              desde, hasta),
                      respaldo_de="SMAP", orden=2)]

router = APIRouter(tags=["SMAP L3 (pruebas internas)"])


@router.get("/humedad-suelo/l3", response_model=list[Observacion])
def humedad_suelo_l3(lote_id: str, lat: float, lon: float, desde: date, hasta: date) -> list[Observacion]:
    try:
        validar_pedido(lat, lon, desde, hasta)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener_humedad_l3(lote_id, lat, lon, desde, hasta)
    except earthdata.FaltanCredenciales as error:
        raise HTTPException(status_code=503, detail=str(error))
    except ErrorSMAPL3 as error:
        raise HTTPException(status_code=502, detail=str(error))
