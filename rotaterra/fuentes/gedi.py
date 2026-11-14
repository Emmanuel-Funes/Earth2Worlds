"""Conector GEDI: cobertura y estructura de la vegetación en la zona del lote, medidas con láser (spec 059).

GEDI es el láser (lidar) de la NASA en la Estación Espacial. Cada disparo mide un círculo de ~25 m y dice qué
fracción del suelo tapa la vegetación (`cover`) y cuánta superficie de hojas y ramas hay por m² de suelo (`pai`).
Los disparos van en líneas separadas ~600 m y la Estación no pasa siempre por el mismo lugar: en un lote de 25 ha
caen de 0 a 7 disparos por pasada. Por eso se mira la **zona** (el lote más 2 km alrededor) y los últimos 3 años,
y el lote solo cuando tiene disparos buenos suficientes.

Sirve para ver montes, cortinas forestales y pastizales de la zona (estructura que el NDVI no muestra). En cultivos
anuales la cobertura que mide GEDI es baja (1 a 12 %): no es un indicador del cultivo.

Producto GEDI02_B (L2B, LP DAAC). No se baja el archivo de cada pasada (~1 GB): el servicio Harmony de la NASA
recorta en sus servidores la zona y solo 6 variables por haz (~1,4 MB en total). Tarda ~3 minutos.
"""

import io
import threading
import time
from datetime import date, datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rotaterra.geo import validar_poligono as validar_geojson
from rotaterra.contrato import Observacion
from rotaterra.fuentes import earthdata
from rotaterra.fuentes.registro import Satelite

PRODUCTO = "GEDI02_B"
URL_HARMONY = "https://harmony.earthdata.nasa.gov"
HACES = ("BEAM0000", "BEAM0001", "BEAM0010", "BEAM0011", "BEAM0101", "BEAM0110", "BEAM1000", "BEAM1011")
CAMPOS = ("lat_lowestmode", "lon_lowestmode", "cover", "pai", "l2b_quality_flag_rel3", "geolocation/delta_time")
ZONA_KM = 2.0
ANIOS = 3
ESPERA_S = 10
TOPE_S = 900
EPOCA_GEDI = datetime(2018, 1, 1, tzinfo=timezone.utc)  # delta_time: segundos desde el 1/1/2018 UTC
MIN_ZONA = 30  # disparos buenos para que la zona sea "buena"
MIN_LOTE = 5   # disparos buenos dentro del lote para dar un valor del lote
MONTE = 0.30   # cobertura desde la que un disparo es vegetación leñosa (monte, cortina); supuesto a validar
RESOLUCION_M = 25


class ErrorGEDI(Exception):
    """Harmony o el LP DAAC no respondieron o respondieron algo ilegible."""


def validar_poligono(poligono: dict) -> None:
    from shapely.geometry import shape

    validar_geojson(poligono)
    oeste, sur, este, norte = shape(poligono).bounds
    if sur < -51.6 or norte > 51.6:  # la órbita de la Estación cubre de 51,6° S a 51,6° N
        raise ValueError("GEDI solo mide entre 51,6° S y 51,6° N")


def caja_zona(poligono: dict, km: float = ZONA_KM) -> tuple[float, float, float, float]:
    """(oeste, sur, este, norte) del lote agrandado `km` hacia cada lado."""
    import math

    from shapely.geometry import shape

    oeste, sur, este, norte = shape(poligono).bounds
    dlat = km / 111.32
    dlon = km / (111.32 * math.cos(math.radians((sur + norte) / 2)))
    return (round(oeste - dlon, 4), round(sur - dlat, 4), round(este + dlon, 4), round(norte + dlat, 4))


def variables() -> str:
    """Lista de variables para Harmony, con las barras codificadas como pide su API."""
    return ",".join(f"%2F{haz}%2F{campo.replace('/', '%2F')}" for haz in HACES for campo in CAMPOS)


# ---------- pedido a Harmony (red) ----------

def pedir_recorte(cliente: httpx.Client, coleccion: str, caja: tuple[float, float, float, float], desde: date,
                  hasta: date) -> str:
    """Manda el trabajo a Harmony y devuelve su número."""
    oeste, sur, este, norte = caja
    url = f"{URL_HARMONY}/{coleccion}/ogc-api-coverages/1.0.0/collections/{variables()}/coverage/rangeset"
    respuesta = cliente.get(url, params={"subset": [f"lat({sur}:{norte})", f"lon({oeste}:{este})",
                                                    f'time("{desde.isoformat()}T00:00:00Z":"{hasta.isoformat()}T23:59:59Z")'],
                                         "forceAsync": "true"}, follow_redirects=False)
    if respuesta.status_code not in (200, 202, 303):
        raise ErrorGEDI(f"Harmony rechazó el pedido ({respuesta.status_code}): {respuesta.text[:200]}")
    destino = respuesta.headers.get("location", "")
    if "/jobs/" not in destino:
        try:
            destino = respuesta.json()["links"][0]["href"]
        except (ValueError, KeyError, IndexError):
            raise ErrorGEDI(f"Harmony no devolvió el número de trabajo: {respuesta.text[:200]}")
    return destino.rsplit("/jobs/", 1)[1].split("?")[0]


