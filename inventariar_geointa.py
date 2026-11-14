"""Inventario del catálogo GeoINTA (spec 021, fase 1). Solo lee: no integra nada.

Se usa desde GitHub (Actions → "Probar GeoINTA (inventario del catálogo)").

    python inventariar_geointa.py "lat, lon; lat, lon; ..."   # esquinas del lote de prueba

Para cada dataset del catálogo anota lo que publica el INTA (nombre, descripción, tipo, fechas, extensión,
enlaces) y, si la capa se puede consultar por WFS, si toca el lote. Lo que el catálogo no publica queda vacío:
no se completa nada a ojo.
"""

import json
import re
import sys
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import httpx

BASE = "https://geo-backend.inta.gob.ar"
OWS = f"{BASE}/geoserver/ows"
POR_PAGINA = 100
HILOS = 6


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def esquinas(texto: str) -> list[tuple[float, float]]:
    """'lat, lon; lat, lon; ...' → [(lon, lat), ...] cerrado."""
    puntos = []
    for par in texto.split(";"):
        lat, lon = (float(x) for x in par.split(","))
        puntos.append((lon, lat))
    return puntos + [puntos[0]]


def recursos(cliente: httpx.Client) -> list[dict]:
    """Todos los recursos del catálogo GeoNode, probando las rutas de la API v2 y v1."""
    for ruta, clave in (("/api/v2/resources", "resources"), ("/api/v2/datasets", "datasets"),
                        ("/api/v2/layers", "layers"), ("/api/layers/", "objects")):
        todos, pagina = [], 1
        while True:
            params = {"page_size": POR_PAGINA, "page": pagina} if ruta.startswith("/api/v2") \
                else {"limit": POR_PAGINA, "offset": (pagina - 1) * POR_PAGINA}
            try:
                r = cliente.get(BASE + ruta, params=params)
            except httpx.HTTPError as error:
                print(f"  {ruta}: {type(error).__name__}")
                break
            print(f"  {ruta} página {pagina} → HTTP {r.status_code}")
            if r.status_code != 200 or "json" not in r.headers.get("content-type", ""):
                break
            datos = r.json()
            lote = datos.get(clave) or []
            todos += lote
            total = datos.get("total") or (datos.get("meta") or {}).get("total_count") or 0
            if not lote or len(todos) >= total:
                break
            pagina += 1
        if todos:
            print(f"  → {len(todos)} recursos desde {ruta} (total publicado {total})")
            print(f"  claves de un recurso: {sorted(todos[0].keys())}")
            return todos
    return []


def capas_wfs(cliente: httpx.Client) -> dict[str, dict]:
    r = cliente.get(OWS, params={"service": "WFS", "version": "1.1.0", "request": "GetCapabilities"})
    print(f"  WFS GetCapabilities → HTTP {r.status_code}, {len(r.content)} bytes")
    capas = {}
    for ft in ET.fromstring(r.content).iter():
        if _local(ft.tag) != "FeatureType":
            continue
        d = {}
        for hijo in ft:
            nombre = _local(hijo.tag)
            if nombre in ("Name", "Title", "Abstract", "DefaultSRS"):
                d[nombre] = (hijo.text or "").strip()
            elif nombre == "WGS84BoundingBox":
                esq = {_local(e.tag): e.text for e in hijo}
                d["caja"] = [float(x) for x in (esq.get("LowerCorner", "") + " " + esq.get("UpperCorner", "")).split()]
        capas[d.get("Name", "")] = d
    return capas


def capas_wcs(cliente: httpx.Client) -> dict[str, dict]:
    r = cliente.get(OWS, params={"service": "WCS", "version": "1.0.0", "request": "GetCapabilities"})
    print(f"  WCS GetCapabilities → HTTP {r.status_code}, {len(r.content)} bytes")
    capas = {}
    try:
        raiz = ET.fromstring(r.content)
    except ET.ParseError:
        return capas
    for cov in raiz.iter():
        if _local(cov.tag) != "CoverageOfferingBrief":
            continue
        d = {}
        for hijo in cov:
            nombre = _local(hijo.tag)
            if nombre in ("name", "label", "description"):
                d[nombre] = (hijo.text or "").strip()
            elif nombre == "lonLatEnvelope":
                pos = [p.text for p in hijo if _local(p.tag) == "pos"]
                d["caja"] = [float(x) for p in pos for x in p.split()]
        capas[d.get("name", "")] = d
    return capas


