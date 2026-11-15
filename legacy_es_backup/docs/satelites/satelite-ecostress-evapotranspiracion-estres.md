# ECOSTRESS - evapotranspiración y estrés hídrico a 70 m

**Rama:** `satelite-ecostress-evapotranspiracion-estres` · **Conector:** `rotaterra/fuentes/ecostress.py` · **Specs:** `docs/specs/018-ecostress-et-y-estres.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector ECOSTRESS: evapotranspiración diaria y estrés hídrico (ESI) del lote a 70 m (spec 018).

Primer respaldo de la ET principal: si la principal falla, entra ECOSTRESS; si tampoco trae datos, entra FAO-56.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_ecostress.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-ecostress.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_ecostress.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_ecostress.py "-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300" "2026-11-14" "2026-11-14"`

```
ECO_L3T_JET (et_mm_dia): colección C4057232489-LPCLOUD
  3 gránulos que tocan el lote del 2026-11-14 al 2026-11-14; mosaicos ['20HKH']
  capas del primero (ECOv003_L3T_JET_46928_025_20HKH_20261014T212735_01): ['bessjpldaily', 'cloud', 'etdaily', 'etuncertainty', 'pmjpldaily', 'ptjplsmcanopy', 'ptjplsmdaily', 'ptjplsminst', 'ptjplsminterception', 'ptjplsmsoil', 's
ECO_L4T_ESI (esi): colección C4057232495-LPCLOUD
  3 gránulos que tocan el lote del 2026-11-14 al 2026-11-14; mosaicos ['20HKH']
  capas del primero (ECOv003_L4T_ESI_46928_025_20HKH_20261014T212735_01): ['cloud', 'esi', 'pet', 'water']

ECOSTRESS del 2026-11-14 al 2026-11-14: 4 observaciones en 10 s

Evapotranspiración (mm/día) y estrés hídrico (ESI: 0 = estrés máximo, 1 = sin estrés), 70 m

Fecha            ET    ESI  Calidad ET Calidad ESI  Detalle
2026-11-14      —      —    descartada descartada   Solo 0% de píxeles válidos (nube, agua o sin dato) · ECO_L3T_JET ETdaily · pasada 21:27 UTC (17:06 hora solar) · máscaras: cloud, water · ECOv003_L3T_JET_46928_025_20HKH_20261014
2026-11-14      —     0.32  descartada buena        Solo 0% de píxeles válidos (nube, agua o sin dato) · ECO_L3T_JET ETdaily · pasada 19:54 UTC (15:33 hora solar) · máscaras: cloud, water · ECOv003_L3T_JET_46989_023_20HKH_20261018

2 fechas con pasada, 1 valores con dato (1 con el lote despejado).
```
