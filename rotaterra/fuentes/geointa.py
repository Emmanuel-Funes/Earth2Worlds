"""Conector GeoINTA: suelo e historia de cultivos del lote desde los geoservicios del INTA (specs 020 y 021).

Excepción prevista a la regla NASA (Guía técnica): el suelo lo releva el INTA, no un satélite.
Las cartas de suelo se consultan por WFS sin bajar geometrías (algunas unidades, como las áreas urbanas de
Buenos Aires, son enormes): primero qué unidades tocan el lote y después en qué unidad cae cada punto de una
grilla dentro del lote. La unidad dominante es la que tiene más puntos.
El Mapa Nacional de Cultivos se recorta por WCS al lote y se cuentan sus píxeles de 30 m (spec 021).
La textura y el pH se leen por WMS en una grilla de puntos, porque el INTA no los publica por WCS ni WFS
(spec 021, decisión de Hernán).
El carbono orgánico del suelo 2023 se recorta por WCS al lote y se promedian sus píxeles de 250 m (spec 021, §23.6).
"""

import hashlib
import json
import re
import threading
import time
import unicodedata
from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import date

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rotaterra.contrato import Observacion
from rotaterra.fuentes.registro import Satelite
from rotaterra.geo import validar_poligono

URL_WFS = "https://geo-backend.inta.gob.ar/geoserver/ows"
# geoservicios publicados en https://geo.inta.gob.ar/geoservicios/ (anexo de la spec 021)
URL_WCS = "https://geo-backend.inta.gob.ar/geoserver/wcs"
URL_WMS = "https://geo-backend.inta.gob.ar/geoserver/wms"
URL_WFS_NODO15 = "https://geo-nodo15.inta.gob.ar/geoserver/wfs"  # región La Pampa - San Luis
URL_WMS_NODO05 = "https://geo-nodo05.inta.gob.ar/geoserver/wms"  # textura y pH: solo los publica por WMS
MAX_UNIDADES = 50
GRILLA = 5              # puntos de muestreo: grilla de 5 × 5 sobre el lote (los que caen dentro)
UMBRAL_DOMINANTE = 0.5  # la unidad dominante tiene que cubrir al menos la mitad del lote; si no → dudosa
HILOS = 5


class Carta(BaseModel):
    capa: str
    nombre: str
    escala: int
    fecha: date  # fecha de la versión digital publicada por el INTA
    campos: list[str]  # atributos que se piden (nunca la geometría)
    geometria: str = "the_geom"
    url: str = URL_WFS
    nodo: str = "Nacional"
    caja: tuple[float, float, float, float] | None = None  # oeste, sur, este, norte (extensión publicada)

    @property
    def origen(self) -> str:
        escala = f"{self.escala:,}".replace(",", ".")
        return (f"{self.nombre}, escala 1:{escala} (versión digital del {self.fecha:%d/%m/%Y}) · "
                f"WFS del nodo {self.nodo}, capa {self.capa}")

    def toca(self, oeste: float, sur: float, este: float, norte: float) -> bool:
        if self.caja is None:
            return True
        return not (este < self.caja[0] or oeste > self.caja[2] or norte < self.caja[1] or sur > self.caja[3])

    @property
    def resolucion_m(self) -> int:
        # SUPUESTO: 0,5 mm del mapa a esa escala (lo más fino que se puede leer en la carta)
        return round(self.escala * 0.0005)


ATLAS = Carta(capa="geonode:suelos_argentina_1_500", nombre="Atlas de Suelos de la República Argentina (INTA) v9",
              escala=500_000, fecha=date(2013, 1, 7),
              campos=["provincia", "simbc", "tipo_uc", "ind_prod", "limit_ppal", "limit_secu", "limit_terc",
                      "text_sups1", "text_bs1", "drenaje_s1"]
              + [f"{c}{i}" for i in (1, 2, 3) for c in ("porc_sue", "posi_sue", "sgrup_sue")])
BUENOS_AIRES = Carta(capa="geonode:Suelos_BA_50mil_V2", nombre="Cartas de Suelo de Buenos Aires (INTA) v2",
                     escala=50_000, fecha=date(2023, 4, 17),
                     campos=["SIMBC", "Nombre_UC", "TIPO", "PAISAJE", "CAP_USO", "taxo_ppal"]
                     + [f"{c}{i}" for i in range(1, 7) for c in ("SERIE", "PORC", "FASE")])


def _hoja(capa: str, nombre: str, fecha: date, caja: tuple, escala: int = 100_000) -> Carta:
    return Carta(capa=capa, nombre=f"Carta de suelos {nombre}, San Luis (INTA)", escala=escala, fecha=fecha,
                 campos=["uc", "cap_uso", "ip"], geometria="geometry", url=URL_WFS_NODO15,
                 nodo="15 (La Pampa - San Luis)", caja=caja)


# hojas de suelo de San Luis publicadas por el nodo 15 (inventario de la spec 021, sección 22).
# La fecha es la de alta de la versión digital en el catálogo de GeoINTA; la caja, su extensión publicada.
HOJAS_SAN_LUIS = [
    _hoja("geonode:villamercedes_v0", "Villa Mercedes", date(2025, 9, 22), (-66.001, -34.0, -65.002, -32.999)),
    _hoja("geonode:sanluis_v1", "San Luis", date(2025, 9, 22), (-67.198, -34.0, -66.001, -32.999)),
    _hoja("geonode:buenaesperanza_v0", "Buena Esperanza", date(2025, 9, 22), (-66.001, -35.0, -65.105, -33.999)),
    _hoja("geonode:villagralroca_v0", "Villa General Roca", date(2025, 9, 22), (-67.347, -33.0, -66.001, -31.834),
          escala=200_000),
    _hoja("geonode:concaran_v0_676e7dd96118736d2ea36e767bd7c7fd", "Concarán", date(2025, 9, 19),
          (-66.001, -33.0, -64.871, -31.888)),
    _hoja("geonode:loyola_varela_v0_017028c132f4111b991dff14de997fd8", "Martín de Loyola y Varela",
          date(2025, 9, 19), (-66.813, -36.0, -66.001, -33.999)),
    _hoja("geonode:arizona_v0_02d647e0a3661237e9442c9ce388df2d", "Arizona", date(2025, 9, 19),
          (-66.001, -36.0, -65.105, -35.0)),
]

ROMANOS = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8}
SUBCLASES = {"e": "erosión", "w": "exceso de agua", "s": "limitaciones del suelo", "c": "clima"}


class ErrorGeoINTA(Exception):
    """El servidor del INTA no respondió o respondió algo ilegible."""


# ---------- lectura del WFS ----------

def _wkt(geometria) -> str:
    from shapely import wkt

    return wkt.dumps(geometria, rounding_precision=6)