def toca_caja(caja: list[float] | None, lon: float, lat: float) -> bool | None:
    if not caja or len(caja) != 4:
        return None
    return caja[0] <= lon <= caja[2] and caja[1] <= lat <= caja[3]


def geometria_de(cliente: httpx.Client, capa: str, url: str = OWS) -> tuple[str | None, list[str]]:
    r = cliente.get(url, params={"service": "WFS", "version": "1.1.0", "request": "DescribeFeatureType",
                                 "typeName": capa})
    if r.status_code != 200:
        return None, []
    try:
        raiz = ET.fromstring(r.content)
    except ET.ParseError:
        return None, []
    geom, campos = None, []
    for e in raiz.iter():
        if _local(e.tag) == "element" and e.get("name") and e.get("type"):
            tipo = e.get("type").rsplit(":", 1)[-1]
            if "Geometry" in tipo or "Polygon" in tipo or "Point" in tipo or "Line" in tipo:
                geom = e.get("name")
            else:
                campos.append(e.get("name"))
    return geom, campos


def en_el_lote(cliente: httpx.Client, url: str, capa: str, geom: str, campos: list[str],
               poligono: list[tuple[float, float]]) -> dict:
    """Unidades de la capa que tocan el lote (sin traer geometrías) y los atributos de la primera."""
    wkt = "POLYGON((" + ", ".join(f"{lon} {lat}" for lon, lat in poligono) + "))"
    params = {"service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": capa,
              "outputFormat": "application/json", "maxFeatures": 5, "srsName": "EPSG:4326",
              "CQL_FILTER": f"INTERSECTS({geom}, {wkt})"}
    r = None
    for intento in ([campos[:60]] if campos else []) + [None]:
        if intento:
            params["propertyName"] = ",".join(intento)
        else:
            params.pop("propertyName", None)
        r = cliente.get(url, params=params)
        if r.status_code == 200 and "json" in r.headers.get("content-type", ""):
            elementos = r.json().get("features", [])
            return {"estado": "WFS ok", "unidades": len(elementos),
                    "atributos": [e.get("properties") for e in elementos][:3] or None}
    return {"estado": f"WFS HTTP {r.status_code}", "detalle": corto(r.text[-600:], 600)}


def pixel_en(cliente: httpx.Client, url: str, capa: str, lon: float, lat: float) -> dict:
    """Valor del ráster en el centro del lote (WMS GetFeatureInfo)."""
    d = 0.001
    r = cliente.get(url, params={"service": "WMS", "version": "1.1.1", "request": "GetFeatureInfo", "layers": capa,
                                 "query_layers": capa, "styles": "", "srs": "EPSG:4326",
                                 "bbox": f"{lon - d},{lat - d},{lon + d},{lat + d}", "width": 101, "height": 101,
                                 "x": 50, "y": 50, "info_format": "application/json", "feature_count": 3})
    if r.status_code != 200 or "json" not in r.headers.get("content-type", ""):
        return {"estado": f"WMS HTTP {r.status_code}", "detalle": corto(r.text, 300)}
    elementos = r.json().get("features", [])
    return {"estado": "WMS ok", "unidades": len(elementos),
            "atributos": [e.get("properties") for e in elementos][:3] or None}


def leyenda(cliente: httpx.Client, url: str, capa: str) -> list | None:
    """Clases de la leyenda publicada (valor → etiqueta), para traducir el código del píxel."""
    try:
        r = cliente.get(url, params={"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic",
                                     "layer": capa, "format": "application/json"})
        if r.status_code != 200 or "json" not in r.headers.get("content-type", ""):
            return None
        out = []
        for capa_ in r.json().get("Legend", []):
            for regla in capa_.get("rules", []):
                for simb in regla.get("symbolizers", []):
                    mapa = (simb.get("Raster") or {}).get("colormap") or {}
                    for e in mapa.get("entries", []):
                        out.append([e.get("quantity"), e.get("label")])
                if regla.get("title") or regla.get("name"):
                    out.append([regla.get("filter"), regla.get("title") or regla.get("name")])
        return out[:80] or None
    except (httpx.HTTPError, ValueError):
        return None


