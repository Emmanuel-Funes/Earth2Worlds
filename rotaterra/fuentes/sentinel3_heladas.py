"""Conector Sentinel-3 SLSTR LST nocturna: segundo respaldo de heladas, después de MODIS (spec 051).

Respaldo de VIIRS_LST (variable temp_sup_min_c). La fuente es el producto oficial de temperatura de la
**superficie** de la ESA, SL_2_LST (SLSTR de Sentinel-3A y 3B, 1 km), que solo publica el portal
Copernicus Data Space Ecosystem (la NASA no lo redistribuye). Pide una cuenta gratis de Copernicus:
COPERNICUS_USERNAME / COPERNICUS_PASSWORD como variables de entorno o secrets, nunca en el código.

Satélite independiente (spec 009): no importa a ningún otro satélite. Da la temperatura de la superficie
(suelo/canopeo), no la del aire: la helada agronómica se decide con esto más el criterio del productor.
"""

import io
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

import httpx
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rotaterra.contrato import Observacion
from rotaterra.fuentes.registro import Satelite
from rotaterra.geo import validar_poligono

URL_TOKEN = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
URL_CATALOGO = "https://catalogue.dataspace.copernicus.eu/odata/v1"
URL_DESCARGA = "https://download.dataspace.copernicus.eu/odata/v1"
SATELITES_S3 = {"S3A": "Sentinel-3A", "S3B": "Sentinel-3B"}
# archivo dentro del producto -> variables que se leen
ARCHIVOS = {"LST_in.nc": ("LST",), "geodetic_in.nc": ("latitude_in", "longitude_in"),
            "flags_in.nc": ("confidence_in",)}
CERO_ABS = 273.15
KELVIN_MIN, KELVIN_MAX = 150.0, 400.0  # rango físico sano; afuera es relleno
RESOLUCION_M = 1000
HILOS = 4
MAX_DIAS = 366
UNIDAD = "°C"
UMBRAL_HELADA = 0.0           # a 0 °C o menos de superficie, se avisa riesgo de helada
UMBRAL_BUENA = 60.0           # % de píxeles válidos del lote (mismos umbrales que VIIRS y MODIS)
UMBRAL_DESCARTADA = 20.0
MARGEN_GRADOS = 0.03          # alrededor del lote se miran ~3 km para ubicar los píxeles de 1 km
MAX_M_PIXEL = 1000            # el píxel más cercano al centro del lote tiene que estar a menos de un píxel
# es de noche si la hora solar del lugar está entre las 18 y las 6
NOCHE_DESDE, NOCHE_HASTA = 18, 6

_NOMBRE = re.compile(r"^(S3[AB])_SL_2_LST____(\d{8}T\d{6})_")


class FaltanCredencialesCopernicus(Exception):
    """No están COPERNICUS_USERNAME / COPERNICUS_PASSWORD."""


class ErrorSentinel3Heladas(Exception):
    """Copernicus no respondió o respondió algo ilegible."""


# ---------- cálculo puro (testeable sin internet) ----------

def validar_pedido(poligono: dict, desde: date, hasta: date) -> None:
    validar_poligono(poligono)
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise ValueError(f"El rango supera {MAX_DIAS} días")


def hora_solar(utc: datetime, lon: float) -> datetime:
    """Hora solar del lugar: la UTC corrida 4 minutos por grado de longitud."""
    return utc + timedelta(hours=lon / 15)


def es_de_noche(utc: datetime, lon: float) -> bool:
    hora = hora_solar(utc, lon).hour
    return hora >= NOCHE_DESDE or hora < NOCHE_HASTA


def noche_de(utc: datetime, lon: float) -> date:
    """Fecha de la madrugada a la que pertenece el paso: las 22 h del 21/9 y la 1 h del 22/9 son la noche del 22/9
    (la misma convención de VIIRS y MODIS, que fechan la madrugada)."""
    return (hora_solar(utc, lon) + timedelta(hours=24 - NOCHE_DESDE)).date()


def leer_nombre(nombre: str) -> tuple[str, datetime] | None:
    """'S3A_SL_2_LST____20260922T021617_...' -> ('Sentinel-3A', 2026-09-22 02:16:17 UTC)."""
    hallado = _NOMBRE.match(nombre)
    if not hallado:
        return None
    return SATELITES_S3[hallado[1]], datetime.strptime(hallado[2], "%Y%m%dT%H%M%S")


