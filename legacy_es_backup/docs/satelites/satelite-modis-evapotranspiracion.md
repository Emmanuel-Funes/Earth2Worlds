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

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_et.py "-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300" "2026-11-14" "2026-11-14"`

```
No se pudo revisar CMR: ConnectError: [Errno 104] Connection reset by peer

Evapotranspiración del lote (500 m, compuestos de 8 días) del 2026-11-14 al 2026-11-14 · mosaico h12v12 · 7 s
Capas leídas: {'MOD16A2': {'et': '/MOD_Grid_MOD16A2/Data_Fields/ET_500m', 'pet': '/MOD_Grid_MOD16A2/Data_Fields/PET_500m', 'qc': '/MOD_Grid_MOD16A2/Data_Fields/ET_QC_500m'}}
Atributos: {'MOD16A2': {'et': {'escala': 0.1, 'valido_max': 32700.0}, 'pet': {'escala': 0.1, 'valido_max': 32700.0}, 'qc': {'escala': 0.1, 'valido_max': 254.0}}}

Inicio      Variable     mm/día  Calidad     Detalle
2026-11-14  et_mm_dia      0.30  buena       MODIS · MOD16A2 (MODIS Terra) · fecha = inicio del compuesto de 8 días (2026-11-14 al 2026-11-14) · promedio diario = suma 2.4 mm / 8 días · 1 píxeles de 500 m · válidos 100% · algoritm
2026-11-14  pet_mm_dia     5.65  buena       MODIS · MOD16A2 (MODIS Terra) · fecha = inicio del compuesto de 8 días (2026-11-14 al 2026-11-14) · promedio diario = suma 45.2 mm / 8 días · 1 píxeles de 500 m · válidos 100% · algorit
2026-11-14  et_mm_dia      0.56  buena       MODIS · MOD16A2 (MODIS Terra) · fecha = inicio del compuesto de 8 días (2026-11-14 al 2026-11-14) · promedio diario = suma 4.5 mm / 8 días · 1 píxeles de 500 m · válidos 100% · algoritm
2026-11-14  pet_mm_dia     5.90  buena       MODIS · MOD16A2 (MODIS Terra) · fecha = inicio del compuesto de 8 días (2026-11-14 al 2026-11-14) · promedio diario = suma 47.2 mm / 8 días · 1 píxeles de 500 m · válidos 100% · algorit
2026-11-14  et_mm_dia      0.80  buena       MODIS · MOD16A2 (MODIS Terra) · fecha = inicio del compuesto de 8 días (2026-11-14 al 2026-11-14) · promedio diario = suma 6.4 mm / 8 días · 1 píxeles de 500 m · válidos 100% · algoritm
2026-11-14  pet_mm_dia     5.34  buena       MODIS · MOD16A2 (MODIS Terra) · fecha = inicio del compuesto de 8 días (2026-11-14 al 2026-11-14) · promedio diario = suma 42.7 mm / 8 días · 1 píxeles de 500 m · válidos 100% · algorit
2026-11-14  et_mm_dia      1.36  dudosa      MODIS · MOD16A2 (MODIS Terra) · fecha = inicio del compuesto de 8 días (2026-11-14 al 2026-11-14) · promedio diario = suma 10.9 mm / 8 días · 1 píxeles de 500 m · válidos 100% · algorit
2026-11-14  pet_mm_dia     3.19  dudosa      MODIS · MOD16A2 (MODIS Terra) · fecha = inicio del compuesto de 8 días (2026-11-14 al 2026-11-14) · promedio diario = suma 25.5 mm / 8 días · 1 píxeles de 500 m · válidos 100% · algorit
2026-11-14  et_mm_dia      0.94  buena       MODIS · MOD16A2 (MODIS Terra) · fecha = inicio del compuesto de 8 días (2026-11-14 al 2026-11-14) · promedio diario = suma 7.5 mm / 8 días · 1 píxeles de 500 m · válidos 100% · algoritm
2026-11-14  pet_mm_dia     5.15  buena       MODIS · MOD16A2 (MODIS Terra) · fecha = inicio del compuesto de 8 días (2026-11-14 al 2026-11-14) · promedio diario = suma 41.2 mm / 8 días · 1 píxeles de 500 m · válidos 100% · algorit
2026-11-14  et_mm_dia      0.70  buena       MODIS · MOD16A2 (MODIS Terra) · fecha = inicio del compuesto de 8 días (2026-11-14 al 2026-11-14) · promedio diario = suma 5.6 mm / 8 días · 1 píxeles de 500 m · válidos 100% · algoritm
2026-11-14  pet_mm_dia     6.44  buena       MODIS · MOD16A2 (MODIS Terra) · fecha = inicio del compuesto de 8 días (2026-11-14 al 2026-11-14) · promedio diario = suma 51.5 mm / 8 días · 1 píxeles de 500 m · válidos 100% · algorit

6 compuestos, 6 con ET válida.
```
