"""Conector Sentinel-2 L2A (ESA): NDVI a 10 m y NDMI a 20 m, primer respaldo de HLS (spec 014).

Datos de la ESA/Copernicus distribuidos como COG públicos en AWS Open Data y catalogados en el STAC
público Earth Search de Element 84. No pide credenciales.
"""

import time
from dataclasses import dataclass
from datetime import date

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rotaterra.contrato import Observacion
from rotaterra.fuentes.registro import Satelite
from rotaterra.geo import validar_poligono

URL_STAC = "https://earth-search.aws.element84.com/v1"
# la primera es la de la spec; la segunda ("colección 1") solo si la primera no devuelve nada
COLECCIONES = ["sentinel-2-l2a", "sentinel-2-c1-l2a"]
MAX_DIAS = 366
SIN_DATO = 0  # DN 0 = sin dato en todas las bandas y en SCL
ESCALA = 0.0001
OFFSET_DESDE_BASELINE_4 = -0.1  # BOA_ADD_OFFSET = -1000 desde la línea de base 04.00

# asset de Earth Search de cada banda lógica
ASSETS = {"rojo": "red", "nir": "nir", "nir08": "nir08", "swir1": "swir16", "scl": "scl"}

# SCL (Scene Classification de la ESA): válidos = 4 vegetación, 5 suelo desnudo.
# Se descartan 0 sin dato, 1 saturado, 2 zona oscura, 3 sombra de nube, 6 agua (como HLS), 7 sin clasificar,
# 8-9 nubes, 10 cirros, 11 nieve.
SCL_VALIDOS = (4, 5)
SCL_NOMBRES = {0: "sin dato", 1: "saturado", 2: "zona oscura", 3: "sombra de nube", 4: "vegetación",
               5: "suelo desnudo", 6: "agua", 7: "sin clasificar", 8: "nube media", 9: "nube densa",
               10: "cirros", 11: "nieve"}

# variable -> (banda a, banda b, resolución en metros): (a - b) / (a + b)
INDICES = {
    "ndvi": ("nir", "rojo", 10),
    "ndmi": ("nir08", "swir1", 20),
}
UNIDAD = "índice (-1 a 1)"

UMBRAL_BUENA = 60.0
UMBRAL_DESCARTADA = 20.0

ENTORNO_GDAL = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
                    GDAL_HTTP_MAX_RETRY="3", GDAL_HTTP_RETRY_DELAY="2", AWS_NO_SIGN_REQUEST="YES")


class ErrorSentinel2(Exception):
    """Earth Search no respondió o las escenas no se pudieron leer."""


@dataclass
class Resumen:
    mediana: float | None
    media: float | None
    p10: float | None
    p90: float | None
    validos_pct: float


# ---------- cálculo puro (testeable sin internet) ----------

def mascara_valida(scl: np.ndarray) -> np.ndarray:
    """True donde la SCL dice vegetación o suelo desnudo."""
    return np.isin(scl, SCL_VALIDOS)


def motivo_descarte(scl: np.ndarray, dentro_lote: np.ndarray) -> str:
    """Qué dice la SCL de los píxeles del lote que no sirven: 'cirros 93%, sombra de nube 7%'."""
    malos = scl[dentro_lote & ~mascara_valida(scl)]
    total = int(dentro_lote.sum())
    if malos.size == 0 or total == 0:
        return "sin dato en las bandas"
    clases, cuentas = np.unique(malos, return_counts=True)
    orden = sorted(zip(cuentas.tolist(), clases.tolist()), reverse=True)[:3]
    return ", ".join(f"{SCL_NOMBRES.get(c, f'clase {c}')} {100 * n / total:.0f}%" for n, c in orden)


def escala_y_offset(propiedades: dict, bandas_raster: list | None) -> tuple[float, float]:
    """Cómo pasar el DN de una banda a reflectancia: reflectancia = DN * escala + offset.

    Earth Search marca `earthsearch:boa_offset_applied: true` cuando ya restó el offset en los píxeles; sus
    `raster:bands` igual dicen offset -0.1, así que en ese caso no se aplica otra vez (verificado el 4/10/2026:
    el rojo de la vegetación del lote vale DN ~270, que solo tiene sentido sin offset).
    """
    banda = (bandas_raster or [{}])[0]
    escala = float(banda.get("scale", ESCALA))
    if propiedades.get("earthsearch:boa_offset_applied") is True:
        return escala, 0.0
    if "offset" in banda:
        return escala, float(banda["offset"])
    linea = propiedades.get("s2:processing_baseline")
    try:
        nueva = float(linea) >= 4
    except (TypeError, ValueError):
        nueva = False
    return escala, OFFSET_DESDE_BASELINE_4 if nueva else 0.0


