# Spec 016 · Altimetría de respaldo con Copernicus DEM (ESA)

**Estado:** aprobada por Hernán el 4/10/2026 ("Sumar lo necesario para cubrir lo que hace falta") y verificada con datos reales · **Etapa:** pipeline satélite → API → app · **Requiere:** nada (acceso público, sin credenciales) · **Respalda a:** NASADEM (spec 008)

## Objetivo

Que el lote tenga altura, pendiente y ambientes aunque NASADEM falle. Hoy NASADEM no tiene respaldo: si LP DAAC de la NASA o Earthdata no responden, el lote se queda sin relieve. Un respaldo con SRTM no sirve, porque NASADEM y SRTM salen del mismo archivo de la NASA y fallan juntos. Copernicus DEM es de la **ESA** (agencia socia), está en otra infraestructura y no pide la cuenta de Earthdata, así que es un respaldo real.

## Fuente

**Copernicus DEM GLO-30** (programa Copernicus de la Unión Europea, ESA): modelo de elevación global de 1 segundo de arco (~30 m), hecho con la misión de radar **TanDEM-X** (DLR / Airbus). Es **estático**: se pide una sola vez por lote.

**Cómo se accede:** por el distribuidor público **AWS Open Data**, bucket `copernicus-dem-30m` (`https://copernicus-dem-30m.s3.amazonaws.com`), que publica los archivos originales de la ESA sin cambios y sin pedir usuario ni clave. AWS no es la fuente del dato: solo lo aloja (lo permite el brief de fuentes: "un distribuidor público de datos de una agencia se puede usar si se aclara").

**Verificado (4/10/2026) leyendo el bucket:**
- Un mosaico de 1° × 1° por carpeta. Para el lote de prueba: `Copernicus_DSM_COG_10_S34_00_W066_00_DEM/Copernicus_DSM_COG_10_S34_00_W066_00_DEM.tif`. El nombre lleva la esquina **suroeste**, igual que NASADEM (`s34w066`): el mosaico va de -34° a -33° de latitud y de -66° a -65° de longitud.
- El GeoTIFF es un COG (*Cloud Optimized GeoTIFF*): se lee **solo la ventana del lote** con rasterio, sin bajar el mosaico entero.
- Valores en `float32`, metros sobre el geoide EGM2008 (NASADEM usa EGM96; en la llanura la diferencia es de centímetros), sin valor de relleno declarado. Grilla de 3600 × 3600 con el centro de cada píxel en múltiplos exactos de 1" (la misma grilla que NASADEM). Por encima de 50° de latitud la grilla es más ancha en longitud (1,5" a 10"): el conector usa la resolución que trae cada mosaico.
- Cada carpeta trae un XML de metadatos (`Copernicus_DSM_10_S34_00_W066_00.xml`) con el período de toma del radar en ese mosaico (`tsxx_startTime` / `tsxx_stopTime`). Para el lote de prueba: del 17/01/2011 al 30/10/2013.
- Si un mosaico no existe (mar abierto), la carpeta no está y el XML da 404.

## Diferencias con NASADEM (importante para leer los datos)

| | NASADEM (principal) | Copernicus DEM (respaldo) |
|---|---|---|
| Agencia | NASA (SRTM) | ESA (TanDEM-X) |
| Tipo | elevación de radar banda C | **superficie (DSM)**: incluye árboles, montes y construcciones |
| Fecha de la toma | febrero de 2000 | **2011-2015**, según el mosaico (el lote de prueba: 2011-2013) |
| Píxel | 1" (~30,9 m norte-sur; ~25,7 m este-oeste a -33,7°) | igual |
| Valores | enteros (m) | decimales (m) |

Al ser DSM, en un lote con monte o cortinas forestales la altura sale más alta donde hay árboles y la pendiente se infla en sus bordes. En lotes agrícolas sin árboles las dos fuentes deberían coincidir dentro de 1 a 2 m.

## Entrada

`lote_id`, `poligono` (GeoJSON Polygon, EPSG:4326).

## Proceso

1. Calcular qué mosaicos de 1° × 1° tocan la caja del lote (con un píxel de margen). Si el lote cruza mosaicos, se leen todos y se **unen** en una sola grilla.
2. Leer el XML de cada mosaico con httpx: si da 404 el mosaico no existe (mar) y se saltea; de ahí sale la fecha de la toma.
3. Leer con rasterio solo la ventana del lote (más un píxel de margen para la pendiente), alineada a la grilla del producto.
4. Quedarse con los píxeles cuyo centro cae dentro del lote.
5. Calcular **las mismas 7 variables, con las mismas reglas que NASADEM** (spec 008):
   - altura media, mínima y máxima (m);
   - pendiente media (%), con el tamaño real del píxel en metros a esa latitud (norte-sur y este-oeste por separado);
   - ambientes por altura relativa a la media del lote: **bajo** si está más de 1 m por debajo, **loma** si está más de 1 m por encima, **media loma** el resto. Superficie de cada uno = proporción de píxeles × superficie del polígono, en hectáreas.

El umbral de 1 m es el mismo **supuesto** de arranque que NASADEM; tiene que calibrarse con asesores locales.

## Salida (contrato común)

Una observación por variable, con:
- `fuente: "COPDEM"`, `resolucion_m: 30`;
- `fecha`: el **último día de toma del radar** en el mosaico (`tsxx_stopTime` del XML; si el lote cruza mosaicos, el más reciente). Es la fecha real más cercana a "cuándo se midió" el relieve. Para el lote de prueba: `2013-10-30`.