def elegir_productos(productos: list[dict], lon: float) -> list[dict]:
    """Solo pasos de noche; si un paso viene en dos versiones, la definitiva (NT) gana a la rápida (NR)."""
    por_paso: dict[tuple, dict] = {}
    for producto in productos:
        leido = leer_nombre(producto["Name"])
        if leido is None or not es_de_noche(leido[1], lon):
            continue
        clave = leido
        if clave not in por_paso or ("_NT_" in producto["Name"] and "_NT_" not in por_paso[clave]["Name"]):
            por_paso[clave] = producto
    return [por_paso[c] for c in sorted(por_paso, key=lambda c: c[1])]


def escalar(conjunto) -> np.ndarray:
    """Valores físicos de una variable NetCDF leída con h5py: aplica relleno, escala y desplazamiento."""
    crudo = conjunto[()]
    valores = crudo.astype("float64")
    relleno = conjunto.attrs.get("_FillValue")
    if relleno is not None:
        valores[crudo == np.atleast_1d(relleno)[0]] = np.nan
    valores *= float(np.atleast_1d(conjunto.attrs.get("scale_factor", 1.0))[0])
    valores += float(np.atleast_1d(conjunto.attrs.get("add_offset", 0.0))[0])
    return valores


def bits_de(atributos) -> dict[str, int]:
    """Nombre de bandera -> bit, de 'flag_meanings' y 'flag_masks' del NetCDF."""
    nombres = atributos["flag_meanings"]
    nombres = (nombres.decode() if isinstance(nombres, bytes) else str(nombres)).split()
    return dict(zip(nombres, (int(m) for m in np.atleast_1d(atributos["flag_masks"]))))


def limpios(confianza: np.ndarray, bits: dict[str, int]) -> np.ndarray:
    """True donde el píxel es tierra y no tiene nube según la ESA (bandera summary_cloud)."""
    tierra = bits.get("land", 0)
    malos = bits.get("summary_cloud", 0) | bits.get("unfilled", 0)
    es_tierra = (confianza & tierra) != 0 if tierra else np.ones(confianza.shape, dtype=bool)
    return es_tierra & ((confianza & malos) == 0)


def distancia_km(lat: np.ndarray, lon: np.ndarray, lat0: float, lon0: float) -> np.ndarray:
    return 111.2 * np.hypot(lat - lat0, (lon - lon0) * np.cos(np.radians(lat0)))


def mascara_lote(poligono: dict, lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, str] | None:
    """Píxeles con el centro dentro del lote; si no hay, el más cercano al centro; None si el lote no está en la franja."""
    from shapely import contains_xy
    from shapely.geometry import shape

    lote = shape(poligono)
    dentro = contains_xy(lote, lon, lat)
    if dentro.any():
        return dentro, ""
    centro = lote.centroid
    distancia = distancia_km(lat, lon, centro.y, centro.x)
    if not np.isfinite(distancia).any() or 1000 * np.nanmin(distancia) > MAX_M_PIXEL:
        return None
    return distancia == np.nanmin(distancia), "lote menor a un píxel de 1 km: se usa el píxel del centro · "


def resumir(lote_id: str, poligono: dict, datos: dict[str, np.ndarray], fecha: date, satelite: str,
            hora_local: str) -> tuple[Observacion, float] | None:
    """Temperatura de superficie MÍNIMA de los píxeles del lote para un paso nocturno, y su % válido."""
    lugar = mascara_lote(poligono, datos["lat"], datos["lon"])
    if lugar is None:
        return None
    dentro, aviso = lugar
    kelvin = datos["lst"]
    validos = dentro & datos["limpios"] & np.isfinite(kelvin) & (kelvin >= KELVIN_MIN) & (kelvin <= KELVIN_MAX)
    total, n_validos = int(dentro.sum()), int(validos.sum())
    pct = 100.0 * n_validos / total if total else 0.0
    base = dict(lote_id=lote_id, fecha=fecha, variable="temp_sup_min_c", unidad=UNIDAD,
                fuente="SENTINEL3", resolucion_m=RESOLUCION_M)
    detalle = (f"Respaldo · Sentinel-3 SLSTR LST nocturna (temperatura de superficie, no del aire) · {aviso}"
               f"SL_2_LST ({satelite}, ESA Copernicus) · noche del {fecha}, paso de las {hora_local} hora solar "
               f"(temprano: la madrugada suele ser más fría) · "
               f"{total} píxeles de 1 km · válidos {pct:.0f}%")
    if pct < UMBRAL_DESCARTADA:
        return Observacion(**base, valor=None, calidad="descartada", nota=f"Nubes o sin dato · {detalle}"), pct
    valor = round(float(np.min(kelvin[validos]) - CERO_ABS), 1)
    riesgo = " · riesgo de helada (≤ 0 °C de superficie)" if valor <= UMBRAL_HELADA else ""
    calidad = "buena" if pct >= UMBRAL_BUENA else "dudosa"
    return Observacion(**base, valor=valor, calidad=calidad, nota=f"{detalle}{riesgo}"), pct


