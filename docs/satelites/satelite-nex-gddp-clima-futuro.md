# NEX-GDDP-CMIP6 - clima futuro 2041-2060 de la zona del lote

**Rama:** `satelite-nex-gddp-clima-futuro` · **Conector:** `rotaterra/fuentes/nex_gddp.py` · **Specs:** `docs/specs/058-clima-futuro-nex-gddp.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector NEX-GDDP-CMIP6 (NASA): clima futuro de la zona del lote, 2041-2060 contra 1995-2014 (spec 058).

Proyecciones diarias de temperatura máxima, mínima y lluvia de los modelos climáticos CMIP6, corregidas y
bajadas de escala por la NASA (Ames, NEX) a una grilla de 0,25° (~25 km). Se leen por el servicio NCSS del THREDDS
público del NCCS (sin cuenta), un año por pedido, solo en la celda del lote.

Con eso se calculan indicadores para comparar rotaciones frente al clima que viene: días de calor (≥ 35 °C), máxima
de verano, días de helada del aire, lluvia del año y de la campaña, días de lluvia extrema (≥ 50 mm) y la racha
seca más larga de la campaña. Para cada uno: la línea de base de los modelos (1995-2014) y dos escenarios a
2041-2060, SSP2-4.5 (emisiones intermedias) y SSP5-8.5 (emisiones altas).

Es una PROYECCIÓN de modelos, no un pronóstico, y un dato REGIONAL de ~25 km: todo sale `dudosa`. Los datos
no cambian, así que cada celda se calcula una sola vez y queda en memoria. La primera vez tarda unos 15 minutos
(540 pedidos de unos 7 s, de a 4 a la vez).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_nex_gddp.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-nex-gddp.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_nex_gddp.py <lat> <lon> <desde> <hasta>` en la compu.
- No necesita claves.

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_nex_gddp.py "-33.70" "-65.30"`

```
Clima futuro NEX-GDDP-CMIP6 en la celda de ~25 km de -33.7, -65.3 · 1223 s

Indicador                   1995-2014   SSP2-4.5   SSP5-8.5  Unidad
dias_calor_35                    29.6       38.5       43.2  días/año
tmax_verano_c                    31.7       32.9       32.9  °C
dias_helada_aire                 28.9       19.1         19  días/año
lluvia_anual_mm                   649        709        720  mm
lluvia_campana_mm                 516        556        564  mm
dias_lluvia_extrema_50            0.2       0.25       0.35  días/año
racha_seca_campana_dias            17         17         17  días

