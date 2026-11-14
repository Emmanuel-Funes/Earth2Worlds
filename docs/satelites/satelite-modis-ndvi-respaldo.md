# MODIS - NDVI de 250 m como respaldo de HLS

**Rama:** `satelite-modis-ndvi-respaldo` · **Conector:** `rotaterra/fuentes/modis.py` · **Specs:** `docs/specs/007-ndvi-modis-respaldo.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector MODIS: NDVI de 250 m del lote, respaldo de HLS (spec 007).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_modis.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-modis.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_modis.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_modis.py "-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300" "2026-11-14" "2026-11-14"`

```
NDVI del lote (MODIS Terra, 250 m, compuestos de 16 días) del 2026-11-14 al 2026-11-14 · 5 s

Fecha          NDVI  Calidad     Detalle
2026-11-14     0.34  buena       Respaldo de HLS · MOD13Q1 compuesto del 2026-11-14 · 4 píxeles de 250 m · válidos 100%
2026-11-14     0.32  buena       Respaldo de HLS · MOD13Q1 compuesto del 2026-11-14 · 4 píxeles de 250 m · válidos 100%
2026-11-14     0.42  buena       Respaldo de HLS · MOD13Q1 compuesto del 2026-11-14 · 4 píxeles de 250 m · válidos 100%

3 compuestos, 3 con el lote despejado.
```
