"""Balance hídrico propio con NASA POWER e IMERG: respaldo del balance de SEPA (spec 024).

Un balde de 2 m por lote: entra la lluvia, sale la ET del cultivo (Kc × ET0 FAO-56, reducida por Ks cuando el
suelo se seca) y lo que sobra de la capacidad es excedente. Se resume por década, como SEPA.
La lluvia de cada día es la menor entre POWER e IMERG: POWER marca lluvias de invierno que IMERG y SEPA no ven.
Calibrado contra 87 décadas de SEPA en San Luis (spec 024): diferencia media de 16 mm.
"""

import calendar
import math
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import httpx
from fastapi import APIRouter, HTTPException

from rotaterra.contrato import Observacion
from rotaterra.fuentes import earthdata
from rotaterra.fuentes.registro import Satelite

URL_POWER = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMETROS = ["T2M_MAX", "T2M_MIN", "T2MDEW", "RH2M", "WS2M", "ALLSKY_SFC_SW_DWN", "PRECTOTCORR"]
RESOLUCION_M = 55000  # grilla de ~0,5°: dato regional, no del lote
VALOR_RELLENO = -999
MAX_DIAS = 366
ARRANQUE_DIAS = 365      # el balance arranca un año antes de `desde`
ARRANQUE_FRACCION = 0.5  # supuesto: el suelo arranca a la mitad de su capacidad
# Calibración contra 87 décadas de SEPA en San Luis (spec 024): diferencia media de 16 mm (antes 54 mm)
P_AGOTAMIENTO = 0.7      # por debajo del 30 % de la capacidad la planta transpira menos (FAO-56 tabla 22: 0,3 a 0,8)
KC_DEFECTO = 0.5         # Kc de octubre a mayo: cobertura verde parcial, como la del lote de San Luis
KC_INVIERNO = 0.5        # de junio a septiembre se consume la mitad (cultivo o pasto parado): Kc 0,25
MESES_INVIERNO = {6, 7, 8, 9}
FRACCION_RAICES = 0.7    # las raíces no exploran parejo los 2 m: se usa el 70 % del agua útil de la tabla
RANGO_KC = (0.1, 1.3)
CALIBRADO = True
AVISO_SIN_CALIBRAR = "sin calibrar todavía (spec 024)"
CALIBRACION = "calibrado contra 87 décadas de SEPA en San Luis, diferencia media 16 mm (spec 024)"

# lluvia de IMERG (núcleo `earthdata`, sin importar el satélite IMERG): Final y, si todavía no salió, Late
PRODUCTOS_IMERG = ("GPM_3IMERGDF", "GPM_3IMERGDL")
LLUVIA_MINIMA_IMERG = 0.1  # solo se le pregunta a IMERG por los días en que POWER marca lluvia
HILOS_IMERG = 12

# FAO-56 tabla 19: centro del rango de agua útil (θcc − θpmp, m³/m³), por 2.000 mm de suelo
AGUA_UTIL = {
    "arenoso": 0.08,
    "arenoso franco": 0.09,
    "franco arenoso": 0.13,
    "franco": 0.155,
    "franco limoso": 0.16,
    "limoso": 0.18,
    "franco arcillo limoso": 0.155,
    "arcillo limoso": 0.16,
    "arcilloso": 0.16,
}
TEXTURA_DEFECTO = "franco"
DIAS_RELATIVA = 365  # el % equiparado se mide contra el último año del balance
PROFUNDIDAD_MM = 2000

SIGMA = 4.903e-9    # constante de Stefan-Boltzmann, MJ K⁻⁴ m⁻² día⁻¹
GSC = 0.0820        # constante solar, MJ m⁻² min⁻¹
ALBEDO = 0.23       # pasto de referencia
KRS_INTERIOR = 0.16  # FAO-56 ec. 50, lugares del interior (no costeros)
VIENTO_DEFECTO = 2.0  # FAO-56 cap. 3: viento de 2 m/s cuando no hay dato


class ErrorBalance(Exception):
    """POWER no respondió o respondió algo que no se puede leer."""


# ---------- FAO-56 (Allen et al. 1998); mismas ecuaciones que la spec 019, sin importar ese satélite ----------

def e_saturacion(t: float) -> float:
    return 0.6108 * math.exp(17.27 * t / (t + 237.3))


