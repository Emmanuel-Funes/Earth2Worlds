"""Conector SEPA INTA y GOES-19: agua en el suelo, anomalías, heladas, temperatura de superficie y Q de trigo (spec 023).

De dónde sale cada número (ver la spec 023, §5):
- **SEPA INTA (GeoSEPA):** balance hídrico por década desde mayo de 2024 (agua disponible hasta 2 m, confort hídrico,
  variación, drenaje y porcentaje de agua), y la última anomalía histórica de NDVI de 16 días y su persistencia.
  Son GeoTIFF; se lee solo el pedazo del lote con pedidos por rangos de bytes (nunca el mapa entero).
- **GOES-19 (NOAA):** los visores de heladas y de temperatura diurna de SEPA se calculan con GOES-19. Acá se lee el
  producto oficial de la NOAA (temperatura de superficie, topes nubosos, infrarrojo y rayos) del archivo abierto en AWS.
- **Q de trigo:** el INTA lo estima con el pronóstico GFS. Acá se calcula igual (Tb 4,5 °C) con datos de NASA POWER.
- Los productos de SEPA que solo existen como imagen de colores van con `valor: null` y la dirección de la imagen en
  la `nota`, para que el frontend la muestre. Nunca se lee un número de un color.
"""

import calendar
import math
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rotaterra.contrato import Observacion
from rotaterra.fuentes.registro import Satelite
from rotaterra.geo import validar_poligono

SEPA = "https://sepa.inta.gob.ar"
AGENTE = "Rotaterra/0.1 (+https://github.com/hernanfirmapaz-ops/N4-4-1.2)"
ENTORNO_GDAL = dict(GDAL_HTTP_TIMEOUT=30, GDAL_HTTP_MAX_RETRY=2, GDAL_HTTP_RETRY_DELAY=2,
                    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_USE_HEAD="NO",
                    GDAL_HTTP_USERAGENT=AGENTE)
CITA = "Fuente: SEPA, Instituto de Clima y Agua (CIRN-INTA)"
USO = ("uso autorizado por el CIRN-INTA para Rotaterra en la hackatón NASA; "
       "el uso comercial necesita acordar condiciones con el INTA")
MAX_DIAS = 366


# ---------- 1. agua en el suelo (GeoSEPA, por década) ----------

@dataclass(frozen=True)
class ProductoAgua:
    codigo: str          # nombre en GeoSEPA: ad, ch, db, dr, pj
    variable: str
    unidad: str
    rango: tuple[float, float]
    descripcion: str
    sin_calculo: float | None = None   # código que SEPA pone donde no calcula el producto
    motivo_sin_calculo: str = ""
    clases: dict | None = None         # si el raster trae clases y no cantidades: código -> significado


# leyenda del raster db, de su metodología (sepa.inta.gob.ar/productos/geosepa/agua_en_suelo/db/metodologia.pdf)
CLASES_VARIACION = {1: "disminución mayor a 30 mm", 2: "disminución menor a 30 mm", 3: "aumento menor a 30 mm",
                    4: "aumento entre 30 y 90 mm", 5: "aumento mayor a 90 mm"}

AGUA = [
    ProductoAgua("ad", "agua_disponible_2m", "mm", (0, 600), "agua disponible para la vegetación hasta 2 m, al final de la década"),
    ProductoAgua("ch", "confort_hidrico_inta", "%", (0, 100),
                 "confort hídrico (transpiración lograda ÷ demanda transpiratoria de la década)",
                 sin_calculo=-99, motivo_sin_calculo="SEPA no calcula el confort hídrico donde la cobertura verde "
                                                     "es menor al 20% (código -99)"),
    ProductoAgua("db", "variacion_agua_disponible_clase", "clase", (1, 5),
                 "variación del agua disponible respecto de la década anterior",
                 clases=CLASES_VARIACION),
    ProductoAgua("dr", "agua_excedente_inta", "mm", (0, 600), "agua excedente (drenaje) en la década"),
    ProductoAgua("pj", "agua_suelo_porcentaje", "%", (0, 100), "agua disponible en % de la capacidad potencial"),
]
INICIO_AGUA = date(2024, 5, 1)   # GeoSEPA publica el balance por década desde mayo de 2024
RESOLUCION_AGUA_M = 500


def decadas(desde: date, hasta: date) -> list[tuple[int, int, int, date]]:
    """Décadas (año, mes, década 1-3, último día) que terminan dentro del rango pedido."""
    salida = []
    anio, mes = desde.year, desde.month
    while date(anio, mes, 1) <= hasta:
        ultimo_mes = calendar.monthrange(anio, mes)[1]
        for d, fin in ((1, 10), (2, 20), (3, ultimo_mes)):
            dia = date(anio, mes, fin)
            if desde <= dia <= hasta:
                salida.append((anio, mes, d, dia))
        anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    return salida


def url_agua(producto: str, anio: int, mes: int, decada: int) -> str:
    return f"{SEPA}/productos/geosepa/agua_en_suelo/{producto}/tif/{producto}_{anio}{mes:02d}_{decada}.tif"


