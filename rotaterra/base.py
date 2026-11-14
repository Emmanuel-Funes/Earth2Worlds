"""Base de datos de Rotaterra: lotes, observaciones guardadas y estado de cada actualización (spec 004)."""

import json
import os
from datetime import date, datetime, timezone

from sqlalchemy import (Column, Date, DateTime, Float, Integer, MetaData, String, Table, Text,
                        and_, create_engine, delete, func, insert, select)
from sqlalchemy.engine import Engine

from rotaterra.contrato import Observacion

URL_POR_DEFECTO = "sqlite:///rotaterra.db"

metadata = MetaData()

lotes = Table(
    "lotes", metadata,
    Column("id", String(64), primary_key=True),
    Column("nombre", String(200), nullable=False),
    Column("poligono", Text, nullable=False),  # GeoJSON Polygon, EPSG:4326
    Column("lat", Float, nullable=False),      # centro del lote
    Column("lon", Float, nullable=False),
    Column("creado", DateTime(timezone=True), nullable=False),
)

observaciones = Table(
    "observaciones", metadata,
    Column("lote_id", String(64), primary_key=True),
    Column("fecha", Date, primary_key=True),
    Column("variable", String(64), primary_key=True),
    Column("fuente", String(32), primary_key=True),
    Column("valor", Float, nullable=True),
    Column("unidad", String(32), nullable=False),
    Column("resolucion_m", Integer, nullable=False),
    Column("calidad", String(16), nullable=False),
    Column("nota", Text, nullable=False, default=""),
    Column("actualizado", DateTime(timezone=True), nullable=False),
)

actualizaciones = Table(
    "actualizaciones", metadata,
    Column("lote_id", String(64), primary_key=True),
    Column("fuente", String(32), primary_key=True),
    Column("ultima_corrida", DateTime(timezone=True), nullable=False),
    Column("resultado", String(16), nullable=False),  # ok | pendiente | error
    Column("mensaje", Text, nullable=False, default=""),
    Column("filas", Integer, nullable=False, default=0),
)


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def conectar(url: str | None = None) -> Engine:
    """Abre la base (SQLite o PostgreSQL según DATABASE_URL) y crea las tablas que falten."""
    url = url or os.environ.get("DATABASE_URL") or URL_POR_DEFECTO
    if url.startswith("postgres://"):  # formato viejo que todavía dan algunos proveedores
        url = "postgresql://" + url.removeprefix("postgres://")
    motor = create_engine(url)
    metadata.create_all(motor)
    return motor


# ---------- lotes ----------

def guardar_lote(motor: Engine, lote_id: str, nombre: str, poligono: dict) -> dict:
    from shapely.geometry import shape

    centro = shape(poligono).centroid
    fila = dict(id=lote_id, nombre=nombre, poligono=json.dumps(poligono),
                lat=round(centro.y, 6), lon=round(centro.x, 6), creado=ahora())
    with motor.begin() as conexion:
        conexion.execute(delete(lotes).where(lotes.c.id == lote_id))
        conexion.execute(insert(lotes).values(**fila))
    return _lote(fila)


def _lote(fila) -> dict:
    fila = dict(fila)
    fila["poligono"] = json.loads(fila["poligono"])
    return fila


def listar_lotes(motor: Engine) -> list[dict]:
    with motor.connect() as conexion:
        return [_lote(f) for f in conexion.execute(select(lotes).order_by(lotes.c.id)).mappings()]


def obtener_lote(motor: Engine, lote_id: str) -> dict | None:
    with motor.connect() as conexion:
        fila = conexion.execute(select(lotes).where(lotes.c.id == lote_id)).mappings().first()
    return _lote(fila) if fila else None


# ---------- observaciones ----------

def guardar_observaciones(motor: Engine, nuevas: list[Observacion]) -> int:
    """Guarda en el contrato común; si ya existía la misma clave, la reemplaza (no duplica)."""
    if not nuevas:
        return 0
    momento = ahora()
    filas = [dict(o.model_dump(), actualizado=momento) for o in nuevas]
    with motor.begin() as conexion:
        for fila in filas:
            conexion.execute(delete(observaciones).where(and_(
                observaciones.c.lote_id == fila["lote_id"], observaciones.c.fecha == fila["fecha"],
                observaciones.c.variable == fila["variable"], observaciones.c.fuente == fila["fuente"])))
        conexion.execute(insert(observaciones), filas)
    return len(filas)


