"""Inicialización limpia e idempotente de earth2worlds.db (14/11/2026)."""

from datetime import datetime
import os

from app.auth import get_password_hash
from app.database import Base, SessionLocal, engine
from app.models import RolEnum, Usuario

FECHA_INICIO_PLATAFORMA = datetime(2026, 11, 14, 0, 0, 0)


def init_db() -> None:
    """Crea las tablas del esquema y el único usuario Administrador inicial de forma idempotente."""
    Base.metadata.create_all(bind=engine)

    admin_email = "admin@earth2worlds.com"
    admin_password = os.environ.get("ADMIN_PASSWORD", "NasaVM2026")

    db = SessionLocal()
    try:
        admin_existente = (
            db.query(Usuario)
            .filter((Usuario.email == admin_email) | (Usuario.rol == RolEnum.ADMIN))
            .first()
        )
        if not admin_existente:
            nuevo_admin = Usuario(
                nombre="Admin",
                apellido="Earth2Worlds",
                email=admin_email,
                password_hash=get_password_hash(admin_password),
                rol=RolEnum.ADMIN,
                pais="Argentina",
                provincia="San Luis",
                ciudad="Villa Mercedes",
                codigo_postal="5730",
                propietario_id=None,
                campos_asignados=[],
                creado_en=max(datetime.utcnow(), FECHA_INICIO_PLATAFORMA),
            )
            db.add(nuevo_admin)
            db.commit()
            db.refresh(nuevo_admin)
            print(
                f"[Earth2Worlds] Base de datos inicializada limpia (14/11/2026). "
                f"Administrador creado: {nuevo_admin.nombre} ({nuevo_admin.email})"
            )
        else:
            print(
                f"[Earth2Worlds] Base de datos verificada. "
                f"Administrador activo: {admin_existente.nombre} ({admin_existente.email})"
            )
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
