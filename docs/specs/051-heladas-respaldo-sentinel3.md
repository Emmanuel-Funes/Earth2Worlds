# Spec 051 · Segundo respaldo de heladas con Sentinel-3 SLSTR LST nocturna (ESA)

**Estado:** aprobada por Hernán ("SI PORFAVOR … Es urgente conectarlo") · código y tests listos · **prueba real hecha** con la cuenta de Copernicus de Hernán (anda, ver abajo) · **Etapa:** pipeline satélite → API → app · **Requiere:** cuenta gratis de Copernicus Data Space (`COPERNICUS_USERNAME` / `COPERNICUS_PASSWORD`) · **Rama:** `SENTINEL3-heladas_respaldo` · **Depende de:** (`NUCLEO-varios_respaldos_en_orden`)

## Objetivo

Darle un **segundo respaldo** a la alerta de heladas (spec 030). Hoy la cadena es VIIRS LST (NOAA-20/21) → MODIS LST (Terra/Aqua, spec 035), y MODIS está en fin de misión. Sentinel-3A y 3B pasan **todas las noches** sobre San Luis con el radiómetro térmico SLSTR, y la ESA publica la temperatura de la superficie ya calculada (producto oficial SL_2_LST, 1 km). Queda:

VIIRS_LST → MODIS → **Sentinel-3**

## Fuente

| | |
|---|---|
| Agencia | **ESA** (programa Copernicus), socia de la NASA |
| Producto | **SL_2_LST** (SLSTR Nivel 2, temperatura de la superficie terrestre), grilla de 1 km de la vista nadir, Sentinel-3A y 3B |
| Distribuidor | **Copernicus Data Space Ecosystem** (portal oficial de la ESA). La NASA **no** redistribuye este producto: en CMR solo está el nivel 1 (`S3A_SL_1_RBT`, temperaturas de brillo), del que habría que calcular la LST con coeficientes propios. Se prefiere el producto oficial |
| Catálogo | OData público `https://catalogue.dataspace.copernicus.eu/odata/v1/Products` (sin token) |
| Descarga | `https://download.dataspace.copernicus.eu/odata/v1/Products({Id})/Nodes({Nombre})/Nodes({archivo})/$value` con token. Se bajan solo 3 archivos del producto, no el .zip entero |
| Token | `https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token` (`client_id=cdse-public`, usuario y clave); dura ~10 minutos y se renueva solo si vence |
| Credenciales | `COPERNICUS_USERNAME` / `COPERNICUS_PASSWORD`, solo como variables de entorno o secrets, nunca en el código ni en el chat |
| Dominios | `*.dataspace.copernicus.eu` (catálogo, identidad, descarga y su redireccionamiento) |

Archivos y variables que se leen:

| Archivo | Variable | Qué es |
|---|---|---|
| `LST_in.nc` | `LST` | temperatura de la superficie en kelvin (se aplican `_FillValue`, `scale_factor` y `add_offset` del archivo) |
| `geodetic_in.nc` | `latitude_in`, `longitude_in` | ubicación de cada píxel |
| `flags_in.nc` | `confidence_in` | banderas; los nombres y bits se leen de `flag_meanings` / `flag_masks` |

**Verificado con datos reales:** los 3 archivos y las variables existen con esos nombres en productos `..._NT_005.SEN3` reales. `confidence_in` trae `flag_meanings` = `coastline ocean tidal land inland_water unfilled spare spare cosmetic duplicate day twilight sun_glint snow summary_cloud summary_pointing` (land = 8, unfilled = 32, summary_cloud = 16384). No hizo falta cambiar el código.

## Entrada

`lote["id"]`, `lote["poligono"]` (GeoJSON, EPSG:4326), `desde`–`hasta` (máximo 366 días).

## Proceso

