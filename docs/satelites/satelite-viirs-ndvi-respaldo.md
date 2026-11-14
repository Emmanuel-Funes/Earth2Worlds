# VIIRS - NDVI de 500 m como respaldo de HLS

**Rama:** `satelite-viirs-ndvi-respaldo` · **Conector:** `rotaterra/fuentes/viirs.py` · **Specs:** `docs/specs/011-ndvi-viirs-respaldo.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector VIIRS: NDVI de 500 m del lote, primer respaldo de HLS y continuidad de MODIS (spec 011).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_viirs.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-viirs.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_viirs.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
