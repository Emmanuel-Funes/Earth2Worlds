# GLDAS - humedad del suelo y ET como respaldo

**Rama:** `satelite-gldas-humedad-y-et-respaldo` · **Conector:** `rotaterra/fuentes/gldas.py` · **Specs:** `docs/specs/032-humedad-y-et-respaldo-gldas.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector GLDAS: respaldo de humedad del suelo y de ET real de la NASA (spec 032).

Respaldo final de SMAP (humedad) y de la ET (después de ECOSTRESS). La fuente es GLDAS Noah 0.25°
(`GLDAS_NOAH025_3H`, con el producto temprano `_EP` para lo reciente), un modelo de superficie de la
NASA (GES DISC) que da humedad del suelo por capas y ET cada 3 horas, en una grilla de ~25 km, con ~1
mes de atraso. Es un dato REGIONAL de modelo: el píxel cubre miles de hectáreas.

Se lee por OPeNDAP (`.dmr` para los metadatos, `.dap.csv` para el recorte), solo el píxel del lote, y
los 8 pasos de 3 h de cada día se promedian. No importa a ningún otro satélite (spec 009): las ayudas de
OPeNDAP están repetidas acá a propósito.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_gldas.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-gldas.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_gldas.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