def radiacion_extraterrestre(lat: float, dia_del_anio: int) -> float:
    """Ra en MJ/m²/día (ecs. 21 a 25)."""
    phi = math.radians(lat)
    dr = 1 + 0.033 * math.cos(2 * math.pi / 365 * dia_del_anio)
    decl = 0.409 * math.sin(2 * math.pi / 365 * dia_del_anio - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(decl))))
    return 24 * 60 / math.pi * GSC * dr * (ws * math.sin(phi) * math.sin(decl)
                                          + math.cos(phi) * math.cos(decl) * math.sin(ws))


def et0_fao56(t_max: float, t_min: float, ea: float, u2: float, rs: float,
              lat: float, dia_del_anio: int, altura_m: float) -> float:
    """ET0 diaria en mm/día (ec. 6), G = 0 en paso diario."""
    t_media = (t_max + t_min) / 2
    gamma = 0.665e-3 * 101.3 * ((293 - 0.0065 * altura_m) / 293) ** 5.26
    es = (e_saturacion(t_max) + e_saturacion(t_min)) / 2
    delta = 4098 * e_saturacion(t_media) / (t_media + 237.3) ** 2
    ra = radiacion_extraterrestre(lat, dia_del_anio)
    rso = (0.75 + 2e-5 * altura_m) * ra
    relativa = min(rs / rso, 1.0) if rso > 0 else 1.0
    rnl = (SIGMA * ((t_max + 273.16) ** 4 + (t_min + 273.16) ** 4) / 2
           * (0.34 - 0.14 * math.sqrt(max(ea, 0.0))) * (1.35 * relativa - 0.35))
    rn = (1 - ALBEDO) * rs - rnl
    return ((0.408 * delta * rn + gamma * 900 / (t_media + 273) * u2 * (es - ea))
            / (delta + gamma * (1 + 0.34 * u2)))


# ---------- el balance ----------

def normalizar_textura(textura: str | None) -> str | None:
    if textura is None or not textura.strip():
        return None
    sin_tildes = unicodedata.normalize("NFKD", textura).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.lower().replace("-", " ").split())


def capacidad_mm(textura: str) -> float:
    return round(AGUA_UTIL[textura] * PROFUNDIDAD_MM * FRACCION_RAICES)


def kc_del_dia(kc: float, dia: date) -> float:
    return kc * KC_INVIERNO if dia.month in MESES_INVIERNO else kc


def _falta(valor) -> bool:
    return valor is None or valor == VALOR_RELLENO


def et0_del_dia(insumos: dict, lat: float, dia: date, altura_m: float) -> tuple[float | None, list[str], list[str]]:
    """(ET0 del día, parámetros de POWER que faltan sin arreglo, datos estimados con FAO-56).

    Sin temperatura no hay ET0. Si falta otro dato, se usa el método que da FAO-56 para datos faltantes
    y el día queda marcado como estimado: radiación con Hargreaves (ec. 50), viento de 2 m/s (cap. 3)
    y humedad con el rocío igual a la mínima (ec. 48).
    """
    faltan = [p for p in ("T2M_MAX", "T2M_MIN") if _falta(insumos.get(p))]
    if faltan:
        return None, faltan, []
    t_max, t_min = insumos["T2M_MAX"], insumos["T2M_MIN"]
    if t_max < t_min:
        return None, ["T2M_MAX menor que T2M_MIN"], []
    estimados = []
    rs = insumos.get("ALLSKY_SFC_SW_DWN")
    if _falta(rs) or rs < 0:
        rs = KRS_INTERIOR * math.sqrt(t_max - t_min) * radiacion_extraterrestre(lat, dia.timetuple().tm_yday)
        estimados.append("radiación (Hargreaves, FAO-56 ec. 50)")
    u2 = insumos.get("WS2M")
    if _falta(u2) or u2 < 0:
        u2 = VIENTO_DEFECTO
        estimados.append("viento (2 m/s, FAO-56)")
    if not _falta(insumos.get("T2MDEW")):
        ea = e_saturacion(insumos["T2MDEW"])
    elif not _falta(insumos.get("RH2M")):
        ea = insumos["RH2M"] / 100 * (e_saturacion(t_max) + e_saturacion(t_min)) / 2
    else:
        ea = e_saturacion(t_min)
        estimados.append("humedad (rocío = mínima, FAO-56 ec. 48)")
    et0 = et0_fao56(t_max, t_min, ea, u2, rs, lat, dia.timetuple().tm_yday, altura_m)
    return max(0.0, et0), [], estimados