# ---------- acceso a Copernicus Data Space ----------

class Copernicus:
    """Cliente con el token de Copernicus; lo renueva si vence (dura ~10 minutos)."""

    def __init__(self, cliente: httpx.Client | None = None):
        self.usuario = os.environ.get("COPERNICUS_USERNAME")
        self.clave = os.environ.get("COPERNICUS_PASSWORD")
        if not self.usuario or not self.clave:
            raise FaltanCredencialesCopernicus("Faltan COPERNICUS_USERNAME y COPERNICUS_PASSWORD")
        self.cliente = cliente or httpx.Client(timeout=120)
        self.token = self._pedir_token()

    def _pedir_token(self) -> str:
        respuesta = self.cliente.post(URL_TOKEN, data={"client_id": "cdse-public", "grant_type": "password",
                                                       "username": self.usuario, "password": self.clave})
        if respuesta.status_code in (400, 401):
            raise ErrorSentinel3Heladas("Copernicus rechazó el usuario o la contraseña")
        respuesta.raise_for_status()
        return respuesta.json()["access_token"]

    def bajar(self, url: str) -> bytes:
        """GET con el token, siguiendo a mano los redireccionamientos para no perder el token (así lo pide la ESA)."""
        for intento in range(2):
            actual = url
            for _ in range(5):
                respuesta = self.cliente.get(actual, headers={"Authorization": f"Bearer {self.token}"},
                                             follow_redirects=False)
                if respuesta.status_code not in (301, 302, 303, 307, 308):
                    break
                actual = respuesta.headers["Location"]
            if respuesta.status_code == 401 and intento == 0:
                self.token = self._pedir_token()
                continue
            respuesta.raise_for_status()
            return respuesta.content
        raise ErrorSentinel3Heladas("Copernicus negó el acceso")


def filtro_odata(poligono: dict, desde: date, hasta: date) -> str:
    from shapely.geometry import shape

    oeste, sur, este, norte = shape(poligono).bounds
    caja = f"POLYGON(({oeste} {sur},{este} {sur},{este} {norte},{oeste} {norte},{oeste} {sur}))"
    # la noche del 'desde' arranca la tarde anterior
    return (f"Collection/Name eq 'SENTINEL-3' and contains(Name,'SL_2_LST') "
            f"and OData.CSC.Intersects(area=geography'SRID=4326;{caja}') "
            f"and ContentDate/Start ge {(desde - timedelta(days=1)).isoformat()}T12:00:00.000Z "
            f"and ContentDate/Start le {hasta.isoformat()}T12:00:00.000Z")


def buscar_productos(cliente: httpx.Client, poligono: dict, desde: date, hasta: date) -> list[dict]:
    """Productos SL_2_LST del catálogo (público, sin token) que tocan el lote en el período."""
    params = {"$filter": filtro_odata(poligono, desde, hasta), "$orderby": "ContentDate/Start asc", "$top": 1000}
    respuesta = cliente.get(f"{URL_CATALOGO}/Products", params=params)
    respuesta.raise_for_status()
    return respuesta.json().get("value", [])


