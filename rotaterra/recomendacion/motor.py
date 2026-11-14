"""Motor de recomendación de cultivos, Fase 1: catálogo y filtro de viabilidad (spec 027).

No le pide nada a la NASA: recibe el cuestionario del productor y las observaciones que la app ya trajo con
`POST /consulta`. Mismo pedido y misma versión del catálogo dan siempre la misma respuesta.
"""

import json
from decimal import ROUND_HALF_UP, Decimal
from datetime import date
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

CATALOGO = Path(__file__).with_name("catalogo.json")
AVISO = "Es una ayuda para decidir. No reemplaza el asesoramiento de un ingeniero agrónomo."

Sistema = Literal["secano", "riego_total", "riego_complementario"]
Textura = Literal["arenoso", "franco", "arcilloso", "no_sabe"]
CultivoAnterior = Literal["soja", "maiz", "trigo", "girasol", "pastura", "otro", "no_sabe"]
Objetivo = Literal["margen", "riesgo_sequia", "equilibrio", "rotacion_suelo"]
MetodoPh = Literal["agua_1_2_5", "agua_otro", "kcl", "cacl2", "no_sabe"]


# ---------- pedido ----------

class AnalisisSuelo(BaseModel):
    """El pH decide solo si viene con laboratorio y fecha de muestreo; sin eso es un pH declarado (spec 046)."""
    ph: Optional[float] = Field(None, ge=0, le=14)
    salinidad_ds_m: Optional[float] = Field(None, ge=0)
    laboratorio: Optional[str] = Field(None, min_length=3, max_length=120, description="Quién hizo el análisis")
    fecha_muestreo: Optional[date] = Field(None, description="Cuándo se sacó la muestra; no puede ser futura")
    profundidad_cm: Optional[str] = Field(None, max_length=20, description='Por ejemplo "0-20"')
    metodo_ph: MetodoPh = "no_sabe"

    @field_validator("laboratorio", mode="before")
    @classmethod
    def _sin_espacios(cls, valor):
        return (valor.strip() or None) if isinstance(valor, str) else valor

    @field_validator("fecha_muestreo")
    @classmethod
    def _no_futura(cls, valor):
        if valor is not None and valor > date.today():
            raise ValueError("La fecha de muestreo no puede ser futura")
        return valor

    @property
    def de_laboratorio(self) -> bool:
        return self.ph is not None and self.laboratorio is not None and self.fecha_muestreo is not None


class Rinde(BaseModel):
    campana: str
    cultivo: str
    rinde_kg_ha: Optional[float] = None


class Lote(BaseModel):
    poligono: dict
    superficie_ha: Optional[float] = None
    sistema: Sistema
    textura_declarada: Textura = "no_sabe"
    cultivo_anterior: CultivoAnterior = "no_sabe"
    analisis_suelo: Optional[AnalisisSuelo] = None
    napa_m: Optional[float] = Field(None, ge=0, description="Profundidad de la napa medida por el productor")
    historial_rindes: list[Rinde] = []


class Planificacion(BaseModel):
    objetivo: Objetivo
    horizonte_anios: Literal[1, 3, 5]


class ObservacionRecibida(BaseModel):
    """Una observación como la devuelve `POST /consulta`. La fuente queda abierta: el motor no la valida."""
    lote_id: str = ""
    fecha: date
    variable: str
    valor: Optional[float]
    unidad: str
    fuente: str
    resolucion_m: int
    calidad: str
    nota: str = ""


class PedidoViabilidad(BaseModel):
    lote: Lote
    planificacion: Planificacion
    observaciones: list[ObservacionRecibida] = []


# ---------- perfil del lote ----------

