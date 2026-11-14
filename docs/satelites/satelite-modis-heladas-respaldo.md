# MODIS LST nocturna - heladas como respaldo de VIIRS

**Rama:** `satelite-modis-heladas-respaldo` · **Conector:** `rotaterra/fuentes/modis_heladas.py` · **Specs:** `docs/specs/035-heladas-respaldo-modis.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector MODIS LST nocturna: respaldo de heladas de la NASA (spec 035).

Respaldo de VIIRS_LST (que hoy no tenía ninguno). La fuente es la temperatura de la **superficie**
de noche de MODIS: MOD11A1 (Terra) y MYD11A1 (Aqua), producto diario de 1 km (colección 6.1). Entra
solo en la consulta en vivo cuando VIIRS_LST (NOAA-20/21) no devuelve dato para el lote y las fechas.

Satélite independiente (spec 009): hace su propio pedido a la NASA y no importa a ningún otro satélite,
aunque comparta con VIIRS la grilla sinusoidal de 1 km (se repite acá a propósito). Da la temperatura de
la superficie (suelo/canopeo), no la del aire: una helada agronómica se decide con esto más el criterio
del productor. Ojo: MODIS está en fin de misión (Terra y Aqua se retiran), por eso es respaldo y no principal.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_modis_heladas.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-modis-heladas.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_modis_heladas.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_modis_heladas.py "-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300" "2026-11-14" "2026-11-14"`

```
Temperatura de superficie nocturna del lote (MODIS Terra/Aqua, LST de 1 km, RESPALDO de VIIRS) del 2026-11-14 al 2026-11-14 · mosaico h12v12 · 17 s
Capas leídas: {'MOD11A1': '/MODIS_Grid_Daily_1km_LST/Data_Fields/LST_Night_1km', 'MYD11A1': '/MODIS_Grid_Daily_1km_LST/Data_Fields/LST_Night_1km'}

Fecha        T sup °C  Calidad     Detalle
2026-11-14        9.4  buena       Respaldo · MODIS LST nocturna (temperatura de superficie, no del aire) · MOD11A1 (Terra) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 100%
2026-11-14       11.1  buena       Respaldo · MODIS LST nocturna (temperatura de superficie, no del aire) · MOD11A1 (Terra) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 100%
2026-11-14       12.9  buena       Respaldo · MODIS LST nocturna (temperatura de superficie, no del aire) · MOD11A1 (Terra) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 100%
2026-11-14        9.4  buena       Respaldo · MODIS LST nocturna (temperatura de superficie, no del aire) · MYD11A1 (Aqua) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 100%
2026-11-14       —     descartada  Nubes o sin dato · Respaldo · MODIS LST nocturna (temperatura de superficie, no del aire) · MOD11A1 (Terra) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 0%
2026-11-14       12.5  buena       Respaldo · MODIS LST nocturna (temperatura de superficie, no del aire) · MOD11A1 (Terra) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 100%
2026-11-14       —     descartada  Nubes o sin dato · Respaldo · MODIS LST nocturna (temperatura de superficie, no del aire) · MOD11A1 (Terra) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 0%
2026-11-14       —     descartada  Nubes o sin dato · Respaldo · MODIS LST nocturna (temperatura de superficie, no del aire) · MOD11A1 (Terra) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 0%
2026-11-14       10.1  buena       Respaldo · MODIS LST nocturna (temperatura de superficie, no del aire) · MOD11A1 (Terra) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 100%
2026-11-14       —     descartada  Nubes o sin dato · Respaldo · MODIS LST nocturna (temperatura de superficie, no del aire) · MOD11A1 (Terra) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 0%
2026-11-14       —     descartada  Nubes o sin dato · Respaldo · MODIS LST nocturna (temperatura de superficie, no del aire) · MOD11A1 (Terra) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 0%
2026-11-14        6.9  buena       Respaldo · MODIS LST nocturna (temperatura de superficie, no del aire) · MOD11A1 (Terra) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 100%
2026-11-14       14.2  buena       Respaldo · MODIS LST nocturna (temperatura de superficie, no del aire) · MOD11A1 (Terra) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 100%
2026-11-14       —     descartada  Nubes o sin dato · Respaldo · MODIS LST nocturna (temperatura de superficie, no del aire) · MOD11A1 (Terra) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 0%
2026-11-14       14.2  buena       Respaldo · MODIS LST nocturna (temperatura de superficie, no del aire) · MOD11A1 (Terra) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 100%
2026-11-14       19.2  buena       Respaldo · MODIS LST nocturna (temperatura de superficie, no del aire) · MOD11A1 (Terra) · noche del 2026-11-14 · 1 píxeles de 1 km · válidos 100%

16 noches · calidad {'buena': 10, 'descartada': 6} · 10 con dato · 0 con riesgo de helada (≤ 0 °C)
Noche más fría: 2026-11-14 con 6.9 °C de superficie
Variable temp_sup_min_c en °C, fuente MODIS, resolución 1000 m
```