def consultar(cliente: httpx.Client, carta: Carta, filtro: str, propiedades: list[str],
              maximo: int = MAX_UNIDADES) -> dict[str, dict]:
    """Unidades de la carta que cumplen el filtro CQL: id → atributos. Sin geometría (respuesta liviana)."""
    respuesta = cliente.get(carta.url, params={
        "service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": carta.capa,
        "outputFormat": "application/json", "maxFeatures": maximo, "propertyName": ",".join(propiedades),
        "CQL_FILTER": filtro})
    respuesta.raise_for_status()
    if "json" not in respuesta.headers.get("content-type", ""):
        raise ErrorGeoINTA(f"GeoINTA no devolvió JSON para {carta.capa}: {respuesta.text[:200]!r}")
    return {str(f.get("id")): f.get("properties") or {} for f in respuesta.json().get("features", [])}


def puntos_de_muestreo(poligono: dict, lado: int = GRILLA) -> list[tuple[float, float]]:
    """Centros de una grilla lado × lado sobre la caja del lote que caen dentro del polígono (lon, lat)."""
    from shapely.geometry import Point, shape

    lote = shape(poligono)
    oeste, sur, este, norte = lote.bounds
    puntos = [(oeste + (este - oeste) * (i + 0.5) / lado, sur + (norte - sur) * (j + 0.5) / lado)
              for i in range(lado) for j in range(lado)]
    dentro = [p for p in puntos if lote.contains(Point(p))]
    if not dentro:  # lote angosto o con forma rara: al menos un punto seguro adentro
        punto = lote.representative_point()
        dentro = [(punto.x, punto.y)]
    return dentro


def unidades_en_el_lote(cliente: httpx.Client, carta: Carta, poligono: dict) -> list[tuple[dict, float]]:
    """(atributos, fracción del lote que cubre) de cada unidad que toca el lote, de mayor a menor.

    La fracción es la proporción de puntos de muestreo que caen en la unidad; si una unidad toca el lote pero
    no le toca ningún punto, queda con 0. Lo que falta para sumar 1 es lote sin unidad en la carta.
    """
    from shapely.geometry import shape

    lote = shape(poligono).simplify(1e-5)  # ~1 m: el polígono va en la URL
    unidades = consultar(cliente, carta, f"INTERSECTS({carta.geometria}, {_wkt(lote)})", carta.campos)
    if not unidades:
        return []
    puntos = puntos_de_muestreo(poligono)
    clave = carta.campos[0]

    def unidad_del_punto(punto: tuple[float, float]) -> str | None:
        encontradas = consultar(cliente, carta, f"INTERSECTS({carta.geometria}, POINT({punto[0]:.6f} {punto[1]:.6f}))",
                                [clave], maximo=1)
        return next(iter(encontradas), None)

    if len(puntos) == 1:
        en_puntos = [unidad_del_punto(puntos[0])]
    else:
        with ThreadPoolExecutor(max_workers=HILOS) as hilos:
            en_puntos = list(hilos.map(unidad_del_punto, puntos))
    fracciones = [(atributos, en_puntos.count(fid) / len(puntos)) for fid, atributos in unidades.items()]
    return sorted(fracciones, key=lambda par: -par[1])


# ---------- interpretación de cada carta ----------

def _texto(valor) -> str:
    texto = str(valor or "").strip()
    return "" if texto in ("-", "0") else texto


def _cobertura(unidades: list[tuple[dict, float]], campo: str) -> str:
    """'cubre 70% del lote · otras unidades: AD1 30%' (por muestreo de puntos)."""
    texto = f"cubre {unidades[0][1]:.0%} del lote"
    if len(unidades) > 1:
        texto += " · otras unidades: " + ", ".join(
            f"{_texto(a.get(campo)) or '?'} {f:.0%}" if f > 0 else f"{_texto(a.get(campo)) or '?'} (borde)"
            for a, f in unidades[1:])
    sin_unidad = 1 - sum(f for _, f in unidades)
    if sin_unidad > 1e-9:
        texto += f" · {sin_unidad:.0%} del lote sin unidad en la carta"
    return texto + " (muestreo de puntos)"


def clase_capacidad_uso(texto: str) -> tuple[int | None, str]:
    """'IVe' → (4, 'e'); 'I-2' → (1, ''); ilegible → (None, '')."""
    coincidencia = re.match(r"\s*(VIII|VII|VI|IV|V|III|II|I)(?![IVX])\s*-?\s*([ewsc]*)", texto or "")
    if not coincidencia:
        return None, ""
    return ROMANOS[coincidencia.group(1)], coincidencia.group(2)


def indice_productividad(lote_id: str, unidades: list[tuple[dict, float]]) -> Observacion:
    """Índice de productividad (IP, 0-100) de la unidad dominante del Atlas 1:500.000."""
    base = dict(lote_id=lote_id, fecha=ATLAS.fecha, variable="suelo_indice_productividad", unidad="IP 0-100",
                fuente="GeoINTA", resolucion_m=ATLAS.resolucion_m)
    origen = ATLAS.origen
    if not unidades:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"La carta no tiene ninguna unidad de suelo en este lote · {origen}")
    atributos, fraccion = unidades[0]
    ip = atributos.get("ind_prod")
    componentes = [f"{_texto(atributos.get(f'sgrup_sue{i}'))} {atributos.get(f'porc_sue{i}'):g} %"
                   + (f" ({_texto(atributos.get(f'posi_sue{i}'))})" if _texto(atributos.get(f'posi_sue{i}')) else "")
                   for i in (1, 2, 3)
                   if _texto(atributos.get(f"sgrup_sue{i}")) and isinstance(atributos.get(f"porc_sue{i}"), (int, float))]
    limitantes = [t for t in (_texto(atributos.get(c)) for c in ("limit_ppal", "limit_secu", "limit_terc")) if t]
    detalle = " · ".join(p for p in [
        f"Unidad {_texto(atributos.get('simbc')) or '?'} ({_texto(atributos.get('tipo_uc')) or 'tipo desconocido'})"
        f", {_texto(atributos.get('provincia')).title()}",
        "suelos: " + ", ".join(componentes) if componentes else "",
        f"textura superficial {_texto(atributos.get('text_sups1')).lower()}" if _texto(atributos.get("text_sups1")) else "",
        f"subsuelo {_texto(atributos.get('text_bs1')).lower()}" if _texto(atributos.get("text_bs1")) else "",
        f"drenaje {_texto(atributos.get('drenaje_s1')).lower()}" if _texto(atributos.get("drenaje_s1")) else "",
        "limitantes: " + ", ".join(limitantes) if limitantes else "",
        _cobertura(unidades, "simbc"),
        origen,
    ] if p)
    if not isinstance(ip, (int, float)) or not 0 < ip <= 100:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"La unidad no trae índice de productividad válido ({ip!r}; p. ej. agua, "
                                f"urbano o misceláneas) · {detalle}")
    calidad = "buena" if fraccion >= UMBRAL_DOMINANTE else "dudosa"
    aviso = "" if calidad == "buena" else f"lote mixto: la unidad dominante cubre menos del {UMBRAL_DOMINANTE:.0%} · "
    return Observacion(**base, valor=float(ip), calidad=calidad, nota=aviso + detalle)


