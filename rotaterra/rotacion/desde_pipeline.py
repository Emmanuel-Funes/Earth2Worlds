"""Completa el pedido del motor de rotación con lo que ya trajo `POST /consulta` (spec 062, §3 bis).

No agrega satélites: usa las observaciones de las fuentes que ya tiene Rotaterra. Lo que cargó el productor
siempre manda; una observación solo llena un campo vacío, y la respuesta dice qué se tomó de dónde.
"""

from __future__ import annotations

from rotaterra.recomendacion.motor import CULTIVO_MNC, ObservacionRecibida, _ultima

# Código común de textura de GeoINTA (spec 021, §23.3), de grueso a fino → clases del motor de rotación
TEXTURA_GEOINTA = {1: "arenoso", 2: "arenoso", 3: "franco_arenoso", 4: "franco", 5: "franco_limoso", 6: "franco_limoso",
                   7: "franco_arcilloso", 8: "franco_arcilloso", 9: "franco_arcilloso", 10: "arcilloso", 11: "arcilloso",
                   12: "arcilloso", 13: "franco"}
CULTIVOS_DEL_MOTOR = {"maiz", "soja", "girasol", "sorgo", "mani", "trigo"}  # algodón cuenta como agricultura, pero no entra al historial
CAPAS_GEOINTA = {(0, 15): "suelo_textura_0_15cm", (15, 30): "suelo_textura_15_30cm",
                 (30, 60): "suelo_textura_30_60cm", (60, 100): "suelo_textura_60_100cm"}
# Cobertura de árboles y arbustos desde la que se sospecha monte: 10 % (umbral de bosque de la FAO, FRA 2020)
MONTE_PCT = 10.0
RINDES = ("maiz", "soja", "soja_2da", "sorgo", "mani", "girasol", "trigo")


def campana_de(fecha) -> str:
    """La campaña (mayo a abril) a la que pertenece una fecha."""
    y = fecha.year if fecha.month >= 5 else fecha.year - 1
    return f"{y}/{str(y + 1)[2:]}"


