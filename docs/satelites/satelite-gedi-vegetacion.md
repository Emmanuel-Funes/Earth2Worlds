# GEDI - cobertura y estructura de la vegetación (láser)

**Rama:** `satelite-gedi-vegetacion` · **Conector:** `rotaterra/fuentes/gedi.py` · **Specs:** `docs/specs/059-vegetacion-de-la-zona-gedi.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector GEDI: cobertura y estructura de la vegetación en la zona del lote, medidas con láser (spec 059).

GEDI es el láser (lidar) de la NASA en la Estación Espacial. Cada disparo mide un círculo de ~25 m y dice qué
fracción del suelo tapa la vegetación (`cover`) y cuánta superficie de hojas y ramas hay por m² de suelo (`pai`).
Los disparos van en líneas separadas ~600 m y la Estación no pasa siempre por el mismo lugar: en un lote de 25 ha
caen de 0 a 7 disparos por pasada. Por eso se mira la **zona** (el lote más 2 km alrededor) y los últimos 3 años,
y el lote solo cuando tiene disparos buenos suficientes.

Sirve para ver montes, cortinas forestales y pastizales de la zona (estructura que el NDVI no muestra). En cultivos
anuales la cobertura que mide GEDI es baja (1 a 12 %): no es un indicador del cultivo.

Producto GEDI02_B (L2B, LP DAAC). No se baja el archivo de cada pasada (~1 GB): el servicio Harmony de la NASA
recorta en sus servidores la zona y solo 6 variables por haz (~1,4 MB en total). Tarda ~3 minutos.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_gedi.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-gedi.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_gedi.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