# textura del modelo de 1 km de GeoINTA (clases 1 a 13, spec 021) -> grupo del cuestionario
GRUPO_TEXTURA = {1: "arenoso", 2: "arenoso", 10: "arcilloso", 11: "arcilloso", 12: "arcilloso"}
# código de cultivo del Mapa Nacional de Cultivos (spec 021) -> cultivo del cuestionario
CULTIVO_MNC = {1: "maiz", 2: "soja", 3: "girasol", 4: "sorgo", 5: "mani", 7: "algodon", 20: "trigo", 32: "girasol"}
# clases del mapa que no son un cultivo agrícola: barbecho, no agrícola, ganadería y vegetación (spec 021)
SIN_CULTIVO_MNC = {40: "barbecho", 41: "sin_agricultura", 42: "sin_agricultura", 43: "sin_agricultura",
                   44: "sin_agricultura", 45: "sin_agricultura"}
CLASES_ROMANAS = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII"}
# pH de los mapas, en orden: GeoINTA (1 km) y su respaldo de la NASA, HWSD (~5 km). Ningún satélite mide pH
FUENTES_PH_MAPA = ("GeoINTA", "HWSD")
AVISO_PH_MAPA = "solo de referencia: la última palabra la tiene el análisis de suelo del productor"
# pH del productor (spec 046)
METODOS_PH = {"agua_1_2_5": "pH en agua 1:2,5", "agua_otro": "pH en agua (otra relación)",
              "kcl": "pH en KCl", "cacl2": "pH en CaCl2"}
ANIOS_ANALISIS_VIEJO = 5     # supuesto, a confirmar con un agrónomo
DIFERENCIA_CON_EL_MAPA = 1.5


def indicador(valor, fuente: str, escala: str, fecha: date | None = None, calidad: str = "buena",
              detalle: str = "") -> dict:
    return {"valor": valor, "fuente": fuente, "escala": escala, "fecha": fecha, "calidad": calidad,
            "detalle": detalle}


def _ultima(observaciones: list[ObservacionRecibida], variable: str,
            fuentes: tuple[str, ...] | None = None) -> ObservacionRecibida | None:
    """La observación más nueva con valor de una variable; si se dan fuentes, la primera fuente que tenga."""
    utiles = [o for o in observaciones if o.variable == variable and o.valor is not None and o.calidad != "descartada"]
    for fuente in fuentes or (None,):
        candidatas = [o for o in utiles if fuente is None or o.fuente == fuente]
        if candidatas:
            return max(candidatas, key=lambda o: o.fecha)
    return None


def ph_del_productor(analisis: AnalisisSuelo, mapa: ObservacionRecibida | None) -> dict:
    """Con laboratorio y fecha es del lote y decide; sin eso es "declarado", dudoso, y queda aparte (spec 046)."""
    partes, calidad = [], "buena"
    if analisis.de_laboratorio:
        escala = "lote"
        partes.append(f"análisis de suelo de {analisis.laboratorio}, muestreo del {analisis.fecha_muestreo.isoformat()}"
                      + (f", {analisis.profundidad_cm} cm" if analisis.profundidad_cm else ""))
        if analisis.metodo_ph in ("kcl", "cacl2"):
            calidad = "dudosa"
            partes.append(f"{METODOS_PH[analisis.metodo_ph]}: da valores más bajos que en agua, no se convierte")
        elif analisis.metodo_ph in METODOS_PH:
            partes.append(METODOS_PH[analisis.metodo_ph])
        if (date.today() - analisis.fecha_muestreo).days > ANIOS_ANALISIS_VIEJO * 365.25:
            calidad = "dudosa"
            partes.append(f"análisis de más de {ANIOS_ANALISIS_VIEJO} años")
        partes.append("manda sobre el mapa" + (f" ({mapa.fuente} daba {mapa.valor:g})" if mapa else ""))
    else:
        escala, calidad = "declarado", "dudosa"
        sin = [n for n, v in (("laboratorio", analisis.laboratorio), ("fecha de muestreo", analisis.fecha_muestreo))
               if v is None]
        partes.append(f"pH declarado sin {' ni '.join(sin)}: se muestra pero no decide"
                      + (f" ({mapa.fuente} daba {mapa.valor:g})" if mapa else ""))
    if mapa:
        if abs(analisis.ph - mapa.valor) > DIFERENCIA_CON_EL_MAPA:
            partes.append(f"difiere {abs(analisis.ph - mapa.valor):.1f} del mapa: conviene revisar la muestra")
    return indicador(analisis.ph, "productor", escala, analisis.fecha_muestreo, calidad, "; ".join(partes))