def leer_lote(url: str, poligono: dict) -> tuple[list[float], float]:
    """Valores de los píxeles del lote (con pedidos por rangos) y tamaño del píxel en metros."""
    import numpy as np
    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.windows import Window, from_bounds
    from shapely.geometry import shape

    geometria = shape(poligono)
    with rasterio.Env(**ENTORNO_GDAL), rasterio.open(("/vsicurl/" if url.startswith("http") else "") + url) as ds:
        # la ventana se agranda un píxel para no perder los bordes del lote al redondear
        ventana = from_bounds(*geometria.bounds, ds.transform)
        col, fila = math.floor(ventana.col_off), math.floor(ventana.row_off)
        ventana = Window(col, fila, math.ceil(ventana.col_off + ventana.width) - col + 1,
                         math.ceil(ventana.row_off + ventana.height) - fila + 1)
        datos = ds.read(1, window=ventana, masked=True, boundless=True)
        dentro = ~geometry_mask([poligono], out_shape=datos.shape, transform=ds.window_transform(ventana),
                                all_touched=True)
        if not dentro.any():  # lote más chico que un píxel: el píxel del centro
            fila, col = ds.index(geometria.centroid.x, geometria.centroid.y)
            datos = ds.read(1, window=Window(col, fila, 1, 1), masked=True, boundless=True)
            dentro = np.ones(datos.shape, bool)
        valores = datos[dentro]
        validos = [float(v) for v in valores.compressed() if math.isfinite(float(v))]
        return validos, abs(ds.res[0]) * 111_320


def _resumen(valores: list[float]) -> str:
    ordenados = sorted(valores)
    return f"mín {ordenados[0]:.1f} · máx {ordenados[-1]:.1f} · {len(valores)} píxeles"


def agua_del_lote(lote_id: str, poligono: dict, desde: date, hasta: date, leer=leer_lote) -> list[Observacion]:
    observaciones = []
    for anio, mes, decada, dia in decadas(max(desde, INICIO_AGUA), hasta):
        for p in AGUA:
            url = url_agua(p.codigo, anio, mes, decada)
            base = dict(lote_id=lote_id, fecha=dia, variable=p.variable, unidad=p.unidad, fuente="SEPA_INTA",
                        resolucion_m=RESOLUCION_AGUA_M)
            try:
                valores, _ = leer(url, poligono)
            except Exception as error:  # un raster que falta o no responde no frena a los demás
                observaciones.append(Observacion(**base, valor=None, calidad="descartada",
                                                 nota=f"SEPA no entregó {p.codigo}_{anio}{mes:02d}_{decada}: "
                                                      f"{type(error).__name__}. {url}"))
                continue
            sin_calculo = [v for v in valores if p.sin_calculo is not None and v == p.sin_calculo]
            valores = [v for v in valores if p.sin_calculo is None or v != p.sin_calculo]
            if not valores:
                motivo = p.motivo_sin_calculo if sin_calculo else "Sin dato en el lote (píxeles sin valor)"
                observaciones.append(Observacion(**base, valor=None, calidad="descartada", nota=f"{motivo}. {url}"))
                continue
            aparte = (f" · {len(sin_calculo)} píxeles sin cálculo quedaron afuera ({p.motivo_sin_calculo})"
                      if sin_calculo else "")
            if p.clases:  # clases: va la que más superficie ocupa en el lote, y el reparto en la nota
                conteo = {c: sum(1 for v in valores if round(v) == c) for c in sorted({round(v) for v in valores})}
                clase = max(conteo, key=conteo.get)
                reparto = ", ".join(f"{c} ({p.clases.get(c, 'código sin leyenda')}) {100 * n / len(valores):.0f}%"
                                    for c, n in conteo.items())
                observaciones.append(Observacion(
                    **base, valor=float(clase), calidad="buena" if clase in p.clases else "dudosa",
                    nota=f"Clase que más ocupa el lote: {clase} = {p.clases.get(clase, 'código sin leyenda')} "
                         f"({p.descripcion}, década {decada} de {mes:02d}/{anio}) · reparto: {reparto} · "
                         f"balance hídrico SEPA · {CITA}; {USO}"))
                continue
            media = sum(valores) / len(valores)
            minimo, maximo = p.rango
            calidad = "buena" if minimo <= media <= maximo else "dudosa"
            observaciones.append(Observacion(
                **base, valor=round(media, 2), calidad=calidad,
                nota=f"Media del lote de {p.descripcion}, década {decada} de {mes:02d}/{anio} · {_resumen(valores)}{aparte} · "
                     f"balance hídrico SEPA · {CITA}; {USO}"))
    if desde < INICIO_AGUA <= hasta or hasta < INICIO_AGUA:
        observaciones.append(Observacion(
            lote_id=lote_id, fecha=min(hasta, INICIO_AGUA - timedelta(days=1)), variable="agua_disponible_2m",
            valor=None, unidad="mm", fuente="SEPA_INTA", resolucion_m=RESOLUCION_AGUA_M, calidad="descartada",
            nota="GeoSEPA publica el balance hídrico por década recién desde mayo de 2024"))
    return observaciones


