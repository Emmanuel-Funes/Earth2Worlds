# VIIRS LST nocturna - aviso de heladas del lote

**Rama:** `satelite-viirs-heladas` · **Conector:** `rotaterra/fuentes/viirs_heladas.py` · **Specs:** `docs/specs/008-altimetria-nasadem.md`, `docs/specs/030-heladas-viirs-lst.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector VIIRS LST nocturna: temperatura de la superficie de noche del lote, para alertar heladas (spec 030).

Satélite independiente (spec 009): hace su propio pedido a la NASA y no importa a ningún otro satélite,
aunque comparta con el VIIRS de NDVI la grilla sinusoidal (se repite acá a propósito).

NOAA es una de las agencias socias permitidas (spec 008). El producto da la temperatura de la **superficie**
(suelo/canopeo) de noche, no la del aire: una helada agronómica se decide con esto más el criterio del productor.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_viirs_heladas.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-viirs-heladas.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_viirs_heladas.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
