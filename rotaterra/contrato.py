"""Contrato JSON común: el formato en que toda fuente de datos entrega sus valores a la app."""

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel

Fuente = Literal["HLS", "SMAP", "IMERG", "POWER", "ECOSTRESS", "NASADEM", "MODIS", "VIIRS", "MERRA2", "SENTINEL2", "SENTINEL3", "COPDEM",
                "GeoINTA", "GRACE", "CPC", "HWSD", "GLDAS", "SEPA_INTA", "GOES", "FLDAS", "ASTER", "PERSIANN", "MAGyP",
                "GEOS_FP", "IMERG_EARLY", "MODIS_NRT", "SMAP_NRT", "SISINTA", "NISAR", "NEX_GDDP", "GEDI", "productor"]
Calidad = Literal["buena", "dudosa", "descartada"]


class Observacion(BaseModel):
    lote_id: str
    fecha: date
    variable: str
    valor: Optional[float]
    unidad: str
    fuente: Fuente
    resolucion_m: int
    calidad: Calidad
    nota: str = ""
