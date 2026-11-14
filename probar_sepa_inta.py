"""Prueba real del conector SEPA INTA y GOES-19 (spec 023).

Se usa desde GitHub (Actions → "Probar SEPA INTA y GOES (agua, heladas, Q de trigo)").

    python probar_sepa_inta.py sepa "lat, lon; lat, lon; ..." 2026-09-01 2026-10-04 --exigir a,b
    python probar_sepa_inta.py goes "lat, lon; lat, lon; ..." 2026-09-28 2026-10-04 --exigir a,b

Las fechas son opcionales (por defecto: los últimos 35 días para SEPA y los últimos 7 para GOES).
`--exigir` hace fallar la prueba si alguna de esas variables no trae ningún valor.
"""

import re
import sys
import time
from collections import defaultdict
from datetime import date, timedelta

from rotaterra.fuentes.sepa_inta import obtener_goes, obtener_sepa
from rotaterra.geo import poligono_desde_esquinas

if __name__ == "__main__":
    que, esquinas = sys.argv[1], sys.argv[2]
    fechas = [a for a in sys.argv[3:] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", a)]
    hoy = date.today()
    desde = date.fromisoformat(fechas[0]) if fechas else hoy - timedelta(days=35 if que == "sepa" else 6)
    hasta = date.fromisoformat(fechas[1]) if len(fechas) > 1 else hoy
    funcion = obtener_sepa if que == "sepa" else obtener_goes

    inicio = time.time()
    obs = funcion("lote-prueba", poligono_desde_esquinas(esquinas), desde, hasta)
    print(f"\n{que.upper()} del lote · {desde} a {hasta} · {len(obs)} observaciones · {time.time() - inicio:.0f} s\n")
    print(f"{'Fecha':<11} {'Variable':<34}{'Valor':>9}  {'Unidad':<14} {'Fuente':<10} {'Calidad':<11}")
    for o in sorted(obs, key=lambda o: (o.variable, o.fecha)):
        valor = "—" if o.valor is None else f"{o.valor:g}"
        print(f"{o.fecha!s:<11} {o.variable:<34}{valor:>9}  {o.unidad:<14} {o.fuente:<10} {o.calidad:<11}")

    # una nota de ejemplo por variable (la más reciente con valor, o la más reciente si no hay)
    por_variable = defaultdict(list)
    for o in obs:
        por_variable[o.variable].append(o)
    print("\nNotas (una por variable):")
    for variable, lista in sorted(por_variable.items()):
        elegida = max([o for o in lista if o.valor is not None] or lista, key=lambda o: o.fecha)
        print(f"\n{variable} ({elegida.fecha}): {elegida.nota}")

    exigidas = sys.argv[sys.argv.index("--exigir") + 1].split(",") if "--exigir" in sys.argv else []
    con_valor = {o.variable for o in obs if o.valor is not None}

    # SEPA caído (decisión de Hernán, 4/10/2026): si el servidor del INTA no entregó ningún archivo,
    # no se cuenta como falla del conector; se avisa y se exige solo lo que no depende de SEPA
    de_sepa = [o for o in obs if o.fuente == "SEPA_INTA" and o.nota.startswith("SEPA no ")]
    if de_sepa and not any(o.fuente == "SEPA_INTA" and o.valor is not None for o in obs):
        variables_sepa = {o.variable for o in obs if o.fuente == "SEPA_INTA"}
        exigidas = [v for v in exigidas if v not in variables_sepa]
        print(f"\n::warning::SEPA no respondió en {len(de_sepa)} pedidos (servidor del INTA caído o lento). "
              "No se cuenta como falla: el agua del suelo sale del balance propio con datos de la NASA (spec 024).")
    faltan = [v for v in exigidas if v not in con_valor] or (["todas"] if not con_valor else [])
    if faltan:
        print(f"\nFALLA: sin valor en {', '.join(faltan)}")
        sys.exit(1)
