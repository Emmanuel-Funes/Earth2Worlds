# ASTER GDEM - relieve como segundo respaldo de NASADEM

**Rama:** `satelite-aster-relieve-respaldo` · **Conector:** `rotaterra/fuentes/aster.py` · **Specs:** `docs/specs/008-altimetria-nasadem.md`, `docs/specs/016-altimetria-copernicus-dem-respaldo.md`, `docs/specs/037-altimetria-respaldo-aster.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector ASTER GDEM v3 (NASA/METI): altura, pendiente y ambientes del lote, respaldo de NASADEM (spec 037).

Mismas 7 variables y mismas reglas que NASADEM (spec 008) y Copernicus DEM (spec 016), con el modelo global
de 30 m de la NASA y el METI de Japón (ASTGTM, colección v003). Es un segundo respaldo de relieve, después
de Copernicus DEM. Se baja el mosaico de 1° del lote por CMR + Earthdata y se lee con rasterio solo la
ventana del lote. No importa a ningún otro satélite (spec 009).

ASTER GDEM v3 es un COMPUESTO de tomas de 2000 a 2013 (publicado en 2019): es un dato fijo por lugar.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_aster.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-aster.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_aster.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
