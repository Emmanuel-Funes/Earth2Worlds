# Copernicus DEM - relieve como respaldo de NASADEM

**Rama:** `satelite-copernicus-dem-relieve-respaldo` · **Conector:** `rotaterra/fuentes/copdem.py` · **Specs:** `docs/specs/008-altimetria-nasadem.md`, `docs/specs/016-altimetria-copernicus-dem-respaldo.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector Copernicus DEM GLO-30 (ESA): altura, pendiente y ambientes del lote, respaldo de NASADEM (spec 016).

Mismas 7 variables y mismas reglas que NASADEM (spec 008), con el modelo de la ESA hecho con TanDEM-X.
Se lee sin credenciales del bucket público de AWS Open Data que distribuye los archivos de la ESA.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_copdem.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-copdem.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_copdem.py <lat> <lon> <desde> <hasta>` en la compu.
- No necesita claves.

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
