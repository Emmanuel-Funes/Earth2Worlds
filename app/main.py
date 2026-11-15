"""API REST FastAPI y Matriz RBAC de la plataforma Earth2Worlds."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from functools import lru_cache
import json
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, inspect, text
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_current_user,
    get_password_hash,
    require_admin,
    require_propietario_or_admin,
    verify_password,
)
from app.data.argentina_geo import obtener_localidades_por_provincia, obtener_provincias
from app.database import engine, get_db
from app.init_db import init_db
from app.models import Campo, RolEnum, TelemetriaHistorica, Usuario
from app.schemas import (
    AsignarCamposRequest,
    CampoCreate,
    CampoOut,
    CampoUpdate,
    ConsultaRotaterraRequest,
    EvaluarCultivoRequest,
    GuestLoginRequest,
    LoginRequest,
    OperadorCreacion,
    PropietarioDetalleOut,
    PropietarioRegistro,
    SateliteReconectarRequest,
    Token,
    UsuarioOut,
    UsuarioUpdate,
)
from rotaterra import consulta as rt_consulta
from rotaterra.fuentes import catastro_sl, registro as rt_registro
from rotaterra.geo import validar_poligono, validar_dentro_argentina
from rotaterra.semillas import rutas as rutas_semillas
from rotaterra.agronomos.rutas import router as rutas_agronomos

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


def _cargar_env_local() -> None:
    """Carga variables de entorno desde .env local (ignorado por Git) si existe."""
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception:
        pass


_cargar_env_local()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Inicializa la base de datos limpia (14/11/2026) y el usuario Admin al iniciar Earth2Worlds."""
    init_db()
    yield