def reflectancia(dn: np.ndarray, escala: float, offset: float) -> np.ndarray:
    """DN -> reflectancia de superficie; NaN donde no hay dato."""
    resultado = dn.astype("float64") * escala + offset
    resultado[dn == SIN_DATO] = np.nan
    return resultado


def diferencia_normalizada(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """(a - b) / (a + b) sobre reflectancias; NaN donde no se puede calcular o queda fuera de -1..1."""
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


def a_observacion(lote_id: str, fecha: date, variable: str, r: Resumen, escena: str,
                  motivo: str = "nubes, sombra, agua o sin dato") -> Observacion:
    base = dict(lote_id=lote_id, fecha=fecha, variable=variable, unidad=UNIDAD,
                fuente="SENTINEL2", resolucion_m=INDICES[variable][2])
    origen = f"Respaldo de HLS · Sentinel-2 L2A (ESA) · {escena}"
    if r.validos_pct < UMBRAL_DESCARTADA or r.mediana is None:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"{origen} · solo {r.validos_pct:.0f}% de píxeles limpios · SCL: {motivo}")
    detalle = f"media {r.media:.2f} · p10 {r.p10:.2f} · p90 {r.p90:.2f} · válidos {r.validos_pct:.0f}%"
    if r.validos_pct < UMBRAL_BUENA:
        return Observacion(**base, valor=round(r.mediana, 3), calidad="dudosa",
                           nota=f"{origen} · lote parcialmente cubierto · {detalle}")
    return Observacion(**base, valor=round(r.mediana, 3), calidad="buena", nota=f"{origen} · {detalle}")


def validar_pedido(poligono: dict, desde: date, hasta: date) -> None:
    validar_poligono(poligono)
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise ValueError(f"El rango supera {MAX_DIAS} días")


def nombre_corto(escena) -> str:
    """'S2C_20HKH_20260116_0_L2A' -> 'S2C 20HKH' (satélite y mosaico MGRS) para la nota."""
    partes = str(escena.id).split("_")
    return " ".join(partes[:2]) if len(partes) >= 2 else str(escena.id)


# ---------- acceso a Earth Search (AWS Open Data) ----------

def buscar_escenas(poligono: dict, desde: date, hasta: date, nubosidad_max: float, intentos: int = 3):
    """Escenas que tocan el rectángulo del lote; el recorte exacto se hace al leer."""
    from pystac_client import Client
    from shapely.geometry import shape

    bbox = list(shape(poligono).bounds)
    periodo = f"{desde.isoformat()}T00:00:00Z/{hasta.isoformat()}T23:59:59Z"
    for coleccion in COLECCIONES:
        for intento in range(1, intentos + 1):
            try:
                busqueda = Client.open(URL_STAC).search(
                    collections=[coleccion], bbox=bbox, datetime=periodo, limit=100, max_items=500)
                escenas = list(busqueda.items())
                break
            except Exception as error:
                if intento == intentos:
                    raise ErrorSentinel2(f"No se pudo buscar escenas {coleccion} en Earth Search: {error}") from error
                time.sleep(5 * intento)
        if escenas:
            return [e for e in escenas if (e.properties.get("eo:cloud_cover") or 0) <= nubosidad_max]
    return []


def _asset(escena, banda: str):
    clave = ASSETS[banda]
    if clave not in escena.assets:
        raise ErrorSentinel2(f"La escena {escena.id} no trae la banda '{clave}'")
    return escena.assets[clave]


