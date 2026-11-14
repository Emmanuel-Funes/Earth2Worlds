# Copernicus DEM - relieve como respaldo de NASADEM

**Rama:** `satelite-copernicus-dem-relieve-respaldo` · **Conector:** `rotaterra/fuentes/copdem.py` · **Specs:** `docs/specs/008-altimetria-nasadem.md`, `docs/specs/016-altimetria-copernicus-dem-respaldo.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector Copernicus DEM GLO-30 (ESA): altura, pendiente y ambientes del lote, respaldo de NASADEM (spec 016).

Mismas 7 variables y mismas reglas que NASADEM (spec 008), con el modelo de la ESA hecho con TanDEM-X.
Se lee sin credenciales del bucket público de AWS Open Data que distribuye los archivos de la ESA.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_copdem.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-copdem.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_copdem.py <lat> <lon> <desde> <hasta>` en la compu.
- No necesita claves.

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_copdem.py "-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300"`

```
Altimetría del lote (Copernicus DEM GLO-30 de la ESA, 30 m, fecha 2026-11-14) · 2 s · mosaicos ['S34_00_W066_00']

Variable                      Valor  Unidad Calidad     NASADEM
altura_media_m                489.4  m      buena         488.4
altura_min_m                  487.1  m      buena           485
altura_max_m                  493.4  m      buena           492
pendiente_media_pct            2.09  %      buena          2.76
superficie_bajo_ha             8.36  ha     buena          8.28
superficie_media_loma_ha       10.6  ha     buena         10.86
superficie_loma_ha             6.76  ha     buena          6.58

Detalle: bajo / loma = más de 1 m por debajo / por encima de la media del lote (umbral supuesto, a calibrar) · proporción de píxeles × 25.7 ha del lote · Copernicus DEM GLO-30 de la ESA (TanDEM-X, tomado del 14/11/2026 al 30/10/20
```
