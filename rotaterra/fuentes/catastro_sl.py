"""Conector CATASTRO_SL: límites oficiales y datos de una parcela del Catastro de San Luis (spec 025).

Excepción a la regla de fuentes (decisión de Hernán, spec 025): la Dirección Provincial de Catastro y Tierras
Fiscales de San Luis es la fuente oficial de los límites de los lotes en la provincia.

Cómo funciona el visor público (relevado con ingeniería inversa, ver la spec):
1. `f?p=VISPUB:1` (Oracle APEX) redirige a una sesión nueva (`p_instance`) y trae, en el campo oculto
   `P1_CATGIS_VISUALIZADOR_URL`, la dirección del mapa con un TOKEN de un solo uso.
2. El mapa (Angular + OpenLayers) dibuja y consulta las capas de un GeoServer público en el mismo servidor,
   con WMS/WFS. Las parcelas están en las capas `SanLuis:GIS_PARCELAS_RUR_VV`, `_SUB_VV` y `_URB_VV`
   (EPSG:22183, Gauss-Krüger faja 3), y el GeoServer las reproyecta a EPSG:4326 si se le pide.
Este conector abre la sesión del visor para saber en qué servidor está el mapa (nunca usa un Session ID fijo)
y después consulta el WFS directamente.
"""

import asyncio
import gzip
import html
import json
import math
import re
import time
from datetime import date
from pathlib import Path
from typing import Literal, Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

VISOR = "http://www.sistemacatastro.sanluis.gov.ar/pls/apex/f?p=VISPUB:1"
SERVIDOR_CONOCIDO = "http://visualcatsl.dyndns.info"  # el que figuraba en el visor
CAPAS = {"RURAL": "SanLuis:GIS_PARCELAS_RUR_VV", "SUBURBANA": "SanLuis:GIS_PARCELAS_SUB_VV",
         "URBANA": "SanLuis:GIS_PARCELAS_URB_VV"}
MARGEN = 0.0005          # grados alrededor del punto para la caja de búsqueda (~50 m)
MAX_PARCELAS = 20
TOLERANCIA_SUPERFICIE = 0.05  # si la superficie medida difiere más de 5 % de la registrada → dudosa
DURACION_SESION = 3600   # segundos que se reutiliza el servidor leído del visor
TIEMPO_MAXIMO = 30
FUENTE = "Catastro San Luis"
RADIO_TIERRA = 6_371_008.8
CODIGO = re.compile(r"^[A-Za-z0-9-]{3,40}$")  # nomenclaturas y partidas: E5-03-01-00-000000-003565, 01-1064404

Calidad = Literal["buena", "dudosa", "descartada"]


class ErrorCatastro(Exception):
    """El Catastro de San Luis no respondió o respondió algo ilegible."""


class ParcelaCatastral(BaseModel):
    """Lo que el Catastro dice de una parcela. Si no hay parcela, todo queda en null y la nota explica por qué."""

    nomenclatura_catastral: Optional[str] = None   # cuadrante-depto-circunscripción-sección-manzana-parcela
    partida_inmobiliaria: Optional[str] = None     # "Nom. Tributaria" del visor (padrón de Rentas)
    numero_parcela: Optional[str] = None
    tipo_parcela: Optional[str] = None             # RURAL, SUBURBANA o URBANA
    plano_mensura: Optional[str] = None
    superficie_registrada_m2: Optional[float] = None  # la del Catastro (mensura)
    superficie_calculada_m2: Optional[float] = None   # medida sobre el polígono devuelto
    geometria_lote: Optional[dict] = None          # GeoJSON Polygon EPSG:4326, listo para recortar satélites
    geometria_parcela: Optional[dict] = None       # la geometría completa tal como viene (puede ser MultiPolygon)
    capa: Optional[str] = None
    fuente: str = FUENTE
    fecha_consulta: date
    calidad: Calidad
    nota: str = ""


# ---------- sesión del visor (Oracle APEX) ----------

_sesion: dict = {"servidor": None, "hasta": 0.0}


def _campo(pagina: str, marca: str) -> str | None:
    """Valor de un <input> del formulario APEX que tiene esa marca (name o id)."""
    etiqueta = re.search(rf"<input\b[^>]*{marca}[^>]*>", pagina)
    valor = re.search(r'\bvalue="([^"]*)"', etiqueta.group(0)) if etiqueta else None
    return html.unescape(valor.group(1)) if valor and valor.group(1) else None