def paso_diario(agua: float, capacidad: float, lluvia: float, etc: float) -> tuple[float, float, float]:
    """Un día de balance: devuelve (agua al final del día, ETR, excedente)."""
    umbral = (1 - P_AGOTAMIENTO) * capacidad
    ks = 1.0 if agua >= umbral else agua / umbral
    etr = min(ks * etc, agua + lluvia)  # no se consume agua que no hay
    agua = agua + lluvia - etr
    excedente = max(0.0, agua - capacidad)
    return min(agua, capacidad), etr, excedente


def decadas(desde: date, hasta: date) -> list[tuple[date, date, int]]:
    """(primer día, último día, número) de cada década cuyo último día cae entre desde y hasta."""
    salida = []
    anio, mes = desde.year, desde.month
    while date(anio, mes, 1) <= hasta:
        fin_mes = calendar.monthrange(anio, mes)[1]
        for numero, (a, b) in enumerate(((1, 10), (11, 20), (21, fin_mes)), start=1):
            if desde <= date(anio, mes, b) <= hasta:
                salida.append((date(anio, mes, a), date(anio, mes, b), numero))
        anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    return salida


def _f(x: float, decimales: int = 1) -> str:
    return f"{x:.{decimales}f}".replace(".", ",")


def agua_relativa(por_dia: dict, dia: date) -> float | None:
    """Agua del día en % entre lo más seco y lo más húmedo del último año del balance (0 = lo más seco).

    Es la forma de "equiparar" fuentes que miden distinto (spec 024): se compara la forma de la curva, no los mm.
    """
    anio = [por_dia[d][0] for d in (dia - timedelta(days=i) for i in range(DIAS_RELATIVA)) if d in por_dia]
    if len(anio) < DIAS_RELATIVA or max(anio) == min(anio):
        return None
    return 100 * (por_dia[dia][0] - min(anio)) / (max(anio) - min(anio))


