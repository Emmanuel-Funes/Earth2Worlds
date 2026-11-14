# FLDAS - humedad del suelo como respaldo final de SMAP

**Rama:** `satelite-fldas-humedad-respaldo` · **Conector:** `rotaterra/fuentes/fldas.py` · **Specs:** `docs/specs/036-humedad-respaldo-fldas.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector FLDAS: respaldo de humedad del suelo de la NASA (spec 036).

Respaldo final de SMAP (después de AppEEARS, SMAP L3 y GLDAS). La fuente es FLDAS Noah 0.1°
(`FLDAS_NOAH01_C_GL_M`), un modelo de superficie de la NASA (GES DISC), hermano de GLDAS pero con una
grilla más fina (~11 km) y paso **mensual**. Da la humedad del suelo por capas en m³/m³.

Es un dato REGIONAL de modelo y MENSUAL: el píxel cubre miles de hectáreas y el valor es el promedio del
mes. Por eso entra último (orden 4) y su calidad nunca pasa de `dudosa`. Se lee por OPeNDAP (`.dmr` para
los metadatos, `.dap.csv` para el recorte), solo el píxel del lote. No importa a ningún otro satélite
(spec 009): las ayudas de OPeNDAP están repetidas acá a propósito (vienen del patrón de GLDAS).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_fldas.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-fldas.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_fldas.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