def capacidad_uso(lote_id: str, unidades: list[tuple[dict, float]]) -> Observacion:
    """Clase de capacidad de uso (1 a 8) de la unidad dominante de la carta 1:50.000 de Buenos Aires."""
    base = dict(lote_id=lote_id, fecha=BUENOS_AIRES.fecha, variable="suelo_clase_capacidad_uso", unidad="clase 1-8",
                fuente="GeoINTA", resolucion_m=BUENOS_AIRES.resolucion_m)
    origen = BUENOS_AIRES.origen
    if not unidades:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota="Sin carta de suelo detallada del INTA con capacidad de uso para este lote (GeoINTA "
                                "la publica en las cartas 1:50.000 de Buenos Aires y 1:100.000 de San Luis) · "
                                f"{origen}")
    atributos, fraccion = unidades[0]
    texto = _texto(atributos.get("CAP_USO"))
    clase, subclase = clase_capacidad_uso(texto)
    series = [f"{_texto(atributos.get(f'SERIE{i}'))} {atributos.get(f'PORC{i}')} %"
              + (f" ({_texto(atributos.get(f'FASE{i}'))})" if _texto(atributos.get(f"FASE{i}")) else "")
              for i in range(1, 7) if _texto(atributos.get(f"SERIE{i}"))]
    explicacion = ", ".join(SUBCLASES[s] for s in subclase if s in SUBCLASES)
    detalle = " · ".join(p for p in [
        f"Unidad {_texto(atributos.get('SIMBC')) or '?'} ({_texto(atributos.get('Nombre_UC')) or 'sin nombre'})",
        "series: " + ", ".join(series) if series else "",
        _texto(atributos.get("taxo_ppal")),
        _texto(atributos.get("PAISAJE")),
        f"capacidad de uso '{texto}'" + (f" = clase {clase}" if clase else "")
        + (f", subclase {subclase} ({explicacion})" if explicacion else ""),
        _cobertura(unidades, "SIMBC"),
        origen,
    ] if p)
    if clase is None:
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"La unidad no trae una clase de capacidad de uso legible · {detalle}")
    calidad = "buena" if fraccion >= UMBRAL_DOMINANTE else "dudosa"
    aviso = "" if calidad == "buena" else f"lote mixto: la unidad dominante cubre menos del {UMBRAL_DOMINANTE:.0%} · "
    return Observacion(**base, valor=float(clase), calidad=calidad, nota=aviso + detalle)


def carta_san_luis(lote_id: str, carta: Carta, unidades: list[tuple[dict, float]]) -> list[Observacion]:
    """Clase de capacidad de uso e índice de productividad de la unidad dominante de una hoja de San Luis."""
    comun = dict(lote_id=lote_id, fecha=carta.fecha, fuente="GeoINTA", resolucion_m=carta.resolucion_m)
    atributos, fraccion = unidades[0]
    texto = _texto(atributos.get("cap_uso"))
    clase, subclase = clase_capacidad_uso(texto)
    ip = atributos.get("ip")
    explicacion = ", ".join(SUBCLASES[s] for s in subclase if s in SUBCLASES)
    detalle = " · ".join(p for p in [
        f"Unidad {_texto(atributos.get('uc')) or '?'}",
        f"capacidad de uso '{texto}'" + (f" = clase {clase}" if clase else "")
        + (f", subclase {subclase} ({explicacion})" if explicacion else ""),
        f"IP {ip}" if ip is not None else "",
        _cobertura(unidades, "uc"),
        carta.origen,
    ] if p)
    calidad = "buena" if fraccion >= UMBRAL_DOMINANTE else "dudosa"
    aviso = "" if calidad == "buena" else f"lote mixto: la unidad dominante cubre menos del {UMBRAL_DOMINANTE:.0%} · "
    capacidad = (Observacion(**comun, variable="suelo_clase_capacidad_uso", unidad="clase 1-8", valor=float(clase),
                             calidad=calidad, nota=aviso + detalle) if clase is not None else
                 Observacion(**comun, variable="suelo_clase_capacidad_uso", unidad="clase 1-8", valor=None,
                             calidad="descartada", nota=f"La unidad no trae una clase de capacidad de uso legible · {detalle}"))
    if isinstance(ip, (int, float)) and 0 < ip <= 100:
        indice = Observacion(**comun, variable="suelo_indice_productividad_detallado", unidad="IP 0-100",
                             valor=float(ip), calidad=calidad, nota=aviso + detalle)
    else:
        indice = Observacion(**comun, variable="suelo_indice_productividad_detallado", unidad="IP 0-100", valor=None,
                             calidad="descartada", nota=f"La unidad no trae índice de productividad válido ({ip!r}) · {detalle}")
    return [capacidad, indice]


def capacidad_del_lote(cliente: httpx.Client, lote_id: str, poligono: dict) -> list[Observacion]:
    """Capacidad de uso de la carta detallada que cubre el lote: hojas de San Luis (nodo 15) o Buenos Aires."""
    from shapely.geometry import shape

    caja = shape(poligono).bounds
    hojas = [h for h in HOJAS_SAN_LUIS if h.toca(*caja)]
    for hoja in hojas:
        unidades = unidades_en_el_lote(cliente, hoja, poligono)
        if unidades:
            return carta_san_luis(lote_id, hoja, unidades)
    if hojas:  # el lote está en San Luis pero ninguna hoja lo cubre
        return [capacidad_uso(lote_id, [])]
    return [capacidad_uso(lote_id, unidades_en_el_lote(cliente, BUENOS_AIRES, poligono))]


# ---------- Mapa Nacional de Cultivos (spec 021) ----------

class Campana(BaseModel):
    capa: str
    nombre: str
    estacion: str  # verano, invierno o campana (la 2018/19 es un solo mapa con los dos ciclos)
    fecha: date    # SUPUESTO: verano → 1 de enero del año de cosecha; invierno → 1 de julio; campaña → 1 de enero
    url_tif: str | None = None            # campañas que el INTA publica solo en GeoSEPA (GeoTIFF, sin WCS)
    leyenda: dict[int, str] | None = None  # la de su archivo .qml, porque GeoSEPA no tiene GetLegendGraphic


