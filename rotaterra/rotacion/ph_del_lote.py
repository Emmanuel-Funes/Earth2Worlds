"""pH del lote para el motor de rotación (spec 062, §6 bis).

Usa la misma base de cultivos que el motor de recomendación (`rotaterra/recomendacion/catalogo.json`): los topes de pH
de cada cultivo (FAO Ecocrop, pedidos por Hernán el 29/10/2026) y la misma regla de orden:

1. pH del análisis con laboratorio y fecha: manda. Si un cultivo no cumple, queda "no viable" y sale de los planes.
2. pH escrito por el productor sin laboratorio o sin fecha: reemplaza al mapa. Si un cultivo no cumple, queda
   "no recomendable" (sale de los planes, salvo `incluir_no_recomendables`).
   En los dos casos el descarte es escalonado (revisión agronómica del equipo, Leandro, 10/11/2026): un pH medido
   que se pasa del tope hasta en `TOLERANCIA_PH` (0,3) no decide si el cultivo nace o no, así que queda "tolerable":
   no se descarta y el plan lleva el aviso. Dentro del rango el cultivo está "apto"; más allá de la tolerancia, recién
   ahí se descarta.
3. Sin pH del productor: el de nuestras fuentes (perfiles medidos del INTA, SISINTA; si no, el mapa GeoINTA → HWSD),
   marcado "pH no medido". Si un cultivo no cumple, NO se descarta: el plan avisa "precaución por fuente GeoINTA"
   (Hernán, 05/11/2026).
4. Sin ningún pH: no se descarta nada y se avisa que falta.

Además, los riesgos con fuente argentina del banco de cultivos (clorosis de la soja, sodio en maíz, manganeso en maní,
alfalfa) se suman como riesgos de los planes que llevan esos cultivos. Son riesgos, nunca descartes.
"""

from __future__ import annotations

from rotaterra.recomendacion.motor import FUENTES_PH_MAPA, ObservacionRecibida, _ultima, cumple
from rotaterra.recomendacion.motor import cargar_catalogo as cargar_catalogo_recomendacion

# Cultivo del motor de rotación → cultivo del catálogo de recomendación (la cobertura de centeno no tiene regla de pH)
CULTIVO_RECOMENDACION = {"maiz": "maiz", "soja": "soja", "girasol": "girasol", "sorgo": "sorgo", "mani": "mani",
                         "trigo": "trigo", "alfalfa": "alfalfa"}
ORDEN = {"viable": 0, "requiere_datos": 1, "no_recomendable": 2, "no_viable": 3}
# Hasta cuánto puede pasarse del tope un pH medido sin descartar el cultivo: queda "tolerable" con aviso.
# Revisión agronómica del equipo (Leandro, 10/11/2026): 8,2 u 8,3 contra un tope de 8,0 no determinan si nace o no.
TOLERANCIA_PH = 0.3


def exceso_ph(regla: dict, ph: float) -> float | None:
    """Cuánto se pasa el pH del tope de la regla (positivo = no cumple). None si la regla no es de umbral."""
    if regla["operador"] in ("<=", "<"):
        return round(ph - regla["valor"], 2)  # redondeado: 8,3 − 8,0 tiene que dar 0,3 justo, no 0,30000000000000071
    if regla["operador"] in (">=", ">"):
        return round(regla["valor"] - ph, 2)
    return None


def ph_del_lote(analisis, observaciones: list[ObservacionRecibida]) -> dict | None:
    """El pH que se usa para el lote, con su origen: laboratorio, productor o referencia (no medido)."""
    if analisis is not None and analisis.ph is not None:
        if analisis.laboratorio and analisis.fecha:
            return {"valor": analisis.ph, "origen": "laboratorio", "medido": True,
                    "fuente": f"análisis de suelo ({analisis.laboratorio}, {analisis.fecha})"}
        sin = [n for n, v in (("laboratorio", analisis.laboratorio), ("fecha", analisis.fecha)) if not v]
        return {"valor": analisis.ph, "origen": "productor", "medido": True,
                "fuente": f"pH cargado por el productor, sin {' ni '.join(sin)}"}
    if o := _ultima(observaciones, "suelo_ph_perfiles_0_30cm"):
        return {"valor": o.valor, "origen": "referencia", "medido": False, "fuente_corta": o.fuente,
                "fuente": f"{o.fuente}: perfiles medidos del INTA cerca del lote ({o.fecha})"}
    if o := (_ultima(observaciones, "suelo_ph_0_30cm", FUENTES_PH_MAPA) or _ultima(observaciones, "suelo_ph_0_30cm")):
        return {"valor": o.valor, "origen": "referencia", "medido": False, "fuente_corta": o.fuente,
                "fuente": f"{o.fuente}: mapa de pH 0-30 cm ({o.resolucion_m} m, {o.fecha})"}
    return None


