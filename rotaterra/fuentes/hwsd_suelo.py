"""Conector HWSD: respaldo de suelo de la NASA (spec 031).

Respaldo de GeoINTA (que hoy no tiene ninguno). Entrega la textura (clase común 1-12) y el pH del lote
a partir de la Harmonized World Soil Database v1.2 regrillada (HWSD_1247) del ORNL DAAC de la NASA, una
base mundial de suelo en una grilla de 0,05° (~5,5 km). Es un dato estático y REGIONAL: la base no cambia
y cada celda cubre miles de hectáreas, así que respalda a GeoINTA pero no lo reemplaza (calidad `dudosa`).

Cada capa es un NetCDF que se baja una sola vez a la caché (igual que los mascons de GRACE) y se lee con
rasterio solo en la celda del centro del lote. No importa a ningún otro satélite (spec 009).
"""

import tempfile
from datetime import date
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rotaterra.contrato import Observacion
from rotaterra.fuentes import earthdata
from rotaterra.fuentes.registro import Satelite
from rotaterra.geo import validar_poligono

PRODUCTO = "HWSD_1247"
RESOLUCION_M = 5500           # supuesto si no se puede leer del archivo: grilla de 0,05° ≈ 5,5 km
FECHA = date(2012, 3, 1)      # HWSD v1.2 es una base fija de 2012; se guarda como dato estático
CARPETA = Path(tempfile.gettempdir()) / "rotaterra-hwsd"

# capa del archivo -> (variable del contrato de GeoINTA, profundidad para la nota)
# HWSD solo tiene superficie (T, 0-30 cm) y subsuelo (S, 30-100 cm); se reparten en las 4 de GeoINTA.
TEXTURA = [
    ("T", "suelo_textura_0_15cm", "0–30 cm usada para 0–15 cm"),
    ("T", "suelo_textura_15_30cm", "0–30 cm usada para 15–30 cm"),
    ("S", "suelo_textura_30_60cm", "30–100 cm usada para 30–60 cm"),
    ("S", "suelo_textura_60_100cm", "30–100 cm usada para 60–100 cm"),
]
PH = [
    ("T_PH_H2O", "suelo_ph_0_30cm", "0–30 cm"),
    ("S_PH_H2O", "suelo_ph_30_100cm", "30–100 cm"),
]
UNIDAD_TEXTURA = "clase textural (1 arenoso … 12 arcilloso, spec 021)"
# clase común 1-12 (spec 021): la misma que arma GeoINTA
NOMBRE_CLASE = {
    1: "arenoso", 2: "areno franco", 3: "franco arenoso", 4: "franco", 5: "franco limoso", 6: "limoso",
    7: "franco arcillo arenoso", 8: "franco arcilloso", 9: "franco arcillo limoso", 10: "arcillo arenoso",
    11: "arcillo limoso", 12: "arcilloso",
}


class ErrorHWSD(Exception):
    """La NASA no respondió o respondió algo ilegible."""


# ---------- triángulo textural del USDA -> clase común 1-12 ----------

def clase_textural(arena: float, arcilla: float) -> int:
    """Clase del USDA (código común 1-12) a partir de arena y arcilla en %. El limo es el resto.

    Sigue el orden de decisión estándar del triángulo del USDA (el mismo de los paquetes de edafología):
    se prueba una clase tras otra y gana la primera que entra.
    """
    limo = 100 - arena - arcilla
    if limo + 1.5 * arcilla < 15:
        return 1   # arenoso (sand)
    if limo + 2 * arcilla < 30:
        return 2   # areno franco (loamy sand)
    if (7 <= arcilla < 20 and arena > 52 and limo + 2 * arcilla >= 30) or \
            (arcilla < 7 and limo < 50 and limo + 2 * arcilla >= 30):
        return 3   # franco arenoso (sandy loam)
    if 7 <= arcilla < 27 and 28 <= limo <= 50 and arena <= 52:
        return 4   # franco (loam)
    if (limo >= 50 and 12 <= arcilla < 27) or (50 <= limo < 80 and arcilla < 12):
        return 5   # franco limoso (silt loam)
    if limo >= 80 and arcilla < 12:
        return 6   # limoso (silt)
    if 20 <= arcilla <= 35 and limo < 28 and arena > 45:
        return 7   # franco arcillo arenoso (sandy clay loam)
    if 27 <= arcilla < 40 and 20 <= arena <= 45:
        return 8   # franco arcilloso (clay loam)
    if 27 <= arcilla < 40 and arena <= 20:
        return 9   # franco arcillo limoso (silty clay loam)
    if arcilla >= 35 and arena > 45:
        return 10  # arcillo arenoso (sandy clay)
    if arcilla >= 40 and limo >= 40:
        return 11  # arcillo limoso (silty clay)
    return 12      # arcilloso (clay)


