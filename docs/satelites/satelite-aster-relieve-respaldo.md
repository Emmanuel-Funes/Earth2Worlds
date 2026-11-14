# ASTER GDEM - relieve como segundo respaldo de NASADEM

**Rama:** `satelite-aster-relieve-respaldo` · **Conector:** `rotaterra/fuentes/aster.py` · **Specs:** `docs/specs/008-altimetria-nasadem.md`, `docs/specs/016-altimetria-copernicus-dem-respaldo.md`, `docs/specs/037-altimetria-respaldo-aster.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector ASTER GDEM v3 (NASA/METI): altura, pendiente y ambientes del lote, respaldo de NASADEM (spec 037).

Mismas 7 variables y mismas reglas que NASADEM (spec 008) y Copernicus DEM (spec 016), con el modelo global
de 30 m de la NASA y el METI de Japón (ASTGTM, colección v003). Es un segundo respaldo de relieve, después
de Copernicus DEM. Se baja el mosaico de 1° del lote por CMR + Earthdata y se lee con rasterio solo la
ventana del lote. No importa a ningún otro satélite (spec 009).

ASTER GDEM v3 es un COMPUESTO de tomas de 2000 a 2013 (publicado en 2019): es un dato fijo por lugar.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_aster.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-aster.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_aster.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_aster.py "-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300"`

```
Altimetría del lote (ASTER GDEM v3, NASA/METI, 30 m, fecha 2026-11-14) · 3 s

Variable                      Valor  Unidad Calidad     NASADEM
altura_media_m                487.7  m      buena         488.4
altura_min_m                    479  m      buena           485
altura_max_m                    493  m      buena           492
pendiente_media_pct            6.94  %      buena          2.76
superficie_bajo_ha             7.78  ha     buena          8.28
superficie_media_loma_ha       7.38  ha     buena         10.86
superficie_loma_ha            10.56  ha     buena          6.58

Detalle: bajo / loma = más de 1 m por debajo / por encima de la media del lote (umbral supuesto, a calibrar) · proporción de píxeles × 25.7 ha del lote · ASTER GDEM v3 de la NASA y el METI (compuesto de tomas 2000–2013, publicado 
```
