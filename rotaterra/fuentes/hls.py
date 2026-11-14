"""Conector HLS: NDVI y NDMI del lote a 30 m (spec 002)."""

import os
from dataclasses import dataclass
from datetime import date

import httpx
import numpy as np

from rotaterra.contrato import Observacion
from rotaterra.geo import validar_poligono
from rotaterra.fuentes import earthdata
from rotaterra.fuentes.registro import Satelite
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

URL_STAC = "https://cmr.earthdata.nasa.gov/stac/LPCLOUD"
COLECCIONES = ["HLSL30_2.0", "HLSS30_2.0"]
RESOLUCION_M = 30
ESCALA = 0.0001
FMASK_RELLENO = 255
MAX_DIAS = 366

# Bits de Fmask que invalidan un píxel: nube (1), nube adyacente (2), sombra (3), nieve/hielo (4), agua (5)
FMASK_BITS_INVALIDOS = 0b111110

# banda lógica -> nombre del asset en cada colección
BANDAS = {
    "HLSL30": {"rojo": "B04", "nir": "B05", "swir1": "B06", "fmask": "Fmask"},
    "HLSS30": {"rojo": "B04", "nir": "B8A", "swir1": "B11", "fmask": "Fmask"},
}

INDICES = {
    "ndvi": ("nir", "rojo"),
    "ndmi": ("nir", "swir1"),
}
UNIDAD = "índice (-1 a 1)"

UMBRAL_BUENA = 60.0
UMBRAL_DESCARTADA = 20.0


class ErrorHLS(Exception):
    """NASA no respondió o las escenas no se pudieron leer."""


class FaltanCredenciales(Exception):
    """No están EARTHDATA_USERNAME / EARTHDATA_PASSWORD."""


@dataclass
class Resumen:
    mediana: float | None
    media: float | None
    p10: float | None
    p90: float | None
    validos_pct: float


# ---------- cálculo puro (testeable sin internet) ----------

def mascara_valida(fmask: np.ndarray) -> np.ndarray:
    """True donde el píxel está limpio según Fmask."""
    fmask = fmask.astype(np.uint16)
    return (fmask != FMASK_RELLENO) & ((fmask & FMASK_BITS_INVALIDOS) == 0)


def diferencia_normalizada(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """(a - b) / (a + b) sobre reflectancias escaladas; NaN donde no se puede calcular."""
    a = a.astype("float64") * ESCALA
    b = b.astype("float64") * ESCALA
    with np.errstate(divide="ignore", invalid="ignore"):
        resultado = (a - b) / (a + b)
    resultado[~np.isfinite(resultado) | (resultado < -1) | (resultado > 1)] = np.nan
    return resultado


def resumir(indice: np.ndarray, dentro_lote: np.ndarray, validos: np.ndarray) -> Resumen:
    """Estadísticas del índice sobre los píxeles del lote que están limpios."""
    total = int(dentro_lote.sum())
    if total == 0:
        return Resumen(None, None, None, None, 0.0)
    valores = indice[dentro_lote & validos & np.isfinite(indice)]
    pct = 100.0 * valores.size / total
    if valores.size == 0:
        return Resumen(None, None, None, None, pct)
    p10, mediana, p90 = np.percentile(valores, [10, 50, 90])
    return Resumen(float(mediana), float(valores.mean()), float(p10), float(p90), pct)


def a_observacion(lote_id: str, fecha: date, variable: str, r: Resumen, coleccion: str) -> Observacion:
    base = dict(lote_id=lote_id, fecha=fecha, variable=variable, unidad=UNIDAD,
                fuente="HLS", resolucion_m=RESOLUCION_M)
    if r.validos_pct < UMBRAL_DESCARTADA or r.mediana is None:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"Solo {r.validos_pct:.0f}% de píxeles limpios (nubes, sombra o agua) · {coleccion}")
    detalle = (f"media {r.media:.2f} · p10 {r.p10:.2f} · p90 {r.p90:.2f} · "
               f"válidos {r.validos_pct:.0f}% · {coleccion}")
    if r.validos_pct < UMBRAL_BUENA:
        return Observacion(**base, valor=round(r.mediana, 3), calidad="dudosa",
                           nota=f"Lote parcialmente cubierto · {detalle}")
    return Observacion(**base, valor=round(r.mediana, 3), calidad="buena", nota=detalle)


def validar_pedido(poligono: dict, desde: date, hasta: date) -> None:
    validar_poligono(poligono)
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise ValueError(f"El rango supera {MAX_DIAS} días")


# ---------- acceso a NASA ----------

def configurar_credenciales(cliente: httpx.Client | None = None) -> httpx.Client:
    """Cliente con el token de Earthdata del núcleo (el mismo que usa NASADEM) y GDAL listo para leer por HTTP."""
    try:
        cliente = earthdata.cliente_autorizado(cliente)
    except earthdata.FaltanCredenciales as error:
        raise FaltanCredenciales(str(error)) from error
    except (httpx.HTTPError, earthdata.ErrorNASA) as error:
        raise ErrorHLS(f"No se pudo obtener el token de Earthdata: {error}") from error
    os.environ.update({
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "GDAL_HTTP_MAX_RETRY": "3",
        "GDAL_HTTP_RETRY_DELAY": "2",
    })
    return cliente


