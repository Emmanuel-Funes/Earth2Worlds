"""ET de referencia FAO-56 (Penman-Monteith) con el clima diario de NASA POWER: último respaldo de la ET (spec 019).

Es la ET de un pasto de referencia, NO la ET real del cultivo: ET cultivo = Kc × ET0 (FAO-56, capítulo 6).
"""

import math
from datetime import date

import httpx
from fastapi import APIRouter, HTTPException

from rotaterra.contrato import Observacion
from rotaterra.fuentes.registro import Satelite

URL_POWER = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMETROS = ["T2M_MAX", "T2M_MIN", "T2MDEW", "RH2M", "WS2M", "ALLSKY_SFC_SW_DWN"]
RESOLUCION_M = 55000  # grilla de ~0,5°: dato regional, no del lote
VALOR_RELLENO = -999
MAX_DIAS = 366
RANGO_ET0 = (0.0, 15.0)  # supuesto: mm/día razonables para una ET de referencia diaria

SIGMA = 4.903e-9    # constante de Stefan-Boltzmann, MJ K⁻⁴ m⁻² día⁻¹
GSC = 0.0820        # constante solar, MJ m⁻² min⁻¹
ALBEDO = 0.23       # pasto de referencia

AVISO = "ET de referencia de pasto (FAO-56 Penman-Monteith), NO es la ET real del cultivo: ET cultivo = Kc × ET0"


class ErrorET0(Exception):
    """POWER no respondió o respondió algo que no se puede leer."""


# ---------- FAO-56 (Allen et al. 1998), ecuación por ecuación ----------

def presion(altura_m: float) -> float:
    """Presión atmosférica en kPa (ec. 7)."""
    return 101.3 * ((293 - 0.0065 * altura_m) / 293) ** 5.26


def psicrometrica(presion_kpa: float) -> float:
    """Constante psicrométrica γ en kPa/°C (ec. 8)."""
    return 0.665e-3 * presion_kpa


def e_saturacion(t: float) -> float:
    """Presión de vapor de saturación e°(T) en kPa (ec. 11)."""
    return 0.6108 * math.exp(17.27 * t / (t + 237.3))


def pendiente(t: float) -> float:
    """Pendiente de la curva de presión de vapor Δ en kPa/°C (ec. 13)."""
    return 4098 * e_saturacion(t) / (t + 237.3) ** 2


def ea_rocio(t_rocio: float) -> float:
    """Presión de vapor real con el punto de rocío (ec. 14)."""
    return e_saturacion(t_rocio)


def ea_humedad_media(hr_media: float, t_max: float, t_min: float) -> float:
    """Presión de vapor real con la humedad relativa media (ec. 19)."""
    return hr_media / 100 * (e_saturacion(t_max) + e_saturacion(t_min)) / 2


def radiacion_extraterrestre(lat: float, dia_del_anio: int) -> float:
    """Ra en MJ/m²/día (ecs. 21 a 25)."""
    phi = math.radians(lat)
    dr = 1 + 0.033 * math.cos(2 * math.pi / 365 * dia_del_anio)
    delta = 0.409 * math.sin(2 * math.pi / 365 * dia_del_anio - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(delta))))
    return 24 * 60 / math.pi * GSC * dr * (ws * math.sin(phi) * math.sin(delta)
                                          + math.cos(phi) * math.cos(delta) * math.sin(ws))


def radiacion_cielo_despejado(ra: float, altura_m: float) -> float:
    """Rso en MJ/m²/día (ec. 37)."""
    return (0.75 + 2e-5 * altura_m) * ra


def onda_larga_neta(t_max: float, t_min: float, ea: float, rs: float, rso: float) -> float:
    """Rnl en MJ/m²/día (ec. 39), con Rs/Rso limitado a 1,0."""
    relativa = min(rs / rso, 1.0) if rso > 0 else 1.0
    return (SIGMA * ((t_max + 273.16) ** 4 + (t_min + 273.16) ** 4) / 2
            * (0.34 - 0.14 * math.sqrt(ea)) * (1.35 * relativa - 0.35))


def et0_fao56(t_max: float, t_min: float, ea: float, u2: float, rs: float,
              lat: float, dia_del_anio: int, altura_m: float) -> dict[str, float]:
    """ET0 diaria en mm/día (ec. 6) y los términos intermedios. G = 0 en paso diario (ec. 42)."""
    t_media = (t_max + t_min) / 2
    gamma = psicrometrica(presion(altura_m))
    es = (e_saturacion(t_max) + e_saturacion(t_min)) / 2
    delta = pendiente(t_media)
    ra = radiacion_extraterrestre(lat, dia_del_anio)
    rso = radiacion_cielo_despejado(ra, altura_m)
    rns = (1 - ALBEDO) * rs
    rnl = onda_larga_neta(t_max, t_min, ea, rs, rso)
    rn = rns - rnl
    g = 0.0
    et0 = ((0.408 * delta * (rn - g) + gamma * 900 / (t_media + 273) * u2 * (es - ea))
           / (delta + gamma * (1 + 0.34 * u2)))
    return dict(et0=et0, es=es, ea=ea, delta=delta, gamma=gamma, ra=ra, rso=rso, rns=rns, rnl=rnl, rn=rn)


# ---------- NASA POWER ----------

def validar_pedido(lat: float, lon: float, desde: date, hasta: date) -> None:
    if not -90 <= lat <= 90:
        raise ValueError(f"Latitud fuera de rango: {lat}")
    if not -180 <= lon <= 180:
        raise ValueError(f"Longitud fuera de rango: {lon}")
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise ValueError(f"El rango supera {MAX_DIAS} días")


def _falta(valor) -> bool:
    return valor is None or valor == VALOR_RELLENO


