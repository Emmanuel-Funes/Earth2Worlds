# Spec 050 · NDVI diario de respaldo con Sentinel-3 (ESA)

**Estado:** aprobada por Hernán ("SI PORFAVOR, es increíble que no lo tengamos conectado siendo que pasa diariamente … Es urgente conectarlo") y verificada con datos reales · **Etapa:** pipeline satélite → API → app · **Requiere:** credenciales de Earthdata (`EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD`, ya cargadas) · **Rama:** `SENTINEL3-NDVI_respaldo` · **Depende de:** (`NUCLEO-varios_respaldos_en_orden`)

## Objetivo

Sumar a la cadena del NDVI un satélite que pasa **todos los días** por el lote con buen detalle. Hoy, cuando HLS y Sentinel-2 no tienen el lote despejado, el siguiente respaldo es VIIRS (500 m, compuestos de 16 días). Sentinel-3 da una imagen **por día** (Sentinel-3A y 3B juntos) a **300 m**, con reflectancia de superficie corregida por la atmósfera. Entra **entre Sentinel-2 y VIIRS**:

HLS → Sentinel-2 → **Sentinel-3** → VIIRS → MODIS

## Fuente

| | |
|---|---|
| Agencia | **ESA** (programa Copernicus), socia de la NASA |
| Producto | **SY_2_SYN** (Synergy Nivel 2: OLCI + SLSTR), reflectancia de superficie sobre tierra a 300 m, de Sentinel-3A y Sentinel-3B |
| Distribuidor | **NASA LAADS DAAC**, que redistribuye los datos de la ESA sin cambiarlos: colecciones de CMR `S3A_SY_2_SYN` (C1685833594-LAADS) y `S3B_SY_2_SYN` (C1685849802-LAADS) |
| Credenciales | Las mismas de Earthdata que ya usa la app. No hace falta cuenta de Copernicus |
| Bandas | `SDR_Oa08` (rojo, 665 nm) y `SDR_Oa17` (infrarrojo cercano, 865 nm); escala 0,0001, relleno −10000 |
| Banderas | `SYN_flags` (Synergy) y `CLOUD_flags` (nubes de OLCI) de `flags.nc` |
| Ubicación | `geolocation.nc` (lat/lon de cada píxel) y `tiepoints_olci.nc` (puntos de enlace, uno cada 64 columnas) |

**Verificado:** CMR devuelve para el lote de prueba entre 1 y 2 pasadas por día (3A ~13:30 UTC, 3B ~14:00 UTC); cada pasada es un `.zip` de 350 a 900 MB en `data.laadsdaac.earthdatacloud.nasa.gov`, con los NetCDF guardados **sin comprimir** adentro y lectura por rangos de bytes permitida (HTTP 206).

Por qué SYN y no OLCI solo: el nivel 2 terrestre de OLCI de la ESA (OL_2_LFR) no lo redistribuye la NASA y no trae NDVI sino OGVI; SYN sí trae la reflectancia de superficie de las bandas de OLCI, que es lo que hace falta para un NDVI comparable con HLS.

## Entrada

Igual que los otros respaldos del NDVI: `lote_id`, polígono GeoJSON (EPSG:4326), `desde`, `hasta` (máximo 366 días).

## Proceso

