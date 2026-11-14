"""Conector Sentinel-3 (ESA): NDVI diario de 300 m del lote, respaldo de HLS entre Sentinel-2 y VIIRS (spec 050).

Producto SYN L2 (Synergy OLCI + SLSTR: reflectancia de superficie sobre tierra) de Sentinel-3A y 3B, que la
NASA redistribuye en LAADS DAAC con la misma cuenta de Earthdata. Cada pasada es un .zip de 350-900 MB con
NetCDF guardados sin comprimir adentro: se leen por HTTP solo los pedazos que tocan al lote (~5 MB por pasada).
"""

import io
import re
import struct
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime

import httpx
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rotaterra.contrato import Observacion
from rotaterra.fuentes import earthdata
from rotaterra.fuentes.registro import Satelite
from rotaterra.geo import validar_poligono

# Sentinel-3A y 3B pasan cada uno cada 1-2 días por San Luis: entre los dos, casi una pasada diaria
PRODUCTOS = {"S3A_SY_2_SYN": "Sentinel-3A", "S3B_SY_2_SYN": "Sentinel-3B"}
ROJO, NIR = "Oa08", "Oa17"  # bandas OLCI de 665 nm y 865 nm
ESCALA_REFLECTANCIA = 0.0001
RELLENO_REFLECTANCIA = -10000
ESCALA_GRADOS = 1e-6
RESOLUCION_M = 300
MAX_DIAS = 366
HILOS = 12
UNIDAD = "índice (-1 a 1)"
UMBRAL_BUENA = 60.0       # % de píxeles válidos: mismos umbrales que HLS, Sentinel-2, VIIRS y MODIS
UMBRAL_DESCARTADA = 20.0
MARGEN_PIXELES = 48       # los puntos de enlace van cada 64 columnas: con 48 de cada lado la ventana cubre el lote
MAX_KM_PUNTO_ENLACE = 25  # si el punto de enlace más cercano queda más lejos, el lote está fuera de la pasada
MAX_M_PIXEL = 300         # el píxel más cercano al centro del lote tiene que estar a menos de un píxel

# SYN_flags: banderas que descartan el píxel (los nombres y bits se leen del archivo)
SYN_MALOS = ("SYN_cloud", "SYN_snow_risk", "SYN_high_error", "SYN_SDR_OOR", "SYN_partly_water")
# CLOUD_flags (de OLCI): CLOUD, CLOUD_AMBIGUOUS, CLOUD_MARGIN, SNOW_ICE; cualquiera descarta el píxel

BLOQUE = 1 << 19          # se piden pedazos de 512 KB y se guardan los últimos 64 (32 MB por pasada)
MAX_BLOQUES = 64

_NOMBRE = re.compile(r"_(\d{8})T(\d{6})_")


class ErrorSentinel3(Exception):
    """LAADS no respondió o la pasada no se pudo leer."""


# ---------- lectura de un .zip remoto por pedazos ----------

class ArchivoRemoto(io.RawIOBase):
    """Archivo por HTTP que se lee por rangos de bytes, con los últimos pedazos guardados en memoria."""

    def __init__(self, cliente: httpx.Client, url: str):
        self.cliente = cliente
        respuesta = cliente.get(url, headers={"Range": "bytes=0-0"})
        if respuesta.status_code in (401, 403):
            raise earthdata.ErrorNASA("LAADS negó el acceso: ¿está autorizada la aplicación LAADS en Earthdata?")
        respuesta.raise_for_status()
        rango = respuesta.headers.get("content-range", "")
        if respuesta.status_code != 206 or "/" not in rango:
            raise ErrorSentinel3(f"LAADS no deja leer por pedazos {url}")
        self.url = str(respuesta.url)  # después del redireccionamiento a la nube
        self.tamanio = int(rango.split("/")[1])
        self.posicion = 0
        self.bloques: dict[int, bytes] = {}
        self.descargado = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.posicion

    def seek(self, desplazamiento: int, desde: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.posicion, io.SEEK_END: self.tamanio}[desde]
        self.posicion = base + desplazamiento
        return self.posicion

    def _bloque(self, numero: int) -> bytes:
        if numero not in self.bloques:
            inicio = numero * BLOQUE
            fin = min(inicio + BLOQUE, self.tamanio) - 1
            respuesta = self.cliente.get(self.url, headers={"Range": f"bytes={inicio}-{fin}"})
            respuesta.raise_for_status()
            if len(self.bloques) >= MAX_BLOQUES:
                self.bloques.pop(next(iter(self.bloques)))
            self.bloques[numero] = respuesta.content
            self.descargado += len(respuesta.content)
        return self.bloques[numero]

    def readinto(self, destino) -> int:
        if self.posicion >= self.tamanio:
            return 0
        numero, corrimiento = divmod(self.posicion, BLOQUE)
        datos = self._bloque(numero)[corrimiento:corrimiento + len(destino)]
        destino[:len(datos)] = datos
        self.posicion += len(datos)
        return len(datos)


