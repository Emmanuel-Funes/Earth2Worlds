# MERRA-2 - temperatura y radiación como respaldo de POWER

**Rama:** `satelite-merra2-clima-respaldo` · **Conector:** `rotaterra/fuentes/merra2.py` · **Specs:** `docs/specs/006-lluvia-imerg-y-respaldo-merra2.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector MERRA-2: temperatura y radiación diarias, respaldo de NASA POWER (spec 006).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_merra2.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-merra2.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_merra2.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
