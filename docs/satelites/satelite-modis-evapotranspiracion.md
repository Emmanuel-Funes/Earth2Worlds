# MODIS MOD16 - evapotranspiración real y potencial

**Rama:** `satelite-modis-evapotranspiracion` · **Conector:** `rotaterra/fuentes/et.py` · **Specs:** `docs/specs/017-evapotranspiracion.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector de evapotranspiración: ET real y potencial de 500 m y 8 días de la NASA, fuente principal de ET (spec 017).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_et.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-et.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_et.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