def servicios(rec: dict) -> dict[str, tuple[str, str]]:
    """Servicios OGC que publica el catálogo para el recurso: tipo → (url, nombre de la capa)."""
    out = {}
    for enlace in rec.get("links") or []:
        tipo = enlace.get("link_type") or ""
        if tipo.startswith("OGC:") and enlace.get("url"):
            out.setdefault(tipo, (enlace["url"].split("?")[0], enlace.get("name") or rec.get("alternate") or ""))
    return out


_WMS: dict[str, dict[str, str]] = {}
_CANDADO = threading.Lock()


def capas_wms(cliente: httpx.Client, url: str) -> dict[str, str]:
    """Nombre → título de las capas que publica un servidor WMS (una sola consulta por servidor)."""
    with _CANDADO:
        if url not in _WMS:
            capas = {}
            try:
                r = cliente.get(url, params={"service": "WMS", "version": "1.1.1", "request": "GetCapabilities"})
                print(f"  WMS GetCapabilities {url} → HTTP {r.status_code}, {len(r.content)} bytes")
                for capa in ET.fromstring(r.content).iter():
                    if _local(capa.tag) == "Layer":
                        d = {_local(h.tag): (h.text or "").strip() for h in capa if _local(h.tag) in ("Name", "Title")}
                        if d.get("Name"):
                            capas[d["Name"]] = d.get("Title", "")
            except (httpx.HTTPError, ET.ParseError) as error:
                print(f"  WMS GetCapabilities {url} → {type(error).__name__}")
            _WMS[url] = capas
        return _WMS[url]


def nombre_en(capas: dict[str, str], alternate: str, titulo: str) -> str | None:
    """Nombre real de la capa en ese servidor: por nombre, por nombre sin espacio de trabajo o por título."""
    if alternate in capas:
        return alternate
    corto_ = alternate.split(":", 1)[-1]
    for n in capas:
        if n.split(":", 1)[-1] == corto_:
            return n
    for n, t in capas.items():
        if t and titulo and t.strip().lower() == titulo.strip().lower():
            return n
    return None


def caja_de(geojson) -> list[float] | None:
    if isinstance(geojson, dict) and geojson.get("coordinates"):
        xs = [p[0] for anillo in geojson["coordinates"] for p in anillo]
        ys = [p[1] for anillo in geojson["coordinates"] for p in anillo]
        return [min(xs), min(ys), max(xs), max(ys)]
    return None


def corto(texto, n: int = 140) -> str:
    texto = " ".join(str(texto or "").split())
    return texto if len(texto) <= n else texto[: n - 1] + "…"


# Anexo de geoservicios (spec 021): nodos que publica https://geo.inta.gob.ar/geoservicios/
PAGINA_GEOSERVICIOS = "https://geo.inta.gob.ar/geoservicios/"
NODOS = {"Nacional": "https://geo-backend.inta.gob.ar/geoserver",
         "La Pampa - San Luis (nodo 15)": "https://geo-nodo15.inta.gob.ar/geoserver",
         "nodo 05 (textura y pH)": "https://geo-nodo05.inta.gob.ar/geoserver"}
# capas aprobadas por Hernán (prioridad 1 y 2), con el nombre verificado en el inventario
HOJAS_SAN_LUIS = ["geonode:villamercedes_v0", "geonode:sanluis_v1", "geonode:buenaesperanza_v0",
                  "geonode:villagralroca_v0", "geonode:concaran_v0_676e7dd96118736d2ea36e767bd7c7fd",
                  "geonode:loyola_varela_v0_017028c132f4111b991dff14de997fd8",
                  "geonode:arizona_v0_02d647e0a3661237e9442c9ce388df2d"]