# ---------- 2. anomalías de NDVI de 16 días (solo el último período tiene GeoTIFF) ----------

# variable, unidad, carpeta, prefijo del GeoTIFF, prefijo de la imagen (que sí tiene historial), descripción
ANOMALIAS = [
    ("anomalia_historica_ndvi", "%", "anomalia_16d_historica", "sc-", "sc_",
     "anomalía del NDVI respecto de la media histórica (16 días, MODIS)"),
    ("duracion_anomalia_negativa", "días", "persistencia_16d", "persistencia-", "persistencia_",
     "días seguidos con NDVI por debajo de la media histórica"),
]


def _fecha_juliana(texto: str) -> date:
    return date(int(texto[:4]), 1, 1) + timedelta(days=int(texto[4:]) - 1)


def ultimo_periodo(cliente: httpx.Client, carpeta: str, prefijo: str) -> str | None:
    """AAAADDD del único GeoTIFF que SEPA deja publicado, leído del enlace de la página del producto."""
    pagina = cliente.get(f"{SEPA}/productos/indices_de_vegetacion/{carpeta}/", timeout=30)
    pagina.raise_for_status()
    encontrados = re.findall(re.escape(prefijo) + r"(\d{7})\.tif", pagina.text)
    return max(encontrados) if encontrados else None


def anomalias_del_lote(lote_id: str, poligono: dict, desde: date, hasta: date, cliente: httpx.Client,
                       leer=leer_lote) -> list[Observacion]:
    """SEPA solo deja el GeoTIFF del último compuesto de 16 días: si cae en el rango pedido, va el número."""
    observaciones = []
    for variable, unidad, carpeta, prefijo, prefijo_imagen, descripcion in ANOMALIAS:
        base = dict(lote_id=lote_id, variable=variable, unidad=unidad, fuente="SEPA_INTA", resolucion_m=250)
        carpeta_url = f"{SEPA}/productos/indices_de_vegetacion/{carpeta}"
        try:
            periodo = ultimo_periodo(cliente, carpeta, prefijo)
        except httpx.HTTPError as error:
            observaciones.append(Observacion(**base, fecha=hasta, valor=None, calidad="descartada",
                                             nota=f"SEPA no respondió la página del producto ({type(error).__name__})"))
            continue
        inicio = _fecha_juliana(periodo) if periodo else None
        if inicio is None or not desde - timedelta(days=15) <= inicio <= hasta:
            ultimo = f" (el último publicado empieza el {inicio:%d/%m/%Y})" if inicio else ""
            observaciones.append(Observacion(
                **base, fecha=hasta, valor=None, calidad="descartada",
                nota=f"SEPA solo publica el GeoTIFF del último compuesto de 16 días{ultimo}; para este rango hay solo "
                     f"imágenes de colores, sin número: {carpeta_url}/{prefijo_imagen}AAAADDD.gif · {CITA}"))
            continue
        url = f"{carpeta_url}/{prefijo}{periodo}.tif"
        try:
            valores, _ = leer(url, poligono)
        except Exception as error:  # noqa: BLE001
            observaciones.append(Observacion(**base, fecha=inicio, valor=None, calidad="descartada",
                                             nota=f"SEPA no entregó {url}: {type(error).__name__}"))
            continue
        if not valores:
            observaciones.append(Observacion(**base, fecha=inicio, valor=None, calidad="descartada",
                                             nota=f"Sin dato en el lote. {url}"))
            continue
        observaciones.append(Observacion(
            **base, fecha=inicio, valor=round(sum(valores) / len(valores), 2), calidad="buena",
            nota=f"Media del lote: {descripcion}, compuesto que empieza el {inicio:%d/%m/%Y} · {_resumen(valores)} · "
                 f"{CITA}; {USO}"))
    return observaciones


# ---------- 3. productos que SEPA publica solo como imagen ----------

# variable, unidad, ruta de la imagen por período ({anio}, {mes}, {decada}, {dia}), paso
IMAGENES = [
    ("ndvi_10d_inta", "adimensional", "sepaproductos/compuesto_10d/iv_{anio}{mes:02d}_{decada}.gif", "decada"),
    ("ndvi_16d_inta", "adimensional", "geosepa/indices_de_vegetacion/compuesto_16d_ndvi/jpg/iv_{anio}{dia:03d}.jpg",
     "16d"),
    ("evi_16d_inta", "adimensional", "geosepa/indices_de_vegetacion/compuesto_16d_evi/jpg/iv_{anio}{dia:03d}.jpg",
     "16d"),
    ("ndvi_mensual_inta", "adimensional", "sepaproductos/mensual/iv_{anio}{mes:02d}.gif", "mes"),
    ("vci_8d_inta", "%", "sepaproductos/vci_8d/vi_{anio}{dia:03d}.jpg", "8d"),
    ("etr_10d_inta", "mm/día", "sepaproductos/et_10d/et_{anio}{mes:02d}_{decada}.gif", "decada"),
    ("anomalia_etr_10d", "%", "sepaproductos/anomalia_et/et_{anio}{mes:02d}_{decada}.jpg", "decada"),
    ("radiacion_solar_mensual", "MJ/m²", "sepaproductos/rg_mes/rg_{anio}{mes:02d}.jpeg", "mes"),
]
# productos que solo existen como la imagen más reciente, sin historial
IMAGENES_ACTUALES = [
    ("anomalia_ndvi_inta", "%", "DF_DECADA.gif"),
    ("temp_superficie_10d", "°C", "TS.gif"),
]
MAX_IMAGENES = 40