class Miembro(io.RawIOBase):
    """Un archivo guardado sin comprimir dentro del .zip, visto como un archivo aparte."""

    def __init__(self, archivo: io.RawIOBase, inicio: int, tamanio: int):
        self.archivo, self.inicio, self.tamanio, self.posicion = archivo, inicio, tamanio, 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.posicion

    def seek(self, desplazamiento: int, desde: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.posicion, io.SEEK_END: self.tamanio}[desde]
        self.posicion = base + desplazamiento
        return self.posicion

    def readinto(self, destino) -> int:
        cuanto = min(len(destino), self.tamanio - self.posicion)
        if cuanto <= 0:
            return 0
        self.archivo.seek(self.inicio + self.posicion)
        datos = self.archivo.read(cuanto)
        destino[:len(datos)] = datos
        self.posicion += len(datos)
        return len(datos)


class Pasada:
    """Una pasada SYN (.zip) abierta: da acceso a cada NetCDF de adentro sin bajar el resto."""

    def __init__(self, archivo: io.RawIOBase):
        self.archivo = archivo
        self.zip = zipfile.ZipFile(archivo)
        self.abiertos: list = []

    def netcdf(self, sufijo: str):
        import h5py

        infos = [i for i in self.zip.infolist() if i.filename.endswith(f"/{sufijo}") or i.filename == sufijo]
        if not infos:
            raise ErrorSentinel3(f"La pasada no trae {sufijo}")
        info = infos[0]
        if info.compress_type != zipfile.ZIP_STORED:
            raise ErrorSentinel3(f"{sufijo} viene comprimido dentro del .zip: no se puede leer por pedazos")
        self.archivo.seek(info.header_offset)
        encabezado = self.archivo.read(30)
        largo_nombre, largo_extra = struct.unpack("<HH", encabezado[26:30])
        inicio = info.header_offset + 30 + largo_nombre + largo_extra
        abierto = h5py.File(io.BufferedReader(Miembro(self.archivo, inicio, info.file_size), 1 << 16), "r")
        self.abiertos.append(abierto)
        return abierto

    def cerrar(self) -> None:
        for abierto in reversed(self.abiertos):
            abierto.close()
        self.abiertos.clear()


# ---------- cálculo puro (testeable sin internet) ----------

def validar_pedido(poligono: dict, desde: date, hasta: date) -> None:
    validar_poligono(poligono)
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise ValueError(f"El rango supera {MAX_DIAS} días")


