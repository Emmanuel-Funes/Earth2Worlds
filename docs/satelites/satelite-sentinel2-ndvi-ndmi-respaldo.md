# Sentinel-2 - NDVI 10 m y NDMI 20 m como respaldo de HLS

**Rama:** `satelite-sentinel2-ndvi-ndmi-respaldo` · **Conector:** `rotaterra/fuentes/sentinel2.py` · **Specs:** `docs/specs/014-ndvi-ndmi-sentinel2-respaldo.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector Sentinel-2 L2A (ESA): NDVI a 10 m y NDMI a 20 m, primer respaldo de HLS (spec 014).

Datos de la ESA/Copernicus distribuidos como COG públicos en AWS Open Data y catalogados en el STAC
público Earth Search de Element 84. No pide credenciales.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_sentinel2.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-sentinel2.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_sentinel2.py <lat> <lon> <desde> <hasta>` en la compu.
- No necesita claves.

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