def perfil_del_lote(pedido: PedidoViabilidad) -> dict[str, dict]:
    """Un indicador por tema, con su fuente, fecha, calidad y escala (lote o regional). Spec 027 §4."""
    lote, obs = pedido.lote, pedido.observaciones
    perfil: dict[str, dict] = {}

    # el pH del mapa se muestra siempre como referencia; si el productor carga su análisis, manda ese (spec 027 §4)
    mapa = _ultima(obs, "suelo_ph_0_30cm", FUENTES_PH_MAPA) or _ultima(obs, "suelo_ph_0_30cm")
    if mapa:
        perfil["ph_referencia"] = indicador(mapa.valor, mapa.fuente, "regional", mapa.fecha, mapa.calidad,
                                            f"mapa de pH 0-30 cm ({mapa.resolucion_m} m), {AVISO_PH_MAPA}")
    # segunda referencia: pH medido en los perfiles del INTA cerca del lote (SISINTA, spec 048); tampoco decide
    if perfiles := _ultima(obs, "suelo_ph_perfiles_0_30cm"):
        perfil["ph_referencia_perfiles"] = indicador(perfiles.valor, perfiles.fuente, "regional", perfiles.fecha,
                                                     perfiles.calidad, perfiles.nota)
    # el pH del lote: el de laboratorio si lo hay; si no, el de nuestras fuentes: primero los perfiles medidos del INTA
    # (SISINTA) y si no hay, el mapa (GeoINTA → HWSD) (Hernán, 29/10/2026). Ese nunca descarta: a lo sumo deja el cultivo
    # "no recomendable". Un pH escrito sin laboratorio ni fecha se muestra aparte y no decide (spec 046)
    analisis = lote.analisis_suelo
    if analisis and analisis.de_laboratorio:
        perfil["ph"] = {**ph_del_productor(analisis, mapa), "origen": "laboratorio"}
    else:
        if analisis and analisis.ph is not None:
            perfil["ph_declarado"] = ph_del_productor(analisis, mapa)
        if perfiles:
            perfil["ph"] = {**perfil["ph_referencia_perfiles"], "origen": "dataset"}
        elif mapa:
            perfil["ph"] = {**perfil["ph_referencia"], "origen": "dataset"}

    if lote.textura_declarada != "no_sabe":
        perfil["textura_grupo"] = indicador(lote.textura_declarada, "productor", "lote", detalle="declarada")
    elif o := _ultima(obs, "suelo_textura_0_15cm"):
        grupo = GRUPO_TEXTURA.get(round(o.valor), "franco")
        perfil["textura_grupo"] = indicador(grupo, o.fuente, "regional", o.fecha, o.calidad,
                                            f"clase textural {round(o.valor)} del modelo 0-15 cm ({o.resolucion_m} m)")

    if o := _ultima(obs, "agua_disponible_2m", ("SEPA_INTA", "POWER")):
        origen = "SEPA (INTA)" if o.fuente == "SEPA_INTA" else "balance propio con datos de la NASA"
        perfil["agua_util_mm"] = indicador(o.valor, o.fuente, "regional" if o.resolucion_m > 1000 else "lote",
                                           o.fecha, o.calidad, f"agua disponible hasta 2 m, {origen}")

    if lote.napa_m is not None:
        perfil["napa"] = indicador(lote.napa_m, "productor", "lote", detalle="profundidad medida (m)")
    elif o := _ultima(obs, "napa_percentil"):
        perfil["napa"] = indicador(o.valor, o.fuente, "regional", o.fecha, o.calidad,
                                   "percentil de agua subterránea de la región (GRACE-FO)")

    if o := _ultima(obs, "suelo_clase_capacidad_uso"):
        perfil["clase_capacidad_uso"] = indicador(round(o.valor), o.fuente, "lote", o.fecha, o.calidad,
                                                  "cartas de suelo del INTA")

    if lote.cultivo_anterior != "no_sabe":
        perfil["cultivo_anterior"] = indicador(lote.cultivo_anterior, "productor", "lote", detalle="declarado")
    elif o := _ultima(obs, "cultivo_mnc_verano"):
        codigo = round(o.valor)
        cultivo = CULTIVO_MNC.get(codigo) or SIN_CULTIVO_MNC.get(codigo, "otro")
        # la nota del conector dice la clase del mapa y su % del lote: se conserva para que se vea qué había
        perfil["cultivo_anterior"] = indicador(cultivo, o.fuente, "lote", o.fecha, o.calidad,
                                               "Mapa Nacional de Cultivos (verano)" + (f": {o.nota}" if o.nota else ""))

    if o := _ultima(obs, "pendiente_media_pct"):
        perfil["pendiente_pct"] = indicador(o.valor, o.fuente, "lote", o.fecha, o.calidad, "pendiente media")
    if o := _ultima(obs, "superficie_bajo_ha"):
        perfil["bajos_ha"] = indicador(o.valor, o.fuente, "lote", o.fecha, o.calidad, "superficie en bajos")

    if o := _ultima(obs, "dias_libres_heladas"):
        perfil["dias_libres_heladas"] = indicador(o.valor, o.fuente, "regional", o.fecha, o.calidad,
                                                  "días libres de heladas en 8 de cada 10 años, aire a 2 m (spec 034)"
                                                  + (f": {o.nota}" if o.nota else ""))
    if o := _ultima(obs, "lluvia_campana_mm_p50"):
        seco = _ultima(obs, "lluvia_campana_mm_p20")
        perfil["lluvia_campana_mm"] = indicador(o.valor, o.fuente, "regional", o.fecha, o.calidad,
                                                "lluvia de octubre a marzo, mediana de 35 años" +
                                                (f"; {seco.valor:g} mm en un año seco (1 de cada 5)" if seco else ""))

    hay_clima = any(o.valor is not None and o.calidad != "descartada" and
                    (o.variable.startswith(("lluvia", "temperatura", "et0", "et_")) or o.variable == "agua_disponible_2m")
                    for o in obs)
    if hay_clima:
        perfil["clima_o_agua"] = indicador(True, "observaciones", "regional", detalle="hay clima, lluvia o agua")
    return perfil


