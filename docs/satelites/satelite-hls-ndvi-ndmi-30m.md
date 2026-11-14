# HLS (Landsat + Sentinel-2) - NDVI y NDMI del lote a 30 m

**Rama:** `satelite-hls-ndvi-ndmi-30m` · **Conector:** `rotaterra/fuentes/hls.py` · **Specs:** `docs/specs/002-conector-hls-ndvi.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector HLS: NDVI y NDMI del lote a 30 m (spec 002).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_hls.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-hls.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_hls.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
