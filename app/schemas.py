"""Esquemas Pydantic v2 y validadores para la API de Earth2Worlds."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import RolEnum


def _validar_password_segura(v: str) -> str:
    if v is None:
        raise ValueError("La contraseña es obligatoria.")
    limpia = v.strip()
    if len(limpia) < 6:
        raise ValueError("La contraseña debe tener al menos 6 caracteres sin espacios vacíos.")
    if " " in limpia:
        raise ValueError("La contraseña no debe contener espacios en blanco.")
    return limpia


# ==============================================================================
# ESQUEMAS DE CAMPOS
# ==============================================================================


class CampoBase(BaseModel):
    nombre_campo: str = Field(..., min_length=2, max_length=150)
    descripcion_ubicacion: Optional[str] = Field(default=None, max_length=255)
    superficie_ha: Optional[float] = Field(default=None, ge=0)
    geometria_geojson: Optional[str] = None
    configuracion_extra: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @field_validator("nombre_campo")
    @classmethod
    def validar_nombre_campo(cls, v: str) -> str:
        limpio = v.strip()
        if len(limpio) < 2:
            raise ValueError("El nombre del campo debe tener al menos 2 caracteres.")
        return limpio


class CampoCreate(CampoBase):
    propietario_id: Optional[int] = None


class CampoUpdate(BaseModel):
    nombre_campo: Optional[str] = Field(default=None, min_length=2, max_length=150)
    descripcion_ubicacion: Optional[str] = Field(default=None, max_length=255)
    superficie_ha: Optional[float] = Field(default=None, ge=0)
    propietario_id: Optional[int] = None
    geometria_geojson: Optional[str] = None
    configuracion_extra: Optional[Dict[str, Any]] = None


class CampoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    propietario_id: int
    propietario_nombre: Optional[str] = None
    propietario_email: Optional[str] = None
    nombre_campo: str
    descripcion_ubicacion: Optional[str] = None
    superficie_ha: Optional[float] = None
    geometria_geojson: Optional[str] = None
    configuracion_extra: Optional[Dict[str, Any]] = None
    elevacion_msnm: Optional[float] = None
    pendiente_porcentaje: Optional[float] = None
    orientacion_escurrimiento: Optional[str] = None
    satelites_disponibles: List[str] = Field(default_factory=list)
    creado_en: datetime


# ==============================================================================
# ESQUEMAS DE USUARIOS Y AUTENTICACIÓN
# ==============================================================================


class LoginRequest(BaseModel):
    email_o_usuario: str = Field(..., min_length=2, max_length=150)
    password: str = Field(..., min_length=1)


class GuestLoginRequest(BaseModel):
    modo: str = Field(default="basico", description="Modo de sesión: 'basico' o 'avanzado'")


class PropietarioRegistro(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)
    apellido: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    pais: str = Field(default="Argentina", max_length=100)
    provincia: Optional[str] = Field(default=None, max_length=100)
    ciudad: Optional[str] = Field(default=None, max_length=100)
    codigo_postal: Optional[str] = Field(default=None, max_length=20)

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return _validar_password_segura(v)

    @field_validator("nombre", "apellido")
    @classmethod
    def check_no_vacio(cls, v: str) -> str:
        limpio = v.strip()
        if len(limpio) < 2:
            raise ValueError("El nombre y apellido deben tener al menos 2 caracteres.")
        return limpio


class OperadorCreacion(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)
    apellido: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    pais: str = Field(default="Argentina", max_length=100)
    provincia: Optional[str] = Field(default=None, max_length=100)
    ciudad: Optional[str] = Field(default=None, max_length=100)
    codigo_postal: Optional[str] = Field(default=None, max_length=20)
    propietario_id: Optional[int] = None
    campos_asignados: List[int] = Field(default_factory=list)

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return _validar_password_segura(v)


class AdminCreacion(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)
    apellido: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    rol: RolEnum = Field(default=RolEnum.PROPIETARIO)
    pais: str = Field(default="Argentina", max_length=100)
    provincia: Optional[str] = Field(default=None, max_length=100)
    ciudad: Optional[str] = Field(default=None, max_length=100)
    codigo_postal: Optional[str] = Field(default=None, max_length=20)
    propietario_id: Optional[int] = None
    campos_asignados: List[int] = Field(default_factory=list)

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return _validar_password_segura(v)


class UsuarioUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=100)
    apellido: Optional[str] = Field(default=None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    rol: Optional[RolEnum] = None
    pais: Optional[str] = Field(default=None, max_length=100)
    provincia: Optional[str] = Field(default=None, max_length=100)
    ciudad: Optional[str] = Field(default=None, max_length=100)
    codigo_postal: Optional[str] = Field(default=None, max_length=20)
    propietario_id: Optional[int] = None
    campos_asignados: Optional[List[int]] = None

    @field_validator("password")
    @classmethod
    def check_optional_password(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        return _validar_password_segura(v)


class AsignarCamposRequest(BaseModel):
    campos_ids: List[int] = Field(default_factory=list)


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    apellido: str
    email: str
    rol: RolEnum
    pais: str
    provincia: Optional[str] = None
    ciudad: Optional[str] = None
    codigo_postal: Optional[str] = None
    propietario_id: Optional[int] = None
    propietario_nombre: Optional[str] = None
    campos_asignados: List[int] = Field(default_factory=list)
    campos_asignados_detalle: Optional[List[CampoOut]] = None
    creado_en: datetime


class PropietarioDetalleOut(UsuarioOut):
    campos: List[CampoOut] = Field(default_factory=list)
    operadores: List[UsuarioOut] = Field(default_factory=list)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut


# ==============================================================================
# ESQUEMAS DE INTEGRACIÓN ROTATERRA (SATÉLITES, FUENTES Y CONSULTA)
# ==============================================================================


class ConsultaRotaterraRequest(BaseModel):
    satelite: Optional[str] = Field(default=None, max_length=60)
    satelites: Optional[List[str]] = None
    desde: date
    hasta: date
    campo_id: Optional[int] = None
    poligono: Optional[Dict[str, Any]] = None
    forzar_remoto: bool = False


class SateliteReconectarRequest(BaseModel):
    satelite: str = Field(..., min_length=1, max_length=60)
    campo_id: Optional[int] = None
    desde: Optional[date] = None
    hasta: Optional[date] = None


class EvaluarCultivoRequest(BaseModel):
    campo_id: int
    sistema_hidrico: str = "secano"
    objetivo: str = "margen"
    horizonte: int = 1
    textura_manual: Optional[str] = None
    ph_manual: Optional[float] = None
    profundidad_napa_m: Optional[float] = None
    cultivo_anterior: Optional[str] = None


