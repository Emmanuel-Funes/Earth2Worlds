# GPM IMERG - lluvia diaria del lote

**Rama:** `satelite-gpm-imerg-lluvia` · **Conector:** `rotaterra/fuentes/imerg.py` · **Specs:** `docs/specs/006-lluvia-imerg-y-respaldo-merra2.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector GPM IMERG: lluvia diaria del punto del lote (spec 006).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_imerg.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-imerg.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_imerg.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (en GitHub Actions, corrida https://github.com/Emmanuel-Funes/Earth2Worlds/actions/runs/43600975413). Lote de prueba de San Luis.

Comando: `python probar_imerg.py "-33.70" "-65.30" "2026-10-28" "2026-11-10"`

```
Lluvia GPM IMERG en (-33.7, -65.3) del 2026-10-28 al 2026-11-10 · 4 s

Fecha            mm  Calidad     Producto
2026-10-28      0.0  buena       IMERG Late, sin corregir con pluviómetros · celda de 0,1°
2026-10-29      0.0  buena       IMERG Late, sin corregir con pluviómetros · celda de 0,1°
2026-10-30      3.9  buena       IMERG Late, sin corregir con pluviómetros · celda de 0,1°
2026-10-31      5.5  buena       IMERG Late, sin corregir con pluviómetros · celda de 0,1°
2026-11-01     14.3  buena       IMERG Late, sin corregir con pluviómetros · celda de 0,1°
2026-11-02      1.4  buena       IMERG Late, sin corregir con pluviómetros · celda de 0,1°
2026-11-03     13.2  buena       IMERG Late, sin corregir con pluviómetros · celda de 0,1°
2026-11-04      0.0  buena       IMERG Late, sin corregir con pluviómetros · celda de 0,1°
2026-11-05      0.0  buena       IMERG Late, sin corregir con pluviómetros · celda de 0,1°
2026-11-06      0.1  buena       IMERG Late, sin corregir con pluviómetros · celda de 0,1°
2026-11-07      0.0  buena       IMERG Late, sin corregir con pluviómetros · celda de 0,1°
2026-11-08      0.0  buena       IMERG Late, sin corregir con pluviómetros · celda de 0,1°
2026-11-09      0.0  buena       IMERG Late, sin corregir con pluviómetros · celda de 0,1°
2026-11-10      1.9  buena       IMERG Late, sin corregir con pluviómetros · celda de 0,1°

Lluvia acumulada: 40.4 mm en 14 días.
```
