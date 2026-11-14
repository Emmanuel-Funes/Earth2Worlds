"""El Niño / La Niña de NOAA CPC como aviso de la campaña (spec 039).

Satélite independiente (spec 009): baja sus propios archivos de NOAA y no usa otros satélites.
NOAA es una de las agencias socias de la NASA permitidas (spec 008).

- Principal: el ONI (Oceanic Niño Index) de CPC, la anomalía de temperatura del mar en la región
  Niño 3.4 en trimestres móviles, más la sinopsis y el estado de alerta de la discusión mensual de ENSO.
- Respaldo: el índice Niño 3.4 mensual de NOAA PSL (ERSST, hoy V6), promediando los tres últimos meses
  publicados. Es otro servidor de NOAA.

El índice es uno solo para todo el planeta: no depende del lote. Por eso se ignoran el lugar y el
período pedidos y siempre sale el último dato publicado.
"""

from __future__ import annotations

import calendar
import html
import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import httpx
from fastapi import APIRouter, HTTPException

from rotaterra.contrato import Observacion
from rotaterra.fuentes.registro import Satelite

URL_ONI = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
URL_DISCUSION = "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml"
URL_PSL = "https://psl.noaa.gov/data/correlation/nina34.anom.data"
TIMEOUT = 30
VARIABLE = "enso_oni"
UNIDAD = "°C (anomalía)"
RESOLUCION_M = 0              # índice global: no tiene píxel
MESES_VIGENCIA = 3            # un trimestre que terminó hace más de 3 meses queda "dudoso"
FALTANTE_PSL = -99.0          # PSL marca los meses sin dato con -99.99
CIERRE = "Índice del Pacífico, no del lote."

# trimestre móvil de NOAA -> mes del medio (DJF 2026 = dic 2025, ene y feb 2026)
TRIMESTRES = {"DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6,
              "JJA": 7, "JAS": 8, "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12}
MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MESES_LARGOS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
                "octubre", "noviembre", "diciembre"]
MESES_INGLES = ["january", "february", "march", "april", "may", "june", "july", "august", "september",
                "october", "november", "december"]
# estado del sistema de alertas de ENSO de NOAA -> castellano
ALERTAS = {
    "el niño advisory": "Aviso de El Niño",
    "la niña advisory": "Aviso de La Niña",
    "el niño watch": "Vigilancia de El Niño",
    "la niña watch": "Vigilancia de La Niña",
    "final el niño advisory": "Aviso final de El Niño",
    "final la niña advisory": "Aviso final de La Niña",
    "not active": "Sin alerta",
}


class ErrorENSO(Exception):
    """NOAA no respondió o respondió algo que no se puede leer."""


# ---------- clasificación (funciones puras: el motor puede copiarlas) ----------

