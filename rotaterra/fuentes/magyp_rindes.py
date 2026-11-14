"""Conector MAGyP: rindes de referencia del departamento (spec 040).

Las Estimaciones Agrícolas del Ministerio de Agricultura, Ganadería y Pesca (MAGyP) dan, por departamento y
por campaña, la superficie sembrada y cosechada, la producción y el rinde de cada cultivo. De ahí sale un rinde
de referencia por cultivo: la mediana de las últimas 10 campañas con rinde. Es un dato DEL DEPARTAMENTO, no del
lote: sirve para comparar cultivos y tener un orden de magnitud, no reemplaza el historial del productor.

El departamento del lote sale de la API Georef del Estado nacional (o viene en el pedido). No es una fuente de la
NASA: entra como excepción aprobada por Hernán (Georef,). No hay respaldo.

El servidor del Ministerio no responde desde fuera del país, y Render está en Estados Unidos. Por eso
la app lee una copia del CSV vigente guardada en el repo (`datos/magyp_rindes.csv.gz`, solo los cultivos del
catálogo desde 2000/01). El Ministerio publica un archivo nuevo una o dos veces por año; la copia se renueva con
el workflow "Actualizar copia de MAGyP (rindes de referencia)".
"""

import csv
import gzip
import io
import json
import math
import re
import statistics
import tempfile
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException

from rotaterra.contrato import Observacion
from rotaterra.fuentes.registro import Satelite

URL_PORTAL = "https://datos.magyp.gob.ar/api/3/action/package_search"
BUSQUEDA = "estimaciones agricolas"
URL_GEOREF = "https://apis.datos.gob.ar/georef/api/ubicacion"
CARPETA = Path(tempfile.gettempdir()) / "rotaterra-magyp"
COPIA = Path(__file__).resolve().parent / "datos" / "magyp_rindes.csv.gz"  # su ficha: magyp_rindes.json
DESDE_COPIA = 2000           # la copia guarda desde la campaña 2000/01 (de sobra para las últimas 10 con rinde)
TIEMPO = httpx.Timeout(60, connect=20)  # por pedido chico (portal y Georef); conectar no debería tardar
TIEMPO_DESCARGA = httpx.Timeout(300, connect=20)  # el CSV tiene todo el país desde 1969/70
RESOLUCION_M = 100000        # escala de departamento
CAMPANIAS = 10               # últimas campañas con rinde que entran en la mediana
MINIMO_BUENA = 5             # con menos campañas el dato sale "dudosa"
# ids del catálogo del motor (spec 027): siempre sale una observación por cada uno
CATALOGO = ["maiz", "soja", "soja_2da", "sorgo", "mani", "girasol", "trigo", "alfalfa", "algodon"]
# nombre del Ministerio (en minúsculas y sin tildes) -> id del catálogo. "soja total" no entra: mezcla primera y
# segunda, y la soja del catálogo es la de primera.
CULTIVOS = {
    "maiz": "maiz", "maiz total": "maiz",
    "soja 1ra": "soja", "soja 1a": "soja", "soja 1era": "soja", "soja primera": "soja", "soja de primera": "soja",
    "soja 2da": "soja_2da", "soja 2a": "soja_2da", "soja segunda": "soja_2da", "soja de segunda": "soja_2da",
    "sorgo": "sorgo", "sorgo granifero": "sorgo", "sorgo total": "sorgo",
    "mani": "mani", "mani total": "mani",
    "girasol": "girasol", "girasol total": "girasol",
    "trigo": "trigo", "trigo total": "trigo", "trigo pan": "trigo",
    "alfalfa": "alfalfa",
    "algodon": "algodon", "algodon total": "algodon",
}
REINTENTOS = 3              # el portal del Ministerio a veces tarda en aceptar la conexión
ENCABEZADOS = {"User-Agent": "Rotaterra/040 (rindes de referencia; github.com/hernanfirmapaz-ops/N4-4-1.2)"}
FUENTE_TEXTO = "Estimaciones Agrícolas, Ministerio de Agricultura"
_CAMPANIA = re.compile(r"(\d{4})\s*/\s*(\d{2,4})")


class ErrorMAGyP(Exception):
    """El portal del Ministerio o Georef no respondieron, o respondieron algo ilegible."""


