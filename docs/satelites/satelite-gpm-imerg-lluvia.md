# GPM IMERG - lluvia diaria del lote

**Rama:** `satelite-gpm-imerg-lluvia` · **Conector:** `rotaterra/fuentes/imerg.py` · **Specs:** `docs/specs/006-lluvia-imerg-y-respaldo-merra2.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector GPM IMERG: lluvia diaria del punto del lote (spec 006).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_imerg.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-imerg.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_imerg.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
