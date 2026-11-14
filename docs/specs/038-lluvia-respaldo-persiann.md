# Spec 038 · Tercer respaldo de la lluvia con NOAA PERSIANN-CDR (estimación por satélite)

**Estado:** aprobada por Hernán ("Listo, sigamos con los que dijiste") y verificada con datos reales · **Etapa:** pipeline satélite → API → app · **Requiere:** nada (archivos públicos de NOAA NCEI, sin cuenta) · **Rama:** `PERSIANN-lluvia_respaldo` · **Depende de:** (`NUCLEO-varios_respaldos_en_orden`)

## Objetivo

Que la lluvia del lote siga llegando cuando **GPM IMERG** (spec 006, principal de `lluvia_mm`) **y** sus dos primeros respaldos, **NASA POWER** (spec 013) y **NOAA CPC** (spec 029), fallan a la vez, quedan pendientes o no traen datos.

Los tres de más arriba tienen un punto flaco común: IMERG desde el 14/11/2026 es "Late" (sin corrección por pluviómetros); POWER es un modelo; y CPC, al ser pluviómetros interpolados, **se queda sin dato donde no hay estaciones cerca**. **PERSIANN-CDR** es una estimación **por satélite** (infrarrojo), calibrada con GPCP mensual: estima la lluvia incluso donde no hay estaciones, así que es una red de contención distinta de las tres anteriores. Es un *Climate Data Record* de NOAA, una de las agencias socias de la NASA permitidas (spec 008).

## Fuente

| Producto | Agencia | Qué da | Grilla | Demora | Acceso |
|---|---|---|---|---|---|
| PERSIANN-CDR (Precipitation Estimation from Remotely Sensed Information using Artificial Neural Networks — Climate Data Record) | NOAA (NCEI), con UC Irvine (CHRS) | Lluvia diaria estimada por satélite IR, calibrada con GPCP, en mm/día | 0,25° (~27 km), 60°S a 60°N | ~1 a 2 días la versión interina | un NetCDF por día en `https://www.ncei.noaa.gov/data/precipitation-persiann/access/{AÑO}/`, público, sin cuenta |

Cada día es un archivo `PERSIANN-CDR_v01r01_AAAAMMDD_cAAAAMMDD.nc` (la `c` es la fecha de creación, que varía), con la variable `precip` (mm/día), longitudes de 0 a 360. El conector arma el mapa de días leyendo el índice HTML del año, así no depende de adivinar la fecha de creación. Verificado en la investigación 028: en el lote de San Luis, del 1 al 14 de enero de 2026, PERSIANN-CDR dio ~25,3 mm (IMERG 32,0, CMORPH 25,2, CPC 17,5, POWER 13,6).

## Entrada

El lote como lo recibe cualquier satélite: `lote["id"]`, `lote["lat"]`, `lote["lon"]` (centro del lote, EPSG:4326) y el período `desde`–`hasta`.

## Proceso

1. Validar el pedido: latitud, longitud, **60°S a 60°N** (lo que cubre PERSIANN), fechas y **máximo 186 días**. Un pedido inválido no baja nada.
2. Para cada año del período, bajar el índice HTML de NCEI una sola vez y armar el mapa `{fecha: nombre de archivo}`.
3. Bajar el NetCDF de cada día pedido que exista en el índice (~1-2 MB por día) y leer con `rasterio` (driver NetCDF de GDAL, ya en `requirements.txt`; no se agrega ninguna dependencia nueva) el píxel de 0,25° que contiene el centro del lote. Cada archivo se guarda en la carpeta temporal y se reusa.
4. Devolver **un valor por día pedido**, igual que IMERG, POWER y CPC. Un día que PERSIANN todavía no publicó (no está en el índice) queda descartado; un píxel sin dato también.

Es un pedido propio: no importa ningún otro satélite (spec 009, satélites independientes).

### Por qué 186 días de tope

PERSIANN se baja **un archivo por día** (a diferencia de CPC, que es un NetCDF por año), así que un período largo son muchas descargas. Como es el respaldo de **último recurso** (entra solo si IMERG, POWER y CPC fallan), 186 días (media campaña) cubre de sobra los pedidos reales (una década, un mes, una campaña) sin dejar que un pedido enorme dispare cientos de bajadas.

## Salida (contrato común)

```json
{"lote_id": "lote-7", "fecha": "2026-11-14", "variable": "lluvia_mm", "valor": 15.8,
 "unidad": "mm/día", "fuente": "PERSIANN", "resolucion_m": 27000, "calidad": "buena",
 "nota": "Respaldo de IMERG · NOAA PERSIANN-CDR (estimación por satélite, calibrada con GPCP) · celda de 0,25°"}
```

- `variable` y `unidad` son **las mismas que IMERG** (`lluvia_mm`, `mm/día`), así la app recibe la misma serie venga de donde venga.
- `fuente: "PERSIANN"` (sumada al contrato) y `resolucion_m: 27000` dicen que es un dato regional, no del lote.

## Reglas de calidad

1. **Nunca inventar.** Píxel sin dato, relleno del NetCDF (NaN o relleno gigante) o día que PERSIANN todavía no publicó → `valor: null`, `calidad: "descartada"`, y la `nota` dice por qué.
2. Rango físico 0 a 500 mm/día (el mismo que IMERG, POWER y CPC). Fuera de rango → `calidad: "dudosa"`, sin corregir el valor.
3. Supuesto: PERSIANN estima la lluvia **desde el satélite** (nubes frías en infrarrojo), calibrada al mes con GPCP. Es buena para patrones y acumulados, pero un chaparrón puntual o una tormenta de base cálida los puede estimar de más o de menos. La `nota` lo aclara con "estimación por satélite" y "celda de 0,25°".

