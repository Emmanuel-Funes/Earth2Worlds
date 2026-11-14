"""Prueba real del balance hídrico propio con NASA POWER e IMERG (spec 024).

Se usa desde GitHub (Actions → "Probar POWER (balance hídrico propio)"). IMERG necesita los secretos de Earthdata.

    python probar_balance_hidrico.py "lat, lon; lat, lon; ..." 2026-08-31 2026-09-30 "franco arenoso"

Muestra el balance por década con el Kc por defecto y, para comparar, con Kc 0,4 y 0,6. Al lado pone lo que dio
SEPA en el lote de San Luis (spec 023), cuando hay ese dato. Falla si el Kc por defecto no da ningún valor
o si IMERG no respondió.
"""

import sys
import time
from datetime import date

from shapely.geometry import shape

from rotaterra.fuentes import balance_hidrico as b
from rotaterra.geo import poligono_desde_esquinas

# lo que dio SEPA en el lote de San Luis (los 6 píxeles del lote, workflow "Comparar balance hídrico propio con SEPA"):
# agua disponible hasta 2 m, en mm
SEPA_SAN_LUIS = {date(2026, 8, 31): 92.1, date(2026, 9, 10): 86.03, date(2026, 9, 20): 83.93, date(2026, 9, 30): 84.0,
                 date(2025, 1, 10): 89.4, date(2025, 1, 20): 59.4, date(2025, 1, 31): 29.97}
COMPARAR = (0.4, 0.6)

if __name__ == "__main__":
    esquinas, desde, hasta = sys.argv[1], date.fromisoformat(sys.argv[2]), date.fromisoformat(sys.argv[3])
    textura = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] else None
    centro = shape(poligono_desde_esquinas(esquinas)).centroid
    lat, lon = round(centro.y, 6), round(centro.x, 6)

    imerg_leido = {}

    def imerg_una_vez(lat_, lon_, dias):  # la lluvia de IMERG se pide una sola vez para las tres corridas
        if "lluvia" not in imerg_leido:
            inicio = time.time()
            imerg_leido["lluvia"] = b.lluvia_imerg(lat_, lon_, dias)
            leidos = "nada" if imerg_leido["lluvia"] is None else f"{len(imerg_leido['lluvia'])} de {len(dias)} días"
            print(f"IMERG: {leidos} con lluvia en POWER, en {time.time() - inicio:.0f} s")
        return imerg_leido["lluvia"]

    corridas = {}
    for kc in (b.KC_DEFECTO, *COMPARAR):
        inicio = time.time()
        corridas[kc] = b.obtener_balance("lote-prueba", lat, lon, desde, hasta, textura=textura, kc=kc,
                                         leer_imerg=imerg_una_vez)
        print(f"Kc {kc}: {len(corridas[kc])} observaciones en {time.time() - inicio:.0f} s")

    print(f"\nBalance propio · lote {lat}, {lon} · {desde} a {hasta} · textura {textura or 'sin dato'}\n")
    print(f"{'Década':<11} {'Agua mm':>8} {'%':>6} {'Relat.':>7} {'Exced.':>7} {'Confort':>8}   "
          f"{'Kc 0,4':>7} {'Kc 0,6':>7}   {'SEPA mm':>8}")
    por = {kc: {(o.variable, o.fecha): o.valor for o in obs} for kc, obs in corridas.items()}
    fechas = sorted({o.fecha for o in corridas[b.KC_DEFECTO]})

    def ver(valor):
        return "—" if valor is None else f"{valor:g}"
    for f in fechas:
        d = por[b.KC_DEFECTO]
        print(f"{f!s:<11} {ver(d['agua_disponible_2m', f]):>8} {ver(d['agua_suelo_porcentaje', f]):>6} "
              f"{ver(d['agua_relativa_balance', f]):>7} "
              f"{ver(d['excedente_balance_mm', f]):>7} {ver(d['confort_hidrico_balance', f]):>8}   "
              f"{ver(por[0.4]['agua_disponible_2m', f]):>7} {ver(por[0.6]['agua_disponible_2m', f]):>7}   "
              f"{ver(SEPA_SAN_LUIS.get(f)):>8}")

    obs = corridas[b.KC_DEFECTO]
    print("\nNotas (una por década):")
    for o in obs:
        if o.variable == "agua_disponible_2m":
            print(f"\n{o.fecha} ({o.calidad}): {o.nota}")

    if not any(o.valor is not None for o in obs):
        print("\nFALLA: el balance no dio ningún valor")
        sys.exit(1)
    if imerg_leido.get("lluvia") is None:
        print("\nFALLA: IMERG no respondió (¿están los secretos de Earthdata?)")
        sys.exit(1)
