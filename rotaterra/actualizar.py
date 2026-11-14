"""Actualización de datos por adelantado: baja lo nuevo de cada satélite y lo guarda (spec 004).

Se corre de noche desde GitHub Actions y es opcional: la app consulta a la NASA en el momento (spec 010) y esto
solo guarda una copia cuando hay base de datos. Solo participan los satélites
unidos a esta rama (spec 009): cada uno se anuncia solo y el núcleo no depende de ninguno.
"""

import os
import sys
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.engine import Engine

from rotaterra import base
from rotaterra.fuentes import registro
from rotaterra.fuentes.registro import Satelite

HISTORIAL_DIAS = int(os.environ.get("HISTORIAL_DIAS", 365))
SOLAPE_DIAS = int(os.environ.get("SOLAPE_DIAS", 5))


@dataclass
class Resultado:
    lote_id: str
    fuente: str
    resultado: str  # ok | pendiente | error | al_dia
    filas: int = 0
    mensaje: str = ""


def periodo(motor: Engine, lote_id: str, fuente: str, hoy: date, estatico: bool = False,
            historial_dias: int = HISTORIAL_DIAS, solape_dias: int = SOLAPE_DIAS) -> tuple[date, date] | None:
    """Qué fechas pedir: el historial la primera vez; después, los últimos días guardados (solape) hasta ayer."""
    hasta = hoy - timedelta(days=1)
    ultima = base.ultima_fecha(motor, lote_id, fuente)
    if estatico and ultima is not None:  # dato fijo ya guardado (spec 008)
        return None
    desde = hoy - timedelta(days=historial_dias) if ultima is None else ultima - timedelta(days=solape_dias - 1)
    desde = max(desde, hoy - timedelta(days=historial_dias))
    return (desde, hasta) if desde <= hasta else None


def correr(motor: Engine, lote: dict, satelite: Satelite, desde: date, hasta: date) -> Resultado:
    """Pide un período a un satélite y lo guarda. Cualquier falla queda contenida en este satélite."""
    detalle = f"respaldo de {satelite.respaldo_de}, " if satelite.respaldo_de else ""
    try:
        filas = base.guardar_observaciones(motor, satelite.pedir(lote, desde, hasta))
        r = Resultado(lote["id"], satelite.nombre, "ok", filas, f"{detalle}{desde} a {hasta}")
    except registro.Pendiente as error:
        r = Resultado(lote["id"], satelite.nombre, "pendiente", 0, f"{detalle}{error}. Se retoma en la próxima corrida.")
    except Exception as error:  # un satélite caído no frena a los demás
        r = Resultado(lote["id"], satelite.nombre, "error", 0, f"{detalle}{type(error).__name__}: {error}")
    base.registrar_actualizacion(motor, r.lote_id, r.fuente, r.resultado, r.mensaje, r.filas)
    return r


def actualizar_lote(motor: Engine, lote: dict, hoy: date | None = None,
                    satelites: list[Satelite] | None = None) -> list[Resultado]:
    """Actualiza cada satélite por separado; si uno falla, entran sus respaldos en orden hasta que uno traiga datos."""
    hoy = hoy or date.today()
    satelites = registro.descubrir().satelites if satelites is None else satelites
    respaldos = registro.respaldos_en_orden(satelites)
    resultados = []
    for satelite in (s for s in satelites if not s.respaldo_de):
        rango = periodo(motor, lote["id"], satelite.nombre, hoy, satelite.estatico)
        if rango is None:
            resultados.append(Resultado(lote["id"], satelite.nombre, "al_dia"))
            continue
        r = correr(motor, lote, satelite, *rango)
        resultados.append(r)
        if r.resultado not in ("error", "pendiente"):
            continue
        for respaldo in respaldos.get(satelite.nombre, []):  # ej. HLS → VIIRS → MODIS (spec 011)
            resultados.append(correr(motor, lote, respaldo, *rango))
            if resultados[-1].resultado == "ok" and resultados[-1].filas > 0:
                break
    return resultados


def actualizar_todo(motor: Engine, satelites: list[Satelite] | None = None) -> list[Resultado]:
    satelites = registro.descubrir().satelites if satelites is None else satelites
    resultados = []
    for lote in base.listar_lotes(motor):
        resultados += actualizar_lote(motor, lote, satelites=satelites)
    return resultados


def main() -> int:
    conectados = registro.descubrir()
    if not conectados.satelites:
        print("No hay satélites unidos a esta rama: cada satélite está en su propia rama, listo para unir.")
        return 0
    print("Satélites conectados: " + ", ".join(s.nombre for s in conectados.satelites))
    for modulo, error in conectados.rotos.items():
        print(f"Atención: el satélite '{modulo}' no carga ({error}). Los demás siguen.")
    if not os.environ.get("DATABASE_URL"):
        print("Falta el secreto DATABASE_URL: todavía no hay base de datos configurada. No se hace nada.")
        return 0
    motor = base.conectar()
    resultados = actualizar_todo(motor, conectados.satelites)
    if not resultados:
        print("No hay lotes cargados. Cargá uno con POST /lotes o con el workflow 'Cargar lote'.")
        return 0
    print(f"\n{'Lote':<16}{'Fuente':<18}{'Resultado':<11}{'Filas':>6}  Detalle")
    for r in resultados:
        print(f"{r.lote_id:<16}{r.fuente:<18}{r.resultado:<11}{r.filas:>6}  {r.mensaje[:120]}")
    # una principal caída con su respaldo guardado no cuenta como error de la corrida
    respaldo_de = {s.nombre: s.respaldo_de for s in conectados.satelites if s.respaldo_de}
    cubiertas = {(r.lote_id, respaldo_de[r.fuente]) for r in resultados
                 if r.resultado == "ok" and r.fuente in respaldo_de}
    errores = [r for r in resultados if r.resultado == "error" and (r.lote_id, r.fuente) not in cubiertas]
    print(f"\n{len(resultados)} actualizaciones: {len(errores)} con error.")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
