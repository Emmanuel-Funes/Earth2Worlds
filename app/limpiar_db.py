"""Script para limpiar la base de datos de usuarios de prueba en earth2worlds.db.
Conserva exclusivamente al usuario permanente Administrador (Admin / admin@earth2worlds.com).
"""

import sys
from app.database import SessionLocal
from app.models import Campo, RolEnum, TelemetriaHistorica, Usuario


def limpiar_usuarios_de_prueba() -> None:
    """Elimina todos los usuarios de prueba y sus campos asociados, manteniendo solo al Admin."""
    db = SessionLocal()
    try:
        # Identificar admin
        admin = (
            db.query(Usuario)
            .filter((Usuario.email == "admin@earth2worlds.com") | (Usuario.rol == RolEnum.ADMIN))
            .first()
        )
        if not admin:
            print("[Limpieza] Advertencia: No se encontró usuario Admin permanente.")
            return

        print(f"[Limpieza] Administrador preservado: ID {admin.id} - {admin.nombre} ({admin.email})")

        # Usuarios a eliminar
        usuarios_eliminar = (
            db.query(Usuario)
            .filter(Usuario.id != admin.id, Usuario.email != "admin@earth2worlds.com")
            .all()
        )
        ids_eliminar = [u.id for u in usuarios_eliminar]
        total_usuarios = len(usuarios_eliminar)

        if ids_eliminar:
            # Eliminar campos de usuarios que se van a eliminar
            campos_eliminar = db.query(Campo).filter(Campo.propietario_id.in_(ids_eliminar)).all()
            ids_campos = [c.id for c in campos_eliminar]
            total_campos = len(campos_eliminar)

            # Eliminar telemetría de esos campos si existe
            if ids_campos:
                db.query(TelemetriaHistorica).filter(TelemetriaHistorica.campo_id.in_(ids_campos)).delete(synchronize_session=False)

            # Eliminar los campos
            db.query(Campo).filter(Campo.propietario_id.in_(ids_eliminar)).delete(synchronize_session=False)

            # Eliminar los usuarios de prueba
            for u in usuarios_eliminar:
                db.delete(u)

            db.commit()
            print(f"[Limpieza] Se eliminaron {total_usuarios} usuarios de prueba y {total_campos} campos asociados.")
        else:
            print("[Limpieza] La base de datos ya está limpia. No hay usuarios de prueba que eliminar.")

        # Verificar estado final
        usuarios_restantes = db.query(Usuario).all()
        campos_restantes = db.query(Campo).all()
        print(f"[Limpieza] Estado final: {len(usuarios_restantes)} usuario(s) - {[u.email for u in usuarios_restantes]}")
        print(f"[Limpieza] Campos registrados: {len(campos_restantes)}")

    except Exception as e:
        db.rollback()
        print(f"[Limpieza] Error al limpiar la base de datos: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    limpiar_usuarios_de_prueba()
