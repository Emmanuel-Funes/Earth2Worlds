"""Conector NASADEM: altura, pendiente y ambientes (bajo, media loma, loma) del lote (spec 008)."""

import io
import math
import zipfile
from datetime import date

import httpx
import numpy as np

from rotaterra.contrato import Observacion
from rotaterra.fuentes import earthdata
from rotaterra.geo import validar_poligono
from rotaterra.fuentes.registro import Satelite
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

PRODUCTO = "NASADEM_HGT"
FECHA = date(2000, 2, 11)  # inicio de la misión SRTM, de donde sale NASADEM
RESOLUCION_M = 30
RELLENO = -32768
ALTURA_MIN, ALTURA_MAX = -500, 9000
UMBRAL_AMBIENTE_M = 1.0  # SUPUESTO de arranque para lotes de llanura: calibrar con asesores locales
MIN_PIXELES = 10
SEGUNDO = 1 / 3600  # la grilla de NASADEM es de 1 segundo de arco (~30 m)
_R = 6371008.8
_LADO_M = _R * math.radians(SEGUNDO)  # ~30,9 m en dirección norte-sur

_CACHE: dict[str, np.ndarray] = {}  # mosaicos ya bajados en esta corrida (varios lotes comparten mosaico)


class ErrorNASADEM(Exception):
    """La NASA no respondió o respondió algo ilegible."""


def mosaico(lat: float, lon: float) -> str:
    """Nombre del mosaico de 1° × 1° que contiene el punto: (-33.7, -65.3) → 's34w066'."""
    sur, oeste = math.floor(lat), math.floor(lon)
    return f"{'n' if sur >= 0 else 's'}{abs(sur):02d}{'e' if oeste >= 0 else 'w'}{abs(oeste):03d}"


def esquina(nombre: str) -> tuple[int, int]:
    """'s34w066' → (-34, -66): latitud y longitud de la esquina suroeste."""
    lat = int(nombre[1:3]) * (1 if nombre[0] == "n" else -1)
    lon = int(nombre[4:7]) * (1 if nombre[3] == "e" else -1)
    return lat, lon


