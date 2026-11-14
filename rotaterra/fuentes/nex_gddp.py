"""Conector NEX-GDDP-CMIP6 (NASA): clima futuro de la zona del lote, 2041-2060 contra 1995-2014 (spec 058).

Proyecciones diarias de temperatura máxima, mínima y lluvia de los modelos climáticos CMIP6, corregidas y
bajadas de escala por la NASA (Ames, NEX) a una grilla de 0,25° (~25 km). Se leen por el servicio NCSS del THREDDS
público del NCCS (sin cuenta), un año por pedido, solo en la celda del lote.

Con eso se calculan indicadores para comparar rotaciones frente al clima que viene: días de calor (≥ 35 °C), máxima
de verano, días de helada del aire, lluvia del año y de la campaña, días de lluvia extrema (≥ 50 mm) y la racha
seca más larga de la campaña. Para cada uno: la línea de base de los modelos (1995-2014) y dos escenarios a
2041-2060, SSP2-4.5 (emisiones intermedias) y SSP5-8.5 (emisiones altas).

Es una PROYECCIÓN de modelos, no un pronóstico, y un dato REGIONAL de ~25 km: todo sale `dudosa`. Los datos
no cambian, así que cada celda se calcula una sola vez y queda en memoria. La primera vez tarda unos 15 minutos
(540 pedidos de unos 7 s, de a 4 a la vez).
"""

import re
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import httpx
from fastapi import APIRouter, HTTPException

from rotaterra.contrato import Observacion
from rotaterra.fuentes.registro import Satelite

URL_BASE = "https://ds.nccs.nasa.gov/thredds"
RAIZ = "AMES/NEX/GDDP-CMIP6"
RESOLUCION_M = 25000
# Tres modelos que cubren el rango de CMIP6 para el centro de Argentina: ACCESS-CM2 (cálido), MPI-ESM1-2-HR
# (templado) y MRI-ESM2-0 (intermedio). Los tres tienen las 3 variables en los 3 períodos con el miembro r1i1p1f1.
MODELOS = ("ACCESS-CM2", "MPI-ESM1-2-HR", "MRI-ESM2-0")
PERIODOS = {  # nombre en la salida -> (escenario en el NCCS, primer año, último año)
    "historico": ("historical", 1995, 2014),
    "ssp245": ("ssp245", 2041, 2060),
    "ssp585": ("ssp585", 2041, 2060),
}
TEXTO_PERIODO = {"historico": "línea de base de los modelos 1995-2014 (no es lo observado)",
                 "ssp245": "SSP2-4.5 (emisiones intermedias) 2041-2060",
                 "ssp585": "SSP5-8.5 (emisiones altas) 2041-2060"}
VARIABLES = ("tasmax", "tasmin", "pr")
HILOS = 4  # el servidor del NCCS corta conexiones con 16 pedidos a la vez
INTENTOS = 3
ESPERA_S = 5
MIN_ANIOS = 18  # de 20: un modelo con menos años completos en un período queda afuera de ese período
UMBRAL_CALOR = 35.0
UMBRAL_HELADA = 0.0
UMBRAL_EXTREMA = 50.0
UMBRAL_DIA_SECO = 1.0
REGIONAL = "proyección de modelos corregidos, no pronóstico · dato REGIONAL de la celda de 0,25° (~25 km), no del lote"

# indicador -> (unidad, decimales, qué es)
INDICADORES = {
    "dias_calor_35": ("días/año", 1, f"Días por año con máxima del aire ≥ {UMBRAL_CALOR:g} °C (estrés por calor)"),
    "tmax_verano_c": ("°C", 1, "Máxima media del aire de diciembre a febrero"),
    "dias_helada_aire": ("días/año", 1, f"Días por año con mínima del aire ≤ {UMBRAL_HELADA:g} °C"),
    "lluvia_anual_mm": ("mm", 0, "Lluvia del año"),
    "lluvia_campana_mm": ("mm", 0, "Lluvia de octubre a marzo"),
    "dias_lluvia_extrema_50": ("días/año", 2, f"Días por año con lluvia ≥ {UMBRAL_EXTREMA:g} mm"),
    "racha_seca_campana_dias": ("días", 0,
                                f"Racha más larga de días seguidos con menos de {UMBRAL_DIA_SECO:g} mm, de octubre a marzo"),
}

_ARCHIVO = re.compile(r'name="((?:tasmax|tasmin|pr)_day_[^"]+?_(\d{4})(?:_v(\d+)\.(\d+))?\.nc)"')
_MIEMBRO = re.compile(r'xlink:title="(r\d+i\d+p\d+f\d+)"')