# ---------- lectura de una celda del NetCDF ----------

def _subdataset(ruta: Path) -> str:
    """La variable de datos del NetCDF (descarta lat/lon/crs). rasterio la abre como `netcdf:ruta:variable`."""
    import rasterio

    try:
        with rasterio.open(f"netcdf:{ruta}") as ds:
            subs = ds.subdatasets
    except rasterio.errors.RasterioIOError:
        return str(ruta)  # no es NetCDF (p. ej. un GeoTIFF de prueba): se abre directo
    if not subs:
        return f"netcdf:{ruta}"
    datos = [s for s in subs if not s.rsplit(":", 1)[-1].lower() in ("lat", "latitude", "lon", "longitude", "crs")]
    return (datos or subs)[0]


def valor_de_celda(ruta: Path, lat: float, lon: float) -> float | None:
    """Valor de la celda de 0,05° que contiene el punto, y la resolución del archivo en metros."""
    import math

    import rasterio
    from rasterio.windows import Window

    with rasterio.open(_subdataset(ruta)) as ds:
        x = lon % 360 if ds.bounds.right > 180 else lon
        fila, columna = ds.index(x, lat)
        if not (0 <= fila < ds.height and 0 <= columna < ds.width):
            raise ErrorHWSD(f"El punto ({lat}, {lon}) cae fuera de la grilla de HWSD")
        crudo = ds.read(1, window=Window(columna, fila, 1, 1))
        valor = float(crudo[0, 0]) if crudo.size else None
        relleno = ds.nodata
        grados = abs(ds.res[0])
    resolucion = round(grados * 111_320 * math.cos(math.radians(lat))) or RESOLUCION_M
    if valor is None or (relleno is not None and valor == relleno) or valor <= -9000 or valor != valor:
        return None, resolucion
    return valor, resolucion


# ---------- descarga (una vez) de cada capa ----------

def url_de_capa(cliente: httpx.Client, coleccion_id: str, capa: str) -> str:
    """URL de descarga del archivo de una capa de HWSD (ej. 'T_SAND' -> .../T_SAND.nc4)."""
    respuesta = cliente.get(f"{earthdata.URL_CMR}/granules.umm_json",
                            params={"collection_concept_id": coleccion_id, "page_size": 100})
    respuesta.raise_for_status()
    for item in respuesta.json().get("items", []):
        for enlace in item["umm"].get("RelatedUrls", []):
            url = enlace.get("URL", "")
            if (enlace.get("Type") == "GET DATA" and url.startswith("https")
                    and url.rsplit("/", 1)[-1].split(".")[0] == capa):
                return url
    raise ErrorHWSD(f"CMR no tiene el archivo de la capa {capa} de {PRODUCTO}")


def archivo_de_capa(cliente: httpx.Client, coleccion_id: str, capa: str) -> Path:
    """Baja el NetCDF de una capa a la caché (una sola vez: HWSD es fijo)."""
    url = url_de_capa(cliente, coleccion_id, capa)
    ruta = CARPETA / url.rsplit("/", 1)[-1]
    if ruta.exists() and ruta.stat().st_size > 0:
        return ruta
    CARPETA.mkdir(parents=True, exist_ok=True)
    parcial = ruta.with_suffix(ruta.suffix + ".parcial")
    with cliente.stream("GET", url, timeout=300) as descarga:
        if descarga.status_code in (401, 403):
            raise earthdata.ErrorNASA("La NASA negó la descarga de HWSD")
        descarga.raise_for_status()
        with open(parcial, "wb") as destino:
            for pedazo in descarga.iter_bytes():
                destino.write(pedazo)
    parcial.rename(ruta)
    return ruta


# ---------- observaciones ----------

NOTA_BASE = ("Respaldo de GeoINTA · HWSD v1.2 de la NASA (ORNL DAAC), base mundial de suelo · "
             "dato REGIONAL de modelo, no una medición del lote")


def _descartada(lote_id: str, variable: str, unidad: str, resolucion: int, motivo: str) -> Observacion:
    return Observacion(lote_id=lote_id, fecha=FECHA, variable=variable, unidad=unidad, fuente="HWSD",
                       resolucion_m=resolucion, valor=None, calidad="descartada", nota=f"{motivo} · {NOTA_BASE}")