RASTERS = {"nodo 05 (textura y pH)": ["texclass_0_15_con_mascara_a8f640b4c16411b2c134d1de0a29cc79",
                                      "texclass_30_60_con_mascara_9654064cf709638813faeb3a54f6e9e1",
                                      "ph_0_30_nuevo_recorte_m_4d4cbbd459875375ae3e856e2870841f"],
           "Nacional": ["mnc_verano2024_f300268fd112b0ec3ef5f731edb78882", "mnc_2018_2019_V1R1", "MNC_invierno2022"]}


def _caps(cliente: httpx.Client, url: str, servicio: str, version: str) -> tuple[str, list[str], list[str]]:
    """Estado, versiones y nombres de capas de un GetCapabilities."""
    try:
        r = cliente.get(url, params={"service": servicio, "version": version, "request": "GetCapabilities"})
    except httpx.HTTPError as error:
        return type(error).__name__, [], []
    try:
        raiz = ET.fromstring(r.content)
    except ET.ParseError:
        return f"HTTP {r.status_code}, no es XML", [], []
    etiqueta = {"WMS": "Layer", "WFS": "FeatureType", "WCS": "CoverageOfferingBrief"}[servicio]
    nombres = []
    for e in raiz.iter():
        if _local(e.tag) == etiqueta:
            for h in e:
                if _local(h.tag) in ("Name", "name") and h.text:
                    nombres.append(h.text.strip())
                    break
    formatos = sorted({(h.text or "").strip() for h in raiz.iter() if _local(h.tag) in ("Format", "formats")
                       and h.text and len(h.text) < 60})[:12]
    return f"HTTP {r.status_code}, versión {raiz.get('version')}", nombres, formatos


def geoservicios(cliente: httpx.Client, poligono: list[tuple[float, float]]) -> None:
    print("\n6. Geoservicios del INTA (anexo de la spec 021)\n")
    try:
        r = cliente.get(PAGINA_GEOSERVICIOS)
        nodos = sorted(set(re.findall(r"https?://[\w.-]*inta\.gob\.ar/geoserver/(?:wms|wfs|wcs)", r.text)))
        print(f"  {PAGINA_GEOSERVICIOS} → HTTP {r.status_code}; {len(nodos)} URL de servicios publicadas:")
        for u in nodos:
            print(f"    {u}")
    except httpx.HTTPError as error:
        print(f"  {PAGINA_GEOSERVICIOS} → {type(error).__name__}")
    capas = {}
    for nodo, base in NODOS.items():
        for servicio, version in (("WMS", "1.1.1"), ("WFS", "1.1.0"), ("WCS", "1.0.0")):
            url = f"{base}/{servicio.lower()}"
            estado, nombres, formatos = _caps(cliente, url, servicio, version)
            capas[(nodo, servicio)] = nombres
            print(f"  {nodo} · {servicio} {url} → {estado}; {len(nombres)} capas; formatos {formatos}")
    wkt = "POLYGON((" + ", ".join(f"{lon} {lat}" for lon, lat in poligono) + "))"
    print("\n  Hojas de suelo de San Luis 1:100.000 en el nodo 15:")
    wfs15 = f"{NODOS['La Pampa - San Luis (nodo 15)']}/wfs"
    for hoja in HOJAS_SAN_LUIS:
        en_wfs = hoja in capas[("La Pampa - San Luis (nodo 15)", "WFS")]
        linea = f"    {hoja}: WFS {'sí' if en_wfs else 'no'}"
        if en_wfs:
            geom, campos = geometria_de(cliente, hoja, wfs15)
            linea += f" · geometría {geom} · atributos {campos}"
            if geom and hoja.endswith("villamercedes_v0"):
                linea += f" · en el lote {en_el_lote(cliente, wfs15, hoja, geom, campos, poligono)}"
        print(linea)
    print(f"  (filtro usado: INTERSECTS(geom, {wkt[:60]}…))")
    print("\n  Rásters aprobados por WCS (DescribeCoverage):")
    for nodo, coberturas in RASTERS.items():
        url = f"{NODOS[nodo]}/wcs"
        for cob in coberturas:
            nombre = next((n for n in capas[(nodo, "WCS")] if n.split(":", 1)[-1] == cob), None)
            if not nombre:
                print(f"    {nodo} · {cob}: no está en el WCS")
                continue
            try:
                r = cliente.get(url, params={"service": "WCS", "version": "1.0.0", "request": "DescribeCoverage",
                                             "coverage": nombre})
                raiz = ET.fromstring(r.content)
                datos = {k: [(e.text or "").strip() for e in raiz.iter() if _local(e.tag) == k][:3]
                         for k in ("offsetVector", "low", "high", "requestResponseCRSs", "nativeCRSs", "formats",
                                   "interpolationMethod", "nullValues", "singleValue")}
                print(f"    {nodo} · {nombre}: " + json.dumps(datos, ensure_ascii=False))
            except (httpx.HTTPError, ET.ParseError) as error:
                print(f"    {nodo} · {nombre}: {type(error).__name__}")


