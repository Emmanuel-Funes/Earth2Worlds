# SMAP L3 - humedad de superficie como respaldo de SMAP L4

**Rama:** `satelite-smap-l3-humedad-respaldo` · **Conector:** `rotaterra/fuentes/smap_l3.py` · **Specs:** `docs/specs/015-humedad-smap-l3-respaldo.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector SMAP L3: humedad de superficie observada por satélite, segundo respaldo de SMAP L4 (spec 015).

El L4 (SPL4SMGP) es un modelo que asimila SMAP; el L3 mejorado (SPL3SMP_E) es la observación del
radiómetro, sin modelo: una pasada AM y una PM por día cuando la órbita cruza la celda de 9 km.
Se lee solo la celda del lote por OPeNDAP de la NASA (CMR + Earthdata), como el camino directo del L4.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_smap_l3.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-smap-l3.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_smap_l3.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
