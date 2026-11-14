"""Conector GEOS-FP: clima y evapotranspiración del día del modelo de la NASA, respaldo "del día" de POWER y de ET
(spec 043).

POWER publica con 4 días de atraso (la radiación con 7) y la evapotranspiración de MODIS con 8 días o más. GEOS-FP es el
modelo con el que trabaja la NASA (GMAO) y publica cada hora con unas 9 horas de atraso, en celdas de 0,25° × 0,3125°
(unos 28 km). Solo completa los últimos días que la principal todavía no publicó: el núcleo lo pide con `al_dia=True`
(spec 043, parte A).

Satélite independiente (spec 009): hace su propio pedido a la NASA y no importa a ningún otro satélite. El servidor
OPeNDAP de GEOS-FP es público: no usa la cuenta de Earthdata.
"""

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta, timezone

import httpx
from fastapi import APIRouter, HTTPException

from rotaterra.contrato import Observacion
from rotaterra.fuentes.registro import Satelite

BASE = "https://opendap.nccs.nasa.gov/dods/GEOS-5/fp/0.25_deg/assim"
# colección horaria -> (variable GEOS-FP, variable Rotaterra)
PEDIDOS = {
    "temp": ("tavg1_2d_slv_Nx", "t2m"),        # temperatura del aire a 2 m (K)
    "radiacion": ("tavg1_2d_rad_Nx", "swgdn"),  # radiación solar que llega al suelo (W/m²)
    "lluvia": ("tavg1_2d_flx_Nx", "prectot"),   # lluvia total (kg/m²/s = mm/s)
}
PEDIDO_ET = ("tavg1_2d_lnd_Nx", "evland")      # evaporación total sobre tierra, suelo + plantas (kg/m²/s = mm/s)
RESOLUCION_M = 28000
RELLENO = 1e14
HUSO = timedelta(hours=-3)  # día local argentino (UTC−3)
RANGOS = {"temp_max": (-40.0, 60.0), "temp_min": (-40.0, 60.0), "radiacion": (0.0, 50.0), "lluvia_mm": (0.0, 500.0),
          "et_mm_dia": (0.0, 20.0)}
UNIDADES = {"temp_max": "°C", "temp_min": "°C", "radiacion": "MJ/m²/día", "lluvia_mm": "mm/día", "et_mm_dia": "mm/día"}
NOTA = ("Dato del día de NASA GEOS-FP (modelo del GMAO, no una medición), celda de 0,25° × 0,3125° "
        "(~28 km, regional): completa los días que POWER todavía no publicó")
NOTA_ET = ("Dato del día de NASA GEOS-FP (modelo del GMAO, no una medición), celda de 0,25° × 0,3125° "
           "(~28 km, regional): evapotranspiración del día, completa los días que MODIS todavía no publicó")
# del modelo se dan como orientativas: la lluvia (no pasa por pluviómetros) y la evapotranspiración (celda de 28 km
# contra los 500 m de MODIS)
ORIENTATIVAS = {"lluvia_mm": "la lluvia de un modelo es orientativa",
                "et_mm_dia": "la evapotranspiración de un modelo de 28 km es orientativa"}
MAX_DIAS = 366
# cada hora es un archivo distinto en el servidor: más de ~24 horas por pedido da 504 (prueba real)
BLOQUE_HORAS = 12
HILOS = 4
REINTENTOS = 2


class ErrorGEOSFP(Exception):
    """El servidor de GEOS-FP no respondió o respondió algo que no se puede leer."""


def celda(lat: float, lon: float) -> tuple[int, int]:
    """Índices (lat, lon) de la celda más cercana. Grilla: 721 latitudes desde −90 × 1152 longitudes desde −180."""
    return round((lat + 90) / 0.25), round((lon + 180) / 0.3125) % 1152


def leer_ascii(texto: str) -> list[float | None]:
    """Valores de la primera variable de una respuesta `.ascii` de GrADS-DODS (sin las coordenadas de después).

    Formato: una línea `t2m, [24][1][1]`, una línea `[i][j], valor` por hora (con líneas en blanco entre horas) y
    después las coordenadas (`time, [24]`, `lat, [1]`, `lon, [1]`), que no se leen.
    """
    lineas = texto.strip().splitlines()
    if not lineas or "," not in lineas[0]:
        raise ErrorGEOSFP(f"respuesta ilegible de GEOS-FP: {texto[:120]!r}")
    valores: list[float | None] = []
    for linea in lineas[1:]:
        if not linea.strip():
            continue
        if not linea.startswith("["):
            break  # empiezan las coordenadas
        for crudo in linea.split(",")[1:]:
            v = float(crudo)
            valores.append(None if abs(v) >= RELLENO else v)
    return valores


