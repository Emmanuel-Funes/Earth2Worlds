# ECOSTRESS LST - heladas por zona del lote a 70 m

**Rama:** `satelite-ecostress-heladas-por-zona` · **Conector:** `rotaterra/fuentes/ecostress_heladas.py` · **Specs:** `docs/specs/030-heladas-viirs-lst.md`, `docs/specs/053-heladas-por-zona-ecostress.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector ECOSTRESS LST nocturna: heladas por zona del lote a 70 m (spec 053).

Satélite independiente (spec 009): hace su propio pedido a la NASA y no importa al ECOSTRESS de la ET,
aunque comparta con él la forma de leer los mosaicos (se repite acá a propósito).

VIIRS (spec 030) da un solo píxel de 1 km para todo el lote. ECOSTRESS mide la temperatura de superficie a
70 m, así que muestra **en qué parte del lote** hiela (los bajos). Pasa desde la Estación Espacial, sin
horario fijo: hay noches con dato y noches sin él. Complementa a VIIRS, no lo reemplaza.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_ecostress_heladas.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-ecostress-heladas.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_ecostress_heladas.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
