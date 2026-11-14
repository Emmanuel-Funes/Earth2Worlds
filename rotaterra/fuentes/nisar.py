"""Conector NISAR: radar en banda L a 20 m sobre el lote, con nubes o sin nubes (spec 054).

NISAR es la misión de radar de la NASA y la ISRO (agencia socia permitida, spec 008). El producto GCOV da cuánto
"rebota" el radar en el suelo y la planta (retrodispersión gamma0, ya corregida por el relieve), en dos
polarizaciones: HH (sube con el suelo mojado y la rugosidad) y HV (sube con la biomasa del cultivo).

Cada archivo pesa ~1,8 GB. No se baja: se leen por HTTP solo los pedazos (de ~1 MB) que caen sobre el lote.
El producto es **provisional** (NASA todavía no lo dio por validado): todo dato sale como mucho "dudoso".
"""

import io
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

PRODUCTOS = ("NISAR_L2_GCOV_V1", "NISAR_L2_GCOV_PROVISIONAL_V1")  # el validado primero, cuando la NASA lo publique
GRILLA = "science/LSAR/GCOV/grids/frequencyA"
IDENTIFICACION = "science/LSAR/identification"
CAPAS = {"radar_hh_db": "HHHH", "radar_hv_db": "HVHV"}
RELLENO_MASCARA = 255
RESOLUCION_M = 20
MAX_DIAS = 366
HILOS = 4
BLOQUE = 2 * 2 ** 20          # bytes por pedido HTTP
UNIDAD = "dB"
UMBRAL_DUDOSA = 60.0          # % de píxeles válidos del lote; con producto provisional nunca llega a "buena"
UMBRAL_DESCARTADA = 20.0


class ErrorNISAR(Exception):
    """La NASA no respondió o el archivo no se pudo leer."""


@dataclass
class Granulo:
    nombre: str
    producto: str
    inicio: datetime
    url: str


# ---------- lectura por pedazos (sin bajar el archivo) ----------

class ArchivoRemoto(io.RawIOBase):
    """Archivo de solo lectura que trae por HTTP (Range) solo los bloques que h5py pide, y los guarda en memoria."""

    def __init__(self, cliente: httpx.Client, url: str, bloque: int = BLOQUE,
                 sin_token: httpx.Client | None = None):
        respuesta = cliente.get(url, headers={"Range": "bytes=0-0"}, follow_redirects=False)
        # ASF redirige a un enlace firmado de CloudFront; el token de Earthdata no viaja a CloudFront
        self.url = respuesta.headers["location"] if respuesta.is_redirect else url
        self._http = (sin_token or httpx.Client(timeout=120)) if respuesta.is_redirect else cliente
        if not respuesta.is_redirect:
            respuesta.raise_for_status()
        primera = self._http.get(self.url, headers={"Range": "bytes=0-0"})
        primera.raise_for_status()
        self.tamano = int(primera.headers["content-range"].rsplit("/", 1)[-1])
        self.bloque, self.pos, self.bloques = bloque, 0, {}

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, desplazamiento: int, desde: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.pos, io.SEEK_END: self.tamano}[desde]
        self.pos = max(0, base + desplazamiento)
        return self.pos

    def _bloque(self, numero: int) -> bytes:
        if numero not in self.bloques:
            inicio = numero * self.bloque
            fin = min(inicio + self.bloque, self.tamano) - 1
            respuesta = self._http.get(self.url, headers={"Range": f"bytes={inicio}-{fin}"})
            respuesta.raise_for_status()
            self.bloques[numero] = respuesta.content
        return self.bloques[numero]

    def readinto(self, destino) -> int:
        cuanto = min(len(destino), self.tamano - self.pos)
        if cuanto <= 0:
            return 0
        partes, pos, fin = [], self.pos, self.pos + cuanto
        while pos < fin:
            numero, corrido = divmod(pos, self.bloque)
            trozo = self._bloque(numero)[corrido:corrido + fin - pos]
            partes.append(trozo)
            pos += len(trozo)
        datos = b"".join(partes)
        destino[:len(datos)] = datos
        self.pos += len(datos)
        return len(datos)

    @property
    def leidos_mb(self) -> float:
        return sum(len(b) for b in self.bloques.values()) / 2 ** 20


