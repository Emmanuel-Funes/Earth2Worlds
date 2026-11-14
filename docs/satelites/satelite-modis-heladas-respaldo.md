# MODIS LST nocturna - heladas como respaldo de VIIRS

**Rama:** `satelite-modis-heladas-respaldo` · **Conector:** `rotaterra/fuentes/modis_heladas.py` · **Specs:** `docs/specs/035-heladas-respaldo-modis.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector MODIS LST nocturna: respaldo de heladas de la NASA (spec 035).

Respaldo de VIIRS_LST (que hoy no tenía ninguno). La fuente es la temperatura de la **superficie**
de noche de MODIS: MOD11A1 (Terra) y MYD11A1 (Aqua), producto diario de 1 km (colección 6.1). Entra
solo en la consulta en vivo cuando VIIRS_LST (NOAA-20/21) no devuelve dato para el lote y las fechas.

Satélite independiente (spec 009): hace su propio pedido a la NASA y no importa a ningún otro satélite,
aunque comparta con VIIRS la grilla sinusoidal de 1 km (se repite acá a propósito). Da la temperatura de
la superficie (suelo/canopeo), no la del aire: una helada agronómica se decide con esto más el criterio
del productor. Ojo: MODIS está en fin de misión (Terra y Aqua se retiran), por eso es respaldo y no principal.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_modis_heladas.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-modis-heladas.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_modis_heladas.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