async def abrir_sesion(cliente: httpx.AsyncClient) -> str:
    """Abre una sesión nueva del visor y devuelve el servidor del mapa (esquema + host).

    APEX asigna un `p_instance` nuevo en cada visita; acá se lo lee del formulario, nunca se usa uno fijo.
    """
    respuesta = await cliente.get(VISOR)
    respuesta.raise_for_status()
    instancia = _campo(respuesta.text, r'name="p_instance"')
    mapa = _campo(respuesta.text, r'id="P1_CATGIS_VISUALIZADOR_URL"')
    if not instancia or not mapa:
        raise ErrorCatastro("El visor del Catastro cambió: no trae la sesión APEX ni la dirección del mapa")
    url = urlparse(mapa)
    if not url.scheme or not url.netloc:
        raise ErrorCatastro(f"Dirección del mapa ilegible: {mapa[:120]!r}")
    return f"{url.scheme}://{url.netloc}"


async def servidor_del_mapa(cliente: httpx.AsyncClient) -> tuple[str, str]:
    """(servidor, cómo se obtuvo). Si el visor no responde se usa el servidor conocido y se lo aclara."""
    if _sesion["servidor"] and time.monotonic() < _sesion["hasta"]:
        return _sesion["servidor"], "servidor leído del visor público en esta sesión"
    try:
        servidor = await abrir_sesion(cliente)
    except (httpx.HTTPError, ErrorCatastro) as error:
        return SERVIDOR_CONOCIDO, (f"el visor APEX no respondió ({type(error).__name__}); se usó el servidor "
                                   f"conocido {SERVIDOR_CONOCIDO}")
    _sesion.update(servidor=servidor, hasta=time.monotonic() + DURACION_SESION)
    return servidor, "servidor leído del visor público (sesión APEX nueva)"


# ---------- lectura del WFS ----------

async def consultar(cliente: httpx.AsyncClient, servidor: str, capa: str, **filtro) -> list[dict]:
    """Parcelas de una capa en EPSG:4326 (GeoJSON features). filtro: bbox=... o CQL_FILTER=..."""
    respuesta = await cliente.get(f"{servidor}/geoserver/wfs", params={
        "service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": capa,
        "outputFormat": "application/json", "srsName": "EPSG:4326", "maxFeatures": MAX_PARCELAS, **filtro})
    respuesta.raise_for_status()
    if "json" not in respuesta.headers.get("content-type", ""):
        raise ErrorCatastro(f"El Catastro no devolvió JSON para {capa}: {respuesta.text[:200]!r}")
    return respuesta.json().get("features", [])


async def en_todas_las_capas(cliente: httpx.AsyncClient, servidor: str, **filtro) -> list[tuple[str, dict]]:
    resultados = await asyncio.gather(*(consultar(cliente, servidor, capa, **filtro) for capa in CAPAS.values()))
    return [(capa, f) for capa, features in zip(CAPAS.values(), resultados) for f in features]


# ---------- de la respuesta del Catastro a ParcelaCatastral ----------

def leer_ficha(texto: str | None) -> dict[str, str]:
    """El campo NOMBRE trae la ficha del visor: ' Parcela: 3565 \\n Nom.Catastral: ... \\n Sup. Terreno: 5278958.35 m2'."""
    ficha = {}
    for renglon in re.split(r"\\n|\n", texto or ""):
        if ":" in renglon:
            clave, valor = renglon.split(":", 1)
            ficha[clave.strip().lower()] = valor.strip()
    return ficha


def _numero(texto: str | None) -> float | None:
    m = re.search(r"[\d.]+", texto or "")
    try:
        return float(m.group(0)) if m else None
    except ValueError:
        return None


def superficie_m2(geometria: dict) -> float:
    """Superficie en m² de un GeoJSON en grados, proyectado en el plano tangente al centro (error < 0,1 % en un lote)."""
    from shapely.geometry import shape
    from shapely.ops import transform

    figura = shape(geometria)
    lat0 = math.radians(figura.centroid.y)
    plano = transform(lambda lon, lat: (RADIO_TIERRA * math.radians(lon) * math.cos(lat0),
                                        RADIO_TIERRA * math.radians(lat)), figura)
    return plano.area