def leer_hgt(contenido: bytes) -> np.ndarray:
    """ZIP de la NASA → matriz de alturas (fila 0 = borde norte). Enteros de 16 bits big-endian."""
    with zipfile.ZipFile(io.BytesIO(contenido)) as archivo:
        miembro = next((n for n in archivo.namelist() if n.lower().endswith(".hgt")), None)
        if miembro is None:
            raise ErrorNASADEM("El ZIP de NASADEM no trae un archivo .hgt")
        crudo = archivo.read(miembro)
    lado = math.isqrt(len(crudo) // 2)
    if lado * lado * 2 != len(crudo):
        raise ErrorNASADEM("El archivo .hgt no es cuadrado")
    return np.frombuffer(crudo, dtype=">i2").reshape(lado, lado)


def urls_mosaicos(cliente: httpx.Client, caja: tuple[float, float, float, float]) -> dict[str, str]:
    """Mosaico → URL del ZIP, buscando en CMR los que tocan la caja (oeste, sur, este, norte)."""
    coleccion = earthdata.coleccion_vigente(cliente, PRODUCTO)
    if coleccion is None:
        raise ErrorNASADEM(f"CMR no tiene {PRODUCTO}")
    respuesta = cliente.get(f"{earthdata.URL_CMR}/granules.umm_json",
                            params={"collection_concept_id": coleccion, "page_size": 20,
                                    "bounding_box": ",".join(str(c) for c in caja)})
    respuesta.raise_for_status()
    urls = {}
    for item in respuesta.json()["items"]:
        nombre = item["umm"]["GranuleUR"].rsplit("_", 1)[-1].lower()
        zips = [u["URL"] for u in item["umm"].get("RelatedUrls", [])
                if u.get("Type") == "GET DATA" and u["URL"].endswith(".zip") and u["URL"].startswith("https")]
        if zips:
            urls[nombre] = zips[0]
    return urls


def bajar_mosaico(cliente: httpx.Client, url: str) -> np.ndarray:
    if url not in _CACHE:
        respuesta = cliente.get(url)
        if respuesta.status_code in (401, 403):
            raise ErrorNASADEM("La NASA negó el acceso: ¿está autorizada la aplicación LP DAAC en Earthdata?")
        respuesta.raise_for_status()
        if len(_CACHE) >= 4:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[url] = leer_hgt(respuesta.content)
    return _CACHE[url]


def armar_grilla(mosaicos: dict[str, np.ndarray], caja: tuple[float, float, float, float]):
    """Alturas de la caja del lote (con un píxel de margen), juntando los mosaicos que hagan falta.

    Devuelve (alturas en m con NaN donde no hay dato, latitud de cada fila, longitud de cada columna).
    """
    oeste, sur, este, norte = caja
    # índices globales de la grilla de 1": fila 0 = 90° N, columna 0 = 180° O
    f0, f1 = math.floor((90 - norte) * 3600) - 1, math.ceil((90 - sur) * 3600) + 1
    c0, c1 = math.floor((oeste + 180) * 3600) - 1, math.ceil((este + 180) * 3600) + 1
    alturas = np.full((f1 - f0 + 1, c1 - c0 + 1), np.nan)
    for nombre, datos in mosaicos.items():
        lat_so, lon_so = esquina(nombre)
        lado = datos.shape[0] - 1  # 3600: la última fila y columna repiten el borde del vecino
        fila_norte = round((90 - (lat_so + 1)) * 3600)
        col_oeste = round((lon_so + 180) * 3600)
        a0, a1 = max(f0, fila_norte), min(f1, fila_norte + lado)
        b0, b1 = max(c0, col_oeste), min(c1, col_oeste + lado)
        if a0 > a1 or b0 > b1:
            continue
        recorte = datos[a0 - fila_norte:a1 - fila_norte + 1, b0 - col_oeste:b1 - col_oeste + 1].astype("float64")
        alturas[a0 - f0:a1 - f0 + 1, b0 - c0:b1 - c0 + 1] = recorte
    alturas[(alturas == RELLENO) | (alturas < ALTURA_MIN) | (alturas > ALTURA_MAX)] = np.nan
    lats = 90 - np.arange(f0, f1 + 1) * SEGUNDO
    lons = np.arange(c0, c1 + 1) * SEGUNDO - 180
    return alturas, lats, lons


def superficie_ha(poligono: dict) -> float:
    """Superficie del lote en hectáreas (proyección local; error menor a 0,5 % en lotes agrícolas)."""
    from shapely.geometry import Polygon

    anillo = poligono["coordinates"][0]
    lat0 = sum(lat for _, lat in anillo) / len(anillo)
    metros = [(math.radians(lon) * _R * math.cos(math.radians(lat0)), math.radians(lat) * _R) for lon, lat in anillo]
    return Polygon(metros).area / 10_000


def resumir(lote_id: str, poligono: dict, alturas: np.ndarray, lats: np.ndarray, lons: np.ndarray) -> list[Observacion]:
    """Las 7 variables de altimetría del lote a partir de la grilla de alturas."""
    import shapely
    from shapely.geometry import shape

    lon_m, lat_m = np.meshgrid(lons, lats)
    dentro = shapely.contains_xy(shape(poligono), lon_m, lat_m)
    validos = dentro & np.isfinite(alturas)
    total, n = int(dentro.sum()), int(validos.sum())
    lat_media = float(np.mean(lats))
    # pendiente con el tamaño real del píxel a esta latitud
    dz_dy, dz_dx = np.gradient(alturas, _LADO_M, _LADO_M * math.cos(math.radians(lat_media)))
    pendiente = 100 * np.hypot(dz_dx, dz_dy)

    base = dict(lote_id=lote_id, fecha=FECHA, fuente="NASADEM", resolucion_m=RESOLUCION_M)
    detalle = f"NASADEM (SRTM, febrero de 2000) · {n} de {total} píxeles de 30 m con dato"
    variables = [("altura_media_m", "m"), ("altura_min_m", "m"), ("altura_max_m", "m"),
                 ("pendiente_media_pct", "%"), ("superficie_bajo_ha", "ha"),
                 ("superficie_media_loma_ha", "ha"), ("superficie_loma_ha", "ha")]
    if n == 0:
        nota = f"Sin píxeles con dato dentro del lote · {detalle}"
        return [Observacion(**base, variable=v, valor=None, unidad=u, calidad="descartada", nota=nota)
                for v, u in variables]

    h = alturas[validos]
    media = float(h.mean())
    p = pendiente[validos]
    hectareas = superficie_ha(poligono)
    bajo = float((h < media - UMBRAL_AMBIENTE_M).sum()) / n
    loma = float((h > media + UMBRAL_AMBIENTE_M).sum()) / n
    valores = {
        "altura_media_m": round(media, 1),
        "altura_min_m": round(float(h.min()), 1),
        "altura_max_m": round(float(h.max()), 1),
        "pendiente_media_pct": round(float(np.nanmean(p)), 2) if np.isfinite(p).any() else None,
        "superficie_bajo_ha": round(bajo * hectareas, 2),
        "superficie_loma_ha": round(loma * hectareas, 2),
    }
    valores["superficie_media_loma_ha"] = round(hectareas - valores["superficie_bajo_ha"]
                                                - valores["superficie_loma_ha"], 2)
    calidad = "dudosa" if n < MIN_PIXELES else "buena"
    aviso = f"menos de {MIN_PIXELES} píxeles (lote menor a ~1 ha) · " if calidad == "dudosa" else ""
    ambientes = (f"bajo / loma = más de {UMBRAL_AMBIENTE_M:g} m por debajo / por encima de la media del lote "
                 f"(umbral supuesto, a calibrar) · proporción de píxeles × {hectareas:.1f} ha del lote · ")
    # Orientación media de la pendiente (rumbo hacia donde desciende el terreno)
    gx = float(np.nanmean(-dz_dx[validos])) if np.isfinite(dz_dx[validos]).any() else 0.0
    gy = float(np.nanmean(dz_dy[validos])) if np.isfinite(dz_dy[validos]).any() else 0.0
    angulo = (math.degrees(math.atan2(gx, gy)) + 360) % 360
    rumbos = ["Norte", "Noreste", "Este", "Sureste", "Sur", "Suroeste", "Oeste", "Noroeste"]
    rumbo = rumbos[int((angulo + 22.5) // 45) % 8]

    observaciones = []
    for variable, unidad in variables:
        valor = valores[variable]
        nota = aviso + (ambientes if variable.startswith("superficie") else "") + detalle
        if variable == "pendiente_media_pct" and valor is not None:
            nota = f"Pendiente con orientación hacia el {rumbo} ({angulo:.0f}°) · " + nota
        if valor is None:
            observaciones.append(Observacion(**base, variable=variable, valor=None, unidad=unidad,
                                             calidad="descartada", nota=f"Sin vecinos para calcular la pendiente · {nota}"))
        else:
            observaciones.append(Observacion(**base, variable=variable, valor=valor, unidad=unidad,
                                             calidad=calidad, nota=nota))
    return observaciones


def obtener_altimetria(lote_id: str, poligono: dict, cliente: httpx.Client | None = None) -> list[Observacion]:
    """Altura, pendiente y ambientes del lote en el contrato común. Es un dato fijo: se pide una sola vez."""
    validar_poligono(poligono)
    from shapely.geometry import shape

    caja = shape(poligono).bounds
    try:
        cliente = earthdata.cliente_autorizado(cliente)
        urls = urls_mosaicos(cliente, caja)
        if not urls:
            raise ErrorNASADEM("NASADEM no tiene datos para este lugar (¿lote en el mar?)")
        mosaicos = {nombre: bajar_mosaico(cliente, url) for nombre, url in urls.items()}
    except earthdata.FaltanCredenciales:
        raise
    except (httpx.HTTPError, KeyError, ValueError, zipfile.BadZipFile, earthdata.ErrorNASA) as error:
        raise ErrorNASADEM(f"No se pudo obtener la altimetría de NASADEM: {error}") from error
    return resumir(lote_id, poligono, *armar_grilla(mosaicos, caja))


# ---------- conexión con el núcleo (spec 009) ----------

SATELITES = [Satelite("NASADEM", lambda lote, desde, hasta: obtener_altimetria(lote["id"], lote["poligono"]),
                      estatico=True)]

router = APIRouter(tags=["NASADEM (pruebas internas)"])


class PedidoAltimetria(BaseModel):
    lote_id: str
    poligono: dict


@router.post("/altimetria", response_model=list[Observacion])
def altimetria(pedido: PedidoAltimetria) -> list[Observacion]:
    try:
        validar_poligono(pedido.poligono)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener_altimetria(pedido.lote_id, pedido.poligono)
    except earthdata.FaltanCredenciales as error:
        raise HTTPException(status_code=503, detail=str(error))
    except ErrorNASADEM as error:
        raise HTTPException(status_code=502, detail=str(error))
