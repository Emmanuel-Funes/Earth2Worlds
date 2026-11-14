"""Conector clima de la campaña con NASA POWER (spec 034).

Una climatología del lote para el motor de recomendación: días libres de heladas, fechas de helada con riesgo,
lluvia esperada de octubre a marzo, grados-día y la fecha en que el suelo pasa los 14 °C. Sale de 35 años de
POWER (API diaria por punto, sin cuenta) en el centro del lote. Es un dato REGIONAL: la celda de POWER es de ~0,5°.

Respaldo: la temperatura horaria a 2 m de MERRA-2 (M2T1NXSLV) por el servicio de series de tiempo de Giovanni
(GES DISC, NASA), con el token de Earthdata.
Solo da heladas y grados-día; la lluvia y el suelo quedan sin respaldo (spec 034 §2).
"""

import re
import statistics
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import httpx
from fastapi import APIRouter, HTTPException

from rotaterra.contrato import Observacion
from rotaterra.fuentes import earthdata
from rotaterra.fuentes.registro import Satelite

URL_POWER = "https://power.larc.nasa.gov/api/temporal/daily/point"
URL_SERIES = "https://api.giovanni.earthdata.nasa.gov/timeseries"
VARIABLE_MERRA2 = "M2T1NXSLV_5_12_4_T2M"
RESOLUCION_M = 55000  # celda de ~0,5°: dato regional
ANIOS = 35
PRIMER_ANIO_SUELO = 2001  # TSOIL1 de POWER arranca en 2001
UMBRAL_HELADA = 0.0  # aprobado por Hernán (el conservador); -2 °C va en la nota
UMBRAL_HELADA_SUAVE = -2.0
UMBRALES_SUELO = (10.0, 14.0)
DIAS_SUELO = 10
MIN_CAMPANAS = 20
UMBRAL_CALOR = 35.0  # máxima del aire que daña la floración (spec 034, parte B)
UMBRAL_EXTREMA = 50.0
UMBRAL_DIA_SECO = 1.0
ANIOS_TENDENCIA = 10  # primeros contra últimos 10 años del período
MAX_FALTANTES = 0.05
DIA_DEL_ANIO = "día del año"
REGIONAL = "dato REGIONAL de la celda de ~0,5° de POWER, no del lote"
_LINEA_SERIE = re.compile(r"^(\d{4}-\d{2}-\d{2})[T ](\d{2})[^,\s]*[,\s]+(-?[\d.]+(?:[eE][-+]?\d+)?)\s*$")


class ErrorClimaCampana(Exception):
    """POWER o MERRA-2 no respondieron o respondieron algo ilegible."""


def validar_punto(lat: float, lon: float) -> None:
    if not -90 <= lat <= 90:
        raise ValueError(f"Latitud fuera de rango: {lat}")
    if not -180 <= lon <= 180:
        raise ValueError(f"Longitud fuera de rango: {lon}")


def periodo(hoy: date | None = None) -> tuple[date, date]:
    """Los 35 años completos más recientes: hoy, en 2026, de 1991 a 2025."""
    hoy = hoy or date.today()
    hasta = date(hoy.year - 1, 12, 31)
    return date(hasta.year - ANIOS + 1, 1, 1), hasta


def percentil(valores: list[float], p: float) -> float:
    """Percentil con interpolación lineal (el mismo método que la investigación 033)."""
    ordenados = sorted(valores)
    k = (len(ordenados) - 1) * p / 100
    piso = int(k)
    techo = min(piso + 1, len(ordenados) - 1)
    return ordenados[piso] + (ordenados[techo] - ordenados[piso]) * (k - piso)


def dia_del_anio(dia: date) -> int:
    return (dia - date(dia.year, 1, 1)).days + 1


def dd_mm(numero: float) -> str:
    """Día del año como fecha corta, en un año no bisiesto (250 → 07/09)."""
    return (date(2001, 1, 1) + timedelta(days=round(numero) - 1)).strftime("%d/%m")