# La campaña 2024/25 está solo en GeoSEPA (sepa.inta.gob.ar), no en el WCS de GeoINTA. Sus leyendas son las de
# MNC_verano.qml y MNC_invierno.qml de la misma carpeta (spec 021, §23.4).
GEOSEPA_MNC = "https://sepa.inta.gob.ar/productos/geosepa/Mapa_Nacional_Cultivo/tif"
LEYENDA_MNC_VERANO = {10: "Maíz", 11: "Soja", 12: "Girasol", 13: "Poroto", 14: "Caña de azúcar", 15: "Algodón",
                      16: "Maní", 17: "Arroz", 18: "Sorgo", 19: "Girasol-CV", 21: "Barbecho", 22: "No agrícola",
                      26: "Papa", 27: "Verdeo de maíz", 28: "Verdeo de sorgo", 30: "Tabaco", 31: "Máscara"}
LEYENDA_MNC_INVIERNO = {6: "Garbanzo", 16: "Cereales de invierno", 17: "Otros cultivos de invierno", 18: "Barbecho",
                        19: "Caña de azúcar", 20: "No agrícola", 24: "Arveja", 25: "Máscara", 26: "Papa"}
USO_GEOSEPA = ("descargado de GeoSEPA: uso comercial sujeto a autorización del CIRN-INTA (términos de SEPA); "
               "fuente: SEPA, Instituto de Clima y Agua (CIRN-INTA)")
ENTORNO_GDAL = dict(GDAL_HTTP_TIMEOUT=30, GDAL_HTTP_MAX_RETRY=2, GDAL_HTTP_RETRY_DELAY=2,
                    GDAL_HTTP_LOW_SPEED_TIME=15, GDAL_HTTP_LOW_SPEED_LIMIT=1000,  # corta un rango que casi no baja
                    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_USE_HEAD="NO")
# Tope para todo el Mapa Nacional de Cultivos. El 16/10/2026 la lectura de GeoSEPA quedó trabada más de una hora en
# dos parcelas reales de San Luis (456 y 196 ha) y la consulta del suelo no volvía nunca: pasado el tope, las
# campañas que faltan quedan descartadas y el suelo contesta igual.
TOPE_MNC_SEGUNDOS = 90

CAMPANAS = [
    Campana(capa="geonode:mnc_2018_2019_V1R1", nombre="campaña 2018/19", estacion="campana", fecha=date(2019, 1, 1)),
    Campana(capa="geonode:mnc_invierno_2019", nombre="invierno 2019", estacion="invierno", fecha=date(2019, 7, 1)),
    Campana(capa="geonode:mnc_verano_2020", nombre="verano 2019/20", estacion="verano", fecha=date(2020, 1, 1)),
    Campana(capa="geonode:invierno2020", nombre="invierno 2020", estacion="invierno", fecha=date(2020, 7, 1)),
    Campana(capa="geonode:mnc_verano2021", nombre="verano 2020/21", estacion="verano", fecha=date(2021, 1, 1)),
    Campana(capa="geonode:MNC_invierno2021", nombre="invierno 2021", estacion="invierno", fecha=date(2021, 7, 1)),
    Campana(capa="geonode:MNC_verano2022", nombre="verano 2021/22", estacion="verano", fecha=date(2022, 1, 1)),
    Campana(capa="geonode:MNC_invierno2022", nombre="invierno 2022", estacion="invierno", fecha=date(2022, 7, 1)),
    Campana(capa="geonode:MNC_verano_2023", nombre="verano 2022/23", estacion="verano", fecha=date(2023, 1, 1)),
    Campana(capa="geonode:mnc_invierno2023_d86dd2aa0b678a011b89830f77cec883", nombre="invierno 2023",
            estacion="invierno", fecha=date(2023, 7, 1)),
    Campana(capa="geonode:mnc_verano2024_f300268fd112b0ec3ef5f731edb78882", nombre="verano 2023/24",
            estacion="verano", fecha=date(2024, 1, 1)),
    Campana(capa="GeoSEPA MNC_invierno_2024-2025", nombre="invierno 2024", estacion="invierno",
            fecha=date(2024, 7, 1), url_tif=f"{GEOSEPA_MNC}/MNC_invierno_2024-2025.tif", leyenda=LEYENDA_MNC_INVIERNO),
    Campana(capa="GeoSEPA MNC_verano_2024-2025", nombre="verano 2024/25", estacion="verano",
            fecha=date(2025, 1, 1), url_tif=f"{GEOSEPA_MNC}/MNC_verano_2024-2025.tif", leyenda=LEYENDA_MNC_VERANO),
]
PIXEL_MNC = 2.694945852388963e-4  # grados, de DescribeCoverage (~30 m)

# Código común de Rotaterra para las clases del Mapa Nacional de Cultivos: cada campaña publica su propia
# leyenda (la soja es 1 en 2018/19 y 11 después), así que se traduce por el nombre de la clase (spec 021, §23).
CULTIVOS = {
    "maiz": 1, "soja": 2, "girasol": 3, "sorgo": 4, "mani": 5, "poroto": 6, "algodon": 7, "arroz": 8,
    "cana de azucar": 9, "papa": 10, "tabaco": 11, "verdeo de sorgo": 12, "verdeo de maiz": 13,
    "cereales de invierno": 20, "cultivo de invierno": 21, "garbanzo": 22, "arveja": 23, "otros cultivos": 24,
    "otros cultivos de invierno": 24,
    "cultivo de invierno - soja": 30, "cultivo de invierno - maiz": 31, "girasol - cultivo de verano": 32,
    "girasol-cv": 32,
    "barbecho": 40, "no agricola": 41, "ganaderia": 42, "vegetacion natural lenosa": 43,
    "plantaciones forestales y frutales": 44, "vegetacion lenosa implantada": 45,
}
NO_SON_CLASE = {"zonas enmascaradas", "limite", "mascara"}


def _normalizar(etiqueta: str) -> str:
    texto = unicodedata.normalize("NFKD", etiqueta or "").encode("ascii", "ignore").decode().lower()
    texto = re.sub(r"\(.*?\)", "", texto)  # "(Cultivo único)"
    texto = re.sub(r"\s+gr$", "", " ".join(texto.split()))  # "Sorgo GR"
    return texto.strip()


def codigo_cultivo(etiqueta: str) -> int | None:
    return CULTIVOS.get(_normalizar(etiqueta))


def leyenda_raster(cliente: httpx.Client, url_wms: str, capa: str) -> dict[int, str]:
    """Código del píxel → nombre de la clase, según la leyenda que publica la propia capa."""
    respuesta = cliente.get(url_wms, params={"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic",
                                             "layer": capa, "format": "application/json"})
    respuesta.raise_for_status()
    if "json" not in respuesta.headers.get("content-type", ""):
        raise ErrorGeoINTA(f"GeoINTA no devolvió la leyenda de {capa}: {respuesta.text[:200]!r}")
    clases = {}
    for capa_ in respuesta.json().get("Legend", []):
        for regla in capa_.get("rules", []):
            for simbolo in regla.get("symbolizers", []):
                for entrada in ((simbolo.get("Raster") or {}).get("colormap") or {}).get("entries", []):
                    try:
                        clases[round(float(entrada["quantity"]))] = str(entrada.get("label") or "").strip()
                    except (KeyError, TypeError, ValueError):
                        continue
    if not clases:
        raise ErrorGeoINTA(f"La leyenda de {capa} no trae clases")
    return clases


