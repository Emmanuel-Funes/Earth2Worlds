# ECOSTRESS LST - heladas por zona del lote a 70 m

**Rama:** `satelite-ecostress-heladas-por-zona` · **Conector:** `rotaterra/fuentes/ecostress_heladas.py` · **Specs:** `docs/specs/030-heladas-viirs-lst.md`, `docs/specs/053-heladas-por-zona-ecostress.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector ECOSTRESS LST nocturna: heladas por zona del lote a 70 m (spec 053).

Satélite independiente (spec 009): hace su propio pedido a la NASA y no importa al ECOSTRESS de la ET,
aunque comparta con él la forma de leer los mosaicos (se repite acá a propósito).

VIIRS (spec 030) da un solo píxel de 1 km para todo el lote. ECOSTRESS mide la temperatura de superficie a
70 m, así que muestra **en qué parte del lote** hiela (los bajos). Pasa desde la Estación Espacial, sin
horario fijo: hay noches con dato y noches sin él. Complementa a VIIRS, no lo reemplaza.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_ecostress_heladas.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-ecostress-heladas.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_ecostress_heladas.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_ecostress_heladas.py "-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300" "2026-09-15" "2026-11-12"`

```
Heladas por zona del lote (ECOSTRESS LST nocturna, 70 m) del 2026-09-15 al 2026-11-12 · 14 s

Noche         Mín °C  % ≤0 °C  Calidad     Detalle
2026-09-16       —        —    descartada  Nubes o franja del satélite al costado del lote (válidos 0%) · pasada 2026-09-16 09:03 UTC (04:42 hora solar) · nube en 0% del lote · sin medición en 100% · ECOv003_L2T_LSTE_46483_022_20H
2026-09-20       —        —    descartada  Nubes o franja del satélite al costado del lote (válidos 0%) · pasada 2026-09-20 07:29 UTC (03:08 hora solar) · nube en 0% del lote · sin medición en 100% · ECOv003_L2T_LSTE_46544_025_20H
2026-09-28       —        —    descartada  Nubes o franja del satélite al costado del lote (válidos 0%) · pasada 2026-09-28 04:23 UTC (00:02 hora solar) · nube en 0% del lote · sin medición en 100% · ECOv003_L2T_LSTE_46667_023_20H
2026-09-29       —        —    descartada  Nubes o franja del satélite al costado del lote (válidos 0%) · pasada 2026-09-29 03:35 UTC (23:14 hora solar) · nube en 0% del lote · sin medición en 100% · ECOv003_L2T_LSTE_46683_023_20H
2026-10-03       —        —    descartada  Nubes o franja del satélite al costado del lote (válidos 0%) · pasada 2026-10-03 02:03 UTC (21:42 hora solar) · nube en 0% del lote · sin medición en 100% · ECOv003_L2T_LSTE_46744_022_20H
2026-10-08      -0.2        2  buena       ECOSTRESS LST nocturna a 70 m (temperatura de superficie, no del aire) · mínima -0.2 · mediana 3.2 · máxima 4.0 °C · 2% del lote a 0 °C o menos · punto más frío en -33.70465, -65.2958 · v
2026-10-17       —        —    descartada  Nubes o franja del satélite al costado del lote (válidos 0%) · pasada 2026-10-17 04:02 UTC (23:40 hora solar) · nube en 0% del lote · sin medición en 100% · ECOv003_L2T_LSTE_46963_028_20H
2026-10-24       3.4        0  dudosa      ECOSTRESS LST nocturna a 70 m (temperatura de superficie, no del aire) · mínima 3.4 · mediana 3.7 · máxima 3.8 °C · 0% del lote a 0 °C o menos · punto más frío en -33.70333, -65.29878 · v
2026-11-07       8.2        0  buena       ECOSTRESS LST nocturna a 70 m (temperatura de superficie, no del aire) · mínima 8.2 · mediana 12.9 · máxima 14.8 °C · 0% del lote a 0 °C o menos · punto más frío en -33.70086, -65.2957 · 

9 noches con pasada · calidad {'descartada': 6, 'buena': 2, 'dudosa': 1} · 3 con dato · 1 con riesgo de helada
```