def observacion_textura(lote_id: str, variable: str, detalle: str, arena: float | None, limo: float | None,
                        arcilla: float | None, resolucion: int) -> Observacion:
    base = dict(lote_id=lote_id, fecha=FECHA, variable=variable, unidad=UNIDAD_TEXTURA, fuente="HWSD",
                resolucion_m=resolucion)
    valores = [arena, limo, arcilla]
    if any(v is None for v in valores) or not all(0 <= v <= 100 for v in valores):
        return _descartada(lote_id, variable, UNIDAD_TEXTURA, resolucion,
                           f"HWSD sin textura válida en la celda (arena {arena}, limo {limo}, arcilla {arcilla})")
    codigo = clase_textural(arena, arcilla)
    nota = (f"arena {arena:.0f} %, limo {limo:.0f} %, arcilla {arcilla:.0f} % → {NOMBRE_CLASE[codigo]} "
            f"(clase común {codigo}) · celda de 0,05° (~{resolucion} m), {detalle} · {NOTA_BASE}")
    return Observacion(**base, valor=float(codigo), calidad="dudosa", nota=nota)


def observacion_ph(lote_id: str, variable: str, detalle: str, ph: float | None, resolucion: int) -> Observacion:
    base = dict(lote_id=lote_id, fecha=FECHA, variable=variable, unidad="pH", fuente="HWSD",
                resolucion_m=resolucion)
    if ph is None or not 0 < ph <= 14:
        return _descartada(lote_id, variable, "pH", resolucion, f"HWSD sin pH válido en la celda ({ph})")
    return Observacion(**base, valor=round(ph, 2), calidad="dudosa",
                       nota=f"pH {ph:.2f} en {detalle} · celda de 0,05° (~{resolucion} m) · {NOTA_BASE}")


def obtener_suelo(lote_id: str, poligono: dict, cliente: httpx.Client | None = None) -> list[Observacion]:
    """Textura (4 profundidades) y pH (2) del lote, leídos de HWSD. Respaldo de GeoINTA."""
    from shapely.geometry import shape

    validar_poligono(poligono)
    centro = shape(poligono).centroid
    lat, lon = centro.y, centro.x
    cliente = earthdata.cliente_autorizado(cliente)
    coleccion_id = earthdata.coleccion_vigente(cliente, PRODUCTO)
    if coleccion_id is None:
        raise ErrorHWSD(f"CMR no tiene la colección {PRODUCTO}")
    try:
        # cada capa se lee una vez; las de textura (T_SAND/T_SILT/T_CLAY/S_SAND/S_CLAY) comparten lectura
        capas = {}

        def leer(capa: str) -> tuple[float | None, int]:
            if capa not in capas:
                ruta = archivo_de_capa(cliente, coleccion_id, capa)
                capas[capa] = valor_de_celda(ruta, lat, lon)
            return capas[capa]

        t_arena, resol = leer("T_SAND")
        t_limo = leer("T_SILT")[0]
        t_arcilla = leer("T_CLAY")[0]
        s_arena = leer("S_SAND")[0]
        s_arcilla = leer("S_CLAY")[0]
        s_limo = None if (s_arena is None or s_arcilla is None) else 100 - s_arena - s_arcilla

        observaciones = []
        for capa, variable, detalle in TEXTURA:
            if capa == "T":
                observaciones.append(observacion_textura(lote_id, variable, detalle, t_arena, t_limo, t_arcilla, resol))
            else:
                observaciones.append(observacion_textura(lote_id, variable, detalle, s_arena, s_limo, s_arcilla, resol))
        for capa, variable, detalle in PH:
            ph, resol_ph = leer(capa)
            observaciones.append(observacion_ph(lote_id, variable, detalle, ph, resol_ph))
    except earthdata.FaltanCredenciales:
        raise
    except earthdata.ErrorNASA:
        raise
    except (httpx.HTTPError, ValueError, KeyError, OSError, ErrorHWSD) as error:
        raise ErrorHWSD(f"No se pudo leer HWSD de la NASA: {type(error).__name__}: {error}") from error
    return observaciones


# ---------- conexión con el núcleo (spec 009) ----------

SATELITES = [Satelite("GeoINTA:HWSD", lambda lote, desde, hasta: obtener_suelo(lote["id"], lote["poligono"]),
                      respaldo_de="GeoINTA", estatico=True)]

router = APIRouter(tags=["HWSD (pruebas internas)"])


class PedidoSuelo(BaseModel):
    lote_id: str
    poligono: dict


@router.post("/suelo-respaldo", response_model=list[Observacion])
def suelo_respaldo(pedido: PedidoSuelo) -> list[Observacion]:
    try:
        validar_poligono(pedido.poligono)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener_suelo(pedido.lote_id, pedido.poligono)
    except earthdata.FaltanCredenciales as error:
        raise HTTPException(status_code=503, detail=str(error))
    except (ErrorHWSD, earthdata.ErrorNASA) as error:
        raise HTTPException(status_code=502, detail=str(error))