def ultima_hora(cliente: httpx.Client, coleccion: str) -> tuple[datetime, int]:
    """Última hora publicada (centro del promedio horario, UTC) y cantidad de horas de la serie."""
    try:
        das = cliente.get(f"{BASE}/{coleccion}.das")
        dds = cliente.get(f"{BASE}/{coleccion}.dds")
        das.raise_for_status()
        dds.raise_for_status()
    except httpx.HTTPError as error:
        raise ErrorGEOSFP(f"GEOS-FP no respondió ({coleccion}): {error}") from error
    maximo = re.search(r'time\s*\{[^}]*maximum\s+"([^"]+)"', das.text, re.S)
    largo = re.search(r"time\s*=\s*(\d+)", dds.text)
    if not maximo or not largo:
        raise ErrorGEOSFP(f"GEOS-FP no dice hasta qué hora publicó ({coleccion})")
    ultimo = datetime.strptime(maximo.group(1), "%H:%Mz%d%b%Y").replace(tzinfo=timezone.utc)
    return ultimo, int(largo.group(1))


def horas_del_dia(dia: date) -> list[datetime]:
    """Las 24 horas UTC (centro de cada promedio horario) del día local argentino."""
    inicio = datetime.combine(dia, time(0, 30), tzinfo=timezone.utc) - HUSO
    return [inicio + timedelta(hours=h) for h in range(24)]


def serie(cliente: httpx.Client, coleccion: str, variable: str, lat: float, lon: float,
          desde: date, hasta: date) -> dict[datetime, float | None]:
    """Valores horarios en la celda del lote entre el primer día y el último publicado (hora UTC -> valor)."""
    ultimo, largo = ultima_hora(cliente, coleccion)
    primera, final = horas_del_dia(desde)[0], min(horas_del_dia(hasta)[-1], ultimo)
    if final < primera:
        return {}
    i_fin = largo - 1 - round((ultimo - final).total_seconds() / 3600)
    i_ini = max(0, i_fin - round((final - primera).total_seconds() / 3600))
    i_lat, i_lon = celda(lat, lon)
    bloques = [(i, min(i + BLOQUE_HORAS - 1, i_fin)) for i in range(i_ini, i_fin + 1, BLOQUE_HORAS)]

    def pedir(bloque: tuple[int, int]) -> list[float | None]:
        url = f"{BASE}/{coleccion}.ascii?{variable}[{bloque[0]}:{bloque[1]}][{i_lat}][{i_lon}]"
        for intento in range(REINTENTOS + 1):
            try:
                r = cliente.get(url)
                r.raise_for_status()
                break
            except httpx.HTTPError as error:
                cae = isinstance(error, httpx.HTTPStatusError) and error.response.status_code < 500
                if cae or intento == REINTENTOS:
                    raise ErrorGEOSFP(f"GEOS-FP no respondió ({coleccion}/{variable}): {error}") from error
        valores = leer_ascii(r.text)
        if len(valores) != bloque[1] - bloque[0] + 1:
            raise ErrorGEOSFP(f"GEOS-FP devolvió {len(valores)} horas y se pidieron {bloque[1] - bloque[0] + 1}")
        return valores

    with ThreadPoolExecutor(max_workers=HILOS) as grupo:
        valores = [v for parte in grupo.map(pedir, bloques) for v in parte]
    return {final - timedelta(hours=i_fin - i): v for i, v in zip(range(i_ini, i_fin + 1), valores)}


def _observacion(lote_id: str, dia: date, variable: str, valor: float | None, horas: int, ultima: datetime | None,
                 parcial: str = "dudosa") -> Observacion:
    nota = NOTA_ET if variable == "et_mm_dia" else NOTA
    base = dict(lote_id=lote_id, fecha=dia, variable=variable, unidad=UNIDADES[variable], fuente="GEOS_FP",
                resolucion_m=RESOLUCION_M)
    if valor is None:
        motivo = "GEOS-FP todavía no publicó este día" if horas == 0 else \
            f"día incompleto ({horas} de 24 horas, hasta las {ultima:%H:%M} UTC): la suma del día quedaría corta"
        return Observacion(**base, valor=None, calidad="descartada", nota=f"{nota} · {motivo}")
    minimo, maximo = RANGOS[variable]
    if not minimo <= valor <= maximo:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"{nota} · valor fuera de rango ({valor:.1f} {UNIDADES[variable]})")
    if horas == 24:
        calidad = "dudosa" if variable in ORIENTATIVAS else "buena"
        extra = f" · {ORIENTATIVAS[variable]}" if variable in ORIENTATIVAS else ""
        return Observacion(**base, valor=round(valor, 2), calidad=calidad, nota=nota + extra)
    return Observacion(**base, valor=round(valor, 2), calidad=parcial,
                       nota=f"{nota} · día en curso: {horas} de 24 horas, hasta las {ultima:%H:%M} UTC")


