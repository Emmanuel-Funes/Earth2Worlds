# HLS (Landsat + Sentinel-2) - NDVI y NDMI del lote a 30 m

**Rama:** `satelite-hls-ndvi-ndmi-30m` · **Conector:** `rotaterra/fuentes/hls.py` · **Specs:** `docs/specs/002-conector-hls-ndvi.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector HLS: NDVI y NDMI del lote a 30 m (spec 002).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_hls.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-hls.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_hls.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_hls.py "-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300" "2026-11-14" "2026-11-14"`

```
NDVI y NDMI del lote (HLS, 30 m) del 2026-11-14 al 2026-11-14

Fecha          NDVI   NDMI  Calidad     NDVI gráfico
2026-11-14     0.29  -0.10  buena       █████████
2026-11-14     0.28  -0.15  buena       ████████
2026-11-14     0.29  -0.17  buena       █████████
2026-11-14     0.29  -0.14  buena       █████████
2026-11-14     0.31  -0.15  buena       █████████
2026-11-14     0.32  -0.15  buena       █████████
2026-11-14     0.31  -0.14  buena       █████████
2026-11-14     0.32  -0.14  buena       ██████████
2026-11-14     0.29  -0.15  buena       █████████

9 fechas con imagen, 9 con el lote despejado.
```
