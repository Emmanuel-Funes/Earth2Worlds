"""Prueba real contra GeoINTA (cartas de suelo del INTA).

Se usa desde GitHub (Actions → "Probar GeoINTA (suelos y cultivos)").

    python probar_geointa.py "lat, lon; lat, lon; ..."     # suelo del lote con el conector
    python probar_geointa.py "..." --exigir a,b            # falla si esas variables no tienen valor
    python probar_geointa.py --explorar "lat, lon" ...     # qué ofrecen los servidores OGC del INTA en esos puntos
    python probar_geointa.py --metadatos-carbono           # qué publica el INTA de la capa de carbono 2023
"""

import sys
import time
import xml.etree.ElementTree as ET

import httpx

# servidores OGC públicos del INTA donde se buscan capas de suelo
SERVIDORES = [
    "https://geo-backend.inta.gob.ar/geoserver/ows",
    "https://geointa.inta.gob.ar/geoserver/ows",
    "http://geointa.inta.gov.ar/geoserver/ows",
]
PALABRAS = ("suelo", "carta", "edaf", "capacidad", "productiv", "aptitud", "perfil")
MARGEN = 0.002  # grados alrededor del punto para la caja de búsqueda (~200 m)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def capas_de_suelo(cliente: httpx.Client, servidor: str) -> list[tuple[str, str]]:
    r = cliente.get(servidor, params={"service": "WFS", "version": "1.1.0", "request": "GetCapabilities"})
    print(f"  GetCapabilities WFS → HTTP {r.status_code}, {len(r.content)} bytes")
    r.raise_for_status()
    raiz = ET.fromstring(r.content)
    capas = []
    for ft in raiz.iter():
        if _local(ft.tag) != "FeatureType":
            continue
        nombre = titulo = ""
        for hijo in ft:
            if _local(hijo.tag) == "Name":
                nombre = (hijo.text or "").strip()
            elif _local(hijo.tag) == "Title":
                titulo = (hijo.text or "").strip()
        capas.append((nombre, titulo))
    print(f"  {len(capas)} capas WFS en total")
    return [(n, t) for n, t in capas if any(p in f"{n} {t}".lower() for p in PALABRAS)]


def atributos(cliente: httpx.Client, servidor: str, capa: str) -> list[str]:
    r = cliente.get(servidor, params={"service": "WFS", "version": "1.1.0", "request": "DescribeFeatureType",
                                      "typeName": capa})
    if r.status_code != 200:
        return [f"(DescribeFeatureType HTTP {r.status_code})"]
    try:
        raiz = ET.fromstring(r.content)
    except ET.ParseError:
        return ["(DescribeFeatureType ilegible)"]
    return [f"{e.get('name')}:{(e.get('type') or '').rsplit(':', 1)[-1]}"
            for e in raiz.iter() if _local(e.tag) == "element" and e.get("name") and e.get("type")]


def en_el_punto(cliente: httpx.Client, servidor: str, capa: str, lat: float, lon: float) -> None:
    caja = f"{lon - MARGEN},{lat - MARGEN},{lon + MARGEN},{lat + MARGEN}"
    r = cliente.get(servidor, params={"service": "WFS", "version": "1.0.0", "request": "GetFeature",
                                      "typeName": capa, "outputFormat": "application/json", "maxFeatures": 3,
                                      "srsName": "EPSG:4326", "bbox": caja})
    if r.status_code != 200 or "json" not in r.headers.get("content-type", ""):
        print(f"      GetFeature HTTP {r.status_code} {r.headers.get('content-type', '')}: {r.text[:300]!r}")
        return
    datos = r.json()
    elementos = datos.get("features", [])
    print(f"      {len(elementos)} elementos en ({lat}, {lon}) · crs {datos.get('crs')}")
    for e in elementos:
        geometria = e.get("geometry") or {}
        print(f"      · id {e.get('id')} · geometría {geometria.get('type')}")
        for clave, valor in (e.get("properties") or {}).items():
            print(f"          {clave} = {valor!r}"[:220])


def explorar(puntos: list[tuple[float, float]]) -> None:
    with httpx.Client(timeout=90, follow_redirects=True, headers={"User-Agent": "Rotaterra/0.1"}) as cliente:
        for servidor in SERVIDORES:
            print(f"\n=== {servidor}")
            try:
                capas = capas_de_suelo(cliente, servidor)
            except Exception as error:
                print(f"  no responde: {type(error).__name__}: {str(error)[:200]}")
                continue
            for nombre, titulo in capas:
                print(f"\n  ▸ {nombre} — {titulo}")
                try:
                    print(f"    atributos: {', '.join(atributos(cliente, servidor, nombre))}"[:1500])
                    for lat, lon in puntos:
                        en_el_punto(cliente, servidor, nombre, lat, lon)
                except Exception as error:
                    print(f"    error: {type(error).__name__}: {str(error)[:200]}")