# ---------- completitud (SDD §5.3) ----------

def nivel_de_datos(pedido: PedidoViabilidad, perfil: dict) -> str:
    suelo = any(k in perfil for k in ("ph", "textura_grupo", "clase_capacidad_uso"))
    nivel_b = "clima_o_agua" in perfil and suelo
    if not nivel_b:
        return "A"
    lote = pedido.lote
    analisis = lote.analisis_suelo is not None and lote.analisis_suelo.de_laboratorio
    historia = len({r.campana for r in lote.historial_rindes}) >= 2
    extra = lote.napa_m is not None or lote.sistema != "secano" or any(k in perfil for k in ("pendiente_pct", "bajos_ha"))
    return "C" if analisis and historia and extra else "B"


ESTADO_POR_NIVEL = {"A": "preliminar", "B": "basica", "C": "completa"}


def faltantes(pedido: PedidoViabilidad, perfil: dict) -> list[dict]:
    salida = []

    def falta(dato: str, por_que: str, como: str) -> None:
        salida.append({"dato": dato, "por_que": por_que, "como_obtenerlo": como})

    if perfil.get("ph", {}).get("origen") != "laboratorio":
        referencias = [f"{r['fuente']}: {r['valor']:g}" for r in (perfil.get("ph_referencia"),
                                                                    perfil.get("ph_referencia_perfiles")) if r]
        falta("ph", "Descarta soja y alfalfa; con el pH de referencia (mapa y perfiles del INTA) un cultivo puede "
              "quedar no recomendable, pero no descartado"
              + (f" ({'; '.join(referencias)})" if referencias else ""),
              "Falta el laboratorio y la fecha del análisis que ya cargó (pH en agua 1:2,5)" if "ph_declarado" in perfil
              else "Análisis de suelo del productor (pH en agua 1:2,5)")
    if perfil.get("textura_grupo", {}).get("escala") != "lote":
        falta("textura", "Descarta maíz, girasol y maní; la textura regional no alcanza para descartar",
              "Declaración del productor o análisis de suelo")
    if "dias_libres_heladas" not in perfil:
        falta("dias_libres_heladas", "Decide maní y algodón",
              "Pedir el clima de la campaña (POWER_CAMPANA) a /consulta")
    if "agua_util_mm" not in perfil:
        falta("agua_util_mm", "Riesgo hídrico de cada cultivo", "Pedir SEPA_INTA (o su respaldo, el balance propio) a /consulta")
    if pedido.lote.napa_m is None:
        falta("napa_m", "Aporte de agua de la napa y riesgo de anegamiento", "Medición del productor")
    if len({r.campana for r in pedido.lote.historial_rindes}) < 2:
        falta("historial_rindes", "Nivel C de completitud (SDD §5.3)", "Registros del productor de dos campañas o más")
    return salida