def esperar(cliente: httpx.Client, trabajo: str, tope_s: float = TOPE_S, espera_s: float = ESPERA_S) -> list[str]:
    """Espera a que Harmony termine y devuelve las direcciones de los recortes."""
    fin = time.monotonic() + tope_s
    while True:
        estado = cliente.get(f"{URL_HARMONY}/jobs/{trabajo}").json()
        if estado["status"] in ("successful", "complete_with_errors"):
            return [l["href"] for l in estado.get("links", []) if l.get("rel") == "data"]
        if estado["status"] in ("failed", "canceled"):
            raise ErrorGEDI(f"Harmony no pudo recortar GEDI: {estado.get('message', '')[:200]}")
        if time.monotonic() >= fin:
            raise ErrorGEDI(f"Harmony no terminó en {tope_s:.0f} s (va {estado.get('progress', 0)} %)")
        time.sleep(espera_s)


def leer_recorte(contenido: bytes) -> list[dict]:
    """Disparos de un recorte: lat, lon, cover, pai, calidad y fecha."""
    import h5py

    disparos = []
    with h5py.File(io.BytesIO(contenido), "r") as archivo:
        for haz in HACES:
            if haz not in archivo or "lat_lowestmode" not in archivo[haz]:
                continue  # un haz sin disparos en la zona viene vacío
            g = archivo[haz]
            columnas = [g[c][:] for c in CAMPOS]
            for lat, lon, cover, pai, calidad, segundos in zip(*columnas):
                disparos.append({"lat": float(lat), "lon": float(lon), "cover": float(cover), "pai": float(pai),
                                 "buena": int(calidad) == 1,
                                 "fecha": (EPOCA_GEDI + timedelta(seconds=float(segundos))).date()})
    return disparos


# ---------- cálculos (sin red) ----------

def _percentil(valores: list[float], p: float) -> float:
    ordenados = sorted(valores)
    k = (len(ordenados) - 1) * p / 100
    piso = int(k)
    techo = min(piso + 1, len(ordenados) - 1)
    return ordenados[piso] + (ordenados[techo] - ordenados[piso]) * (k - piso)


def validos(disparos: list[dict]) -> list[dict]:
    """Calidad 1 de la NASA y valores físicos (cover 0-1, pai 0-12); el relleno (-9999) queda afuera."""
    return [d for d in disparos if d["buena"] and 0 <= d["cover"] <= 1 and 0 <= d["pai"] <= 12]


