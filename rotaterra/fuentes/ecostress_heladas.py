"""Conector ECOSTRESS LST nocturna: heladas por zona del lote a 70 m (spec 053).

Satélite independiente (spec 009): hace su propio pedido a la NASA y no importa al ECOSTRESS de la ET,
aunque comparta con él la forma de leer los mosaicos (se repite acá a propósito).

VIIRS (spec 030) da un solo píxel de 1 km para todo el lote. ECOSTRESS mide la temperatura de superficie a
70 m, así que muestra **en qué parte del lote** hiela (los bajos). Pasa desde la Estación Espacial, sin
horario fijo: hay noches con dato y noches sin él. Complementa a VIIRS, no lo reemplaza.
"""

import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import httpx
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rotaterra.contrato import Observacion
from rotaterra.fuentes import earthdata
from rotaterra.fuentes.registro import Satelite
from rotaterra.geo import validar_poligono

PRODUCTO = "ECO_L2T_LSTE"     # temperatura de superficie en mosaicos de 70 m (LP DAAC); se usa la versión más nueva
CAPA_LST = "lst"              # kelvin
MASCARAS = ("cloud", "water")  # 1 = nube / agua
RELLENO_MASCARA = 255
RESOLUCION_M = 70
MAX_DIAS = 366
HILOS = 4
CERO_ABS = 273.15
KELVIN_MIN, KELVIN_MAX = 248.15, 343.15  # -25 a 70 °C: afuera es nube que se escapó a la máscara o relleno
UMBRAL_HELADA = 0.0
UMBRAL_BUENA = 60.0           # % de píxeles válidos del lote (mismos umbrales que ECOSTRESS ET y VIIRS)
UMBRAL_DESCARTADA = 20.0
NOCHE = (20, 8)               # hora solar: de 20 a 8 h es "noche" (supuesto, spec 053)
UNIDAD_T, UNIDAD_PCT = "°C", "%"


class ErrorECOSTRESSHeladas(Exception):
    """La NASA no respondió o los archivos no se pudieron leer."""


@dataclass
class Granulo:
    nombre: str
    inicio: datetime              # hora UTC de la pasada
    capas: dict[str, str]         # capa en minúsculas -> URL de descarga


@dataclass
class Zonas:
    minima: float | None          # °C del píxel más frío del lote
    mediana: float | None
    maxima: float | None
    helada_pct: float | None      # % de los píxeles válidos a 0 °C o menos
    validos_pct: float
    lugar_mas_frio: tuple[float, float] | None  # (lat, lon) del píxel más frío


# ---------- cálculo puro (testeable sin internet) ----------

def validar_pedido(poligono: dict, desde: date, hasta: date) -> None:
    validar_poligono(poligono)
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise ValueError(f"El rango supera {MAX_DIAS} días")


def hora_solar(inicio_utc: datetime, lon: float) -> datetime:
    """Hora solar local: hora UTC + longitud / 15 (en San Luis, unas 4 h 21 min menos)."""
    return inicio_utc + timedelta(hours=lon / 15)


def es_de_noche(solar: datetime) -> bool:
    desde, hasta = NOCHE
    return solar.hour >= desde or solar.hour < hasta


def noche_de(solar: datetime) -> date:
    """Una helada se fecha por la madrugada: una pasada de 20 a 24 h cuenta para la noche que termina al día siguiente."""
    return solar.date() + timedelta(days=1) if solar.hour >= NOCHE[0] else solar.date()


_HORA = re.compile(r"_(\d{8}T\d{6})_")


def hora_de_pasada(umm: dict, nombre: str) -> datetime:
    texto = umm.get("TemporalExtent", {}).get("RangeDateTime", {}).get("BeginningDateTime")
    if texto:
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).astimezone(timezone.utc)
    hallado = _HORA.search(nombre)
    if not hallado:
        raise ValueError(f"No se sabe la hora de la pasada del gránulo {nombre}")
    return datetime.strptime(hallado[1], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)


def capas_del_granulo(nombre: str, urls: list[str]) -> dict[str, str]:
    """Capa -> URL https, a partir de archivos como '<gránulo>_LST.tif'."""
    capas = {}
    for url in urls:
        archivo = url.split("?")[0].rsplit("/", 1)[-1]
        if not url.startswith("https://") or not archivo.lower().endswith(".tif"):
            continue
        base = archivo[:-4]
        capa = base[len(nombre) + 1:] if base.startswith(nombre + "_") else base.rsplit("_", 1)[-1]
        capas[capa.lower()] = url
    return capas


