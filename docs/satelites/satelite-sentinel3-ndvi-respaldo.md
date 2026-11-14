# Sentinel-3 - NDVI diario de 300 m como respaldo de HLS

**Rama:** `satelite-sentinel3-ndvi-respaldo` · **Conector:** `rotaterra/fuentes/sentinel3.py` · **Specs:** `docs/specs/050-ndvi-respaldo-sentinel3.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector Sentinel-3 (ESA): NDVI diario de 300 m del lote, respaldo de HLS entre Sentinel-2 y VIIRS (spec 050).

Producto SYN L2 (Synergy OLCI + SLSTR: reflectancia de superficie sobre tierra) de Sentinel-3A y 3B, que la
NASA redistribuye en LAADS DAAC con la misma cuenta de Earthdata. Cada pasada es un .zip de 350-900 MB con
NetCDF guardados sin comprimir adentro: se leen por HTTP solo los pedazos que tocan al lote (~5 MB por pasada).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_sentinel3.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-sentinel3.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_sentinel3.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