def _dias(desde: date, hasta: date) -> list[date]:
    return [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]


# ---------- cálculos (sin red) ----------

def heladas(tmin: dict[date, float | None], primer_anio: int, ultimo_anio: int, umbral: float) -> dict:
    """Última helada de primavera, primera de otoño y días libres de cada campaña (julio a junio).

    Una campaña con más del 5 % de días sin dato no cuenta. Sin helada en un semestre se usa el borde
    (1/7 o 30/6) y se cuenta cuántas veces pasó, para decirlo en la nota.
    """
    ultimas, primeras, libres, sin_helada = [], [], [], 0
    for anio in range(primer_anio, ultimo_anio):
        temporada = _dias(date(anio, 7, 1), date(anio + 1, 6, 30))
        valores = [tmin.get(d) for d in temporada]
        if sum(v is None for v in valores) > MAX_FALTANTES * len(temporada):
            continue
        primavera = [d for d, v in zip(temporada, valores) if v is not None and d.year == anio and v <= umbral]
        otonio = [d for d, v in zip(temporada, valores) if v is not None and d.year == anio + 1 and v <= umbral]
        ultima = max(primavera) if primavera else date(anio, 7, 1)
        primera = min(otonio) if otonio else date(anio + 1, 6, 30)
        sin_helada += (not primavera) + (not otonio)
        ultimas.append(dia_del_anio(ultima))
        primeras.append(dia_del_anio(primera))
        libres.append((primera - ultima).days - 1)
    return {"ultimas": ultimas, "primeras": primeras, "libres": libres, "sin_helada": sin_helada}


def sumas_de_campana(tmin: dict[date, float | None], tmax: dict[date, float | None],
                     lluvia: dict[date, float | None] | None, primer_anio: int, ultimo_anio: int) -> dict:
    """Lluvia y grados-día base 10 °C de octubre a marzo. Una suma necesita la campaña completa:
    un día faltante la achicaría sin avisar."""
    lluvias, grados = [], []
    for anio in range(primer_anio, ultimo_anio):
        dias = _dias(date(anio, 10, 1), date(anio + 1, 3, 31))
        tn, tx = [tmin.get(d) for d in dias], [tmax.get(d) for d in dias]
        if None not in tn and None not in tx:
            grados.append(sum(max(0.0, (a + b) / 2 - 10) for a, b in zip(tx, tn)))
        if lluvia is not None:
            p = [lluvia.get(d) for d in dias]
            if None not in p:
                lluvias.append(sum(p))
    return {"lluvias": lluvias, "grados": grados}


def fechas_de_suelo(tsuelo: dict[date, float | None], primer_anio: int, ultimo_anio: int,
                    umbral: float) -> list[int]:
    """Primer día desde el 15/7 en que el suelo queda 10 días seguidos ≥ umbral (un día sin dato corta la racha)."""
    fechas = []
    for anio in range(primer_anio, ultimo_anio + 1):
        for i in range(150):
            inicio = date(anio, 7, 15) + timedelta(days=i)
            ventana = [tsuelo.get(inicio + timedelta(days=k)) for k in range(DIAS_SUELO)]
            if None not in ventana and min(ventana) >= umbral:
                fechas.append(dia_del_anio(inicio))
                break
    return fechas