def pixeles_validos(kelvin: np.ndarray, mascaras: dict[str, np.ndarray]) -> np.ndarray:
    """True donde hay temperatura en el rango físico, sin nube y sin agua."""
    with np.errstate(invalid="ignore"):
        validos = np.isfinite(kelvin) & (kelvin >= KELVIN_MIN) & (kelvin <= KELVIN_MAX)
    for mascara in mascaras.values():
        validos &= mascara != 1
    return validos


def mascara_del_lote(geometria, forma: tuple[int, int], transformada) -> tuple[np.ndarray, bool]:
    """Píxeles cuyo centro cae en el lote. Si ninguno (lote más chico que un píxel), los que el lote toca."""
    import shapely

    filas, columnas = np.indices(forma)
    x, y = transformada * (columnas + 0.5, filas + 0.5)
    dentro = shapely.contains_xy(geometria, x, y)
    if dentro.any():
        return dentro, False
    x0, y0 = transformada * (columnas, filas)
    x1, y1 = transformada * (columnas + 1, filas + 1)
    cajas = shapely.box(np.minimum(x0, x1), np.minimum(y0, y1), np.maximum(x0, x1), np.maximum(y0, y1))
    return shapely.intersects(geometria, cajas), True


def zonas(kelvin: np.ndarray, dentro_lote: np.ndarray, validos: np.ndarray,
          lat: np.ndarray | None = None, lon: np.ndarray | None = None) -> Zonas:
    """Temperatura mínima, mediana y máxima del lote, y qué parte queda a 0 °C o menos."""
    total = int(dentro_lote.sum())
    usar = dentro_lote & validos
    pct = 100.0 * int(usar.sum()) / total if total else 0.0
    if not usar.any():
        return Zonas(None, None, None, None, pct, None)
    celsius = kelvin - CERO_ABS
    valores = celsius[usar]
    lugar = None
    if lat is not None and lon is not None:
        fila, col = np.unravel_index(np.argmin(np.where(usar, celsius, np.inf)), celsius.shape)
        lugar = (round(float(lat[fila, col]), 5), round(float(lon[fila, col]), 5))
    helada = 100.0 * float((valores <= UMBRAL_HELADA).sum()) / valores.size
    return Zonas(float(valores.min()), float(np.median(valores)), float(valores.max()), helada, pct, lugar)


def a_observaciones(lote_id: str, fecha: date, z: Zonas, detalle: str) -> list[Observacion]:
    """Dos datos por noche: la mínima del lote a 70 m y qué % del lote quedó a 0 °C o menos."""
    base = dict(lote_id=lote_id, fecha=fecha, fuente="ECOSTRESS", resolucion_m=RESOLUCION_M)
    if z.validos_pct < UMBRAL_DESCARTADA or z.minima is None:
        nota = f"Nubes o franja del satélite al costado del lote (válidos {z.validos_pct:.0f}%) · {detalle}"
        return [Observacion(**base, variable="temp_sup_min_70m_c", unidad=UNIDAD_T, valor=None,
                            calidad="descartada", nota=nota),
                Observacion(**base, variable="helada_superficie_pct", unidad=UNIDAD_PCT, valor=None,
                            calidad="descartada", nota=nota)]
    calidad = "buena" if z.validos_pct >= UMBRAL_BUENA else "dudosa"
    lugar = f" · punto más frío en {z.lugar_mas_frio[0]}, {z.lugar_mas_frio[1]}" if z.lugar_mas_frio else ""
    riesgo = " · riesgo de helada (≤ 0 °C de superficie)" if z.minima <= UMBRAL_HELADA else ""
    texto = (f"ECOSTRESS LST nocturna a 70 m (temperatura de superficie, no del aire) · mínima {z.minima:.1f} · "
             f"mediana {z.mediana:.1f} · máxima {z.maxima:.1f} °C · {z.helada_pct:.0f}% del lote a 0 °C o menos"
             f"{lugar} · válidos {z.validos_pct:.0f}%{riesgo} · {detalle}")
    return [Observacion(**base, variable="temp_sup_min_70m_c", unidad=UNIDAD_T, valor=round(z.minima, 1),
                        calidad=calidad, nota=texto),
            Observacion(**base, variable="helada_superficie_pct", unidad=UNIDAD_PCT, valor=round(z.helada_pct, 1),
                        calidad=calidad, nota=texto)]


def quedarse_con_la_mejor(candidatas: list[tuple[list[Observacion], float]]) -> list[Observacion]:
    """Una noche, un par de datos: el de la pasada con más píxeles válidos."""
    por_noche: dict[date, list[tuple[list[Observacion], float]]] = {}
    for par, pct in candidatas:
        por_noche.setdefault(par[0].fecha, []).append((par, pct))
    elegidas = []
    for fecha in sorted(por_noche):
        opciones = por_noche[fecha]
        par, _ = max(opciones, key=lambda o: (o[0][0].valor is not None, o[1]))
        if len(opciones) > 1:
            extra = f" · {len(opciones)} pasadas esa noche, queda la más limpia"
            par = [o.model_copy(update={"nota": o.nota + extra}) for o in par]
        elegidas += par
    return elegidas