1. Validar el pedido. Un pedido inválido no llama a la NASA.
2. Pedir a CMR las pasadas de `S3A_SY_2_SYN` y `S3B_SY_2_SYN` que tocan el rectángulo del lote en el período.
3. De cada pasada, **sin bajar el .zip**: leer el índice del zip y, de cada NetCDF que hace falta, solo los pedazos que tocan al lote (pedidos HTTP de 512 KB con el token de Earthdata). Unos **5 MB por pasada**.
4. Ubicar el lote: el punto de enlace más cercano a su centro da la fila y la columna aproximadas (si está a más de 25 km, el lote queda **fuera de la franja** de esa pasada y se saltea). Después se leen las lat/lon de una ventana de ±48 píxeles y se toman los píxeles con el centro dentro del lote. Si no hay ninguno (lote más chico que un píxel de 9 ha), el píxel más cercano al centro, y la `nota` lo dice. Si ese píxel está a más de 300 m, el lote cae en el borde de la franja y la pasada se saltea.
5. **Píxel válido:** `SYN_land` prendido; sin `SYN_cloud`, `SYN_snow_risk`, `SYN_high_error`, `SYN_SDR_OOR` ni `SYN_partly_water`; `CLOUD_flags` = 0 (sin nube, nube dudosa, borde de nube ni nieve); las dos bandas con dato. Los nombres y bits de las banderas se leen del archivo. `SYN_partly_cloudy` **no** descarta: en la pasada despejada del 14/11/2026 viene prendida en todo el lote (se refiere a la vista de 1 km de SLSTR) y `CLOUD_flags` de OLCI, a 300 m, decide.
6. **NDVI = (Oa17 − Oa08) / (Oa17 + Oa08)** sobre reflectancia de superficie. Valor del lote = **mediana** de los píxeles válidos; la `nota` lleva media, p10, p90 y % válido.
7. Si dos pasadas caen el mismo día (3A y 3B, o dos tramos vecinos), queda **la más limpia**.

## Salida (contrato común)

```json
{"lote_id": "lote-7", "fecha": "2026-11-14", "variable": "ndvi", "valor": 0.31,
 "unidad": "índice (-1 a 1)", "fuente": "SENTINEL3", "resolucion_m": 300, "calidad": "buena",
 "nota": "Respaldo de HLS · Sentinel-3A SYN L2 (OLCI+SLSTR, ESA, vía NASA LAADS) · 3 píxeles de 300 m · media 0.28 · p10 0.23 · p90 0.33 · válidos 100%"}
```

La fecha es la del paso (hora UTC ~13:30-14:00, mañana en Argentina).

## Reglas de calidad

1. **Nunca inventar.** Con menos del 20 % de píxeles válidos el día queda `descartada` con `valor: null`.
2. Mismos umbrales que HLS, Sentinel-2, VIIRS y MODIS: válidos ≥ 60 % → `buena`, ≥ 20 % → `dudosa`.
3. Supuesto: a 300 m, un lote de 50 ha son 2 a 5 píxeles; el valor puede mezclar el borde con el lote vecino. Por eso va después de Sentinel-2 (10 m) en la cadena.

## Dónde entra

- **Registro (spec 009):** `SATELITES = [Satelite("HLS:SENTINEL3", pedir, respaldo_de="HLS", orden=2)]`. Comparte `orden=2` con VIIRS y entra antes porque el núcleo desempata por nombre (`HLS:SENTINEL3` < `HLS:VIIRS`); así no hay que cambiar las ramas de VIIRS ni de MODIS. Test `test_entra_entre_sentinel2_y_viirs`.
- **Núcleo:** `"SENTINEL3"` se suma a `Fuente` en `contrato.py` y a `PRIORIDAD` en `base.py` con 3 (como VIIRS: respaldo de detalle intermedio, después de Sentinel-2).
- **Dependencia nueva:** `h5py` (lee los NetCDF-4 de la ESA desde la memoria).
- Endpoint de prueba `POST /ndvi/sentinel3` (sin respaldos).

## Tiempo de respuesta

Cada pasada lleva ~10-15 s (muchos pedidos chicos a la nube de la NASA); se leen 12 a la vez. Medido desde la máquina de pruebas: 16 días en **176 s con 6 a la vez**, y **enero de 2026 completo (31 días) en 5 min 49 s con 12 a la vez**. Es más lento que VIIRS, pero solo corre cuando HLS y Sentinel-2 fallaron.

## Prueba real

Workflow `Probar Sentinel-3 (NDVI de respaldo)` (`.github/workflows/probar-sentinel3.yml`, `probar_sentinel3.py`). Por defecto: lote de prueba de San Luis, con un período automático que se cuenta desde el día en que corre. Como GitHub Actions no tiene minutos hasta, la prueba se corrió con el mismo script desde la máquina de trabajo (entorno con acceso a la NASA).