def balance(lote_id: str, lat: float, desde: date, hasta: date, series: dict, altura_m: float | None,
            textura: str | None = None, kc: float = KC_DEFECTO, imerg: dict | None = None) -> list[Observacion]:
    """Corre el balance día por día desde el arranque y lo resume por década.

    `imerg`: lluvia de IMERG (AAAAMMDD → mm) de los días en que POWER marca lluvia; None si IMERG no respondió.
    """
    textura_usada = textura or TEXTURA_DEFECTO
    capacidad = capacidad_mm(textura_usada)
    inicio = desde - timedelta(days=ARRANQUE_DIAS)
    calidad = "buena" if textura and CALIBRADO and imerg is not None else "dudosa"
    suelo = (f"suelo {textura_usada}, {capacidad} mm de agua útil en 2 m" if textura
             else f"sin textura del lote: se supuso {textura_usada}, {capacidad} mm de agua útil en 2 m")
    lluvia_usada = ("lluvia: la menor entre POWER (0,5°) e IMERG (0,1°) de cada día" if imerg is not None else
                    "lluvia solo de POWER porque IMERG no respondió (POWER marca lluvias de invierno que no hubo)")
    supuestos = (f"{suelo} · Kc {_f(kc)} (de junio a septiembre {_f(kc * KC_INVIERNO, 2)}) · "
                 f"arranque {ARRANQUE_FRACCION:.0%} el {inicio:%d/%m/%Y} · {lluvia_usada}; ET0 FAO-56 con POWER · "
                 + (CALIBRACION if CALIBRADO else AVISO_SIN_CALIBRAR))

    agua = ARRANQUE_FRACCION * capacidad
    por_dia: dict[date, tuple[float, float, float, float, float]] = {}  # agua, lluvia, etc, etr, excedente
    estimados_del_dia: dict[date, list[str]] = {}
    sin_imerg: set[date] = set()  # días con lluvia de POWER que IMERG no tenía: se usó la de POWER
    hueco, que_falta = (None, []) if not _falta(altura_m) else (inicio, ["elevación"])
    dia = inicio
    while hueco is None and dia <= hasta:
        clave = dia.strftime("%Y%m%d")
        insumos = {p: series.get(p, {}).get(clave) for p in PARAMETROS}
        et0, faltan, estimados = et0_del_dia(insumos, lat, dia, altura_m)
        lluvia = insumos["PRECTOTCORR"]
        if _falta(lluvia) or lluvia < 0:
            faltan.append("PRECTOTCORR")
        if faltan:
            hueco, que_falta = dia, faltan
            break
        if estimados:
            estimados_del_dia[dia] = estimados
        if imerg is not None and lluvia >= LLUVIA_MINIMA_IMERG:
            if imerg.get(clave) is None:
                sin_imerg.add(dia)
            else:
                lluvia = min(lluvia, imerg[clave])
        etc = kc_del_dia(kc, dia) * et0
        agua, etr, excedente = paso_diario(agua, capacidad, lluvia, etc)
        por_dia[dia] = (agua, lluvia, etc, etr, excedente)
        dia += timedelta(days=1)

    observaciones = []
    for primero, ultimo, numero in decadas(desde, hasta):
        base = dict(lote_id=lote_id, fecha=ultimo, fuente="POWER", resolucion_m=RESOLUCION_M)
        variables = (("agua_disponible_2m", "mm"), ("agua_suelo_porcentaje", "%"),
                     ("excedente_balance_mm", "mm"), ("confort_hidrico_balance", "%"),
                     ("agua_relativa_balance", "%"))
        if hueco is not None and hueco <= ultimo:
            motivo = (f"NASA POWER no tiene {', '.join(que_falta)} del {hueco:%d/%m/%Y} (relleno -999 o todavía sin "
                      f"publicar): el balance se corta ahí · balance propio (spec 024)")
            observaciones += [Observacion(**base, variable=v, unidad=u, valor=None, calidad="descartada", nota=motivo)
                              for v, u in variables]
            continue
        dias = [por_dia[primero + timedelta(days=i)] for i in range((ultimo - primero).days + 1)]
        agua_fin = dias[-1][0]
        lluvia, etc, etr, excedente = (sum(d[i] for d in dias) for i in (1, 2, 3, 4))
        confort = 100.0 if etc <= 0 else 100 * etr / etc
        # los días estimados de todo el balance hasta esta década (el agua de hoy arrastra los anteriores)
        con_estimados = sorted(d for d in estimados_del_dia if d <= ultimo)
        recientes = {e for d in con_estimados if d >= primero for e in estimados_del_dia[d]}
        aviso = ""
        faltan_imerg = sorted(d for d in sin_imerg if d <= ultimo)
        recientes_imerg = [d for d in faltan_imerg if d >= primero]
        if faltan_imerg:
            aviso += (f" · {len(faltan_imerg)} días con lluvia solo de POWER porque IMERG no los tenía"
                      f" (último el {faltan_imerg[-1]:%d/%m/%Y})")
        if con_estimados:
            aviso += (f" · {len(con_estimados)} días del balance con datos estimados por FAO-56 porque POWER no los tenía"
                     f" (último el {con_estimados[-1]:%d/%m/%Y}" + (f"; en esta década: {', '.join(sorted(recientes))}"
                                                                     if recientes else "") + ")")
        nota = (f"Balance propio (spec 024), respaldo de SEPA · década {numero} de {ultimo:%m/%Y}: lluvia {_f(lluvia)} mm, "
                f"ETc {_f(etc)} mm, ETR {_f(etr)} mm · {supuestos}{aviso}")
        relativa = agua_relativa(por_dia, ultimo)
        valores = (round(agua_fin, 1), round(100 * agua_fin / capacidad, 1), round(excedente, 1), round(confort, 1),
                   None if relativa is None else round(relativa, 1))
        calidad_decada = "dudosa" if recientes or recientes_imerg else calidad
        observaciones += [Observacion(**base, variable=v, unidad=u, valor=x, calidad=calidad_decada, nota=nota)
                          if x is not None else
                          Observacion(**base, variable=v, unidad=u, valor=None, calidad="descartada",
                                      nota="No hay un año completo de balance para medir el % relativo · " + nota)
                          for (v, u), x in zip(variables, valores)]
    return observaciones


# ---------- NASA POWER ----------

def validar_pedido(lat: float, lon: float, desde: date, hasta: date, textura: str | None, kc: float) -> None:
    if not -90 <= lat <= 90:
        raise ValueError(f"Latitud fuera de rango: {lat}")
    if not -180 <= lon <= 180:
        raise ValueError(f"Longitud fuera de rango: {lon}")
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise ValueError(f"El rango supera {MAX_DIAS} días")
    if textura is not None and textura not in AGUA_UTIL:
        raise ValueError(f"Textura desconocida: '{textura}'. Opciones: {', '.join(AGUA_UTIL)}")
    if not RANGO_KC[0] <= kc <= RANGO_KC[1]:
        raise ValueError(f"Kc fuera de rango ({RANGO_KC[0]} a {RANGO_KC[1]}): {kc}")


# ---------- IMERG (lluvia de 0,1°) ----------