def pixeles_en_el_lote(cliente: httpx.Client, url_wcs: str, cobertura: str, poligono: dict, pixel: float):
    """Valores de los píxeles del ráster cuyo centro cae dentro del lote (WCS 1.0.0, GeoTIFF recortado al lote)."""
    import warnings

    import numpy as np
    import rasterio
    from rasterio.errors import NotGeoreferencedWarning
    from rasterio.features import geometry_mask
    from rasterio.transform import from_bounds
    from shapely.geometry import shape

    lote = shape(poligono)
    oeste, sur, este, norte = lote.bounds
    oeste, sur, este, norte = oeste - pixel, sur - pixel, este + pixel, norte + pixel
    ancho, alto = max(1, round((este - oeste) / pixel)), max(1, round((norte - sur) / pixel))
    respuesta = cliente.get(url_wcs, params={
        "service": "WCS", "version": "1.0.0", "request": "GetCoverage", "coverage": cobertura, "crs": "EPSG:4326",
        "bbox": f"{oeste:.6f},{sur:.6f},{este:.6f},{norte:.6f}", "width": ancho, "height": alto, "format": "GeoTIFF"})
    respuesta.raise_for_status()
    if "tif" not in respuesta.headers.get("content-type", ""):
        raise ErrorGeoINTA(f"GeoINTA no devolvió un GeoTIFF para {cobertura}: {respuesta.text[:200]!r}")
    with rasterio.MemoryFile(respuesta.content) as archivo, archivo.open() as raster:
        datos = raster.read(1)
        nodata = raster.nodata
        # si el GeoTIFF no trae georreferencia, es la grilla que se pidió
        transform = raster.transform if not raster.transform.is_identity else \
            from_bounds(oeste, sur, este, norte, datos.shape[1], datos.shape[0])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NotGeoreferencedWarning)  # aviso interno de GDAL al rasterizar en memoria
        fuera = geometry_mask([lote.__geo_interface__], out_shape=datos.shape, transform=transform)
        if fuera.all():  # lote más chico que un píxel: los que toca
            fuera = geometry_mask([lote.__geo_interface__], out_shape=datos.shape, transform=transform,
                                  all_touched=True)
    valores = datos[~fuera]
    if nodata is not None:
        valores = valores[valores != nodata]
    return np.asarray(valores)


def leer_geosepa(url: str, poligono: dict):
    """Píxeles del lote en un GeoTIFF de GeoSEPA, leyendo solo ese pedazo con rangos de bytes.

    El servidor de SEPA es muy lento para bajar el mapa entero (193 MB), pero acepta rangos: se pide la ventana del
    lote. Mismo criterio que el WCS: cuentan los píxeles con el centro dentro del lote.
    """
    import numpy as np
    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.windows import Window, from_bounds
    from shapely.geometry import shape

    lote = shape(poligono)
    with rasterio.Env(**ENTORNO_GDAL), rasterio.open(("/vsicurl/" if url.startswith("http") else "") + url) as raster:
        ventana = from_bounds(*lote.bounds, raster.transform).round_offsets(op="floor").round_lengths(op="ceil")
        ventana = Window(ventana.col_off, ventana.row_off, max(ventana.width, 1) + 1, max(ventana.height, 1) + 1)
        datos = raster.read(1, window=ventana, boundless=True, fill_value=raster.nodata or 0)
        transform = raster.window_transform(ventana)
        nodata = raster.nodata
    fuera = geometry_mask([lote.__geo_interface__], out_shape=datos.shape, transform=transform)
    if fuera.all():
        fuera = geometry_mask([lote.__geo_interface__], out_shape=datos.shape, transform=transform, all_touched=True)
    valores = datos[~fuera]
    if nodata is not None:
        valores = valores[valores != nodata]
    return np.asarray(valores)


def cultivo_de_campana(lote_id: str, campana: Campana, valores, leyenda: dict[int, str]) -> Observacion:
    """Cultivo dominante del lote en una campaña, con el reparto de clases en la nota."""
    base = dict(lote_id=lote_id, fecha=campana.fecha, variable=f"cultivo_mnc_{campana.estacion}",
                unidad="código de cultivo (spec 021)", fuente="GeoINTA", resolucion_m=30)
    lugar = (f"GeoTIFF de GeoSEPA {campana.url_tif} leído por rangos · {USO_GEOSEPA}" if campana.url_tif
             else f"WCS del nodo Nacional, capa {campana.capa}")
    origen = (f"Mapa Nacional de Cultivos {campana.nombre} (INTA), píxel de 30 m · {lugar} · fecha: SUPUESTO, la "
              f"campaña se fecha el 1/1 del año de cosecha (verano) o el 1/7 (invierno)")
    codigos = [round(float(v)) for v in valores]
    validos = Counter(c for c in codigos if c in leyenda and codigo_cultivo(leyenda[c]) is not None)
    if not validos:
        sin_clase = sorted({leyenda.get(c, f"código {c} fuera de la leyenda") for c in codigos})
        motivo = ", ".join(sin_clase) if sin_clase else "ningún píxel dentro del lote"
        return Observacion(**base, valor=None, calidad="descartada",
                           nota=f"El mapa no clasifica el lote en esa campaña ({motivo}) · {origen}")
    total = len(codigos)
    dominante, cantidad = validos.most_common(1)[0]
    fraccion = cantidad / total
    reparto = ", ".join(f"{leyenda[c]} {n / total:.0%}" for c, n in validos.most_common())
    sin_dato = total - sum(validos.values())
    if sin_dato:
        reparto += f", sin clasificar {sin_dato / total:.0%}"
    calidad = "buena" if fraccion >= UMBRAL_DOMINANTE else "dudosa"
    aviso = "" if calidad == "buena" else f"lote mixto: la clase dominante cubre menos del {UMBRAL_DOMINANTE:.0%} · "
    return Observacion(**base, valor=float(codigo_cultivo(leyenda[dominante])), calidad=calidad,
                       nota=f"{aviso}{leyenda[dominante]} (código {codigo_cultivo(leyenda[dominante])}) en el "
                            f"{fraccion:.0%} del lote · reparto: {reparto} ({total} píxeles) · {origen}")


def _campana_descartada(lote_id: str, campana: Campana, motivo: str) -> Observacion:
    return Observacion(lote_id=lote_id, fecha=campana.fecha, variable=f"cultivo_mnc_{campana.estacion}",
                       unidad="código de cultivo (spec 021)", fuente="GeoINTA", resolucion_m=30, valor=None,
                       calidad="descartada",
                       nota=f"GeoINTA no respondió ({motivo[:150]}); se reintenta en la próxima consulta · "
                            f"Mapa Nacional de Cultivos {campana.nombre}")


