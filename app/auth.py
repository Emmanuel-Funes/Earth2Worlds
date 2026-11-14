"""Autenticación JWT HS256, hashing Bcrypt y dependencias RBAC de Earth2Worlds."""

from datetime import datetime, timedelta, timezone
import os
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RolEnum, Usuario

# Compatibilidad de metadatos para passlib sobre bcrypt >= 4.1 / Python 3.14
if not hasattr(bcrypt, "__about__"):
    bcrypt.__about__ = type("about", (), {"__version__": getattr(bcrypt, "__version__", "4.2.0")})()

JWT_SECRET_KEY = os.environ.get(
    "JWT_SECRET_KEY",
    "earth2worlds-jwt-secret-key-2026-11-14-san-luis-argentina",
)
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

bearer_scheme = HTTPBearer(auto_error=False)


def get_password_hash(password: str) -> str:
    """Genera un hash Bcrypt seguro a partir de una contraseña en texto plano."""
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica una contraseña en texto plano contra su hash Bcrypt almacenado."""
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8")[:72],
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crea un token JWT firmado con HS256 y expiración de 24 horas por defecto."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta is not None else timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    )
    to_encode.update({"exp": expire, "iss": "Earth2Worlds"})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    """Obtiene el usuario autenticado mediante el token Bearer JWT."""
    unauthorized_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autorizado. Inicia sesión en Earth2Worlds.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or not credentials.credentials:
        raise unauthorized_exc

    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            raise unauthorized_exc
        user_id = int(sub)
    except (JWTError, ValueError, TypeError):
        raise unauthorized_exc

    usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
    if usuario is None:
        raise unauthorized_exc
    return usuario


def require_admin(current_user: Usuario = Depends(get_current_user)) -> Usuario:
    """Exige que el usuario autenticado tenga rol ADMIN."""
    if current_user.rol != RolEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: se requieren privilegios de Administrador en Earth2Worlds.",
        )
    return current_user


def require_propietario_or_admin(current_user: Usuario = Depends(get_current_user)) -> Usuario:
    """Exige que el usuario autenticado tenga rol PROPIETARIO o ADMIN."""
    if current_user.rol not in (RolEnum.ADMIN, RolEnum.PROPIETARIO):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: los operadores tienen permisos de solo lectura.",
        )
    return current_user
