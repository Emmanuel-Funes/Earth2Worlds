# Spec 031 · Respaldo de suelo con HWSD de la NASA

**Estado:** propuesta (investigación 028, aprobada por Hernán: "Bueno, sigamos con el proyecto, acepto lo que decías") · **Etapa:** pipeline satélite → API → app · **Requiere:** credenciales de Earthdata (`EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD`, ya cargadas) · **Rama:** `HWSD-suelo_respaldo` · **Depende de:** (`NUCLEO-varios_respaldos_en_orden`)

## Objetivo

Darle un **respaldo** al suelo, que hoy depende solo de GeoINTA (spec 020/021) y no tiene ninguno. Cuando los servidores del INTA (WFS y WMS de los nodos) no responden, la app se queda sin textura ni pH del lote. HWSD cubre ese hueco con una fuente de la NASA.

La fuente es la **Harmonized World Soil Database v1.2 regrillada** (`HWSD_1247`) del ORNL DAAC de la NASA (agencia permitida, spec 008). Es una base mundial de suelo en una grilla de 0,05° (~5,5 km) con, para cada celda, la textura (arena, limo, arcilla), el pH, el carbono orgánico y la clase de agua útil, en dos profundidades: superficie (T, 0–30 cm) y subsuelo (S, 30–100 cm). Se verificó en la investigación 028: el lote de San Luis dio **83 % de arena, 6 % de arcilla y pH 8,1** en 0–30 cm, que coincide con lo que da GeoINTA (franco arenoso, pH ~8,5).

Es un **respaldo**, no una fuente nueva: entrega las mismas variables de textura y pH que GeoINTA, con menor prioridad, así la consulta usa GeoINTA cuando responde y recurre a HWSD solo cuando GeoINTA se cae por completo.

## Fuente

| Producto | Agencia | Qué da | Grilla | Demora | Acceso |
|---|---|---|---|---|---|
| `HWSD_1247` (Regridded Harmonized World Soil Database v1.2), capas `T_SAND`, `T_SILT`, `T_CLAY`, `T_PH_H2O` (0–30 cm) y `S_SAND`, `S_CLAY`, `S_PH_H2O` (30–100 cm) | NASA (ORNL DAAC) | Textura y pH del suelo | 0,05° (~5,5 km) | dato fijo (base de 2012) | CMR + descarga del NetCDF de cada capa, leído con rasterio |

Es un dato **estático**: la base no cambia, así que cada capa se baja una sola vez y se guarda en caché (igual que el archivo de mascons de GRACE, spec 026). El núcleo marca la fuente como `estatico=True`: una vez que un lote tiene suelo, no se vuelve a pedir.

## Entrada

El lote como lo recibe cualquier satélite: `lote["id"]` y `lote["poligono"]` (GeoJSON, EPSG:4326). HWSD es estático, así que no usa el período.

## Proceso

1. Validar el polígono. Un pedido inválido no llama a la NASA.
2. Tomar el centro del lote (la celda de 5,5 km es más grande que casi cualquier lote).
3. Por cada capa, pedir a CMR el archivo de `HWSD_1247`, bajarlo (una vez, a la caché) y leer con rasterio solo la celda que contiene el centro.
4. Textura: pasar arena/limo/arcilla al **triángulo textural del USDA** y a la clase común 1–12 (spec 021). La capa de superficie (0–30 cm) llena las dos variables de GeoINTA de superficie (0–15 y 15–30 cm) y la de subsuelo (30–100 cm) llena las dos de abajo (30–60 y 60–100 cm); la `nota` aclara que HWSD solo tiene esas dos profundidades.
5. pH: tomar el valor de la celda (0–14). `T_PH_H2O` → `suelo_ph_0_30cm`, `S_PH_H2O` → `suelo_ph_30_100cm` (las profundidades coinciden con las de GeoINTA).

## Salida (contrato común)

```json
{"lote_id": "lote-7", "fecha": "2012-03-01", "variable": "suelo_textura_0_15cm", "valor": 2.0,
 "unidad": "clase textural (1 arenoso … 12 arcilloso, spec 021)", "fuente": "HWSD", "resolucion_m": 5500,
 "calidad": "dudosa", "nota": "Respaldo de GeoINTA · HWSD v1.2 de la NASA (ORNL DAAC) · arena 83 %, limo 11 %, arcilla 6 % → areno franco (clase común 2) · celda de 0,05° (~5,5 km), 0–30 cm usada para 0–15 cm · dato REGIONAL de modelo, no una medición del lote"}
```

- Las variables son las mismas de GeoINTA (`suelo_textura_0_15cm`, `…_15_30cm`, `…_30_60cm`, `…_60_100cm`, `suelo_ph_0_30cm`, `suelo_ph_30_100cm`), con las mismas unidades, para que el núcleo lo trate como respaldo de GeoINTA.
- `fuente: "HWSD"` es nueva en el contrato. En `base.py` se le da prioridad 5 (bien por debajo de GeoINTA, que es 1).
- La calidad de HWSD es como mucho `dudosa`: es un valor de modelo regional de 5,5 km, no una medición del lote. Fuera de rango físico → `descartada` con `valor: null`.

## Reglas de calidad