def cultivos_del_lote(cliente: httpx.Client, lote_id: str, poligono: dict,
                      tope: float = TOPE_MNC_SEGUNDOS) -> list[Observacion]:
    """Cultivo dominante en cada campaña del Mapa Nacional de Cultivos (2018/19 a verano 2024/25)."""
    errores = []

    def una(campana: Campana) -> Observacion:
        try:
            if campana.url_tif:
                leyenda, valores = campana.leyenda, leer_geosepa(campana.url_tif, poligono)
            else:
                leyenda = leyenda_raster(cliente, URL_WMS, campana.capa)
                valores = pixeles_en_el_lote(cliente, URL_WCS, campana.capa, poligono, PIXEL_MNC)
            return cultivo_de_campana(lote_id, campana, valores, leyenda)
        except Exception as error:  # noqa: BLE001 — cualquier falla de una campaña descarta solo esa
            errores.append(f"{campana.capa}: {type(error).__name__}: {error}")
            return _campana_descartada(lote_id, campana, f"{type(error).__name__}: {error}")

    hilos = ThreadPoolExecutor(max_workers=HILOS)
    futuros = [hilos.submit(una, campana) for campana in CAMPANAS]
    listos, _ = wait(futuros, timeout=tope)
    hilos.shutdown(wait=False, cancel_futures=True)  # no se espera a una lectura trabada
    observaciones = []
    for campana, futuro in zip(CAMPANAS, futuros):
        if futuro in listos:
            observaciones.append(futuro.result())
        else:
            errores.append(f"{campana.capa}: no respondió en {tope:.0f} s")
            observaciones.append(_campana_descartada(lote_id, campana, f"no respondió en {tope:.0f} s"))
    if len(errores) == len(CAMPANAS):
        raise ErrorGeoINTA("Mapa Nacional de Cultivos: " + " | ".join(errores[:3]))
    return observaciones


# ---------- textura y pH (spec 021): el nodo 05 los publica solo por WMS ----------

class CapaWMS(BaseModel):
    capa: str
    variable: str
    nombre: str


TEXTURA = [
    CapaWMS(capa="geonode:texclass_0_15_con_mascara_a8f640b4c16411b2c134d1de0a29cc79",
            variable="suelo_textura_0_15cm", nombre="Clases texturales 0-15 cm"),
    CapaWMS(capa="geonode:texclass_15_30_con_mascara_c63eeded54b6b2b5540007ee7d6f8ade",
            variable="suelo_textura_15_30cm", nombre="Clases texturales 15-30 cm"),
    CapaWMS(capa="geonode:texclass_30_60_con_mascara_9654064cf709638813faeb3a54f6e9e1",
            variable="suelo_textura_30_60cm", nombre="Clases texturales 30-60 cm"),
    CapaWMS(capa="geonode:texclass_60_100_con_mascara_676377cf2182b97bf62cfead3515bdf4",
            variable="suelo_textura_60_100cm", nombre="Clases texturales 60-100 cm"),
]
PH = [
    CapaWMS(capa="geonode:ph_0_30_nuevo_recorte_m_4d4cbbd459875375ae3e856e2870841f",
            variable="suelo_ph_0_30cm", nombre="Mapa de pH del suelo 0-30 cm"),
    CapaWMS(capa="geonode:ph_30_100_nuevo_recorte_m_cbccd7b512bb4f943ad9672e961bee3d",
            variable="suelo_ph_30_100cm", nombre="Mapa de pH del suelo 30-100 cm"),
]
GRILLA_WMS = 3  # puntos de lectura: grilla de 3 × 3 sobre el lote (los ráster son de ~1 km)
RESOLUCION_PH = 1000  # publicada: "Resolución del pixel: 1 km"
RESOLUCION_TEXTURA = 1000  # SUPUESTO: no publicada; se toma la del pH, del mismo proyecto y autor

# Código común de textura (de gruesa a fina). Cada profundidad publica su propia leyenda (el 9 es "Limoso"
# a 0-15 cm y "Franco arenoso" a 30-60 cm), así que se traduce por el nombre de la clase (spec 021, §23.2).
TEXTURAS = {
    "arenoso": 1, "areno franco": 2, "franco arenoso": 3, "franco": 4, "franco limoso": 5, "limoso": 6,
    "franco arcillo arenoso": 7, "franco arcilloso": 8, "franco arcillo limoso": 9, "arcillo arenoso": 10,
    "arcillo limoso": 11, "arcilloso": 12, "franco/franco limoso": 13,
}


def codigo_textura(etiqueta: str) -> int | None:
    return TEXTURAS.get(_normalizar(etiqueta).replace(" / ", "/"))


def valor_en_punto(cliente: httpx.Client, url_wms: str, capa: str, punto: tuple[float, float]) -> float | None:
    """Valor del píxel del ráster en un punto (WMS GetFeatureInfo). None si el punto no tiene dato."""
    lon, lat, d = punto[0], punto[1], 0.0005
    respuesta = cliente.get(url_wms, params={
        "service": "WMS", "version": "1.1.1", "request": "GetFeatureInfo", "layers": capa, "query_layers": capa,
        "styles": "", "srs": "EPSG:4326", "bbox": f"{lon - d:.6f},{lat - d:.6f},{lon + d:.6f},{lat + d:.6f}",
        "width": 11, "height": 11, "x": 5, "y": 5, "info_format": "application/json", "feature_count": 1})
    respuesta.raise_for_status()
    if "json" not in respuesta.headers.get("content-type", ""):
        raise ErrorGeoINTA(f"GeoINTA no devolvió JSON para {capa}: {respuesta.text[:200]!r}")
    elementos = respuesta.json().get("features", [])
    valor = (elementos[0].get("properties") or {}).get("GRAY_INDEX") if elementos else None
    return float(valor) if isinstance(valor, (int, float)) else None


def _origen_wms(capa: CapaWMS, puntos: int) -> str:
    return (f"{capa.nombre} (INTA) · WMS GetFeatureInfo del nodo 05 (único servicio que lo publica), capa "
            f"{capa.capa}, {puntos} puntos del lote")