def extremos(tmax: dict[date, float | None], lluvia: dict[date, float | None] | None, primer_anio: int,
             ultimo_anio: int) -> dict[str, list[tuple[int, float]]]:
    """Días de calor y de lluvia extrema por año y racha seca más larga por campaña, como (año, valor).
    Un año o una campaña con más del 5 % de días sin dato no cuenta; los días sin dato no suman."""
    salida = {"calor": [], "extrema": [], "racha": []}
    for anio in range(primer_anio, ultimo_anio + 1):
        dias = _dias(date(anio, 1, 1), date(anio, 12, 31))
        tx = [tmax.get(d) for d in dias]
        if sum(v is None for v in tx) <= MAX_FALTANTES * len(dias):
            salida["calor"].append((anio, sum(v >= UMBRAL_CALOR for v in tx if v is not None)))
        if lluvia is not None:
            p = [lluvia.get(d) for d in dias]
            if sum(v is None for v in p) <= MAX_FALTANTES * len(dias):
                salida["extrema"].append((anio, sum(v >= UMBRAL_EXTREMA for v in p if v is not None)))
            if anio < ultimo_anio:
                campana = [lluvia.get(d) for d in _dias(date(anio, 10, 1), date(anio + 1, 3, 31))]
                if None not in campana:
                    racha = maxima = 0
                    for v in campana:
                        racha = racha + 1 if v < UMBRAL_DIA_SECO else 0
                        maxima = max(maxima, racha)
                    salida["racha"].append((anio, maxima))
    return salida


def tendencia(serie: list[tuple[int, float]]) -> str:
    """Promedio de los primeros contra los últimos 10 años del período, para ver si el indicador viene subiendo."""
    if len(serie) < 2 * ANIOS_TENDENCIA:
        return ""
    primeros = [v for _, v in serie[:ANIOS_TENDENCIA]]
    ultimos = [v for _, v in serie[-ANIOS_TENDENCIA:]]
    return (f"; promedio {serie[0][0]}-{serie[ANIOS_TENDENCIA - 1][0]}: {statistics.mean(primeros):.1f}, "
            f"{serie[-ANIOS_TENDENCIA][0]}-{serie[-1][0]}: {statistics.mean(ultimos):.1f}")


# ---------- salida en el contrato común ----------

def _calidad(n: int) -> str:
    return "buena" if n >= MIN_CAMPANAS else "dudosa"


def _obs(lote_id: str, fecha: date, variable: str, unidad: str, valores: list[float], valor: float | None,
         nota: str, fuente: str, base_nota: str) -> Observacion:
    base = dict(lote_id=lote_id, fecha=fecha, variable=variable, unidad=unidad, fuente=fuente,
                resolucion_m=RESOLUCION_M)
    if not valores or valor is None:
        return Observacion(**base, valor=None, calidad="descartada", nota=f"{nota} · {base_nota}")
    return Observacion(**base, valor=round(valor), calidad=_calidad(len(valores)),
                       nota=f"{nota} · {base_nota}" + ("" if len(valores) >= MIN_CAMPANAS else
                                                       f" · solo {len(valores)} campañas (< {MIN_CAMPANAS})"))


def observaciones_heladas(lote_id: str, fecha: date, h: dict, h_suave: dict, fuente: str, base_nota: str,
                          anios: str) -> list[Observacion]:
    libres, ultimas, primeras = h["libres"], h["ultimas"], h["primeras"]
    n = len(libres)
    if not n:
        falta = "No hay ninguna campaña con datos suficientes de temperatura mínima"
        return [_obs(lote_id, fecha, v, u, [], None, falta, fuente, base_nota)
                for v, u in (("dias_libres_heladas", "días"), ("ultima_helada_primavera_p80", DIA_DEL_ANIO),
                             ("primera_helada_otono_p20", DIA_DEL_ANIO))]
    bordes = f" · en {h['sin_helada']} semestres no heló y se usó el borde (1/7 o 30/6)" if h["sin_helada"] else ""
    suave = (f" · con ≤ {UMBRAL_HELADA_SUAVE:g} °C: mediana {statistics.median(h_suave['libres']):.0f} días, "
             f"{percentil(h_suave['libres'], 20):.0f} en 8 de cada 10 años") if h_suave["libres"] else ""
    return [
        _obs(lote_id, fecha, "dias_libres_heladas", "días", libres, percentil(libres, 20),
             f"Días entre la última helada de primavera y la primera de otoño (mínima del aire a 2 m ≤ "
             f"{UMBRAL_HELADA:g} °C), superados en 8 de cada 10 años (percentil 20); mediana "
             f"{statistics.median(libres):.0f} días; {n} campañas ({anios}){suave}{bordes}", fuente, base_nota),
        _obs(lote_id, fecha, "ultima_helada_primavera_p80", DIA_DEL_ANIO, ultimas, percentil(ultimas, 80),
             f"En 8 de cada 10 años la última helada de primavera es antes del {dd_mm(percentil(ultimas, 80))}; "
             f"mediana {dd_mm(statistics.median(ultimas))}, la más tardía {dd_mm(max(ultimas))}; {n} campañas "
             f"({anios}){bordes}", fuente, base_nota),
        _obs(lote_id, fecha, "primera_helada_otono_p20", DIA_DEL_ANIO, primeras, percentil(primeras, 20),
             f"En 8 de cada 10 años la primera helada de otoño es después del {dd_mm(percentil(primeras, 20))}; "
             f"mediana {dd_mm(statistics.median(primeras))}, la más temprana {dd_mm(min(primeras))}; {n} campañas "
             f"({anios}){bordes}", fuente, base_nota),
    ]


