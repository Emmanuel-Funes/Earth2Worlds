"""Prueba real contra el Catastro de San Luis (spec 025).

Se usa desde GitHub (Actions → "Probar CATASTRO_SL (límites y parcelas)").

    python probar_catastro_sl.py --fuera -33.960 -60.650    # punto sin parcela (Pergamino): tiene que volver vacío
    python probar_catastro_sl.py --exportar parcelas.geojson  # todas las parcelas rurales, para el frontend
    python probar_catastro_sl.py --explorar        # qué hay detrás del visor (sesión APEX, mapa, servicios)
"""

import html as html_lib
import re
import sys
from urllib.parse import urljoin, urlparse

import httpx

INICIO = "http://www.sistemacatastro.sanluis.gov.ar/pls/apex/f?p=VISPUB:1"
PATRON_URL = re.compile(r"""["'(]((?:https?:)?//[^"'()\s<>]{4,}|/[A-Za-z0-9_\-./]*(?:wms|wfs|ows|geoserver|arcgis|"""
                        r"""mapserv|MapServer|rest|services|Servlet|servlet|ajax|json|\.do|\.jsp|\.php|\.ashx)"""
                        r"""[^"'()\s<>]*)["')]""", re.I)
PALABRAS = re.compile(r"wms|wfs|geoserver|arcgis|mapserv|getfeature|GetFeatureInfo|identify|parcela|nomencla|"
                      r"partida|superficie|buscar|search|ajax|\$\.post|\$\.get|\$\.ajax|fetch\(|XMLHttpRequest|"
                      r"url\s*:|EPSG|proj4|TOKEN|layers?\s*:", re.I)
LIBRERIAS = ("jquery", "openlayers", "/ol.js", "ol-", "proj4", "bootstrap", "leaflet", "font", "/i/libraries/")


def contexto(texto: str, patron: re.Pattern, ancho: int = 200, maximo: int = 80) -> list[str]:
    salida, ultimo = [], -1
    for m in patron.finditer(texto):
        if m.start() < ultimo:
            continue
        salida.append(texto[max(0, m.start() - ancho): m.end() + ancho].replace("\n", " "))
        ultimo = m.end() + ancho
        if len(salida) >= maximo:
            break
    return salida


def mostrar(c: httpx.Client, url: str, profundidad: int = 0, vistos: set | None = None) -> None:
    vistos = set() if vistos is None else vistos
    if url in vistos or len(vistos) > 40:
        return
    vistos.add(url)
    print(f"\n{'=' * (3 + profundidad)} GET {url}")
    try:
        r = c.get(url)
    except Exception as error:
        print(f"  no responde: {type(error).__name__}: {error}")
        return
    tipo = r.headers.get("content-type", "")
    print(f"  HTTP {r.status_code} · {tipo} · final {r.url} · {len(r.text)} bytes · cookies {dict(c.cookies)}")
    texto = r.text
    es_html = "html" in tipo
    if es_html:
        for m in re.finditer(r"<(input|select|button|form|iframe|a)\b[^>]*>", texto):
            print("   tag:", html_lib.unescape(m.group(0))[:300])
        for m in re.finditer(r"<script(?![^>]*src)[^>]*>(.*?)</script>", texto, re.S):
            if m.group(1).strip():
                print("   script en línea >>>", m.group(1).strip()[:6000])
        print("   texto:", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>|<style.*?</style>",
                                                                              " ", texto, flags=re.S)))[:1500])
    urls = sorted({html_lib.unescape(u) for u in PATRON_URL.findall(texto)})
    for u in urls[:150]:
        print("   url:", u[:300])
    if not es_html:
        for frag in contexto(texto, PALABRAS):
            print("   …", frag[:500])
    if profundidad >= 2:
        return
    recursos = [html_lib.unescape(x) for x in
                re.findall(r"""<(?:script|iframe|frame)[^>]+src=["']([^"']+)["']""", texto)]
    for rec in recursos:
        destino = urljoin(str(r.url), rec)
        if any(x in destino.lower() for x in LIBRERIAS):
            print("   (librería, no se baja)", destino)
            continue
        mostrar(c, destino, profundidad + 1, vistos)


def visor(c: httpx.Client) -> str:
    r = c.get(INICIO)
    m = re.search(r'id="P1_CATGIS_VISUALIZADOR_URL" value="([^"]+)"', r.text)
    print(f"Sesión APEX: {r.url}")
    return html_lib.unescape(m.group(1)) if m else ""