def _listas(coordenadas):
    if coordenadas and isinstance(coordenadas[0], (int, float)):
        return list(coordenadas)
    return [_listas(c) for c in coordenadas]


def reparar(geometria: dict) -> tuple[dict | None, bool]:
    """(geometría, se reparó). Si el polígono del Catastro se cruza a sí mismo se repara con make_valid y quedan
    solo las partes con superficie; así pasa validar_poligono y se puede usar para recortar satélites."""
    from shapely.geometry import MultiPolygon, mapping, shape
    from shapely.validation import make_valid

    figura = shape(geometria)
    if figura.is_valid:
        return geometria, False
    arreglada, partes = make_valid(figura), []
    for parte in getattr(arreglada, "geoms", [arreglada]):
        if parte.geom_type == "Polygon" and parte.area > 0:
            partes.append(parte)
        elif parte.geom_type == "MultiPolygon":
            partes.extend(p for p in parte.geoms if p.area > 0)
    if not partes:
        return None, True
    figura = partes[0] if len(partes) == 1 else MultiPolygon(partes)
    arreglada = mapping(figura)
    return {"type": arreglada["type"], "coordinates": _listas(arreglada["coordinates"])}, True


def poligono_para_recortar(geometria: dict) -> tuple[dict, int]:
    """(Polygon, cantidad de partes). Un MultiPolygon de una parte se pasa a Polygon; si tiene varias, la mayor."""
    from shapely.geometry import mapping, shape

    figura = shape(geometria)
    partes = list(getattr(figura, "geoms", [figura]))
    mayor = max(partes, key=lambda p: p.area)
    poligono = mapping(mayor)
    return {"type": "Polygon", "coordinates": [[list(p) for p in anillo] for anillo in poligono["coordinates"]]}, \
        len(partes)


def armar(capa: str, feature: dict, como: str, extra: str = "") -> ParcelaCatastral:
    p = feature.get("properties") or {}
    ficha = leer_ficha(p.get("NOMBRE"))
    geometria = feature.get("geometry")
    tipo_por_capa = next((t for t, c in CAPAS.items() if c == capa), None)
    notas = [f"Catastro de San Luis, capa {capa} ({como})."]
    calidad: Calidad = "buena"

    registrada = _numero(ficha.get("sup. terreno"))
    calculada = lote = None
    if geometria and geometria.get("coordinates"):
        geometria, reparada = reparar(geometria)
        if reparada:
            calidad = "dudosa"
            notas.append("El polígono del Catastro se cruza a sí mismo: se reparó (make_valid) para poder usarlo "
                         "como lote; conviene que el productor confirme el límite.")
    if geometria and geometria.get("coordinates"):
        calculada = round(superficie_m2(geometria), 1)
        lote, partes = poligono_para_recortar(geometria)
        if partes > 1:
            calidad = "dudosa"
            notas.append(f"La parcela tiene {partes} partes separadas; geometria_lote es la mayor.")
    else:
        calidad = "dudosa"
        notas.append("El Catastro no devolvió el polígono de la parcela.")
    if registrada is None:
        notas.append("El Catastro no publica la superficie de mensura de esta parcela.")
    elif calculada is not None:
        diferencia = abs(calculada - registrada) / registrada if registrada else 1
        notas.append(f"Superficie registrada {registrada / 10_000:.2f} ha, medida sobre el polígono "
                     f"{calculada / 10_000:.2f} ha ({diferencia:.1%} de diferencia).")
        if diferencia > TOLERANCIA_SUPERFICIE:
            calidad = "dudosa"
            notas.append(f"SUPUESTO: más de {TOLERANCIA_SUPERFICIE:.0%} de diferencia se marca dudosa "
                         "(polígono digitalizado distinto de la mensura).")
    if extra:
        notas.append(extra)

    return ParcelaCatastral(
        nomenclatura_catastral=p.get("CATNMC_CAT") or ficha.get("nom.catastral"),
        partida_inmobiliaria=p.get("CATNMC_TRI") or ficha.get("nom.tributaria"),
        numero_parcela=p.get("ETIQUETA") or ficha.get("parcela"),
        tipo_parcela=(ficha.get("tipo parcela") or tipo_por_capa or "").upper() or None,
        plano_mensura=p.get("CATMEN_CODIGO") or ficha.get("plano mensura"),
        superficie_registrada_m2=registrada, superficie_calculada_m2=calculada,
        geometria_lote=lote, geometria_parcela=geometria, capa=capa,
        fecha_consulta=date.today(), calidad=calidad, nota=" ".join(notas))


