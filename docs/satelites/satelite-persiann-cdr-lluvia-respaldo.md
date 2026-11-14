# PERSIANN-CDR - lluvia como respaldo de IMERG

**Rama:** `satelite-persiann-cdr-lluvia-respaldo` · **Conector:** `rotaterra/fuentes/persiann.py` · **Specs:** `docs/specs/008-altimetria-nasadem.md`, `docs/specs/038-lluvia-respaldo-persiann.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Tercer respaldo de la lluvia de IMERG con NOAA PERSIANN-CDR (spec 038).

Satélite independiente (spec 009): baja sus propios archivos diarios de NOAA NCEI y no usa otros satélites.
NOAA es una de las agencias socias de la NASA permitidas (spec 008). Entra como tercer respaldo de la
lluvia, detrás de IMERG (principal), POWER (respaldo 1) y CPC (respaldo 2).

PERSIANN-CDR es una estimación por satélite (infrarrojo), calibrada con GPCP mensual: es un *Climate Data
Record* de NOAA. A diferencia de CPC (pluviómetros) estima la lluvia donde no hay estaciones, así que sirve
como última red de contención cuando IMERG y los dos primeros respaldos fallan o no traen el día.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_persiann.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-persiann.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_persiann.py <lat> <lon> <desde> <hasta>` en la compu.
- No necesita claves.

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_persiann.py "-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300" "2026-11-14" "2026-11-14"`

```
Lluvia NOAA PERSIANN-CDR (estimación por satélite, precip) como respaldo de IMERG · satélite IMERG:PERSIANN (respaldo de IMERG, orden 3)
Centro del lote (-33.7025, -65.2975) · del 2026-11-14 al 2026-11-14 · 5.3 s

Fecha        Lluvia mm  Calidad     Nota
2026-11-14        1.02  buena       Respaldo de IMERG · NOAA PERSIANN-CDR (estimación por satélite, calibrada con GPCP) · celda de 0,25°
2026-11-14        1.40  buena       Respaldo de IMERG · NOAA PERSIANN-CDR (estimación por satélite, calibrada con GPCP) · celda de 0,25°
2026-11-14        0.13  buena       Respaldo de IMERG · NOAA PERSIANN-CDR (estimación por satélite, calibrada con GPCP) · celda de 0,25°
2026-11-14        0.56  buena       Respaldo de IMERG · NOAA PERSIANN-CDR (estimación por satélite, calibrada con GPCP) · celda de 0,25°
2026-11-14        0.95  buena       Respaldo de IMERG · NOAA PERSIANN-CDR (estimación por satélite, calibrada con GPCP) · celda de 0,25°
2026-11-14        0.40  buena       Respaldo de IMERG · NOAA PERSIANN-CDR (estimación por satélite, calibrada con GPCP) · celda de 0,25°
2026-11-14        0.00  buena       Respaldo de IMERG · NOAA PERSIANN-CDR (estimación por satélite, calibrada con GPCP) · celda de 0,25°
2026-11-14        1.41  buena       Respaldo de IMERG · NOAA PERSIANN-CDR (estimación por satélite, calibrada con GPCP) · celda de 0,25°
2026-11-14        0.00  buena       Respaldo de IMERG · NOAA PERSIANN-CDR (estimación por satélite, calibrada con GPCP) · celda de 0,25°
2026-11-14        0.52  buena       Respaldo de IMERG · NOAA PERSIANN-CDR (estimación por satélite, calibrada con GPCP) · celda de 0,25°
2026-11-14        0.47  buena       Respaldo de IMERG · NOAA PERSIANN-CDR (estimación por satélite, calibrada con GPCP) · celda de 0,25°
2026-11-14        0.00  buena       Respaldo de IMERG · NOAA PERSIANN-CDR (estimación por satélite, calibrada con GPCP) · celda de 0,25°
2026-11-14        0.00  buena       Respaldo de IMERG · NOAA PERSIANN-CDR (estimación por satélite, calibrada con GPCP) · celda de 0,25°
2026-11-14        0.00  buena       Respaldo de IMERG · NOAA PERSIANN-CDR (estimación por satélite, calibrada con GPCP) · celda de 0,25°

14 días · calidad {'buena': 14} · total 6.9 mm
Variable lluvia_mm en mm/día, fuente PERSIANN, resolución 27000 m
```