def leer_escena(escena, poligono: dict) -> dict[str, np.ndarray]:
    """Lee la ventana del lote de cada banda (reflectancia) y la SCL, a 10 m y a 20 m, con la máscara del lote."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.features import geometry_mask
    from rasterio.warp import transform_geom
    from rasterio.windows import bounds as limites_ventana
    from rasterio.windows import from_bounds
    from shapely.geometry import shape

    datos: dict[str, np.ndarray] = {}
    with rasterio.Env(**ENTORNO_GDAL):
        for res, bandas in ((20, ("scl", "nir08", "swir1")), (10, ("rojo", "nir"))):
            ventana = transform = None
            for banda in bandas:
                asset = _asset(escena, banda)
                with rasterio.open(asset.href) as fuente:
                    if ventana is None:
                        geom = transform_geom("EPSG:4326", fuente.crs, poligono)
                        ventana = from_bounds(*shape(geom).bounds, transform=fuente.transform)
                        ventana = ventana.round_offsets().round_lengths()
                        transform = fuente.window_transform(ventana)
                    dn = fuente.read(1, window=ventana, boundless=True, fill_value=SIN_DATO)
                    if banda == "scl":
                        datos[f"scl{res}"] = dn
                    else:
                        escala, offset = escala_y_offset(escena.properties,
                                                         asset.extra_fields.get("raster:bands"))
                        datos[banda] = reflectancia(dn, escala, offset)
                    if res == 10 and banda == "rojo":
                        # SCL de 20 m llevada a la grilla de 10 m por vecino más cercano
                        with rasterio.open(_asset(escena, "scl").href) as scl:
                            v20 = from_bounds(*limites_ventana(ventana, fuente.transform), transform=scl.transform)
                            datos["scl10"] = scl.read(1, window=v20, out_shape=dn.shape, boundless=True,
                                                      fill_value=SIN_DATO, resampling=Resampling.nearest)
            datos[f"lote{res}"] = geometry_mask([geom], out_shape=datos[f"scl{res}"].shape,
                                                transform=transform, invert=True)
    return datos


def procesar_escena(lote_id: str, escena, poligono: dict) -> list[tuple[Observacion, float]]:
    datos = leer_escena(escena, poligono)
    fecha = escena.datetime.date()
    resultado = []
    for variable, (a, b, res) in INDICES.items():
        indice = diferencia_normalizada(datos[a], datos[b])
        validos = mascara_valida(datos[f"scl{res}"]) & np.isfinite(datos[a]) & np.isfinite(datos[b])
        r = resumir(indice, datos[f"lote{res}"], validos)
        motivo = motivo_descarte(datos[f"scl{res}"], datos[f"lote{res}"])
        resultado.append((a_observacion(lote_id, fecha, variable, r, nombre_corto(escena), motivo), r.validos_pct))
    return resultado


def obtener_ndvi(lote_id: str, poligono: dict, desde: date, hasta: date,
                 nubosidad_max: float = 70) -> list[Observacion]:
    """Serie de NDVI y NDMI del lote; si hay dos escenas el mismo día, gana la más limpia."""
    validar_pedido(poligono, desde, hasta)
    mejores: dict[tuple[date, str], tuple[Observacion, float]] = {}
    for escena in buscar_escenas(poligono, desde, hasta, nubosidad_max):
        try:
            observaciones = procesar_escena(lote_id, escena, poligono)
        except ErrorSentinel2:
            raise
        except Exception as error:
            raise ErrorSentinel2(f"No se pudo leer la escena {escena.id}: {error}") from error
        for obs, pct in observaciones:
            clave = (obs.fecha, obs.variable)
            if clave not in mejores or pct > mejores[clave][1]:
                mejores[clave] = (obs, pct)
    return [obs for _, (obs, _) in sorted(mejores.items())]


# ---------- conexión con el núcleo (spec 009) ----------

SATELITES = [Satelite("HLS:SENTINEL2",
                      lambda lote, desde, hasta: obtener_ndvi(lote["id"], lote["poligono"], desde, hasta),
                      respaldo_de="HLS", orden=1)]

router = APIRouter(tags=["Sentinel-2 (pruebas internas)"])


class PedidoNdvi(BaseModel):
    lote_id: str
    poligono: dict
    desde: date
    hasta: date
    nubosidad_max: float = 70


@router.post("/ndvi/sentinel2", response_model=list[Observacion])
def ndvi_sentinel2(pedido: PedidoNdvi) -> list[Observacion]:
    try:
        validar_pedido(pedido.poligono, pedido.desde, pedido.hasta)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener_ndvi(pedido.lote_id, pedido.poligono, pedido.desde, pedido.hasta, pedido.nubosidad_max)
    except ErrorSentinel2 as error:
        raise HTTPException(status_code=502, detail=str(error))