def sin_parcela(motivo: str) -> ParcelaCatastral:
    return ParcelaCatastral(fecha_consulta=date.today(), calidad="descartada", nota=motivo)


# ---------- búsquedas ----------

def _cliente() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=TIEMPO_MAXIMO, follow_redirects=True,
                             headers={"User-Agent": "Rotaterra/0.1 (+https://github.com/hernanfirmapaz-ops/N4-4-1.2)"})


async def parcela_en_punto(lat: float, lon: float, cliente: httpx.AsyncClient | None = None) -> ParcelaCatastral:
    """La parcela que contiene el punto (lat, lon en grados, EPSG:4326)."""
    from shapely.geometry import Point, shape

    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Coordenadas fuera de rango: usá grados decimales (EPSG:4326)")
    propio = cliente is None
    cliente = cliente or _cliente()
    try:
        servidor, como = await servidor_del_mapa(cliente)
        caja = f"{lon - MARGEN},{lat - MARGEN},{lon + MARGEN},{lat + MARGEN},EPSG:4326"
        candidatas = await en_todas_las_capas(cliente, servidor, bbox=caja)
    except httpx.HTTPError as error:
        raise ErrorCatastro(f"El Catastro de San Luis no respondió: {type(error).__name__}: {error}") from error
    finally:
        if propio:
            await cliente.aclose()

    punto = Point(lon, lat)
    contienen = [(capa, f) for capa, f in candidatas
                 if f.get("geometry") and shape(f["geometry"]).buffer(1e-9).contains(punto)]
    if not contienen:
        cerca = f" Hay {len(candidatas)} parcelas a menos de ~50 m." if candidatas else ""
        return sin_parcela(f"El punto ({lat}, {lon}) no cae dentro de ninguna parcela publicada por el Catastro de "
                           f"San Luis (puede ser un camino, una ruta, un curso de agua, una parcela sin datos "
                           f"públicos o un punto fuera de la provincia).{cerca}")
    contienen.sort(key=lambda cf: shape(cf[1]["geometry"]).area)  # si se superponen, la más chica (la más precisa)
    extra = ""
    if len(contienen) > 1:
        otras = ", ".join((f.get("properties") or {}).get("CATNMC_CAT") or "?" for _, f in contienen[1:])
        extra = f"El punto cae también en {otras} (superposición en el Catastro); se eligió la parcela más chica."
    parcela = armar(*contienen[0], como=como, extra=extra)
    if len(contienen) > 1:
        parcela.calidad = "dudosa"
    return parcela


async def parcela_por_codigo(campo: Literal["CATNMC_CAT", "CATNMC_TRI"], codigo: str,
                             cliente: httpx.AsyncClient | None = None) -> ParcelaCatastral:
    codigo = codigo.strip().upper()
    if not CODIGO.match(codigo):
        raise ValueError("Código inválido: solo letras, números y guiones (ej. E5-03-01-00-000000-003565)")
    nombre = "nomenclatura catastral" if campo == "CATNMC_CAT" else "partida inmobiliaria"
    propio = cliente is None
    cliente = cliente or _cliente()
    try:
        servidor, como = await servidor_del_mapa(cliente)
        encontradas = await en_todas_las_capas(cliente, servidor, CQL_FILTER=f"{campo}='{codigo}'")
    except httpx.HTTPError as error:
        raise ErrorCatastro(f"El Catastro de San Luis no respondió: {type(error).__name__}: {error}") from error
    finally:
        if propio:
            await cliente.aclose()
    if not encontradas:
        return sin_parcela(f"El Catastro de San Luis no tiene ninguna parcela publicada con {nombre} {codigo}.")
    extra = ""
    if len(encontradas) > 1:
        extra = f"Hay {len(encontradas)} parcelas con esa {nombre}; se devuelve la primera."
    parcela = armar(*encontradas[0], como=como, extra=extra)
    if len(encontradas) > 1:
        parcela.calidad = "dudosa"
    return parcela


