# VIIRS LST nocturna - aviso de heladas del lote

**Rama:** `satelite-viirs-heladas` · **Conector:** `rotaterra/fuentes/viirs_heladas.py` · **Specs:** `docs/specs/008-altimetria-nasadem.md`, `docs/specs/030-heladas-viirs-lst.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector VIIRS LST nocturna: temperatura de la superficie de noche del lote, para alertar heladas (spec 030).

Satélite independiente (spec 009): hace su propio pedido a la NASA y no importa a ningún otro satélite,
aunque comparta con el VIIRS de NDVI la grilla sinusoidal (se repite acá a propósito).

NOAA es una de las agencias socias permitidas (spec 008). El producto da la temperatura de la **superficie**
(suelo/canopeo) de noche, no la del aire: una helada agronómica se decide con esto más el criterio del productor.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_viirs_heladas.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-viirs-heladas.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_viirs_heladas.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_viirs_heladas.py "-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300" "2026-11-14" "2026-11-14"`

```
Temperatura de superficie nocturna del lote (VIIRS NOAA-20/21, LST de 1 km) del 2026-11-14 al 2026-11-14 · mosaico h12v12 · 13 s
Capas leídas: {'VJ121A1N': '/HDFEOS/GRIDS/VIIRS_Grid_Daily_1km_LST21/Data_Fields/LST_1KM', 'VJ221A1N': '/HDFEOS/GRIDS/VIIRS_Grid_Daily_1km_LST21/Data_Fields/LST_1KM'}

Fecha        T sup °C  Calidad     Detalle
2026-11-14        7.9  buena       VIIRS LST nocturna (temperatura de superficie, no del aire) · VJ121A1N (NOAA-20) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 100%
2026-11-14        7.1  buena       VIIRS LST nocturna (temperatura de superficie, no del aire) · VJ121A1N (NOAA-20) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 100%
2026-11-14       —     descartada  Nubes o sin dato · VIIRS LST nocturna (temperatura de superficie, no del aire) · VJ121A1N (NOAA-20) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 0%
2026-11-14       —     descartada  Nubes o sin dato · VIIRS LST nocturna (temperatura de superficie, no del aire) · VJ121A1N (NOAA-20) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 0%
2026-11-14       —     descartada  Nubes o sin dato · VIIRS LST nocturna (temperatura de superficie, no del aire) · VJ121A1N (NOAA-20) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 0%
2026-11-14        9.4  buena       VIIRS LST nocturna (temperatura de superficie, no del aire) · VJ121A1N (NOAA-20) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 100%
2026-11-14       —     descartada  Nubes o sin dato · VIIRS LST nocturna (temperatura de superficie, no del aire) · VJ121A1N (NOAA-20) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 0%
2026-11-14       —     descartada  Nubes o sin dato · VIIRS LST nocturna (temperatura de superficie, no del aire) · VJ121A1N (NOAA-20) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 0%
2026-11-14        8.9  buena       VIIRS LST nocturna (temperatura de superficie, no del aire) · VJ121A1N (NOAA-20) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 100%
2026-11-14       12.9  buena       VIIRS LST nocturna (temperatura de superficie, no del aire) · VJ121A1N (NOAA-20) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 100%
2026-11-14       —     descartada  Nubes o sin dato · VIIRS LST nocturna (temperatura de superficie, no del aire) · VJ221A1N (NOAA-21) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 0%
2026-11-14        5.3  buena       VIIRS LST nocturna (temperatura de superficie, no del aire) · VJ221A1N (NOAA-21) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 100%
2026-11-14       10.8  buena       VIIRS LST nocturna (temperatura de superficie, no del aire) · VJ221A1N (NOAA-21) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 100%
2026-11-14       19.9  buena       VIIRS LST nocturna (temperatura de superficie, no del aire) · VJ221A1N (NOAA-21) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 100%
2026-11-14       11.4  buena       VIIRS LST nocturna (temperatura de superficie, no del aire) · VJ221A1N (NOAA-21) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 100%
2026-11-14       —     descartada  Nubes o sin dato · VIIRS LST nocturna (temperatura de superficie, no del aire) · VJ221A1N (NOAA-21) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 0%

16 noches · calidad {'buena': 9, 'descartada': 7} · 9 con dato · 0 con riesgo de helada (≤ 0 °C)
Noche más fría: 2026-11-14 con 5.3 °C de superficie
Variable temp_sup_min_c en °C, fuente VIIRS, resolución 1000 m
```
