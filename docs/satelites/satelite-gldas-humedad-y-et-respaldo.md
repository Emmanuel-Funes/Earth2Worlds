# GLDAS - humedad del suelo y ET como respaldo

**Rama:** `satelite-gldas-humedad-y-et-respaldo` · **Conector:** `rotaterra/fuentes/gldas.py` · **Specs:** `docs/specs/032-humedad-y-et-respaldo-gldas.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector GLDAS: respaldo de humedad del suelo y de ET real de la NASA (spec 032).

Respaldo final de SMAP (humedad) y de la ET (después de ECOSTRESS). La fuente es GLDAS Noah 0.25°
(`GLDAS_NOAH025_3H`, con el producto temprano `_EP` para lo reciente), un modelo de superficie de la
NASA (GES DISC) que da humedad del suelo por capas y ET cada 3 horas, en una grilla de ~25 km, con ~1
mes de atraso. Es un dato REGIONAL de modelo: el píxel cubre miles de hectáreas.

Se lee por OPeNDAP (`.dmr` para los metadatos, `.dap.csv` para el recorte), solo el píxel del lote, y
los 8 pasos de 3 h de cada día se promedian. No importa a ningún otro satélite (spec 009): las ayudas de
OPeNDAP están repetidas acá a propósito.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_gldas.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-gldas.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_gldas.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (en GitHub Actions, corrida https://github.com/Emmanuel-Funes/Earth2Worlds/actions/runs/43600972574). Lote de prueba de San Luis.

Comando: `python probar_gldas.py "<esquinas del lote de prueba>" "2026-09-30" "2026-10-06"`

```
=== Humedad del suelo (GLDAS Noah 0,25 °, respaldo) · centro -33.7025, -65.2975 · del 2026-09-30 al 2026-10-06 ===
(13 s)

Fecha       Variable                 Valor  Calidad     Detalle
2026-09-30  humedad_superficial      0.247  buena       Promedio de 8 pasos de 3 h · Respaldo · humedad del suelo de 0 a 10 cm del modelo GLDAS Noah de la NASA (GES DISC) · píxel de 0,25° (~25 km), dato REGIONAL de modelo, no una 
2026-09-30  humedad_zona_raiz        0.257  buena       Promedio de 8 pasos de 3 h · Respaldo · humedad de la zona de raíces (~0 a 100 cm) del modelo GLDAS Noah de la NASA (GES DISC) · píxel de 0,25° (~25 km), dato REGIONAL de mod
2026-10-01  humedad_superficial      0.302  buena       Promedio de 8 pasos de 3 h · Respaldo · humedad del suelo de 0 a 10 cm del modelo GLDAS Noah de la NASA (GES DISC) · píxel de 0,25° (~25 km), dato REGIONAL de modelo, no una 
2026-10-01  humedad_zona_raiz        0.264  buena       Promedio de 8 pasos de 3 h · Respaldo · humedad de la zona de raíces (~0 a 100 cm) del modelo GLDAS Noah de la NASA (GES DISC) · píxel de 0,25° (~25 km), dato REGIONAL de mod
2026-10-02  humedad_superficial      0.280  buena       Promedio de 8 pasos de 3 h · Respaldo · humedad del suelo de 0 a 10 cm del modelo GLDAS Noah de la NASA (GES DISC) · píxel de 0,25° (~25 km), dato REGIONAL de modelo, no una 
2026-10-02  humedad_zona_raiz        0.263  buena       Promedio de 8 pasos de 3 h · Respaldo · humedad de la zona de raíces (~0 a 100 cm) del modelo GLDAS Noah de la NASA (GES DISC) · píxel de 0,25° (~25 km), dato REGIONAL de mod
2026-10-03  humedad_superficial      0.271  buena       Promedio de 8 pasos de 3 h · Respaldo · humedad del suelo de 0 a 10 cm del modelo GLDAS Noah de la NASA (GES DISC) · píxel de 0,25° (~25 km), dato REGIONAL de modelo, no una 
2026-10-03  humedad_zona_raiz        0.262  buena       Promedio de 8 pasos de 3 h · Respaldo · humedad de la zona de raíces (~0 a 100 cm) del modelo GLDAS Noah de la NASA (GES DISC) · píxel de 0,25° (~25 km), dato REGIONAL de mod
2026-10-04  humedad_superficial      0.260  buena       Promedio de 8 pasos de 3 h · Respaldo · humedad del suelo de 0 a 10 cm del modelo GLDAS Noah de la NASA (GES DISC) · píxel de 0,25° (~25 km), dato REGIONAL de modelo, no una 
2026-10-04  humedad_zona_raiz        0.260  buena       Promedio de 8 pasos de 3 h · Respaldo · humedad de la zona de raíces (~0 a 100 cm) del modelo GLDAS Noah de la NASA (GES DISC) · píxel de 0,25° (~25 km), dato REGIONAL de mod
2026-10-05  humedad_superficial      0.276  buena       Promedio de 8 pasos de 3 h · Respaldo · humedad del suelo de 0 a 10 cm del modelo GLDAS Noah de la NASA (GES DISC) · píxel de 0,25° (~25 km), dato REGIONAL de modelo, no una 
2026-10-05  humedad_zona_raiz        0.262  buena       Promedio de 8 pasos de 3 h · Respaldo · humedad de la zona de raíces (~0 a 100 cm) del modelo GLDAS Noah de la NASA (GES DISC) · píxel de 0,25° (~25 km), dato REGIONAL de mod
2026-10-06  humedad_superficial      0.264  buena       Promedio de 8 pasos de 3 h · Respaldo · humedad del suelo de 0 a 10 cm del modelo GLDAS Noah de la NASA (GES DISC) · píxel de 0,25° (~25 km), dato REGIONAL de modelo, no una 
2026-10-06  humedad_zona_raiz        0.260  buena       Promedio de 8 pasos de 3 h · Respaldo · humedad de la zona de raíces (~0 a 100 cm) del modelo GLDAS Noah de la NASA (GES DISC) · píxel de 0,25° (~25 km), dato REGIONAL de mod