def grilla_de_enlace(valores: np.ndarray, filas: int) -> np.ndarray:
    """Los puntos de enlace vienen en una tira: columna de enlace por columna de enlace, cada una con todas las filas.

    Verificado el 27/10/2026 en S3A_SY_2_SYN del 20/9/2026: 314.930 puntos = 77 columnas × 4.090 filas, y los
    primeros 4.090 bajan por la primera columna. Se devuelve como (filas, columnas de enlace).
    """
    return valores.reshape(valores.size // filas, filas).T


def distancia_km(lat: np.ndarray, lon: np.ndarray, lat0: float, lon0: float) -> np.ndarray:
    """Distancia aproximada (plana, sirve a pocos km) de cada punto a (lat0, lon0)."""
    return 111.2 * np.hypot(lat - lat0, (lon - lon0) * np.cos(np.radians(lat0)))


def ubicar(tp_lat: np.ndarray, tp_lon: np.ndarray, columnas: int, lat0: float, lon0: float) -> tuple[int, int] | None:
    """Fila y columna aproximadas del lote en la pasada, o None si el lote queda fuera de la franja."""
    distancia = distancia_km(tp_lat, tp_lon, lat0, lon0)
    if not np.isfinite(distancia).any():
        return None
    fila, enlace = np.unravel_index(np.nanargmin(distancia), distancia.shape)
    if distancia[fila, enlace] > MAX_KM_PUNTO_ENLACE:
        return None
    columna = round(enlace * (columnas - 1) / (tp_lat.shape[1] - 1))
    return int(fila), int(columna)


def bits_de(atributos) -> dict[str, int]:
    """Nombre de bandera -> bit, de 'flag_meanings' y 'flag_masks' del NetCDF."""
    nombres = atributos["flag_meanings"]
    nombres = (nombres.decode() if isinstance(nombres, bytes) else str(nombres)).split()
    return dict(zip(nombres, (int(m) for m in np.atleast_1d(atributos["flag_masks"]))))


def mascara_lote(poligono: dict, lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, str]:
    """Píxeles con el centro dentro del lote; si no hay ninguno, el más cercano al centro del lote."""
    from shapely import contains_xy
    from shapely.geometry import shape

    lote = shape(poligono)
    dentro = contains_xy(lote, lon, lat)
    if dentro.any():
        return dentro, ""
    centro = lote.centroid
    distancia = distancia_km(lat, lon, centro.y, centro.x)
    return distancia == np.nanmin(distancia), "lote menor a un píxel: se usa el píxel del centro · "


def ndvi(rojo_crudo: np.ndarray, nir_crudo: np.ndarray) -> np.ndarray:
    """NDVI de la reflectancia de superficie; NaN donde falta una banda o queda fuera de -1..1."""
    rojo = rojo_crudo.astype("float64") * ESCALA_REFLECTANCIA
    nir = nir_crudo.astype("float64") * ESCALA_REFLECTANCIA
    rojo[rojo_crudo == RELLENO_REFLECTANCIA] = np.nan
    nir[nir_crudo == RELLENO_REFLECTANCIA] = np.nan
    with np.errstate(divide="ignore", invalid="ignore"):
        resultado = (nir - rojo) / (nir + rojo)
    resultado[~np.isfinite(resultado) | (resultado < -1) | (resultado > 1)] = np.nan
    return resultado


def limpios(syn: np.ndarray, bits_syn: dict[str, int], nubes: np.ndarray) -> np.ndarray:
    """True donde el píxel es tierra, sin nube, sin nieve y con la reflectancia bien calculada."""
    malos = 0
    for nombre in SYN_MALOS:
        malos |= bits_syn.get(nombre, 0)
    tierra = bits_syn.get("SYN_land", 0)
    es_tierra = (syn & tierra) != 0 if tierra else np.ones(syn.shape, dtype=bool)
    return es_tierra & ((syn & malos) == 0) & (nubes == 0)


def fecha_de(nombre: str) -> date:
    """'S3A_SY_2_SYN____20260920T133311_...' -> 2026-09-20 (hora UTC ~13:30, mañana en Argentina)."""
    hallado = _NOMBRE.search(nombre)
    if not hallado:
        raise ErrorSentinel3(f"No se entiende la fecha de {nombre}")
    return datetime.strptime(hallado[1], "%Y%m%d").date()


def resumir(lote_id: str, fecha: date, datos: dict[str, np.ndarray], satelite: str,
            aviso: str = "") -> tuple[Observacion, float]:
    """Observación del lote para una pasada y su % de píxeles válidos."""
    dentro, valores, validos = datos["dentro"], datos["ndvi"], datos["validos"]
    usados = dentro & validos & np.isfinite(valores)
    total, n = int(dentro.sum()), int(usados.sum())
    pct = 100.0 * n / total if total else 0.0
    base = dict(lote_id=lote_id, fecha=fecha, variable="ndvi", unidad=UNIDAD, fuente="SENTINEL3",
                resolucion_m=RESOLUCION_M)
    origen = (f"Respaldo de HLS · {aviso}{satelite} SYN L2 (OLCI+SLSTR, ESA, vía NASA LAADS) · "
              f"{total} píxeles de 300 m")
    if pct < UMBRAL_DESCARTADA:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"Nubes, nieve o sin dato · {origen} · válidos {pct:.0f}%"), pct
    elegidos = valores[usados]
    p10, mediana, p90 = np.percentile(elegidos, [10, 50, 90])
    detalle = f"{origen} · media {elegidos.mean():.2f} · p10 {p10:.2f} · p90 {p90:.2f} · válidos {pct:.0f}%"
    calidad = "buena" if pct >= UMBRAL_BUENA else "dudosa"
    if calidad == "dudosa":
        detalle = f"lote parcialmente cubierto · {detalle}"
    return Observacion(**base, valor=round(float(mediana), 3), calidad=calidad, nota=detalle), pct