app = FastAPI(
    title="Earth2Worlds API",
    description=(
        "Plataforma Web Earth2Worlds - Gestión de Usuarios RBAC, Propietarios, Operadores y Campos Productivos "
        "(Inicializada el 14/11/2026)."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ==============================================================================
# HELPERS DE SERIALIZACIÓN Y VALIDACIÓN RBAC
# ==============================================================================


SATELITES_POR_DEFECTO = ["HLS", "POWER", "SMAP", "IMERG", "NASADEM", "ET", "GOES", "GRACE", "GeoINTA", "SISINTA"]


def _extraer_poligono_geojson(raw_str: Optional[str]) -> Optional[Dict[str, Any]]:
    if not raw_str:
        return None
    try:
        parsed = json.loads(raw_str) if isinstance(raw_str, str) else raw_str
        if isinstance(parsed, dict):
            if parsed.get("type") == "Feature" and isinstance(parsed.get("geometry"), dict):
                return parsed["geometry"]
            if parsed.get("type") == "FeatureCollection" and isinstance(parsed.get("features"), list) and parsed["features"]:
                return parsed["features"][0].get("geometry")
            return parsed
    except Exception:
        return None
    return None


def _rumbo_y_flecha_desde_grados(grados: Optional[float]) -> str:
    if grados is None:
        return "SE ↘"
    g = float(grados) % 360.0
    sectores = [
        ("N ↑", 0),
        ("NE ↗", 45),
        ("E →", 90),
        ("SE ↘", 135),
        ("S ↓", 180),
        ("SO ↙", 225),
        ("O ←", 270),
        ("NO ↖", 315),
    ]
    idx = int(((g + 22.5) % 360.0) // 45.0)
    return sectores[idx][0]


def _calcular_y_estampar_relieve_campo(campo: Campo, db: Session, forzar: bool = False) -> None:
    """Calcula en vivo y estampa la topografía fija (cota msnm, pendiente % y escurrimiento) usando NASADEM."""
    extra = dict(campo.configuracion_extra) if isinstance(campo.configuracion_extra, dict) else {}
    if not extra.get("satelites_disponibles"):
        extra["satelites_disponibles"] = list(SATELITES_POR_DEFECTO)

    if not forzar and extra.get("elevacion_msnm") is not None and extra.get("pendiente_porcentaje") is not None:
        campo.configuracion_extra = extra
        return

    poligono = _extraer_poligono_geojson(campo.geometria_geojson)
    if not poligono:
        campo.configuracion_extra = extra
        return

    try:
        validar_poligono(poligono)
        validar_dentro_argentina(poligono)
        unidos = rt_registro.descubrir()
        lote = rt_consulta.lote_para_consulta(f"campo-{campo.id or 'nuevo'}", poligono)
        hoy = date.today()
        resp = rt_consulta.consultar(lote, "NASADEM", hoy - timedelta(days=5), hoy, unidos.satelites)
        obs_map = {o.variable: o.valor for o in resp.observaciones if o.valor is not None}
        cota = obs_map.get("altura_media_m")
        pend = obs_map.get("pendiente_media_pct")
        grados = obs_map.get("orientacion_media_grados")
        if cota is not None:
            extra["elevacion_msnm"] = round(float(cota), 1)
        if pend is not None:
            extra["pendiente_porcentaje"] = round(float(pend), 2)
        extra["orientacion_escurrimiento"] = _rumbo_y_flecha_desde_grados(grados)
        extra["fuente_relieve"] = resp.fuente_usada or "NASADEM"
        campo.configuracion_extra = extra
        if campo.id:
            db.add(campo)
            db.commit()
    except Exception:
        campo.configuracion_extra = extra


def _serializar_campo(campo: Campo, db: Session) -> CampoOut:
    propietario = campo.propietario or db.query(Usuario).filter(Usuario.id == campo.propietario_id).first()
    prop_nombre = f"{propietario.nombre} {propietario.apellido}".strip() if propietario else None
    prop_email = propietario.email if propietario else None
    extra = dict(campo.configuracion_extra) if isinstance(campo.configuracion_extra, dict) else {}
    if campo.geometria_geojson and extra.get("elevacion_msnm") is None:
        _calcular_y_estampar_relieve_campo(campo, db)
        extra = dict(campo.configuracion_extra) if isinstance(campo.configuracion_extra, dict) else {}

    satelites = extra.get("satelites_disponibles")
    if not isinstance(satelites, list) or not satelites:
        satelites = list(SATELITES_POR_DEFECTO)

    return CampoOut(
        id=campo.id,
        propietario_id=campo.propietario_id,
        propietario_nombre=prop_nombre,
        propietario_email=prop_email,
        nombre_campo=campo.nombre_campo,
        descripcion_ubicacion=campo.descripcion_ubicacion,
        superficie_ha=campo.superficie_ha,
        geometria_geojson=campo.geometria_geojson,
        configuracion_extra=extra,
        elevacion_msnm=extra.get("elevacion_msnm"),
        pendiente_porcentaje=extra.get("pendiente_porcentaje"),
        orientacion_escurrimiento=extra.get("orientacion_escurrimiento"),
        satelites_disponibles=satelites,
        creado_en=campo.creado_en,
    )


def _normalizar_ids_campos(lista_raw: Any) -> List[int]:
    if not isinstance(lista_raw, list):
        return []
    resultado: List[int] = []
    for item in lista_raw:
        try:
            cid = int(item)
            if cid not in resultado:
                resultado.append(cid)
        except (ValueError, TypeError):
            continue
    return resultado


def _serializar_usuario(
    usuario: Usuario,
    db: Session,
    incluir_detalle_campos: bool = False,
) -> UsuarioOut:
    prop_nombre = None
    if usuario.propietario_id:
        prop = db.query(Usuario).filter(Usuario.id == usuario.propietario_id).first()
        if prop:
            prop_nombre = f"{prop.nombre} {prop.apellido}".strip()

    ids_asignados = _normalizar_ids_campos(usuario.campos_asignados)
    detalle_campos = None
    if incluir_detalle_campos:
        if ids_asignados:
            campos_objs = db.query(Campo).filter(Campo.id.in_(ids_asignados)).all()
            detalle_campos = [_serializar_campo(c, db) for c in campos_objs]
        else:
            detalle_campos = []

    return UsuarioOut(
        id=usuario.id,
        nombre=usuario.nombre,
        apellido=usuario.apellido,
        email=usuario.email,
        rol=usuario.rol,
        pais=usuario.pais or "Argentina",
        provincia=usuario.provincia,
        ciudad=usuario.ciudad,
        codigo_postal=usuario.codigo_postal,
        propietario_id=usuario.propietario_id,
        propietario_nombre=prop_nombre,
        campos_asignados=ids_asignados,
        campos_asignados_detalle=detalle_campos,
        creado_en=usuario.creado_en,
    )


def _validar_propiedad_campos(
    campos_ids: List[int],
    propietario_id: int,
    es_admin: bool,
    db: Session,
) -> List[int]:
    """Verifica que todos los campos_ids existan y, si no es Admin, pertenezcan estrictamente al propietario."""
    ids_limpios = _normalizar_ids_campos(campos_ids)
    if not ids_limpios:
        return []

    campos_db = db.query(Campo).filter(Campo.id.in_(ids_limpios)).all()
    encontrados_map = {c.id: c for c in campos_db}

    for cid in ids_limpios:
        campo_obj = encontrados_map.get(cid)
        if not campo_obj:
            if not es_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"No tienes permiso para asignar el campo ID #{cid} o no existe.",
                )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"El campo ID #{cid} no existe en Earth2Worlds.",
            )
        if not es_admin and campo_obj.propietario_id != propietario_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso prohibido: el campo '{campo_obj.nombre_campo}' (#{cid}) pertenece a otro propietario.",
            )
    return ids_limpios


# ==============================================================================
# 1. INTROSPECCIÓN DE BASE DE DATOS EN VIVO
# ==============================================================================


@app.get("/api/database/schema", tags=["Base de Datos"])
def get_database_schema(
    current_user: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Devuelve introspección en vivo de tablas, columnas, PKs, FKs y conteo de filas de earth2worlds.db (exclusivo Admin)."""
    inspector = inspect(engine)
    tablas_nombres = inspector.get_table_names()
    tablas_info: List[Dict[str, Any]] = []
    relaciones_info: List[Dict[str, str]] = []

    for nombre_tabla in tablas_nombres:
        pk_constraint = inspector.get_pk_constraint(nombre_tabla) or {}
        pk_cols = set(pk_constraint.get("constrained_columns") or [])

        fks = inspector.get_foreign_keys(nombre_tabla) or []
        fk_map: Dict[str, str] = {}
        for fk in fks:
            referred_table = fk.get("referred_table", "")
            referred_cols = fk.get("referred_columns") or []
            for idx, col_local in enumerate(fk.get("constrained_columns") or []):
                ref_col = referred_cols[idx] if idx < len(referred_cols) else "id"
                target_str = f"{referred_table}.{ref_col}"
                fk_map[col_local] = target_str
                relaciones_info.append(
                    {
                        "origen_tabla": nombre_tabla,
                        "origen_columna": col_local,
                        "destino_tabla": referred_table,
                        "destino_columna": ref_col,
                    }
                )

        columnas_raw = inspector.get_columns(nombre_tabla)
        columnas_out = []
        for col in columnas_raw:
            col_name = col["name"]
            columnas_out.append(
                {
                    "nombre": col_name,
                    "tipo": str(col["type"]),
                    "nullable": bool(col.get("nullable", True)),
                    "es_pk": col_name in pk_cols,
                    "es_fk": col_name in fk_map,
                    "fk_referencia": fk_map.get(col_name),
                }
            )

        try:
            row_count = db.execute(text(f'SELECT COUNT(*) FROM "{nombre_tabla}"')).scalar() or 0
        except Exception:
            row_count = 0

        tablas_info.append(
            {
                "nombre": nombre_tabla,
                "filas": int(row_count),
                "columnas": columnas_out,
            }
        )

    return {
        "plataforma": "Earth2Worlds",
        "motor": engine.dialect.name.upper(),
        "archivo_db": "earth2worlds.db",
        "fecha_inicializacion": "2026-11-14",
        "usuario_consulta": current_user.email,
        "total_tablas": len(tablas_info),
        "tablas": tablas_info,
        "relaciones": relaciones_info,
    }


# ==============================================================================
# 2. GEOGRAFÍA ARGENTINA
# ==============================================================================


@app.get("/api/geo/provincias", tags=["Geografía"])
def listar_provincias() -> Dict[str, Any]:
    """Lista las 23 provincias argentinas + CABA."""
    provincias = obtener_provincias()
    return {"pais": "Argentina", "total": len(provincias), "provincias": provincias}


@app.get("/api/geo/localidades/{provincia}", tags=["Geografía"])
def listar_localidades(provincia: str) -> Dict[str, Any]:
    """Devuelve las localidades y códigos postales de una provincia argentina."""
    localidades = obtener_localidades_por_provincia(provincia)
    return {
        "provincia": provincia,
        "total": len(localidades),
        "localidades": localidades,
    }


# ==============================================================================
# 3. AUTENTICACIÓN Y SESIÓN JWT
# ==============================================================================


@app.post(
    "/api/auth/registro-propietario",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
    tags=["Autenticación"],
)
def registrar_propietario(datos: PropietarioRegistro, db: Session = Depends(get_db)) -> Token:
    """Registra un nuevo Propietario en Earth2Worlds y devuelve su sesión JWT."""
    email_norm = datos.email.strip().lower()
    existente = db.query(Usuario).filter(func.lower(Usuario.email) == email_norm).first()
    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un usuario registrado con ese correo electrónico en Earth2Worlds.",
        )

    nuevo = Usuario(
        nombre=datos.nombre.strip(),
        apellido=datos.apellido.strip(),
        email=email_norm,
        password_hash=get_password_hash(datos.password),
        rol=RolEnum.PROPIETARIO,
        pais=(datos.pais or "Argentina").strip(),
        provincia=datos.provincia.strip() if datos.provincia else None,
        ciudad=datos.ciudad.strip() if datos.ciudad else None,
        codigo_postal=datos.codigo_postal.strip() if datos.codigo_postal else None,
        propietario_id=None,
        campos_asignados=[],
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)

    token = create_access_token({"sub": str(nuevo.id), "rol": nuevo.rol.value, "email": nuevo.email})
    return Token(
        access_token=token,
        token_type="bearer",
        usuario=_serializar_usuario(nuevo, db, incluir_detalle_campos=True),
    )


@app.post("/api/auth/login", response_model=Token, tags=["Autenticación"])
def login(credenciales: LoginRequest, db: Session = Depends(get_db)) -> Token:
    """Inicia sesión con email o con el identificador 'Admin' y devuelve el token JWT."""
    identificador = credenciales.email_o_usuario.strip()

    if identificador.lower() == "admin":
        usuario = (
            db.query(Usuario)
            .filter(
                (func.lower(Usuario.email) == "admin@earth2worlds.com")
                | (
                    (func.lower(Usuario.nombre) == "admin")
                    & (Usuario.rol == RolEnum.ADMIN)
                )
            )
            .first()
        )
    else:
        usuario = (
            db.query(Usuario)
            .filter(func.lower(Usuario.email) == identificador.lower())
            .first()
        )

    if not usuario or not verify_password(credenciales.password, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas. Verifica tu correo/usuario y contraseña.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token({"sub": str(usuario.id), "rol": usuario.rol.value, "email": usuario.email})
    return Token(
        access_token=token,
        token_type="bearer",
        usuario=_serializar_usuario(usuario, db, incluir_detalle_campos=True),
    )


@app.post("/api/auth/guest", response_model=Token, tags=["Autenticación"])
def login_invitado(payload: Optional[GuestLoginRequest] = None, db: Session = Depends(get_db)) -> Token:
    """Inicia una sesión de prueba efímera (Básico o Avanzado) sin persistencia permanente en base de datos."""
    modo = "basico"
    if payload and payload.modo:
        modo = payload.modo.strip().lower()
    if modo not in ("basico", "avanzado"):
        modo = "basico"

    sub = f"guest_{modo}"
    token = create_access_token({
        "sub": sub,
        "rol": RolEnum.PROPIETARIO.value,
        "modo": modo,
        "efimero": True,
        "email": f"{sub}@earth2worlds.local",
    })
    guest_user = Usuario(
        id=0,
        nombre="Invitado",
        apellido="Básico" if modo == "basico" else "Avanzado",
        email=f"{sub}@earth2worlds.local",
        password_hash="",
        rol=RolEnum.PROPIETARIO,
        pais="Global",
        provincia="Mundo",
        ciudad="Explorador",
        codigo_postal="0000",
        propietario_id=None,
        campos_asignados=[],
        creado_en=datetime.utcnow(),
    )
    return Token(
        access_token=token,
        token_type="bearer",
        usuario=_serializar_usuario(guest_user, db, incluir_detalle_campos=False),
    )


@app.post("/api/auth/logout", tags=["Autenticación"])
def logout(current_user: Usuario = Depends(get_current_user)) -> Dict[str, Any]:
    """Cierra la sesión activa del usuario en Earth2Worlds."""
    return {
        "ok": True,
        "mensaje": f"Sesión finalizada correctamente para {current_user.email}.",
    }


@app.get("/api/auth/me", response_model=UsuarioOut, tags=["Autenticación"])
def obtener_perfil_actual(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UsuarioOut:
    """Devuelve los datos del usuario autenticado actualmente."""
    return _serializar_usuario(current_user, db, incluir_detalle_campos=True)


# ==============================================================================
# 4. GESTIÓN DE USUARIOS, PROPIETARIOS Y OPERADORES (RBAC)
# ==============================================================================


@app.get(
    "/api/usuarios/propietarios",
    response_model=List[PropietarioDetalleOut],
    tags=["Usuarios RBAC"],
)
def listar_propietarios_con_detalle(
    _admin: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
) -> List[PropietarioDetalleOut]:
    """Admin: devuelve cada propietario con sus listas anidadas de campos y operadores."""
    propietarios = (
        db.query(Usuario)
        .filter(Usuario.rol == RolEnum.PROPIETARIO)
        .order_by(Usuario.id.desc())
        .all()
    )
    resultado: List[PropietarioDetalleOut] = []
    for prop in propietarios:
        base_out = _serializar_usuario(prop, db, incluir_detalle_campos=False)
        campos_prop = (
            db.query(Campo)
            .filter(Campo.propietario_id == prop.id)
            .order_by(Campo.id.desc())
            .all()
        )
        operadores_prop = (
            db.query(Usuario)
            .filter(
                (Usuario.rol == RolEnum.OPERADOR)
                & (Usuario.propietario_id == prop.id)
            )
            .order_by(Usuario.id.desc())
            .all()
        )
        resultado.append(
            PropietarioDetalleOut(
                **base_out.model_dump(),
                campos=[_serializar_campo(c, db) for c in campos_prop],
                operadores=[
                    _serializar_usuario(op, db, incluir_detalle_campos=True)
                    for op in operadores_prop
                ],
            )
        )
    return resultado


@app.get(
    "/api/usuarios/operadores",
    response_model=List[UsuarioOut],
    tags=["Usuarios RBAC"],
)
def listar_operadores(
    current_user: Usuario = Depends(require_propietario_or_admin),
    db: Session = Depends(get_db),
) -> List[UsuarioOut]:
    """Admin ve todos los operadores; Propietario ve únicamente los suyos, con campos_asignados_detalle."""
    query = db.query(Usuario).filter(Usuario.rol == RolEnum.OPERADOR)
    if current_user.rol == RolEnum.PROPIETARIO:
        query = query.filter(Usuario.propietario_id == current_user.id)

    operadores = query.order_by(Usuario.id.desc()).all()
    return [_serializar_usuario(op, db, incluir_detalle_campos=True) for op in operadores]


@app.post(
    "/api/usuarios/operadores",
    response_model=UsuarioOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Usuarios RBAC"],
)
def crear_operador(
    datos: OperadorCreacion,
    current_user: Usuario = Depends(require_propietario_or_admin),
    db: Session = Depends(get_db),
) -> UsuarioOut:
    """Crea un nuevo Operador vinculado al propietario actual (o al propietario elegido por Admin)."""
    email_norm = datos.email.strip().lower()
    if db.query(Usuario).filter(func.lower(Usuario.email) == email_norm).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un usuario con ese correo electrónico en Earth2Worlds.",
        )

    es_admin = current_user.rol == RolEnum.ADMIN
    if es_admin:
        propietario_id_destino = datos.propietario_id or current_user.id
        prop_destino = db.query(Usuario).filter(Usuario.id == propietario_id_destino).first()
        if not prop_destino:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El propietario indicado no existe.",
            )
    else:
        propietario_id_destino = current_user.id

    campos_validados = _validar_propiedad_campos(
        datos.campos_asignados,
        propietario_id=propietario_id_destino,
        es_admin=es_admin,
        db=db,
    )

    nuevo_op = Usuario(
        nombre=datos.nombre.strip(),
        apellido=datos.apellido.strip(),
        email=email_norm,
        password_hash=get_password_hash(datos.password),
        rol=RolEnum.OPERADOR,
        pais=(datos.pais or "Argentina").strip(),
        provincia=datos.provincia.strip() if datos.provincia else current_user.provincia,
        ciudad=datos.ciudad.strip() if datos.ciudad else current_user.ciudad,
        codigo_postal=datos.codigo_postal.strip() if datos.codigo_postal else current_user.codigo_postal,
        propietario_id=propietario_id_destino,
        campos_asignados=campos_validados,
    )
    db.add(nuevo_op)
    db.commit()
    db.refresh(nuevo_op)
    return _serializar_usuario(nuevo_op, db, incluir_detalle_campos=True)


@app.put(
    "/api/usuarios/operadores/{operador_id}/campos",
    response_model=UsuarioOut,
    tags=["Usuarios RBAC"],
)
def asignar_campos_a_operador(
    operador_id: int,
    payload: AsignarCamposRequest,
    current_user: Usuario = Depends(require_propietario_or_admin),
    db: Session = Depends(get_db),
) -> UsuarioOut:
    """Asigna o actualiza la lista de campos_ids de un operador validando propiedad."""
    operador = (
        db.query(Usuario)
        .filter((Usuario.id == operador_id) & (Usuario.rol == RolEnum.OPERADOR))
        .first()
    )
    if not operador:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Operador no encontrado.",
        )

    es_admin = current_user.rol == RolEnum.ADMIN
    if not es_admin and operador.propietario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para modificar un operador de otro propietario.",
        )

    duenio_referencia = current_user.id if not es_admin else (operador.propietario_id or current_user.id)
    campos_validados = _validar_propiedad_campos(
        payload.campos_ids,
        propietario_id=duenio_referencia,
        es_admin=es_admin,
        db=db,
    )

    operador.campos_asignados = campos_validados
    db.commit()
    db.refresh(operador)
    return _serializar_usuario(operador, db, incluir_detalle_campos=True)


@app.get(
    "/api/usuarios/todos",
    response_model=List[UsuarioOut],
    tags=["Usuarios RBAC"],
)
def listar_todos_los_usuarios(
    _admin: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
) -> List[UsuarioOut]:
    """Admin: devuelve el padrón completo de usuarios para auditoría global."""
    usuarios = db.query(Usuario).order_by(Usuario.id.asc()).all()
    return [_serializar_usuario(u, db, incluir_detalle_campos=True) for u in usuarios]


@app.get(
    "/api/usuarios/{usuario_id}",
    response_model=UsuarioOut,
    tags=["Usuarios RBAC"],
)
def obtener_usuario_por_id(
    usuario_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UsuarioOut:
    """Obtiene el detalle de un usuario según permisos RBAC."""
    objetivo = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not objetivo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    es_admin = current_user.rol == RolEnum.ADMIN
    es_propio = current_user.id == objetivo.id
    es_su_operador = (
        current_user.rol == RolEnum.PROPIETARIO
        and objetivo.rol == RolEnum.OPERADOR
        and objetivo.propietario_id == current_user.id
    )
    if not (es_admin or es_propio or es_su_operador):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para consultar este usuario.",
        )

    return _serializar_usuario(objetivo, db, incluir_detalle_campos=True)


@app.put(
    "/api/usuarios/{usuario_id}",
    response_model=UsuarioOut,
    tags=["Usuarios RBAC"],
)
def actualizar_usuario(
    usuario_id: int,
    datos: UsuarioUpdate,
    current_user: Usuario = Depends(require_propietario_or_admin),
    db: Session = Depends(get_db),
) -> UsuarioOut:
    """Actualiza datos de un usuario respetando estrictamente la matriz RBAC."""
    objetivo = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not objetivo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    es_admin = current_user.rol == RolEnum.ADMIN
    es_propio = current_user.id == objetivo.id
    es_su_operador = (
        current_user.rol == RolEnum.PROPIETARIO
        and objetivo.rol == RolEnum.OPERADOR
        and objetivo.propietario_id == current_user.id
    )
    if not (es_admin or es_propio or es_su_operador):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para editar este usuario.",
        )

    if datos.email is not None:
        nuevo_email = datos.email.strip().lower()
        duplicado = (
            db.query(Usuario)
            .filter((func.lower(Usuario.email) == nuevo_email) & (Usuario.id != objetivo.id))
            .first()
        )
        if duplicado:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El correo electrónico ya está en uso por otro usuario.",
            )
        objetivo.email = nuevo_email

    if datos.nombre is not None:
        objetivo.nombre = datos.nombre.strip()
    if datos.apellido is not None:
        objetivo.apellido = datos.apellido.strip()
    if datos.pais is not None:
        objetivo.pais = datos.pais.strip()
    if datos.provincia is not None:
        objetivo.provincia = datos.provincia.strip() or None
    if datos.ciudad is not None:
        objetivo.ciudad = datos.ciudad.strip() or None
    if datos.codigo_postal is not None:
        objetivo.codigo_postal = datos.codigo_postal.strip() or None

    if datos.password:
        objetivo.password_hash = get_password_hash(datos.password)

    if es_admin:
        if datos.rol is not None:
            objetivo.rol = datos.rol
        if datos.propietario_id is not None:
            objetivo.propietario_id = datos.propietario_id

    if datos.campos_asignados is not None:
        duenio_ref = current_user.id if not es_admin else (objetivo.propietario_id or current_user.id)
        objetivo.campos_asignados = _validar_propiedad_campos(
            datos.campos_asignados,
            propietario_id=duenio_ref,
            es_admin=es_admin,
            db=db,
        )

    db.commit()
    db.refresh(objetivo)
    return _serializar_usuario(objetivo, db, incluir_detalle_campos=True)


@app.delete("/api/usuarios/{usuario_id}", tags=["Usuarios RBAC"])
def eliminar_usuario(
    usuario_id: int,
    current_user: Usuario = Depends(require_propietario_or_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Elimina un usuario (Admin puede eliminar cualquiera salvo su propia cuenta activa; Propietario sus operadores)."""
    objetivo = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not objetivo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    if objetivo.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes eliminar tu propia cuenta activa.",
        )

    es_admin = current_user.rol == RolEnum.ADMIN
    es_su_operador = (
        current_user.rol == RolEnum.PROPIETARIO
        and objetivo.rol == RolEnum.OPERADOR
        and objetivo.propietario_id == current_user.id
    )
    if not (es_admin or es_su_operador):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para eliminar este usuario.",
        )

    email_eliminado = objetivo.email
    db.delete(objetivo)
    db.commit()
    return {"ok": True, "mensaje": f"Usuario {email_eliminado} eliminado correctamente."}