1. Validar el pedido. Un pedido inválido no llama a Copernicus.
2. Buscar en el catálogo los productos `SL_2_LST` que tocan el rectángulo del lote, desde el mediodía UTC del día anterior a `desde` hasta el mediodía UTC de `hasta`.
3. Quedarse con los **pasos de noche**: hora solar del lugar entre las 18 y las 6 (en San Luis, Sentinel-3 pasa ~22-23 h). Si un paso viene en versión rápida (`NR`) y definitiva (`NT`), gana la definitiva.
4. De cada paso bajar los 3 archivos, recortar los píxeles a ~3 km del lote y tomar los que tienen el centro dentro del lote (o el más cercano al centro si el lote es más chico que un píxel; si está a más de 1 km, el paso no cubre el lote y se saltea).
5. **Píxel válido:** bandera `land` prendida, `summary_cloud` y `unfilled` apagadas, LST entre 150 y 400 K.
6. Valor del lote = temperatura de superficie **mínima** de los píxeles válidos (el punto más frío, donde se forma la helada), en °C. Si 3A y 3B ven la misma noche, gana el paso con más píxeles despejados.
7. **Fecha:** la de la madrugada, igual que VIIRS y MODIS. Un paso a las 22 h del 21/9 es la "noche del 22/9".

## Salida (contrato común)

```json
{"lote_id": "lote-7", "fecha": "2026-09-22", "variable": "temp_sup_min_c", "valor": -3.0,
 "unidad": "°C", "fuente": "SENTINEL3", "resolucion_m": 1000, "calidad": "buena",
 "nota": "Respaldo · Sentinel-3 SLSTR LST nocturna (temperatura de superficie, no del aire) · SL_2_LST (Sentinel-3A, ESA Copernicus) · noche del 2026-09-22, paso de las 21:55 hora solar (temprano: la madrugada suele ser más fría) · 1 píxeles de 1 km · válidos 100% · riesgo de helada (≤ 0 °C de superficie)"}
```

## Reglas de calidad

1. **Nunca inventar.** Con menos del 20 % de píxeles válidos la noche queda `descartada` con `valor: null`.
2. Mismos umbrales que VIIRS y MODIS: válidos ≥ 60 % → `buena`, ≥ 20 % → `dudosa`.
3. A ≤ 0 °C de superficie, la `nota` agrega "riesgo de helada".
4. **Supuesto agronómico (clave):** es temperatura de la **superficie**, no del aire a 1,5 m, y el paso es temprano (~22-23 h): la madrugada suele ser más fría todavía. Sirve como alerta temprana y para ordenar las noches frías; el productor confirma la helada.

## Dónde entra

- **Registro (spec 009):** `SATELITES = [Satelite("VIIRS_LST:SENTINEL3", pedir, respaldo_de="VIIRS_LST", orden=2)]`: entra cuando VIIRS y MODIS (orden 1) no traen dato. Test `test_entra_despues_de_modis`.
- **Núcleo:** `"SENTINEL3"` en `Fuente` (`contrato.py`) y en `PRIORIDAD` con 3 (`base.py`, igual que en la rama del NDVI, spec 050). Para `temp_sup_min_c` se baja a 5 en `PRIORIDAD_POR_VARIABLE`, así queda detrás de MODIS (4) como en la cadena.
- **Dependencia nueva:** `h5py` (lee los NetCDF-4 de la ESA desde la memoria; la misma que la spec 050).
- Endpoint de prueba `POST /heladas/sentinel3` (sin respaldos).

## Lo que tiene que hacer Hernán (una vez)

1. Crear la cuenta gratis en https://dataspace.copernicus.eu (botón **Register**) y confirmarla desde el mail.
2. En el entorno de la nube **NASA** de Claude: sumar `*.dataspace.copernicus.eu` a **Allowed domains** y las variables `COPERNICUS_USERNAME` y `COPERNICUS_PASSWORD`.
3. Para Actions (cuando vuelvan los minutos, 1/11): GitHub → Settings → Secrets and variables → Actions → los mismos dos secrets.
4. Para Render, cuando se suba: las mismas dos variables de entorno en el servicio `rotaterra-api`.

## Prueba real

Workflow `Probar Sentinel-3 (heladas)` (`.github/workflows/probar-sentinel3-heladas.yml`, `probar_sentinel3_heladas.py`). Por defecto: lote de prueba de San Luis, con un período automático que se cuenta desde el día en que corre. Mientras Actions no tenga minutos, se corre el mismo script desde un hilo nuevo del entorno NASA con los pasos de arriba hechos.

## Resultado de la prueba real

