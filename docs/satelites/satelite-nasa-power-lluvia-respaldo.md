# NASA POWER - lluvia diaria como respaldo de IMERG

**Rama:** `satelite-nasa-power-lluvia-respaldo` · **Conector:** `rotaterra/fuentes/power_lluvia.py` · **Specs:** `docs/specs/013-lluvia-respaldo-power.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Respaldo de la lluvia de IMERG con NASA POWER: lluvia diaria del punto del lote (spec 013).

Satélite independiente (spec 009): hace su propio pedido a POWER y no usa el conector `power.py`.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_power_lluvia.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-power-lluvia.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_power_lluvia.py <lat> <lon> <desde> <hasta>` en la compu.
- No necesita claves.

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