def main() -> int:
    poligono = esquinas(sys.argv[1] if len(sys.argv) > 1 else
                        "-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300")
    lon_c = sum(p[0] for p in poligono[:-1]) / (len(poligono) - 1)
    lat_c = sum(p[1] for p in poligono[:-1]) / (len(poligono) - 1)
    print(f"Lote: centro {lat_c:.4f}, {lon_c:.4f}\n")
    inicio = time.monotonic()
    with httpx.Client(timeout=90, follow_redirects=True, headers={"User-Agent": "Rotaterra/0.1 (Earth2Worlds)"}) as c:
        print("1. Catálogo")
        cat = recursos(c)
        print("2. Servicios OGC")
        wfs = capas_wfs(c)
        wcs = capas_wcs(c)
        print(f"  {len(wfs)} capas WFS, {len(wcs)} coberturas WCS")

        print("3. ¿Qué recursos tienen dato en el lote?")
        muestra = {}
        for rec in cat:
            muestra.setdefault(rec.get("subtype") or rec.get("resource_type"),
                               [e for e in rec.get("links") or [] if (e.get("link_type") or "").startswith("OGC:")])
        for tipo, enlaces in muestra.items():
            print(f"  enlaces OGC de un recurso '{tipo}': " + corto(json.dumps(enlaces, ensure_ascii=False), 1200))

        def revisar(rec: dict) -> tuple[str, dict]:
            pk = str(rec.get("pk"))
            alt = rec.get("alternate") or ""
            serv = servicios(rec)
            if toca_caja(caja_de(rec.get("ll_bbox_polygon")), lon_c, lat_c) is False:
                return pk, {"estado": "fuera de su extensión", "unidades": 0, "servicios": list(serv)}
            res = {"servicios": {k: v[0] for k, v in serv.items()}}
            try:
                url_wms = serv.get("OGC:WMS", (None, None))[0]
                capa = nombre_en(capas_wms(c, url_wms), alt, rec.get("title") or "") if url_wms else None
                res["capa_en_servidor"] = capa
                url_wfs = serv.get("OGC:WFS", (None, None))[0]
                if url_wfs and capa:
                    geom, campos = geometria_de(c, capa, url_wfs)
                    res["wfs"] = en_el_lote(c, url_wfs, capa, geom, campos, poligono) if geom \
                        else {"estado": "WFS sin geometría"}
                if url_wms and capa and "wfs" not in res:
                    res["wms"] = pixel_en(c, url_wms, capa, lon_c, lat_c)
                    if rec.get("subtype") in ("raster", "remote"):
                        res["leyenda"] = leyenda(c, url_wms, capa)
                if url_wms and not capa:
                    res["wms"] = {"estado": "capa no publicada en el WMS"}
            except httpx.HTTPError as error:
                res["error"] = type(error).__name__
            return pk, res

        candidatos = [r for r in cat if (r.get("subtype") or r.get("resource_type")) in ("vector", "raster", "remote")]
        with ThreadPoolExecutor(HILOS) as pool:
            cobertura = dict(pool.map(revisar, candidatos))

    filas = []
    for rec in cat:
        alt = rec.get("alternate") or rec.get("typename") or ""
        nombre_ows = alt if alt in wfs else (alt.split(":", 1)[-1] if alt.split(":", 1)[-1] in wcs else alt)
        cob = cobertura.get(str(rec.get("pk")))
        filas.append({
            "dataset_id": rec.get("pk") or rec.get("id"),
            "capa": alt,
            "nombre": rec.get("title"),
            "descripcion": corto(rec.get("abstract") or rec.get("raw_abstract"), 400),
            "organismo": ((rec.get("owner") or {}).get("organization") if isinstance(rec.get("owner"), dict) else None)
                         or ((rec.get("group") or {}).get("name") if isinstance(rec.get("group"), dict) else None),
            "tipo": rec.get("subtype") or rec.get("resource_type") or rec.get("storeType"),
            "categoria": (rec.get("category") or {}).get("identifier") if isinstance(rec.get("category"), dict) else rec.get("category"),
            "fecha": rec.get("date"), "tipo_fecha": rec.get("date_type"),
            "extension": rec.get("extent") or rec.get("ll_bbox_polygon") or rec.get("bbox_polygon"),
            "srid": rec.get("srid"),
            "palabras": [k.get("name") if isinstance(k, dict) else k for k in (rec.get("keywords") or [])][:12],
            "regiones": [k.get("name") if isinstance(k, dict) else k for k in (rec.get("regions") or [])][:8],
            "calidad_datos": corto(rec.get("data_quality_statement") or rec.get("raw_data_quality_statement"), 300),
            "info_suplementaria": corto(rec.get("supplemental_information") or rec.get("raw_supplemental_information"), 300),
            "publicado": rec.get("is_published"),
            "wfs": alt in wfs, "wcs": nombre_ows in wcs,
            "cobertura_lote": cob,
        })
    # capas OGC que no aparecen en el catálogo
    en_catalogo = {f["capa"] for f in filas}
    for nombre, d in wfs.items():
        if nombre not in en_catalogo:
            filas.append({"dataset_id": None, "capa": nombre, "nombre": d.get("Title"), "descripcion": corto(d.get("Abstract"), 400),
                          "tipo": "vector (solo WFS)", "wfs": True, "wcs": False, "cobertura_lote": None})

    print(f"\n4. Inventario ({len(filas)} entradas, {time.monotonic() - inicio:.0f} s)\n")
    print("| id | nombre | tipo | fecha | WFS | WMS | dato en el lote |")
    print("|---|---|---|---|---|---|---|")

    def resumen(cob: dict | None) -> str:
        if not cob:
            return "—"
        if cob.get("estado") == "fuera de su extensión":
            return "fuera de su extensión"
        partes = []
        for k in ("wfs", "wms"):
            if k in cob:
                v = cob[k]
                partes.append(f"{v.get('estado')}: {v.get('unidades')}" if "unidades" in v else v.get("estado"))
        return "; ".join(partes) or cob.get("error") or "sin servicio OGC"

    for f in filas:
        cob = f.get("cobertura_lote") or {}
        print(f"| {f['dataset_id']} | {corto(f.get('nombre'), 70)} | {f.get('tipo')} | {str(f.get('fecha') or '')[:10]} "
              f"| {'sí' if 'OGC:WFS' in (cob.get('servicios') or {}) or f.get('wfs') else 'no'} "
              f"| {'sí' if 'OGC:WMS' in (cob.get('servicios') or {}) else 'no'} | {resumen(cob)} |")
    print("\n5. Detalle por dataset (JSON por línea)\n")
    for f in filas:
        print("DATASET " + json.dumps(f, ensure_ascii=False, default=str))
    with httpx.Client(timeout=90, follow_redirects=True, headers={"User-Agent": "Rotaterra/0.1 (Earth2Worlds)"}) as c:
        geoservicios(c, poligono)
    return 0 if filas else 1


if __name__ == "__main__":
    sys.exit(main())