1. **Nunca inventar.** Celda sin dato, relleno o fuera de rango físico (arena/arcilla fuera de 0–100 %, pH fuera de 0–14) → `descartada` con `valor: null` y la `nota` dice por qué.
2. **Calidad `dudosa`, nunca `buena`:** HWSD es un modelo mundial de 5,5 km; la celda cubre miles de hectáreas, no el lote. Es un respaldo para cuando GeoINTA no está, no un reemplazo.
3. **Supuesto de profundidad:** HWSD solo distingue 0–30 y 30–100 cm. La capa de superficie se repite para las dos profundidades finas de GeoINTA de arriba (0–15 y 15–30) y la de subsuelo para las dos de abajo (30–60 y 60–100). La `nota` lo aclara en cada caso.
4. **Supuesto de resolución:** se toma del archivo (grilla de 0,05°); si no se puede leer, se usa 5500 m y la `nota` lo marca como supuesto.

## Dónde entra

- **Registro (spec 009):** `SATELITES = [Satelite("GeoINTA:HWSD", pedir, respaldo_de="GeoINTA", estatico=True)]`. Es el **respaldo** de GeoINTA (hoy GeoINTA no tiene ninguno).
- **Consulta en el momento (spec 012):** si GeoINTA responde (aunque sea con algún dato), se usa GeoINTA; si GeoINTA se cae por completo, responde HWSD.
- **Núcleo:** se agrega `"HWSD"` al contrato (`Fuente`) y `"HWSD": 5` a `PRIORIDAD` en `base.py` (único cambio de núcleo permitido por la Guía, punto 9, porque fija la confianza de la fuente). No toca ningún otro archivo del núcleo ni a otro satélite.

## Prueba real

Workflow `Probar HWSD (suelo)` (`.github/workflows/probar-hwsd-suelo.yml`, `probar_hwsd_suelo.py`). Por defecto, el lote de prueba de San Luis. Corre en cada PR que toque estos archivos y a mano con un clic. Necesita las credenciales de Earthdata (ya cargadas como secrets).

## Resultado de la prueba real

Workflow `Probar HWSD (suelo)`, lote de prueba (centro −33,7025; −65,2975), respuesta en 9 s, celda de 0,05° (~4631 m). Las 6 variables con dato:

| Variable | Valor | Calidad | Lectura |
|---|---|---|---|
| suelo_textura_0_15cm | 2 (areno franco) | dudosa | 0–30 cm: arena 83 %, limo 11 %, arcilla 6 % |
| suelo_textura_15_30cm | 2 (areno franco) | dudosa | 0–30 cm (reusada para 15–30 cm) |
| suelo_textura_30_60cm | 2 (areno franco) | dudosa | 30–100 cm: arena 84 %, limo 11 %, arcilla 5 % |
| suelo_textura_60_100cm | 2 (areno franco) | dudosa | 30–100 cm (reusada para 60–100 cm) |
| suelo_ph_0_30cm | 8,10 | dudosa | pH 0–30 cm |
| suelo_ph_30_100cm | 8,50 | dudosa | pH 30–100 cm |

Coincide con la investigación 028 (83 % arena, pH 8,1) y con GeoINTA (franco arenoso, pH ~8,5): el respaldo da el mismo cuadro de suelo arenoso y alcalino del lote.

## Criterios de aceptación

- [x] La celda del lote en la grilla de 0,05° se ubica por el centro y vuelve el valor correcto (tests de lectura con un ráster real de prueba; prueba real: celda ~4631 m).
- [x] Arena/limo/arcilla se clasifican con el triángulo del USDA a la clase común 1–12, y el lote de San Luis (83 % arena, 6 % arcilla) da areno franco (clase 2) (test `test_el_lote_de_san_luis_es_areno_franco` y prueba real).
- [x] La capa de superficie llena 0–15 y 15–30 cm, y la de subsuelo 30–60 y 60–100 cm, con el aviso de profundidad en la nota (prueba real: las 4 profundidades con su aviso "0–30 cm usada para …").
- [x] El pH de 0–30 y 30–100 cm sale de `T_PH_H2O` y `S_PH_H2O` (8,10 y 8,50 en la prueba real); valores fuera de 0–14 no se inventan (`test_observacion_ph_fuera_de_rango_no_inventa`).
- [x] HWSD es `dudosa`, nunca `buena`; una celda sin dato o fuera de rango queda `descartada` sin inventar (tests y prueba real: las 6 `dudosa`).
- [x] Se anuncia como `GeoINTA:HWSD`, respaldo de GeoINTA, estático, y no importa ningún otro satélite (`test_se_anuncia_como_respaldo_de_geointa` y `tests/test_nucleo.py`).
- [x] Un pedido inválido no llama a la NASA; sin credenciales pide credenciales (`test_pedido_invalido_no_llama_a_la_nasa`, `test_sin_credenciales_pide_credenciales`).
- [x] Tests sin internet verdes (38 pasan en local).
- [x] Prueba real con un clic y automática en cada PR que toque el conector (`Probar HWSD (suelo)` en verde): 6 de 6 variables con dato, en 9 s.

## Fuera de alcance

- El carbono orgánico y la clase de agua útil de HWSD (variables que GeoINTA no tiene todavía; se dejan anotadas para una etapa posterior).
- Respaldar el índice de productividad y la clase de capacidad de uso de GeoINTA: son índices propios del INTA que HWSD no calcula.
- La versión nativa de 30 arc-seg (~1 km) de HWSD (la regrillada de 0,05° alcanza para un respaldo regional).
