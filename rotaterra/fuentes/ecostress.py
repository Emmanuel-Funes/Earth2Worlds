"""Conector ECOSTRESS: evapotranspiración diaria y estrés hídrico (ESI) del lote a 70 m (spec 018).

Primer respaldo de la ET principal: si la principal falla, entra ECOSTRESS; si tampoco trae datos, entra FAO-56.
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

RESOLUCION_M = 70
MAX_DIAS = 366
HILOS = 4
UMBRAL_BUENA = 60.0       # % de píxeles válidos: mismos umbrales que HLS
UMBRAL_DESCARTADA = 20.0
HORAS_DE_SOL = (9, 16)    # supuesto (spec 018): pasada fuera de 9 a 16 h solar → a lo sumo "dudosa"


@dataclass(frozen=True)
class Producto:
    nombre: str                  # nombre corto en CMR (LP DAAC, colección 2 en mosaicos)
    capas: tuple[str, ...]       # nombres posibles de la capa (sin distinguir mayúsculas)
    unidad: str
    rango: tuple[float, float]   # rango físico: afuera el píxel es inválido (supuesto, spec 018)
    explicacion: str


PRODUCTOS = {
    "et_mm_dia": Producto("ECO_L3T_JET", ("ETdaily", "ET_daily"), "mm/día", (0.0, 20.0),
                          "ET del día de la pasada (ensamble JET)"),
    "esi": Producto("ECO_L4T_ESI", ("ESI",), "índice (0 a 1)", (0.0, 2.0),
                    "ESI = ET real / ET potencial: 0 = estrés máximo, 1 = sin estrés"),
}
# máscaras que pueden venir en el mismo gránulo: 1 = nube / agua
MASCARAS = ("cloud", "water")
RELLENO_MASCARA = 255


class ErrorECOSTRESS(Exception):
    """La NASA no respondió o los archivos no se pudieron leer."""


@dataclass
class Granulo:
    nombre: str
    producto: str
    inicio: datetime              # hora UTC de la pasada
    capas: dict[str, str]         # capa en minúsculas -> URL de descarga


@dataclass
class Resumen:
    mediana: float | None
    media: float | None
    p10: float | None
    p90: float | None
    validos_pct: float


# ---------- cálculo puro (testeable sin internet) ----------

def validar_pedido(poligono: dict, desde: date, hasta: date) -> None:
    validar_poligono(poligono)
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise ValueError(f"El rango supera {MAX_DIAS} días")


def hora_solar(inicio_utc: datetime, lon: float) -> datetime:
    """Hora solar local de la pasada: hora UTC + longitud / 15 (en San Luis, unas 4 h 21 min menos)."""
    return inicio_utc + timedelta(hours=lon / 15)


def fecha_local(inicio_utc: datetime, lon: float) -> date:
    """Día de la pasada en hora solar local."""
    return hora_solar(inicio_utc, lon).date()


_HORA = re.compile(r"_(\d{8}T\d{6})_")


def hora_de_pasada(umm: dict, nombre: str) -> datetime:
    """Hora UTC de la pasada: la de CMR o, si falta, la que figura en el nombre del gránulo."""
    rango = umm.get("TemporalExtent", {}).get("RangeDateTime", {})
    texto = rango.get("BeginningDateTime")
    if texto:
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).astimezone(timezone.utc)
    hallado = _HORA.search(nombre)
    if not hallado:
        raise ValueError(f"No se sabe la hora de la pasada del gránulo {nombre}")
    return datetime.strptime(hallado[1], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)


def capas_del_granulo(nombre: str, urls: list[str]) -> dict[str, str]:
    """Capa -> URL https, a partir de archivos como '<gránulo>_ETdaily.tif'."""
    capas = {}
    for url in urls:
        archivo = url.split("?")[0].rsplit("/", 1)[-1]
        if not url.startswith("https://") or not archivo.lower().endswith(".tif"):
            continue
        base = archivo[:-4]
        capa = base[len(nombre) + 1:] if base.startswith(nombre + "_") else base.rsplit("_", 1)[-1]
        capas[capa.lower()] = url
    return capas


def capa_de(producto: Producto, granulo: Granulo) -> str | None:
    for capa in producto.capas:
        if capa.lower() in granulo.capas:
            return capa.lower()
    return None


def pixeles_validos(dato: np.ndarray, producto: Producto, mascaras: dict[str, np.ndarray]) -> np.ndarray:
    """True donde el valor es un número en el rango físico, sin nube y sin agua."""
    minimo, maximo = producto.rango
    with np.errstate(invalid="ignore"):
        validos = np.isfinite(dato) & (dato >= minimo) & (dato <= maximo)
    for mascara in mascaras.values():
        validos &= mascara != 1
    return validos


def mascara_del_lote(geometria, forma: tuple[int, int], transformada) -> tuple[np.ndarray, bool]:
    """Píxeles cuyo centro cae en el lote. Si ninguno (lote más chico que un píxel), los que el lote toca.

    Se calcula con shapely y no con el rasterizado de GDAL, que da avisos falsos cuando se lee en paralelo.
    """
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


def resumir(dato: np.ndarray, dentro_lote: np.ndarray, validos: np.ndarray) -> Resumen:
    """Estadísticas sobre los píxeles del lote que son válidos."""
    total = int(dentro_lote.sum())
    if total == 0:
        return Resumen(None, None, None, None, 0.0)
    valores = dato[dentro_lote & validos]
    pct = 100.0 * valores.size / total
    if valores.size == 0:
        return Resumen(None, None, None, None, pct)
    p10, mediana, p90 = np.percentile(valores, [10, 50, 90])
    return Resumen(float(mediana), float(valores.mean()), float(p10), float(p90), pct)


def a_observacion(lote_id: str, fecha: date, variable: str, r: Resumen, detalle: str) -> Observacion:
    producto = PRODUCTOS[variable]
    base = dict(lote_id=lote_id, fecha=fecha, variable=variable, unidad=producto.unidad,
                fuente="ECOSTRESS", resolucion_m=RESOLUCION_M)
    if r.validos_pct < UMBRAL_DESCARTADA or r.mediana is None:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"Solo {r.validos_pct:.0f}% de píxeles válidos (nube, agua o sin dato) · {detalle}")
    texto = (f"Respaldo de la ET · {producto.explicacion} · media {r.media:.2f} · p10 {r.p10:.2f} · "
             f"p90 {r.p90:.2f} · válidos {r.validos_pct:.0f}% · {detalle}")
    if r.validos_pct < UMBRAL_BUENA:
        return Observacion(**base, valor=round(r.mediana, 3), calidad="dudosa",
                           nota=f"Lote parcialmente cubierto · {texto}")
    return Observacion(**base, valor=round(r.mediana, 3), calidad="buena", nota=texto)


def quedarse_con_la_mejor(candidatas: list[tuple[Observacion, float]]) -> list[Observacion]:
    """Una observación por fecha y variable: la de más píxeles válidos; la nota dice cuántas pasadas hubo."""
    por_clave: dict[tuple[date, str], list[tuple[Observacion, float]]] = {}
    for obs, pct in candidatas:
        por_clave.setdefault((obs.fecha, obs.variable), []).append((obs, pct))
    elegidas = []
    for clave in sorted(por_clave):
        opciones = por_clave[clave]
        obs, _ = max(opciones, key=lambda o: (o[0].valor is not None, o[1]))
        if len(opciones) > 1:
            obs = obs.model_copy(update={"nota": f"{obs.nota} · {len(opciones)} pasadas ese día, queda la más limpia"})
        elegidas.append(obs)
    return elegidas


# ---------- acceso a la NASA ----------

def configurar_credenciales(cliente: httpx.Client | None = None) -> httpx.Client:
    """Cliente con el token de Earthdata del núcleo, y GDAL listo para leer COG por HTTP."""
    cliente = earthdata.cliente_autorizado(cliente)
    os.environ.update({
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "GDAL_HTTP_MAX_RETRY": "3",
        "GDAL_HTTP_RETRY_DELAY": "2",
    })
    return cliente


def enlace_firmado(cliente: httpx.Client, url: str) -> str:
    """LP DAAC redirige cada archivo a un enlace firmado de CloudFront que no pide credenciales.

    GDAL no sigue bien esa redirección con el token (lo mismo que pasó con HLS), así que la
    resolvemos con httpx y GDAL lee el enlace firmado directo. El token nunca llega a GDAL.
    """
    respuesta = cliente.get(url, headers={"Range": "bytes=0-0"}, follow_redirects=False)
    if respuesta.is_redirect:
        loc = respuesta.headers["location"]
        if loc.startswith("file:///"):
            return loc[8:] if len(loc) > 9 and loc[9] == ":" else loc[7:]
        return loc
    respuesta.raise_for_status()
    return url


_FIRMA = re.compile(r"(https?://[^\s'\"?]+)\?[^\s'\"]*")


def sin_firma(texto: str) -> str:
    """Saca la parte firmada (?Policy=…&Signature=…) de los enlaces de CloudFront antes de guardar o mostrar."""
    return _FIRMA.sub(r"\1", texto)


def buscar_granulos(cliente: httpx.Client, producto: str, desde: date, hasta: date,
                    caja: tuple[float, float, float, float]) -> list[Granulo]:
    """Gránulos del producto cuyo mosaico toca el rectángulo del lote (oeste, sur, este, norte)."""
    coleccion = earthdata.coleccion_vigente(cliente, producto)
    if coleccion is None:
        raise ErrorECOSTRESS(f"CMR no tiene la colección {producto}")
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
            granulos.append(Granulo(nombre, producto, hora_de_pasada(umm, nombre),
                                    capas_del_granulo(nombre, urls)))
        siguiente = respuesta.headers.get("CMR-Search-After")
        if not siguiente or len(items) < params["page_size"]:
            return granulos
        encabezados = {"CMR-Search-After": siguiente}


def leer_capas(granulo: Granulo, capas: list[str], poligono: dict,
               cliente: httpx.Client | None = None) -> dict:
    """Lee la ventana del lote de cada capa (sin cliente: archivos locales) y la máscara del polígono."""
    import rasterio
    from rasterio.warp import transform_geom
    from rasterio.windows import from_bounds
    from shapely.geometry import shape

    datos: dict = {}
    for capa in capas:
        href = granulo.capas[capa]
        enlace = enlace_firmado(cliente, href) if cliente is not None and href.startswith("http") else href
        with rasterio.open(enlace) as fuente:
            geom = transform_geom("EPSG:4326", fuente.crs, poligono)
            ventana = from_bounds(*shape(geom).bounds, transform=fuente.transform)
            ventana = ventana.round_offsets().round_lengths()
            if capa in MASCARAS:
                datos[capa] = fuente.read(1, window=ventana, boundless=True, fill_value=RELLENO_MASCARA)
                continue
            leido = fuente.read(1, window=ventana, boundless=True, masked=True).astype("float64")
            escala, desplazamiento = fuente.scales[0], fuente.offsets[0]
            datos["dato"] = leido.filled(np.nan) * escala + desplazamiento
            forma, transformada = datos["dato"].shape, fuente.window_transform(ventana)
            datos["lote"], datos["todo_tocado"] = mascara_del_lote(shape(geom), forma, transformada)
    return datos


def procesar(lote_id: str, poligono: dict, lon: float, variable: str, granulo: Granulo,
             cliente: httpx.Client | None = None) -> tuple[Observacion, float]:
    producto = PRODUCTOS[variable]
    capa = capa_de(producto, granulo)
    mascaras = [m for m in MASCARAS if m in granulo.capas]
    datos = leer_capas(granulo, [capa, *mascaras], poligono, cliente)
    validos = pixeles_validos(datos["dato"], producto, {m: datos[m] for m in mascaras})
    r = resumir(datos["dato"], datos["lote"], validos)
    nombre_capa = next(c for c in producto.capas if c.lower() == capa)
    solar = hora_solar(granulo.inicio, lon)
    detalle = (f"{producto.nombre} {nombre_capa} · "
               f"pasada {granulo.inicio:%H:%M} UTC ({solar:%H:%M} hora solar) · "
               f"máscaras: {', '.join(mascaras) if mascaras else 'las de la NASA (nube ya en blanco)'}")
    if datos["todo_tocado"]:
        detalle += " · lote más chico que un píxel: se usan los píxeles que toca"
    detalle += f" · {granulo.nombre}"
    obs = a_observacion(lote_id, fecha_local(granulo.inicio, lon), variable, r, detalle)
    return con_poco_sol(obs, solar), r.validos_pct


def con_poco_sol(obs: Observacion, solar: datetime) -> Observacion:
    """Pasada fuera de 9 a 16 h solar: la NASA estima el día entero desde una hora con poco sol → a lo sumo dudosa."""
    desde, hasta = HORAS_DE_SOL
    if obs.calidad != "buena" or desde <= solar.hour < hasta:
        return obs
    return obs.model_copy(update={
        "calidad": "dudosa",
        "nota": f"Pasada con poco sol ({solar:%H:%M} hora solar): el valor del día se estima desde esa hora · {obs.nota}"})


def obtener(lote_id: str, poligono: dict, desde: date, hasta: date, cliente: httpx.Client | None = None,
            variables: tuple[str, ...] = tuple(PRODUCTOS), hilos: int = HILOS) -> list[Observacion]:
    """ET diaria y ESI de ECOSTRESS por día de pasada. Sin pasadas en el período: lista vacía."""
    from shapely.geometry import shape

    validar_pedido(poligono, desde, hasta)
    geometria = shape(poligono)
    lon = geometria.centroid.x
    try:
        cliente = configurar_credenciales(cliente)
        pedidos = []  # (variable, gránulo)
        for variable in variables:
            producto = PRODUCTOS[variable]
            # un día de margen a cada lado: la fecha local puede no coincidir con la UTC
            for granulo in buscar_granulos(cliente, producto.nombre, desde - timedelta(days=1),
                                           hasta + timedelta(days=1), geometria.bounds):
                if capa_de(producto, granulo) and desde <= fecha_local(granulo.inicio, lon) <= hasta:
                    pedidos.append((variable, granulo))
    except earthdata.FaltanCredenciales:
        raise
    except (httpx.HTTPError, KeyError, ValueError, earthdata.ErrorNASA) as error:
        raise ErrorECOSTRESS(f"No se pudo buscar ECOSTRESS en CMR: {error}") from error

    def uno(pedido):
        variable, granulo = pedido
        try:
            return procesar(lote_id, poligono, lon, variable, granulo, cliente), None
        except Exception as error:  # un archivo ilegible no inventa nada: queda descartado con el motivo
            return None, sin_firma(f"{type(error).__name__}: {error}")

    with ThreadPoolExecutor(max_workers=hilos) as grupo:
        resultados = list(grupo.map(uno, pedidos))
    errores = [e for _, e in resultados if e]
    if pedidos and len(errores) == len(pedidos):
        variable, granulo = pedidos[0]
        archivo = granulo.capas[capa_de(PRODUCTOS[variable], granulo)]
        raise ErrorECOSTRESS(f"No se pudo leer ningún archivo de ECOSTRESS: {errores[0]} · archivo {archivo}")
    candidatas = []
    for (variable, granulo), (hecho, error) in zip(pedidos, resultados):
        if hecho:
            candidatas.append(hecho)
        else:
            candidatas.append((Observacion(
                lote_id=lote_id, fecha=fecha_local(granulo.inicio, lon), variable=variable, valor=None,
                unidad=PRODUCTOS[variable].unidad, fuente="ECOSTRESS", resolucion_m=RESOLUCION_M,
                calidad="descartada", nota=f"No se pudo leer el archivo: {error} · {granulo.nombre}"), -1.0))
    return quedarse_con_la_mejor(candidatas)


# ---------- conexión con el núcleo (spec 009) ----------

# primer respaldo de la ET principal; si ECOSTRESS tampoco trae datos, entra FAO-56 ("ET:FAO56", orden 2)
SATELITES = [Satelite("ET:ECOSTRESS", lambda lote, desde, hasta: obtener(lote["id"], lote["poligono"], desde, hasta),
                      respaldo_de="ET", orden=1)]

router = APIRouter(tags=["ECOSTRESS (pruebas internas)"])


class PedidoEcostress(BaseModel):
    lote_id: str
    poligono: dict
    desde: date
    hasta: date


@router.post("/estres-hidrico", response_model=list[Observacion])
def estres_hidrico(pedido: PedidoEcostress) -> list[Observacion]:
    """ET diaria (mm/día) y ESI de ECOSTRESS del lote, por día de pasada de la Estación Espacial."""
    try:
        validar_pedido(pedido.poligono, pedido.desde, pedido.hasta)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener(pedido.lote_id, pedido.poligono, pedido.desde, pedido.hasta)
    except earthdata.FaltanCredenciales as error:
        raise HTTPException(status_code=503, detail=str(error))
    except ErrorECOSTRESS as error:
        raise HTTPException(status_code=502, detail=str(error))