def a_observaciones(lote_id: str, poligono: dict, disparos: list[dict], desde: date, hasta: date) -> list[Observacion]:
    from shapely.geometry import Point, shape

    lote = shape(poligono)
    buenos = validos(disparos)
    en_lote = [d for d in buenos if lote.contains(Point(d["lon"], d["lat"]))]
    pasadas = len({d["fecha"] for d in disparos})
    contexto = (f"GEDI L2B (NASA, láser de la Estación Espacial), {desde:%d/%m/%Y} a {hasta:%d/%m/%Y} · zona = lote + "
                f"{ZONA_KM:g} km · {len(buenos)} disparos buenos de {len(disparos)} en {pasadas} pasadas")
    fecha = max((d["fecha"] for d in buenos), default=hasta)
    base = dict(lote_id=lote_id, fecha=fecha, fuente="GEDI", resolucion_m=RESOLUCION_M)

    def obs(variable, unidad, valor, n, minimo, nota):
        if n < 1 or valor is None:
            return Observacion(**base, variable=variable, unidad=unidad, valor=None, calidad="descartada",
                               nota=f"{nota} · sin disparos buenos · {contexto}")
        decimales = 2 if unidad == "m²/m²" else 1
        return Observacion(**base, variable=variable, unidad=unidad, valor=round(valor, decimales),
                           calidad="buena" if n >= minimo else "dudosa",
                           nota=f"{nota} · {n} disparos" + ("" if n >= minimo else f" (< {minimo})") + f" · {contexto}")

    cover = [d["cover"] * 100 for d in buenos]
    pai = [d["pai"] for d in buenos]
    lote_cover = [d["cover"] * 100 for d in en_lote]
    return [
        obs("gedi_cobertura_zona_pct", "%", _percentil(cover, 50) if cover else None, len(cover), MIN_ZONA,
            "Cobertura de la vegetación en la zona, mediana de los disparos (fracción del suelo tapada vista desde arriba) "
            "· dato de la ZONA, no del lote"),
        obs("gedi_cobertura_zona_p90_pct", "%", _percentil(cover, 90) if cover else None, len(cover), MIN_ZONA,
            "Cobertura de la vegetación en la zona, el 10 % más tapado (montes, cortinas) · dato de la ZONA"),
        obs("gedi_monte_zona_pct", "%", 100 * sum(c >= MONTE * 100 for c in cover) / len(cover) if cover else None,
            len(cover), MIN_ZONA, f"Disparos con cobertura ≥ {MONTE * 100:g} % (vegetación leñosa: monte, cortina, "
                                  f"arbustal; supuesto a validar) · dato de la ZONA"),
        obs("gedi_pai_zona", "m²/m²", _percentil(pai, 50) if pai else None, len(pai), MIN_ZONA,
            "Índice de área de planta (hojas y ramas por m² de suelo), mediana de la zona · dato de la ZONA"),
        obs("gedi_cobertura_lote_pct", "%", _percentil(lote_cover, 50) if lote_cover else None, len(lote_cover),
            MIN_LOTE, "Cobertura de la vegetación dentro del lote, mediana de los disparos que cayeron adentro"),
    ]


# ---------- principal ----------

_MEMORIA: dict[str, list[dict]] = {}
_CANDADO = threading.Lock()


def _clave(poligono: dict) -> str:
    from shapely.geometry import shape

    return ",".join(f"{v:.5f}" for v in shape(poligono).bounds)


def obtener(lote_id: str, poligono: dict, hoy: date | None = None, cliente: httpx.Client | None = None) -> list[Observacion]:
    """Cobertura y estructura de la vegetación de la zona del lote en los últimos 3 años. Se guarda en memoria por
    lote: GEDI pasa cada varias semanas, así que el mismo lote no se vuelve a pedir."""
    validar_poligono(poligono)
    hoy = hoy or date.today()
    desde, hasta = date(hoy.year - ANIOS, hoy.month, 1), hoy
    clave = _clave(poligono)
    with _CANDADO:
        disparos = _MEMORIA.get(clave)
    if disparos is None:
        try:
            cliente = earthdata.cliente_autorizado(cliente)
            coleccion = earthdata.coleccion_vigente(cliente, PRODUCTO)
            if not coleccion:
                raise ErrorGEDI(f"CMR no tiene el producto {PRODUCTO}")
            trabajo = pedir_recorte(cliente, coleccion, caja_zona(poligono), desde, hasta)
            disparos = []
            for url in esperar(cliente, trabajo):
                respuesta = cliente.get(url)
                respuesta.raise_for_status()
                disparos += leer_recorte(respuesta.content)
        except earthdata.FaltanCredenciales:
            raise
        except (httpx.HTTPError, ValueError, KeyError, OSError, earthdata.ErrorNASA) as error:
            raise ErrorGEDI(f"No se pudo leer GEDI: {type(error).__name__}: {error}") from error
        with _CANDADO:
            _MEMORIA[clave] = disparos
    return a_observaciones(lote_id, poligono, disparos, desde, hasta)


# ---------- conexión con el núcleo (spec 009) ----------
# Fuente propia (no es respaldo de nadie). No usa el período del pedido: siempre los últimos 3 años.

SATELITES = [Satelite("GEDI", lambda lote, desde, hasta: obtener(lote["id"], lote["poligono"]))]

router = APIRouter(tags=["GEDI (pruebas internas)"])


class PedidoGEDI(BaseModel):
    lote_id: str
    poligono: dict


@router.post("/vegetacion-gedi", response_model=list[Observacion])
def vegetacion_gedi(pedido: PedidoGEDI) -> list[Observacion]:
    """Cobertura y estructura de la vegetación (GEDI) en el lote y 2 km alrededor. Tarda ~3 minutos la primera vez."""
    try:
        validar_poligono(pedido.poligono)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener(pedido.lote_id, pedido.poligono)
    except earthdata.FaltanCredenciales as error:
        raise HTTPException(status_code=503, detail=str(error))
    except ErrorGEDI as error:
        raise HTTPException(status_code=502, detail=str(error))
