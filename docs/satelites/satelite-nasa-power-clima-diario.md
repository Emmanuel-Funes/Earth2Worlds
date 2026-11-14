# NASA POWER - clima diario del lote (temperatura, lluvia, radiación)

**Rama:** `satelite-nasa-power-clima-diario` · **Conector:** `rotaterra/fuentes/power.py` · **Specs:** `docs/specs/001-conector-nasa-power.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector NASA POWER: clima diario por punto (spec 001).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_power.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-power.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_power.py <lat> <lon> <desde> <hasta>` en la compu.
- No necesita claves.

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