# ---------- acceso a la NASA ----------

def configurar_credenciales(cliente: httpx.Client | None = None) -> httpx.Client:
    cliente = earthdata.cliente_autorizado(cliente)
    os.environ.update({"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR", "GDAL_HTTP_MAX_RETRY": "3",
                       "GDAL_HTTP_RETRY_DELAY": "2"})
    return cliente


def enlace_firmado(cliente: httpx.Client, url: str) -> str:
    """LP DAAC redirige a un enlace firmado de CloudFront; GDAL lee ese enlace y el token nunca llega a GDAL."""
    respuesta = cliente.get(url, headers={"Range": "bytes=0-0"}, follow_redirects=False)
    if respuesta.is_redirect:
        return respuesta.headers["location"]
    respuesta.raise_for_status()
    return url


_FIRMA = re.compile(r"(https?://[^\s'\"?]+)\?[^\s'\"]*")


def sin_firma(texto: str) -> str:
    return _FIRMA.sub(r"\1", texto)


def buscar_granulos(cliente: httpx.Client, desde: date, hasta: date,
                    caja: tuple[float, float, float, float]) -> list[Granulo]:
    coleccion = earthdata.coleccion_vigente(cliente, PRODUCTO)
    if coleccion is None:
        raise ErrorECOSTRESSHeladas(f"CMR no tiene la colección {PRODUCTO}")
    params = {"collection_concept_id": coleccion, "page_size": 500, "sort_key": "start_date",
              "bounding_box": ",".join(str(c) for c in caja),
              "temporal": f"{desde.isoformat()}T00:00:00Z,{hasta.isoformat()}T23:59:59Z"}
    granulos, encabezados = [], {}
    while True:
        respuesta = cliente.get(f"{earthdata.URL_CMR}/granules.umm_json", params=params, headers=encabezados)
        respuesta.raise_for_status()
        items = respuesta.json()["items"]
        for item in items:
            umm = item["umm"]
            nombre = umm["GranuleUR"]
            urls = [u["URL"] for u in umm.get("RelatedUrls", []) if u.get("Type") == "GET DATA"]
            granulos.append(Granulo(nombre, hora_de_pasada(umm, nombre), capas_del_granulo(nombre, urls)))
        siguiente = respuesta.headers.get("CMR-Search-After")
        if not siguiente or len(items) < params["page_size"]:
            return granulos
        encabezados = {"CMR-Search-After": siguiente}


def leer(granulo: Granulo, poligono: dict, cliente: httpx.Client | None = None) -> dict:
    """Ventana del lote de la LST y sus máscaras (sin cliente: archivos locales), más lat/lon de cada píxel."""
    import rasterio
    from rasterio.warp import transform, transform_geom
    from rasterio.windows import from_bounds
    from shapely.geometry import shape

    datos: dict = {"mascaras": {}}
    for capa in (CAPA_LST, *[m for m in MASCARAS if m in granulo.capas]):
        href = granulo.capas[capa]
        enlace = enlace_firmado(cliente, href) if cliente is not None and href.startswith("http") else href
        with rasterio.open(enlace) as fuente:
            geom = transform_geom("EPSG:4326", fuente.crs, poligono)
            ventana = from_bounds(*shape(geom).bounds, transform=fuente.transform).round_offsets().round_lengths()
            if capa != CAPA_LST:
                datos["mascaras"][capa] = fuente.read(1, window=ventana, boundless=True, fill_value=RELLENO_MASCARA)
                continue
            leido = fuente.read(1, window=ventana, boundless=True, masked=True).astype("float64")
            datos["kelvin"] = leido.filled(np.nan) * fuente.scales[0] + fuente.offsets[0]
            forma, transformada = datos["kelvin"].shape, fuente.window_transform(ventana)
            datos["lote"], datos["todo_tocado"] = mascara_del_lote(shape(geom), forma, transformada)
            filas, columnas = np.indices(forma)
            x, y = transformada * (columnas + 0.5, filas + 0.5)
            lon, lat = transform(fuente.crs, "EPSG:4326", x.ravel().tolist(), y.ravel().tolist())
            datos["lat"], datos["lon"] = np.array(lat).reshape(forma), np.array(lon).reshape(forma)
    return datos