def _periodos_imagen(paso: str, desde: date, hasta: date) -> list[tuple[dict, date]]:
    if paso == "decada":
        return [(dict(anio=a, mes=m, decada=d), dia) for a, m, d, dia in decadas(desde, hasta)]
    if paso == "mes":
        salida, anio, mes = [], desde.year, desde.month
        while date(anio, mes, 1) <= hasta:
            fin = date(anio, mes, calendar.monthrange(anio, mes)[1])
            if desde <= fin <= hasta:
                salida.append((dict(anio=anio, mes=mes), fin))
            anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
        return salida
    salida = []
    for anio in range(desde.year, hasta.year + 1):
        for dia in range(1, 366, 16 if paso == "16d" else 8):
            inicio = date(anio, 1, 1) + timedelta(days=dia - 1)
            if desde <= inicio <= hasta:
                salida.append((dict(anio=anio, dia=dia), inicio))
    return salida


def imagenes_del_lote(lote_id: str, desde: date, hasta: date, cliente: httpx.Client) -> list[Observacion]:
    """Una observación sin valor por período, con la imagen de SEPA en la nota si existe (se comprueba con HEAD)."""
    observaciones, pedidos = [], 0
    for variable, unidad, patron, paso in IMAGENES:
        for campos, fecha in _periodos_imagen(paso, desde, hasta):
            url = f"{SEPA}/productos/{patron.format(**{'mes': 1, 'decada': 1, 'dia': 1, **campos})}"
            existe = None
            if pedidos < MAX_IMAGENES:
                pedidos += 1
                try:
                    existe = cliente.head(url, timeout=15).status_code == 200
                except httpx.HTTPError:
                    existe = None
            if existe is False:
                continue
            aviso = "" if existe else " (no se comprobó que exista)"
            observaciones.append(Observacion(
                lote_id=lote_id, fecha=fecha, variable=variable, valor=None, unidad=unidad, fuente="SEPA_INTA",
                resolucion_m=1000, calidad="descartada",
                nota=f"SEPA lo publica solo como mapa de colores, sin el número: no se lee un valor del color. "
                     f"Imagen{aviso}: {url} · {CITA}"))
    if hasta >= date.today() - timedelta(days=10):
        for variable, unidad, archivo in IMAGENES_ACTUALES:
            observaciones.append(Observacion(
                lote_id=lote_id, fecha=min(hasta, date.today()), variable=variable, valor=None, unidad=unidad,
                fuente="SEPA_INTA", resolucion_m=1000, calidad="descartada",
                nota=f"SEPA lo publica solo como la imagen más reciente, sin historial ni número. "
                     f"Imagen: {SEPA}/productos/sepaproductos/{archivo} · {CITA}"))
    return observaciones


# ---------- 4. Q de trigo con NASA POWER (fórmula del INTA, Tb 4,5 °C) ----------

URL_POWER = "https://power.larc.nasa.gov/api/temporal/daily/point"
TB_TRIGO = 4.5
MARGEN_Q = 0.5


def cociente_fototermal(radiacion_mj: float | None, temp_media: float | None) -> tuple[float | None, str]:
    """Q = radiación global (MJ/m²/día) ÷ (temperatura media − 4,5 °C). Sin dato si la diferencia es ≤ 0,5 °C."""
    if radiacion_mj is None or temp_media is None:
        return None, "POWER no tiene radiación o temperatura para la fecha"
    termico = temp_media - TB_TRIGO
    if termico <= MARGEN_Q:
        return None, f"Temperatura media {temp_media:.1f} °C: Tmedia − Tb ≤ {MARGEN_Q} °C, Q no se calcula (criterio INTA)"
    return round(radiacion_mj / termico, 3), ""