def redondeo_noaa(oni: float) -> float:
    """NOAA clasifica con el ONI redondeado a un decimal (0,45 -> 0,5)."""
    return float(Decimal(str(oni)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def intensidad(oni: float) -> str:
    """Intensidad por el valor absoluto: débil hasta 0,9, moderado 1,0-1,4, fuerte 1,5-1,9, muy fuerte desde 2,0."""
    absoluto = abs(redondeo_noaa(oni))
    if absoluto >= 2.0:
        return "muy fuerte"
    if absoluto >= 1.5:
        return "fuerte"
    if absoluto >= 1.0:
        return "moderado"
    return "débil"


def fase(oni: float) -> str:
    """Fase con los umbrales de NOAA: ≥ +0,5 El Niño, ≤ −0,5 La Niña; si no, neutral.

    Ejemplos: 2,16 -> "El Niño muy fuerte"; −0,6 -> "La Niña débil"; 0,3 -> "neutral".
    """
    redondeado = redondeo_noaa(oni)
    if redondeado >= 0.5:
        return f"El Niño {intensidad(oni)}"
    if redondeado <= -0.5:
        return f"La Niña {intensidad(oni).replace('moderado', 'moderada')}"
    return "neutral"


# ---------- fechas ----------

def fin_de_mes(anio: int, mes: int) -> date:
    return date(anio, mes, calendar.monthrange(anio, mes)[1])


def meses_del_trimestre(trimestre: str, anio: int) -> list[tuple[int, int]]:
    """[(año, mes), ...] de los tres meses de un trimestre de NOAA (el año es el del mes del medio)."""
    medio = TRIMESTRES[trimestre]
    meses = []
    for corrimiento in (-1, 0, 1):
        mes, a = medio + corrimiento, anio
        if mes == 0:
            mes, a = 12, anio - 1
        elif mes == 13:
            mes, a = 1, anio + 1
        meses.append((a, mes))
    return meses


def nombre_periodo(meses: list[tuple[int, int]]) -> str:
    """'jul-sep 2026', o 'dic 2025-feb 2026' si cruza el año."""
    (a1, m1), (a3, m3) = meses[0], meses[-1]
    if a1 == a3:
        return f"{MESES_CORTOS[m1 - 1]}-{MESES_CORTOS[m3 - 1]} {a3}"
    return f"{MESES_CORTOS[m1 - 1]} {a1}-{MESES_CORTOS[m3 - 1]} {a3}"


def viejo(fin: date, hoy: date) -> bool:
    """¿El dato terminó hace más de MESES_VIGENCIA meses?"""
    mes = hoy.month - MESES_VIGENCIA
    anio = hoy.year
    while mes < 1:
        mes, anio = mes + 12, anio - 1
    limite = date(anio, mes, min(hoy.day, calendar.monthrange(anio, mes)[1]))
    return fin < limite


def _signo(valor: float) -> str:
    return f"{valor:+.2f}".replace(".", ",")


# ---------- lectura de los archivos de NOAA ----------

def leer_oni(texto: str) -> tuple[str, int, float]:
    """Último trimestre publicado de oni.ascii.txt: (trimestre, año, anomalía).

    Formato: encabezado "SEAS  YR   TOTAL   ANOM" y filas como "JAS 2026   28.85   2.16".
    """
    ultimo = None
    for linea in texto.splitlines():
        partes = linea.split()
        if len(partes) < 4 or partes[0].upper() not in TRIMESTRES:
            continue
        try:
            anio, anomalia = int(partes[1]), float(partes[3])
        except ValueError:
            continue
        if anomalia <= FALTANTE_PSL:  # por si algún día NOAA marca faltantes
            continue
        ultimo = (partes[0].upper(), anio, anomalia)
    if ultimo is None:
        raise ErrorENSO(f"oni.ascii.txt no trae ningún trimestre legible (empieza con {texto[:80]!r})")
    return ultimo


def leer_psl(texto: str) -> list[tuple[int, int, float]]:
    """[(año, mes, anomalía)] de los meses publicados en el archivo de PSL, en orden.

    Formato: primera línea "1948 2026", después "AÑO v1 ... v12" (-99.99 = sin dato) y al final
    unas líneas de texto que se saltean.
    """
    meses = []
    for linea in texto.splitlines()[1:]:
        partes = linea.split()
        if len(partes) != 13:
            continue
        try:
            anio, valores = int(partes[0]), [float(v) for v in partes[1:]]
        except ValueError:
            continue
        meses += [(anio, mes, v) for mes, v in enumerate(valores, start=1) if v > FALTANTE_PSL]
    return meses


def describir_psl(texto: str) -> str:
    """Qué serie es, según el pie del archivo de PSL: "ERSST V6, anomalía frente a 1981-2010"."""
    version = re.search(r"\bERSST\s*v?\s*(\d+)", texto, re.I)
    base = re.search(r"Anomaly from\s*(\d{4})\s*-\s*(\d{4})", texto, re.I)
    partes = [f"ERSST V{version[1]}" if version else "ERSST (versión no indicada)"]
    if base:
        partes.append(f"anomalía frente a {base[1]}-{base[2]}")
    return ", ".join(partes)


def _texto_plano(pagina: str) -> str:
    """HTML -> texto, con un salto de línea por párrafo y los espacios colapsados dentro de cada línea."""
    pagina = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", pagina)
    pagina = re.sub(r"(?i)<\s*(br|p|/p|div|/div|h\d|/h\d|tr|li)\b[^>]*>", "\n\n", pagina)
    pagina = html.unescape(re.sub(r"<[^>]+>", " ", pagina)).replace("\xa0", " ")
    lineas = (re.sub(r"[ \t\r\f\v]+", " ", l).strip() for l in pagina.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lineas)).strip()


def _limpio(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()


def _mes_ingles(palabra: str) -> int | None:
    palabra = palabra.lower()
    for i, nombre in enumerate(MESES_INGLES, start=1):
        if len(palabra) >= 3 and nombre.startswith(palabra):
            return i
    return None


def leer_discusion(pagina: str) -> dict:
    """Saca de la discusión de ENSO la sinopsis, el estado de alerta y la fecha de publicación.

    Devuelve {"sinopsis", "alerta", "publicada"} (cada uno puede ser None). No traduce: solo lee.
    """
    texto = _texto_plano(pagina)
    sinopsis = re.search(r"Synopsis\s*:\s*(.+?)(?:\n\s*\n|$)", texto, re.S)
    alerta = re.search(r"ENSO Alert System Status\s*:\s*(.+?)(?:\n|Synopsis|$)", texto, re.S | re.I)
    publicada = None
    emitida = re.search(r"issued by.{0,300}?(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", texto, re.S | re.I)
    if emitida and _mes_ingles(emitida[2]):
        try:
            publicada = date(int(emitida[3]), _mes_ingles(emitida[2]), int(emitida[1]))
        except ValueError:
            publicada = None
    return {
        "sinopsis": _limpio(sinopsis[1])[:800] if sinopsis else None,
        "alerta": _limpio(alerta[1]).rstrip(".")[:80] if alerta else None,
        "publicada": publicada,
    }


def traducir_alerta(alerta: str | None) -> str | None:
    if not alerta:
        return None
    return ALERTAS.get(_limpio(alerta).lower().replace("nino", "niño").replace("nina", "niña"), alerta)


_MES = r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|" \
       r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"


def _periodos(texto: str) -> list[tuple[int, str, str]]:
    """[(posición, preposición, período)] de los períodos que nombra un texto en inglés.

    Entiende "January-March 2027" y los códigos de NOAA como "NDJ 2026". La preposición es "hasta" si
    el período va después de "through" o "until", y "para" en cualquier otro caso.
    """
    encontrados = []
    patron_rango = r"(\w+)?\s*" + _MES + r"\s*[-–]\s*" + _MES + r",?\s*(\d{4})"
    for m in re.finditer(patron_rango, texto, re.I):
        periodo = f"{MESES_CORTOS[_mes_ingles(m[2]) - 1]}-{MESES_CORTOS[_mes_ingles(m[3]) - 1]} {m[4]}"
        encontrados.append((m.start(2), m[1] or "", periodo))
    for m in re.finditer(r"(\w+)?\s*\b(" + "|".join(TRIMESTRES) + r")\s+(\d{4})\b", texto):
        encontrados.append((m.start(2), m[1] or "", nombre_periodo(meses_del_trimestre(m[2], int(m[3])))))
    return [(pos, "hasta" if previa.lower() in ("through", "until", "thru") else "para", periodo)
            for pos, previa, periodo in sorted(encontrados)]


def probabilidad(sinopsis: str | None) -> tuple[str, str | None] | None:
    """La probabilidad que da NOAA y para cuándo, si la sinopsis la dice.

    "likely through January-March 2027 (remaining greater than an 83% chance)" -> ("más de 83 %",
    "hasta ene-mar 2027"); "(55% chance)" sin período -> ("55 %", None); sin "% chance" -> None.
    Se usa el período que sigue al porcentaje y, si no hay, el último que lo precede.
    """
    if not sinopsis:
        return None
    m = re.search(r"(greater than|more than|>|about|~)?\s*(?:an?\s+)?(\d{1,3})\s*%\s*chance", sinopsis, re.I)
    if not m:
        return None
    prefijo = {"greater than": "más de ", "more than": "más de ", ">": "más de ", "about": "alrededor de ",
               "~": "alrededor de "}.get((m[1] or "").lower(), "")
    periodos = _periodos(sinopsis)
    despues = [p for p in periodos if m.end() <= p[0] <= m.end() + 60]
    antes = [p for p in periodos if p[0] < m.start()]
    elegido = despues[0] if despues else (antes[-1] if antes else None)
    return f"{prefijo}{m[2]} %", (f"{elegido[1]} {elegido[2]}" if elegido else None)


def resumen_discusion(discusion: dict | None, error: str | None = None) -> str:
    """El pronóstico de NOAA en castellano, armado con datos estructurados (no hay traductor)."""
    if not discusion or not discusion.get("sinopsis"):
        motivo = error or "la página no trae una sinopsis"
        return f"Sin pronóstico de NOAA: no se pudo leer la discusión de ENSO ({motivo})."
    partes = []
    publicada = discusion.get("publicada")
    encabezado = "NOAA CPC" + (f", discusión del {publicada.day} de {MESES_LARGOS[publicada.month - 1]} de "
                               f"{publicada.year}" if publicada else ", discusión sin fecha legible")
    alerta = traducir_alerta(discusion.get("alerta"))
    if alerta:
        partes.append(alerta)
    prob = probabilidad(discusion["sinopsis"])
    if prob:
        porcentaje, periodo = prob
        partes.append(f"probabilidad de {porcentaje}" + (f" {periodo}" if periodo else ""))
    detalle = "; ".join(partes) if partes else "sin estado de alerta legible"
    return f"{encabezado}: {detalle}. Sinopsis original: \"{discusion['sinopsis']}\""


# ---------- pedidos a NOAA ----------

def _cliente(cliente: httpx.Client | None) -> httpx.Client:
    return cliente or httpx.Client(timeout=TIMEOUT, follow_redirects=True,
                                   headers={"User-Agent": "Rotaterra/1.0 (datos agricolas)"})  # solo ASCII


def _bajar(cliente: httpx.Client, url: str, quien: str) -> str:
    try:
        respuesta = cliente.get(url, timeout=TIMEOUT)
        respuesta.raise_for_status()
    except httpx.HTTPError as error:
        raise ErrorENSO(f"{quien} no respondió: {type(error).__name__}: {error}") from error
    return respuesta.text


def bajar_discusion(cliente: httpx.Client) -> tuple[dict | None, str | None]:
    """(discusión leída, error). Nunca corta el pedido: sin discusión, el índice igual sale."""
    try:
        return leer_discusion(_bajar(cliente, URL_DISCUSION, "La discusión de ENSO de CPC")), None
    except Exception as error:
        return None, f"{type(error).__name__}: {error}"


def _observacion(lote_id: str, fin: date, valor: float | None, calidad: str, nota: str) -> Observacion:
    return Observacion(lote_id=lote_id, fecha=fin, variable=VARIABLE, valor=valor, unidad=UNIDAD, fuente="CPC",
                       resolucion_m=RESOLUCION_M, calidad=calidad, nota=nota)


def obtener_oni(lote_id: str, cliente: httpx.Client | None = None, hoy: date | None = None) -> list[Observacion]:
    """Principal: último ONI de CPC + sinopsis de la discusión. Si CPC no da el índice, lanza ErrorENSO."""
    hoy = hoy or date.today()
    cliente = _cliente(cliente)
    trimestre, anio, oni = leer_oni(_bajar(cliente, URL_ONI, "El ONI de CPC"))
    meses = meses_del_trimestre(trimestre, anio)
    fin = fin_de_mes(*meses[-1])
    discusion, error = bajar_discusion(cliente)
    calidad, aviso = "buena", ""
    if viejo(fin, hoy):
        calidad, aviso = "dudosa", f" Ojo: el último trimestre publicado terminó hace más de {MESES_VIGENCIA} meses."
    nota = (f"{fase(oni)} (ONI {nombre_periodo(meses)}: {_signo(oni)} °C, trimestre {trimestre} {anio}).{aviso} "
            f"{resumen_discusion(discusion, error)} {CIERRE}")
    return [_observacion(lote_id, fin, round(oni, 2), calidad, nota)]


def obtener_psl(lote_id: str, cliente: httpx.Client | None = None, hoy: date | None = None) -> list[Observacion]:
    """Respaldo: promedio de los tres últimos meses del Niño 3.4 de PSL. Si PSL no responde, lanza ErrorENSO."""
    hoy = hoy or date.today()
    cliente = _cliente(cliente)
    texto = _bajar(cliente, URL_PSL, "El Niño 3.4 de PSL")
    meses = leer_psl(texto)
    origen = f"Respaldo del ONI de CPC · Niño 3.4 mensual de NOAA PSL ({describir_psl(texto)}; {URL_PSL})"
    if len(meses) < 3:
        raise ErrorENSO(f"El archivo de PSL no trae meses legibles (empieza con {texto[:80]!r})")
    ultimos = meses[-3:]
    consecutivos = all(_siguiente(a, m) == (a2, m2) for (a, m, _), (a2, m2, _) in zip(ultimos, ultimos[1:]))
    fin = fin_de_mes(*ultimos[-1][:2])
    if not consecutivos:
        return [_observacion(lote_id, fin, None, "descartada",
                             f"Sin índice: los tres últimos meses publicados por PSL no son seguidos "
                             f"({', '.join(f'{m}/{a}' for a, m, _ in ultimos)}). {origen}. {CIERRE}")]
    promedio = round(sum(v for _, _, v in ultimos) / 3, 2)
    periodo = nombre_periodo([(a, m) for a, m, _ in ultimos])
    aviso = f" Ojo: el último mes publicado terminó hace más de {MESES_VIGENCIA} meses." if viejo(fin, hoy) else ""
    discusion, error = bajar_discusion(cliente)
    nota = (f"{fase(promedio)} (Niño 3.4 promedio {periodo}: {_signo(promedio)} °C; parecido al ONI pero con otra "
            f"base de anomalías).{aviso} {origen}. {resumen_discusion(discusion, error)} {CIERRE}")
    return [_observacion(lote_id, fin, promedio, "dudosa", nota)]


def _siguiente(anio: int, mes: int) -> tuple[int, int]:
    return (anio + 1, 1) if mes == 12 else (anio, mes + 1)


def obtener_enso(lote_id: str, cliente: httpx.Client | None = None, hoy: date | None = None) -> list[Observacion]:
    """CPC, y si falla, PSL. Si fallan los dos, el índice sale vacío y descartado (nunca se inventa la fase)."""
    errores = []
    for funcion in (obtener_oni, obtener_psl):
        try:
            return funcion(lote_id, cliente, hoy)
        except ErrorENSO as error:
            errores.append(str(error))
    hoy = hoy or date.today()
    return [_observacion(lote_id, hoy, None, "descartada",
                         f"Sin índice de El Niño / La Niña: {' · '.join(errores)}. {CIERRE}")]


# ---------- conexión con el núcleo (spec 009) ----------

SATELITES = [
    Satelite("NOAA_ENSO", lambda lote, desde, hasta: obtener_oni(lote["id"])),
    Satelite("NOAA_ENSO:PSL", lambda lote, desde, hasta: obtener_psl(lote["id"]), respaldo_de="NOAA_ENSO"),
]

router = APIRouter(tags=["NOAA El Niño / La Niña (pruebas internas)"])


@router.get("/enso", response_model=list[Observacion])
def enso(lote_id: str = "consulta") -> list[Observacion]:
    """Fase del Pacífico: CPC, con PSL de respaldo. No necesita lugar: el índice es global."""
    return obtener_enso(lote_id)


@router.get("/enso/psl", response_model=list[Observacion])
def enso_psl(lote_id: str = "consulta") -> list[Observacion]:
    try:
        return obtener_psl(lote_id)
    except ErrorENSO as error:
        raise HTTPException(status_code=502, detail=str(error))