# ---------- cálculo puro (testeable sin internet) ----------

def validar_pedido(poligono: dict, desde: date, hasta: date) -> None:
    validar_poligono(poligono)
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise ValueError(f"El rango supera {MAX_DIAS} días")


def ventana(xs: np.ndarray, ys: np.ndarray, caja: tuple[float, float, float, float],
            margen: int = 1) -> tuple[slice, slice] | None:
    """Filas y columnas de la grilla (centros xs, ys) que cubren la caja (x0, y0, x1, y1). None si el lote cae afuera."""
    x0, y0, x1, y1 = caja
    columnas = np.nonzero((xs >= x0 - abs(xs[1] - xs[0])) & (xs <= x1 + abs(xs[1] - xs[0])))[0]
    filas = np.nonzero((ys >= y0 - abs(ys[1] - ys[0])) & (ys <= y1 + abs(ys[1] - ys[0])))[0]
    if columnas.size == 0 or filas.size == 0:
        return None
    return (slice(max(filas.min() - margen, 0), min(filas.max() + margen + 1, ys.size)),
            slice(max(columnas.min() - margen, 0), min(columnas.max() + margen + 1, xs.size)))


def a_db(potencia: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return 10 * np.log10(potencia)


def resumir_capa(potencia: np.ndarray, dentro: np.ndarray, mascara: np.ndarray | None) -> tuple[float | None, float]:
    """Mediana en dB de los píxeles del lote con dato (potencia > 0, máscara distinta de relleno) y % válido.

    La mediana se toma sobre la potencia y recién después se pasa a dB (igual da, y no promedia logaritmos).
    """
    validos = dentro & np.isfinite(potencia) & (potencia > 0)
    if mascara is not None:
        validos &= mascara != RELLENO_MASCARA
    total = int(dentro.sum())
    pct = 100.0 * int(validos.sum()) / total if total else 0.0
    if not validos.any():
        return None, pct
    return float(a_db(np.median(potencia[validos]))), pct


def a_observacion(lote_id: str, fecha: date, variable: str, valor: float | None, pct: float,
                  detalle: str) -> Observacion:
    base = dict(lote_id=lote_id, fecha=fecha, variable=variable, unidad=UNIDAD, fuente="NISAR",
                resolucion_m=RESOLUCION_M)
    if valor is None or pct < UMBRAL_DESCARTADA:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"El lote quedó fuera de la imagen o sin dato (válidos {pct:.0f}%) · {detalle}")
    texto = f"válidos {pct:.0f}% · {detalle}"
    if pct < UMBRAL_DUDOSA:
        texto = f"Lote parcialmente cubierto · {texto}"
    return Observacion(**base, valor=round(valor, 2), calidad="dudosa", nota=texto)


def quedarse_con_la_mejor(candidatas: list[tuple[list[Observacion], float]]) -> list[Observacion]:
    """Una fecha, un par HH/HV: el de la imagen que más cubre el lote."""
    por_fecha: dict[date, list[tuple[list[Observacion], float]]] = {}
    for par, pct in candidatas:
        por_fecha.setdefault(par[0].fecha, []).append((par, pct))
    elegidas = []
    for fecha in sorted(por_fecha):
        par, _ = max(por_fecha[fecha], key=lambda o: (o[0][0].valor is not None, o[1]))
        elegidas += par
    return elegidas


def texto(valor) -> str:
    if isinstance(valor, np.ndarray):
        valor = valor.item() if valor.size == 1 else valor.tolist()
    return valor.decode() if isinstance(valor, bytes) else str(valor)


# ---------- acceso a la NASA ----------

