"""Consulta en el momento con respaldos: la app pide a un satélite y, si falla, responden sus respaldos (spec 012).

No usa la base de datos. El núcleo no nombra a ningún satélite: usa los unidos a esta rama (spec 009).
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from rotaterra.contrato import Observacion
from rotaterra.fuentes import registro
from rotaterra.fuentes.registro import Satelite

MAX_DIAS = 366
# variables donde un hueco largo sin dato útil se rellena con el respaldo siguiente, en el orden de la cadena
# (de más detalle a menos): días máximos seguidos sin dato que se toleran (spec 052)
HUECO_MAXIMO_DIAS = {"ndvi": 2, "ndmi": 2}
# ajuste por lote del satélite que rellena (spec 056): pares con la fuente que contestó a no más de este número de
# días, y mínimo de pares para ajustar; con menos, el relleno queda sin ajuste y "dudosa"
AJUSTE_DIAS_PAR = 1
AJUSTE_MIN_PARES = 5
# el desvío cambia con la época (enero 2026: +0,08 al principio, ~0 al final): se mide con los pares a no más de
# estos días del valor que se ajusta, y si ahí no hay suficientes, con los de todo el período
AJUSTE_VENTANA_DIAS = 10


class SateliteDesconocido(LookupError):
    """No hay un satélite principal con ese nombre unido a esta rama."""


@dataclass
class Intento:
    satelite: str
    resultado: str  # ok | sin_datos | pendiente | error | completo (spec 043) | relleno (rellenó huecos, spec 052)
    filas: int = 0
    mensaje: str = ""
    sin_credenciales: bool = False


@dataclass
class Respuesta:
    fuente_usada: str | None
    observaciones: list[Observacion]
    intentos: list[Intento]
    completada_con: list[str] = field(default_factory=list)  # respaldos del día que completaron la cola (spec 043)
    rellenada_con: list[str] = field(default_factory=list)  # respaldos que rellenaron huecos largos (spec 052)


def lote_para_consulta(lote_id: str, poligono: dict) -> dict:
    """El lote como lo reciben los satélites: id, polígono y su centro (lat/lon)."""
    from shapely.geometry import shape

    centro = shape(poligono).centroid
    return {"id": lote_id, "poligono": poligono, "lat": round(centro.y, 6), "lon": round(centro.x, 6)}


def _falta_credencial(error: Exception) -> bool:
    return any(clase.__name__ == "FaltanCredenciales" for clase in type(error).__mro__)


def _todo_descartado(observaciones: list[Observacion]) -> bool:
    return all(o.valor is None or o.calidad == "descartada" for o in observaciones)


def consultar(lote: dict, satelite: str, desde: date, hasta: date,
              satelites: list[Satelite] | None = None) -> Respuesta:
    """Pide al principal; si falla, sigue pendiente o no trae datos, prueba sus respaldos en orden.

    Una fuente que contesta con todas sus observaciones descartadas (ej. HLS con todo el mes nublado) también deja
    pasar al respaldo siguiente. Si nadie trae nada útil, vuelve la primera de esas, con sus notas (spec 041, parte B).
    Después, los huecos largos sin dato útil (más de HUECO_MAXIMO_DIAS) los rellenan los respaldos siguientes, de más
    detalle a menos (spec 052). Al final, los respaldos del día completan los últimos días que la respuesta todavía no
    tiene (spec 043).
    """
    if desde > hasta:
        raise ValueError("La fecha 'desde' es posterior a 'hasta'")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise ValueError(f"El rango supera {MAX_DIAS} días")
    satelites = registro.descubrir().satelites if satelites is None else satelites
    principal = next((s for s in satelites if s.nombre == satelite and not s.respaldo_de), None)
    if principal is None:
        raise SateliteDesconocido(satelite)
    intentos = []
    respuesta = _con_respaldos(lote, principal, satelites, desde, hasta, intentos)
    respuesta = _rellenar_huecos(lote, principal, satelites, desde, hasta, respuesta)
    return _completar_cola(lote, principal, satelites, desde, hasta, respuesta)


def _con_respaldos(lote: dict, principal: Satelite, satelites: list[Satelite], desde: date, hasta: date,
                   intentos: list[Intento]) -> Respuesta:
    reserva: Respuesta | None = None
    for s in [principal] + registro.respaldos_en_orden(satelites).get(principal.nombre, []):
        try:
            observaciones = s.pedir(lote, desde, hasta)
        except registro.Pendiente as error:
            intentos.append(Intento(s.nombre, "pendiente", mensaje=str(error)))
            continue
        except Exception as error:  # un satélite caído deja pasar al siguiente respaldo
            intentos.append(Intento(s.nombre, "error", mensaje=f"{type(error).__name__}: {error}",
                                    sin_credenciales=_falta_credencial(error)))
            continue
        if not observaciones:
            intentos.append(Intento(s.nombre, "sin_datos", mensaje="no trajo ningún dato para el período"))
            continue
        if _todo_descartado(observaciones):
            motivo = observaciones[0].nota or "sin nota"
            intentos.append(Intento(s.nombre, "sin_datos", filas=len(observaciones),
                                    mensaje=f"todas sus observaciones vienen descartadas: {motivo}"))
            reserva = reserva or Respuesta(s.nombre, observaciones, intentos)
            continue
        intentos.append(Intento(s.nombre, "ok", filas=len(observaciones)))
        return Respuesta(s.nombre, observaciones, intentos)
    if reserva:
        return Respuesta(reserva.fuente_usada, reserva.observaciones, intentos)
    return Respuesta(None, [], intentos)


def _util(o: Observacion) -> bool:
    return o.valor is not None and o.calidad != "descartada"


def huecos(fechas: set[date], desde: date, hasta: date, maximo: int) -> list[tuple[date, date]]:
    """Tramos de más de `maximo` días seguidos sin dato útil dentro del período (incluye el principio y el final)."""
    tramos, inicio = [], desde
    for dia in sorted(f for f in fechas if desde <= f <= hasta) + [hasta + timedelta(days=1)]:
        if (dia - inicio).days > maximo:
            tramos.append((inicio, dia - timedelta(days=1)))
        inicio = dia + timedelta(days=1)
    return tramos


def pares(referencia: list[Observacion], otras: list[Observacion], variable: str) -> list[tuple[date, float]]:
    """(fecha, otra − referencia) de cada observación útil de `otras` con la de `referencia` más cercana a no más de
    AJUSTE_DIAS_PAR días, en la misma variable (spec 056)."""
    ref = [o for o in referencia if o.variable == variable and _util(o)]
    hallados = []
    for o in otras:
        if o.variable != variable or not _util(o):
            continue
        cerca = [r for r in ref if abs((r.fecha - o.fecha).days) <= AJUSTE_DIAS_PAR]
        if cerca:
            par = min(cerca, key=lambda r: abs((r.fecha - o.fecha).days))
            hallados.append((o.fecha, o.valor - par.valor))
    return hallados


def _mediana(valores: list[float]) -> float:
    valores = sorted(valores)
    medio = len(valores) // 2
    return valores[medio] if len(valores) % 2 else (valores[medio - 1] + valores[medio]) / 2


def corrimiento(todos: list[tuple[date, float]], fecha: date) -> tuple[float | None, int, str]:
    """Corrimiento del lote para el valor de `fecha`: mediana de los pares a ±AJUSTE_VENTANA_DIAS; si no alcanzan,
    la de todo el período; None si tampoco hay AJUSTE_MIN_PARES (spec 056). Devuelve (corrimiento, pares, alcance)."""
    cerca = [d for f, d in todos if abs((f - fecha).days) <= AJUSTE_VENTANA_DIAS]
    if len(cerca) >= AJUSTE_MIN_PARES:
        return _mediana(cerca), len(cerca), f"a ±{AJUSTE_VENTANA_DIAS} días"
    if len(todos) >= AJUSTE_MIN_PARES:
        return _mediana([d for _, d in todos]), len(todos), "del período"
    return None, len(todos), ""


def ajustar(o: Observacion, todos: list[tuple[date, float]], contra: str | None) -> Observacion:
    """La observación de relleno con el corrimiento del lote descontado; sin pares suficientes queda 'dudosa'."""
    desvio, n, alcance = corrimiento(todos, o.fecha)
    if desvio is None:
        return o.model_copy(update={"calidad": "dudosa", "nota": f"{o.nota} · sin ajuste al lote: solo {n} "
                                    f"pares con {contra} para comparar (hacen falta {AJUSTE_MIN_PARES})"})
    valor = round(min(1.0, max(-1.0, o.valor - desvio)), 3)
    return o.model_copy(update={"valor": valor, "nota": f"{o.nota} · ajustado al lote: {-desvio:+.3f} (mediana de "
                                f"{n} pares {alcance} con {contra}, a ±{AJUSTE_DIAS_PAR} día cada uno), "
                                f"valor original {o.valor}"})


def _rellenar_huecos(lote: dict, principal: Satelite, satelites: list[Satelite], desde: date, hasta: date,
                     respuesta: Respuesta) -> Respuesta:
    """Los huecos largos de las variables de HUECO_MAXIMO_DIAS los rellenan los respaldos que vienen después del que
    contestó, en orden (spec 052). A cada respaldo se le pide todo el período, para poder compararlo con la fuente que
    contestó (spec 056), y de lo que trae se toma solo lo que cae dentro de un hueco, con el ajuste del lote. Nunca se
    promedia: cada día queda con una sola fuente."""
    variables = {o.variable for o in respuesta.observaciones} & set(HUECO_MAXIMO_DIAS)
    if not variables:
        return respuesta
    cadena = registro.respaldos_en_orden(satelites).get(principal.nombre, [])
    usados = [s.nombre for s in [principal] + cadena]
    siguientes = cadena[usados.index(respuesta.fuente_usada):] if respuesta.fuente_usada in usados else []
    observaciones = list(respuesta.observaciones)
    referencia = [o for o in observaciones if _util(o)]  # lo que trajo la fuente que contestó, antes de rellenar
    rellenada_con = []

    def tramos_de(variable: str) -> list[tuple[date, date]]:
        utiles = {o.fecha for o in observaciones if o.variable == variable and _util(o)}
        return huecos(utiles, desde, hasta, HUECO_MAXIMO_DIAS[variable])

    for s in siguientes:
        abiertos = {v: tramos_de(v) for v in variables}
        abiertos = {v: t for v, t in abiertos.items() if t}
        if not abiertos:
            break
        inicio = min(t[0][0] for t in abiertos.values())
        fin = max(t[-1][1] for t in abiertos.values())
        try:
            nuevas = s.pedir(lote, desde, hasta)
        except Exception as error:  # un respaldo caído deja los huecos para el siguiente
            respuesta.intentos.append(Intento(s.nombre, "error", mensaje=f"{type(error).__name__}: {error}",
                                              sin_credenciales=_falta_credencial(error)))
            continue
        todos = {v: pares(referencia, nuevas or [], v) for v in abiertos}
        puestas = [ajustar(o, todos[o.variable], respuesta.fuente_usada) for o in nuevas or []
                   if _util(o) and o.variable in abiertos and any(a <= o.fecha <= b for a, b in abiertos[o.variable])]
        if not puestas:
            respuesta.intentos.append(Intento(s.nombre, "sin_datos",
                                              mensaje=f"no trajo datos útiles para los huecos del {inicio} al {fin}"))
            continue
        reemplazadas = {(o.fecha, o.variable) for o in puestas}
        observaciones = [o for o in observaciones if (o.fecha, o.variable) not in reemplazadas] + puestas
        dias = sorted({o.fecha for o in puestas})
        respuesta.intentos.append(Intento(s.nombre, "relleno", filas=len(puestas),
                                          mensaje=f"rellenó {len(dias)} días de huecos entre el {dias[0]} y el {dias[-1]}"))
        rellenada_con.append(s.nombre)
    if not rellenada_con:
        return respuesta
    observaciones.sort(key=lambda o: (o.fecha, o.variable))
    return Respuesta(respuesta.fuente_usada, observaciones, respuesta.intentos, respuesta.completada_con,
                     rellenada_con)


def _completar_cola(lote: dict, principal: Satelite, satelites: list[Satelite], desde: date, hasta: date,
                    respuesta: Respuesta) -> Respuesta:
    """Los días posteriores al último dato útil de cada variable los completan los respaldos del día (spec 043).

    No se rellenan huecos del medio del período (ej. días sin pasada de HLS): solo la cola que la fuente todavía no
    publicó. Del respaldo del día se toman solo las variables que ya trajo la respuesta; si no trajo ninguna, todas.
    """
    del_dia = registro.respaldos_en_orden(satelites, al_dia=True).get(principal.nombre, [])
    if not del_dia:
        return respuesta
    observaciones = list(respuesta.observaciones)
    variables = {o.variable for o in observaciones}

    def inicio_de(variable: str) -> date:
        utiles = [o.fecha for o in observaciones if o.variable == variable and _util(o)]
        return max(utiles) + timedelta(days=1) if utiles else desde

    completada_con = []
    for s in del_dia:
        inicios = {v: inicio_de(v) for v in variables}
        inicio = min(inicios.values(), default=desde)
        if inicio > hasta:
            break
        try:
            nuevas = s.pedir(lote, inicio, hasta)
        except Exception as error:  # el respaldo del día caído deja la respuesta como estaba
            respuesta.intentos.append(Intento(s.nombre, "error", mensaje=f"{type(error).__name__}: {error}",
                                              sin_credenciales=_falta_credencial(error)))
            continue
        ocupados = {(o.fecha, o.variable) for o in observaciones if _util(o)}
        puestas = [o for o in nuevas or [] if _util(o) and (o.fecha, o.variable) not in ocupados
                   and (not variables or o.variable in variables)
                   and o.fecha >= inicios.get(o.variable, desde) and desde <= o.fecha <= hasta]
        if not puestas:
            respuesta.intentos.append(Intento(s.nombre, "sin_datos", mensaje=f"no trajo datos útiles desde {inicio}"))
            continue
        reemplazadas = {(o.fecha, o.variable) for o in puestas}
        observaciones = [o for o in observaciones if (o.fecha, o.variable) not in reemplazadas] + puestas
        variables = variables or {o.variable for o in puestas}
        dias = sorted({o.fecha for o in puestas})
        respuesta.intentos.append(Intento(s.nombre, "completo", filas=len(puestas),
                                          mensaje=f"completó del {dias[0]} al {dias[-1]}"))
        completada_con.append(s.nombre)
    if not completada_con:
        return respuesta
    observaciones.sort(key=lambda o: (o.fecha, o.variable))
    return Respuesta(respuesta.fuente_usada or completada_con[0], observaciones, respuesta.intentos, completada_con,
                     respuesta.rellenada_con)