# ---------- acceso a LAADS (NASA) ----------

def granulos(cliente: httpx.Client, coleccion: str, desde: date, hasta: date,
             caja: tuple[float, float, float, float]) -> list[tuple[str, str]]:
    """(nombre, URL https del .zip) de cada pasada que CMR dice que toca la caja del lote."""
    params = {"collection_concept_id": coleccion, "page_size": 2000, "sort_key": "start_date",
              "temporal": f"{desde.isoformat()}T00:00:00Z,{hasta.isoformat()}T23:59:59Z",
              "bounding_box": ",".join(str(c) for c in caja)}
    respuesta = cliente.get(f"{earthdata.URL_CMR}/granules.umm_json", params=params)
    respuesta.raise_for_status()
    hallados = []
    for item in respuesta.json()["items"]:
        urls = [u["URL"] for u in item["umm"].get("RelatedUrls", [])
                if u["URL"].startswith("https://") and u["URL"].endswith(".zip")]
        if urls:
            hallados.append((urls[0].rsplit("/", 1)[-1], urls[0]))
    return hallados


def leer_pasada(pasada: Pasada, poligono: dict) -> dict[str, np.ndarray] | None:
    """Ventana del lote con NDVI, máscara de píxeles limpios y máscara del lote; None si el lote no está en la franja."""
    from shapely.geometry import shape

    centro = shape(poligono).centroid
    geo = pasada.netcdf("geolocation.nc")
    filas, columnas = geo["lat"].shape
    enlace = pasada.netcdf("tiepoints_olci.nc")
    tp_lat = grilla_de_enlace(enlace["OLC_TP_lat"][:] * ESCALA_GRADOS, filas)
    tp_lon = grilla_de_enlace(enlace["OLC_TP_lon"][:] * ESCALA_GRADOS, filas)
    lugar = ubicar(tp_lat, tp_lon, columnas, centro.y, centro.x)
    if lugar is None:
        return None
    fila, columna = lugar
    f0, f1 = max(fila - MARGEN_PIXELES, 0), min(fila + MARGEN_PIXELES + 1, filas)
    c0, c1 = max(columna - MARGEN_PIXELES, 0), min(columna + MARGEN_PIXELES + 1, columnas)
    lat = geo["lat"][f0:f1, c0:c1] * ESCALA_GRADOS
    lon = geo["lon"][f0:f1, c0:c1] * ESCALA_GRADOS
    if 1000 * np.nanmin(distancia_km(lat, lon, centro.y, centro.x)) > MAX_M_PIXEL:
        return None  # borde de la franja: el lote cae afuera
    # se achica la ventana al rectángulo del lote con un píxel de margen
    dentro, aviso = mascara_lote(poligono, lat, lon)
    ff, cc = np.nonzero(dentro)
    g0, g1 = max(ff.min() - 1, 0), min(ff.max() + 2, lat.shape[0])
    h0, h1 = max(cc.min() - 1, 0), min(cc.max() + 2, lat.shape[1])
    ventana = (slice(f0 + g0, f0 + g1), slice(c0 + h0, c0 + h1))
    banderas = pasada.netcdf("flags.nc")
    syn = banderas["SYN_flags"]
    validos = limpios(syn[ventana].astype("int64"), bits_de(syn.attrs), banderas["CLOUD_flags"][ventana])
    rojo = pasada.netcdf(f"Syn_{ROJO}_reflectance.nc")[f"SDR_{ROJO}"][ventana]
    nir = pasada.netcdf(f"Syn_{NIR}_reflectance.nc")[f"SDR_{NIR}"][ventana]
    return {"ndvi": ndvi(rojo, nir), "validos": validos, "dentro": dentro[g0:g1, h0:h1], "aviso": aviso}


