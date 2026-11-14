# GEDI - cobertura y estructura de la vegetación (láser)

**Rama:** `satelite-gedi-vegetacion` · **Conector:** `rotaterra/fuentes/gedi.py` · **Specs:** `docs/specs/059-vegetacion-de-la-zona-gedi.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector GEDI: cobertura y estructura de la vegetación en la zona del lote, medidas con láser (spec 059).

GEDI es el láser (lidar) de la NASA en la Estación Espacial. Cada disparo mide un círculo de ~25 m y dice qué
fracción del suelo tapa la vegetación (`cover`) y cuánta superficie de hojas y ramas hay por m² de suelo (`pai`).
Los disparos van en líneas separadas ~600 m y la Estación no pasa siempre por el mismo lugar: en un lote de 25 ha
caen de 0 a 7 disparos por pasada. Por eso se mira la **zona** (el lote más 2 km alrededor) y los últimos 3 años,
y el lote solo cuando tiene disparos buenos suficientes.

Sirve para ver montes, cortinas forestales y pastizales de la zona (estructura que el NDVI no muestra). En cultivos
anuales la cobertura que mide GEDI es baja (1 a 12 %): no es un indicador del cultivo.

Producto GEDI02_B (L2B, LP DAAC). No se baja el archivo de cada pasada (~1 GB): el servicio Harmony de la NASA
recorta en sus servidores la zona y solo 6 variables por haz (~1,4 MB en total). Tarda ~3 minutos.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_gedi.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-gedi.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_gedi.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_gedi.py "-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300"`

```
GEDI en el lote y 2 km alrededor, últimos 3 años · 39 s

· gedi_cobertura_zona_pct: 2.8 % · buena · último disparo 2026-11-14 · Cobertura de la vegetación en la zona, mediana de los disparos (fracción del suelo tapada vista desde arriba) · dato de la ZONA, no del lote · 1121 disparos · 
· gedi_cobertura_zona_p90_pct: 24.9 % · buena · último disparo 2026-11-14 · Cobertura de la vegetación en la zona, el 10 % más tapado (montes, cortinas) · dato de la ZONA · 1121 disparos · GEDI L2B (NASA, láser de la Estación Espa
· gedi_monte_zona_pct: 7.7 % · buena · último disparo 2026-11-14 · Disparos con cobertura ≥ 30 % (vegetación leñosa: monte, cortina, arbustal; supuesto a validar) · dato de la ZONA · 1121 disparos · GEDI L2B (NASA, láser de la Est
· gedi_pai_zona: 0.06 m²/m² · buena · último disparo 2026-11-14 · Índice de área de planta (hojas y ramas por m² de suelo), mediana de la zona · dato de la ZONA · 1121 disparos · GEDI L2B (NASA, láser de la Estación Espacial), 01/
· gedi_cobertura_lote_pct: 26.2 % · buena · último disparo 2026-11-14 · Cobertura de la vegetación dentro del lote, mediana de los disparos que cayeron adentro · 10 disparos · GEDI L2B (NASA, láser de la Estación Espacial), 01/11/
```
