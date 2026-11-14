# NASA POWER - lluvia diaria como respaldo de IMERG

**Rama:** `satelite-nasa-power-lluvia-respaldo` · **Conector:** `rotaterra/fuentes/power_lluvia.py` · **Specs:** `docs/specs/013-lluvia-respaldo-power.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Respaldo de la lluvia de IMERG con NASA POWER: lluvia diaria del punto del lote (spec 013).

Satélite independiente (spec 009): hace su propio pedido a POWER y no usa el conector `power.py`.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_power_lluvia.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-power-lluvia.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_power_lluvia.py <lat> <lon> <desde> <hasta>` en la compu.
- No necesita claves.

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_power_lluvia.py "-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300" "2026-10-28" "2026-11-10"`

```
Lluvia NASA POWER (PRECTOTCORR, día UTC) como respaldo de IMERG · satélite IMERG:POWER (respaldo de IMERG, orden 1)
Centro del lote (-33.7025, -65.2975) · del 2026-10-28 al 2026-11-10 · 0.6 s

Fecha        Lluvia mm  Calidad     Nota
2026-10-28        0.09  buena       Respaldo de IMERG · NASA POWER (MERRA-2/IMERG corregido) · celda de 0,5°
2026-10-29        0.05  buena       Respaldo de IMERG · NASA POWER (MERRA-2/IMERG corregido) · celda de 0,5°
2026-10-30        0.81  buena       Respaldo de IMERG · NASA POWER (MERRA-2/IMERG corregido) · celda de 0,5°
2026-10-31        0.56  buena       Respaldo de IMERG · NASA POWER (MERRA-2/IMERG corregido) · celda de 0,5°
2026-11-01        3.87  buena       Respaldo de IMERG · NASA POWER (MERRA-2/IMERG corregido) · celda de 0,5°
2026-11-02        0.13  buena       Respaldo de IMERG · NASA POWER (MERRA-2/IMERG corregido) · celda de 0,5°
2026-11-03        9.62  buena       Respaldo de IMERG · NASA POWER (MERRA-2/IMERG corregido) · celda de 0,5°
2026-11-04        1.47  buena       Respaldo de IMERG · NASA POWER (MERRA-2/IMERG corregido) · celda de 0,5°
2026-11-05        0.11  buena       Respaldo de IMERG · NASA POWER (MERRA-2/IMERG corregido) · celda de 0,5°
2026-11-06        1.99  buena       Respaldo de IMERG · NASA POWER (MERRA-2/IMERG corregido) · celda de 0,5°
2026-11-07        3.27  buena       Respaldo de IMERG · NASA POWER (MERRA-2/IMERG corregido) · celda de 0,5°
2026-11-08        0.00  buena       Respaldo de IMERG · NASA POWER (MERRA-2/IMERG corregido) · celda de 0,5°
2026-11-09        0.00  buena       Respaldo de IMERG · NASA POWER (MERRA-2/IMERG corregido) · celda de 0,5°
2026-11-10        1.40  buena       Respaldo de IMERG · NASA POWER (MERRA-2/IMERG corregido) · celda de 0,5°

14 días · calidad {'buena': 14} · total 23.4 mm
Variable lluvia_mm en mm/día, fuente POWER, resolución 55000 m
```