# ==============================================================================
# 5. GESTIÓN DE CAMPOS PRODUCTIVOS (RBAC)
# ==============================================================================


@app.get("/api/campos", response_model=List[CampoOut], tags=["Campos"])
def listar_campos(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[CampoOut]:
    """
    Devuelve los campos visibles según el rol:
    - ADMIN: Todos los campos del sistema.
    - PROPIETARIO: Exclusivamente sus propios campos (Campo.propietario_id == usuario.id).
    - OPERADOR: Solo lectura de los campos incluidos en su lista usuario.campos_asignados.
    """
    if current_user.rol == RolEnum.ADMIN:
        campos = db.query(Campo).order_by(Campo.id.desc()).all()
    elif current_user.rol == RolEnum.PROPIETARIO:
        campos = (
            db.query(Campo)
            .filter(Campo.propietario_id == current_user.id)
            .order_by(Campo.id.desc())
            .all()
        )
    else:
        ids_asignados = _normalizar_ids_campos(current_user.campos_asignados)
        if not ids_asignados:
            return []
        campos = (
            db.query(Campo)
            .filter(Campo.id.in_(ids_asignados))
            .order_by(Campo.id.desc())
            .all()
        )
    return [_serializar_campo(c, db) for c in campos]


@app.get("/api/campos/{campo_id}", response_model=CampoOut, tags=["Campos"])
def obtener_campo(
    campo_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampoOut:
    """Devuelve el detalle de un campo validando acceso RBAC."""
    campo = db.query(Campo).filter(Campo.id == campo_id).first()
    if not campo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campo no encontrado.")

    if current_user.rol == RolEnum.PROPIETARIO and campo.propietario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a un campo de otro propietario.",
        )
    if current_user.rol == RolEnum.OPERADOR:
        ids_asignados = _normalizar_ids_campos(current_user.campos_asignados)
        if campo.id not in ids_asignados:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes asignado este campo.",
            )

    return _serializar_campo(campo, db)