def observaciones_grados(lote_id: str, fecha: date, grados: list[float], fuente: str, base_nota: str,
                         anios: str) -> Observacion:
    nota = (f"Grados-día base 10 °C de octubre a marzo, mediana de {len(grados)} campañas ({anios}); de "
            f"{min(grados):.0f} a {max(grados):.0f}" if grados else
            "No hay ninguna campaña completa de octubre a marzo con temperaturas")
    return _obs(lote_id, fecha, "grados_dia_campana", "°C·día", grados,
                statistics.median(grados) if grados else None, nota, fuente, base_nota)


def observaciones_lluvia(lote_id: str, fecha: date, lluvias: list[float], fuente: str, base_nota: str,
                         anios: str, falta: str = "") -> list[Observacion]:
    if not lluvias:
        falta = falta or "No hay ninguna campaña completa de octubre a marzo con lluvia"
        return [_obs(lote_id, fecha, v, "mm", [], None, falta, fuente, base_nota)
                for v in ("lluvia_campana_mm_p50", "lluvia_campana_mm_p20")]
    rango = (f"{len(lluvias)} campañas ({anios}); año húmedo (percentil 80) {percentil(lluvias, 80):.0f} mm; "
             f"de {min(lluvias):.0f} a {max(lluvias):.0f} mm; POWER subestima las tormentas, así que es un piso")
    return [
        _obs(lote_id, fecha, "lluvia_campana_mm_p50", "mm", lluvias, statistics.median(lluvias),
             f"Lluvia de octubre a marzo, mediana; {rango}", fuente, base_nota),
        _obs(lote_id, fecha, "lluvia_campana_mm_p20", "mm", lluvias, percentil(lluvias, 20),
             f"Lluvia de octubre a marzo en un año seco (1 de cada 5 años llueve menos, percentil 20); {rango}",
             fuente, base_nota),
    ]


def observacion_suelo(lote_id: str, fecha: date, tsuelo: dict[date, float | None] | None, primer_anio: int,
                      ultimo_anio: int, fuente: str, base_nota: str, sin_dato: str = "") -> Observacion:
    fechas = fechas_de_suelo(tsuelo, primer_anio, ultimo_anio, 14.0) if tsuelo else []
    if not fechas:
        return _obs(lote_id, fecha, "suelo_14c_fecha_mediana", DIA_DEL_ANIO, [], None,
                    sin_dato or "Ningún año tuvo 10 días seguidos con el suelo ≥ 14 °C", fuente, base_nota)
    diez = fechas_de_suelo(tsuelo, primer_anio, ultimo_anio, 10.0)
    extra = f"; ≥ 10 °C: mediana {dd_mm(statistics.median(diez))}" if diez else ""
    return _obs(lote_id, fecha, "suelo_14c_fecha_mediana", DIA_DEL_ANIO, fechas, statistics.median(fechas),
                f"Suelo de 0 a 10 cm (TSOIL1): primer día desde el 15/7 con {DIAS_SUELO} días seguidos ≥ 14 °C, "
                f"mediana {dd_mm(statistics.median(fechas))}; en 8 de cada 10 años antes del "
                f"{dd_mm(percentil(fechas, 80))}; {len(fechas)} años ({primer_anio}-{ultimo_anio}){extra}",
                fuente, base_nota)