@dataclass
class Fila:
    cultivo: str          # id del catálogo
    inicio: int           # año en que empieza la campaña (2024 para 2024/25)
    sembrada: float | None
    cosechada: float | None
    rinde: float | None


@dataclass
class Departamento:
    codigo: str                     # código del INDEC de 5 dígitos, "74035"
    nombre: str = ""
    provincia: str = ""
    filas: list[Fila] = field(default_factory=list)
    ultimo_anio_archivo: int | None = None   # año en que termina la campaña más nueva de todo el archivo
    archivo: str = ""                        # nombre del CSV del Ministerio del que salen los datos


def nuevo_cliente() -> httpx.Client:
    """Cliente con nombre propio y reintentos de conexión (el portal a veces no contesta al primer intento)."""
    return httpx.Client(timeout=TIEMPO, follow_redirects=True, headers=ENCABEZADOS,
                        transport=httpx.HTTPTransport(retries=REINTENTOS))


# ---------- texto y números del CSV ----------

def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y con un solo espacio: "Maíz " -> "maiz", "Soja 1ra." -> "soja 1ra"."""
    sin_tildes = "".join(c for c in unicodedata.normalize("NFKD", texto or "") if not unicodedata.combining(c))
    return " ".join(sin_tildes.lower().replace(".", " ").split())


def cultivo_del_catalogo(nombre: str) -> str | None:
    return CULTIVOS.get(normalizar(nombre))


def numero(texto: str | None) -> float | None:
    """Número del CSV: vacío -> None; acepta coma decimal ("2462,5") y punto de miles ("1.234,5")."""
    t = (texto or "").strip().replace(" ", "")
    if not t or t.upper() in ("NA", "N/A", "SD", "S/D", "-"):
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        valor = float(t)
    except ValueError:
        return None
    return None if math.isnan(valor) else valor


def entero(texto: str | None) -> int | None:
    valor = numero(texto)
    return None if valor is None else int(valor)


def inicio_campania(campania: str | None, anio: str | None) -> int | None:
    """Año en que empieza la campaña: "2024/25" o "2024/2025" -> 2024. Sin campaña, se usa la columna anio."""
    hallado = _CAMPANIA.search(campania or "")
    if hallado:
        return int(hallado[1])
    return entero(anio)


def campania_texto(inicio: int) -> str:
    return f"{inicio}/{(inicio + 1) % 100:02d}"


def codigo_indec(texto: str | int) -> str:
    """Código del departamento con 5 dígitos ("6007" -> "06007"). Falla si no es un código de departamento."""
    digitos = re.sub(r"\D", "", str(texto))
    if not 4 <= len(digitos) <= 5:
        raise ValueError(f"El código de departamento debe tener 5 dígitos (provincia + departamento): {texto!r}")
    return digitos.zfill(5)


def es_del_departamento(codigo: str, provincia_id: str | None, departamento_id: str | None) -> bool:
    """Compara como número: el CSV puede traer "74035", o "35" con la provincia "74" en otra columna."""
    dep = entero(departamento_id)
    if dep is None:
        return False
    if dep == int(codigo):
        return True
    prov = entero(provincia_id)
    return prov == int(codigo[:2]) and dep == int(codigo[2:])


# ---------- el departamento del lote: Georef ----------

def departamento_del_punto(lat: float, lon: float, cliente: httpx.Client) -> tuple[str, str, str]:
    """(código INDEC, departamento, provincia) del punto, según la API Georef del Estado nacional."""
    try:
        respuesta = cliente.get(URL_GEOREF, params={"lat": lat, "lon": lon}, timeout=TIEMPO)
        respuesta.raise_for_status()
        ubicacion = respuesta.json().get("ubicacion") or {}
    except (httpx.HTTPError, ValueError) as error:
        raise ErrorMAGyP(f"Georef no respondió para ({lat}, {lon}): {error}") from error
    departamento = ubicacion.get("departamento") or {}
    provincia = ubicacion.get("provincia") or {}
    if not departamento.get("id"):
        raise ErrorMAGyP(f"Georef no encontró un departamento para ({lat}, {lon}): ¿el punto está en Argentina?")
    return codigo_indec(departamento["id"]), departamento.get("nombre") or "", provincia.get("nombre") or ""


# ---------- el CSV del Ministerio ----------

def _sin_tildes_ni_espacios(texto: str) -> str:
    return normalizar(texto).replace(" ", "-")


def recurso_vigente(paquetes: list[dict]) -> dict:
    """El recurso CSV más nuevo cuyo nombre o URL dice "estimaciones-agricolas"."""
    candidatos = []
    for paquete in paquetes:
        for recurso in paquete.get("resources") or []:
            url = recurso.get("url") or ""
            texto = f"{_sin_tildes_ni_espacios(recurso.get('name') or '')} {url.lower()}"
            es_csv = (recurso.get("format") or "").strip().lower() == "csv" or url.lower().endswith(".csv")
            if es_csv and "estimaciones-agricolas" in texto:
                fecha_url = re.search(r"(\d{4})[-_](\d{2})", url.rsplit("/", 1)[-1])
                orden = (f"{fecha_url[1]}-{fecha_url[2]}" if fecha_url else "",
                         recurso.get("last_modified") or recurso.get("created") or "")
                candidatos.append((orden, recurso))
    if not candidatos:
        raise ErrorMAGyP(f"El portal del Ministerio no tiene un CSV de Estimaciones Agrícolas (búsqueda '{BUSQUEDA}')")
    return max(candidatos, key=lambda c: c[0])[1]


def buscar_csv(cliente: httpx.Client) -> str:
    """URL del CSV vigente, según la API (CKAN) del portal de datos abiertos del Ministerio."""
    try:
        respuesta = cliente.get(URL_PORTAL, params={"q": BUSQUEDA, "rows": 5}, timeout=TIEMPO)
        respuesta.raise_for_status()
        paquetes = respuesta.json()["result"]["results"]
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
        raise ErrorMAGyP(f"El portal del Ministerio no respondió la búsqueda del CSV: {error}") from error
    return recurso_vigente(paquetes)["url"]


def archivo_del_dia(cliente: httpx.Client, hoy: date | None = None) -> Path:
    """Baja el CSV vigente a la carpeta temporal; durante el mismo día se reusa el que ya se bajó."""
    hoy = hoy or date.today()
    ruta = CARPETA / f"estimaciones-agricolas-{hoy:%Y%m%d}.csv"
    if ruta.exists():
        return ruta
    url = buscar_csv(cliente)
    CARPETA.mkdir(parents=True, exist_ok=True)
    parcial = ruta.with_suffix(".parcial")
    try:
        with cliente.stream("GET", url, timeout=TIEMPO_DESCARGA) as descarga:
            descarga.raise_for_status()
            with open(parcial, "wb") as destino:
                for pedazo in descarga.iter_bytes():
                    destino.write(pedazo)
    except httpx.HTTPError as error:
        parcial.unlink(missing_ok=True)
        raise ErrorMAGyP(f"No se pudo bajar el CSV del Ministerio ({url}): {error}") from error
    for viejo in CARPETA.glob("estimaciones-agricolas-*.csv"):  # el de otro día ya no hace falta
        viejo.unlink()
    parcial.replace(ruta)
    return ruta


def texto_del_archivo(ruta: Path) -> str:
    """El CSV puede venir en UTF-8 o en Latin-1."""
    crudo = ruta.read_bytes()
    try:
        return crudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        return crudo.decode("latin-1")


def lector(texto: str) -> csv.DictReader:
    encabezado = texto.split("\n", 1)[0]
    separador = ";" if encabezado.count(";") > encabezado.count(",") else ","
    filas = csv.DictReader(io.StringIO(texto), delimiter=separador)
    filas.fieldnames = [normalizar(n).replace(" ", "_") for n in filas.fieldnames or []]
    faltan = {"cultivo", "departamento_id", "rendimiento_kgxha"} - set(filas.fieldnames)
    if faltan or not ({"campania", "anio"} & set(filas.fieldnames)):
        raise ErrorMAGyP(f"El CSV del Ministerio cambió de columnas: faltan {sorted(faltan) or ['campania/anio']} "
                         f"(tiene {filas.fieldnames})")
    return filas


# ---------- la copia del CSV que vive en el repo ----------

def armar_copia(texto: str) -> tuple[str, int]:
    """Del CSV completo del Ministerio, solo los cultivos del catálogo desde la campaña 2000/01, con las mismas
    columnas. Devuelve (texto de la copia, filas guardadas)."""
    filas = lector(texto)
    salida = io.StringIO()
    escritor = csv.DictWriter(salida, fieldnames=filas.fieldnames, lineterminator="\n", extrasaction="ignore")
    escritor.writeheader()
    guardadas = 0
    for fila in filas:
        inicio = inicio_campania(fila.get("campania"), fila.get("anio"))
        if inicio is None or inicio < DESDE_COPIA or cultivo_del_catalogo(fila.get("cultivo") or "") is None:
            continue
        escritor.writerow(fila)
        guardadas += 1
    return salida.getvalue(), guardadas


def guardar_copia(texto: str, ficha: dict, copia: Path | None = None) -> int:
    """Escribe la copia comprimida y su ficha (de qué archivo del Ministerio salió y cuándo)."""
    copia = copia or COPIA
    recorte, guardadas = armar_copia(texto)
    copia.parent.mkdir(parents=True, exist_ok=True)
    with open(copia, "wb") as destino, gzip.GzipFile(fileobj=destino, mode="wb", mtime=0) as comprimido:
        comprimido.write(recorte.encode("utf-8"))
    ficha_ruta(copia).write_text(json.dumps({**ficha, "filas": guardadas}, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
    return guardadas


def ficha_ruta(copia: Path) -> Path:
    return copia.with_name(copia.name.removesuffix(".csv.gz") + ".json")


def leer_copia(copia: Path | None = None) -> tuple[str, dict]:
    """(texto del CSV, ficha) de la copia del repo."""
    copia = copia or COPIA
    try:
        texto = gzip.decompress(copia.read_bytes()).decode("utf-8")
        ficha = json.loads(ficha_ruta(copia).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ErrorMAGyP(f"No se pudo leer la copia de los rindes del Ministerio ({copia.name}): {error}") from error
    return texto, ficha


def leer_departamento(texto: str, codigo: str) -> Departamento:
    """Las filas del departamento, con el cultivo ya pasado al catálogo del motor."""
    dep = Departamento(codigo=codigo)
    for fila in lector(texto):
        inicio = inicio_campania(fila.get("campania"), fila.get("anio"))
        if inicio is not None:
            dep.ultimo_anio_archivo = max(dep.ultimo_anio_archivo or 0, inicio + 1)
        if not es_del_departamento(codigo, fila.get("provincia_id"), fila.get("departamento_id")):
            continue
        dep.nombre = dep.nombre or (fila.get("departamento") or "").strip()
        dep.provincia = dep.provincia or (fila.get("provincia") or "").strip()
        cultivo = cultivo_del_catalogo(fila.get("cultivo") or "")
        if cultivo is None or inicio is None:
            continue
        dep.filas.append(Fila(cultivo=cultivo, inicio=inicio, sembrada=numero(fila.get("superficie_sembrada_ha")),
                              cosechada=numero(fila.get("superficie_cosechada_ha")),
                              rinde=numero(fila.get("rendimiento_kgxha"))))
    return dep


# ---------- de las filas a las observaciones ----------

def con_rinde(fila: Fila) -> bool:
    return fila.rinde is not None and fila.rinde > 0


def perdida_total(fila: Fila) -> bool:
    """Se sembró y no se cosechó nada: rinde 0 o superficie cosechada 0 (un rinde vacío solo no alcanza)."""
    return (fila.sembrada or 0) > 0 and (fila.rinde == 0 or fila.cosechada == 0)


def redondear(valor: float) -> int:
    return math.floor(valor + 0.5)


def kg(valor: float) -> str:
    return f"{redondear(valor)}" if abs(valor - round(valor)) < 1e-9 else f"{valor:g}"


def rinde_de_referencia(lote_id: str, cultivo: str, dep: Departamento) -> Observacion:
    fuente = f"{FUENTE_TEXTO}, archivo {dep.archivo}" if dep.archivo else FUENTE_TEXTO
    lugar = ", ".join(t for t in (dep.nombre, dep.provincia) if t) or f"el departamento {dep.codigo}"
    base = dict(lote_id=lote_id, variable=f"rinde_referencia_{cultivo}_kg_ha", unidad="kg/ha", fuente="MAGyP",
                resolucion_m=RESOLUCION_M)
    filas = sorted((f for f in dep.filas if f.cultivo == cultivo), key=lambda f: f.inicio)
    # una fila por campaña: si el archivo repite la campaña, vale la primera con rinde
    por_campania: dict[int, Fila] = {}
    for f in filas:
        if f.inicio not in por_campania or (con_rinde(f) and not con_rinde(por_campania[f.inicio])):
            por_campania[f.inicio] = f
    usadas = [f for _, f in sorted(por_campania.items()) if con_rinde(f)][-CAMPANIAS:]
    fecha_archivo = date(dep.ultimo_anio_archivo, 6, 30) if dep.ultimo_anio_archivo else date.today()
    if not usadas:
        motivo = "sin datos en el departamento" if not filas else "sin campañas con rinde en el departamento"
        perdidas = sum(1 for f in por_campania.values() if perdida_total(f))
        extra = f" · {perdidas} campañas con pérdida total" if perdidas else ""
        return Observacion(**base, fecha=fecha_archivo, valor=None, calidad="descartada",
                           nota=f"{motivo.capitalize()} ({lugar}, {fuente}){extra}")
    rindes = [f.rinde for f in usadas]
    primera, ultima = usadas[0].inicio, usadas[-1].inicio
    perdidas = sum(1 for inicio, f in por_campania.items() if inicio >= primera and perdida_total(f))
    nota = (f"Mediana de {len(usadas)} campañas ({campania_texto(primera)} a {campania_texto(ultima)}) en {lugar}: "
            f"de {kg(min(rindes))} a {kg(max(rindes))} kg/ha. Promedio del departamento, no del lote "
            f"({fuente}).")
    if perdidas:
        nota += f" · {perdidas} campañas con pérdida total"
    return Observacion(**base, fecha=date(ultima + 1, 6, 30), valor=redondear(statistics.median(rindes)),
                       calidad="buena" if len(usadas) >= MINIMO_BUENA else "dudosa", nota=nota)


def observaciones(lote_id: str, dep: Departamento) -> list[Observacion]:
    """Una observación por cada cultivo del catálogo, aunque el departamento no lo siembre (sale descartada)."""
    return [rinde_de_referencia(lote_id, cultivo, dep) for cultivo in CATALOGO]


def leer_rindes(lat: float, lon: float, departamento_id: str | None = None,
                cliente: httpx.Client | None = None) -> Departamento:
    """Departamento del lote (pedido o Georef) con sus filas de la copia del CSV del Ministerio."""
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError(f"Coordenadas fuera de rango: ({lat}, {lon})")
    cliente = cliente or nuevo_cliente()
    nombre = provincia = ""
    if departamento_id:
        codigo = codigo_indec(departamento_id)
    else:
        codigo, nombre, provincia = departamento_del_punto(lat, lon, cliente)
    texto, ficha = leer_copia()
    try:
        dep = leer_departamento(texto, codigo)
    except csv.Error as error:
        raise ErrorMAGyP(f"No se pudo leer la copia del CSV del Ministerio: {error}") from error
    dep.nombre, dep.provincia = dep.nombre or nombre, dep.provincia or provincia
    dep.archivo = ficha.get("archivo") or ""
    return dep


def obtener_rindes(lote_id: str, lat: float, lon: float, departamento_id: str | None = None,
                   cliente: httpx.Client | None = None) -> list[Observacion]:
    return observaciones(lote_id, leer_rindes(lat, lon, departamento_id, cliente))


# ---------- conexión con el núcleo (spec 009) ----------

SATELITES = [
    Satelite("MAGYP", lambda lote, desde, hasta: obtener_rindes(lote["id"], lote["lat"], lote["lon"],
                                                               lote.get("departamento_id"))),
]

router = APIRouter(tags=["MAGyP (pruebas internas)"])


@router.get("/rindes-referencia", response_model=list[Observacion])
def rindes_referencia(lote_id: str, lat: float, lon: float, departamento_id: str | None = None) -> list[Observacion]:
    try:
        return obtener_rindes(lote_id, lat, lon, departamento_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    except ErrorMAGyP as error:
        raise HTTPException(status_code=502, detail=str(error))