def textura_del_lote(lote_id: str, capa: CapaWMS, valores: list[float | None], leyenda: dict[int, str]) -> Observacion:
    base = dict(lote_id=lote_id, fecha=date(2024, 12, 10), variable=capa.variable,
                unidad="clase textural (1 arenoso … 12 arcilloso, spec 021)", fuente="GeoINTA",
                resolucion_m=RESOLUCION_TEXTURA)
    origen = (_origen_wms(capa, len(valores)) + " · fecha: alta en el catálogo · resolución: SUPUESTO 1 km (no "
              "publicada) · mapa de modelo: no es una medición del lote")
    codigos = [round(v) for v in valores if v is not None]
    validos = Counter(c for c in codigos if c in leyenda and codigo_textura(leyenda[c]) is not None)
    if not validos:
        motivo = ", ".join(sorted({leyenda.get(c, f"código {c} fuera de la leyenda") for c in codigos})) or "sin dato"
        return Observacion(**base, valor=None, calidad="descartada", nota=f"Sin clase textural en el lote ({motivo}) · {origen}")
    dominante, cantidad = validos.most_common(1)[0]
    fraccion = cantidad / len(valores)
    reparto = ", ".join(f"{leyenda[c]} {n / len(valores):.0%}" for c, n in validos.most_common())
    calidad = "buena" if fraccion >= UMBRAL_DOMINANTE else "dudosa"
    codigo = codigo_textura(leyenda[dominante])
    return Observacion(**base, valor=float(codigo), calidad=calidad,
                       nota=f"{leyenda[dominante]} (código común {codigo}) en {cantidad} de {len(valores)} puntos · "
                            f"reparto: {reparto} · {origen}")


def ph_del_lote(lote_id: str, capa: CapaWMS, valores: list[float | None]) -> Observacion:
    base = dict(lote_id=lote_id, fecha=date(2024, 12, 9), variable=capa.variable, unidad="pH", fuente="GeoINTA",
                resolucion_m=RESOLUCION_PH)
    origen = (_origen_wms(capa, len(valores)) + " · fecha: alta en el catálogo · modelo de 1 km (RMSE 0,84; "
              "R² 0,456): estimación regional, no es una medición del lote")
    validos = [v for v in valores if v is not None and 0 < v <= 14]  # 101 = Miscelánea
    if not validos:
        return Observacion(**base, valor=None, calidad="descartada", nota=f"Sin pH en el lote · {origen}")
    media = sum(validos) / len(validos)
    calidad = "buena" if len(validos) / len(valores) >= UMBRAL_DOMINANTE else "dudosa"
    return Observacion(**base, valor=round(media, 2), calidad=calidad,
                       nota=f"Media de {len(validos)} de {len(valores)} puntos (de {min(validos):.2f} a "
                            f"{max(validos):.2f}) · {origen}")


def textura_y_ph(cliente: httpx.Client, lote_id: str, poligono: dict) -> list[Observacion]:
    """Clase textural en 4 profundidades y pH en 2, leídos por WMS en una grilla de puntos del lote."""
    puntos = puntos_de_muestreo(poligono, GRILLA_WMS)
    errores = []

    def una(capa: CapaWMS) -> Observacion:
        try:
            valores = [valor_en_punto(cliente, URL_WMS_NODO05, capa.capa, p) for p in puntos]
            if capa in TEXTURA:
                return textura_del_lote(lote_id, capa, valores, leyenda_raster(cliente, URL_WMS_NODO05, capa.capa))
            return ph_del_lote(lote_id, capa, valores)
        except Exception as error:  # noqa: BLE001 — una capa caída descarta solo esa
            errores.append(f"{capa.capa}: {type(error).__name__}: {error}")
            return _textura_o_ph_vacia(lote_id, capa).model_copy(update={
                "nota": f"GeoINTA no respondió ({type(error).__name__}: {str(error)[:150]}); se reintenta en la "
                        f"próxima consulta · {capa.nombre}"})

    with ThreadPoolExecutor(max_workers=HILOS) as hilos:
        observaciones = list(hilos.map(una, TEXTURA + PH))
    if len(errores) == len(TEXTURA + PH):
        raise ErrorGeoINTA("Textura y pH: " + " | ".join(errores[:3]))
    return observaciones


def _textura_o_ph_vacia(lote_id: str, capa: CapaWMS) -> Observacion:
    return textura_del_lote(lote_id, capa, [], {}) if capa in TEXTURA else ph_del_lote(lote_id, capa, [])


# ---------- carbono orgánico del suelo 2023 (spec 021, §23.6) ----------

COBERTURA_COS = "geonode:Mapa_COS_Nacional"  # recurso 487 del catálogo, "Almacenamiento de Carbono - 2023"
PIXEL_COS = 0.002245788210298804  # grados, de DescribeCoverage (offsetVector)
RESOLUCION_COS = round(PIXEL_COS * 111_320)  # 250 m (un grado de latitud son ~111,32 km)
FECHA_COS = date(2023, 10, 27)  # publicación del recurso 487 en el catálogo (las muestras son de 2015-2022)
ORIGEN_COS = ("Mapa de almacenamiento de carbono orgánico del suelo 2023 (Gaitán et al. 2023; INTA, Aapresid, CREA y "
              "SAGyP), 0-30 cm, en t/ha según el resumen del recurso 487 del catálogo GeoINTA · WCS del nodo Nacional, "
              f"cobertura {COBERTURA_COS}, píxel de {PIXEL_COS:.6f}° (~{RESOLUCION_COS} m) · fecha: publicación en el "
              "catálogo, con muestras de 2015 a 2022 · modelo nacional (Random Forest): estimación regional, no es una "
              "medición del lote, y el catálogo no publica su error · licencia CC BY-NC-SA 2.5 (uso no comercial)")


def carbono_organico(lote_id: str, valores) -> Observacion:
    """Carbono orgánico del suelo 0-30 cm (t/ha): media de los píxeles del lote, con cantidad y rango en la nota.

    El GeoTIFF no declara un valor de "sin dato", así que no cuentan los píxeles vacíos (NaN), los de 0 o menos
    y los de ±3,4e38 (el relleno de los float32): ninguno es un almacenamiento de carbono posible.
    """
    import numpy as np

    base = dict(lote_id=lote_id, fecha=FECHA_COS, variable="suelo_carbono_organico_0_30cm_t_ha", unidad="t/ha",
                fuente="GeoINTA", resolucion_m=RESOLUCION_COS)
    todos = np.asarray(valores, dtype="float64").ravel()
    validos = todos[np.isfinite(todos) & (todos > 0) & (todos < 1e30)]
    if not validos.size:
        motivo = (f"los {todos.size} píxeles del lote no tienen dato" if todos.size
                  else "ningún píxel dentro del lote")
        return Observacion(**base, valor=None, calidad="descartada", nota=f"Sin carbono orgánico ({motivo}) · {ORIGEN_COS}")
    sin_dato = todos.size - validos.size
    return Observacion(**base, valor=round(float(validos.mean()), 2), calidad="dudosa",
                       nota=f"Media de {validos.size} píxeles con centro en el lote (de {validos.min():.2f} a "
                            f"{validos.max():.2f} t/ha)" + (f", {sin_dato} píxeles sin dato" if sin_dato else "")
                            + f" · {ORIGEN_COS}")