def buscar_granulos(cliente: httpx.Client, desde: date, hasta: date,
                    caja: tuple[float, float, float, float]) -> list[Granulo]:
    """Imágenes del producto validado si existe; si no, las provisionales."""
    for producto in PRODUCTOS:
        coleccion = earthdata.coleccion_vigente(cliente, producto)
        if coleccion is None:
            continue
        respuesta = cliente.get(f"{earthdata.URL_CMR}/granules.umm_json", params={
            "collection_concept_id": coleccion, "page_size": 500, "sort_key": "start_date",
            "bounding_box": ",".join(str(c) for c in caja),
            "temporal": f"{desde.isoformat()}T00:00:00Z,{hasta.isoformat()}T23:59:59Z"})
        respuesta.raise_for_status()
        granulos = []
        for item in respuesta.json()["items"]:
            umm = item["umm"]
            urls = [u["URL"] for u in umm.get("RelatedUrls", [])
                    if u.get("Type") == "GET DATA" and u["URL"].startswith("https") and u["URL"].endswith(".h5")]
            inicio = umm["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"]
            if urls:
                granulos.append(Granulo(umm["GranuleUR"], producto,
                                        datetime.fromisoformat(inicio.replace("Z", "+00:00")).astimezone(timezone.utc),
                                        urls[0]))
        if granulos:
            return granulos
    return []


def leer(archivo, poligono: dict) -> dict:
    """Recorte del lote de HH y HV, la máscara, qué píxeles caen en el lote y datos de la pasada."""
    import h5py
    import shapely
    from rasterio.warp import transform_geom
    from shapely.geometry import shape

    with h5py.File(archivo, "r") as f:
        grilla = f[GRILLA]
        epsg = int(np.asarray(grilla["projection"][()]).item())
        lote = shape(transform_geom("EPSG:4326", f"EPSG:{epsg}", poligono))
        xs, ys = grilla["xCoordinates"][:], grilla["yCoordinates"][:]
        recorte = ventana(xs, ys, lote.bounds)
        identificacion = f[IDENTIFICACION] if IDENTIFICACION in f else {}
        pasada = {k: texto(identificacion[k][()]) for k in ("orbitPassDirection", "trackNumber", "frameNumber")
                  if k in identificacion}
        if recorte is None:
            return {"pasada": pasada, "recorte": None}
        filas, columnas = recorte
        x, y = np.meshgrid(xs[columnas], ys[filas])
        datos = {"pasada": pasada, "recorte": recorte, "dentro": shapely.contains_xy(lote, x, y),
                 "mascara": grilla["mask"][filas, columnas] if "mask" in grilla else None}
        if not datos["dentro"].any():  # lote más chico que un píxel de 20 m: el píxel más cercano al centro
            centro = lote.centroid
            distancia = (x - centro.x) ** 2 + (y - centro.y) ** 2
            datos["dentro"] = distancia == distancia.min()
        for variable, capa in CAPAS.items():
            datos[variable] = grilla[capa][filas, columnas].astype("float64") if capa in grilla else None
    return datos


def procesar(lote_id: str, poligono: dict, lon: float, granulo: Granulo,
             cliente: httpx.Client | None = None) -> tuple[list[Observacion], float]:
    archivo = ArchivoRemoto(cliente, granulo.url) if cliente is not None else granulo.url
    datos = leer(archivo, poligono)
    fecha = (granulo.inicio + timedelta(hours=lon / 15)).date()  # día en hora solar del lote
    p = datos["pasada"]
    orbita = {"Ascending": "ascendente", "Descending": "descendente"}.get(p.get("orbitPassDirection"), "?")
    provisional = "PROVISIONAL" in granulo.producto
    detalle = (f"NISAR banda L, gamma0 corregido por relieve · {'producto PROVISIONAL de la NASA · ' if provisional else ''}"
               f"órbita {orbita}, traza {p.get('trackNumber', '?')} · pasada {granulo.inicio:%Y-%m-%d %H:%M} UTC")
    if isinstance(archivo, ArchivoRemoto):
        detalle += f" · leídos {archivo.leidos_mb:.0f} MB del archivo"
    detalle += f" · {granulo.nombre}"
    if datos["recorte"] is None:
        par = [a_observacion(lote_id, fecha, v, None, 0.0, detalle) for v in CAPAS]
        return par, 0.0
    resumenes = {v: resumir_capa(datos[v], datos["dentro"], datos["mascara"]) if datos[v] is not None else (None, 0.0)
                 for v in CAPAS}
    hh, hv = resumenes["radar_hh_db"][0], resumenes["radar_hv_db"][0]
    if hh is not None and hv is not None:
        detalle = f"HV − HH {hv - hh:.1f} dB (más alto = más planta) · {detalle}"
    par = [a_observacion(lote_id, fecha, v, valor, pct, detalle) for v, (valor, pct) in resumenes.items()]
    return par, min(pct for _, pct in resumenes.values())


