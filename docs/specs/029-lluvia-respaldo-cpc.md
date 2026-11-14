# Spec 029 · Segundo respaldo de la lluvia con NOAA CPC (gauge-based)

**Estado:** propuesta (investigación 028, aprobada por Hernán: "Si, dale, ya tengo la autorización") · **Etapa:** pipeline satélite → API → app · **Requiere:** nada (archivo público de NOAA PSL, sin cuenta) · **Rama:** `CPC-lluvia_respaldo` · **Depende de:** (`NUCLEO-varios_respaldos_en_orden`)

## Objetivo

Que la lluvia del lote siga llegando, y con mejor base, cuando **GPM IMERG** (spec 006, principal de `lluvia_mm`) **y** su primer respaldo **NASA POWER** (spec 013) fallan, quedan pendientes o no traen datos.

Hay una segunda razón, de calidad: la NASA **dejó de publicar IMERG Final el 30/9/2025** (investigación 028), así que toda la lluvia de IMERG desde esa fecha es **IMERG Late**, sin la corrección por pluviómetros que trae el producto Final. POWER es un modelo (MERRA-2) y en el lote de prueba subestima los chaparrones y marca lloviznas de décimas en días secos (spec 013 y calibración del balance, spec 024). **NOAA CPC Global Unified** es un análisis **basado en pluviómetros**, de una agencia socia permitida (spec 008), así que aporta una mirada independiente y más terrestre de la lluvia.

## Fuente

| Producto | Agencia | Qué da | Grilla | Demora | Acceso |
|---|---|---|---|---|---|
| CPC Global Unified Gauge-Based Analysis of Daily Precipitation | NOAA (Physical Sciences Laboratory) | Lluvia diaria interpolada de pluviómetros, en mm/día | 0,5° (~55 km) | ~1 a 2 días | `https://downloads.psl.noaa.gov/Datasets/cpc_global_precip/precip.{AÑO}.nc`, público, sin cuenta |

Es un NetCDF por año (variable `precip`, mm, eje de tiempo "hours since 1900-01-01" según GDAL, longitudes de 0 a 360). Verificado en la investigación 028: en el lote de San Luis el archivo `precip.2026.nc` traía datos hasta, y del 1 al 14 de enero de 2026 dio ~17,5 mm (IMERG 32,0, CMORPH 25,2, POWER 13,6).

## Entrada

El lote como lo recibe cualquier satélite: `lote["id"]`, `lote["lat"]`, `lote["lon"]` (centro del lote, EPSG:4326) y el período `desde`–`hasta` (máximo 366 días).

## Proceso

1. Validar el pedido (latitud, longitud, fechas, máximo 366 días). Un pedido inválido no baja nada.
2. Bajar el NetCDF anual de CPC de cada año que toca el período (~49 MB cada uno). Se guarda en la carpeta temporal y se reusa dentro del mismo día; CPC agrega los días nuevos al mismo archivo del año, así que se vuelve a bajar si el guardado es de un día anterior.
3. Leer el píxel de 0,5° que contiene el centro del lote con `rasterio` (driver NetCDF de GDAL, ya en `requirements.txt`; no se agrega ninguna dependencia nueva), y mapear el eje de tiempo a fechas.
4. Devolver **un valor por día pedido**, igual que IMERG y POWER. Un día que CPC todavía no publicó queda descartado; un píxel sin dato (mar o sin pluviómetro cercano) también.

Es un pedido propio: no importa ningún otro satélite (spec 009, satélites independientes).

## Salida (contrato común)

```json
{"lote_id": "lote-7", "fecha": "2026-01-13", "variable": "lluvia_mm", "valor": 12.4,
 "unidad": "mm/día", "fuente": "CPC", "resolucion_m": 55000, "calidad": "buena",
 "nota": "Respaldo de IMERG · NOAA CPC Global Unified (pluviómetros) · celda de 0,5°"}
```

- `variable` y `unidad` son **las mismas que IMERG** (`lluvia_mm`, `mm/día`), así la app recibe la misma serie venga de donde venga.
- `fuente: "CPC"` (sumada al contrato) y `resolucion_m: 55000` dicen que es un dato regional, no del lote.

## Reglas de calidad

1. **Nunca inventar.** Píxel sin dato, relleno del NetCDF (NaN o relleno gigante) o día que CPC todavía no publicó → `valor: null`, `calidad: "descartada"`, y la `nota` dice por qué.
2. Rango físico 0 a 500 mm/día (el mismo que IMERG y POWER). Fuera de rango → `calidad: "dudosa"`, sin corregir el valor.
3. Supuesto: la lluvia de CPC es el promedio interpolado de una celda de ~55 km a partir de pluviómetros, y los datos recientes son preliminares. En tormentas locales puede no ver un chaparrón puntual, y donde no hay estaciones cerca queda sin dato. La `nota` lo aclara con "celda de 0,5°" y "pluviómetros".

## Dónde entra

- **Registro (spec 009):** `SATELITES = [Satelite("IMERG:CPC", pedir, respaldo_de="IMERG", orden=2)]`, **segundo** respaldo de IMERG, detrás de POWER (`orden=1`, spec 013).
- **Consulta en el momento (spec 012) y actualización nocturna (spec 004):** si IMERG falla y POWER también, se pide el mismo período a este respaldo. Si IMERG o POWER andan, este respaldo **no se consulta**. Unido sin IMERG, queda en espera.
- **`combinar=true`:** para `lluvia_mm` gana IMERG donde tiene valor (`PREFERIDA` en `base.py`); CPC rellena solo donde IMERG falta. No hace falta tocar `base.py`: CPC no está en `PRIORIDAD`, así que toma la prioridad por defecto y nunca le gana a IMERG ni a POWER cuando los tres tienen valor para el mismo día.
- No trae endpoint de prueba propio: la app pide la lluvia a IMERG y el núcleo pasa a los respaldos solo.