CATALOGO = "https://geo-backend.inta.gob.ar/api/v2"


def metadatos_carbono() -> None:
    """Lo que publica el INTA de la capa de carbono 2023 (spec 021, §23.6): unidad, fecha, licencia, píxel y leyenda."""
    import html
    import re

    from rotaterra.fuentes.geointa import COBERTURA_COS, URL_WCS, URL_WMS

    with httpx.Client(timeout=90, follow_redirects=True, headers={"User-Agent": "Rotaterra/0.1"}) as cliente:
        for id_ in (487, 752):  # el dataset y el documento con la descarga del ráster
            try:
                r = cliente.get(f"{CATALOGO}/resources/{id_}")
                rec = r.json().get("resource") or {}
            except Exception as error:  # noqa: BLE001 — diagnóstico: se sigue con lo demás
                print(f"\n--- recurso {id_}: {type(error).__name__}: {error}")
                continue
            print(f"\n--- recurso {id_} ({rec.get('resource_type')}): {rec.get('title')}")
            for campo in ("date", "date_type", "alternate", "edition", "raw_purpose", "raw_data_quality_statement",
                          "raw_constraints_other", "download_url"):
                if rec.get(campo):
                    print(f"    {campo}: {html.unescape(str(rec.get(campo)))[:400]}")
            resumen = html.unescape(rec.get("raw_abstract") or "")
            # las frases del resumen que hablan de unidad, profundidad, validación o incertidumbre
            for frase in re.split(r"(?<=[.)])\s+", resumen):
                if re.search(r"t/ha|Mg|kg/m|cm\b|RMSE|R2|R²|incertidumbre|validaci", frase):
                    print(f"    resumen: {frase.strip()[:600]}")
        try:
            r = cliente.get(URL_WCS, params={"service": "WCS", "version": "2.0.1", "request": "DescribeCoverage",
                                             "coverageId": COBERTURA_COS.replace(":", "__")})
            for etiqueta in ("gml:name", "gml:offsetVector", "swe:uom"):
                print(f"\n--- DescribeCoverage {etiqueta}: {re.findall(f'<{etiqueta}[^>]*>[^<]*', r.text)}"[:600])
            r = cliente.get(URL_WMS, params={"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic",
                                             "layer": COBERTURA_COS, "format": "application/json"})
            entradas = r.json()["Legend"][0]["rules"][0]["symbolizers"][0]["Raster"]["colormap"]["entries"]
            print(f"--- leyenda: {[(e.get('quantity'), e.get('label')) for e in entradas]}")
        except Exception as error:  # noqa: BLE001
            print(f"    WCS/WMS: {type(error).__name__}: {str(error)[:300]}")


def _puntos(textos: list[str]) -> list[tuple[float, float]]:
    puntos = []
    for texto in textos:
        for par in texto.split(";"):
            if par.strip():
                lat, lon = (float(x) for x in par.split(","))
                puntos.append((lat, lon))
    return puntos


if __name__ == "__main__":
    if sys.argv[1:2] == ["--explorar"]:
        explorar(_puntos(sys.argv[2:]))
        sys.exit(0)
    if sys.argv[1:2] == ["--metadatos-carbono"]:
        metadatos_carbono()
        sys.exit(0)

    from rotaterra.fuentes.geointa import obtener_suelo
    from rotaterra.geo import poligono_desde_esquinas

    inicio = time.time()
    obs = obtener_suelo("lote-prueba", poligono_desde_esquinas(sys.argv[1]))
    print(f"\nSuelo y cultivos del lote (GeoINTA) · {time.time() - inicio:.0f} s\n")
    print(f"{'Variable':<38}{'Valor':>7}  {'Unidad':<30} {'Calidad':<11}")
    for o in obs:
        valor = "—" if o.valor is None else f"{o.valor:g}"
        print(f"{o.variable:<38}{valor:>7}  {o.unidad:<30} {o.calidad:<11} {o.fecha}")
    for o in obs:
        print(f"\n{o.variable}: {o.nota}")
    exigidas = sys.argv[sys.argv.index("--exigir") + 1].split(",") if "--exigir" in sys.argv else []
    # una variable exigida falla si ninguna de sus observaciones trae valor (la historia de cultivos tiene varias)
    con_valor = {o.variable for o in obs if o.valor is not None}
    faltan = [v for v in exigidas if v not in con_valor] or (["todas"] if not con_valor else [])
    if faltan:
        print(f"\nFALLA: sin valor en {', '.join(faltan)}")
        sys.exit(1)