def observaciones_extremos(lote_id: str, fecha: date, ext: dict, fuente: str, base_nota: str,
                           falta_lluvia: str = "") -> list[Observacion]:
    """Calor, lluvia extrema y racha seca: mediana como valor; año malo (percentil 80) y tendencia en la nota."""
    def una(variable, unidad, serie, que_es, extra=""):
        valores = [v for _, v in serie]
        if not valores:
            return _obs(lote_id, fecha, variable, unidad, [], None, falta_lluvia or f"{que_es}: sin años completos",
                        fuente, base_nota)
        nota = (f"{que_es}, mediana de {len(valores)} años ({serie[0][0]}-{serie[-1][0]}); 1 de cada 5 años "
                f"{percentil(valores, 80):.0f} o más; máximo {max(valores):.0f} en {max(serie, key=lambda s: s[1])[0]}"
                f"{tendencia(serie)}{extra}")
        return _obs(lote_id, fecha, variable, unidad, valores, statistics.median(valores), nota, fuente, base_nota)

    return [
        una("dias_calor_35_anio", "días", ext["calor"],
            f"Días por año con máxima del aire ≥ {UMBRAL_CALOR:g} °C (estrés por calor en floración)"),
        una("dias_lluvia_extrema_50_anio", "días", ext["extrema"],
            f"Días por año con lluvia ≥ {UMBRAL_EXTREMA:g} mm",
            "; POWER suaviza las tormentas en su celda de ~50 km, así que es un piso"),
        una("racha_seca_campana_dias", "días", ext["racha"],
            f"Racha más larga de días seguidos con menos de {UMBRAL_DIA_SECO:g} mm, de octubre a marzo"),
    ]


# ---------- principal: NASA POWER ----------

def serie_power(cliente: httpx.Client, lat: float, lon: float, parametros: list[str], desde: date,
                hasta: date) -> dict[str, dict[date, float | None]]:
    """Serie diaria de POWER; el relleno -999 queda como None."""
    try:
        respuesta = cliente.get(URL_POWER, params={
            "parameters": ",".join(parametros), "community": "AG", "latitude": lat, "longitude": lon,
            "start": desde.strftime("%Y%m%d"), "end": hasta.strftime("%Y%m%d"), "format": "JSON"})
        respuesta.raise_for_status()
        crudas = respuesta.json()["properties"]["parameter"]
    except (httpx.HTTPError, KeyError, ValueError) as error:
        raise ErrorClimaCampana(f"NASA POWER no devolvió {', '.join(parametros)}: {error}") from error
    series = {}
    for nombre in parametros:
        if nombre not in crudas:
            raise ErrorClimaCampana(f"NASA POWER no trajo el parámetro {nombre}")
        series[nombre] = {date(int(k[:4]), int(k[4:6]), int(k[6:8])): (None if v is None or v <= -998 else float(v))
                          for k, v in crudas[nombre].items()}
    return series