def leer_producto(copernicus: Copernicus, producto: dict, poligono: dict) -> dict[str, np.ndarray] | None:
    """Baja solo los 3 NetCDF que hacen falta del producto y recorta la zona del lote."""
    import h5py
    from shapely.geometry import shape

    abiertos = {}
    for archivo in ARCHIVOS:
        url = f"{URL_DESCARGA}/Products({producto['Id']})/Nodes({producto['Name']})/Nodes({archivo})/$value"
        abiertos[archivo] = h5py.File(io.BytesIO(copernicus.bajar(url)), "r")
    try:
        geo = abiertos["geodetic_in.nc"]
        lat, lon = escalar(geo["latitude_in"]), escalar(geo["longitude_in"])
        oeste, sur, este, norte = shape(poligono).bounds
        cerca = ((lat >= sur - MARGEN_GRADOS) & (lat <= norte + MARGEN_GRADOS)
                 & (lon >= oeste - MARGEN_GRADOS) & (lon <= este + MARGEN_GRADOS))
        if not cerca.any():
            return None
        filas, columnas = np.nonzero(cerca)
        ventana = (slice(filas.min(), filas.max() + 1), slice(columnas.min(), columnas.max() + 1))
        confianza = abiertos["flags_in.nc"]["confidence_in"]
        return {"lat": lat[ventana], "lon": lon[ventana], "lst": escalar(abiertos["LST_in.nc"]["LST"])[ventana],
                "limpios": limpios(confianza[()][ventana].astype("int64"), bits_de(confianza.attrs))}
    finally:
        for abierto in abiertos.values():
            abierto.close()


def obtener_heladas(lote_id: str, poligono: dict, desde: date, hasta: date,
                    cliente: httpx.Client | None = None, hilos: int = HILOS) -> list[Observacion]:
    """Temperatura de superficie nocturna mínima del lote por noche (Sentinel-3A y 3B); por noche gana la más limpia."""
    from shapely.geometry import shape

    validar_pedido(poligono, desde, hasta)
    centro = shape(poligono).centroid
    try:
        copernicus = Copernicus(cliente)
        productos = elegir_productos(buscar_productos(copernicus.cliente, poligono, desde, hasta), centro.x)
        with ThreadPoolExecutor(max_workers=hilos) as grupo:
            ventanas = list(grupo.map(lambda p: leer_producto(copernicus, p, poligono), productos))
    except (httpx.HTTPError, KeyError, ValueError, OSError) as error:
        raise ErrorSentinel3Heladas(f"No se pudo obtener la LST de Sentinel-3: {error}") from error
    mejores: dict[date, tuple[Observacion, float]] = {}
    for producto, datos in zip(productos, ventanas):
        if datos is None:
            continue  # el paso no cubre el lote
        satelite, utc = leer_nombre(producto["Name"])
        fecha = noche_de(utc, centro.x)
        resultado = resumir(lote_id, poligono, datos, fecha, satelite, f"{hora_solar(utc, centro.x):%H:%M}")
        if resultado is None:
            continue
        obs, pct = resultado
        if desde <= fecha <= hasta and (fecha not in mejores or pct > mejores[fecha][1]):
            mejores[fecha] = (obs, pct)
    return [obs for _, (obs, _) in sorted(mejores.items())]


# ---------- conexión con el núcleo (spec 009) ----------

# Segundo respaldo de VIIRS_LST (la alerta de heladas, variable temp_sup_min_c): entra cuando VIIRS y MODIS
# (orden 1, spec 035) no traen dato.
SATELITES = [Satelite("VIIRS_LST:SENTINEL3",
                      lambda lote, desde, hasta: obtener_heladas(lote["id"], lote["poligono"], desde, hasta),
                      respaldo_de="VIIRS_LST", orden=2)]

router = APIRouter(tags=["Sentinel-3 heladas (pruebas internas)"])


class PedidoHeladas(BaseModel):
    lote_id: str
    poligono: dict
    desde: date
    hasta: date


@router.post("/heladas/sentinel3", response_model=list[Observacion])
def heladas_sentinel3(pedido: PedidoHeladas) -> list[Observacion]:
    try:
        validar_pedido(pedido.poligono, pedido.desde, pedido.hasta)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener_heladas(pedido.lote_id, pedido.poligono, pedido.desde, pedido.hasta)
    except FaltanCredencialesCopernicus as error:
        raise HTTPException(status_code=503, detail=str(error))
    except ErrorSentinel3Heladas as error:
        raise HTTPException(status_code=502, detail=str(error))