### Decisión abierta para Hernán: ¿CPC por delante de POWER?

Hoy se suma como **orden 2** (detrás de POWER) para no cambiar la cadena IMERG → POWER que ya está viva. Pero CPC es de **pluviómetros** y POWER es un **modelo** que subestima la lluvia del lote, así que podría tener más sentido que CPC entre **primero** (CPC `orden=1`, POWER `orden=2`). Es un cambio de una línea en cada conector; queda a tu decisión, porque cambia qué fuente responde cuando IMERG falla.

## Prueba real

Workflow `Probar CPC (lluvia de respaldo)` (`.github/workflows/probar-cpc-lluvia.yml`, `probar_cpc_lluvia.py`). Por defecto: lote de prueba de San Luis (esquinas `-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300`, centro -33,7025; -65,2975), con un período automático que se cuenta desde el día en que corre. Corre en cada PR que toque estos archivos y a mano con un clic.

## Resultado de la prueba real

Workflow `Probar CPC (lluvia de respaldo)`, lote de prueba (centro -33,7025; -65,2975), 1 al 14 de enero de 2026, respuesta en 2,2 s (incluye la bajada del NetCDF anual):

| Fecha | 1/1 | 8/1 | 9/1 | 10/1 | 13/1 | 14/1 | Resto | Total |
|---|---|---|---|---|---|---|---|---|
| CPC (mm) | 0,20 | 0,39 | 6,15 | 3,46 | 0,00 | 7,35 | 0,00 | **17,5** |
| IMERG (mm, spec 006) | | | | | **22,5** | | | **32,0** |

Los 14 días vinieron `buena`, `lluvia_mm` en `mm/día`, fuente `CPC`, 55000 m.

**Comparación con IMERG:** CPC da **17,5 mm** en los 14 días contra **32,0 mm** de IMERG, más que POWER (13,6 mm, spec 013). Pero reparte la lluvia distinto: ve el episodio del 8-10/1 y marca 7,35 mm el 14/1, mientras que **el 13/1 (el día del chaparrón grande de IMERG, 22,5 mm) CPC da 0,0 mm**. Es lo esperable de un análisis de pluviómetros interpolado a una celda de ~55 km: capta cuánto llovió en la zona en el conjunto de días, no el día ni el punto exactos de una tormenta local. Sirve para no quedarse sin dato cuando IMERG y POWER fallan, y como segunda opinión terrestre; por eso entra como respaldo y `combinar=true` prefiere IMERG.

## Criterios de aceptación

- [x] El conector arma un valor por día pedido con la variable y la unidad de IMERG (`lluvia_mm`, `mm/día`), fuente `CPC`, 55000 m (tests `test_un_valor_por_dia_pedido_con_la_variable_de_imerg`, `test_valor_normal_es_buena_y_la_nota_dice_que_es_respaldo`).
- [x] Píxel sin dato, relleno y días que CPC todavía no publicó → `descartada` con `valor: null`; fuera de rango → `dudosa` sin corregir; el 0,0 es lluvia real, no faltante (tests `test_pixel_sin_dato_no_se_inventa`, `test_dia_que_cpc_todavia_no_publico_queda_descartado`, `test_fuera_de_rango_es_dudosa_sin_corregir`, `test_cero_es_un_dato_real_no_un_faltante`).
- [x] El eje de tiempo ("hours since 1900-01-01", como lo expone GDAL para CPC) se mapea bien a fechas, y un período que cruza el año baja los dos archivos (tests `test_fechas_del_tiempo_lee_horas_desde_1900`, `test_fechas_del_tiempo_tambien_lee_days_since`, `test_periodo_que_cruza_el_anio_baja_los_dos_archivos`).
- [x] Baja el archivo anual una vez por día y lo reusa; un pedido inválido no baja nada; CPC caído da error claro (tests `test_baja_el_archivo_anual_una_vez_por_dia`, `test_pedido_invalido_no_baja_nada`, `test_cpc_caido_o_ilegible_da_error_claro`).
- [x] Se anuncia como `IMERG:CPC`, respaldo de IMERG, orden 2, y no importa ningún otro satélite (`test_se_anuncia_como_segundo_respaldo_de_imerg` y `tests/test_nucleo.py`).
- [x] IMERG caído → entra este respaldo por el mismo período; IMERG OK → no se consulta; sin IMERG unido → queda en espera (tests `test_imerg_caido_entra_cpc_por_el_mismo_periodo`, `test_imerg_ok_no_consulta_el_respaldo`, `test_sin_imerg_unido_queda_en_espera`).
- [x] Tests sin internet verdes (66 pasan en local, incluidos los de CPC; se confirma en `Tests` del PR).
- [x] Prueba real con un clic y automática en cada PR que toque el conector (`Probar CPC (lluvia de respaldo)` en verde): CPC 17,5 mm del 1 al 14/1/2026 en el lote de prueba, 14 días `buena`, en 2,2 s, con la comparación con IMERG anotada arriba.

## Fuera de alcance

Corregir CPC o POWER con pluviómetros del productor o del INTA (eso llega por la gestión con CIRN-INTA, aparte). Un tercer respaldo de la lluvia. Reordenar POWER y CPC sin la decisión de Hernán (ver arriba).