def lluvia_imerg(lat: float, lon: float, dias: list[date], cliente: httpx.Client | None = None) -> dict[str, float] | None:
    """Lluvia diaria de IMERG (AAAAMMDD → mm) en los días pedidos; None si IMERG no responde o faltan credenciales."""
    if not dias:
        return {}
    i_lon = min(int(math.floor((lon + 180) / 0.1)), 3598)  # se piden 2 celdas, ver earthdata.leer_csv
    i_lat = min(int(math.floor((lat + 90) / 0.1)), 1798)
    try:
        cliente = earthdata.cliente_autorizado(cliente)
        url_del_dia: dict[date, str] = {}
        for producto in PRODUCTOS_IMERG:
            coleccion = earthdata.coleccion_vigente(cliente, producto)
            if coleccion:
                for dia, urls in earthdata.archivos_por_dia(cliente, coleccion, min(dias), max(dias)).items():
                    url_del_dia.setdefault(dia, urls[0])
    except (earthdata.FaltanCredenciales, earthdata.ErrorNASA, httpx.HTTPError, KeyError, ValueError):
        return None

    def leer(dia: date) -> tuple[date, float | None]:
        if dia not in url_del_dia:
            return dia, None
        try:
            datos = earthdata.leer_csv(cliente, url_del_dia[dia], f"/precipitation[0][{i_lon}][{i_lat}:1:{i_lat + 1}]")
            valor = datos["precipitation"][0][0]
        except (earthdata.ErrorNASA, httpx.HTTPError, KeyError, IndexError, ValueError):
            return dia, None
        return dia, None if valor is None or valor < 0 else valor
    with ThreadPoolExecutor(max_workers=HILOS_IMERG) as hilos:
        return {d.strftime("%Y%m%d"): v for d, v in hilos.map(leer, dias) if v is not None}


def obtener_balance(lote_id: str, lat: float, lon: float, desde: date, hasta: date, textura: str | None = None,
                    kc: float | None = None, cliente: httpx.Client | None = None,
                    leer_imerg=lluvia_imerg) -> list[Observacion]:
    """Pide a POWER el clima diario (con un año de arranque), a IMERG la lluvia de los días que POWER marca
    con lluvia, y devuelve el balance por década."""
    textura = normalizar_textura(textura)
    kc = KC_DEFECTO if kc is None else kc
    validar_pedido(lat, lon, desde, hasta, textura, kc)
    params = {
        "parameters": ",".join(PARAMETROS),
        "community": "AG",
        "latitude": lat,
        "longitude": lon,
        "start": (desde - timedelta(days=ARRANQUE_DIAS)).strftime("%Y%m%d"),
        "end": hasta.strftime("%Y%m%d"),
        "format": "JSON",
    }
    cliente = cliente or httpx.Client(timeout=120)
    try:
        respuesta = cliente.get(URL_POWER, params=params)
        respuesta.raise_for_status()
        datos = respuesta.json()
        series = datos["properties"]["parameter"]
    except (httpx.HTTPError, KeyError, ValueError) as error:
        raise ErrorBalance(f"No se pudo obtener el clima de NASA POWER para el balance: {error}") from error
    coordenadas = (datos.get("geometry") or {}).get("coordinates") or []
    altura_m = coordenadas[2] if len(coordenadas) > 2 else None
    con_lluvia = sorted(date(int(c[:4]), int(c[4:6]), int(c[6:])) for c, v in series.get("PRECTOTCORR", {}).items()
                        if v is not None and v != VALOR_RELLENO and v >= LLUVIA_MINIMA_IMERG)
    imerg = leer_imerg(lat, lon, con_lluvia)
    return balance(lote_id, lat, desde, hasta, series, altura_m, textura, kc, imerg)


# ---------- conexión con el núcleo (spec 009) ----------

def _pedir(lote: dict, desde: date, hasta: date) -> list[Observacion]:
    return obtener_balance(lote["id"], lote["lat"], lote["lon"], desde, hasta,
                           textura=lote.get("textura"), kc=lote.get("kc"))


SATELITES = [Satelite("SEPA_INTA:BALANCE", _pedir, respaldo_de="SEPA_INTA")]

router = APIRouter(tags=["Balance hídrico propio (pruebas internas)"])


@router.get("/balance-hidrico", response_model=list[Observacion])
def balance_hidrico(lote_id: str, lat: float, lon: float, desde: date, hasta: date,
                    textura: str | None = None, kc: float | None = None) -> list[Observacion]:
    try:
        validar_pedido(lat, lon, desde, hasta, normalizar_textura(textura), KC_DEFECTO if kc is None else kc)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener_balance(lote_id, lat, lon, desde, hasta, textura, kc)
    except ErrorBalance as error:
        raise HTTPException(status_code=502, detail=str(error))