def leer_observaciones(motor: Engine, lote_id: str, variable: str | None = None, fuente: str | None = None,
                       desde: date | None = None, hasta: date | None = None) -> list[Observacion]:
    consulta = select(observaciones).where(observaciones.c.lote_id == lote_id)
    if variable:
        consulta = consulta.where(observaciones.c.variable == variable)
    if fuente:
        consulta = consulta.where(observaciones.c.fuente == fuente)
    if desde:
        consulta = consulta.where(observaciones.c.fecha >= desde)
    if hasta:
        consulta = consulta.where(observaciones.c.fecha <= hasta)
    consulta = consulta.order_by(observaciones.c.fecha, observaciones.c.variable, observaciones.c.fuente)
    with motor.connect() as conexion:
        return [Observacion(**{k: v for k, v in f.items() if k != "actualizado"})
                for f in conexion.execute(consulta).mappings()]


# menor número = más confiable; el productor manda sobre todo, los respaldos van después
PRIORIDAD = {"productor": 0, "HLS": 1, "SMAP": 1, "POWER": 1, "IMERG": 1, "ECOSTRESS": 1, "NASADEM": 1, "GeoINTA": 1,
             "SEPA_INTA": 1, "GOES": 1,
             "SENTINEL2": 2, "MERRA2": 2, "COPDEM": 2, "GRACE": 2, "SENTINEL3": 3, "VIIRS": 3, "MODIS": 4, "HWSD": 5, "GLDAS": 5, "FLDAS": 6, "ASTER": 2, "PERSIANN": 5, "GEOS_FP": 3, "IMERG_EARLY": 2,
             "MODIS_NRT": 5, "SMAP_NRT": 2}
# cuando dos fuentes principales dan la misma variable, la especializada gana (spec 006)
PREFERIDA = {"lluvia_mm": "IMERG"}
# variables donde la confianza cambia: la ET real la da MODIS (principal), ECOSTRESS la respalda (specs 017 y 018)
# y GLDAS entra después (spec 032)
PRIORIDAD_POR_VARIABLE = {"et_mm_dia": {"MODIS": 1, "VIIRS": 1, "ECOSTRESS": 2, "GLDAS": 3},
                          # heladas: VIIRS principal, MODIS primer respaldo y Sentinel-3 segundo (specs 030, 035 y 051)
                          "temp_sup_min_c": {"SENTINEL3": 5}}


def prioridad(o: Observacion) -> int:
    """Confianza de la fuente para esa variable: 0 es la mejor."""
    return PRIORIDAD_POR_VARIABLE.get(o.variable, {}).get(o.fuente, PRIORIDAD.get(o.fuente, 9))


def combinar_fuentes(guardadas: list[Observacion]) -> list[Observacion]:
    """Una observación por fecha y variable: la de mejor fuente que tenga valor."""
    def orden(o: Observacion) -> tuple:
        return (o.valor is None, prioridad(o), PREFERIDA.get(o.variable) != o.fuente)

    elegidas: dict[tuple, Observacion] = {}
    for o in guardadas:
        clave = (o.fecha, o.variable)
        if clave not in elegidas or orden(o) < orden(elegidas[clave]):
            elegidas[clave] = o
    return [elegidas[k] for k in sorted(elegidas)]


def ultima_fecha(motor: Engine, lote_id: str, fuente: str) -> date | None:
    """Última fecha con un valor real (no descartado) de esa fuente para el lote."""
    consulta = select(func.max(observaciones.c.fecha)).where(
        observaciones.c.lote_id == lote_id, observaciones.c.fuente == fuente,
        observaciones.c.valor.is_not(None))
    with motor.connect() as conexion:
        return conexion.execute(consulta).scalar()


# ---------- estado de las actualizaciones ----------

def registrar_actualizacion(motor: Engine, lote_id: str, fuente: str, resultado: str,
                            mensaje: str = "", filas: int = 0) -> None:
    with motor.begin() as conexion:
        conexion.execute(delete(actualizaciones).where(
            actualizaciones.c.lote_id == lote_id, actualizaciones.c.fuente == fuente))
        conexion.execute(insert(actualizaciones).values(
            lote_id=lote_id, fuente=fuente, ultima_corrida=ahora(), resultado=resultado,
            mensaje=mensaje, filas=filas))


def estado(motor: Engine, lote_id: str) -> list[dict]:
    with motor.connect() as conexion:
        filas = conexion.execute(select(actualizaciones).where(actualizaciones.c.lote_id == lote_id)
                                 .order_by(actualizaciones.c.fuente)).mappings().all()
    # un respaldo "SMAP:AppEEARS" guarda sus datos como fuente "SMAP"
    return [dict(f, ultima_fecha_con_dato=ultima_fecha(motor, lote_id, f["fuente"].split(":")[0])) for f in filas]
