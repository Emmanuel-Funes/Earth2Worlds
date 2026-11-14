# Sentinel-3 SLSTR - heladas como segundo respaldo de VIIRS

**Rama:** `satelite-sentinel3-heladas-respaldo` · **Conector:** `rotaterra/fuentes/sentinel3_heladas.py` · **Specs:** `docs/specs/051-heladas-respaldo-sentinel3.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector Sentinel-3 SLSTR LST nocturna: segundo respaldo de heladas, después de MODIS (spec 051).

Respaldo de VIIRS_LST (variable temp_sup_min_c). La fuente es el producto oficial de temperatura de la
**superficie** de la ESA, SL_2_LST (SLSTR de Sentinel-3A y 3B, 1 km), que solo publica el portal
Copernicus Data Space Ecosystem (la NASA no lo redistribuye). Pide una cuenta gratis de Copernicus:
COPERNICUS_USERNAME / COPERNICUS_PASSWORD como variables de entorno o secrets, nunca en el código.

Satélite independiente (spec 009): no importa a ningún otro satélite. Da la temperatura de la superficie
(suelo/canopeo), no la del aire: la helada agronómica se decide con esto más el criterio del productor.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_sentinel3_heladas.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-sentinel3-heladas.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_sentinel3_heladas.py <lat> <lon> <desde> <hasta>` en la compu.
- No necesita claves.

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
