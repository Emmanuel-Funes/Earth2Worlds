# NOAA CPC - lluvia de pluviómetros como respaldo de IMERG

**Rama:** `fuente-noaa-cpc-lluvia-respaldo` · **Conector:** `rotaterra/fuentes/cpc_lluvia.py` · **Specs:** `docs/specs/029-lluvia-respaldo-cpc.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Segundo respaldo de la lluvia de IMERG con NOAA CPC Global Unified gauge-based (spec 029).

Satélite independiente (spec 009): baja su propio archivo anual de NOAA y no usa otros satélites.
NOAA es una de las agencias socias de la NASA permitidas (spec 008). A diferencia de POWER (modelo),
CPC es un análisis de **pluviómetros**: desde que la NASA dejó de publicar IMERG Final (14/11/2026)
toda la lluvia de IMERG es "Late", sin corrección por estaciones, así que un respaldo basado en
pluviómetros gana valor.


## Cómo se prueba

- Sin internet: `pytest -q tests/test_cpc_lluvia.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow `probar-cpc-lluvia.yml` en Actions (corre en el PR y se puede lanzar a mano), o `python probar_cpc_lluvia.py` en la compu.
- No necesita claves.

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ninguna otra fuente.