def carbono_del_lote(cliente: httpx.Client, lote_id: str, poligono: dict) -> Observacion:
    """Carbono orgánico 2023 del lote por WCS. Si el servidor falla, levanta ErrorGeoINTA (o el error de httpx)."""
    try:
        valores = pixeles_en_el_lote(cliente, URL_WCS, COBERTURA_COS, poligono, PIXEL_COS)
    except (httpx.HTTPError, ErrorGeoINTA):
        raise
    except Exception as error:  # noqa: BLE001 — un GeoTIFF ilegible es una falla del servidor
        raise ErrorGeoINTA(f"GeoTIFF de carbono ilegible: {type(error).__name__}: {error}") from error
    return carbono_organico(lote_id, valores)


# ---------- consulta completa ----------

ERRORES_DE_RED = (httpx.HTTPError, ValueError, KeyError, ErrorGeoINTA)


# ---------- memoria del suelo y límite de pedidos al INTA (spec 044) ----------
# En la prueba del piloto el INTA cortó la conexión ("Connection reset") después del primer lote.

MAX_PEDIDOS_INTA = 3               # pedidos HTTP a la vez al INTA, sumando todas las consultas de la app
DURACION_MEMORIA = 30 * 24 * 3600  # el suelo no cambia: un lote ya pedido sale de la memoria 30 días
MAX_LOTES_EN_MEMORIA = 500
NO_RESPONDIO = "GeoINTA no respondió"

_turnos_inta = threading.BoundedSemaphore(MAX_PEDIDOS_INTA)
_memoria: "OrderedDict[str, tuple[float, date, list[Observacion]]]" = OrderedDict()
_candado_memoria = threading.Lock()


class TransporteConTurno(httpx.BaseTransport):
    """Cada pedido HTTP espera su turno: como mucho MAX_PEDIDOS_INTA a la vez en toda la app."""

    def __init__(self, interno: httpx.BaseTransport | None = None):
        self.interno = interno or httpx.HTTPTransport()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        with _turnos_inta:
            respuesta = self.interno.handle_request(request)
            try:
                respuesta.read()  # se lee entero adentro del turno, así no se suelta con el cuerpo a medias
            except BaseException:
                respuesta.close()
                raise
            return respuesta

    def close(self) -> None:
        self.interno.close()


def cliente_inta() -> httpx.Client:
    return httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": "Rotaterra/0.1"},
                        transport=TransporteConTurno())


def llave_del_lote(poligono: dict) -> str:
    """El polígono con coordenadas redondeadas a 6 decimales (~10 cm): el mismo lote da la misma llave."""
    def redondear(c):
        return round(c, 6) if isinstance(c, (int, float)) else [redondear(x) for x in c]
    texto = json.dumps({"type": poligono.get("type"), "coordinates": redondear(poligono.get("coordinates"))})
    return hashlib.sha256(texto.encode()).hexdigest()


def de_la_memoria(llave: str, lote_id: str, ahora: float | None = None) -> list[Observacion] | None:
    ahora = time.time() if ahora is None else ahora
    with _candado_memoria:
        guardado = _memoria.get(llave)
        if guardado is None:
            return None
        hasta, pedido, observaciones = guardado
        if ahora >= hasta:
            del _memoria[llave]
            return None
        _memoria.move_to_end(llave)
    aviso = f" · guardado en memoria: el INTA lo entregó el {pedido.isoformat()}"
    return [o.model_copy(update={"lote_id": lote_id, "nota": o.nota + aviso}) for o in observaciones]


def a_la_memoria(llave: str, observaciones: list[Observacion], ahora: float | None = None) -> None:
    ahora = time.time() if ahora is None else ahora
    with _candado_memoria:
        _memoria[llave] = (ahora + DURACION_MEMORIA, date.today(), list(observaciones))
        _memoria.move_to_end(llave)
        while len(_memoria) > MAX_LOTES_EN_MEMORIA:
            _memoria.popitem(last=False)  # sale el que se usó hace más tiempo


def obtener_suelo(lote_id: str, poligono: dict, cliente: httpx.Client | None = None) -> list[Observacion]:
    """Suelo (IP, capacidad de uso, textura, pH y carbono) e historia de cultivos del lote. Son datos fijos: se piden
    una vez y quedan en memoria (spec 044). Con un cliente propio (los tests) no se usa la memoria."""
    validar_poligono(poligono)
    propio = cliente is None
    llave = llave_del_lote(poligono) if propio else None
    if llave and (guardado := de_la_memoria(llave, lote_id)) is not None:
        return guardado
    cliente = cliente or cliente_inta()
    pasos = [
        ("Atlas de Suelos", lambda: [indice_productividad(lote_id, unidades_en_el_lote(cliente, ATLAS, poligono))],
         lambda: [indice_productividad(lote_id, [])]),
        ("cartas de suelo detalladas", lambda: capacidad_del_lote(cliente, lote_id, poligono),
         lambda: [capacidad_uso(lote_id, [])]),
        ("Mapa Nacional de Cultivos", lambda: cultivos_del_lote(cliente, lote_id, poligono),
         lambda: [_campana_descartada(lote_id, c, "") for c in CAMPANAS]),
        ("textura y pH", lambda: textura_y_ph(cliente, lote_id, poligono),
         lambda: [_textura_o_ph_vacia(lote_id, c) for c in TEXTURA + PH]),
        ("carbono orgánico 2023", lambda: [carbono_del_lote(cliente, lote_id, poligono)],
         lambda: [carbono_organico(lote_id, [])]),
    ]
    observaciones, errores = [], []
    try:
        for nombre, leer, vacias in pasos:
            try:
                observaciones.extend(leer())
            except ERRORES_DE_RED as error:
                errores.append(f"{nombre}: {type(error).__name__}: {error}")
                aviso = (f"{NO_RESPONDIO} ({type(error).__name__}: {str(error)[:150]}); se reintenta "
                         f"en la próxima consulta · {nombre}")
                observaciones.extend(o.model_copy(update={"nota": aviso}) for o in vacias())
    finally:
        if propio:
            cliente.close()
    if len(errores) == len(pasos):
        raise ErrorGeoINTA("No se pudo consultar GeoINTA: " + " | ".join(errores))
    if llave and not errores and not any(o.nota.startswith(NO_RESPONDIO) for o in observaciones):
        a_la_memoria(llave, observaciones)  # solo lo completo: un error guardado se repetiría 30 días
    return observaciones


# ---------- conexión con el núcleo (spec 009) ----------

SATELITES = [Satelite("GeoINTA", lambda lote, desde, hasta: obtener_suelo(lote["id"], lote["poligono"]),
                      estatico=True)]

router = APIRouter(tags=["GeoINTA (pruebas internas)"])


class PedidoSuelo(BaseModel):
    lote_id: str
    poligono: dict


@router.post("/suelo", response_model=list[Observacion])
def suelo(pedido: PedidoSuelo) -> list[Observacion]:
    try:
        validar_poligono(pedido.poligono)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener_suelo(pedido.lote_id, pedido.poligono)
    except ErrorGeoINTA as error:
        raise HTTPException(status_code=502, detail=str(error))
