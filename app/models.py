"""Modelos ORM SQLAlchemy 2.0 para la plataforma Earth2Worlds."""

from datetime import datetime
import enum

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import backref, relationship

from app.database import Base


class RolEnum(str, enum.Enum):
    """Roles del sistema RBAC de Earth2Worlds."""

    ADMIN = "admin"
    PROPIETARIO = "propietario"
    OPERADOR = "operador"


class Usuario(Base):
    """Tabla de usuarios de Earth2Worlds (Administradores, Propietarios y Operadores)."""

    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    rol = Column(Enum(RolEnum), default=RolEnum.PROPIETARIO, nullable=False)
    pais = Column(String(100), default="Argentina", nullable=False)
    provincia = Column(String(100), nullable=True)
    ciudad = Column(String(100), nullable=True)
    codigo_postal = Column(String(20), nullable=True)
    propietario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    campos_asignados = Column(JSON, default=list, nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow, nullable=False)

    operadores = relationship(
        "Usuario",
        backref=backref("propietario", remote_side=[id]),
    )
    campos = relationship(
        "Campo",
        back_populates="propietario",
        cascade="all, delete-orphan",
    )


class Campo(Base):
    """Tabla de campos/establecimientos productivos registrados en Earth2Worlds."""

    __tablename__ = "campos"

    id = Column(Integer, primary_key=True, index=True)
    propietario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    nombre_campo = Column(String(150), nullable=False)
    descripcion_ubicacion = Column(String(255), nullable=True)
    superficie_ha = Column(Float, nullable=True)
    geometria_geojson = Column(Text, nullable=True)  # Slot reservado para futuro módulo cartográfico
    configuracion_extra = Column(JSON, default=dict, nullable=True)  # Slot reservado para futuros módulos externos
    creado_en = Column(DateTime, default=datetime.utcnow, nullable=False)

    propietario = relationship("Usuario", back_populates="campos")