## Dónde entra

- **Registro (spec 009):** `SATELITES = [Satelite("IMERG:PERSIANN", pedir, respaldo_de="IMERG", orden=3)]`, **tercer** respaldo de IMERG, detrás de POWER (`orden=1`) y CPC (`orden=2`).
- **Consulta en el momento (spec 012) y actualización nocturna (spec 004):** se pide el mismo período solo si IMERG, POWER y CPC fallan. Si alguno de los tres anda, este respaldo **no se consulta**. Unido sin IMERG, queda en espera.
- **`combinar=true`:** para `lluvia_mm` gana IMERG donde tiene valor (`PREFERIDA` en `base.py`); PERSIANN rellena solo donde faltan IMERG y los respaldos anteriores. En `PRIORIDAD` de `base.py` entra como `"PERSIANN": 5` (estimación por satélite: la confianza más baja de las fuentes de lluvia), así que nunca le gana a IMERG, POWER ni CPC cuando varias tienen valor para el mismo día.
- No trae endpoint de prueba propio: la app pide la lluvia a IMERG y el núcleo pasa a los respaldos solo.
- Del núcleo se tocan solo dos líneas permitidas por la Guía (pt 9): `"PERSIANN"` en el literal `Fuente` de `contrato.py` y `"PERSIANN": 5` en `PRIORIDAD` de `base.py`.

## Prueba real

Workflow `Probar PERSIANN (lluvia de respaldo)` (`.github/workflows/probar-persiann.yml`, `probar_persiann.py`). Por defecto: lote de prueba de San Luis (esquinas `-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300`, centro -33,7025; -65,2975), con un período automático que se cuenta desde el día en que corre. Corre en cada PR que toque estos archivos y a mano con un clic.

## Resultado de la prueba real

Workflow `Probar PERSIANN (lluvia de respaldo)`, lote de prueba (centro -33,7025; -65,2975), del 1 al 14 de enero de 2026. 14 días, todos con dato `buena`, **total 25,3 mm** (justo lo que estimó la investigación 028). Días con lluvia: 6/1 2,15 · 7/1 0,46 · 8/1 11,54 · 9/1 2,48 · 13/1 5,09 mm; el resto 0,00.

Comparación en el mismo período:

| Fuente | Total 1-14 ene | 13/1 |
|---|---|---|
| IMERG (principal) | 32,0 mm | 22,5 mm |
| PERSIANN (este respaldo) | 25,3 mm | 5,1 mm |
| CPC (respaldo 2, pluviómetros) | 17,5 mm | — |
| POWER (respaldo 1, modelo) | 13,6 mm | — |

PERSIANN queda entre IMERG y CPC en el acumulado: ve bien el patrón de la quincena. En el día del chaparrón grande (13/1) estima bastante menos que IMERG (5,1 contra 22,5 mm), lo esperable de una estimación por satélite para un evento puntual: sirve como respaldo de acumulados y patrón, no para clavar un día de tormenta fuerte.

## Criterios de aceptación

- [x] Con el lote de prueba real (centro -33,7025; -65,2975), del 1 al 14 de enero de 2026, se obtiene un valor de PERSIANN por día, todos `buena`, con total **25,3 mm**, igual a lo estimado en la investigación 028.
- [x] La comparación con IMERG (32,0 mm), CPC (17,5 mm) y POWER (13,6 mm) en el mismo período queda anotada en "Resultado de la prueba real".
- [x] Un día sin publicar queda `descartada` ("todavía no tiene"), un píxel sin dato queda `descartada` ("sin dato"), el 0,0 es un dato real `buena`, y un valor fuera de 0-500 mm/día queda `dudosa` sin corregir (tests en `tests/test_persiann.py`).
- [x] Devuelve un valor por cada día pedido, con `variable: "lluvia_mm"`, `unidad: "mm/día"`, `fuente: "PERSIANN"`, `resolucion_m: 27000`.
- [x] Entra como tercer respaldo de IMERG (`orden=3`): si IMERG falla entra por el mismo período; si IMERG anda no se consulta (tests de integración con `actualizar_lote`).
- [x] 34 tests sin internet (índice y NetCDF simulados, más la detección de la variable de lluvia) pasan junto con `tests/test_nucleo.py` (aislamiento de la spec 009); el conector no importa a ningún otro satélite y el núcleo no lo nombra.

## Riesgos conocidos

- **Estimación por satélite, no medición:** PERSIANN puede errar chaparrones puntuales; es un respaldo de acumulados y patrones, el último de la cadena por algo.
- **Una descarga por día:** por eso el tope de 186 días; si en el futuro se necesita un período más largo, conviene un agregado anual (como CPC) en lugar de subir el tope.
- **Cobertura 60°S-60°N:** cubre toda la Argentina agrícola, pero un pedido fuera de esa banda se rechaza con mensaje claro.
- Depende del índice HTML de NCEI: si NCEI cambia la estructura del directorio, el conector falla con error claro y la prueba real lo detecta.

## Fuera de alcance

PERSIANN-CCS (0,04°, otra familia), la versión en tiempo casi real de CHRS (otro portal), y promover PERSIANN por delante de CPC o POWER (hoy es el último de la cadena; cambiar el orden es una línea y queda a decisión de Hernán).