def parcela_por_nomenclatura(nomenclatura: str, cliente: httpx.AsyncClient | None = None):
    return parcela_por_codigo("CATNMC_CAT", nomenclatura, cliente)


def parcela_por_partida(partida: str, cliente: httpx.AsyncClient | None = None):
    return parcela_por_codigo("CATNMC_TRI", partida, cliente)


# ---------- mapa de parcelas rurales (para dibujarlas todas en el frontend) ----------

CAMPOS_MAPA = "GEOM,ETIQUETA,NOMBRE,CATNMC_TRI,CATNMC_CAT,CATMEN_CODIGO"
MAX_EN_ZONA = 5000         # parcelas por pedido con caja; más que eso pide acercar el mapa
DURACION_MAPA = 24 * 3600  # el mapa completo se guarda en memoria un día (no hay base de datos)
TIEMPO_MAPA = 180
ESPERA_REINTENTO = 5       # segundos antes de reintentar si el Catastro rechaza el pedido
DECIMALES = 6              # ~0,1 m: alcanza para dibujar y achica el archivo

_mapa: dict = {"gz": None, "cantidad": 0, "hasta": 0.0}
_candado = asyncio.Lock()


def _redondear(coordenadas):
    if coordenadas and isinstance(coordenadas[0], (int, float)):
        return [round(c, DECIMALES) for c in coordenadas]
    return [_redondear(c) for c in coordenadas]


def parcela_del_mapa(feature: dict) -> dict:
    """Feature liviano: polígono EPSG:4326 y los datos que el frontend muestra al tocar una parcela."""
    p = feature.get("properties") or {}
    ficha = leer_ficha(p.get("NOMBRE"))
    geometria = feature.get("geometry")
    reparada = False
    if geometria and geometria.get("coordinates"):
        geometria = {"type": geometria["type"], "coordinates": _redondear(geometria["coordinates"])}
        geometria, reparada = reparar(geometria)
    return {"type": "Feature", "id": p.get("CATNMC_CAT") or feature.get("id"), "geometry": geometria,
            "properties": {"nomenclatura_catastral": p.get("CATNMC_CAT") or ficha.get("nom.catastral"),
                           "partida_inmobiliaria": p.get("CATNMC_TRI") or ficha.get("nom.tributaria"),
                           "numero_parcela": p.get("ETIQUETA") or ficha.get("parcela"),
                           "tipo_parcela": (ficha.get("tipo parcela") or "RURAL").upper(),
                           "plano_mensura": p.get("CATMEN_CODIGO") or ficha.get("plano mensura"),
                           "superficie_registrada_m2": _numero(ficha.get("sup. terreno")),
                           "geometria_reparada": reparada}}


def coleccion(features: list[dict], nota: str, truncado: bool = False) -> dict:
    livianos = [parcela_del_mapa(f) for f in features]
    reparadas = sum(f["properties"]["geometria_reparada"] for f in livianos)
    if reparadas:
        nota += (f" {reparadas} parcela(s) venían con el polígono cruzado sobre sí mismo y se repararon "
                 "(geometria_reparada: true).")
    return {"type": "FeatureCollection", "fuente": FUENTE, "fecha_consulta": date.today().isoformat(),
            "crs": "EPSG:4326", "cantidad": len(livianos), "truncado": truncado, "nota": nota,
            "features": livianos}