Entorno NASA de Claude con `COPERNICUS_USERNAME` / `COPERNICUS_PASSWORD` de Hernán. Lote de prueba de San Luis (−33,700/−33,705, −65,300/−65,295), 15 al 30/9/2026. Comando: `python probar_sentinel3_heladas.py "-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300" 2026-09-15 2026-09-30`.

- **Anduvo al primer intento, en 31 s.** El catálogo devolvió 49 productos SL_2_LST, 21 de noche (S3A y S3B; 5 noches con dos pasos). Todos los pasos se leyeron con token y descarga por archivo.
- **16 noches: 5 `buena`, 11 `descartada`** por nube (bandera `summary_cloud` de la ESA). Ninguna `dudosa` (el lote es más chico que un píxel: o está despejado o no).
- **Noche más fría: 22/9 con 0,7 °C** de superficie (Sentinel-3A, paso de las 22:43 hora solar, despejado). No llega a 0 °C, así que no avisa riesgo de helada.

Comparación noche por noche con VIIRS (corrido el mismo día, misma quincena) y MODIS:

| Noche | Sentinel-3 (~22-23 h) | VIIRS (~1-3 h) | Diferencia S3 − VIIRS |
|---|---|---|---|
| 16/9 | 3,2 | 5,2 | −2,0 |
| 19/9 | 10,2 | 11,0 | −0,8 |
| **22/9** | **0,7** | **−3,0** (MODIS 0,1) | **+3,7** |
| 26/9 | 13,1 | 10,3 | +2,8 |
| 28/9 | 9,9 | nube | **S3 llena un hueco de VIIRS** |

**Lectura:**
1. **Sirve como respaldo:** cuando los dos ven el cielo limpio, Sentinel-3 cae a ±1-4 °C de VIIRS y ordena igual las noches frías (el 22/9 es la más fría en las dos). El 28/9 dio dato donde VIIRS tenía nube.
2. **Ve la noche más temprano.** Sentinel-3 pasa a las 22-23 h y VIIRS a la madrugada; en una noche despejada y en calma (helada por radiación, como la del 22/9) el suelo se sigue enfriando hasta el amanecer, por eso 0,7 °C contra −3,0 °C. Por eso la nota ahora dice "temprano: la madrugada suele ser más fría". **Riesgo:** como respaldo puede no avisar una helada leve que VIIRS sí vería; un valor de 0 a 3 °C a las 22 h en noche despejada merece atención.
3. **El filtro de nubes de la ESA se deja estricto.** Se miró el píxel del lote en los 21 pasos: los marcados como nube por el test básico (`cloud_in`) dan valores imposibles (−38,9, −22,6, −21,7 °C); los marcados solo por el test probabilístico (`bayes_in`) a veces coinciden con VIIRS (15/9: 3,6 contra 2,6; 27/9: 18,2 contra 17,0) pero otras veces no (21/9: −10,3 contra 7,9 de VIIRS). Aflojar el filtro daría falsas alarmas de helada, así que se descartan igual.

## Criterios de aceptación

- [x] Separa pasos de noche y de día por hora solar y fecha la madrugada; prefiere la versión NT a la NR (tests `test_noche_y_fecha_de_la_madrugada`, `test_elige_noches_y_prefiere_la_version_definitiva`).
- [x] Aplica relleno, escala y desplazamiento del archivo; banderas leídas del archivo (tests `test_escalar_aplica_relleno_escala_y_desplazamiento`, `test_limpios_pide_tierra_y_sin_nube`).
- [x] Noche fría da °C, `buena` y "riesgo de helada"; toma el píxel más frío; nubes descartan sin inventar; misma noche gana la más limpia; paso que no cubre el lote o de día se saltea (tests de punta a punta).
- [x] El token sigue a mano el redireccionamiento de la descarga, se renueva si vence, y faltan credenciales avisa (tests `test_noche_fria_da_celsius_y_riesgo_de_helada`, `test_token_vencido_se_renueva`, `test_sin_credenciales`).
- [x] Entra después de MODIS (test `test_entra_despues_de_modis`).
- [x] No importa a ningún otro satélite y el núcleo no lo nombra (`tests/test_nucleo.py`).
- [x] Prueba real sobre el lote de San Luis con la cuenta de Copernicus: 5 de 16 noches con dato, más fría 22/9 con 0,7 °C (VIIRS −3,0, MODIS 0,1), ver tabla.
