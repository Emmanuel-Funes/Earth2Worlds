# Spec 059 · Cobertura y estructura de la vegetación de la zona con GEDI

**Estado:** construida y probada con datos reales (30/10/2026) · **Aprobada por:** Hernán, 30/10/2026 (tarjeta "¿Sumamos GEDI como referencia de la zona alrededor del lote?" → "Sí, después del clima futuro") · **Rama:** `GEDI-cobertura_de_la_zona` · **Depende de:** PR #24 (`NUCLEO-varios_respaldos_en_orden`) · **Requiere:** Earthdata (ya cargado)

## Objetivo

El desafío Field Shift nombra a **GEDI** (biomasa y estructura de la vegetación). GEDI es un láser: mide la vegetación **en altura**, cosa que el NDVI no ve. Para Rotaterra sirve para saber **cuánto monte, cortina forestal o arbustal hay en la zona del lote** y qué tan tapado está el suelo. Eso pesa en la erosión eólica, la biodiversidad y los refugios de plagas y enemigos naturales.

**No es un indicador del cultivo:** en cultivos anuales GEDI mide coberturas bajas (1 a 12 %).

## Fuente

| Producto | Agencia | Qué da | Huella | Acceso |
|---|---|---|---|---|
| `GEDI02_B` (la versión más nueva en CMR; hoy la 003) | NASA (GEDI, Estación Espacial; LP DAAC) | Por disparo: fracción del suelo tapada por la vegetación (`cover`), índice de área de planta (`pai`) y calidad | Círculo de ~25 m; líneas cada ~600 m | Servicio **Harmony** de la NASA: recorta en sus servidores la zona y 6 variables por haz |

Cada pasada pesa ~1 GB. Sin pedir variables, el recorte de la zona igual pesaba 64 a 189 MB por pasada (1,4 GB en total). Con las 6 variables el total baja a **1,4 MB**.

## Entrada

`lote["id"]` y `lote["poligono"]` (GeoJSON EPSG:4326). No usa el período del pedido: siempre los **últimos 3 años**.

## Proceso

1. Validar el polígono. GEDI solo mide entre 51,6° S y 51,6° N.
2. Armar la **zona**: el rectángulo del lote agrandado **2 km** hacia cada lado.
3. Mandar a Harmony el recorte de `GEDI02_B` en la zona y el período, con `lat_lowestmode`, `lon_lowestmode`, `cover`, `pai`, `l2b_quality_flag_rel3` y `geolocation/delta_time` de los 8 haces.
4. Esperar el trabajo (consulta cada 10 s, tope 15 minutos) y leer cada recorte con h5py.
5. Quedarse con los disparos de calidad 1 y con valores físicos (`cover` 0-1, `pai` 0-12).
6. Resumir la zona y, aparte, los disparos que caen **dentro del polígono**.
7. Guardar los disparos en memoria por lote: la segunda consulta contesta al instante.

## Salida (contrato común)

| Variable | Unidad | Qué es |
|---|---|---|
| `gedi_cobertura_zona_pct` | % | Mediana de la cobertura de la zona |
| `gedi_cobertura_zona_p90_pct` | % | El 10 % más tapado de la zona (montes, cortinas) |
| `gedi_monte_zona_pct` | % | Porcentaje de disparos con cobertura ≥ 30 % (vegetación leñosa) |
| `gedi_pai_zona` | m²/m² | Mediana del índice de área de planta de la zona |
| `gedi_cobertura_lote_pct` | % | Mediana de la cobertura de los disparos dentro del lote |

- `fuente: "GEDI"` (se suma al contrato), `resolucion_m: 25`, `fecha` = día del último disparo bueno.
- La nota dice período, cantidad de disparos buenos y totales, pasadas, y si el dato es de la zona o del lote.

## Reglas de calidad

1. **Nunca inventar.** Sin disparos buenos → `descartada`, `valor: null`.
2. Zona con ≥ 30 disparos buenos → `buena`; con menos → `dudosa`.
3. Lote con ≥ 5 disparos buenos adentro → `buena`; con menos → `dudosa`, y la nota lo dice.
4. **Supuesto:** cobertura ≥ 30 % = vegetación leñosa. A validar con un agrónomo o con la cartografía de bosque nativo.
5. **Supuesto:** 2 km alrededor y 3 años alcanzan para tener disparos suficientes (en la prueba: 1.121 buenos).
6. **Riesgo:** GEDI estuvo guardado de 2023 a 2024 y vuelve a quedar en riesgo cuando la Estación cambie de carga útil. Si no hay disparos, la fuente lo dice.

## Tiempo

**~2 a 3 minutos** la primera vez (136 s en la prueba real, casi todo es la espera del trabajo de Harmony). Después, al instante.

## Dónde entra

- **Registro (spec 009):** `SATELITES = [Satelite("GEDI", pedir)]`. Fuente propia, no respaldo; no toca el núcleo.
- **Ruta de prueba:** `POST /vegetacion-gedi` con `lote_id` y `poligono`.
- `requirements.txt`: se suma `h5py` (ya está en Render por NISAR y Sentinel-3).

## Criterios de aceptación

- [x] Tests sin internet: zona de 2 km, órbita, variables codificadas, lectura del recorte y fecha, zona y lote, relleno y mala calidad afuera, sin disparos no inventa, memoria por lote, ruta que valida el polígono.
- [x] Prueba real sobre el lote de San Luis.
- [ ] Validar el umbral de vegetación leñosa (30 %).

## Prueba real

30/10/2026 01:35 UTC desde el entorno de la nube (`probar_gedi.py` con el lote de prueba, 25 ha). Período 1/10/2023 a 30/10/2026. **136 s.** 11 pasadas, 2.849 disparos en la zona, **1.121 buenos** (el resto, de noche nublada o con poca señal).

| Variable | Valor | Calidad |
|---|---|---|
| Cobertura de la zona (mediana) | 2,8 % | buena |
| Cobertura de la zona (10 % más tapado) | 24,9 % | buena |
| Disparos con vegetación leñosa (≥ 30 %) | 7,7 % | buena |
| Índice de área de planta de la zona | 0,1 m²/m² | buena |
| Cobertura dentro del lote (10 disparos) | 26,2 % | buena |

**Lectura:** la zona es casi toda cultivo o pastizal ralo (mediana 2,8 %), con manchones de monte o cortinas (~8 % de los disparos). Dentro del lote, los 10 disparos dan una mediana de 26 %: vale mirar en la imagen si el lote tiene árboles o un bajo con arbustal antes de usar ese número.