# ---------- reglas por cultivo ----------

def cargar_catalogo(ruta: Path = CATALOGO) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


def cumple(regla: dict, valor) -> bool:
    operador, umbral = regla["operador"], regla["valor"]
    if operador == ">=":
        return valor >= umbral
    if operador == ">":
        return valor > umbral
    if operador == "<=":
        return valor <= umbral
    if operador == "<":
        return valor < umbral
    if operador == "no_en":
        return valor not in umbral
    raise ValueError(f"Operador desconocido en el catálogo: {operador}")


def evaluar_regla(regla: dict, perfil: dict) -> dict:
    """Resultado de una regla: cumple, no_cumple, ph_incompatible, sin_dato_del_lote, falta_dato o umbral_sin_definir."""
    salida = {"regla": regla["id"], "texto": regla["texto"], "umbral": regla["valor"], "unidad": regla.get("unidad")}
    if regla["valor"] is None:
        return {**salida, "resultado": "umbral_sin_definir", "valor": None, "fuente": None}
    dato = perfil.get(regla["indicador"])
    if dato is None:
        return {**salida, "resultado": "falta_dato", "valor": None, "fuente": None}
    resultado = "cumple" if cumple(regla, dato["valor"]) else "no_cumple"
    if dato["escala"] != "lote":  # un dato regional nunca descarta (spec 027, decisión 4)
        resultado = "sin_dato_del_lote" if resultado == "no_cumple" else "cumple_regional"
        # salvo el pH: si el de nuestras fuentes no cumple y el productor no cargó el suyo a mano, el cultivo queda
        # "no recomendable por pH incompatible" (Hernán, 28/10/2026)
        if resultado == "sin_dato_del_lote" and dato.get("origen") == "dataset" and "ph_declarado" not in perfil:
            resultado = "ph_incompatible"
    return {**salida, "resultado": resultado, "valor": dato["valor"], "fuente": dato["fuente"],
            "escala": dato["escala"], "fecha": dato["fecha"]}


def riesgos_del_cultivo(cultivo: dict, perfil: dict, reglas: list[dict]) -> list[str]:
    riesgos = []
    for r in reglas:
        if r["resultado"] == "ph_incompatible":
            riesgos.append(f"El pH de {r['fuente']} ({r['valor']:g}) no cumple '{r['texto']}'. Si el productor carga "
                           f"su pH, manda ese")
        elif r["resultado"] == "sin_dato_del_lote":
            riesgos.append(f"El dato regional ({r['fuente']}: {r['valor']}) no cumple '{r['texto']}'. No descarta: "
                           f"hace falta el dato del lote para confirmarlo")
    if agua := perfil.get("agua_util_mm"):
        riesgos.append(f"Agua útil hasta 2 m al {agua['fecha']}: {agua['valor']:g} mm ({agua['detalle']}). El catálogo "
                       f"indica: {cultivo['agua']}. No se comparan: falta definir el método (spec 027, decisión 6)")
    if lluvia := perfil.get("lluvia_campana_mm"):
        riesgos.append(f"Lluvia esperada de octubre a marzo: {lluvia['valor']:g} mm ({lluvia['detalle']}; "
                       f"{lluvia['fuente']}, dato regional). El catálogo indica: {cultivo['agua']}. No se comparan: "
                       f"falta definir el método (spec 027, decisión 6)")
    clase = perfil.get("clase_capacidad_uso")
    if clase and clase["valor"] >= 6:
        riesgos.append(f"Clase de capacidad de uso {CLASES_ROMANAS.get(clase['valor'], clase['valor'])} en las cartas "
                       f"del INTA: en esa clasificación, tierras no aptas para cultivos anuales sin prácticas especiales "
                       f"(referencia general, no es una regla del catálogo)")
    napa = perfil.get("napa")
    if cultivo.get("usa_napa") and napa and napa["escala"] == "regional" and napa["valor"] <= 10:
        riesgos.append(f"Napa de la región muy por debajo de lo normal (percentil {napa['valor']:g} de GRACE-FO al "
                       f"{napa['fecha']}); el catálogo pide revisar la napa en zonas secas")
    return riesgos


