# MERRA-2 - temperatura y radiación como respaldo de POWER

**Rama:** `satelite-merra2-clima-respaldo` · **Conector:** `rotaterra/fuentes/merra2.py` · **Specs:** `docs/specs/006-lluvia-imerg-y-respaldo-merra2.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector MERRA-2: temperatura y radiación diarias, respaldo de NASA POWER (spec 006).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_merra2.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-merra2.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_merra2.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_merra2.py "-33.70" "-65.30" "2026-11-14" "2026-11-14"`

```
Respaldo MERRA-2 (temperatura y radiación) en (-33.7, -65.3) del 2026-11-14 al 2026-11-14 · 5 s

Fecha         Máx °C  Mín °C   MJ/m²
2026-11-14      21.8     8.5    14.1
2026-11-14      19.9     8.3    23.7
```