def _f(x: float, decimales: int = 1) -> str:
    return f"{x:.{decimales}f}".replace(".", ",")


def calcular_dia(lote_id: str, fecha: date, insumos: dict, lat: float, altura_m: float | None) -> Observacion:
    """Una Observacion de ET0 para un día, a partir de los parámetros de POWER de ese día."""
    base = dict(lote_id=lote_id, fecha=fecha, variable="et0_mm_dia", unidad="mm/día",
                fuente="POWER", resolucion_m=RESOLUCION_M)

    def descartada(motivo: str) -> Observacion:
        return Observacion(**base, valor=None, calidad="descartada", nota=f"{motivo} · {AVISO}")

    faltan = [p for p in ("T2M_MAX", "T2M_MIN", "WS2M", "ALLSKY_SFC_SW_DWN") if _falta(insumos.get(p))]
    if _falta(insumos.get("T2MDEW")) and _falta(insumos.get("RH2M")):
        faltan.append("T2MDEW y RH2M")
    if _falta(altura_m):
        faltan.append("elevación")
    if faltan:
        return descartada(f"POWER no tiene {', '.join(faltan)} para esta fecha (relleno -999): no se calcula la ET0")

    t_max, t_min = insumos["T2M_MAX"], insumos["T2M_MIN"]
    u2, rs = insumos["WS2M"], insumos["ALLSKY_SFC_SW_DWN"]
    if t_max < t_min:
        return descartada(f"Insumos incoherentes de POWER: T máx {_f(t_max)} °C menor que T mín {_f(t_min)} °C")
    if u2 < 0 or rs < 0:
        return descartada(f"Insumos incoherentes de POWER: viento {u2} m/s o radiación {rs} MJ/m² negativos")

    if not _falta(insumos.get("T2MDEW")):
        ea = ea_rocio(insumos["T2MDEW"])
        humedad = f"rocío {_f(insumos['T2MDEW'])} °C"
    else:
        ea = ea_humedad_media(insumos["RH2M"], t_max, t_min)
        humedad = f"HR media {_f(insumos['RH2M'], 0)} % (sin punto de rocío)"

    r = et0_fao56(t_max, t_min, ea, u2, rs, lat, fecha.timetuple().tm_yday, altura_m)
    et0 = round(r["et0"], 2)
    nota = (f"{AVISO} · NASA POWER: T {_f(t_max)}/{_f(t_min)} °C, {humedad}, viento {_f(u2)} m/s, "
            f"Rs {_f(rs)} MJ/m², altura {altura_m:.0f} m · Rn {_f(r['rn'])} MJ/m² · último respaldo de la ET")

    minimo, maximo = RANGO_ET0
    if not minimo <= et0 <= maximo:
        return Observacion(**base, valor=et0, calidad="dudosa",
                           nota=f"ET0 fuera del rango esperado ({_f(minimo, 0)} a {_f(maximo, 0)} mm/día) · {nota}")
    if r["ea"] > r["es"]:
        return Observacion(**base, valor=et0, calidad="dudosa",
                           nota=f"Humedad incoherente: ea {_f(r['ea'], 2)} kPa mayor que es {_f(r['es'], 2)} kPa · {nota}")
    return Observacion(**base, valor=et0, calidad="buena", nota=nota)


def obtener_et0(lote_id: str, lat: float, lon: float, desde: date, hasta: date,
                cliente: httpx.Client | None = None) -> list[Observacion]:
    """Pide a POWER el clima diario del punto y devuelve la ET0 FAO-56 de cada día en el contrato común."""
    validar_pedido(lat, lon, desde, hasta)
    params = {
        "parameters": ",".join(PARAMETROS),
        "community": "AG",
        "latitude": lat,
        "longitude": lon,
        "start": desde.strftime("%Y%m%d"),
        "end": hasta.strftime("%Y%m%d"),
        "format": "JSON",
    }
    cliente = cliente or httpx.Client(timeout=60)
    try:
        respuesta = cliente.get(URL_POWER, params=params)
        respuesta.raise_for_status()
        datos = respuesta.json()
        series = datos["properties"]["parameter"]
    except (httpx.HTTPError, KeyError, ValueError) as error:
        raise ErrorET0(f"No se pudo obtener el clima de NASA POWER para la ET0: {error}") from error

    coordenadas = (datos.get("geometry") or {}).get("coordinates") or []
    altura_m = coordenadas[2] if len(coordenadas) > 2 else None

    dias = sorted({d for serie in series.values() for d in serie})
    observaciones = []
    for dia in dias:
        fecha = date(int(dia[:4]), int(dia[4:6]), int(dia[6:8]))
        if not desde <= fecha <= hasta:
            continue
        insumos = {p: series.get(p, {}).get(dia) for p in PARAMETROS}
        observaciones.append(calcular_dia(lote_id, fecha, insumos, lat, altura_m))
    return observaciones


# ---------- conexión con el núcleo (spec 009) ----------

# último respaldo de la ET: ET → ECOSTRESS (orden 1) → FAO-56 con POWER (orden 2)
SATELITES = [Satelite("ET:FAO56", lambda lote, desde, hasta: obtener_et0(lote["id"], lote["lat"], lote["lon"], desde, hasta),
                      respaldo_de="ET", orden=2)]

router = APIRouter(tags=["ET de referencia FAO-56 (pruebas internas)"])


@router.get("/et0", response_model=list[Observacion])
def et0(lote_id: str, lat: float, lon: float, desde: date, hasta: date) -> list[Observacion]:
    try:
        validar_pedido(lat, lon, desde, hasta)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    try:
        return obtener_et0(lote_id, lat, lon, desde, hasta)
    except ErrorET0 as error:
        raise HTTPException(status_code=502, detail=str(error))