def resumir_dia(lote_id: str, dia: date, temp: dict, radiacion: dict, lluvia: dict) -> list[Observacion]:
    """Temperatura máxima y mínima, radiación y lluvia del día local a partir de los valores horarios."""
    horas = horas_del_dia(dia)
    t = [temp[h] - 273.15 for h in horas if temp.get(h) is not None]
    sw = [radiacion[h] for h in horas if radiacion.get(h) is not None]
    pr = [lluvia[h] for h in horas if lluvia.get(h) is not None]

    def ultima(serie_: dict) -> datetime | None:
        presentes = [h for h in horas if serie_.get(h) is not None]
        return presentes[-1] + timedelta(minutes=30) if presentes else None

    completa = lambda valores: len(valores) == 24
    return [
        _observacion(lote_id, dia, "temp_max", max(t) if t else None, len(t), ultima(temp)),
        _observacion(lote_id, dia, "temp_min", min(t) if t else None, len(t), ultima(temp)),
        # radiación y lluvia son sumas del día: con el día incompleto la radiación se descarta (quedaría corta) y la
        # lluvia se da como "lluvia hasta esa hora", marcada dudosa
        _observacion(lote_id, dia, "radiacion", sum(sw) * 3600 / 1e6 if completa(sw) else None, len(sw),
                     ultima(radiacion)),
        _observacion(lote_id, dia, "lluvia_mm", sum(pr) * 3600 if pr else None, len(pr), ultima(lluvia)),
    ]


def resumir_et(lote_id: str, dia: date, evaporacion: dict) -> Observacion:
    """Evapotranspiración del día local: suma de las 24 horas. Con el día incompleto se descarta (quedaría corta)."""
    horas = horas_del_dia(dia)
    ev = [evaporacion[h] for h in horas if evaporacion.get(h) is not None]
    presentes = [h for h in horas if evaporacion.get(h) is not None]
    ultima = presentes[-1] + timedelta(minutes=30) if presentes else None
    return _observacion(lote_id, dia, "et_mm_dia", sum(ev) * 3600 if len(ev) == 24 else None, len(ev), ultima)


def validar_pedido(lat: float, lon: float, desde: date, hasta: date) -> None:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Latitud o longitud fuera de rango")
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise ValueError(f"El rango supera {MAX_DIAS} días")


def obtener_clima(lote_id: str, lat: float, lon: float, desde: date, hasta: date,
                  cliente: httpx.Client | None = None) -> list[Observacion]:
    """Clima diario del lote según GEOS-FP: una fila por día y variable, también para los días sin dato (null)."""
    validar_pedido(lat, lon, desde, hasta)
    propio = cliente is None
    cliente = cliente or httpx.Client(timeout=120, follow_redirects=True)
    try:
        series = {clave: serie(cliente, coleccion, variable, lat, lon, desde, hasta)
                  for clave, (coleccion, variable) in PEDIDOS.items()}
    finally:
        if propio:
            cliente.close()
    observaciones = []
    for i in range((hasta - desde).days + 1):
        dia = desde + timedelta(days=i)
        observaciones += resumir_dia(lote_id, dia, series["temp"], series["radiacion"], series["lluvia"])
    return observaciones


def obtener_et(lote_id: str, lat: float, lon: float, desde: date, hasta: date,
               cliente: httpx.Client | None = None) -> list[Observacion]:
    """Evapotranspiración diaria del lote según GEOS-FP: una fila por día, también para los días sin dato (null)."""
    validar_pedido(lat, lon, desde, hasta)
    propio = cliente is None
    cliente = cliente or httpx.Client(timeout=120, follow_redirects=True)
    try:
        evaporacion = serie(cliente, *PEDIDO_ET, lat, lon, desde, hasta)
    finally:
        if propio:
            cliente.close()
    return [resumir_et(lote_id, desde + timedelta(days=i), evaporacion) for i in range((hasta - desde).days + 1)]


SATELITES = [Satelite("POWER:GEOS_FP",
                      lambda lote, desde, hasta: obtener_clima(lote["id"], lote["lat"], lote["lon"], desde, hasta),
                      respaldo_de="POWER", al_dia=True),
             Satelite("ET:GEOS_FP",
                      lambda lote, desde, hasta: obtener_et(lote["id"], lote["lat"], lote["lon"], desde, hasta),
                      respaldo_de="ET", al_dia=True)]


# ---------- endpoint de prueba (spec 009): sin respaldos ----------

router = APIRouter(tags=["GEOS-FP (pruebas internas)"])


@router.get("/clima/geos-fp", response_model=list[Observacion])
def clima_del_dia(lote_id: str, lat: float, lon: float, desde: date, hasta: date) -> list[Observacion]:
    try:
        validar_pedido(lat, lon, desde, hasta)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener_clima(lote_id, lat, lon, desde, hasta)
    except ErrorGEOSFP as error:
        raise HTTPException(status_code=502, detail=str(error))


@router.get("/et/geos-fp", response_model=list[Observacion])
def et_del_dia(lote_id: str, lat: float, lon: float, desde: date, hasta: date) -> list[Observacion]:
    try:
        validar_pedido(lat, lon, desde, hasta)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener_et(lote_id, lat, lon, desde, hasta)
    except ErrorGEOSFP as error:
        raise HTTPException(status_code=502, detail=str(error))
