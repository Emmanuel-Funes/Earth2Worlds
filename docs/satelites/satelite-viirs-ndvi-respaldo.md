# VIIRS - NDVI de 500 m como respaldo de HLS

**Rama:** `satelite-viirs-ndvi-respaldo` · **Conector:** `rotaterra/fuentes/viirs.py` · **Specs:** `docs/specs/011-ndvi-viirs-respaldo.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector VIIRS: NDVI de 500 m del lote, primer respaldo de HLS y continuidad de MODIS (spec 011).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_viirs.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-viirs.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_viirs.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_viirs.py "-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300" "2026-11-14" "2026-11-14"`

```
NDVI del lote (VIIRS NOAA-20/21, 500 m, compuestos de 16 días) del 2026-11-14 al 2026-11-14 · mosaico h12v12 · 14 s
Capas leídas: {'VJ113A1': {'dia': '/HDFEOS/GRIDS/VIIRS_Grid_16Day_VI_500m/Data_Fields/_500_m_16_days_composite_day_of_the_year', 'confiabilidad': '/HDFEOS/GRIDS/VIIRS_Grid_16Day_VI_500m/Data_Fields/_500_m_16_days_pixel_reliability

Fecha          NDVI  Calidad     Detalle
2026-11-14     0.28  buena       Respaldo de HLS · VJ113A1 (NOAA-20) compuesto del 2026-11-14 · 1 píxeles de 500 m · válidos 100%
2026-11-14     0.33  buena       Respaldo de HLS · VJ113A1 (NOAA-20) compuesto del 2026-11-14 · 1 píxeles de 500 m · válidos 100%
2026-11-14     0.27  buena       Respaldo de HLS · VJ213A1 (NOAA-21) compuesto del 2026-11-14 · 1 píxeles de 500 m · válidos 100%
2026-11-14     0.31  buena       Respaldo de HLS · VJ113A1 (NOAA-20) compuesto del 2026-11-14 · 1 píxeles de 500 m · válidos 100%
2026-11-14      —    descartada  Nubes o sin dato · Respaldo de HLS · VJ113A1 (NOAA-20) compuesto del 2026-11-14 · 1 píxeles de 500 m · válidos 0%
2026-11-14     0.29  buena       Respaldo de HLS · VJ213A1 (NOAA-21) compuesto del 2026-11-14 · 1 píxeles de 500 m · válidos 100%
2026-11-14      —    descartada  Nubes o sin dato · Respaldo de HLS · VJ213A1 (NOAA-21) compuesto del 2026-11-14 · 1 píxeles de 500 m · válidos 0%
2026-11-14     0.67  buena       Respaldo de HLS · VJ113A1 (NOAA-20) compuesto del 2026-11-14 · 1 píxeles de 500 m · válidos 100%

8 fechas, 6 con el lote despejado.
```