def procesar(cliente: httpx.Client, url: str, poligono: dict) -> dict | None:
    pasada = Pasada(io.BufferedReader(ArchivoRemoto(cliente, url), BLOQUE))
    try:
        return leer_pasada(pasada, poligono)
    finally:
        pasada.cerrar()


def obtener_ndvi(lote_id: str, poligono: dict, desde: date, hasta: date,
                 cliente: httpx.Client | None = None, hilos: int = HILOS) -> list[Observacion]:
    """NDVI Sentinel-3 del lote (3A y 3B); si hay dos pasadas el mismo día, gana la más limpia."""
    from shapely.geometry import shape

    validar_pedido(poligono, desde, hasta)
    try:
        cliente = earthdata.cliente_autorizado(cliente)
        pedidos: list[tuple[str, str, str]] = []  # (satélite, archivo, url)
        for producto, satelite in PRODUCTOS.items():
            coleccion = earthdata.coleccion_vigente(cliente, producto)
            if coleccion is not None:
                pedidos += [(satelite, nombre, url) for nombre, url in
                            granulos(cliente, coleccion, desde, hasta, shape(poligono).bounds)]
        if not pedidos:
            raise ErrorSentinel3(f"CMR no tiene pasadas de {', '.join(PRODUCTOS)} sobre el lote")
        with ThreadPoolExecutor(max_workers=hilos) as grupo:
            ventanas = list(grupo.map(lambda p: procesar(cliente, p[2], poligono), pedidos))
    except earthdata.FaltanCredenciales:
        raise
    except ErrorSentinel3:
        raise
    except (httpx.HTTPError, KeyError, ValueError, OSError, zipfile.BadZipFile, earthdata.ErrorNASA) as error:
        raise ErrorSentinel3(f"No se pudo obtener el NDVI de Sentinel-3: {error}") from error
    mejores: dict[date, tuple[Observacion, float]] = {}
    for (satelite, nombre, _), datos in zip(pedidos, ventanas):
        if datos is None:
            continue  # la pasada no cubre el lote
        obs, pct = resumir(lote_id, fecha_de(nombre), datos, satelite, datos["aviso"])
        if desde <= obs.fecha <= hasta and (obs.fecha not in mejores or pct > mejores[obs.fecha][1]):
            mejores[obs.fecha] = (obs, pct)
    return [obs for _, (obs, _) in sorted(mejores.items())]


# ---------- conexión con el núcleo (spec 009) ----------

# respaldo de HLS entre Sentinel-2 (orden 1) y VIIRS (orden 2): con el mismo orden que VIIRS entra antes
# porque el núcleo desempata por nombre ("HLS:SENTINEL3" < "HLS:VIIRS"); MODIS sigue último (orden 3)
SATELITES = [Satelite("HLS:SENTINEL3",
                      lambda lote, desde, hasta: obtener_ndvi(lote["id"], lote["poligono"], desde, hasta),
                      respaldo_de="HLS", orden=2)]

router = APIRouter(tags=["Sentinel-3 (pruebas internas)"])


class PedidoNdvi(BaseModel):
    lote_id: str
    poligono: dict
    desde: date
    hasta: date


@router.post("/ndvi/sentinel3", response_model=list[Observacion])
def ndvi_sentinel3(pedido: PedidoNdvi) -> list[Observacion]:
    try:
        validar_pedido(pedido.poligono, pedido.desde, pedido.hasta)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener_ndvi(pedido.lote_id, pedido.poligono, pedido.desde, pedido.hasta)
    except earthdata.FaltanCredenciales as error:
        raise HTTPException(status_code=503, detail=str(error))
    except ErrorSentinel3 as error:
        raise HTTPException(status_code=502, detail=str(error))
