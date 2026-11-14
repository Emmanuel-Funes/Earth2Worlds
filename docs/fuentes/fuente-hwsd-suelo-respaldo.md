# HWSD - textura y pH del suelo como respaldo de GeoINTA

**Rama:** `fuente-hwsd-suelo-respaldo` · **Conector:** `rotaterra/fuentes/hwsd_suelo.py` · **Specs:** `docs/specs/031-suelo-respaldo-hwsd.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector HWSD: respaldo de suelo de la NASA (spec 031).

Respaldo de GeoINTA (que hoy no tiene ninguno). Entrega la textura (clase común 1-12) y el pH del lote
a partir de la Harmonized World Soil Database v1.2 regrillada (HWSD_1247) del ORNL DAAC de la NASA, una
base mundial de suelo en una grilla de 0,05° (~5,5 km). Es un dato estático y REGIONAL: la base no cambia
y cada celda cubre miles de hectáreas, así que respalda a GeoINTA pero no lo reemplaza (calidad `dudosa`).

Cada capa es un NetCDF que se baja una sola vez a la caché (igual que los mascons de GRACE) y se lee con
rasterio solo en la celda del centro del lote. No importa a ningún otro satélite (spec 009).


## Cómo se prueba

- Sin internet: `pytest -q tests/test_hwsd_suelo.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow `probar-hwsd-suelo.yml` en Actions (corre en el PR y se puede lanzar a mano), o `python probar_hwsd_suelo.py` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ninguna otra fuente.