def viabilidad(reglas: list[dict]) -> str:
    if any(r["resultado"] == "no_cumple" for r in reglas):
        return "no_viable"
    if any(r["resultado"] == "ph_incompatible" for r in reglas):
        return "no_recomendable"
    if any(r["resultado"] != "cumple" for r in reglas):
        return "requiere_datos"
    return "viable"


def confianza(nivel: str, catalogo_validado: bool) -> str:
    if nivel == "A":
        return "baja"
    if nivel == "C" and catalogo_validado:
        return "alta"
    return "media"


def explicacion(cultivo: dict, estado: str, reglas: list[dict]) -> str:
    if estado == "no_viable":
        motivos = "; ".join(f"{r['texto']} (dato del lote: {r['valor']})" for r in reglas if r["resultado"] == "no_cumple")
        return f"{cultivo['nombre']} se descarta: {motivos}."
    if estado == "no_recomendable":
        motivos = "; ".join(f"{r['texto']} ({r['fuente']}: {r['valor']:g})" for r in reglas
                            if r["resultado"] == "ph_incompatible")
        return (f"{cultivo['nombre']}: no recomendable por pH incompatible según nuestras fuentes ({motivos}). "
                f"Si el productor carga su pH, manda ese.")
    if estado == "requiere_datos":
        motivos = "; ".join(f"{r['texto']} ({r['resultado'].replace('_', ' ')})" for r in reglas
                            if r["resultado"] != "cumple")
        return f"{cultivo['nombre']}: faltan datos para decidir. {motivos}."
    if not reglas:
        return f"{cultivo['nombre']}: el catálogo no tiene reglas excluyentes para este cultivo."
    return f"{cultivo['nombre']}: cumple todas las reglas excluyentes del catálogo."


# ---------- aviso de la campaña (spec 039) y rinde de referencia (spec 040) ----------

TEXTO_FASE = {
    "El Niño": "En la región pampeana, El Niño suele traer más lluvia de primavera y verano.",
    "La Niña": "En la región pampeana, La Niña suele traer menos lluvia de primavera y verano.",
    "neutral": "Sin El Niño ni La Niña, la campaña no tiene una señal del Pacífico.",
}


