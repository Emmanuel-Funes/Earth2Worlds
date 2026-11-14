# NASADEM - altura, pendiente y ambientes del lote

**Rama:** `satelite-nasadem-relieve` · **Conector:** `rotaterra/fuentes/nasadem.py` · **Specs:** `docs/specs/008-altimetria-nasadem.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector NASADEM: altura, pendiente y ambientes (bajo, media loma, loma) del lote (spec 008).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_nasadem.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-nasadem.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_nasadem.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