def q_trigo(lote_id: str, lat: float, lon: float, desde: date, hasta: date, cliente: httpx.Client) -> list[Observacion]:
    params = {"parameters": "T2M,ALLSKY_SFC_SW_DWN", "community": "AG", "latitude": lat, "longitude": lon,
              "start": desde.strftime("%Y%m%d"), "end": hasta.strftime("%Y%m%d"), "format": "JSON"}
    respuesta = cliente.get(URL_POWER, params=params, timeout=60)
    respuesta.raise_for_status()
    series = respuesta.json()["properties"]["parameter"]
    temp, rad = series.get("T2M", {}), series.get("ALLSKY_SFC_SW_DWN", {})
    limpio = lambda v: None if v is None or v == -999 else float(v)  # noqa: E731
    base = dict(lote_id=lote_id, variable="cociente_fototermal_trigo", unidad="MJ/m²/día/°C", fuente="POWER",
                resolucion_m=55000)
    origen = "Calculado con NASA POWER (radiación ALLSKY_SFC_SW_DWN y temperatura media T2M), Tb 4,5 °C, como el Q de SEPA"
    observaciones, por_decada = [], {}
    for dia in sorted(set(temp) | set(rad)):
        fecha = date(int(dia[:4]), int(dia[4:6]), int(dia[6:8]))
        r, t = limpio(rad.get(dia)), limpio(temp.get(dia))
        q, motivo = cociente_fototermal(r, t)
        observaciones.append(Observacion(**base, fecha=fecha, valor=q, calidad="buena" if q is not None else "descartada",
                                         nota=f"Q diario · {origen}" + (f" · {motivo}" if motivo else "")))
        if r is not None and t is not None:
            fin_decada = date(fecha.year, fecha.month, 10 if fecha.day <= 10 else 20 if fecha.day <= 20
                              else calendar.monthrange(fecha.year, fecha.month)[1])
            por_decada.setdefault(fin_decada, []).append((r, t))
    for fin, dias in sorted(por_decada.items()):
        if len(dias) < 8:  # década incompleta en el rango pedido
            continue
        q, motivo = cociente_fototermal(sum(d[0] for d in dias) / len(dias), sum(d[1] for d in dias) / len(dias))
        observaciones.append(Observacion(
            lote_id=lote_id, fecha=fin, variable="cociente_fototermal_trigo_10d", unidad="MJ/m²/día/°C",
            fuente="POWER", resolucion_m=55000, valor=q, calidad="buena" if q is not None else "descartada",
            nota=f"Q de la década ({len(dias)} días): radiación media ÷ (temperatura media − 4,5) · {origen}"
                 + (f" · {motivo}" if motivo else "")))
    return observaciones


# ---------- 5. GOES-19 (NOAA, archivo abierto en AWS) ----------

GOES19_DESDE = date(2025, 4, 7)   # GOES-19 es el GOES-Este operativo desde el 7/4/2025; antes, GOES-16
CUBOS = {"GOES-19": "https://noaa-goes19.s3.amazonaws.com", "GOES-16": "https://noaa-goes16.s3.amazonaws.com"}
HORAS_NOCHE = (7, 8, 9, 10)       # 4 a 7 h de la Argentina (UTC−3): cerca del mínimo térmico
HORAS_DIA = (16, 17, 18, 19)      # 13 a 16 h de la Argentina: cerca del máximo
MAX_DIAS_GOES = 31
RADIO_RAYOS_KM = 10
MINUTOS_RAYOS = 15
HILOS_GOES = 8
CANDADO_NETCDF = threading.Lock()


def satelite_goes(dia: date) -> str:
    return "GOES-19" if dia >= GOES19_DESDE else "GOES-16"


def archivos_goes(cliente: httpx.Client, producto: str, momento: datetime, filtro: str = "") -> list[str]:
    cubo = CUBOS[satelite_goes(momento.date())]
    prefijo = f"{producto}/{momento:%Y}/{momento:%j}/{momento:%H}/"
    r = cliente.get(cubo, params={"list-type": "2", "prefix": prefijo}, timeout=30)
    r.raise_for_status()
    return [f"{cubo}/{k}" for k in re.findall(r"<Key>([^<]+)</Key>", r.text) if filtro in k]


def leer_goes(url: str, variable: str, lat: float, lon: float, bajar: bool = False) -> tuple[float | None, int | None]:
    """Valor físico (K) y bandera de calidad DQF en el píxel del lote.

    Los archivos chicos (temperatura de superficie, ~0,6 MB) se bajan enteros una vez y se leen las dos variables del
    disco; los grandes (infrarrojo de disco completo) se leen por rangos de bytes, solo lo que hace falta.
    """
    import os
    import tempfile

    import rasterio
    from rasterio.warp import transform
    from rasterio.windows import Window

    def pixel(origen: str, nombre: str):
        with rasterio.Env(**ENTORNO_GDAL), rasterio.open(f"netcdf:{origen}:{nombre}") as ds:
            xs, ys = transform("EPSG:4326", ds.crs, [lon], [lat])
            fila, col = ds.index(xs[0], ys[0])
            crudo = ds.read(1, window=Window(col, fila, 1, 1), boundless=True)[0, 0]
            if ds.nodata is not None and crudo == ds.nodata:
                return None
            return float(crudo) * ds.scales[0] + ds.offsets[0]

    def leer(origen: str):
        valor = pixel(origen, variable)
        try:
            dqf = pixel(origen, "DQF")
        except Exception:
            dqf = None
        return valor, (int(dqf) if dqf is not None else None)

    if not bajar:
        return leer("/vsicurl/" + url)
    respuesta = httpx.get(url, timeout=60, headers={"User-Agent": AGENTE})
    respuesta.raise_for_status()
    descriptor, ruta = tempfile.mkstemp(suffix=".nc")
    try:
        with os.fdopen(descriptor, "wb") as archivo:
            archivo.write(respuesta.content)
        with CANDADO_NETCDF:  # la biblioteca netCDF no admite dos lecturas a la vez: se baja en paralelo, se lee de a una
            return leer(ruta)
    finally:
        os.remove(ruta)


