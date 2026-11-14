# MODIS - NDVI de 250 m como respaldo de HLS

**Rama:** `satelite-modis-ndvi-respaldo` · **Conector:** `rotaterra/fuentes/modis.py` · **Specs:** `docs/specs/007-ndvi-modis-respaldo.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector MODIS: NDVI de 250 m del lote, respaldo de HLS (spec 007).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_modis.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-modis.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_modis.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
