"""Exploración (spec 024, calibración): qué fuentes de la NASA dan agua del suelo en la zona de raíces
para comparar con SEPA y con el balance propio, si el INTA no responde.

Se usa desde GitHub (Actions → "Explorar agua del suelo de la NASA (comparación con SEPA)").
Necesita EARTHDATA_USERNAME y EARTHDATA_PASSWORD (secretos de GitHub). No imprime ningún secreto.

Lee, en el último día de cada década, el píxel del lote por OPeNDAP (núcleo `earthdata`):
- GLDAS 2.2 Catchment con GRACE asimilado (GLDAS_CLSM025_DA1_D), 0,25°, diario: agua en la zona de raíces y en el perfil, kg/m² = mm.
- GLDAS 2.1 Noah (GLDAS_NOAH025_3H), 0,25°, cada 3 horas (se usa la de las 12 UTC): zona de raíces 0-100 cm, kg/m² = mm.
Como cada fuente mide distinto (agua total, no agua útil), además de los mm se muestra cada serie
"equiparada": en % entre su mínimo y su máximo del período, para comparar la forma de la curva.
"""

import calendar
import sys
from datetime import date, timedelta

from rotaterra.fuentes import balance_hidrico as b
from rotaterra.fuentes import earthdata as ed

LAT, LON = -33.7025, -65.2975  # centro del lote de San Luis
# grilla GLDAS de 0,25°: centros desde -59,875 (lat) y -179,875 (lon)
FILA, COLUMNA = round((LAT + 59.875) / 0.25), round((LON + 179.875) / 0.25)
FUENTES = {
    "GLDAS 2.2 CLSM raíces": ("GLDAS_CLSM025_DA1_D", "SoilMoist_RZ_tavg", None),
    "GLDAS 2.2 CLSM perfil": ("GLDAS_CLSM025_DA1_D", "SoilMoist_P_tavg", None),
    "GLDAS 2.1 Noah raíces": ("GLDAS_NOAH025_3H", "RootMoist_inst", ".1200."),
}
PERIODOS = [(date(2024, 5, 1), date(2025, 2, 28)), (date(2026, 5, 1), date(2026, 9, 30))]
SEPA = {date(2026, 8, 31): 92.1, date(2026, 9, 10): 86.03, date(2026, 9, 20): 83.93, date(2026, 9, 30): 84.0,
        date(2025, 1, 10): 58.1, date(2025, 1, 20): 39.2, date(2025, 1, 31): 25.9}


def fines_de_decada(desde: date, hasta: date) -> list[date]:
    fines, dia = [], desde
    while dia <= hasta:
        for d in (10, 20, calendar.monthrange(dia.year, dia.month)[1]):
            if desde <= date(dia.year, dia.month, d) <= hasta:
                fines.append(date(dia.year, dia.month, d))
        dia = (dia.replace(day=28) + timedelta(days=4)).replace(day=1)
    return fines


def equiparar(serie: dict) -> dict:
    """Cada valor en % entre el mínimo y el máximo de la serie (0 = lo más seco, 100 = lo más húmedo)."""
    valores = [v for v in serie.values() if v is not None]
    if len(valores) < 2 or max(valores) == min(valores):
        return {}
    bajo, alto = min(valores), max(valores)
    return {f: None if v is None else 100 * (v - bajo) / (alto - bajo) for f, v in serie.items()}


if __name__ == "__main__":
    cliente = ed.cliente_autorizado()
    fechas = [f for desde, hasta in PERIODOS for f in fines_de_decada(desde, hasta)]
    series = {}
    for nombre, (producto, variable, hora) in FUENTES.items():
        series[nombre] = {}
        coleccion = ed.coleccion_vigente(cliente, producto)
        if not coleccion:
            print(f"{nombre}: CMR no tiene {producto}")
            continue
        for desde, hasta in PERIODOS:
            try:
                por_dia = ed.archivos_por_dia(cliente, coleccion, desde, hasta)
            except Exception as error:
                print(f"{nombre}: CMR falló {desde}–{hasta}: {type(error).__name__}")
                continue
            print(f"{nombre}: {len(por_dia)} días con archivo entre {desde} y {hasta}"
                  + (f" (último {max(por_dia)})" if por_dia else ""))
            for f in fines_de_decada(desde, hasta):
                urls = [u for u in por_dia.get(f, []) if hora is None or hora in u]
                if not urls:
                    continue
                try:
                    datos = ed.leer_csv(cliente, urls[0], f"/{variable}[0][{FILA}][{COLUMNA}:{COLUMNA + 1}]")
                    valor = datos[variable][0][0]
                    series[nombre][f] = None if valor is None or valor < -9000 else valor
                except Exception as error:
                    print(f"   {f}: {type(error).__name__}: {str(error)[:150]}")

    balance = {}
    for desde, hasta in PERIODOS:
        for o in b.obtener_balance("lote-prueba", LAT, LON, desde, hasta, textura="franco arenoso"):
            if o.variable == "agua_disponible_2m":
                balance[o.fecha] = o.valor
    todas = {"SEPA": SEPA, "Balance propio": balance, **series}
    nombres = list(todas)

    def ver(v):
        return f"{v:.1f}" if v is not None else "—"
    print(f"\nAgua del suelo en el lote de San Luis, en mm (píxel GLDAS fila {FILA}, columna {COLUMNA})\n")
    print(f"{'Década':<11}" + "".join(f"{n[:22]:>24}" for n in nombres))
    for f in fechas:
        print(f"{f!s:<11}" + "".join(f"{ver(todas[n].get(f)):>24}" for n in nombres))

    print("\nEquiparadas: % entre el mínimo y el máximo de cada serie en estos períodos\n")
    eq = {n: equiparar(todas[n]) for n in nombres}
    print(f"{'Década':<11}" + "".join(f"{n[:22]:>24}" for n in nombres))
    for f in fechas:
        print(f"{f!s:<11}" + "".join(f"{ver(eq[n].get(f)):>24}" for n in nombres))

    if not any(series.values()):
        print("\nFALLA: ninguna fuente de la NASA respondió")
        sys.exit(1)