CALIDAD_DQF = {0: "buena", 1: "buena", 2: "dudosa"}


def _temp_goes(lote_id: str, dia: date, variable: str, horas: tuple, extremo, lat: float, lon: float,
               cliente: httpx.Client, leer) -> Observacion:
    lecturas = []
    for hora in horas:
        momento = datetime(dia.year, dia.month, dia.day, hora, tzinfo=timezone.utc)
        try:
            urls = archivos_goes(cliente, "ABI-L2-LSTF", momento)
            if urls:
                valor, dqf = leer(urls[0], "LST", lat, lon, bajar=True)
                if valor is not None and dqf in CALIDAD_DQF:
                    lecturas.append((valor - 273.15, dqf, hora))
        except Exception:
            continue
    base = dict(lote_id=lote_id, fecha=dia, variable=variable, unidad="°C", fuente="GOES", resolucion_m=10000)
    sat = satelite_goes(dia)
    if not lecturas:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"{sat} sin temperatura de superficie válida en el lote entre las "
                                f"{horas[0] - 3} y las {horas[-1] - 3} h (nubes o sin pasada)")
    temp, dqf, hora = extremo(lecturas, key=lambda x: x[0])
    return Observacion(**base, valor=round(temp, 1), calidad=CALIDAD_DQF[dqf],
                       nota=f"{'Mínima' if extremo is min else 'Máxima'} de {len(lecturas)} lecturas horarias de "
                            f"temperatura de superficie (piel del suelo, no del aire) de {sat} ABI-L2-LSTF (NOAA), "
                            f"a las {hora - 3} h · {'riesgo de helada en superficie' if extremo is min and temp <= 0 else ''}"
                            .rstrip(" ·"))


def goes_del_lote(lote_id: str, lat: float, lon: float, desde: date, hasta: date, cliente: httpx.Client,
                  leer=leer_goes, ahora: datetime | None = None) -> list[Observacion]:
    ahora = ahora or datetime.now(timezone.utc)
    observaciones = []
    primero = max(desde, hasta - timedelta(days=MAX_DIAS_GOES - 1), date(2017, 12, 18))
    if primero > desde:
        observaciones.append(Observacion(
            lote_id=lote_id, fecha=desde, variable="temp_superficie_nocturna", valor=None, unidad="°C",
            fuente="GOES", resolucion_m=10000, calidad="descartada",
            nota=f"GOES se pide de a {MAX_DIAS_GOES} días como máximo; se leyeron los últimos {MAX_DIAS_GOES} del rango"))
    pedidos, dia = [], primero
    while dia <= min(hasta, ahora.date()):
        pedidos.append((dia, "temp_superficie_nocturna", HORAS_NOCHE, min))
        pedidos.append((dia, "temp_superficie_diurna", HORAS_DIA, max))
        dia += timedelta(days=1)
    # cada día y cada horario es independiente: se leen en paralelo (archivos públicos de la NOAA en AWS)
    with ThreadPoolExecutor(max_workers=HILOS_GOES) as hilos:
        observaciones += list(hilos.map(
            lambda p: _temp_goes(lote_id, p[0], p[1], p[2], p[3], lat, lon, cliente, leer), pedidos))
    if hasta >= ahora.date() - timedelta(days=1):
        observaciones += goes_ahora(lote_id, lat, lon, cliente, leer, ahora)
    return observaciones


def _ultimo(cliente: httpx.Client, producto: str, ahora: datetime, filtro: str = "") -> str | None:
    for atras in range(0, 3):
        urls = archivos_goes(cliente, producto, ahora - timedelta(hours=atras), filtro)
        if urls:
            return urls[-1]
    return None


def contar_rayos(urls: list[str], lat: float, lon: float, leer_vector=None) -> int:
    """Destellos de GLM a menos de RADIO_RAYOS_KM del lote (los archivos de 20 s se leen en paralelo)."""
    leer_vector = leer_vector or _destellos_glm
    total = 0
    with ThreadPoolExecutor(max_workers=HILOS_GOES) as hilos:
        for lats, lons in hilos.map(leer_vector, urls):
            for la, lo in zip(lats, lons):
                dx = (lo - lon) * 111.32 * math.cos(math.radians(lat))
                dy = (la - lat) * 110.57
                if math.hypot(dx, dy) <= RADIO_RAYOS_KM:
                    total += 1
    return total