14 observaciones · 14 con dato · fuente GLDAS, resolución 25000 m

=== Evapotranspiración real (GLDAS Noah 0,25 °, respaldo) · centro -33.7025, -65.2975 · del 2026-09-30 al 2026-10-06 ===
(10 s)

Fecha       Variable                 Valor  Calidad     Detalle
2026-09-30  et_mm_dia                1.259  buena       Promedio de 8 pasos de 3 h · Respaldo · evapotranspiración real del modelo GLDAS Noah de la NASA (GES DISC) · píxel de 0,25° (~25 km), dato REGIONAL de modelo, no una medició
2026-10-01  et_mm_dia                2.596  buena       Promedio de 8 pasos de 3 h · Respaldo · evapotranspiración real del modelo GLDAS Noah de la NASA (GES DISC) · píxel de 0,25° (~25 km), dato REGIONAL de modelo, no una medició
2026-10-02  et_mm_dia                2.396  buena       Promedio de 8 pasos de 3 h · Respaldo · evapotranspiración real del modelo GLDAS Noah de la NASA (GES DISC) · píxel de 0,25° (~25 km), dato REGIONAL de modelo, no una medició
2026-10-03  et_mm_dia                3.116  buena       Promedio de 8 pasos de 3 h · Respaldo · evapotranspiración real del modelo GLDAS Noah de la NASA (GES DISC) · píxel de 0,25° (~25 km), dato REGIONAL de modelo, no una medició
2026-10-04  et_mm_dia                2.195  buena       Promedio de 8 pasos de 3 h · Respaldo · evapotranspiración real del modelo GLDAS Noah de la NASA (GES DISC) · píxel de 0,25° (~25 km), dato REGIONAL de modelo, no una medició
2026-10-05  et_mm_dia                2.293  buena       Promedio de 8 pasos de 3 h · Respaldo · evapotranspiración real del modelo GLDAS Noah de la NASA (GES DISC) · píxel de 0,25° (~25 km), dato REGIONAL de modelo, no una medició
2026-10-06  et_mm_dia                2.154  buena       Promedio de 8 pasos de 3 h · Respaldo · evapotranspiración real del modelo GLDAS Noah de la NASA (GES DISC) · píxel de 0,25° (~25 km), dato REGIONAL de modelo, no una medició

7 observaciones · 7 con dato · fuente GLDAS, resolución 25000 m
```