def evaluar_ph(analisis, observaciones: list[ObservacionRecibida], cat_rotacion: dict,
               cat_recomendacion: dict | None = None) -> dict:
    """Viabilidad por pH de cada cultivo del motor de rotación y los riesgos con fuente argentina."""
    ph = ph_del_lote(analisis, observaciones)
    if ph is None:
        return {"ph": None, "viabilidad": {}, "detalle": [], "riesgos_por_cultivo": {}}
    cat_rec = cat_recomendacion or cargar_catalogo_recomendacion()
    reglas = {c["id"]: [r for r in c["reglas"] if r["indicador"] == "ph" and r["valor"] is not None]
              for c in cat_rec["cultivos"]}
    # pH no medido (perfiles del INTA o mapa): no descarta, avisa precaución "por fuente GeoINTA" (Hernán, 05/11/2026)
    estado_si_no_cumple = {"laboratorio": "no_viable", "productor": "no_recomendable", "referencia": "precaucion"}[ph["origen"]]
    viabilidad, detalle, riesgos = {}, [], {}
    for cultivo, id_rec in CULTIVO_RECOMENDACION.items():
        for r in reglas.get(id_rec, []):
            if not cumple(r, ph["valor"]):
                exceso = exceso_ph(r, ph["valor"])
                estado = estado_si_no_cumple
                if estado != "precaucion" and exceso is not None and exceso <= TOLERANCIA_PH:
                    # pH medido apenas fuera del rango: tolerable, con aviso (revisión del equipo, 10/11/2026)
                    estado = "tolerable"
                if estado == "precaucion":
                    riesgos.setdefault(cultivo, []).append(
                        f"Precaución por fuente {ph['fuente_corta']} (pH {ph['valor']:g}, no medido en el lote): {r['texto']}. "
                        "No se descarta; cargá el análisis de suelo para confirmarlo")
                elif estado == "tolerable":
                    riesgos.setdefault(cultivo, []).append(
                        f"pH {ph['valor']:g} ({ph['origen']}): se pasa {exceso:.1f} del límite ({r['texto']}). Tolerable: "
                        f"hasta {TOLERANCIA_PH:g} fuera del rango no define si el cultivo nace, pero puede rendir menos "
                        "(revisión agronómica del equipo)")
                else:
                    viabilidad[cultivo] = estado
                detalle.append({"cultivo": cultivo, "estado": estado, "regla": r["texto"],
                                **({"exceso_ph": round(exceso, 2)} if estado == "tolerable" else {}),
                                "fuente_umbral": r.get("fuente_umbral", "catálogo de cultivos del motor (SDD v0.1)")})
    if "soja" in viabilidad:
        viabilidad["soja_2da"] = viabilidad["soja"]
    if "soja" in riesgos:
        riesgos.setdefault("soja_2da", list(riesgos["soja"]))
    fuentes = cat_rotacion["fuentes"]
    for cultivo, reglas_riesgo in cat_rotacion["ph_por_cultivo"]["riesgos"].items():
        for rr in reglas_riesgo:
            if cumple({"operador": rr["operador"], "valor": rr["ph"]}, ph["valor"]):
                riesgos.setdefault(cultivo, []).append(f"{rr['texto']} ({fuentes[rr['fuente']]})")
    return {"ph": ph, "viabilidad": viabilidad, "detalle": detalle, "riesgos_por_cultivo": riesgos}


def combinar(pedida: dict[str, str], por_ph: dict[str, str]) -> dict[str, str]:
    """La viabilidad que vino en el pedido y la del pH: queda la más restrictiva de las dos."""
    salida = dict(pedida)
    for c, estado in por_ph.items():
        if ORDEN.get(estado, 0) > ORDEN.get(salida.get(c, "viable"), 0):
            salida[c] = estado
    return salida