async def parcelas_rurales(caja: tuple[float, float, float, float] | None = None,
                           cliente: httpx.AsyncClient | None = None) -> dict:
    """GeoJSON FeatureCollection con las parcelas rurales: todas, o solo las que tocan la caja (oeste, sur, este, norte)."""
    params = {"service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": CAPAS["RURAL"],
              "outputFormat": "application/json", "srsName": "EPSG:4326", "propertyName": CAMPOS_MAPA}
    if caja is not None:
        oeste, sur, este, norte = caja
        if not (-180 <= oeste < este <= 180 and -90 <= sur < norte <= 90):
            raise ValueError("Caja inválida: tiene que ser oeste < este y sur < norte, en grados (EPSG:4326)")
        params.update(bbox=f"{oeste},{sur},{este},{norte},EPSG:4326", maxFeatures=MAX_EN_ZONA + 1)
    propio = cliente is None
    cliente = cliente or httpx.AsyncClient(timeout=TIEMPO_MAPA, follow_redirects=True,
                                           headers={"User-Agent": "Rotaterra/0.1"})
    try:
        servidor, como = await servidor_del_mapa(cliente)
        respuesta = await cliente.get(f"{servidor}/geoserver/wfs", params=params)
        if respuesta.status_code == 403 or respuesta.status_code >= 500:
            # el Catastro respondió una vez 403 y al rato lo mismo dio 200: se reintenta una vez
            await asyncio.sleep(ESPERA_REINTENTO)
            respuesta = await cliente.get(f"{servidor}/geoserver/wfs", params=params)
        respuesta.raise_for_status()
        if "json" not in respuesta.headers.get("content-type", ""):
            raise ErrorCatastro(f"El Catastro no devolvió JSON: {respuesta.text[:200]!r}")
        features = respuesta.json().get("features", [])
    except httpx.HTTPError as error:
        raise ErrorCatastro(f"El Catastro de San Luis no respondió: {type(error).__name__}: {error}") from error
    finally:
        if propio:
            await cliente.aclose()
    truncado = caja is not None and len(features) > MAX_EN_ZONA
    nota = f"Parcelas rurales del Catastro de San Luis, capa {CAPAS['RURAL']} ({como})."
    if truncado:
        features = features[:MAX_EN_ZONA]
        nota += f" Hay más de {MAX_EN_ZONA} parcelas en la zona: se devuelven {MAX_EN_ZONA}; acercá el mapa."
    if not features:
        nota += " No hay parcelas rurales publicadas en esa zona."
    return coleccion(features, nota, truncado)


async def mapa_completo_gz() -> tuple[bytes, int]:
    """Todas las parcelas rurales como GeoJSON comprimido (gzip), guardado en memoria un día."""
    async with _candado:
        if _mapa["gz"] is None or time.monotonic() >= _mapa["hasta"]:
            datos = await parcelas_rurales()
            _mapa.update(gz=gzip.compress(json.dumps(datos, ensure_ascii=False, separators=(",", ":")).encode(), 6),
                         cantidad=datos["cantidad"], hasta=time.monotonic() + DURACION_MAPA)
        return _mapa["gz"], _mapa["cantidad"]


# ---------- copia del mapa de parcelas rurales, para cuando el Catastro no contesta (spec 045) ----------
# El 15/10/2026, de 23:53 a 23:56 de Argentina, el Catastro no contestó y la prueba del piloto se cortó.

DATOS = Path(__file__).with_name("datos")
COPIA = DATOS / "catastro_sl_parcelas_rurales.geojson.gz"
COPIA_INFO = DATOS / "catastro_sl_parcelas_rurales.json"


def info_de_la_copia() -> dict:
    """{"fecha": "AAAA-MM-DD", "cantidad": N}, sin abrir el mapa."""
    return json.loads(COPIA_INFO.read_text(encoding="utf-8"))


def leer_copia() -> dict:
    """El mapa completo de la copia. No se guarda en memoria: se lee solo cuando el Catastro está caído."""
    return json.loads(gzip.decompress(COPIA.read_bytes()))


def _aviso_copia(error: Exception, fecha: str) -> str:
    return (f"{str(error)[:200]} · Se usó la copia del mapa de parcelas rurales guardada en el repo el {fecha} "
            f"(spec 045).")


def _a_feature_del_wfs(liviano: dict) -> dict:
    """De vuelta al formato del WFS, para que armar() mida y califique la parcela igual que con el Catastro."""
    p = liviano["properties"]
    ficha = f"Tipo Parcela: {p.get('tipo_parcela') or 'RURAL'}"
    if p.get("superficie_registrada_m2") is not None:
        ficha += f"\nSup. Terreno: {p['superficie_registrada_m2']} m2"
    return {"type": "Feature", "geometry": liviano.get("geometry"),
            "properties": {"CATNMC_CAT": p.get("nomenclatura_catastral"), "CATNMC_TRI": p.get("partida_inmobiliaria"),
                           "ETIQUETA": p.get("numero_parcela"), "CATMEN_CODIGO": p.get("plano_mensura"),
                           "NOMBRE": ficha}}


