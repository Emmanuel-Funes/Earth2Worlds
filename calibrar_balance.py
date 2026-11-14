"""Calibración del balance propio con fuentes de la NASA (spec 024), sin depender del INTA.

Se usa desde GitHub (Actions → "Calibrar balance hídrico propio (NASA)"). Necesita los secretos de Earthdata.

1. Referencias por década (último día) en el lote, de mayo de 2024 a septiembre de 2026:
   - SMAP L4 zona de raíces (SPL4SMGP, 0-100 cm, 9 km, m³/m³ → mm), al día.
   - GLDAS 2.2 Catchment zona de raíces (mm, 25 km), con ~3 meses de demora.
   - SEPA en las décadas que ya se leyeron (spec 023).
2. Corre el balance con varias combinaciones de Kc y textura sobre el mismo clima de POWER (un solo pedido).
3. Como cada fuente mide distinto, compara la forma de las curvas: correlación por década y error
   después de equiparar (llevar cada serie a % entre su mínimo y su máximo).
"""

import calendar
import math
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import httpx

from rotaterra.fuentes import balance_hidrico as b
from rotaterra.fuentes import earthdata as ed

LAT, LON = -33.7025, -65.2975  # centro del lote de San Luis
DESDE, HASTA = date(2024, 5, 1), date(2026, 9, 30)
KCS = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2]
TEXTURAS = ["arenoso franco", "franco arenoso", "franco"]
SEPA = {date(2026, 8, 31): 92.1, date(2026, 9, 10): 86.03, date(2026, 9, 20): 83.93, date(2026, 9, 30): 84.0,
        date(2025, 1, 10): 58.1, date(2025, 1, 20): 39.2, date(2025, 1, 31): 25.9}

# grilla EASE-Grid 2.0 de 9 km de SMAP L4 (la misma cuenta que el conector SMAP, spec 003)
_A, _E2 = 6378137.0, 0.0066943799901413165
_E = math.sqrt(_E2)
_K0 = math.cos(math.radians(30)) / math.sqrt(1 - _E2 * math.sin(math.radians(30)) ** 2)
_X0, _Y0, _CELDA = -17363027.2924805, 7310037.17138672, 9008.055210146


def celda_ease2(lat: float, lon: float) -> tuple[int, int]:
    s = math.sin(math.radians(lat))
    q = (1 - _E2) * (s / (1 - _E2 * s * s) - (1 / (2 * _E)) * math.log((1 - _E * s) / (1 + _E * s)))
    x, y = _A * _K0 * math.radians(lon), _A * q / (2 * _K0)
    return round((_Y0 - y) / _CELDA), round((x - _X0) / _CELDA)


def fines_de_decada(desde: date, hasta: date) -> list[date]:
    fines, dia = [], desde.replace(day=1)
    while dia <= hasta:
        for d in (10, 20, calendar.monthrange(dia.year, dia.month)[1]):
            if desde <= date(dia.year, dia.month, d) <= hasta:
                fines.append(date(dia.year, dia.month, d))
        dia = (dia.replace(day=28) + timedelta(days=4)).replace(day=1)
    return fines