GEOSERVER = "http://visualcatsl.dyndns.info/geoserver"
JS_PATRONES = re.compile(r"wfs\?request=GetFeature|ords/sis_catastro|obtn_capas|obtener_capas|nomencla|partida|"
                         r"superficie|parcela|CQL_FILTER|cql_filter|GetFeatureInfo|typeName", re.I)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _resumen(c: httpx.Client, etiqueta: str, params: dict, url: str = "") -> list[dict]:
    g = c.get(url or f"{GEOSERVER}/ows", params=params)
    tipo = g.headers.get("content-type") or ""
    print(f"\n   [{etiqueta}] → HTTP {g.status_code} {tipo} {len(g.content)} bytes")
    if "json" not in tipo:
        print("     ", re.sub(r"\s+", " ", g.text[:600]))
        return []
    datos = g.json()
    feats = datos.get("features", [])
    print(f"      {len(feats)} elementos · crs {datos.get('crs')}")
    for f in feats[:6]:
        geo = f.get("geometry") or {}
        coords = str(geo.get("coordinates"))
        print(f"      id {f.get('id')} · {geo.get('type')} · {len(coords)} car. · {coords[:160]}")
        for k, v in (f.get("properties") or {}).items():
            print(f"         {k} = {v!r}"[:300])
    return feats


def explorar(lat: float, lon: float) -> None:
    m = 0.0005
    caja = (lon - m, lat - m, lon + m, lat + m)
    with httpx.Client(timeout=90, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Rotaterra/0.1"}) as c:
        base = {"service": "WFS", "request": "GetFeature", "outputFormat": "application/json"}
        encontrados = {}
        for capa in ("GIS_PARCELAS_TOT_VV", "GIS_PARCELAS_RUR_VV", "GIS_PARCELAS_RUR_RANGO_VV", "GIS_PARCELAS_TOT_RUR_VV"):
            print(f"\n▸ SanLuis:{capa}")
            tn = f"SanLuis:{capa}"
            variantes = {
                "1.0.0 bbox 4326": {**base, "version": "1.0.0", "typeName": tn, "srsName": "EPSG:4326",
                                    "bbox": ",".join(map(str, caja)) + ",EPSG:4326"},
                "1.0.0 CQL BBOX 4326": {**base, "version": "1.0.0", "typeName": tn, "srsName": "EPSG:4326",
                                        "CQL_FILTER": f"BBOX(GEOM,{caja[0]},{caja[1]},{caja[2]},{caja[3]},'EPSG:4326')"},
                "1.1.0 bbox urn lat/lon": {**base, "version": "1.1.0", "typeName": tn, "srsName": "EPSG:4326",
                                           "bbox": f"{caja[1]},{caja[0]},{caja[3]},{caja[2]},urn:ogc:def:crs:EPSG::4326"},
            }
            for etiqueta, params in variantes.items():
                feats = _resumen(c, etiqueta, params)
                if feats and capa not in encontrados:
                    encontrados[capa] = feats
        tot = encontrados.get("GIS_PARCELAS_TOT_VV") or encontrados.get("GIS_PARCELAS_RUR_VV") or []
        for f in tot[:1]:
            p = f.get("properties") or {}
            nom = p.get("CATNMC_CAT")
            print(f"\n=== búsqueda por nomenclatura {nom!r} (como el visor)")
            _resumen(c, "CATNMC_CAT", {**base, "version": "1.0.0", "typeName": "SanLuis:GIS_PARCELAS_TOT_VV",
                                       "srsName": "EPSG:4326", "CQL_FILTER": f"CATNMC_CAT='{nom}'"})
            if p.get("LINK"):
                print(f"\n=== LINK {p['LINK']}")
                try:
                    r = c.get(p["LINK"])
                    print(f"   HTTP {r.status_code} {r.headers.get('content-type')}")
                    print("   ", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text))[:3000])
                except Exception as error:
                    print("   ", type(error).__name__, error)
        rango = encontrados.get("GIS_PARCELAS_RUR_RANGO_VV") or []
        for f in rango[:1]:
            padron = (f.get("properties") or {}).get("PADRON_TRI")
            print(f"\n=== búsqueda por padrón {padron!r}")
            _resumen(c, "PADRON_TRI", {**base, "version": "1.0.0", "typeName": "SanLuis:GIS_PARCELAS_RUR_RANGO_VV",
                                       "srsName": "EPSG:4326", "CQL_FILTER": f"PADRON_TRI='{padron}'"})
        print("\n=== GetFeatureInfo WMS (lo que muestra el visor al hacer clic)")
        for capa in ("GIS_PARCELAS_TOT_VV", "GIS_PARCELAS_RUR_RANGO_VV"):
            _resumen(c, f"GetFeatureInfo {capa}", {
                "SERVICE": "WMS", "VERSION": "1.1.1", "REQUEST": "GetFeatureInfo", "LAYERS": f"SanLuis:{capa}",
                "QUERY_LAYERS": f"SanLuis:{capa}", "SRS": "EPSG:4326", "BBOX": ",".join(map(str, caja)),
                "WIDTH": 101, "HEIGHT": 101, "X": 50, "Y": 50, "INFO_FORMAT": "application/json",
                "FEATURE_COUNT": 5}, url=f"{GEOSERVER}/SanLuis/wms")