def _caja_de(geometria: dict) -> tuple[float, float, float, float]:
    xs, ys = [], []

    def recorrer(c):
        if c and isinstance(c[0], (int, float)):
            xs.append(c[0])
            ys.append(c[1])
        else:
            for x in c:
                recorrer(x)
    recorrer(geometria["coordinates"])
    return min(xs), min(ys), max(xs), max(ys)


def _parcela_de_la_copia(encontradas: list[dict], error: Exception, info: dict, extra: str = "") -> ParcelaCatastral:
    elegida = encontradas[0]
    reparada = elegida["properties"].get("geometria_reparada")
    if reparada:
        extra = ("El polígono del Catastro se cruzaba a sí mismo y la copia lo guarda reparado (make_valid); conviene "
                 "que el productor confirme el límite. " + extra).strip()
    parcela = armar(CAPAS["RURAL"], _a_feature_del_wfs(elegida), como=f"copia del {info['fecha']}", extra=extra)
    parcela.nota = f"{_aviso_copia(error, info['fecha'])} {parcela.nota}"
    parcela.fecha_consulta = date.fromisoformat(info["fecha"])
    if reparada or len(encontradas) > 1:
        parcela.calidad = "dudosa"
    return parcela


def parcela_en_punto_de_la_copia(lat: float, lon: float, error: Exception) -> ParcelaCatastral:
    from shapely.geometry import Point, shape

    info, mapa = info_de_la_copia(), leer_copia()
    punto = Point(lon, lat)
    cerca = [f for f in mapa["features"] if f.get("geometry")
             and (c := _caja_de(f["geometry"]))[0] <= lon <= c[2] and c[1] <= lat <= c[3]]
    contienen = sorted((f for f in cerca if shape(f["geometry"]).buffer(1e-9).contains(punto)),
                       key=lambda f: shape(f["geometry"]).area)
    if not contienen:
        raise ErrorCatastro(f"{error} · Tampoco está en la copia del {info['fecha']}, que solo tiene parcelas "
                            f"rurales: el punto ({lat}, {lon}) no cae en ninguna.")
    extra = ""
    if len(contienen) > 1:
        otras = ", ".join(f["properties"].get("nomenclatura_catastral") or "?" for f in contienen[1:])
        extra = f"El punto cae también en {otras} (superposición en el Catastro); se eligió la parcela más chica."
    return _parcela_de_la_copia(contienen, error, info, extra)


def parcela_por_codigo_de_la_copia(campo: Literal["CATNMC_CAT", "CATNMC_TRI"], codigo: str,
                                   error: Exception) -> ParcelaCatastral:
    propiedad = "nomenclatura_catastral" if campo == "CATNMC_CAT" else "partida_inmobiliaria"
    nombre = "nomenclatura catastral" if campo == "CATNMC_CAT" else "partida inmobiliaria"
    info, mapa = info_de_la_copia(), leer_copia()
    encontradas = [f for f in mapa["features"] if (f["properties"].get(propiedad) or "").upper() == codigo]
    if not encontradas:
        raise ErrorCatastro(f"{error} · Tampoco está en la copia del {info['fecha']}, que solo tiene parcelas "
                            f"rurales: no hay ninguna con {nombre} {codigo}.")
    extra = f"Hay {len(encontradas)} parcelas con esa {nombre}; se devuelve la primera." if len(encontradas) > 1 else ""
    return _parcela_de_la_copia(encontradas, error, info, extra)


def zona_de_la_copia(caja: tuple[float, float, float, float], error: Exception) -> dict:
    from shapely.geometry import box, shape

    info, mapa = info_de_la_copia(), leer_copia()
    oeste, sur, este, norte = caja
    zona = box(*caja)
    features = [f for f in mapa["features"] if f.get("geometry")
                and (c := _caja_de(f["geometry"]))[0] <= este and c[2] >= oeste and c[1] <= norte and c[3] >= sur
                and shape(f["geometry"]).intersects(zona)]
    truncado = len(features) > MAX_EN_ZONA
    nota = _aviso_copia(error, info["fecha"])
    if truncado:
        features = features[:MAX_EN_ZONA]
        nota += f" Hay más de {MAX_EN_ZONA} parcelas en la zona: se devuelven {MAX_EN_ZONA}; acercá el mapa."
    if not features:
        nota += " No hay parcelas rurales en esa zona de la copia."
    return {"type": "FeatureCollection", "fuente": FUENTE, "fecha_consulta": info["fecha"], "crs": "EPSG:4326",
            "cantidad": len(features), "truncado": truncado, "nota": nota, "features": features}


