"""Endpoint del motor de recomendación para agrónomos (spec 064)."""

import httpx
from fastapi import APIRouter, HTTPException

from rotaterra.agronomos.motor import PedidoAgronomos, recomendar
from rotaterra.rotacion.clima import POWER_DIARIO, parametros_power

router = APIRouter(tags=["Recomendación para agrónomos"])


@router.post("/agronomos/recomendacion")
def recomendacion(pedido: PedidoAgronomos) -> dict:
    """Para un lote y una campaña: cada cultivo (maíz de primera y tardío, soja, sorgo, maní, girasol) como
    "Recomendable", "Con cuidado" o "No recomendable", con cada regla de la ficha técnica, el dato del lote, el umbral
    y la fuente. Si no viene `power`, pide la serie diaria a NASA POWER y espera (tarda unos segundos)."""
    power = pedido.power
    if power is None:
        try:
            r = httpx.get(POWER_DIARIO, params=parametros_power(pedido.latitud, pedido.longitud, pedido.desde, pedido.hasta), timeout=120)
            r.raise_for_status()
            power = r.json()
        except httpx.HTTPError as error:
            raise HTTPException(status_code=502, detail=f"NASA POWER no respondió bien: {error}")
    try:
        return recomendar(pedido, power)
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=502, detail=f"La serie de NASA POWER no sirve: {error}")