def _destellos_glm(url: str) -> tuple[list[float], list[float]]:
    """Latitud y longitud de cada destello de un archivo GLM (chico: se baja entero y se lee del disco)."""
    import os
    import tempfile
    import warnings

    import rasterio
    respuesta = httpx.get(url, timeout=60, headers={"User-Agent": AGENTE})
    respuesta.raise_for_status()
    descriptor, ruta = tempfile.mkstemp(suffix=".nc")
    try:
        with os.fdopen(descriptor, "wb") as archivo:
            archivo.write(respuesta.content)
        salida = []
        with CANDADO_NETCDF, warnings.catch_warnings():
            warnings.simplefilter("ignore")  # un vector no tiene georreferencia: rasterio avisa, no es un error
            for nombre in ("flash_lat", "flash_lon"):
                with rasterio.Env(**ENTORNO_GDAL), rasterio.open(f"netcdf:{ruta}:{nombre}") as ds:
                    salida.append([float(v) for v in ds.read(1)[0]] if ds.width > 0 else [])
        return salida[0], salida[1]
    except rasterio.errors.RasterioIOError:  # archivo sin destellos: no trae las variables
        return [], []
    finally:
        os.remove(ruta)


def goes_ahora(lote_id: str, lat: float, lon: float, cliente: httpx.Client, leer, ahora: datetime,
               leer_vector=None) -> list[Observacion]:
    """Lo de 'tiempo real': infrarrojo, topes nubosos, rayos de los últimos minutos y la animación."""
    hoy = ahora.date()
    sat = satelite_goes(hoy)
    observaciones = []
    base = dict(lote_id=lote_id, fecha=hoy, fuente="GOES")
    # infrarrojo térmico (banda 14, 11,2 µm)
    try:
        url = _ultimo(cliente, "ABI-L2-CMIPF", ahora, "C14_")
        valor, dqf = leer(url, "CMI", lat, lon) if url else (None, None)
    except Exception:
        url, valor, dqf = None, None, None
    hora = re.search(r"_s(\d{4})(\d{3})(\d{2})(\d{2})", url or "")
    cuando = f" de las {int(hora.group(3)) - 3:02d}:{hora.group(4)} h" if hora else ""
    observaciones.append(Observacion(
        **base, variable="infrarrojo_termico_goes", unidad="°C", resolucion_m=2000,
        valor=None if valor is None else round(valor - 273.15, 1),
        calidad="descartada" if valor is None else CALIDAD_DQF.get(dqf, "dudosa"),
        nota=f"Temperatura de brillo del infrarrojo térmico (banda 14) de {sat} ABI-L2-CMIPF{cuando}: con cielo "
             f"despejado es la del suelo, con nubes la de la nube" if valor is not None
        else f"{sat} no entregó el infrarrojo térmico de las últimas horas"))
    # topes nubosos
    try:
        url = _ultimo(cliente, "ABI-L2-ACHTF", ahora)
        valor, dqf = leer(url, "TEMP", lat, lon) if url else (None, None)
    except Exception:
        valor, dqf = None, None
    observaciones.append(Observacion(
        **base, variable="temp_topes_nubosos", unidad="°C", resolucion_m=10000,
        valor=None if valor is None else round(valor - 273.15, 1),
        calidad="descartada" if valor is None else CALIDAD_DQF.get(dqf, "dudosa"),
        nota=f"Temperatura del tope de la nube sobre el lote, {sat} ABI-L2-ACHTF" if valor is not None
        else f"Sin nube sobre el lote en la última imagen de {sat} (o sin dato): no hay tope nuboso que medir"))
    # rayos de los últimos minutos
    try:
        urls = []
        for atras in (0, 1):
            urls += archivos_goes(cliente, "GLM-L2-LCFA", ahora - timedelta(hours=atras))
        corte = ahora - timedelta(minutes=MINUTOS_RAYOS)
        recientes = [u for u in urls if (m := re.search(r"_s(\d{13})", u))
                     and datetime.strptime(m.group(1)[:13], "%Y%j%H%M%S").replace(tzinfo=timezone.utc) >= corte]
        cantidad = contar_rayos(recientes, lat, lon, leer_vector) if recientes else None
    except Exception:
        recientes, cantidad = [], None
    area = math.pi * RADIO_RAYOS_KM ** 2
    observaciones.append(Observacion(
        **base, variable="rayos_tiempo_real", unidad="destellos/km²", resolucion_m=8000,
        valor=None if cantidad is None else round(cantidad / area, 4),
        calidad="descartada" if cantidad is None else "buena",
        nota=f"{cantidad} destellos a menos de {RADIO_RAYOS_KM} km del lote en los últimos {MINUTOS_RAYOS} minutos "
             f"({len(recientes)} archivos del GLM de {sat}, NOAA)" if cantidad is not None
        else "No se pudieron leer los rayos del GLM de los últimos minutos"))
    # animación del infrarrojo (multimedia: la URL va en la nota)
    animacion = (f"https://weather.ndc.nasa.gov/cgi-bin/get-abi?satellite=GOESEastfullDiskband14&lat={lat:.2f}"
                 f"&lon={lon:.2f}&zoom=2&type=Animation&numframes=10&width=800&height=800&mapcolor=white"
                 f"&quality=75&palette=ir2.pal")
    observaciones.append(Observacion(
        **base, variable="animacion_ir_goes", unidad="url", resolucion_m=2000, valor=None, calidad="descartada",
        nota=f"Animación del infrarrojo térmico de {sat} centrada en el lote (la misma que usa SEPA, de la NASA): "
             f"{animacion}"))
    return observaciones