def referencia(cliente, producto: str, variable: str, indice, factor: float, fechas: list[date]) -> dict[date, float]:
    coleccion = ed.coleccion_vigente(cliente, producto)
    if not coleccion:
        print(f"{producto}: CMR no lo tiene")
        return {}
    por_dia = ed.archivos_por_dia(cliente, coleccion, fechas[0], fechas[-1])
    print(f"{producto}: archivos en {len(por_dia)} días (último {max(por_dia) if por_dia else '—'})")

    def leer(f):
        urls = sorted(por_dia.get(f, []))
        if not urls:
            return f, None
        try:
            datos = ed.leer_csv(cliente, urls[len(urls) // 2], f"{variable}{indice}")
            valor = next(iter(datos.values()))[0][0]
            return f, None if valor is None or valor < -9000 else valor * factor
        except Exception as error:
            print(f"   {producto} {f}: {type(error).__name__}")
            return f, None
    with ThreadPoolExecutor(8) as hilos:
        return {f: v for f, v in hilos.map(leer, fechas) if v is not None}


def equiparar(serie: dict) -> dict:
    valores = list(serie.values())
    if len(valores) < 2 or max(valores) == min(valores):
        return {}
    bajo, alto = min(valores), max(valores)
    return {f: 100 * (v - bajo) / (alto - bajo) for f, v in serie.items()}


def comparar(a: dict, ref: dict) -> tuple[float | None, float | None, int]:
    """(correlación, error medio en puntos de % equiparado, décadas en común)."""
    comunes = sorted(set(a) & set(ref))
    if len(comunes) < 5:
        return None, None, len(comunes)
    x, y = [a[f] for f in comunes], [ref[f] for f in comunes]
    mx, my = sum(x) / len(x), sum(y) / len(y)
    sx = math.sqrt(sum((v - mx) ** 2 for v in x))
    sy = math.sqrt(sum((v - my) ** 2 for v in y))
    r = None if sx == 0 or sy == 0 else sum((p - mx) * (q - my) for p, q in zip(x, y)) / (sx * sy)
    ea, er = equiparar({f: a[f] for f in comunes}), equiparar({f: ref[f] for f in comunes})
    error = sum(abs(ea[f] - er[f]) for f in comunes) / len(comunes) if ea and er else None
    return r, error, len(comunes)


def clima_power(desde: date, hasta: date):
    respuesta = httpx.get(b.URL_POWER, timeout=300, params={
        "parameters": ",".join(b.PARAMETROS), "community": "AG", "latitude": LAT, "longitude": LON,
        "start": desde.strftime("%Y%m%d"), "end": hasta.strftime("%Y%m%d"), "format": "JSON"})
    respuesta.raise_for_status()
    datos = respuesta.json()
    return datos["properties"]["parameter"], datos["geometry"]["coordinates"][2]


if __name__ == "__main__":
    fechas = fines_de_decada(DESDE, HASTA)
    cliente = ed.cliente_autorizado()
    fila, columna = celda_ease2(LAT, LON)
    gl_fila, gl_col = round((LAT + 59.875) / 0.25), round((LON + 179.875) / 0.25)
    refs = {
        "SMAP L4 raíces": referencia(cliente, "SPL4SMGP", "/Geophysical_Data/sm_rootzone",
                                     f"[{fila}][{columna}:{columna + 1}]", 1000, fechas),
        "GLDAS 2.2 raíces": referencia(cliente, "GLDAS_CLSM025_DA1_D", "/SoilMoist_RZ_tavg",
                                       f"[0][{gl_fila}][{gl_col}:{gl_col + 1}]", 1, fechas),
        "SEPA": SEPA,
    }

    series, altura = clima_power(DESDE - timedelta(days=b.ARRANQUE_DIAS), HASTA)
    resultados = []
    corridas = {}
    for textura in TEXTURAS:
        for kc in KCS:
            agua = {}
            # el balance acepta hasta 366 días por pedido: se corre por tramos con su propio año de arranque
            tramo = DESDE
            while tramo <= HASTA:
                fin = min(HASTA, tramo + timedelta(days=b.MAX_DIAS - 1))
                for o in b.balance("lote-prueba", LAT, tramo, fin, series, altura, textura, kc):
                    if o.variable == "agua_disponible_2m" and o.valor is not None:
                        agua[o.fecha] = o.valor
                tramo = fin + timedelta(days=1)
            corridas[(textura, kc)] = agua
            fila_r = {"textura": textura, "kc": kc}
            for nombre, ref in refs.items():
                fila_r[nombre] = comparar(agua, ref)
            resultados.append(fila_r)

    print(f"\nReferencias: {', '.join(f'{n} ({len(r)} décadas)' for n, r in refs.items())}")
    print("\nr = correlación por década (1 = misma forma) · err = error medio en puntos de % equiparado\n")
    print(f"{'Textura':<16}{'Kc':>5}" + "".join(f"{n:>26}" for n in refs))
    for fila_r in resultados:
        celdas = []
        for n in refs:
            r, err, nn = fila_r[n]
            celdas.append("—" if r is None else f"r {r:.2f} · err {err:.0f} · {nn}")
        print(f"{fila_r['textura']:<16}{fila_r['kc']:>5}" + "".join(f"{c:>26}" for c in celdas))

    def puntaje(fila_r):
        r = [fila_r[n][0] for n in ("SMAP L4 raíces", "GLDAS 2.2 raíces") if fila_r[n][0] is not None]
        return sum(r) / len(r) if r else -9
    mejor = max(resultados, key=puntaje)
    print(f"\nMejor contra la NASA (correlación media con SMAP L4 y GLDAS): {mejor['textura']}, Kc {mejor['kc']}")
    agua = corridas[(mejor["textura"], mejor["kc"])]
    print(f"\n{'Década':<11}{'Balance':>9}{'SMAP L4':>9}{'GLDAS':>9}{'SEPA':>8}")
    for f in fechas:
        def ver(v):
            return "—" if v is None else f"{v:.1f}"
        print(f"{f!s:<11}{ver(agua.get(f)):>9}{ver(refs['SMAP L4 raíces'].get(f)):>9}"
              f"{ver(refs['GLDAS 2.2 raíces'].get(f)):>9}{ver(SEPA.get(f)):>8}")

    if not refs["SMAP L4 raíces"] and not refs["GLDAS 2.2 raíces"]:
        print("\nFALLA: no hubo referencias de la NASA")
        sys.exit(1)