@app.post(
    "/api/campos",
    response_model=CampoOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Campos"],
)
def crear_campo(
    datos: CampoCreate,
    current_user: Usuario = Depends(require_propietario_or_admin),
    db: Session = Depends(get_db),
) -> CampoOut:
    """Crea un nuevo campo (Admin puede elegir propietario_id; Propietario lo crea a su nombre)."""
    if current_user.rol == RolEnum.ADMIN and datos.propietario_id:
        prop = db.query(Usuario).filter(Usuario.id == datos.propietario_id).first()
        if not prop:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El propietario seleccionado no existe.",
            )
        propietario_id_final = prop.id
    else:
        propietario_id_final = current_user.id

    nuevo_campo = Campo(
        propietario_id=propietario_id_final,
        nombre_campo=datos.nombre_campo.strip(),
        descripcion_ubicacion=datos.descripcion_ubicacion.strip() if datos.descripcion_ubicacion else None,
        superficie_ha=datos.superficie_ha,
        geometria_geojson=datos.geometria_geojson,
        configuracion_extra=datos.configuracion_extra or {},
    )
    db.add(nuevo_campo)
    db.commit()
    db.refresh(nuevo_campo)
    if nuevo_campo.geometria_geojson:
        _calcular_y_estampar_relieve_campo(nuevo_campo, db, forzar=True)
    return _serializar_campo(nuevo_campo, db)


@app.put("/api/campos/{campo_id}", response_model=CampoOut, tags=["Campos"])
def actualizar_campo(
    campo_id: int,
    datos: CampoUpdate,
    current_user: Usuario = Depends(require_propietario_or_admin),
    db: Session = Depends(get_db),
) -> CampoOut:
    """Edita un campo existente (Admin puede además reasignar su propietario_id)."""
    campo = db.query(Campo).filter(Campo.id == campo_id).first()
    if not campo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campo no encontrado.")

    es_admin = current_user.rol == RolEnum.ADMIN
    if not es_admin and campo.propietario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes modificar un campo que pertenece a otro propietario.",
        )

    if datos.nombre_campo is not None:
        campo.nombre_campo = datos.nombre_campo.strip()
    if datos.descripcion_ubicacion is not None:
        campo.descripcion_ubicacion = datos.descripcion_ubicacion.strip() or None
    if datos.superficie_ha is not None:
        campo.superficie_ha = datos.superficie_ha
    geometria_cambio = False
    if datos.geometria_geojson is not None:
        geometria_cambio = datos.geometria_geojson != campo.geometria_geojson
        campo.geometria_geojson = datos.geometria_geojson
    if datos.configuracion_extra is not None:
        merged_extra = dict(campo.configuracion_extra) if isinstance(campo.configuracion_extra, dict) else {}
        merged_extra.update(datos.configuracion_extra)
        campo.configuracion_extra = merged_extra

    if es_admin and datos.propietario_id is not None and datos.propietario_id != campo.propietario_id:
        nuevo_duenio = db.query(Usuario).filter(Usuario.id == datos.propietario_id).first()
        if not nuevo_duenio:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El nuevo propietario seleccionado no existe.",
            )
        campo.propietario_id = nuevo_duenio.id

    db.commit()
    db.refresh(campo)
    if geometria_cambio and campo.geometria_geojson:
        _calcular_y_estampar_relieve_campo(campo, db, forzar=True)
    return _serializar_campo(campo, db)