def obtener(lote_id: str, poligono: dict, desde: date, hasta: date, cliente: httpx.Client | None = None,
            hilos: int = HILOS) -> list[Observacion]:
    """Retrodispersión HH y HV (dB) del lote por pasada de NISAR. Sin pasadas: lista vacía."""
    from shapely.geometry import shape

    validar_pedido(poligono, desde, hasta)
    geometria = shape(poligono)
    lon = geometria.centroid.x
    try:
        cliente = earthdata.cliente_autorizado(cliente)
        granulos = [g for g in buscar_granulos(cliente, desde - timedelta(days=1), hasta + timedelta(days=1),
                                               geometria.bounds)
                    if desde <= (g.inicio + timedelta(hours=lon / 15)).date() <= hasta]
    except earthdata.FaltanCredenciales:
        raise
    except (httpx.HTTPError, KeyError, ValueError, earthdata.ErrorNASA) as error:
        raise ErrorNISAR(f"No se pudo buscar NISAR en CMR: {error}") from error

    def uno(granulo):
        try:
            return procesar(lote_id, poligono, lon, granulo, cliente), None
        except Exception as error:  # un archivo ilegible no inventa nada: queda descartado con el motivo
            return None, f"{type(error).__name__}: {str(error).split('?')[0]}"

    with ThreadPoolExecutor(max_workers=hilos) as grupo:
        resultados = list(grupo.map(uno, granulos))
    errores = [e for _, e in resultados if e]
    if granulos and len(errores) == len(granulos):
        raise ErrorNISAR(f"No se pudo leer ninguna imagen de NISAR: {errores[0]}")
    candidatas = []
    for granulo, (hecho, error) in zip(granulos, resultados):
        if hecho:
            candidatas.append(hecho)
        else:
            fecha = (granulo.inicio + timedelta(hours=lon / 15)).date()
            par = [a_observacion(lote_id, fecha, v, None, 0.0, f"No se pudo leer el archivo: {error} · {granulo.nombre}")
                   for v in CAPAS]
            candidatas.append((par, -1.0))
    return quedarse_con_la_mejor(candidatas)


# ---------- conexión con el núcleo (spec 009) ----------

# Fuente propia de dos variables nuevas (radar_hh_db y radar_hv_db). No es respaldo de nadie: es el único dato
# del lote que no depende de las nubes, para seguir humedad del suelo y crecimiento cuando HLS está tapado.
SATELITES = [Satelite("NISAR", lambda lote, desde, hasta: obtener(lote["id"], lote["poligono"], desde, hasta))]

router = APIRouter(tags=["NISAR (pruebas internas)"])


class PedidoNISAR(BaseModel):
    lote_id: str
    poligono: dict
    desde: date
    hasta: date


@router.post("/radar", response_model=list[Observacion])
def radar(pedido: PedidoNISAR) -> list[Observacion]:
    """Retrodispersión de radar NISAR (HH y HV, dB) del lote, por pasada."""
    try:
        validar_pedido(pedido.poligono, pedido.desde, pedido.hasta)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener(pedido.lote_id, pedido.poligono, pedido.desde, pedido.hasta)
    except earthdata.FaltanCredenciales as error:
        raise HTTPException(status_code=503, detail=str(error))
    except ErrorNISAR as error:
        raise HTTPException(status_code=502, detail=str(error))
