"""Clima de la campaña para el motor de rotación (spec 062, §4).

Arma los tres escenarios (año seco, medio y húmedo) a partir de la serie diaria de NASA POWER.
No consulta a la NASA: recibe el JSON que ya devolvió POWER (`temporal/daily/point`) y lo resume.

- La campaña va de mayo a abril (mes 0 = mayo).
- Año seco, medio y húmedo = campañas reales de la serie cuyo total de lluvia queda en el percentil 20, 50 y 80.
- ETo diaria por Hargreaves (FAO-56, ecuación 52), con la radiación extraterrestre de la ecuación 21.
"""

from __future__ import annotations

import calendar
import math
from datetime import date, timedelta

UMBRAL_CALOR = 35.0  # °C de máxima: período crítico de los cultivos de verano (Riglos 2023, tesis FAUBA-INTA, San Luis)
UMBRAL_VIENTO_EROSIVO = 5.0  # m/s a 2 m, umbral de RWEQ (Fryrear et al., 1998)
TB_Q_TRIGO = 4.5    # °C, temperatura base del cociente fototermal del trigo (fórmula del INTA SEPA)
MARGEN_Q = 0.5      # °C: si la temperatura media − 4,5 no supera 0,5 °C, el INTA no da el Q
Q_DIAS_ANTES, Q_DIAS_DESPUES = 20, 10  # período crítico del trigo: 20 días antes a 10 días después de la floración
MESES_CAMPANA = [5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3, 4]  # mayo a abril


POWER_DIARIO = "https://power.larc.nasa.gov/api/temporal/daily/point"


def parametros_power(lat: float, lon: float, desde: int = 1991, hasta: int = 2025) -> dict:
    """Pedido de la serie diaria de NASA POWER que usa el motor: lluvia, temperaturas, viento y ráfaga a 2 m, y temperatura
    del suelo de 0 a 10 cm (TSOIL1, MERRA-2) para el filtro térmico de siembra, y radiación global (ALLSKY_SFC_SW_DWN, MJ/m²/día
    en la comunidad AG) con temperatura media (T2M) para el cociente fototermal del trigo."""
    return {"parameters": "PRECTOTCORR,T2M_MAX,T2M_MIN,WS2M,WS2M_MAX,TSOIL1,ALLSKY_SFC_SW_DWN,T2M", "community": "AG", "longitude": lon, "latitude": lat,
            "start": f"{desde}0101", "end": f"{hasta}0430", "format": "JSON"}


def radiacion_extraterrestre(latitud: float, dia_juliano: int) -> float:
    """Ra en MJ/m²/día (FAO-56, ecuaciones 21 a 25)."""
    fi = math.radians(latitud)
    j = dia_juliano
    dr = 1 + 0.033 * math.cos(2 * math.pi * j / 365)
    delta = 0.409 * math.sin(2 * math.pi * j / 365 - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(fi) * math.tan(delta))))
    return (24 * 60 / math.pi) * 0.0820 * dr * (
        ws * math.sin(fi) * math.sin(delta) + math.cos(fi) * math.cos(delta) * math.sin(ws))


def eto_hargreaves(tmax: float, tmin: float, latitud: float, dia_juliano: int) -> float:
    """ETo en mm/día por Hargreaves (FAO-56, ecuación 52), con la máxima y la mínima del día."""
    tmedia = (tmax + tmin) / 2
    return 0.0023 * (tmedia + 17.8) * math.sqrt(max(tmax - tmin, 0.0)) * 0.408 * radiacion_extraterrestre(latitud, dia_juliano)


def cociente_fototermal(radiacion_mj: float, temp_media: float) -> float | None:
    """Q del trigo como lo publica el INTA (SEPA): radiación global (MJ/m²/día) ÷ (temperatura media − 4,5 °C).
    Sin valor si la temperatura media − 4,5 es 0,5 °C o menos."""
    termico = temp_media - TB_Q_TRIGO
    return None if termico <= MARGEN_Q else radiacion_mj / termico