def mostrar_parcela(titulo: str, p) -> None:
    print(f"\n=== {titulo}")
    for campo in ("nomenclatura_catastral", "partida_inmobiliaria", "numero_parcela", "tipo_parcela",
                  "plano_mensura", "superficie_registrada_m2", "superficie_calculada_m2", "capa", "calidad"):
        print(f"  {campo:<26} {getattr(p, campo)}")
    if p.geometria_lote:
        anillo = p.geometria_lote["coordinates"][0]
        print(f"  {'geometria_lote':<26} Polygon de {len(anillo)} vértices, primero {anillo[0]}")
    print(f"  nota: {p.nota}")


def probar(lat: float, lon: float) -> int:
    import asyncio
    import time

    from rotaterra.fuentes import catastro_sl as cat
    from rotaterra.geo import validar_poligono

    inicio = time.time()
    p = asyncio.run(cat.parcela_en_punto(lat, lon))
    mostrar_parcela(f"Parcela en ({lat}, {lon}) · {time.time() - inicio:.1f} s", p)
    if p.calidad == "descartada" or not p.geometria_lote or not p.nomenclatura_catastral:
        print("\nFALLA: el Catastro no devolvió la parcela del punto de prueba")
        return 1
    validar_poligono(p.geometria_lote)
    errores = 0
    for titulo, coro in (("Misma parcela por nomenclatura", cat.parcela_por_nomenclatura(p.nomenclatura_catastral)),
                         ("Misma parcela por partida", cat.parcela_por_partida(p.partida_inmobiliaria or "x"))):
        inicio = time.time()
        q = asyncio.run(coro)
        mostrar_parcela(f"{titulo} · {time.time() - inicio:.1f} s", q)
        if q.nomenclatura_catastral != p.nomenclatura_catastral:
            print(f"FALLA: {titulo.lower()} no devolvió la misma parcela")
            errores += 1
    return 1 if errores else 0


def exportar(archivo: str) -> int:
    """Baja con el conector todas las parcelas rurales y las guarda en un GeoJSON para el frontend."""
    import asyncio
    import gzip
    import json
    import time

    from rotaterra.fuentes import catastro_sl as cat

    inicio = time.time()
    datos = asyncio.run(cat.parcelas_rurales())
    texto = json.dumps(datos, ensure_ascii=False, separators=(",", ":")).encode()
    with open(archivo, "wb") as salida:
        salida.write(texto)
    sin_nomenclatura = sum(1 for f in datos["features"] if not f["properties"]["nomenclatura_catastral"])
    sin_superficie = sum(1 for f in datos["features"] if f["properties"]["superficie_registrada_m2"] is None)
    sin_geometria = sum(1 for f in datos["features"] if not f["geometry"])
    print(f"\n=== Mapa completo de parcelas rurales · {time.time() - inicio:.0f} s")
    print(f"  parcelas: {datos['cantidad']}")
    print(f"  archivo: {len(texto) / 1e6:.1f} MB, comprimido {len(gzip.compress(texto, 6)) / 1e6:.1f} MB")
    print(f"  sin nomenclatura: {sin_nomenclatura} · sin superficie: {sin_superficie} · sin polígono: {sin_geometria}")
    print(f"  ejemplo: {json.dumps(datos['features'][0]['properties'], ensure_ascii=False)}")
    print(f"  nota: {datos['nota']}")
    zona = asyncio.run(cat.parcelas_rurales((-65.32, -33.72, -65.28, -33.68)))
    print(f"\n=== Zona del lote de prueba (0,04° × 0,04°): {zona['cantidad']} parcelas, truncado {zona['truncado']}")
    if datos["cantidad"] < 10_000 or sin_geometria or zona["cantidad"] == 0:
        print("FALLA: el mapa completo vino incompleto")
        return 1
    return 0


if __name__ == "__main__":
    if "--explorar" in sys.argv:
        explorar(-33.700, -65.300)
        sys.exit(0)
    if "--exportar" in sys.argv:
        sys.exit(exportar(sys.argv[sys.argv.index("--exportar") + 1]))
    if "--fuera" in sys.argv:  # un punto sin parcela tiene que volver vacío, sin inventar nada
        import asyncio

        from rotaterra.fuentes import catastro_sl as cat

        i = sys.argv.index("--fuera")
        q = asyncio.run(cat.parcela_en_punto(float(sys.argv[i + 1]), float(sys.argv[i + 2])))
        mostrar_parcela("Punto fuera de San Luis (tiene que volver vacío)", q)
        sys.exit(0 if q.calidad == "descartada" and q.geometria_lote is None else 1)
    if "--nomenclatura" in sys.argv:
        import asyncio

        from rotaterra.fuentes import catastro_sl as cat

        q = asyncio.run(cat.parcela_por_nomenclatura(sys.argv[sys.argv.index("--nomenclatura") + 1]))
        mostrar_parcela("Parcela por nomenclatura", q)
        sys.exit(1 if q.calidad == "descartada" else 0)
    sys.exit(probar(float(sys.argv[1]), float(sys.argv[2])))