def enlace_firmado(cliente: httpx.Client, url: str) -> str:
    """LP DAAC redirige cada archivo a un enlace firmado de CloudFront que vale un rato y no pide credenciales.

    GDAL dejó de poder seguir esa redirección (devolvía "not recognized as being in a supported
    file format"), así que la resolvemos acá con el token y GDAL lee el enlace firmado directo.
    """
    respuesta = cliente.get(url, headers={"Range": "bytes=0-0"}, follow_redirects=False)
    if respuesta.is_redirect:
        return respuesta.headers["location"]
    respuesta.raise_for_status()
    return url


def buscar_escenas(poligono: dict, desde: date, hasta: date, nubosidad_max: float,
                   intentos: int = 3):
    """Busca escenas por el rectángulo que contiene al lote; el recorte exacto se hace al leer."""
    import time

    from pystac_client import Client
    from shapely.geometry import shape

    # El catálogo de NASA (CMR STAC) falla seguido con búsquedas por polígono: se busca por bbox.
    bbox = list(shape(poligono).bounds)
    periodo = f"{desde.isoformat()}T00:00:00Z/{hasta.isoformat()}T23:59:59Z"
    escenas = []
    for coleccion in COLECCIONES:
        for intento in range(1, intentos + 1):
            try:
                busqueda = Client.open(URL_STAC).search(
                    collections=[coleccion], bbox=bbox, datetime=periodo, limit=100, max_items=500)
                escenas += list(busqueda.items())
                break
            except Exception as error:
                if intento == intentos:
                    raise ErrorHLS(f"No se pudo buscar escenas {coleccion}: {error}") from error
                time.sleep(5 * intento)
    return [e for e in escenas if e.properties.get("eo:cloud_cover", 0) <= nubosidad_max]


def leer_escena(escena, poligono: dict, cliente: httpx.Client | None = None) -> dict[str, np.ndarray]:
    """Lee la ventana del lote de cada banda y la máscara del polígono (sin cliente: archivos locales)."""
    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.warp import transform_geom
    from rasterio.windows import from_bounds
    from shapely.geometry import shape

    coleccion = escena.collection_id.split("_")[0]
    bandas = BANDAS[coleccion]
    datos = {}
    for nombre, asset in bandas.items():
        href = escena.assets[asset].href
        with rasterio.open(enlace_firmado(cliente, href) if cliente else href) as fuente:
            geom = transform_geom("EPSG:4326", fuente.crs, poligono)
            ventana = from_bounds(*shape(geom).bounds, transform=fuente.transform)
            ventana = ventana.round_offsets().round_lengths()
            datos[nombre] = fuente.read(1, window=ventana, boundless=True, fill_value=FMASK_RELLENO if nombre == "fmask" else -9999)
            if "lote" not in datos:
                datos["lote"] = geometry_mask([geom], out_shape=datos[nombre].shape,
                                              transform=fuente.window_transform(ventana), invert=True)
    return datos


def procesar_escena(lote_id: str, escena, poligono: dict,
                    cliente: httpx.Client | None = None) -> list[tuple[Observacion, float]]:
    datos = leer_escena(escena, poligono, cliente)
    validos = mascara_valida(datos["fmask"])
    for banda in ("rojo", "nir", "swir1"):
        validos &= datos[banda] != -9999
    fecha = escena.datetime.date()
    coleccion = escena.collection_id.split("_")[0]
    resultado = []
    for variable, (a, b) in INDICES.items():
        r = resumir(diferencia_normalizada(datos[a], datos[b]), datos["lote"], validos)
        resultado.append((a_observacion(lote_id, fecha, variable, r, coleccion), r.validos_pct))
    return resultado


def obtener_ndvi(lote_id: str, poligono: dict, desde: date, hasta: date,
                 nubosidad_max: float = 70) -> list[Observacion]:
    """Serie de NDVI y NDMI del lote; si hay dos escenas el mismo día, gana la más limpia."""
    validar_pedido(poligono, desde, hasta)
    cliente = configurar_credenciales()
    mejores: dict[tuple[date, str], tuple[Observacion, float]] = {}
    for escena in buscar_escenas(poligono, desde, hasta, nubosidad_max):
        try:
            observaciones = procesar_escena(lote_id, escena, poligono, cliente)
        except Exception as error:
            raise ErrorHLS(f"No se pudo leer la escena {escena.id}: {error}") from error
        for obs, pct in observaciones:
            clave = (obs.fecha, obs.variable)
            if clave not in mejores or pct > mejores[clave][1]:
                mejores[clave] = (obs, pct)
    return [obs for (_, _), (obs, _) in sorted(mejores.items())]


# ---------- conexión con el núcleo (spec 009) ----------

SATELITES = [Satelite("HLS", lambda lote, desde, hasta: obtener_ndvi(lote["id"], lote["poligono"], desde, hasta))]

router = APIRouter(tags=["HLS (pruebas internas)"])


class PedidoNdvi(BaseModel):
    lote_id: str
    poligono: dict
    desde: date
    hasta: date
    nubosidad_max: float = 70


@router.post("/ndvi", response_model=list[Observacion])
def ndvi(pedido: PedidoNdvi) -> list[Observacion]:
    try:
        validar_pedido(pedido.poligono, pedido.desde, pedido.hasta)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener_ndvi(pedido.lote_id, pedido.poligono, pedido.desde, pedido.hasta, pedido.nubosidad_max)
    except FaltanCredenciales as error:
        raise HTTPException(status_code=503, detail=str(error))
    except ErrorHLS as error:
        raise HTTPException(status_code=502, detail=str(error))