def q_periodo_critico(diario: dict[date, tuple[float, float]], floracion: date) -> float | None:
    """Q del período crítico: radiación media ÷ (temperatura media − 4,5) de los 20 días antes a los 10 después de la
    floración (31 días). Hace falta dato en 24 días o más."""
    dias = [diario[d] for k in range(-Q_DIAS_ANTES, Q_DIAS_DESPUES + 1) if (d := floracion + timedelta(days=k)) in diario]
    if len(dias) < 24:
        return None
    q = cociente_fototermal(sum(r for r, _ in dias) / len(dias), sum(t for _, t in dias) / len(dias))
    return None if q is None else round(q, 2)


def _percentil_rango(valores: list[float], q: float) -> int:
    """Índice del valor en el percentil q por rango más cercano (sin interpolar: devuelve un año real)."""
    orden = sorted(range(len(valores)), key=lambda i: valores[i])
    k = max(0, min(len(orden) - 1, math.ceil(q * len(orden)) - 1))
    return orden[k]


def escenarios_desde_power(power: dict, latitud: float) -> dict:
    """Convierte el JSON DIARIO de POWER (`temporal/daily/point` con PRECTOTCORR, T2M_MAX, T2M_MIN y opcionales WS2M y WS2M_MAX)
    en el bloque `clima` del pedido. Se usa la serie diaria porque el T2M_MAX mensual de POWER es el máximo del mes,
    no el promedio de las máximas, y con él Hargreaves da de más."""
    p = power["properties"]["parameter"]
    lluvia, tmax, tmin = p["PRECTOTCORR"], p["T2M_MAX"], p["T2M_MIN"]
    viento = p.get("WS2M")
    rafaga = p.get("WS2M_MAX")
    tsuelo = p.get("TSOIL1")
    radiacion, tmedia = p.get("ALLSKY_SFC_SW_DWN"), p.get("T2M")
    diario_q: dict[date, tuple[float, float]] = {}
    mensual: dict[str, dict] = {}
    for dia, ll in lluvia.items():
        tx, tn = tmax.get(dia), tmin.get(dia)
        if ll is None or ll < 0 or tx is None or tn is None or tx < -90 or tn < -90:
            continue
        clave = dia[:6]
        fecha = date(int(dia[:4]), int(dia[4:6]), int(dia[6:]))
        m = mensual.setdefault(clave, {"lluvia": 0.0, "eto": 0.0, "dias": 0, "viento": [], "erosivos": 0, "dias_rafaga": 0,
                                       "tmin": 99.0, "dias_35": 0, "tsuelo": []})
        m["lluvia"] += ll
        m["tmin"] = min(m["tmin"], tn)
        m["dias_35"] += tx > UMBRAL_CALOR
        m["eto"] += eto_hargreaves(tx, tn, latitud, fecha.timetuple().tm_yday)
        m["dias"] += 1
        if viento and viento.get(dia) is not None and viento[dia] >= 0:
            m["viento"].append(viento[dia])
        if radiacion and radiacion.get(dia) is not None and radiacion[dia] >= 0:
            tm = tmedia.get(dia) if tmedia and tmedia.get(dia) is not None and tmedia[dia] > -90 else (tx + tn) / 2
            diario_q[fecha] = (radiacion[dia], tm)
        if tsuelo and tsuelo.get(dia) is not None and tsuelo[dia] > -90:
            m["tsuelo"].append(tsuelo[dia])
        if rafaga and rafaga.get(dia) is not None and rafaga[dia] >= 0:
            m["dias_rafaga"] += 1
            if rafaga[dia] >= UMBRAL_VIENTO_EROSIVO:
                m["erosivos"] += 1
    anios = sorted({int(k[:4]) for k in mensual})
    campanas = []
    for y in anios:
        claves = [f"{y if m >= 5 else y + 1}{m:02d}" for m in MESES_CAMPANA]
        if not all(c in mensual and mensual[c]["dias"] >= 28 for c in claves):
            continue
        # Un mes con 1 a 3 días sin dato se lleva al mes completo (lluvia y ETo proporcionales a los días con dato)
        escala = [calendar.monthrange(int(c[:4]), int(c[4:]))[1] / mensual[c]["dias"] for c in claves]
        lluvia = [mensual[c]["lluvia"] * f for c, f in zip(claves, escala)]
        # Q del trigo si florece a mediados de cada mes (el motor elige el mes de floración)
        q_mes = [q_periodo_critico(diario_q, date(int(c[:4]), int(c[4:]), 15)) for c in claves] if diario_q else None
        campanas.append({"campana": f"{y}/{str(y + 1)[2:]}", "lluvia": lluvia, "q": q_mes,
                         "tmin": [mensual[c]["tmin"] for c in claves],
                         "dias_35": [round(mensual[c]["dias_35"] * f) for c, f in zip(claves, escala)],
                         "eto": [mensual[c]["eto"] * f for c, f in zip(claves, escala)], "total": sum(lluvia)})
    if len(campanas) < 10:
        raise ValueError("La serie de POWER tiene menos de 10 campañas completas: no alcanza para los escenarios")
    totales = [c["total"] for c in campanas]
    elegidas = {nombre: campanas[_percentil_rango(totales, q)] for nombre, q in (("seco", 0.2), ("medio", 0.5), ("humedo", 0.8))}
    viento_mes = None
    if viento:
        viento_mes = []
        for m in MESES_CAMPANA:
            vals = [v for k, x in mensual.items() if int(k[4:]) == m for v in x["viento"]]
            viento_mes.append(round(sum(vals) / len(vals), 2) if vals else None)
    dias_erosivos = None
    if rafaga:
        dias_erosivos = []
        for m in MESES_CAMPANA:
            meses = [x for k, x in mensual.items() if int(k[4:]) == m and x["dias_rafaga"] >= 28]
            dias_erosivos.append(round(sum(x["erosivos"] for x in meses) / len(meses), 1) if meses else None)
    tsuelo_mes = None
    if tsuelo:
        # Temperatura media del suelo (0 a 10 cm) de cada mes de la campaña, promedio de las campañas usadas
        usadas = {f"{int(c['campana'][:4]) + (0 if m >= 5 else 1)}{m:02d}" for c in campanas for m in MESES_CAMPANA}
        tsuelo_mes = []
        for m in MESES_CAMPANA:
            vals = [v for k, x in mensual.items() if int(k[4:]) == m and k in usadas for v in x["tsuelo"]]
            tsuelo_mes.append(round(sum(vals) / len(vals), 1) if vals else None)
    primera, ultima = campanas[0]["campana"], campanas[-1]["campana"]
    eto_media = sum(sum(c["eto"]) for c in campanas) / len(campanas)
    return {
        "lluvia_mm": {k: [round(x, 1) for x in v["lluvia"]] for k, v in elegidas.items()},
        "eto_mm": {k: [round(x, 1) for x in v["eto"]] for k, v in elegidas.items()},
        "viento_m_s": viento_mes,
        "dias_viento_erosivo": dias_erosivos,
        "tsuelo_c": tsuelo_mes,
        "serie": [{"campana": c["campana"], "lluvia_mm": [round(x, 1) for x in c["lluvia"]], "eto_mm": [round(x, 1) for x in c["eto"]],
                   "tmin_c": [round(x, 1) for x in c["tmin"]], "dias_mas_35": c["dias_35"],
                   **({"q_trigo": c["q"]} if c["q"] and any(v is not None for v in c["q"]) else {})}
                  for c in campanas],
        "campanas_escenario": {k: v["campana"] for k, v in elegidas.items()},
        "fuente": "NASA POWER (diario, MERRA-2 e IMERG)",
        "detalle": (f"{len(campanas)} campañas de mayo a abril ({primera} a {ultima}). Año seco = {elegidas['seco']['campana']} "
                    f"({elegidas['seco']['total']:.0f} mm, percentil 20), medio = {elegidas['medio']['campana']} "
                    f"({elegidas['medio']['total']:.0f} mm, percentil 50), húmedo = {elegidas['humedo']['campana']} "
                    f"({elegidas['humedo']['total']:.0f} mm, percentil 80). ETo diaria por Hargreaves (FAO-56, ec. 52): "
                    f"{eto_media:.0f} mm por campaña en promedio."
                    + (f" Viento erosivo: días con ráfaga a 2 m de {UMBRAL_VIENTO_EROSIVO:g} m/s o más (WS2M_MAX)." if rafaga else "")),
        "escala": "regional",
        "campanas_serie": [{"campana": c["campana"], "lluvia_mm": round(c["total"])} for c in campanas],
    }