def obtener_clima_campana(lote_id: str, lat: float, lon: float, cliente: httpx.Client | None = None,
                          hoy: date | None = None) -> list[Observacion]:
    validar_punto(lat, lon)
    cliente = cliente or httpx.Client(timeout=180, follow_redirects=True)
    desde, hasta = periodo(hoy)
    aire = serie_power(cliente, lat, lon, ["T2M_MIN", "T2M_MAX", "PRECTOTCORR"], desde, hasta)
    try:  # el suelo es aparte: si falla, el resto del clima sale igual
        tsuelo = serie_power(cliente, lat, lon, ["TSOIL1"], date(max(PRIMER_ANIO_SUELO, desde.year), 1, 1),
                             hasta)["TSOIL1"]
        sin_suelo = ""
    except ErrorClimaCampana as error:
        tsuelo, sin_suelo = None, f"POWER no devolvió la temperatura del suelo: {error}"
    anios = f"{desde.year}/{(desde.year + 1) % 100:02d} a {hasta.year - 1}/{hasta.year % 100:02d}"
    base_nota = f"NASA POWER, {desde.year}-{hasta.year}, aire a 2 m · {REGIONAL}"
    h = heladas(aire["T2M_MIN"], desde.year, hasta.year, UMBRAL_HELADA)
    h_suave = heladas(aire["T2M_MIN"], desde.year, hasta.year, UMBRAL_HELADA_SUAVE)
    sumas = sumas_de_campana(aire["T2M_MIN"], aire["T2M_MAX"], aire["PRECTOTCORR"], desde.year, hasta.year)
    ext = extremos(aire["T2M_MAX"], aire["PRECTOTCORR"], desde.year, hasta.year)
    return (observaciones_heladas(lote_id, hasta, h, h_suave, "POWER", base_nota, anios)
            + observaciones_lluvia(lote_id, hasta, sumas["lluvias"], "POWER", base_nota, anios)
            + [observaciones_grados(lote_id, hasta, sumas["grados"], "POWER", base_nota, anios),
               observacion_suelo(lote_id, hasta, tsuelo, max(PRIMER_ANIO_SUELO, desde.year), hasta.year, "POWER",
                                 f"NASA POWER, suelo de 0 a 10 cm · {REGIONAL}", sin_suelo)]
            + observaciones_extremos(lote_id, hasta, ext, "POWER", base_nota))


# ---------- respaldo: MERRA-2 horario por el servicio de series de tiempo de Giovanni ----------

def leer_serie_horaria(texto: str) -> dict[date, list[float]]:
    """Temperatura horaria (K) agrupada por día UTC. Ignora encabezados y valores de relleno."""
    por_dia: dict[date, list[float]] = {}
    for linea in texto.splitlines():
        hallado = _LINEA_SERIE.match(linea.strip())
        if not hallado:
            continue
        valor = float(hallado[3])
        if not 150 <= valor <= 350:  # relleno (-9999, 1e15) o un dato imposible en Kelvin
            continue
        por_dia.setdefault(date.fromisoformat(hallado[1]), []).append(valor)
    return por_dia


def _pedir_tramo(cliente: httpx.Client, lat: float, lon: float, desde: date, hasta: date) -> str:
    respuesta = cliente.get(URL_SERIES, params={
        "data": VARIABLE_MERRA2, "location": f"[{lat},{lon}]",
        "time": f"{desde.isoformat()}T00:00:00/{hasta.isoformat()}T23:59:59"})
    respuesta.raise_for_status()
    return respuesta.text


def serie_merra2(cliente: httpx.Client, lat: float, lon: float, desde: date,
                 hasta: date) -> tuple[dict[date, float | None], dict[date, float | None]]:
    """Mínima y máxima diarias (°C) de MERRA-2, pedidas en tramos de 5 años en paralelo.
    Un día con menos de 24 horas queda sin dato."""
    tramos = [(date(a, 1, 1), min(date(a + 4, 12, 31), hasta)) for a in range(desde.year, hasta.year + 1, 5)]
    try:
        with ThreadPoolExecutor(max_workers=4) as hilos:
            textos = list(hilos.map(lambda t: _pedir_tramo(cliente, lat, lon, *t), tramos))
    except httpx.HTTPError as error:
        raise ErrorClimaCampana(f"Giovanni no devolvió la serie de MERRA-2: {error}") from error
    horas: dict[date, list[float]] = {}
    for texto in textos:
        horas.update(leer_serie_horaria(texto))
    if not horas:
        raise ErrorClimaCampana(f"Giovanni respondió sin datos de MERRA-2: {textos[0][:300]!r}")
    tmin = {d: (min(v) - 273.15 if len(v) >= 24 else None) for d, v in horas.items()}
    tmax = {d: (max(v) - 273.15 if len(v) >= 24 else None) for d, v in horas.items()}
    return tmin, tmax