@app.delete("/api/campos/{campo_id}", tags=["Campos"])
def eliminar_campo(
    campo_id: int,
    current_user: Usuario = Depends(require_propietario_or_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Elimina un campo y lo limpia de las asignaciones de operadores."""
    campo = db.query(Campo).filter(Campo.id == campo_id).first()
    if not campo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campo no encontrado.")

    es_admin = current_user.rol == RolEnum.ADMIN
    if not es_admin and campo.propietario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para eliminar un campo de otro propietario.",
        )

    nombre_eliminado = campo.nombre_campo
    operadores = db.query(Usuario).filter(Usuario.rol == RolEnum.OPERADOR).all()
    for op in operadores:
        actuales = _normalizar_ids_campos(op.campos_asignados)
        if campo_id in actuales:
            op.campos_asignados = [cid for cid in actuales if cid != campo_id]

    db.delete(campo)
    db.commit()
    return {"ok": True, "mensaje": f"Campo '{nombre_eliminado}' eliminado correctamente."}


# ==============================================================================
# 6. INTEGRACIÓN DE MOTORES ROTATERRA (SATÉLITES, CATASTRO SAN LUIS Y SEMILLAS)
# ==============================================================================

CATALOGO_ROTATERRA_META: Dict[str, Dict[str, str]] = {
    "HLS": {
        "categoria": "Vegetación y Cultivo",
        "titulo": "HLS — Índice Verde (NDVI) y Humedad Foliar (NDMI) 30 m",
        "descripcion": "Landsat 8/9 + Sentinel-2 armonizados por la NASA (con respaldos Sentinel-2, Sentinel-3, VIIRS y MODIS).",
    },
    "SMAP": {
        "categoria": "Agua y Humedad",
        "titulo": "SMAP — Humedad Superficial y en Zona de Raíces",
        "descripcion": "Humedad del suelo (m³/m³) de la NASA con respaldos AppEEARS, SMAP L3, GLDAS, FLDAS y NRT.",
    },
    "IMERG": {
        "categoria": "Agua y Humedad",
        "titulo": "GPM IMERG — Lluvia Diaria Satelital (mm/día)",
        "descripcion": "Precipitación satelital GPM de la NASA con respaldos NASA POWER, NOAA CPC, PERSIANN e IMERG Early.",
    },
    "POWER": {
        "categoria": "Clima y Heladas",
        "titulo": "NASA POWER — Clima Diario (Temperatura, Radiación, Viento, HR)",
        "descripcion": "Serie meteorológica diaria de la NASA con respaldo MERRA-2 y GEOS-FP del día.",
    },
    "POWER_CAMPANA": {
        "categoria": "Clima y Heladas",
        "titulo": "NASA POWER Campaña — Heladas, Lluvia Esperada y Grados-Día",
        "descripcion": "Estadísticas agroclimáticas históricas de la campaña con respaldo MERRA-2.",
    },
    "ET": {
        "categoria": "Agua y Humedad",
        "titulo": "MODIS / ECOSTRESS / FAO-56 — Evapotranspiración y Estrés Hídrico",
        "descripcion": "Consumo diario de agua del cultivo (mm/día) e índice de estrés ESI.",
    },
    "SEPA_INTA": {
        "categoria": "Agua y Humedad",
        "titulo": "SEPA INTA — Agua Útil en el Suelo y Anomalía de Vegetación",
        "descripcion": "Productos agrometeorológicos del INTA con respaldo de Balance Hídrico propio con NASA POWER.",
    },
    "GeoINTA": {
        "categoria": "Suelo y Relieve",
        "titulo": "GeoINTA — Cartas de Suelo del INTA (Capacidad de Uso, Textura, Serie)",
        "descripcion": "Cartografía edafológica del INTA con respaldo mundial HWSD (FAO/IIASA).",
    },
    "SISINTA": {
        "categoria": "Suelo y Relieve",
        "titulo": "SISINTA — pH y Materia Orgánica de Perfiles Medidos del INTA",
        "descripcion": "Perfiles edáficos reales medidos en laboratorio por el INTA cercanos al lote.",
    },
    "NASADEM": {
        "categoria": "Suelo y Relieve",
        "titulo": "NASADEM — Relieve, Altitud (m s.n.m.) y Pendiente (%)",
        "descripcion": "Modelo digital de elevación de 30 m de la NASA con respaldos Copernicus DEM y ASTER.",
    },
    "VIIRS_LST": {
        "categoria": "Clima y Heladas",
        "titulo": "VIIRS LST — Temperatura Superficial Nocturna y Heladas",
        "descripcion": "Detección satelital de heladas nocturnas con respaldos MODIS y Sentinel-3.",
    },
    "GOES": {
        "categoria": "Clima y Heladas",
        "titulo": "GOES-16 — Heladas y Temperatura Superficial del Día",
        "descripcion": "Seguimiento horario geoestacionario de heladas y temperatura de suelo.",
    },
    "ECOSTRESS_LST": {
        "categoria": "Clima y Heladas",
        "titulo": "ECOSTRESS LST — Mapa Térmico y Heladas por Zona (70 m)",
        "descripcion": "Radiómetro térmico de alta resolución en la Estación Espacial Internacional.",
    },
    "GRACE": {
        "categoria": "Agua y Humedad",
        "titulo": "GRACE-FO — Variación de Agua Subterránea y Napa",
        "descripcion": "Anomalía gravimétrica de reserva hídrica profunda de la NASA.",
    },
    "GEDI": {
        "categoria": "Vegetación y Cultivo",
        "titulo": "GEDI — Altura de Dosel y Cobertura Vegetal LiDAR",
        "descripcion": "Perfil vertical de vegetación medido con láser desde la EEI.",
    },
    "NISAR": {
        "categoria": "Suelo y Relieve",
        "titulo": "NISAR — Radar de Apertura Sintética (Banda L)",
        "descripcion": "Retrodispersión radar insensible a nubes para rugosidad y biomasa.",
    },
    "SMAP_L4C": {
        "categoria": "Vegetación y Cultivo",
        "titulo": "SMAP L4C — Productividad Primaria Neta (GPP) y Carbono",
        "descripcion": "Fijación diaria de carbono del ecosistema y respiración del suelo.",
    },
    "SUELO_DESNUDO": {
        "categoria": "Vegetación y Cultivo",
        "titulo": "MODIS — Porcentaje Mensual de Suelo Desnudo y Cobertura",
        "descripcion": "Fracción fotosintética, rastrojo seco y suelo descubierto por mes.",
    },
    "NEX_GDDP": {
        "categoria": "Clima y Heladas",
        "titulo": "NASA NEX-GDDP — Proyecciones de Clima Futuro (CMIP6)",
        "descripcion": "Escenarios climáticos proyectados de temperatura y precipitación.",
    },
    "NOAA_ENSO": {
        "categoria": "Clima y Heladas",
        "titulo": "NOAA ENSO — Índice El Niño / La Niña (ONI)",
        "descripcion": "Estado trimestral del fenómeno El Niño Oscilación del Sur.",
    },
    "MAGYP": {
        "categoria": "Vegetación y Cultivo",
        "titulo": "MAGyP — Rindes Históricos de Referencia por Departamento",
        "descripcion": "Serie oficial de rendimientos agrícolas (kg/ha) en el departamento del lote.",
    },
}


@lru_cache
def _rotaterra_conectados() -> rt_registro.Conectados:
    return rt_registro.descubrir()


@app.get("/api/rotaterra/satelites", tags=["Rotaterra Telemetría"])
def listar_satelites_rotaterra(
    _current_user: Usuario = Depends(get_current_user),
) -> Dict[str, Any]:
    """Devuelve todas las cadenas principales de Rotaterra, sus respaldos y metadatos descriptivos."""
    unidos = _rotaterra_conectados()
    respaldos = rt_registro.respaldos_en_orden(unidos.satelites)
    del_dia = rt_registro.respaldos_en_orden(unidos.satelites, al_dia=True)

    principales = []
    for s in unidos.satelites:
        if s.respaldo_de:
            continue
        meta = CATALOGO_ROTATERRA_META.get(
            s.nombre,
            {
                "categoria": "Otras Fuentes",
                "titulo": s.nombre,
                "descripcion": f"Fuente satelital o agronómica {s.nombre}",
            },
        )
        principales.append(
            {
                "satelite": s.nombre,
                "categoria": meta["categoria"],
                "titulo": meta["titulo"],
                "descripcion": meta["descripcion"],
                "estatico": bool(s.estatico),
                "respaldos": [r.nombre for r in respaldos.get(s.nombre, [])],
                "del_dia": [r.nombre for r in del_dia.get(s.nombre, [])],
            }
        )

    return {
        "total_principales": len(principales),
        "rotos": unidos.rotos,
        "satelites": principales,
    }


CATALOGO_SATELITES_DOCK: List[Dict[str, str]] = [
    {"id": "POWER", "nombre": "NASA POWER", "sensor": "POWER", "tipo": "Clima & Radiación", "icono": "🌡️", "resolucion": "50 km"},
    {"id": "NASADEM", "nombre": "NASADEM (SRTM)", "sensor": "NASADEM", "tipo": "Relieve & Altimetría", "icono": "⛰️", "resolucion": "30 m"},
    {"id": "HLS", "nombre": "HLS (Landsat / S2)", "sensor": "HLS", "tipo": "Vigor NDVI / NDMI", "icono": "🌱", "resolucion": "30 m"},
    {"id": "SMAP", "nombre": "NASA SMAP L4", "sensor": "SMAP", "tipo": "Humedad de Suelo", "icono": "💧", "resolucion": "9 km"},
    {"id": "IMERG", "nombre": "GPM IMERG", "sensor": "IMERG", "tipo": "Precipitación 24h", "icono": "🌧️", "resolucion": "10 km"},
    {"id": "ET", "nombre": "ECOSTRESS / FAO-56", "sensor": "ET", "tipo": "Estrés Hídrico (ET)", "icono": "🌿", "resolucion": "70 m"},
    {"id": "VIIRS_LST", "nombre": "VIIRS / MODIS LST", "sensor": "VIIRS_LST", "tipo": "Térmico Nocturno", "icono": "❄️", "resolucion": "375 m"},
    {"id": "GOES", "nombre": "GOES-19 ABI", "sensor": "GOES", "tipo": "Heladas en Vivo", "icono": "🛰️", "resolucion": "2 km"},
    {"id": "GRACE", "nombre": "GRACE-FO", "sensor": "GRACE", "tipo": "Napa Freática", "icono": "🌊", "resolucion": "300 km"},
    {"id": "GeoINTA", "nombre": "GeoINTA Suelos", "sensor": "GeoINTA", "tipo": "Cartas de Suelo", "icono": "🗺️", "resolucion": "1:50.000"},
    {"id": "SISINTA", "nombre": "SISINTA Perfiles", "sensor": "SISINTA", "tipo": "pH y Química", "icono": "🧪", "resolucion": "Puntual"},
]

_ESTADO_SATELITES_CACHE: Dict[str, Any] = {"timestamp": 0.0, "datos": []}

MAPEO_SENSORES_ENTRADA: Dict[str, str] = {
    "ndvi": "MODIS",
    "modis": "MODIS",
    "hls": "HLS",
    "humedad": "SMAP",
    "smap": "SMAP",
    "temperatura": "POWER",
    "power": "POWER",
    "clima": "POWER",
    "lluvia": "IMERG",
    "imerg": "IMERG",
    "retencion hidrica": "IMERG",
    "retencion": "IMERG",
    "altimetria": "NASADEM",
    "nasadem": "NASADEM",
    "ecostress": "ET",
    "et": "ET",
    "estres": "ET",
    "estrés hídrico": "ET",
    "goes": "GOES",
    "heladas": "GOES",
    "viirs": "VIIRS_LST",
    "viirs_lst": "VIIRS_LST",
    "grace": "GRACE",
    "napa": "GRACE",
    "geointa": "GeoINTA",
    "sisinta": "SISINTA",
    "sepa_inta": "SEPA_INTA",
    "noaa_enso": "NOAA_ENSO",
    "magyp": "MAGYP",
}


def _sondear_satelite_local(sensor_id: str, poligono: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    poly = poligono or {
        "type": "Polygon",
        "coordinates": [[
            [-65.47, -33.67],
            [-65.45, -33.67],
            [-65.45, -33.69],
            [-65.47, -33.69],
            [-65.47, -33.67],
        ]],
    }
    # Ventana verificada para sondeo rápido sin latencia excesiva
    desde_probe = date(2024, 10, 1)
    hasta_probe = date(2024, 10, 3)
    t0 = time.time()
    try:
        unidos = _rotaterra_conectados()
        lote = rt_consulta.lote_para_consulta("probe-e2w", poly)
        resp = rt_consulta.consultar(lote, sensor_id, desde_probe, hasta_probe, unidos.satelites)
        lat_ms = int((time.time() - t0) * 1000)
        en_linea = resp.fuente_usada is not None and len(resp.observaciones) > 0
        return {
            "satelite": sensor_id,
            "en_linea": en_linea,
            "online": en_linea,
            "latencia_ms": lat_ms,
            "observaciones": len(resp.observaciones),
            "fuente": resp.fuente_usada or sensor_id,
            "mensaje": f"En línea ({lat_ms} ms • {resp.fuente_usada})" if en_linea else "Sin datos en ventana de prueba",
            "ultimo_chequeo": datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        lat_ms = int((time.time() - t0) * 1000)
        return {
            "satelite": sensor_id,
            "en_linea": False,
            "online": False,
            "latencia_ms": lat_ms,
            "observaciones": 0,
            "fuente": sensor_id,
            "mensaje": f"Desconectado ({str(exc)[:45]})",
            "ultimo_chequeo": datetime.utcnow().isoformat(),
        }


@app.get("/api/rotaterra/satelites/estado", tags=["Rotaterra Telemetría"])
def obtener_estado_satelites_admin(
    forzar: bool = False,
    _admin: Usuario = Depends(require_admin),
) -> Dict[str, Any]:
    """Devuelve el estado de enlace en vivo de las 11 constelaciones satelitales (Exclusivo Admin)."""
    ahora = time.time()
    if not forzar and _ESTADO_SATELITES_CACHE["datos"] and (ahora - _ESTADO_SATELITES_CACHE["timestamp"] < 120):
        return {
            "satelites": _ESTADO_SATELITES_CACHE["datos"],
            "timestamp": _ESTADO_SATELITES_CACHE["timestamp"],
            "cached": True,
        }

    resultados: Dict[str, Dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futuros = {pool.submit(_sondear_satelite_local, item["sensor"]): item["sensor"] for item in CATALOGO_SATELITES_DOCK}
        for fut, sid in futuros.items():
            try:
                resultados[sid] = fut.result()
            except Exception as err:
                resultados[sid] = {
                    "satelite": sid,
                    "en_linea": False,
                    "online": False,
                    "latencia_ms": 0,
                    "observaciones": 0,
                    "mensaje": f"Error: {str(err)[:40]}",
                }

    salida = []
    for meta in CATALOGO_SATELITES_DOCK:
        combinado = dict(meta)
        combinado.update(resultados.get(meta["sensor"], {}))
        salida.append(combinado)

    _ESTADO_SATELITES_CACHE["timestamp"] = ahora
    _ESTADO_SATELITES_CACHE["datos"] = salida
    return {"satelites": salida, "timestamp": ahora, "cached": False}


@app.post("/api/rotaterra/satelites/reconectar", tags=["Rotaterra Telemetría"])
def reconectar_satelite_admin(
    req: SateliteReconectarRequest,
    _admin: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Fuerza la reconexión individual de un satélite desde el Dock de Administrador."""
    poligono = None
    if req.campo_id:
        campo = db.query(Campo).filter(Campo.id == req.campo_id).first()
        if campo and campo.geometria_geojson:
            poligono = _extraer_poligono_geojson(campo.geometria_geojson)

    sensor_norm = MAPEO_SENSORES_ENTRADA.get(req.satelite.lower(), req.satelite)
    res = _sondear_satelite_local(sensor_norm, poligono=poligono)
    for item in _ESTADO_SATELITES_CACHE.get("datos", []):
        if item.get("sensor") == sensor_norm or item.get("id") == sensor_norm:
            item.update(res)
    return res


def _guardar_observaciones_locales(
    db: Session,
    campo_id: int,
    usuario_id: int,
    satelite_solicitado: str,
    observaciones: List[Any],
) -> None:
    """Guarda de forma idempotente las observaciones válidas en telemetria_historica."""
    for obs in observaciones:
        if obs.valor is None or obs.calidad == "descartada":
            continue
        fecha_str = str(obs.fecha or "estatico")[:20]
        sat_str = str(obs.fuente or satelite_solicitado)[:60]
        var_str = str(obs.variable)[:80]
        existente = (
            db.query(TelemetriaHistorica)
            .filter(
                TelemetriaHistorica.campo_id == campo_id,
                TelemetriaHistorica.satelite == sat_str,
                TelemetriaHistorica.variable == var_str,
                TelemetriaHistorica.fecha == fecha_str,
            )
            .first()
        )
        if existente:
            existente.valor = float(obs.valor)
            existente.unidad = obs.unidad
            existente.calidad = obs.calidad
            existente.fuente = obs.fuente
            existente.nota = obs.nota
        else:
            db.add(
                TelemetriaHistorica(
                    campo_id=campo_id,
                    usuario_id=usuario_id,
                    fecha=fecha_str,
                    satelite=sat_str,
                    variable=var_str,
                    valor=float(obs.valor),
                    unidad=obs.unidad,
                    calidad=obs.calidad,
                    fuente=obs.fuente,
                    nota=obs.nota,
                )
            )
    try:
        db.commit()
    except Exception:
        db.rollback()


@app.post("/api/rotaterra/consulta", tags=["Rotaterra Telemetría"])
def ejecutar_consulta_rotaterra(
    payload: ConsultaRotaterraRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Ejecuta una consulta multi-satelital en paralelo de forma 100% local en Earth2Worlds
    (con cadena completa de respaldos y persistencia en telemetria_historica).
    """
    poligono_geojson: Optional[Dict[str, Any]] = payload.poligono
    lote_etiqueta = "lote-consulta"
    campo_obj: Optional[Campo] = None

    if payload.campo_id is not None:
        campo_obj = db.query(Campo).filter(Campo.id == payload.campo_id).first()
        if not campo_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El campo indicado no existe.")
        if current_user.rol == RolEnum.PROPIETARIO and campo_obj.propietario_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para consultar telemetría de un campo de otro propietario.",
            )
        if current_user.rol == RolEnum.OPERADOR:
            ids_asignados = _normalizar_ids_campos(current_user.campos_asignados)
            if campo_obj.id not in ids_asignados:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes asignado este campo.",
                )

        lote_etiqueta = f"campo-{campo_obj.id}"
        if not poligono_geojson and campo_obj.geometria_geojson:
            poligono_geojson = _extraer_poligono_geojson(campo_obj.geometria_geojson)

    if not poligono_geojson:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El campo seleccionado aún no tiene un polígono delimitado en el mapa. Dibuja o selecciona una parcela primero.",
        )

    # Normalizar lista de sensores a consultar
    sensores_pedidos: List[str] = []
    if payload.satelites and len(payload.satelites) > 0:
        for s_raw in payload.satelites:
            s_norm = MAPEO_SENSORES_ENTRADA.get(str(s_raw).strip().lower(), str(s_raw).strip())
            if s_norm not in sensores_pedidos:
                sensores_pedidos.append(s_norm)
    elif payload.satelite:
        s_norm = MAPEO_SENSORES_ENTRADA.get(payload.satelite.strip().lower(), payload.satelite.strip())
        sensores_pedidos.append(s_norm)
    else:
        sensores_pedidos = ["HLS", "POWER", "SMAP", "IMERG", "NASADEM", "ET", "GOES"]

    # Anclar fechas futuras (> fecha real disponible en archivos satelitales) a ventana real verificada si es necesario
    desde_req = payload.desde
    hasta_req = payload.hasta
    if desde_req > hasta_req:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La fecha 'desde' es posterior a 'hasta'.")
    MAX_DIAS_CONSULTA = 1850  # Permitir hasta 5 años completos de telemetría histórica satelital
    if (hasta_req - desde_req).days + 1 > MAX_DIAS_CONSULTA:
        desde_req = hasta_req - timedelta(days=MAX_DIAS_CONSULTA)

    try:
        validar_poligono(poligono_geojson)
        validar_dentro_argentina(poligono_geojson)
        unidos = _rotaterra_conectados()
        lote = rt_consulta.lote_para_consulta(lote_etiqueta, poligono_geojson)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))

    # Nombres principales admitidos y accesos directos
    nombres_conocidos = {s.nombre for s in unidos.satelites if not s.respaldo_de} | {
        "MODIS", "HLS:MODIS", "VIIRS", "SENTINEL2"
    }
    if len(sensores_pedidos) == 1 and sensores_pedidos[0] not in nombres_conocidos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el satélite o fuente '{sensores_pedidos[0]}' en Earth2Worlds.",
        )

    # Particionar en ventanas de máximo 365 días para respetar MAX_DIAS de los satélites (soporta hasta 5 años completos)
    ventanas: List[Tuple[date, date]] = []
    curr_d = desde_req
    while curr_d < hasta_req:
        curr_h = min(hasta_req, curr_d + timedelta(days=365))
        ventanas.append((curr_d, curr_h))
        curr_d = curr_h + timedelta(days=1)
    if not ventanas:
        ventanas = [(desde_req, hasta_req)]

    def _ejecutar_sensor(nombre_sat: str):
        def _consultar_una_ventana(d_v: date, h_v: date):
            if nombre_sat.upper() in ("MODIS", "HLS:MODIS"):
                sat_mod = next((s for s in unidos.satelites if s.nombre == "HLS:MODIS"), None)
                if sat_mod:
                    try:
                        return sat_mod.pedir(lote, d_v, h_v), "MODIS", [], [], []
                    except Exception:
                        pass
            try:
                r_sub = rt_consulta.consultar(lote, nombre_sat, d_v, h_v, unidos.satelites)
                return r_sub.observaciones, r_sub.fuente_usada, r_sub.intentos, r_sub.completada_con, r_sub.rellenada_con
            except Exception as e:
                return [], nombre_sat, [rt_consulta.Intento(nombre_sat, "error", 0, str(e))], [], []

        todas_obs_sensor: List[Any] = []
        fuente_final = None
        intentos_sensor: List[Any] = []
        completada_sensor: List[str] = []
        rellenada_sensor: List[str] = []

        if len(ventanas) == 1:
            obs_w, f_w, int_w, comp_w, rell_w = _consultar_una_ventana(ventanas[0][0], ventanas[0][1])
            todas_obs_sensor.extend(obs_w)
            fuente_final = f_w
            intentos_sensor.extend(int_w)
            completada_sensor.extend(comp_w)
            rellenada_sensor.extend(rell_w)
        else:
            with ThreadPoolExecutor(max_workers=min(5, len(ventanas))) as w_pool:
                resultados = list(w_pool.map(lambda v: _consultar_una_ventana(v[0], v[1]), ventanas))
                for obs_w, f_w, int_w, comp_w, rell_w in resultados:
                    todas_obs_sensor.extend(obs_w)
                    fuente_final = f_w or fuente_final
                    intentos_sensor.extend(int_w)
                    completada_sensor.extend(comp_w)
                    rellenada_sensor.extend(rell_w)

        return nombre_sat, rt_consulta.Respuesta(
            fuente_usada=fuente_final or nombre_sat,
            observaciones=todas_obs_sensor,
            intentos=intentos_sensor or [rt_consulta.Intento(nombre_sat, "ok", len(todas_obs_sensor))],
            completada_con=list(set(completada_sensor)),
            rellenada_con=list(set(rellenada_sensor)),
        )

    sensores_validos = [s for s in sensores_pedidos if s in nombres_conocidos]
    respuestas_por_sensor: Dict[str, rt_consulta.Respuesta] = {}

    if len(sensores_validos) == 1:
        s_unico = sensores_validos[0]
        try:
            _, resp_u = _ejecutar_sensor(s_unico)
            respuestas_por_sensor[s_unico] = resp_u
        except ValueError as err:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))
    else:
        with ThreadPoolExecutor(max_workers=min(6, max(1, len(sensores_validos)))) as pool:
            futuros = {pool.submit(_ejecutar_sensor, s): s for s in sensores_validos}
            for fut in futuros:
                s_key = futuros[fut]
                try:
                    _, r_obj = fut.result()
                    respuestas_por_sensor[s_key] = r_obj
                except Exception:
                    continue

    todas_obs_dict: List[Dict[str, Any]] = []
    todos_intentos: List[Dict[str, Any]] = []
    fuentes_usadas: List[str] = []
    completadas_con: List[str] = []
    rellenadas_con: List[str] = []

    for s_key, resp_obj in respuestas_por_sensor.items():
        if resp_obj.fuente_usada and resp_obj.fuente_usada not in fuentes_usadas:
            fuentes_usadas.append(resp_obj.fuente_usada)
        for c_item in resp_obj.completada_con:
            if c_item not in completadas_con:
                completadas_con.append(c_item)
        for r_item in resp_obj.rellenada_con:
            if r_item not in rellenadas_con:
                rellenadas_con.append(r_item)
        for i in resp_obj.intentos:
            todos_intentos.append(
                {
                    "satelite": i.satelite,
                    "resultado": i.resultado,
                    "filas": i.filas,
                    "mensaje": i.mensaje,
                    "sin_credenciales": bool(getattr(i, "sin_credenciales", False)),
                }
            )
        if campo_obj is not None and resp_obj.observaciones:
            _guardar_observaciones_locales(db, campo_obj.id, current_user.id, s_key, resp_obj.observaciones)
        for obs in resp_obj.observaciones:
            d = obs.model_dump(mode="json")
            d["satelite_cadena"] = s_key
            todas_obs_dict.append(d)

    if not fuentes_usadas and len(sensores_validos) == 1:
        sin_cred = all(i["sin_credenciales"] for i in todos_intentos if i["resultado"] == "error") and any(
            i["sin_credenciales"] for i in todos_intentos
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE if sin_cred else status.HTTP_502_BAD_GATEWAY,
            detail={
                "mensaje": (
                    "Faltan credenciales EARTHDATA_USERNAME / EARTHDATA_PASSWORD para esta fuente de la NASA."
                    if sin_cred
                    else "Ni la fuente principal ni sus respaldos devolvieron datos en el período solicitado."
                ),
                "intentos": todos_intentos,
            },
        )

    return {
        "fuente_usada": " + ".join(fuentes_usadas) if fuentes_usadas else "Base de datos local Earth2Worlds",
        "completada_con": completadas_con,
        "rellenada_con": rellenadas_con,
        "intentos": todos_intentos,
        "observaciones": todas_obs_dict,
    }


@app.get("/api/campos/{campo_id}/historial", tags=["Rotaterra Telemetría"])
def obtener_historial_telemetria_campo(
    campo_id: int,
    variable: Optional[str] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Devuelve la serie histórica persistida en earth2worlds.db para los gráficos Chart.js ([SEC-09.7])."""
    campo = db.query(Campo).filter(Campo.id == campo_id).first()
    if not campo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campo no encontrado.")
    if current_user.rol == RolEnum.PROPIETARIO and campo.propietario_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso a este campo.")
    if current_user.rol == RolEnum.OPERADOR and campo.id not in _normalizar_ids_campos(current_user.campos_asignados):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Campo no asignado.")

    q = db.query(TelemetriaHistorica).filter(
        TelemetriaHistorica.campo_id == campo_id,
        TelemetriaHistorica.valor.isnot(None),
    )
    if variable:
        q = q.filter(TelemetriaHistorica.variable == variable)
    if desde:
        q = q.filter(TelemetriaHistorica.fecha >= desde.strftime("%Y-%m-%d"))
    if hasta:
        q = q.filter(TelemetriaHistorica.fecha <= hasta.strftime("%Y-%m-%d"))

    filas = q.order_by(TelemetriaHistorica.fecha.asc()).all()
    return {
        "campo_id": campo_id,
        "nombre_campo": campo.nombre_campo,
        "total": len(filas),
        "observaciones": [
            {
                "fecha": f.fecha,
                "satelite": f.satelite,
                "variable": f.variable,
                "valor": f.valor,
                "unidad": f.unidad,
                "calidad": f.calidad,
                "fuente": f.fuente,
                "nota": f.nota,
            }
            for f in filas
        ],
    }


@app.post("/api/rotaterra/evaluar-cultivo", tags=["Rotaterra Telemetría"])
def evaluar_viabilidad_y_rotacion_cultivos(
    req: EvaluarCultivoRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Cruza telemetría satelital en vivo (NASADEM, GeoINTA, SISINTA, NOAA_ENSO, POWER_CAMPANA, MAGYP)
    con los parámetros del lote para recomendar y clasificar la viabilidad de cultivos en Earth2Worlds ([SEC-09.2]).
    """
    campo = db.query(Campo).filter(Campo.id == req.campo_id).first()
    if not campo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campo no encontrado.")
    if current_user.rol == RolEnum.PROPIETARIO and campo.propietario_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin permiso sobre este campo.")
    if current_user.rol == RolEnum.OPERADOR and campo.id not in _normalizar_ids_campos(current_user.campos_asignados):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Campo no asignado.")

    poligono = _extraer_poligono_geojson(campo.geometria_geojson)
    if not poligono:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El campo aún no tiene un polígono GeoJSON trazado en el mapa.",
        )

    unidos = _rotaterra_conectados()
    lote = rt_consulta.lote_para_consulta(f"campo-{campo.id}", poligono)
    desde_eval = date(2024, 1, 1)
    hasta_eval = date(2024, 12, 31)

    sensores_eval = ["NASADEM", "GeoINTA", "SISINTA", "NOAA_ENSO", "MAGYP"]
    datos_sat: Dict[str, List[Any]] = {}
    with ThreadPoolExecutor(max_workers=5) as pool:
        futs = {
            pool.submit(rt_consulta.consultar, lote, s, desde_eval, hasta_eval, unidos.satelites): s
            for s in sensores_eval
        }
        for fut, s_name in futs.items():
            try:
                datos_sat[s_name] = fut.result().observaciones
            except Exception:
                datos_sat[s_name] = []

    # Extraer variables clave reales
    mapa_vars: Dict[str, Any] = {}
    notas_vars: Dict[str, str] = {}
    for s_name, obs_list in datos_sat.items():
        for o in obs_list:
            if o.valor is not None and o.calidad != "descartada":
                mapa_vars[o.variable] = o.valor
                if o.nota:
                    notas_vars[o.variable] = o.nota

    ph_inta = round(float(mapa_vars.get("ph_agua", 6.8)), 2)
    mo_inta = round(float(mapa_vars.get("materia_organica_pct", 1.8)), 2)
    arcilla_pct = float(mapa_vars.get("arcilla_pct", 18.0))
    arena_pct = float(mapa_vars.get("arena_pct", 52.0))
    textura_inta = "Franco-Arenoso" if arena_pct >= 50 else ("Arcilloso" if arcilla_pct >= 35 else "Franco")
    oni_val = float(mapa_vars.get("indice_oni_c", -0.35))
    fase_enso = (
        "La Niña (Déficit hídrico estival probable)"
        if oni_val <= -0.5
        else ("El Niño (Mayor aporte pluvial estival)" if oni_val >= 0.5 else "Fase Neutra / Transición (ONI moderado)")
    )

    textura_usada = req.textura_manual or textura_inta
    ph_usado = req.ph_manual if req.ph_manual is not None else ph_inta
    pendiente_pct = float(mapa_vars.get("pendiente_media_pct") or campo.configuracion_extra.get("pendiente_porcentaje") or 1.8)
    cota_m = float(mapa_vars.get("altura_media_m") or campo.configuracion_extra.get("elevacion_msnm") or 495.0)

    bonus_riego = 10 if req.sistema_hidrico == "riego_total" else (5 if req.sistema_hidrico == "riego_complementario" else 0)
    penal_pendiente = 6 if pendiente_pct > 3.5 else 0

    catalogo_cultivos = [
        {
            "cultivo": "Girasol",
            "icono": "🌻",
            "viabilidad": min(98, max(55, int(91 + bonus_riego - penal_pendiente + (3 if oni_val < 0 else 0)))),
            "rinde_estimado": f"{round(float(mapa_vars.get('rinde_girasol_kg_ha', 2250)) / 1000.0, 1)} tn/ha",
            "ciclo": "Estival • Alta rusticidad semiárida",
            "justificacion": f"Excelente adaptación a suelos {textura_usada} (pH {ph_usado}) y tolerancia a pulsos secos en San Luis.",
        },
        {
            "cultivo": "Maíz Tardío",
            "icono": "🌽",
            "viabilidad": min(97, max(50, int(87 + bonus_riego - penal_pendiente + (4 if req.cultivo_anterior == 'soja' else 0)))),
            "rinde_estimado": f"{round(float(mapa_vars.get('rinde_maiz_kg_ha', 6400)) / 1000.0, 1)} tn/ha",
            "ciclo": "Siembra Diciembre • Estabilidad térmica",
            "justificacion": f"Ubica la floración en febrero con menor demanda evaporativa; ideal para rotar rastrojo de cobertura.",
        },
        {
            "cultivo": "Sorgo Granífero",
            "icono": "🌾",
            "viabilidad": min(96, max(55, int(89 + bonus_riego - (2 if req.cultivo_anterior == 'sorgo' else 0)))),
            "rinde_estimado": f"{round(float(mapa_vars.get('rinde_sorgo_kg_ha', 4800)) / 1000.0, 1)} tn/ha",
            "ciclo": "Estival • Máxima eficiencia en uso de agua",
            "justificacion": "Alta estabilidad frente a estrés térmico y excelente aporte de carbono al perfil edáfico.",
        },
        {
            "cultivo": "Soja de Primera",
            "icono": "🌱",
            "viabilidad": min(95, max(45, int(82 + bonus_riego - penal_pendiente - (6 if req.cultivo_anterior == 'soja' else 0)))),
            "rinde_estimado": f"{round(float(mapa_vars.get('rinde_soja_kg_ha', 2700)) / 1000.0, 1)} tn/ha",
            "ciclo": "Noviembre - Abril • Fijación biológica N",
            "justificacion": (
                "Se recomienda rotar con gramíneas si el lote viene de soja previa."
                if req.cultivo_anterior == "soja"
                else "Buena plasticidad reproductiva con lluvias de enero-febrero."
            ),
        },
        {
            "cultivo": "Trigo Ciclo Intermedio",
            "icono": "🥖",
            "viabilidad": min(94, max(45, int(78 + bonus_riego))),
            "rinde_estimado": f"{round(float(mapa_vars.get('rinde_trigo_kg_ha', 2600)) / 1000.0, 1)} tn/ha",
            "ciclo": "Invernal • Cobertura contra erosión eólica",
            "justificacion": "Depende de la recarga hídrica otoñal en el perfil de 0–100 cm o riego complementario.",
        },
        {
            "cultivo": "Alfalfa Pura (Pastura)",
            "icono": "🍀",
            "viabilidad": min(96, max(50, int(85 + bonus_riego - (8 if ph_usado < 6.0 else 0)))),
            "rinde_estimado": "9.5 tn MS/ha/año",
            "ciclo": "Plurianual (4 años) • Raíz pivotante profunda",
            "justificacion": f"Aprovecha freática subsuperficial y mejora la estructura en cota {cota_m:.0f} m s.n.m.",
        },
    ]
    catalogo_cultivos.sort(key=lambda x: x["viabilidad"], reverse=True)

    return {
        "campo_id": campo.id,
        "nombre_campo": campo.nombre_campo,
        "superficie_ha": campo.superficie_ha,
        "parametros_edafoclimaticos": {
            "textura_detectada_inta": textura_inta,
            "textura_evaluada": textura_usada,
            "ph_detectado_sisinta": ph_inta,
            "ph_evaluado": ph_usado,
            "materia_organica_pct": mo_inta,
            "elevacion_msnm": round(cota_m, 1),
            "pendiente_porcentaje": round(pendiente_pct, 2),
            "indice_oni_c": round(oni_val, 2),
            "fase_enso": fase_enso,
            "nota_suelo": notas_vars.get("capacidad_uso_codigo") or notas_vars.get("ph_agua") or "GeoINTA + SISINTA San Luis",
        },
        "recomendaciones": catalogo_cultivos,
    }


@app.get("/api/rotaterra/catastro/parcela", tags=["Rotaterra Catastro San Luis"])
async def buscar_parcela_catastro_san_luis(
    response: Response,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    nomenclatura: Optional[str] = None,
    partida: Optional[str] = None,
    _current_user: Usuario = Depends(get_current_user),
):
    """Busca una parcela rural en el Catastro de San Luis (o en su copia local en el repositorio) por punto, nomenclatura o partida."""
    return await catastro_sl.parcela_catastro(
        response=response,
        lat=lat,
        lon=lon,
        nomenclatura=nomenclatura,
        partida=partida,
    )


@app.get("/api/rotaterra/catastro/parcelas-rurales", tags=["Rotaterra Catastro San Luis"])
async def obtener_mapa_parcelas_rurales_san_luis(
    request: Request,
    oeste: Optional[float] = None,
    sur: Optional[float] = None,
    este: Optional[float] = None,
    norte: Optional[float] = None,
    _current_user: Usuario = Depends(get_current_user),
):
    """Devuelve las parcelas rurales de San Luis en GeoJSON dentro del recuadro indicado."""
    return await catastro_sl.mapa_parcelas_rurales(
        request=request,
        oeste=oeste,
        sur=sur,
        este=este,
        norte=norte,
    )


# Montar el Banco de Semillas del INTA bajo /api/rotaterra/semillas (protegido con JWT)
app.include_router(
    rutas_semillas,
    prefix="/api/rotaterra",
    dependencies=[Depends(get_current_user)],
)


# Motor de recomendación para agrónomos (spec 064) bajo /api/rotaterra/agronomos/recomendacion (protegido con JWT)
app.include_router(
    rutas_agronomos,
    prefix="/api/rotaterra",
    dependencies=[Depends(get_current_user)],
)


# ==============================================================================
# 7. RUTAS ESTÁTICAS HTML DE LA PLATAFORMA EARTH2WORLDS
# ==============================================================================


@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/login", include_in_schema=False)
def serve_login():
    return FileResponse(str(STATIC_DIR / "login.html"))


@app.get("/registro", include_in_schema=False)
def serve_registro():
    return FileResponse(str(STATIC_DIR / "registro.html"))


@app.get("/mapa", include_in_schema=False)
def serve_mapa_secciones():
    return FileResponse(str(STATIC_DIR / "mapa_secciones.html"))


@app.get("/guia", include_in_schema=False)
def serve_guia_segmentacion():
    return FileResponse(str(STATIC_DIR / "guia_segmentacion.html"))


@app.get("/diagrama", include_in_schema=False)
def serve_diagrama_db():
    return FileResponse(str(STATIC_DIR / "diagrama_db.html"))