# ---------- 6. todo junto ----------

def validar_pedido(desde: date, hasta: date) -> None:
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise ValueError(f"El rango supera {MAX_DIAS} días")


def centro(poligono: dict) -> tuple[float, float]:
    from shapely.geometry import shape
    c = shape(poligono).centroid
    return c.y, c.x


AVISO_CAIDO = "SEPA no responde"


def sepa_caido(cliente: httpx.Client) -> str:
    """Vacío si el sitio de SEPA contesta (con cualquier código); si no, el motivo. Tarda como mucho 20 s."""
    try:
        cliente.get(f"{SEPA}/productos/", timeout=20)
    except httpx.HTTPError as error:
        return type(error).__name__
    return ""


def obtener_sepa(lote_id: str, poligono: dict, desde: date, hasta: date,
                 cliente: httpx.Client | None = None) -> list[Observacion]:
    """Lo que publica SEPA para el lote (balance hídrico, anomalías, imágenes) y el Q de trigo."""
    validar_pedido(desde, hasta)
    cliente = cliente or httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": AGENTE})
    lat, lon = centro(poligono)
    caido = sepa_caido(cliente)
    if caido:  # no se esperan minutos de archivos que no van a llegar: se avisa y se sigue con el Q
        observaciones = [Observacion(lote_id=lote_id, fecha=hasta, variable=p.variable, valor=None, unidad=p.unidad,
                                     fuente="SEPA_INTA", resolucion_m=RESOLUCION_AGUA_M, calidad="descartada",
                                     nota=f"{AVISO_CAIDO} ({caido}): el servidor del INTA está caído o no se "
                                          "alcanza. El agua del suelo sale del balance propio con datos de la NASA")
                         for p in AGUA]
    else:
        observaciones = agua_del_lote(lote_id, poligono, desde, hasta)
        observaciones += anomalias_del_lote(lote_id, poligono, desde, hasta, cliente)
        observaciones += imagenes_del_lote(lote_id, desde, hasta, cliente)
    try:
        observaciones += q_trigo(lote_id, lat, lon, desde, min(hasta, date.today()), cliente)
    except (httpx.HTTPError, KeyError, ValueError) as error:
        observaciones.append(Observacion(
            lote_id=lote_id, fecha=hasta, variable="cociente_fototermal_trigo", valor=None, unidad="MJ/m²/día/°C",
            fuente="POWER", resolucion_m=55000, calidad="descartada",
            nota=f"NASA POWER no respondió para calcular el Q: {type(error).__name__}"))
    return observaciones


def obtener_goes(lote_id: str, poligono: dict, desde: date, hasta: date,
                 cliente: httpx.Client | None = None) -> list[Observacion]:
    validar_pedido(desde, hasta)
    cliente = cliente or httpx.Client(timeout=60, headers={"User-Agent": AGENTE})
    lat, lon = centro(poligono)
    return goes_del_lote(lote_id, lat, lon, desde, hasta, cliente)


# ---------- conexión con el núcleo (spec 009) ----------

class SEPACaido(RuntimeError):
    """El sitio de SEPA no contesta: la consulta pasa al balance propio, que trae el agua del suelo (spec 024)."""


def _pedir_sepa(lote: dict, desde: date, hasta: date) -> list[Observacion]:
    """Para POST /consulta. Si SEPA está caído no alcanza con el Q de trigo: sin el agua del suelo tiene que contestar
    el respaldo. El 16/10/2026, con SEPA caído, la consulta devolvía solo el Q y el agua quedaba vacía."""
    observaciones = obtener_sepa(lote["id"], lote["poligono"], desde, hasta)
    caido = next((o for o in observaciones if o.fuente == "SEPA_INTA" and o.nota.startswith(AVISO_CAIDO)), None)
    if caido:
        raise SEPACaido(caido.nota)
    return observaciones


SATELITES = [
    Satelite("SEPA_INTA", _pedir_sepa),
    Satelite("GOES", lambda lote, desde, hasta: obtener_goes(lote["id"], lote["poligono"], desde, hasta)),
]

router = APIRouter(tags=["SEPA INTA y GOES (pruebas internas)"])


class PedidoLote(BaseModel):
    lote_id: str
    poligono: dict
    desde: date
    hasta: date


def _responder(funcion, pedido: PedidoLote) -> list[Observacion]:
    try:
        validar_poligono(pedido.poligono)
        validar_pedido(pedido.desde, pedido.hasta)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    return funcion(pedido.lote_id, pedido.poligono, pedido.desde, pedido.hasta)


@router.post("/sepa", response_model=list[Observacion])
def sepa(pedido: PedidoLote) -> list[Observacion]:
    return _responder(obtener_sepa, pedido)


@router.post("/goes", response_model=list[Observacion])
def goes(pedido: PedidoLote) -> list[Observacion]:
    return _responder(obtener_goes, pedido)