class ErrorNEXGDDP(Exception):
    """El THREDDS del NCCS no respondió o respondió algo ilegible."""


def validar_punto(lat: float, lon: float) -> None:
    if not -60 <= lat <= 90:  # la grilla de NEX-GDDP va de 60° S a 90° N
        raise ValueError(f"Latitud fuera de la grilla de NEX-GDDP (60° S a 90° N): {lat}")
    if not -180 <= lon <= 180:
        raise ValueError(f"Longitud fuera de rango: {lon}")


def celda(lat: float, lon: float) -> tuple[float, float]:
    """Centro de la celda de 0,25° que contiene el punto (latitud, longitud de 0 a 360, como la grilla)."""
    lon360 = lon % 360
    return (round(-59.875 + round((lat + 59.875) / 0.25) * 0.25, 3),
            round(0.125 + round((lon360 - 0.125) / 0.25) * 0.25, 3) % 360)


# ---------- lectura (red) ----------

def _get(cliente: httpx.Client, url: str, **params) -> httpx.Response:
    for intento in range(INTENTOS):
        try:
            respuesta = cliente.get(url, params=params or None)
            respuesta.raise_for_status()
            return respuesta
        except httpx.HTTPError:  # el NCCS a veces corta o tarda: se reintenta
            if intento == INTENTOS - 1:
                raise
            time.sleep(ESPERA_S * (intento + 1))


def elegir_archivos(catalogo: str) -> dict[int, str]:
    """Año -> archivo, quedándose con la versión más nueva (_v2.0 gana a _v1.1 y al nombre sin versión)."""
    elegidos: dict[int, tuple[tuple[int, int], str]] = {}
    for nombre, anio, mayor, menor in _ARCHIVO.findall(catalogo):
        version = (int(mayor or 0), int(menor or 0))
        if int(anio) not in elegidos or version > elegidos[int(anio)][0]:
            elegidos[int(anio)] = (version, nombre)
    return {anio: nombre for anio, (_, nombre) in elegidos.items()}


def archivos(cliente: httpx.Client, modelo: str, escenario: str, variable: str) -> tuple[str, dict[int, str]]:
    """(miembro, año -> archivo) del catálogo del NCCS."""
    catalogo = _get(cliente, f"{URL_BASE}/catalog/{RAIZ}/{modelo}/{escenario}/catalog.xml").text
    miembros = _MIEMBRO.findall(catalogo)
    if not miembros:
        raise ErrorNEXGDDP(f"El catálogo de {modelo} {escenario} no tiene ningún miembro")
    miembro = "r1i1p1f1" if "r1i1p1f1" in miembros else sorted(miembros)[0]
    lista = _get(cliente, f"{URL_BASE}/catalog/{RAIZ}/{modelo}/{escenario}/{miembro}/{variable}/catalog.xml").text
    return miembro, elegir_archivos(lista)


def leer_csv(texto: str, variable: str) -> tuple[dict[date, float], tuple[float, float] | None]:
    """CSV de NCSS -> fecha -> valor en °C o mm/día, y el centro de la celda que usó el servidor."""
    valores, punto = {}, None
    for linea in texto.splitlines()[1:]:
        partes = linea.split(",")
        if len(partes) < 5:
            continue
        try:
            dia, valor = date.fromisoformat(partes[0][:10]), float(partes[-1])
        except ValueError:
            continue
        if valor != valor or abs(valor) > 1e10:  # NaN o relleno
            continue
        valores[dia] = valor - 273.15 if variable.startswith("tas") else valor * 86400
        punto = punto or (float(partes[2]), float(partes[3]))
    return valores, punto


def pedir_anio(cliente: httpx.Client, modelo: str, escenario: str, miembro: str, variable: str, archivo: str,
               anio: int, lat: float, lon360: float) -> tuple[dict[date, float], tuple[float, float] | None]:
    url = f"{URL_BASE}/ncss/grid/{RAIZ}/{modelo}/{escenario}/{miembro}/{variable}/{archivo}"
    texto = _get(cliente, url, var=variable, latitude=lat, longitude=lon360, time_start=f"{anio}-01-01",
                 time_end=f"{anio}-12-31T23:59:59Z", accept="csv").text
    return leer_csv(texto, variable)


# ---------- cálculos (sin red) ----------

def _rango(desde: date, hasta: date) -> list[date]:
    return [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]