def fase_enso(oni: float) -> tuple[str, str]:
    """(fase, nombre con intensidad) con los umbrales de NOAA: ±0,5 °C; débil, moderado, fuerte y muy fuerte.
    Como NOAA, clasifica con el ONI redondeado a un decimal, la mitad hacia arriba (0,45 -> 0,5)."""
    oni = float(Decimal(str(oni)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
    if -0.5 < oni < 0.5:
        return "neutral", "neutral"
    fase = "El Niño" if oni > 0 else "La Niña"
    fuerza = abs(oni)
    intensidad = "débil" if fuerza < 1.0 else "moderada" if fuerza < 1.5 else "fuerte" if fuerza < 2.0 else "muy fuerte"
    if fase == "El Niño":
        intensidad = {"débil": "débil", "moderada": "moderado", "fuerte": "fuerte", "muy fuerte": "muy fuerte"}[intensidad]
    return fase, f"{fase} {intensidad}"


def aviso_campana(observaciones: list[ObservacionRecibida]) -> dict | None:
    """El estado del Pacífico como aviso. Nunca cambia la viabilidad (spec 039 §6)."""
    o = _ultima(observaciones, "enso_oni")
    if o is None:
        return None
    fase, nombre = fase_enso(o.valor)
    return {"fase": nombre, "oni": o.valor, "fuente": o.fuente, "fecha": o.fecha, "calidad": o.calidad,
            "detalle": o.nota,
            "texto": f"{TEXTO_FASE[fase]} Es un patrón histórico, no un pronóstico del lote. No cambia qué se puede sembrar."}


def rinde_referencia(cultivo: dict, observaciones: list[ObservacionRecibida], perfil: dict) -> dict | None:
    """Rinde del departamento para mostrar al lado del cultivo. No es el historial del productor (spec 040 §6)."""
    o = _ultima(observaciones, f"rinde_referencia_{cultivo['id']}_kg_ha")
    if o is None:
        return None
    salida = {"mediana_kg_ha": o.valor, "fuente": o.fuente, "escala": "regional", "fecha": o.fecha,
              "calidad": o.calidad, "detalle": o.nota}
    clase = perfil.get("clase_capacidad_uso")
    if clase and clase["valor"] >= 5:
        salida["aviso"] = "Un lote de esta clase suele rendir por debajo del promedio del departamento."
    return salida


def evaluar(pedido: PedidoViabilidad, catalogo: dict | None = None) -> dict:
    """Viabilidad de cada cultivo del catálogo para el lote (spec 027 §6)."""
    catalogo = catalogo or cargar_catalogo()
    validado = catalogo.get("estado") == "validado"
    perfil = perfil_del_lote(pedido)
    nivel = nivel_de_datos(pedido, perfil)
    cultivos = []
    for cultivo in catalogo["cultivos"]:
        reglas = [evaluar_regla(regla, perfil) for regla in cultivo["reglas"]]
        estado = viabilidad(reglas)
        cultivos.append({
            "cultivo": cultivo["id"], "nombre": cultivo["nombre"], "viabilidad": estado,
            "confianza": confianza(nivel, validado), "provisional": not validado,
            "reglas": reglas, "riesgos": riesgos_del_cultivo(cultivo, perfil, reglas),
            "sin_umbral": cultivo.get("sin_umbral", []), "siembra": cultivo["siembra"],
            "explicacion": explicacion(cultivo, estado, reglas),
            "rinde_referencia": rinde_referencia(cultivo, pedido.observaciones, perfil),
        })
    supuestos = [f"Catálogo v{catalogo['version']} {catalogo['estado']}: {catalogo['origen']}",
                 "Un dato regional (modelo de 1 km, GRACE-FO, SEPA a 500 m) no descarta un cultivo (spec 027, decisión 4)",
                 "Excepción: si el pH de nuestras fuentes no cumple y el productor no cargó el suyo, el cultivo queda "
                 "no recomendable por pH incompatible (Hernán, 28/10/2026)",
                 "El agua no descarta en la Fase 1: falta definir el método (spec 027, decisión 6)",
                 "El rinde de referencia es del departamento: no cuenta como historial de rindes del lote (spec 040)",
                 "El Niño o La Niña es un aviso de la campaña: no cambia la viabilidad (spec 039)"]
    return {
        "estado_evaluacion": ESTADO_POR_NIVEL[nivel], "nivel_datos": nivel,
        "perfil_lote": perfil, "cultivos": cultivos, "faltantes": faltantes(pedido, perfil),
        "planes_rotacion": [], "aviso_rotacion": (f"Horizonte pedido: {pedido.planificacion.horizonte_anios} año(s). "
                                                  "Los planes de rotación son la Fase 4: no hay reglas de secuencia "
                                                  "validadas, así que no se proponen secuencias"),
        "aviso_campana": aviso_campana(pedido.observaciones),
        "supuestos": supuestos, "version_catalogo": catalogo["version"], "aviso": AVISO,
    }
