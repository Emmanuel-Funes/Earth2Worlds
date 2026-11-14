# Sentinel-2 - NDVI 10 m y NDMI 20 m como respaldo de HLS

**Rama:** `satelite-sentinel2-ndvi-ndmi-respaldo` · **Conector:** `rotaterra/fuentes/sentinel2.py` · **Specs:** `docs/specs/014-ndvi-ndmi-sentinel2-respaldo.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector Sentinel-2 L2A (ESA): NDVI a 10 m y NDMI a 20 m, primer respaldo de HLS (spec 014).

Datos de la ESA/Copernicus distribuidos como COG públicos en AWS Open Data y catalogados en el STAC
público Earth Search de Element 84. No pide credenciales.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_sentinel2.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-sentinel2.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_sentinel2.py <lat> <lon> <desde> <hasta>` en la compu.
- No necesita claves.

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_sentinel2.py "-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300" "2026-11-14" "2026-11-14"`

```
NDVI (10 m) y NDMI (20 m) del lote con Sentinel-2 L2A (ESA, vía Earth Search / AWS Open Data) del 2026-11-14 al 2026-11-14 · 26 s

sentinel-2-l2a: 19 escenas
   S2C_20HKH_20261109_0_L2A · nubes 0.004663 · línea de base 05.13 · offset aplicado True · raster:bands [{'nodata': 0, 'data_type': 'uint16', 'spatial_resolution': 10, 'scale': 0.0001, 'offset': -0.1}] · se usa escala/offset (0.0
      https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/20/H/KH/2026/11/S2C_20HKH_20261109_0_L2A/B04.tif
   S2B_20HKH_20261107_0_L2A · nubes 30.718881 · línea de base 05.13 · offset aplicado True · raster:bands [{'nodata': 0, 'data_type': 'uint16', 'spatial_resolution': 10, 'scale': 0.0001, 'offset': -0.1}] · se usa escala/offset (0.
      https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/20/H/KH/2026/11/S2B_20HKH_20261107_0_L2A/B04.tif
   S2B_20HKH_20261104_0_L2A · nubes 0.005936 · línea de base 05.13 · offset aplicado True · raster:bands [{'nodata': 0, 'data_type': 'uint16', 'spatial_resolution': 10, 'scale': 0.0001, 'offset': -0.1}] · se usa escala/offset (0.0
      https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/20/H/KH/2026/11/S2B_20HKH_20261104_0_L2A/B04.tif
sentinel-2-c1-l2a: 19 escenas
   S2C_T20HKH_20261109T142026_L2A · nubes 0.004663 · línea de base 05.13 · offset aplicado None · raster:bands [{'nodata': 0, 'data_type': 'uint16', 'spatial_resolution': 10, 'scale': 0.0001, 'offset': -0.1}] · se usa escala/offse
      https://e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com/sentinel-2-c1-l2a/20/H/KH/2026/11/S2C_T20HKH_20261109T142026_L2A/B04.tif
   S2B_T20HKH_20261107T142531_L2A · nubes 30.718881 · línea de base 05.13 · offset aplicado None · raster:bands [{'nodata': 0, 'data_type': 'uint16', 'spatial_resolution': 10, 'scale': 0.0001, 'offset': -0.1}] · se usa escala/offs
      https://e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com/sentinel-2-c1-l2a/20/H/KH/2026/11/S2B_T20HKH_20261107T142531_L2A/B04.tif
   S2B_T20HKH_20261104T141904_L2A · nubes 0.005936 · línea de base 05.13 · offset aplicado None · raster:bands [{'nodata': 0, 'data_type': 'uint16', 'spatial_resolution': 10, 'scale': 0.0001, 'offset': -0.1}] · se usa escala/offse
      https://e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com/sentinel-2-c1-l2a/20/H/KH/2026/11/S2B_T20HKH_20261104T141904_L2A/B04.tif

Fecha       Variable   Valor  Calidad     Detalle
2026-11-14  ndmi       -0.16  buena       Respaldo de HLS · Sentinel-2 L2A (ESA) · S2B 20HKH · media -0.15 · p10 -0.18 · p90 -0.10 · válidos 100%
2026-11-14  ndvi        0.23  buena       Respaldo de HLS · Sentinel-2 L2A (ESA) · S2B 20HKH · media 0.31 · p10 0.18 · p90 0.46 · válidos 100%
2026-11-14  ndmi       -0.17  buena       Respaldo de HLS · Sentinel-2 L2A (ESA) · S2B 20HKH · media -0.13 · p10 -0.21 · p90 -0.01 · válidos 100%
2026-11-14  ndvi        0.22  buena       Respaldo de HLS · Sentinel-2 L2A (ESA) · S2B 20HKH · media 0.39 · p10 0.17 · p90 0.67 · válidos 100%
2026-11-14  ndmi       -0.17  buena       Respaldo de HLS · Sentinel-2 L2A (ESA) · S2B 20HKH · media -0.10 · p10 -0.22 · p90 0.05 · válidos 100%
2026-11-14  ndvi        0.22  buena       Respaldo de HLS · Sentinel-2 L2A (ESA) · S2B 20HKH · media 0.39 · p10 0.18 · p90 0.65 · válidos 100%
2026-11-14  ndmi       -0.18  buena       Respaldo de HLS · Sentinel-2 L2A (ESA) · S2C 20HKH · media -0.11 · p10 -0.22 · p90 0.04 · válidos 100%
2026-11-14  ndvi        0.24  buena       Respaldo de HLS · Sentinel-2 L2A (ESA) · S2C 20HKH · media 0.40 · p10 0.19 · p90 0.65 · válidos 100%
2026-11-14  ndmi       -0.16  buena       Respaldo de HLS · Sentinel-2 L2A (ESA) · S2A 20HKH · media -0.09 · p10 -0.21 · p90 0.05 · válidos 100%
2026-11-14  ndvi        0.25  buena       Respaldo de HLS · Sentinel-2 L2A (ESA) · S2A 20HKH · media 0.42 · p10 0.20 · p90 0.67 · válidos 100%
2026-11-14  ndmi       -0.15  buena       Respaldo de HLS · Sentinel-2 L2A (ESA) · S2B 20HKH · media -0.07 · p10 -0.20 · p90 0.09 · válidos 100%
2026-11-14  ndvi        0.26  buena       Respaldo de HLS · Sentinel-2 L2A (ESA) · S2B 20HKH · media 0.43 · p10 0.20 · p90 0.69 · válidos 100%
2026-11-14  ndmi         —    descartada  Respaldo de HLS · Sentinel-2 L2A (ESA) · S2B 20HKH · solo 7% de píxeles limpios · SCL: sombra de nube 93%
2026-11-14  ndvi         —    descartada  Respaldo de HLS · Sentinel-2 L2A (ESA) · S2B 20HKH · solo 6% de píxeles limpios · SCL: sombra de nube 94%
2026-11-14  ndmi       -0.16  buena       Respaldo de HLS · Sentinel-2 L2A (ESA) · S2C 20HKH · media -0.07 · p10 -0.20 · p90 0.09 · válidos 100%
2026-11-14  ndvi        0.25  buena       Respaldo de HLS · Sentinel-2 L2A (ESA) · S2C 20HKH · media 0.43 · p10 0.20 · p90 0.70 · válidos 100%

8 fechas, 7 con el lote despejado.
```