Detalle:
· dias_calor_35_historico: 29.6 días/año · dudosa · Días por año con máxima del aire ≥ 35 °C (estrés por calor) · línea de base de los modelos 1995-2014 (no es lo observado) · mediana de 3 modelos: ACCESS-CM2 28.5, MPI-ESM1-2-HR 3
· tmax_verano_c_historico: 31.7 °C · dudosa · Máxima media del aire de diciembre a febrero · línea de base de los modelos 1995-2014 (no es lo observado) · mediana de 3 modelos: ACCESS-CM2 31.7, MPI-ESM1-2-HR 31.9, MRI-ESM2-0 31.7 
· dias_helada_aire_historico: 28.9 días/año · dudosa · Días por año con mínima del aire ≤ 0 °C · línea de base de los modelos 1995-2014 (no es lo observado) · mediana de 3 modelos: ACCESS-CM2 20.3, MPI-ESM1-2-HR 28.9, MRI-ESM2-0 3
· lluvia_anual_mm_historico: 649.0 mm · dudosa · Lluvia del año · línea de base de los modelos 1995-2014 (no es lo observado) · mediana de 3 modelos: ACCESS-CM2 628, MPI-ESM1-2-HR 649, MRI-ESM2-0 673 · NEX-GDDP-CMIP6 (NASA) · celd
· lluvia_campana_mm_historico: 516.0 mm · dudosa · Lluvia de octubre a marzo · línea de base de los modelos 1995-2014 (no es lo observado) · mediana de 3 modelos: ACCESS-CM2 504, MPI-ESM1-2-HR 516, MRI-ESM2-0 524 · NEX-GDDP-CMIP6 
· dias_lluvia_extrema_50_historico: 0.2 días/año · dudosa · Días por año con lluvia ≥ 50 mm · línea de base de los modelos 1995-2014 (no es lo observado) · mediana de 3 modelos: ACCESS-CM2 0.00, MPI-ESM1-2-HR 0.20, MRI-ESM2-0 0.45
· racha_seca_campana_dias_historico: 17.0 días · dudosa · Racha más larga de días seguidos con menos de 1 mm, de octubre a marzo · línea de base de los modelos 1995-2014 (no es lo observado) · mediana de 3 modelos: ACCESS-CM2 14, 
· dias_calor_35_ssp245: 38.5 días/año · dudosa · Días por año con máxima del aire ≥ 35 °C (estrés por calor) · SSP2-4.5 (emisiones intermedias) 2041-2060 · mediana de 3 modelos: ACCESS-CM2 38.5, MPI-ESM1-2-HR 35.4, MRI-ESM2-0 41.6
· tmax_verano_c_ssp245: 32.9 °C · dudosa · Máxima media del aire de diciembre a febrero · SSP2-4.5 (emisiones intermedias) 2041-2060 · mediana de 3 modelos: ACCESS-CM2 33.0, MPI-ESM1-2-HR 32.4, MRI-ESM2-0 32.9 · cambio contra 1995
· dias_helada_aire_ssp245: 19.1 días/año · dudosa · Días por año con mínima del aire ≤ 0 °C · SSP2-4.5 (emisiones intermedias) 2041-2060 · mediana de 3 modelos: ACCESS-CM2 13.2, MPI-ESM1-2-HR 19.1, MRI-ESM2-0 29.4 · cambio contra 
· lluvia_anual_mm_ssp245: 709.0 mm · dudosa · Lluvia del año · SSP2-4.5 (emisiones intermedias) 2041-2060 · mediana de 3 modelos: ACCESS-CM2 764, MPI-ESM1-2-HR 655, MRI-ESM2-0 709 · cambio contra 1995-2014 del mismo modelo: +36 (d
· lluvia_campana_mm_ssp245: 556.0 mm · dudosa · Lluvia de octubre a marzo · SSP2-4.5 (emisiones intermedias) 2041-2060 · mediana de 3 modelos: ACCESS-CM2 579, MPI-ESM1-2-HR 518, MRI-ESM2-0 556 · cambio contra 1995-2014 del mismo m
· dias_lluvia_extrema_50_ssp245: 0.25 días/año · dudosa · Días por año con lluvia ≥ 50 mm · SSP2-4.5 (emisiones intermedias) 2041-2060 · mediana de 3 modelos: ACCESS-CM2 0.15, MPI-ESM1-2-HR 0.30, MRI-ESM2-0 0.25 · cambio contra 19
· racha_seca_campana_dias_ssp245: 17.0 días · dudosa · Racha más larga de días seguidos con menos de 1 mm, de octubre a marzo · SSP2-4.5 (emisiones intermedias) 2041-2060 · mediana de 3 modelos: ACCESS-CM2 12, MPI-ESM1-2-HR 20, MR
· dias_calor_35_ssp585: 43.2 días/año · dudosa · Días por año con máxima del aire ≥ 35 °C (estrés por calor) · SSP5-8.5 (emisiones altas) 2041-2060 · mediana de 3 modelos: ACCESS-CM2 47.9, MPI-ESM1-2-HR 42.1, MRI-ESM2-0 43.2 · cam
· tmax_verano_c_ssp585: 32.9 °C · dudosa · Máxima media del aire de diciembre a febrero · SSP5-8.5 (emisiones altas) 2041-2060 · mediana de 3 modelos: ACCESS-CM2 33.8, MPI-ESM1-2-HR 32.9, MRI-ESM2-0 32.7 · cambio contra 1995-2014 
· dias_helada_aire_ssp585: 19.0 días/año · dudosa · Días por año con mínima del aire ≤ 0 °C · SSP5-8.5 (emisiones altas) 2041-2060 · mediana de 3 modelos: ACCESS-CM2 13.2, MPI-ESM1-2-HR 19.0, MRI-ESM2-0 24.5 · cambio contra 1995-2
· lluvia_anual_mm_ssp585: 720.0 mm · dudosa · Lluvia del año · SSP5-8.5 (emisiones altas) 2041-2060 · mediana de 3 modelos: ACCESS-CM2 720, MPI-ESM1-2-HR 633, MRI-ESM2-0 804 · cambio contra 1995-2014 del mismo modelo: +92 (de -16 
· lluvia_campana_mm_ssp585: 564.0 mm · dudosa · Lluvia de octubre a marzo · SSP5-8.5 (emisiones altas) 2041-2060 · mediana de 3 modelos: ACCESS-CM2 564, MPI-ESM1-2-HR 503, MRI-ESM2-0 631 · cambio contra 1995-2014 del mismo modelo:
· dias_lluvia_extrema_50_ssp585: 0.35 días/año · dudosa · Días por año con lluvia ≥ 50 mm · SSP5-8.5 (emisiones altas) 2041-2060 · mediana de 3 modelos: ACCESS-CM2 0.10, MPI-ESM1-2-HR 0.35, MRI-ESM2-0 0.65 · cambio contra 1995-201
· racha_seca_campana_dias_ssp585: 17.0 días · dudosa · Racha más larga de días seguidos con menos de 1 mm, de octubre a marzo · SSP5-8.5 (emisiones altas) 2041-2060 · mediana de 3 modelos: ACCESS-CM2 12, MPI-ESM1-2-HR 19, MRI-ESM2
```