def indicadores_por_anio(serie: dict[str, dict[date, float]], primero: int, ultimo: int) -> dict[str, list[float]]:
    """Cada indicador, un valor por año (o por campaña de octubre a marzo). Un año o campaña con días sin dato
    no cuenta: un hueco achicaría una suma sin avisar. Los calendarios de 365 o 360 días de algunos modelos no
    traen el 29/2 (o el 31): esos días no se piden."""
    tx, tn, pr = serie["tasmax"], serie["tasmin"], serie["pr"]
    salida = {k: [] for k in INDICADORES}
    for anio in range(primero, ultimo + 1):
        dias = [d for d in _rango(date(anio, 1, 1), date(anio, 12, 31)) if d in tx or d in tn or d in pr]
        if len(dias) >= 360 and all(d in tx and d in tn and d in pr for d in dias):
            salida["dias_calor_35"].append(sum(tx[d] >= UMBRAL_CALOR for d in dias))
            salida["dias_helada_aire"].append(sum(tn[d] <= UMBRAL_HELADA for d in dias))
            salida["lluvia_anual_mm"].append(sum(pr[d] for d in dias))
            salida["dias_lluvia_extrema_50"].append(sum(pr[d] >= UMBRAL_EXTREMA for d in dias))
        if anio < ultimo:  # campaña y verano cruzan de año: la última no está completa dentro del período
            verano = [d for d in _rango(date(anio, 12, 1), date(anio + 1, 2, 28)) if d in tx]
            if len(verano) >= 88:
                salida["tmax_verano_c"].append(statistics.mean(tx[d] for d in verano))
            campana = [d for d in _rango(date(anio, 10, 1), date(anio + 1, 3, 31))
                       if not (d.month == 2 and d.day == 29)]
            if all(d in pr for d in campana):
                salida["lluvia_campana_mm"].append(sum(pr[d] for d in campana))
                racha = maxima = 0
                for d in campana:
                    racha = racha + 1 if pr[d] < UMBRAL_DIA_SECO else 0
                    maxima = max(maxima, racha)
                salida["racha_seca_campana_dias"].append(maxima)
    return salida


def resumen_modelo(por_anio: dict[str, list[float]], anios_periodo: int) -> dict[str, float] | None:
    """Promedio de cada indicador en el período, o None si faltan años (menos de MIN_ANIOS de 20)."""
    if len(por_anio["lluvia_anual_mm"]) < MIN_ANIOS * anios_periodo / 20:
        return None
    return {k: statistics.mean(v) for k, v in por_anio.items() if v}


def a_observaciones(lote_id: str, por_modelo: dict[str, dict[str, dict[str, float] | None]],
                    punto: tuple[float, float]) -> list[Observacion]:
    """Una observación por indicador y período: la mediana de los modelos, con el rango y el cambio en la nota."""
    observaciones = []
    lugar = f"celda centrada en {punto[0]:.3f}, {punto[1] - 360 if punto[1] > 180 else punto[1]:.3f}"
    for periodo, (_, primero, ultimo) in PERIODOS.items():
        for indicador, (unidad, decimales, que_es) in INDICADORES.items():
            valores = {m: r[indicador] for m, r in por_modelo[periodo].items() if r and indicador in r}
            base = dict(lote_id=lote_id, fecha=date(ultimo, 12, 31), variable=f"{indicador}_{periodo}",
                        unidad=unidad, fuente="NEX_GDDP", resolucion_m=RESOLUCION_M)
            fuera = [m for m in MODELOS if m not in valores]
            if not valores:
                observaciones.append(Observacion(**base, valor=None, calidad="descartada",
                                                 nota=f"{que_es} · {TEXTO_PERIODO[periodo]} · ningún modelo trajo "
                                                      f"los años completos · NEX-GDDP-CMIP6 (NASA) · {lugar}"))
                continue
            mediana = statistics.median(valores.values())
            partes = [f"{que_es}", TEXTO_PERIODO[periodo],
                      f"mediana de {len(valores)} modelos: " + ", ".join(
                          f"{m} {v:.{decimales}f}" for m, v in valores.items())]
            if periodo != "historico":
                base_hist = {m: r[indicador] for m, r in por_modelo["historico"].items() if r and indicador in r}
                cambios = [valores[m] - base_hist[m] for m in valores if m in base_hist]
                if cambios:
                    def signo(x):  # sin "-0": un cambio que redondea a cero es +0
                        return f"{round(x, decimales) or 0.0:+.{decimales}f}"
                    partes.append(f"cambio contra 1995-2014 del mismo modelo: {signo(statistics.median(cambios))}"
                                  f" (de {signo(min(cambios))} a {signo(max(cambios))})")
            if fuera:
                partes.append(f"sin {', '.join(fuera)} (le faltaban años)")
            partes += [f"NEX-GDDP-CMIP6 (NASA) · {lugar}", REGIONAL]
            observaciones.append(Observacion(**base, valor=round(mediana, decimales), calidad="dudosa",
                                             nota=" · ".join(partes)))
    return observaciones


