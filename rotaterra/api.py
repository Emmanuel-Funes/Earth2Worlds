"""API de Rotaterra: lo que la app consulta para recibir datos de cada lote."""

import hmac
import os
from datetime import date
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from sqlalchemy.engine import Engine

from rotaterra import base, consulta
from rotaterra.contrato import Observacion
from rotaterra.fuentes import registro
from rotaterra.geo import validar_poligono

# ---------- clave y origen permitidos: solo el frontend autorizado puede consultar (spec 022) ----------

_CLAVE = APIKeyHeader(name="X-API-Key", auto_error=False,
                      description="Clave de la API. Se carga en ROTATERRA_API_KEYS; nunca va en el código.")


def _lista(variable: str) -> list[str]:
    return [v.strip() for v in os.environ.get(variable, "").split(",") if v.strip()]


def verificar_clave(clave: str | None = Security(_CLAVE)) -> None:
    """Sin claves configuradas la API rechaza todo: nunca queda abierta por olvido."""
    validas = _lista("ROTATERRA_API_KEYS")
    if not validas:
        raise HTTPException(status_code=503, detail="La API no tiene una clave configurada")
    # Se recorren todas las claves con compare_digest para no dar pistas por el tiempo de respuesta.
    coincide = False
    for valida in validas:
        coincide |= clave is not None and hmac.compare_digest(clave.encode(), valida.encode())
    if not coincide:
        raise HTTPException(status_code=401, detail="Falta la clave o no es válida (encabezado X-API-Key)")


class CorsDelEntorno:
    """CORS con los orígenes de ROTATERRA_ORIGENES; sin orígenes, ningún navegador de otro sitio puede consultar."""

    def __init__(self, app):
        self.app = app
        self._cors: dict[tuple[str, ...], CORSMiddleware] = {}

    async def __call__(self, scope, receive, send):
        origenes = tuple(_lista("ROTATERRA_ORIGENES"))
        if scope["type"] != "http" or not origenes:
            await self.app(scope, receive, send)
            return
        if origenes not in self._cors:
            self._cors = {origenes: CORSMiddleware(self.app, allow_origins=list(origenes),
                                                   allow_methods=["GET", "POST"],
                                                   allow_headers=["X-API-Key", "Content-Type"])}
        await self._cors[origenes](scope, receive, send)


app = FastAPI(title="Rotaterra API", version="0.3.0", dependencies=[Depends(verificar_clave)])
app.add_middleware(CorsDelEntorno)


async def salud(_: Request) -> JSONResponse:
    """Único endpoint sin clave: dice que la API está viva, sin datos (para el servicio que la aloja)."""
    return JSONResponse({"ok": True})


app.add_route("/salud", salud, methods=["GET"], include_in_schema=False)


@lru_cache
def motor() -> Engine:
    return base.conectar()


# ---------- lo que usa la app: datos ya guardados, respuesta inmediata (spec 004) ----------

class LoteNuevo(BaseModel):
    id: str
    nombre: str
    poligono: dict


@app.get("/lotes")
def lotes(db: Engine = Depends(motor)) -> list[dict]:
    return base.listar_lotes(db)


@app.post("/lotes", status_code=201)
def alta_lote(lote: LoteNuevo, db: Engine = Depends(motor)) -> dict:
    try:
        validar_poligono(lote.poligono)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    return base.guardar_lote(db, lote.id, lote.nombre, lote.poligono)


def _lote_o_404(db: Engine, lote_id: str) -> dict:
    lote = base.obtener_lote(db, lote_id)
    if lote is None:
        raise HTTPException(status_code=404, detail=f"No existe el lote '{lote_id}'")
    return lote


@app.get("/lotes/{lote_id}/observaciones", response_model=list[Observacion])
def observaciones_guardadas(lote_id: str, variable: str | None = None, fuente: str | None = None,
                            desde: date | None = None, hasta: date | None = None, combinar: bool = False,
                            db: Engine = Depends(motor)) -> list[Observacion]:
    """combinar=true: una serie por variable, usando el respaldo solo donde falta la fuente principal."""
    _lote_o_404(db, lote_id)
    guardadas = base.leer_observaciones(db, lote_id, variable, fuente, desde, hasta)
    return base.combinar_fuentes(guardadas) if combinar else guardadas