## Resultado de la prueba real

Lote de prueba (esquinas -33,700/-65,300 a -33,705/-65,295, ~25 ha), del 15 al 14/11/2026, 176 s:

- **16 de 16 días con pasada** (Sentinel-3A y 3B se alternan): **11 `buena`** y 5 `descartada` por nubes (18, 24, 28, 29 y 30/9). 2 a 5 píxeles de 300 m por día.
- NDVI de **0,21 a 0,31** (fin del invierno seco en San Luis).
- **Comparación con HLS** (misma consulta, mismos días): HLS tuvo 5 días con dato y Sentinel-3 11.

| Día | HLS (30 m) | Sentinel-3 (300 m) | Diferencia |
|---|---|---|---|
| 19/9 | 0,270 | 0,30 | +0,03 |
| 22/9 | 0,264 | 0,28 | +0,02 |
| 25/9 | 0,266 | 0,29 | +0,02 |
| 26/9 | 0,275 | 0,24 | −0,04 |
| 27/9 | 0,284 | 0,22 | −0,06 |

Diferencia media −0,01 (de −0,06 a +0,03): Sentinel-3 sigue a HLS sin sesgo marcado, con más ruido día a día por el píxel grueso. El 15/9 HLS estaba nublado y Sentinel-3 dio 0,31: es justo el hueco que viene a llenar.

**Segunda prueba, enero de 2026** (pleno verano), mismo lote, 5 min 49 s: **29 de 31 días con pasada**, **17 `buena`** y 12 `descartada` por nubes. NDVI de **0,40 a 0,73** (sube de 0,40 el 1/1 a 0,70-0,73 a fin de mes, el cultivo creciendo). El 1/1 HLS había dado 0,322 (spec 002, investigación 028): Sentinel-3 da 0,40, **+0,08**. En verano la diferencia con HLS es mayor que en septiembre; VIIRS, en cambio, da 0,07-0,14 *por debajo* de HLS (spec 011). Supuesto: el píxel de 300 m mezcla el lote con vecinos más verdes; se va a seguir mirando al comparar más fechas.

## Criterios de aceptación

- [x] Los puntos de enlace se ordenan por columna y ubican la fila/columna del lote; un lote fuera de la franja devuelve None (tests `test_puntos_de_enlace_se_ordenan_por_columna`, `test_ubicar_encuentra_la_columna_del_lote`, `test_ubicar_lote_fuera_de_la_franja`).
- [x] Las banderas salen de los atributos y descartan nubes de OLCI y de Synergy (tests `test_bits_salen_de_los_atributos`, `test_limpios_respeta_nubes_de_olci_y_de_synergy`).
- [x] El NDVI ignora el relleno; limpio = `buena`, parcial = `dudosa`, nublado = `descartada` sin valor (tests `test_ndvi_con_relleno_queda_vacio`, `test_resumen_*`).
- [x] De punta a punta con un .zip simulado, leído por pedazos con el token de Earthdata; mismo día gana la pasada más limpia; una pasada que no cubre el lote se saltea (tests `test_pasada_despejada_da_ndvi_del_lote`, `test_mismo_dia_gana_la_pasada_mas_limpia`, `test_pasada_que_no_cubre_el_lote_se_saltea`, `test_pasada_nublada_queda_descartada`).
- [x] Entra entre Sentinel-2 y VIIRS (test `test_entra_entre_sentinel2_y_viirs`).
- [x] No importa a ningún otro satélite y el núcleo no lo nombra (`tests/test_nucleo.py`).
- [x] Prueba real sobre el lote de San Luis: septiembre 16/16 días con pasada, 11 con dato, NDVI 0,21-0,31, sigue a HLS (diferencia media −0,01); enero 29/31 días con pasada, 17 con dato, NDVI 0,40-0,73 (+0,08 sobre HLS el 1/1).