# ---------- principal ----------

_MEMORIA: dict[tuple[float, float], tuple[dict, tuple[float, float]]] = {}
_CANDADOS: dict[tuple[float, float], threading.Lock] = {}
_CANDADO = threading.Lock()


def calcular_celda(lat: float, lon360: float, cliente: httpx.Client,
                   hilos: int = HILOS) -> tuple[dict[str, dict[str, dict[str, float] | None]], tuple[float, float]]:
    """Pide los 540 años-variable (3 modelos × 3 variables × 60 años) y resume por modelo y período."""
    try:
        catalogo = {(m, PERIODOS[p][0], v): archivos(cliente, m, PERIODOS[p][0], v)
                    for m in MODELOS for p in PERIODOS for v in VARIABLES}
    except (httpx.HTTPError, ErrorNEXGDDP) as error:
        raise ErrorNEXGDDP(f"El catálogo del NCCS no respondió: {error}") from error
    trabajos = []
    for m in MODELOS:
        for p, (escenario, primero, ultimo) in PERIODOS.items():
            for v in VARIABLES:
                miembro, por_anio = catalogo[(m, escenario, v)]
                trabajos += [(m, p, escenario, miembro, v, por_anio[a], a)
                             for a in range(primero, ultimo + 1) if a in por_anio]

    def uno(t):
        m, p, escenario, miembro, v, archivo, anio = t
        try:
            return t, pedir_anio(cliente, m, escenario, miembro, v, archivo, anio, lat, lon360)
        except httpx.HTTPError:  # un año que no llega deja a ese modelo con un año menos, no inventa
            return t, ({}, None)

    with ThreadPoolExecutor(max_workers=hilos) as grupo:
        resultados = list(grupo.map(uno, trabajos))
    if not any(valores for _, (valores, _) in resultados):
        raise ErrorNEXGDDP("El NCCS no devolvió ningún año de NEX-GDDP-CMIP6 para la celda")
    series: dict[tuple[str, str], dict[str, dict[date, float]]] = {}
    punto = None
    for (m, p, _, _, v, _, _), (valores, centro) in resultados:
        series.setdefault((m, p), {x: {} for x in VARIABLES})[v].update(valores)
        punto = punto or centro
    por_modelo = {p: {} for p in PERIODOS}
    for p, (_, primero, ultimo) in PERIODOS.items():
        for m in MODELOS:
            serie = series.get((m, p), {x: {} for x in VARIABLES})
            por_modelo[p][m] = resumen_modelo(indicadores_por_anio(serie, primero, ultimo), ultimo - primero + 1)
    return por_modelo, punto


def obtener_clima_futuro(lote_id: str, lat: float, lon: float, cliente: httpx.Client | None = None) -> list[Observacion]:
    """Indicadores de clima futuro de la celda de 0,25° del lote. Se calcula una vez por celda y queda en memoria."""
    validar_punto(lat, lon)
    clave = celda(lat, lon)
    with _CANDADO:
        candado = _CANDADOS.setdefault(clave, threading.Lock())
    with candado:  # dos pedidos de la misma celda a la vez: el segundo espera y usa lo del primero
        if clave not in _MEMORIA:
            cliente = cliente or httpx.Client(timeout=120, follow_redirects=True)
            _MEMORIA[clave] = calcular_celda(clave[0], clave[1], cliente)
    por_modelo, punto = _MEMORIA[clave]
    return a_observaciones(lote_id, por_modelo, punto or clave)


# ---------- conexión con el núcleo (spec 009) ----------
# Fuente propia (no es respaldo de nadie) y dato fijo: no usa el período del pedido.

SATELITES = [Satelite("NEX_GDDP", lambda lote, desde, hasta: obtener_clima_futuro(lote["id"], lote["lat"], lote["lon"]),
                      estatico=True)]

router = APIRouter(tags=["Clima futuro NEX-GDDP-CMIP6 (pruebas internas)"])


@router.get("/clima-futuro", response_model=list[Observacion])
def clima_futuro(lat: float, lon: float, lote_id: str = "consulta") -> list[Observacion]:
    """Clima 2041-2060 (SSP2-4.5 y SSP5-8.5) contra 1995-2014 en la celda de ~25 km del lote. La primera
    consulta de una celda tarda unos 15 minutos; después contesta al instante."""
    try:
        validar_punto(lat, lon)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener_clima_futuro(lote_id, lat, lon)
    except ErrorNEXGDDP as error:
        raise HTTPException(status_code=502, detail=str(error))