@app.get("/lotes/{lote_id}/estado")
def estado_lote(lote_id: str, db: Engine = Depends(motor)) -> list[dict]:
    _lote_o_404(db, lote_id)
    return base.estado(db, lote_id)


# ---------- consulta en el momento con respaldos: la app la llama y espera (specs 010 y 012) ----------

@lru_cache
def conectados() -> registro.Conectados:
    return registro.descubrir()


LOTE_SIN_ID = "lote"


class PedidoConsulta(BaseModel):
    satelite: str
    poligono: dict = Field(description="El lote: GeoJSON Polygon en EPSG:4326 (longitud, latitud)")
    lote_id: str = Field(LOTE_SIN_ID, description="Opcional. Etiqueta libre que se copia en cada observación; "
                                                  "no se guarda ni se busca en ninguna base")
    desde: date
    hasta: date


class IntentoConsulta(BaseModel):
    satelite: str
    resultado: str
    filas: int = 0
    mensaje: str = ""


class RespuestaConsulta(BaseModel):
    fuente_usada: str
    observaciones: list[Observacion]
    intentos: list[IntentoConsulta]
    completada_con: list[str] = Field(default_factory=list,
                                      description="Respaldos del día que completaron los últimos días que la fuente "
                                                  "todavía no publicó (spec 043); cada observación dice su fuente")
    rellenada_con: list[str] = Field(default_factory=list,
                                     description="Respaldos que rellenaron huecos largos sin dato útil, de más detalle "
                                                 "a menos (spec 052); cada observación dice su fuente")


@app.get("/satelites")
def satelites(unidos: registro.Conectados = Depends(conectados)) -> list[dict]:
    """Satélites principales unidos a esta rama y sus respaldos, en el orden en que entran."""
    respaldos = registro.respaldos_en_orden(unidos.satelites)
    del_dia = registro.respaldos_en_orden(unidos.satelites, al_dia=True)
    return [{"satelite": s.nombre, "respaldos": [r.nombre for r in respaldos.get(s.nombre, [])],
             "del_dia": [r.nombre for r in del_dia.get(s.nombre, [])]}
            for s in unidos.satelites if not s.respaldo_de]


@app.post("/consulta", response_model=RespuestaConsulta)
def consultar(pedido: PedidoConsulta, unidos: registro.Conectados = Depends(conectados)) -> RespuestaConsulta:
    """Pide el período al satélite; si falla o no trae datos, responden sus respaldos en orden. Puede tardar minutos."""
    try:
        validar_poligono(pedido.poligono)
        lote = consulta.lote_para_consulta(pedido.lote_id, pedido.poligono)
        respuesta = consulta.consultar(lote, pedido.satelite, pedido.desde, pedido.hasta, unidos.satelites)
    except consulta.SateliteDesconocido:
        raise HTTPException(status_code=404, detail=f"No hay un satélite '{pedido.satelite}' unido. Ver GET /satelites.")
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    intentos = [IntentoConsulta(satelite=i.satelite, resultado=i.resultado, filas=i.filas, mensaje=i.mensaje)
                for i in respuesta.intentos]
    if respuesta.fuente_usada is None:
        sin_credenciales = all(i.sin_credenciales for i in respuesta.intentos if i.resultado == "error") \
            and any(i.sin_credenciales for i in respuesta.intentos)
        raise HTTPException(status_code=503 if sin_credenciales else 502,
                            detail={"mensaje": "Ni el satélite ni sus respaldos trajeron datos",
                                    "intentos": [i.model_dump() for i in intentos]})
    return RespuestaConsulta(fuente_usada=respuesta.fuente_usada, observaciones=respuesta.observaciones,
                             intentos=intentos, completada_con=respuesta.completada_con,
                             rellenada_con=respuesta.rellenada_con)


# Banco de semillas: archivo SQLite de solo lectura que viaja con la API (spec 057).
from rotaterra.semillas import rutas as rutas_semillas  # noqa: E402

app.include_router(rutas_semillas)


# Motor de recomendación para agrónomos: un lote y una campaña (spec 064).
from rotaterra.agronomos.rutas import router as rutas_agronomos  # noqa: E402

app.include_router(rutas_agronomos)


# Cada satélite unido a esta rama trae además su propio endpoint, sin respaldos (spec 009).

for _rutas in conectados().rutas:
    app.include_router(_rutas)
