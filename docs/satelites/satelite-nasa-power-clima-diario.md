# NASA POWER - clima diario del lote (temperatura, lluvia, radiación)

**Rama:** `satelite-nasa-power-clima-diario` · **Conector:** `rotaterra/fuentes/power.py` · **Specs:** `docs/specs/001-conector-nasa-power.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector NASA POWER: clima diario por punto (spec 001).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_power.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-power.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_power.py <lat> <lon> <desde> <hasta>` en la compu.
- No necesita claves.

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_power.py "-33.70" "-65.30" "2026-10-28" "2026-11-06"`

```
Clima NASA POWER en (-33.7, -65.3) del 2026-10-28 al 2026-11-06

Fecha         T máx °C  T mín °C  Lluvia mm  Radiación MJ/m²
2026-10-28        27.0      10.5        0.1             24.7
2026-10-29        28.1      14.9        0.4             23.0
2026-10-30        29.0      15.5        0.5             24.2
2026-10-31        29.8      13.7        1.8              5.2
2026-11-01        28.0      17.1        2.7             21.5
2026-11-02        27.4      13.8        0.4             21.8
2026-11-03        23.6      16.4        9.6              6.5
2026-11-04        23.1      14.2        1.1             30.0
2026-11-05        30.6      12.2        0.1         sin dato
2026-11-06        22.6      12.0        4.9             11.0

Calidad de los 40 valores: {'buena': 39, 'descartada': 1}
```