def obtener_clima_campana_merra2(lote_id: str, lat: float, lon: float, cliente: httpx.Client | None = None,
                                 hoy: date | None = None) -> list[Observacion]:
    validar_punto(lat, lon)
    desde, hasta = periodo(hoy)
    try:
        cliente = earthdata.cliente_autorizado(cliente)
    except earthdata.FaltanCredenciales:
        raise
    except httpx.HTTPError as error:
        raise ErrorClimaCampana(f"Earthdata no respondió: {error}") from error
    tmin, tmax = serie_merra2(cliente, lat, lon, desde, hasta)
    anios = f"{desde.year}/{(desde.year + 1) % 100:02d} a {hasta.year - 1}/{hasta.year % 100:02d}"
    base_nota = (f"Respaldo de POWER: MERRA-2 horario (M2T1NXSLV, Giovanni), {desde.year}-{hasta.year}, "
                 f"aire a 2 m, mínima y máxima del día UTC · dato REGIONAL de la celda de MERRA-2 (~0,5°), no del lote")
    h = heladas(tmin, desde.year, hasta.year, UMBRAL_HELADA)
    h_suave = heladas(tmin, desde.year, hasta.year, UMBRAL_HELADA_SUAVE)
    grados = sumas_de_campana(tmin, tmax, None, desde.year, hasta.year)["grados"]
    sin_respaldo = "El respaldo de MERRA-2 no trae lluvia ni temperatura del suelo (spec 034 §2)"
    return (observaciones_heladas(lote_id, hasta, h, h_suave, "MERRA2", base_nota, anios)
            + observaciones_lluvia(lote_id, hasta, [], "MERRA2", base_nota, anios, sin_respaldo)
            + [observaciones_grados(lote_id, hasta, grados, "MERRA2", base_nota, anios),
               observacion_suelo(lote_id, hasta, None, desde.year, hasta.year, "MERRA2", base_nota,
                                 sin_respaldo)]
            + observaciones_extremos(lote_id, hasta, extremos(tmax, None, desde.year, hasta.year), "MERRA2",
                                     base_nota, sin_respaldo))


# ---------- conexión con el núcleo (spec 009) ----------
# Es una climatología: no usa el período del pedido, siempre los 35 años completos más recientes.

SATELITES = [
    Satelite("POWER_CAMPANA", lambda lote, desde, hasta: obtener_clima_campana(lote["id"], lote["lat"], lote["lon"])),
    Satelite("POWER_CAMPANA:MERRA2",
             lambda lote, desde, hasta: obtener_clima_campana_merra2(lote["id"], lote["lat"], lote["lon"]),
             respaldo_de="POWER_CAMPANA"),
]

router = APIRouter(tags=["Clima de la campaña (pruebas internas)"])


def _responder(funcion, lote_id: str, lat: float, lon: float) -> list[Observacion]:
    try:
        validar_punto(lat, lon)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return funcion(lote_id, lat, lon)
    except earthdata.FaltanCredenciales as error:
        raise HTTPException(status_code=503, detail=str(error))
    except (ErrorClimaCampana, earthdata.ErrorNASA) as error:
        raise HTTPException(status_code=502, detail=str(error))


@router.get("/clima-campana", response_model=list[Observacion])
def clima_campana(lat: float, lon: float, lote_id: str = "consulta") -> list[Observacion]:
    return _responder(obtener_clima_campana, lote_id, lat, lon)


@router.get("/clima-campana/merra2", response_model=list[Observacion])
def clima_campana_merra2(lat: float, lon: float, lote_id: str = "consulta") -> list[Observacion]:
    return _responder(obtener_clima_campana_merra2, lote_id, lat, lon)