| Variable | Unidad |
|---|---|
| `altura_media_m`, `altura_min_m`, `altura_max_m` | m |
| `pendiente_media_pct` | % |
| `superficie_bajo_ha`, `superficie_media_loma_ha`, `superficie_loma_ha` | ha |

`nota` aclara: que es Copernicus DEM de la ESA vía AWS Open Data, que es un modelo de **superficie** (incluye árboles y construcciones), el período de toma, los píxeles usados y, en los ambientes, el umbral de 1 m como supuesto.

## Reglas

1. Nunca inventar: píxeles sin dato no cuentan. Si el lote no tiene píxeles válidos, todas las variables quedan `null` + `descartada`.
2. Menos de 10 píxeles válidos (lote menor a ~1 ha) → `dudosa`.
3. Altura fuera de -500 a 9000 m → el píxel se descarta (también el valor -32767 que la ESA usa como inválido).
4. Si el XML de un mosaico existe pero no trae la fecha de toma, el conector falla (no inventa una fecha) y queda como error del respaldo.
5. Si ningún mosaico existe (lote en el mar), el conector falla con un mensaje claro.

## Dónde entra

- **Actualización nocturna (spec 004 y 005):** `Satelite("NASADEM:COPDEM", …, respaldo_de="NASADEM", estatico=True)`. Solo se pide cuando NASADEM termina en error. Como NASADEM es estático, mientras NASADEM no haya guardado nunca un dato, cada noche se vuelve a intentar NASADEM primero; si vuelve a fallar, Copernicus DEM se pide de nuevo (es liviano: unos pocos kB por lote).
- **Consulta en el momento (spec 012):** entra igual, como respaldo de NASADEM.
- **`combinar=true`:** COPDEM tiene prioridad de respaldo (2), por debajo de NASADEM (1). Como las fechas son distintas (2000-02-11 contra la de la toma de TanDEM-X), en la serie combinada pueden aparecer las dos: cada una con su fecha y su fuente.
- Sin endpoint propio: el endpoint de la app es `POST /altimetria` de NASADEM, y el respaldo entra por el núcleo.

## Criterios de aceptación

- [x] Con el lote de prueba real (25,7 ha en -33,70; -65,30) se obtienen las 7 variables de Copernicus DEM, sin credenciales (GitHub Actions, 4/10/2026, mosaico `S34_00_W066_00`, en 3 segundos: altura media 489,4 m, de 487,1 a 493,4 m, pendiente media 2,09 %, 289 de 289 píxeles con dato, todas `buena`).
- [x] Las superficies de los tres ambientes suman la superficie del lote (8,36 + 10,60 + 6,76 = 25,72 ha).
- [x] La fecha de la observación sale del XML del mosaico, no se inventa: `2013-10-30` (toma de TanDEM-X del 17/01/2011 al 30/10/2013). Un XML sin fecha hace fallar al conector (test `test_sin_fecha_en_el_xml_no_se_inventa`).
- [x] Comparación con NASADEM en el mismo lote:

  | Variable | Copernicus DEM | NASADEM | Diferencia |
  |---|---|---|---|
  | Altura media | 489,4 m | 488,4 m | +1,0 m |
  | Altura mínima | 487,1 m | 485 m | +2,1 m |
  | Altura máxima | 493,4 m | 492 m | +1,4 m |
  | Pendiente media | 2,09 % | 2,76 % | -0,67 |
  | Bajo | 8,36 ha | 8,28 ha | +0,08 ha |
  | Media loma | 10,60 ha | 10,86 ha | -0,26 ha |
  | Loma | 6,76 ha | 6,58 ha | +0,18 ha |
  | Píxeles | 289 de 289 | 289 de 289 | la misma grilla |

  La altura sale alrededor de 1 m más alta (geoide distinto, superficie con vegetación y 11-13 años de diferencia) y los ambientes casi coinciden (menos de 0,3 ha de diferencia en cada uno). La pendiente es menor porque Copernicus tiene menos ruido de píxel a píxel (valores con decimales, no enteros como NASADEM).
- [x] Un lote que cruza dos mosaicos se une en una sola grilla (test `test_lote_que_cruza_mosaicos_se_une_en_una_grilla`). Verificado también con datos reales en un lote de 12,3 ha en la esquina -34; -65, que toca 4 mosaicos: 165 de 165 píxeles con dato y fecha `2014-02-17`, la toma más reciente de los cuatro.
- [x] Tests sin internet con mosaicos sintéticos (15 tests en `tests/test_copdem.py`); prueba real con un clic y automática en cada PR que toque el conector (workflow "Probar Copernicus DEM (altimetría de respaldo)", en verde).

## Riesgos conocidos

- **Superficie, no terreno:** árboles, galpones y silos suben la altura. En lotes con monte, el respaldo puede marcar "lomas" que son árboles.
- **Fechas distintas:** NASADEM es de 2000 y Copernicus de 2011-2015. Para relieve de llanura la diferencia en 11-15 años es mínima, salvo movimientos de suelo (terrazas, canales, represas).
- La precisión vertical de ambos modelos en llanura es del orden del metro o más, parecida al umbral de 1 m: los ambientes son **orientativos** hasta calibrarlos.
- Dependencia del distribuidor AWS Open Data: si el bucket cambia de nombre o de formato, el conector falla con error claro y la prueba real lo detecta.

## Fuera de alcance

Copernicus DEM GLO-90, las máscaras auxiliares de la ESA (agua, relleno, error de altura), suavizado del relieve y un modelo de terreno (DTM) que quite la vegetación.