def procesar(lote_id: str, poligono: dict, lon: float, granulo: Granulo,
             cliente: httpx.Client | None = None) -> tuple[list[Observacion], float]:
    datos = leer(granulo, poligono, cliente)
    # una máscara que cae afuera del archivo viene en 255: eso no es nube, es que la franja no pasó por ahí
    validos = pixeles_validos(datos["kelvin"], datos["mascaras"])
    z = zonas(datos["kelvin"], datos["lote"], validos, datos["lat"], datos["lon"])
    solar = hora_solar(granulo.inicio, lon)
    detalle = f"pasada {granulo.inicio:%Y-%m-%d %H:%M} UTC ({solar:%H:%M} hora solar)"
    if z.minima is None:
        sin_dato = 100.0 * float((datos["lote"] & ~np.isfinite(datos["kelvin"])).sum()) / max(int(datos["lote"].sum()), 1)
        nube = datos["mascaras"].get("cloud")
        con_nube = 100.0 * float((datos["lote"] & (nube == 1)).sum()) / max(int(datos["lote"].sum()), 1) if nube is not None else 0.0
        detalle += f" · nube en {con_nube:.0f}% del lote · sin medición en {sin_dato:.0f}%"
    if datos["todo_tocado"]:
        detalle += " · lote más chico que un píxel: se usan los píxeles que toca"
    detalle += f" · {granulo.nombre}"
    return a_observaciones(lote_id, noche_de(solar), z, detalle), z.validos_pct


def obtener(lote_id: str, poligono: dict, desde: date, hasta: date, cliente: httpx.Client | None = None,
            hilos: int = HILOS) -> list[Observacion]:
    """Por cada noche con pasada de ECOSTRESS: mínima del lote a 70 m y % del lote a 0 °C o menos."""
    from shapely.geometry import shape

    validar_pedido(poligono, desde, hasta)
    geometria = shape(poligono)
    lon = geometria.centroid.x
    try:
        cliente = configurar_credenciales(cliente)
        pedidos = [g for g in buscar_granulos(cliente, desde - timedelta(days=1), hasta + timedelta(days=1),
                                              geometria.bounds)
                   if CAPA_LST in g.capas and es_de_noche(hora_solar(g.inicio, lon))
                   and desde <= noche_de(hora_solar(g.inicio, lon)) <= hasta]
    except earthdata.FaltanCredenciales:
        raise
    except (httpx.HTTPError, KeyError, ValueError, earthdata.ErrorNASA) as error:
        raise ErrorECOSTRESSHeladas(f"No se pudo buscar ECOSTRESS en CMR: {error}") from error

    def uno(granulo):
        try:
            return procesar(lote_id, poligono, lon, granulo, cliente), None
        except Exception as error:  # un archivo ilegible no inventa nada: queda descartado con el motivo
            return None, sin_firma(f"{type(error).__name__}: {error}")

    with ThreadPoolExecutor(max_workers=hilos) as grupo:
        resultados = list(grupo.map(uno, pedidos))
    errores = [e for _, e in resultados if e]
    if pedidos and len(errores) == len(pedidos):
        raise ErrorECOSTRESSHeladas(f"No se pudo leer ningún archivo de ECOSTRESS: {errores[0]}")
    candidatas = []
    for granulo, (hecho, error) in zip(pedidos, resultados):
        if hecho:
            candidatas.append(hecho)
        else:
            vacia = Zonas(None, None, None, None, 0.0, None)
            par = a_observaciones(lote_id, noche_de(hora_solar(granulo.inicio, lon)), vacia,
                                  f"No se pudo leer el archivo: {error} · {granulo.nombre}")
            candidatas.append((par, -1.0))
    return quedarse_con_la_mejor(candidatas)


# ---------- conexión con el núcleo (spec 009) ----------

# Fuente propia de dos variables nuevas (temp_sup_min_70m_c y helada_superficie_pct). No es respaldo de VIIRS:
# VIIRS da todas las noches un píxel de 1 km; ECOSTRESS da algunas noches el detalle dentro del lote.
SATELITES = [Satelite("ECOSTRESS_LST", lambda lote, desde, hasta: obtener(lote["id"], lote["poligono"], desde, hasta))]

router = APIRouter(tags=["ECOSTRESS heladas (pruebas internas)"])


class PedidoHeladas(BaseModel):
    lote_id: str
    poligono: dict
    desde: date
    hasta: date


@router.post("/heladas-por-zona", response_model=list[Observacion])
def heladas_por_zona(pedido: PedidoHeladas) -> list[Observacion]:
    """Temperatura de superficie nocturna a 70 m: mínima del lote y % del lote a 0 °C o menos, por noche."""
    try:
        validar_pedido(pedido.poligono, pedido.desde, pedido.hasta)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener(pedido.lote_id, pedido.poligono, pedido.desde, pedido.hasta)
    except earthdata.FaltanCredenciales as error:
        raise HTTPException(status_code=503, detail=str(error))
    except ErrorECOSTRESSHeladas as error:
        raise HTTPException(status_code=502, detail=str(error))