# ---------- API ----------
# No es un satélite: no entrega una serie de Observacion sino los datos fijos del lote. Por eso no se anota en
# SATELITES (la actualización nocturna no lo pide) y solo trae su endpoint.

SATELITES = []

router = APIRouter(tags=["Catastro San Luis"])


@router.get("/catastro-sl/parcela", response_model=ParcelaCatastral)
async def consultar_parcela(response: Response, lat: float | None = None, lon: float | None = None,
                            nomenclatura: str | None = None, partida: str | None = None) -> ParcelaCatastral:
    """Parcela oficial del Catastro de San Luis por punto (lat y lon), por nomenclatura catastral o por partida.

    Si el Catastro no contesta, una parcela rural sale de la copia del mapa guardada en el repo (spec 045): la nota
    lo aclara y la cabecera X-Copia-Del-Catastro trae la fecha de la copia."""
    try:
        try:
            if lat is not None and lon is not None:
                return await parcela_en_punto(lat, lon)
            if nomenclatura:
                return await parcela_por_nomenclatura(nomenclatura)
            if partida:
                return await parcela_por_partida(partida)
        except ErrorCatastro as error:
            if lat is not None and lon is not None:
                parcela = await asyncio.to_thread(parcela_en_punto_de_la_copia, lat, lon, error)
            else:
                campo, codigo = ("CATNMC_CAT", nomenclatura) if nomenclatura else ("CATNMC_TRI", partida)
                parcela = await asyncio.to_thread(parcela_por_codigo_de_la_copia, campo, codigo.strip().upper(), error)
            response.headers["X-Copia-Del-Catastro"] = parcela.fecha_consulta.isoformat()
            return parcela
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    except ErrorCatastro as error:
        raise HTTPException(status_code=502, detail=str(error))
    raise HTTPException(status_code=422, detail="Indicá lat y lon, o nomenclatura, o partida")


@router.get("/catastro-sl/parcelas-rurales")
async def mapa_parcelas_rurales(request: Request, oeste: float | None = None, sur: float | None = None,
                                este: float | None = None, norte: float | None = None):
    """Parcelas rurales de San Luis en GeoJSON (EPSG:4326) para dibujarlas en un mapa.

    Sin parámetros: todas (~18.000, unos 5 MB comprimidos; la primera vez tarda unos segundos y después queda
    guardado un día). Con oeste, sur, este y norte: solo las de esa zona del mapa (hasta 5000). Si el Catastro no
    contesta, salen de la copia guardada en el repo (spec 045), con la cabecera X-Copia-Del-Catastro.
    """
    caja = (oeste, sur, este, norte)
    cabeceras = {}
    try:
        if all(v is not None for v in caja):
            try:
                return await parcelas_rurales(caja)
            except ErrorCatastro as error:
                datos = await asyncio.to_thread(zona_de_la_copia, caja, error)
                return JSONResponse(datos, headers={"X-Copia-Del-Catastro": datos["fecha_consulta"]})
        if any(v is not None for v in caja):
            raise ValueError("Para pedir una zona hacen falta los cuatro: oeste, sur, este y norte")
        try:
            gz, cantidad = await mapa_completo_gz()
            cabeceras["Cache-Control"] = "public, max-age=86400"
        except ErrorCatastro:
            info = info_de_la_copia()
            gz, cantidad = await asyncio.to_thread(COPIA.read_bytes), info["cantidad"]
            cabeceras.update({"Cache-Control": "no-store", "X-Copia-Del-Catastro": info["fecha"]})
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    cabeceras.update({"X-Cantidad-Parcelas": str(cantidad),
                      "Content-Disposition": 'inline; filename="parcelas-rurales-san-luis.geojson"'})
    if "gzip" in request.headers.get("accept-encoding", ""):
        return Response(gz, media_type="application/geo+json", headers={**cabeceras, "Content-Encoding": "gzip"})
    return Response(gzip.decompress(gz), media_type="application/geo+json", headers=cabeceras)
