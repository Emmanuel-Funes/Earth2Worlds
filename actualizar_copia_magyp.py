"""Renueva la copia de los rindes del Ministerio que lee el conector MAGyP (spec 040). Se usa desde GitHub
(Actions → "Actualizar copia de MAGyP (rindes de referencia)"), cuando el Ministerio publica un CSV nuevo.

Sin argumento busca el CSV vigente en el portal del Ministerio y lo baja de ahí. Como ese servidor no responde
desde fuera del país (15/10/2026), si falla busca el mismo recurso en el portal nacional datos.gob.ar y baja el
mismo archivo del Ministerio guardado en el Archivo de Internet (web.archive.org). Solo esta herramienta usa esos
caminos: la app lee siempre la copia del repo. Con una URL, baja ese archivo."""

import re
import sys
import time
from datetime import date

import httpx

from rotaterra.fuentes import magyp_rindes as magyp

URL_NACIONAL = "https://datos.gob.ar/api/3/action/package_search"
URL_ARCHIVO = "https://archive.org/wayback/available"
# el último CSV conocido (investigación 033, 14/10/2026), por si ninguno de los dos portales contesta
ULTIMO_CONOCIDO = ("https://datos.magyp.gob.ar/dataset/9e1e77ba-267e-4eaa-a59f-3296e86b5f36/resource/"
                   "95d066e6-8a0f-4a80-b59d-6f28f88eacd5/download/estimaciones-agricolas-2026-03.csv")


def csv_vigente(cliente: httpx.Client) -> str:
    try:
        return magyp.buscar_csv(cliente)
    except magyp.ErrorMAGyP as error:
        print(f"El portal del Ministerio no respondió ({error}); busco el recurso en datos.gob.ar", flush=True)
    for intento in range(1, 4):
        try:
            r = cliente.get(URL_NACIONAL, params={"q": magyp.BUSQUEDA, "rows": 5})
            r.raise_for_status()
            return magyp.recurso_vigente(r.json()["result"]["results"])["url"]
        except (httpx.HTTPError, ValueError, KeyError, magyp.ErrorMAGyP) as error:
            print(f"datos.gob.ar, intento {intento}: {error}", flush=True)
            time.sleep(10 * intento)
    print(f"Ningún portal contestó; uso el último CSV conocido: {ULTIMO_CONOCIDO}", flush=True)
    return ULTIMO_CONOCIDO


def bajar(cliente: httpx.Client, url: str) -> tuple[bytes, str]:
    """(contenido, URL de la que se bajó): primero del Ministerio y, si no contesta, del Archivo de Internet."""
    try:
        r = cliente.get(url, timeout=magyp.TIEMPO_DESCARGA)
        r.raise_for_status()
        return r.content, url
    except httpx.HTTPError as error:
        if "web.archive.org" in url:
            raise
        print(f"El Ministerio no entregó el archivo ({error}); busco la copia del Archivo de Internet", flush=True)
    r = cliente.get(URL_ARCHIVO, params={"url": re.sub(r"^https?://", "", url)})
    r.raise_for_status()
    foto = (r.json().get("archived_snapshots") or {}).get("closest") or {}
    if not foto.get("available") or str(foto.get("status")) != "200":
        sys.exit(f"El Archivo de Internet no tiene una copia de {url}")
    copia = f"https://web.archive.org/web/{foto['timestamp']}id_/{url}"
    r = cliente.get(copia, timeout=magyp.TIEMPO_DESCARGA)
    r.raise_for_status()
    return r.content, copia


url = sys.argv[1].strip() if len(sys.argv) > 1 and sys.argv[1].strip() else None
cliente = magyp.nuevo_cliente()
if url is None:
    print("Buscando el CSV vigente en el portal del Ministerio…", flush=True)
    url = csv_vigente(cliente)
# la URL original del Ministerio, aunque se baje de una copia ("https://web.archive.org/web/2026…id_/https://…")
original = re.sub(r"^https?://web\.archive\.org/web/[^/]+/", "", url)
archivo = original.rsplit("/", 1)[-1]
if not archivo.lower().endswith(".csv") or "magyp.gob.ar" not in original:
    sys.exit(f"La URL no es un CSV del Ministerio de Agricultura: {url}")

print(f"Bajando {url}", flush=True)
inicio = time.time()
crudo, url = bajar(cliente, url)
print(f"Bajado de {url} · {len(crudo) / 1e6:.1f} MB · {time.time() - inicio:.0f} s")
try:
    texto = crudo.decode("utf-8-sig")
except UnicodeDecodeError:
    texto = crudo.decode("latin-1")
print("Primeras líneas:\n" + "\n".join(texto.splitlines()[:3]))

ficha = {
    "archivo": archivo,
    "url_ministerio": original,
    "bajado_de": url,
    "fecha_copia": date.today().isoformat(),
    "desde_campania": magyp.campania_texto(magyp.DESDE_COPIA),
}
guardadas = magyp.guardar_copia(texto, ficha)
print(f"\nCopia: {magyp.COPIA} · {magyp.COPIA.stat().st_size / 1e6:.2f} MB comprimida · {guardadas} filas")

copia, ficha = magyp.leer_copia()
print(f"Ficha: {ficha}")
dep = magyp.leer_departamento(copia, "74035")
dep.archivo = ficha["archivo"]
print(f"\nGeneral Pedernera (74035), última campaña del archivo termina en {dep.ultimo_anio_archivo}:")
for o in magyp.observaciones("lote-prueba", dep):
    print(f"  {o.variable:<34}{'—' if o.valor is None else int(o.valor):>7}  {o.calidad:<11}{o.fecha}  {o.nota}")