def completar(datos: dict, observaciones: list[ObservacionRecibida]) -> tuple[dict, list[str]]:
    """Devuelve el pedido (como dict) con los campos vacíos completados y la lista de lo que se tomó."""
    usados: list[str] = []
    lote = dict(datos.get("lote") or {})
    if lote.get("textura", "no_sabe") == "no_sabe" and (o := _ultima(observaciones, "suelo_textura_0_15cm")):
        clase = TEXTURA_GEOINTA.get(round(o.valor))
        if clase:
            lote["textura"], lote["textura_fuente"] = clase, f"{o.fuente} (regional, {o.resolucion_m} m)"
            usados.append(f"Textura {clase.replace('_', ' ')}: {o.fuente}, 0-15 cm ({o.fecha})")
            # Las capas de abajo cambian cuánta agua guarda el perfil: se usan si el productor no cargó la textura
            if not lote.get("capas_textura"):
                capas = []
                for (desde, hasta), var in CAPAS_GEOINTA.items():
                    oc = _ultima(observaciones, var)
                    if oc and (cl := TEXTURA_GEOINTA.get(round(oc.valor))):
                        capas.append({"desde_cm": desde, "hasta_cm": hasta, "textura": cl})
                if len(capas) > 1:
                    lote["capas_textura"], lote["capas_fuente"] = capas, f"{o.fuente} (regional, {o.resolucion_m} m)"
                    usados.append("Textura por capas: " + ", ".join(f"{c['desde_cm']}-{c['hasta_cm']} cm {c['textura'].replace('_', ' ')}"
                                                                 for c in capas) + f" ({o.fuente})")
    if lote.get("pendiente_pct") is None and (o := _ultima(observaciones, "pendiente_media_pct")):
        lote["pendiente_pct"] = o.valor
        usados.append(f"Pendiente {o.valor:g} %: {o.fuente}")
    if not lote.get("ambientes_ha"):
        amb = {k: _ultima(observaciones, f"superficie_{k}_ha") for k in ("loma", "media_loma", "bajo")}
        if all(amb.values()) and sum(o.valor for o in amb.values()) > 0:
            fuente = amb["loma"].fuente
            lote["ambientes_ha"] = {k: o.valor for k, o in amb.items()} | {"fuente": f"{fuente} (relieve del lote)"}
            usados.append(f"Ambientes: loma {amb['loma'].valor:g} ha, media loma {amb['media_loma'].valor:g} ha, "
                          f"bajo {amb['bajo'].valor:g} ha ({fuente})")
    for campo, variables, nombre in (("capacidad_uso", ("suelo_clase_capacidad_uso",), "Clase de capacidad de uso"),
                                     ("indice_productividad", ("suelo_indice_productividad_detallado", "suelo_indice_productividad"),
                                      "Índice de productividad")):
        if lote.get(campo) is None:
            o = next((x for v in variables if (x := _ultima(observaciones, v))), None)
            valido = o and (1 <= round(o.valor) <= 8 if campo == "capacidad_uso" else 0 <= o.valor <= 100)
            if valido:
                lote[campo] = round(o.valor) if campo == "capacidad_uso" else o.valor
                lote.setdefault("suelo_fuente", o.fuente)
                usados.append(f"{nombre} {o.valor:g}: {o.fuente}")
    datos["lote"] = lote

    # Datos de la zona que el plan muestra como contexto (no cambian la simulación)
    contexto = dict(datos.get("contexto_satelital") or {})
    for clave, variable in (("carbono_organico_0_30cm_t_ha", "suelo_carbono_organico_0_30cm_t_ha"),
                            ("cobertura_arborea_lote_pct", "gedi_cobertura_lote_pct"),
                            ("monte_zona_pct", "gedi_monte_zona_pct"),
                            ("napa_percentil", "napa_percentil"),
                            ("humedad_raices_percentil", "humedad_raices_percentil")):
        if clave not in contexto and (o := _ultima(observaciones, variable)):
            contexto[clave] = {"valor": o.valor, "fuente": o.fuente, "fecha": o.fecha.isoformat()}
    futuro = {}
    for indicador in ("dias_calor_35", "lluvia_campana_mm", "racha_seca_campana_dias", "dias_lluvia_extrema_50"):
        valores = {p: _ultima(observaciones, f"{indicador}_{p}") for p in ("historico", "ssp245", "ssp585")}
        if all(valores.values()):
            futuro[indicador] = {p: o.valor for p, o in valores.items()}
            fuente_futuro = valores["historico"].fuente
    if futuro and "clima_futuro" not in contexto:
        contexto["clima_futuro"] = {"indicadores": futuro, "fuente": fuente_futuro,
                                    "periodos": "1995-2014 contra 2041-2060 (SSP2-4.5 y SSP5-8.5)"}
    if contexto:
        datos["contexto_satelital"] = contexto

    if not datos.get("agua_util_inicial") and (o := _ultima(observaciones, "agua_disponible_2m", ("SEPA_INTA", "POWER"))):
        origen = "SEPA (INTA)" if o.fuente == "SEPA_INTA" else "balance propio con datos de la NASA"
        datos["agua_util_inicial"] = {"valor": o.valor, "fuente": f"{origen}, agua disponible hasta 2 m al {o.fecha}",
                                      "escala": "regional" if o.resolucion_m > 1000 else "lote"}
        usados.append(f"Agua útil inicial {o.valor:g} mm: {origen} ({o.fecha})")

    refs = dict(datos.get("rindes_referencia") or {})
    for c in RINDES:
        if c not in refs and (o := _ultima(observaciones, f"rinde_referencia_{c}_kg_ha")):
            refs[c] = {"valor": o.valor, "fuente": f"{o.fuente}: {o.nota}" if o.nota else o.fuente, "escala": "regional"}
            usados.append(f"Rinde de referencia de {c.replace('_', ' ')} {o.valor:g} kg/ha: {o.fuente}")
    datos["rindes_referencia"] = refs

    historial = list(datos.get("historial") or [])
    con_dato = {h["campana"] if isinstance(h, dict) else h.campana for h in historial}
    for o in sorted((x for x in observaciones if x.variable == "cultivo_mnc_verano" and x.valor is not None
                     and x.calidad != "descartada"), key=lambda x: x.fecha):
        campana = campana_de(o.fecha)
        cultivo = CULTIVO_MNC.get(round(o.valor))
        if cultivo in CULTIVOS_DEL_MOTOR and campana not in con_dato:
            historial.append({"campana": campana, "cultivo": cultivo, "evidencia": "inferido",
                              "fuente": f"{o.fuente} (Mapa Nacional de Cultivos)"})
            con_dato.add(campana)
            usados.append(f"Campaña {campana}: {cultivo} inferido por el Mapa Nacional de Cultivos")
    datos["historial"] = sorted(historial, key=lambda h: h["campana"] if isinstance(h, dict) else h.campana)

    # Si el Mapa Nacional de Cultivos miró el lote varias campañas y nunca vio un cultivo, puede ser terreno sin agricultura.
    # No se decide solo: se avisa para que el productor lo confirme.
    vistas = {campana_de(x.fecha): CULTIVO_MNC.get(round(x.valor)) for x in observaciones
              if x.variable == "cultivo_mnc_verano" and x.valor is not None and x.calidad != "descartada"}
    gedi = _ultima(observaciones, "gedi_cobertura_lote_pct")
    if lote.get("uso_anterior", "no_sabe") == "no_sabe" and gedi and gedi.valor >= MONTE_PCT:
        usados.append(f"GEDI ve {gedi.valor:g} % de cobertura de árboles y arbustos en el lote ({gedi.fuente}): puede ser monte "
                      "que nunca se cultivó. Confirmalo en uso_anterior; un desmonte necesita autorización (Ley 26.331)")
    if lote.get("uso_anterior", "no_sabe") == "no_sabe" and len(vistas) >= 3 and not any(vistas.values()):
        usados.append(f"El Mapa Nacional de Cultivos no vio agricultura en {len(vistas)} campañas ({min(vistas)} a {max(vistas)}): "
                      "puede ser terreno virgen o pastura. Confirmalo en uso_anterior")
    return datos, usados
