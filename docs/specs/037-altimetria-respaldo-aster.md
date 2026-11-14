# Spec 037 · Altimetría de segundo respaldo con ASTER GDEM v3 (NASA/METI)

**Estado:** aprobada por Hernán y verificada con datos reales ("Listo, sigamos con los que dijiste") · **Etapa:** pipeline satélite → API → app · **Requiere:** credenciales de Earthdata (secrets `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD`) · **Respalda a:** NASADEM (spec 008), después de Copernicus DEM (spec 016)

## Objetivo

Que el lote tenga altura, pendiente y ambientes aunque **fallen a la vez** NASADEM y Copernicus DEM. Hoy el relieve tiene un solo respaldo (Copernicus DEM): si LP DAAC de la NASA y AWS Open Data de la ESA no responden al mismo tiempo, el lote se queda sin altimetría. ASTER GDEM es un **tercer modelo independiente**, de otra misión y otro sensor, así que es un respaldo real detrás de Copernicus DEM.

## Fuente

**ASTER Global Digital Elevation Model v3** (ASTGTM, colección v003): modelo de elevación global de 1 segundo de arco (~30 m), hecho por la **NASA y el METI de Japón** con el sensor **ASTER** del satélite Terra. Es un dato de la NASA (cumple la regla "de NASA o partner de NASA"), repartido por **LP DAAC** (el mismo distribuidor de NASADEM), y pide la cuenta de Earthdata.

Es un **compuesto** de todas las tomas de ASTER entre 2000 y 2013 (publicado en 2019), no una foto de un día: por eso es **estático** (se pide una sola vez por lote) y la fecha es fija.

**Cómo se accede:** por **CMR** (el buscador de Earthdata) se piden los mosaicos de 1° × 1° que tocan el lote; cada granule trae un GeoTIFF de altura (`..._dem.tif`) que se baja con el token de Earthdata y se lee con rasterio solo en la ventana del lote.

## Diferencias con NASADEM y Copernicus DEM (importante para leer los datos)

| | NASADEM (principal) | Copernicus DEM (resp. 1) | ASTER GDEM (resp. 2) |
|---|---|---|---|
| Agencia | NASA (SRTM) | ESA (TanDEM-X) | NASA + METI (ASTER/Terra) |
| Tipo | elevación de radar banda C | superficie (DSM) | **superficie (DSM)**: incluye árboles y construcciones |
| Fecha de la toma | febrero de 2000 | 2011-2015 | **compuesto 2000-2013** (fija) |
| Píxel | 1" (~30,9 m N-S; ~25,7 m E-O a -33,7°) | igual | igual |
| Valores | enteros (m) | decimales (m) | enteros (m), relleno -9999 |

Al ser un DSM compuesto por sensor óptico, ASTER tiene más ruido que los dos anteriores y, sobre nubes o sombras, puede tener artefactos: es un respaldo de último recurso, no un reemplazo de NASADEM.

## Entrada

`lote_id`, `poligono` (GeoJSON Polygon, EPSG:4326).

## Proceso

1. Autorizarse en Earthdata (token) y pedir a CMR los granules de `ASTGTM` que tocan la caja del lote.
2. Quedarse con las URLs de altura (`..._dem.tif`) y bajarlas con el token.
3. Unir los mosaicos que haga falta (lote que cruza 1°) en una sola grilla con rasterio, leyendo solo la ventana del lote más un píxel de margen para la pendiente.
4. Quedarse con los píxeles cuyo centro cae dentro del lote; descartar el relleno -9999 y alturas fuera de -500 a 9000 m.
5. Calcular **las mismas 7 variables, con las mismas reglas que NASADEM** (spec 008): altura media/mínima/máxima, pendiente media con el tamaño real del píxel a esa latitud, y ambientes (bajo / loma / media loma con el umbral de 1 m, superficie = proporción de píxeles × superficie del polígono).

El umbral de 1 m es el mismo **supuesto** de arranque que NASADEM y Copernicus DEM; tiene que calibrarse con asesores locales.

## Salida (contrato común)

Una observación por variable, con `fuente: "ASTER"`, `resolucion_m: 30` y `fecha: 2019-08-05` (publicación de ASTER GDEM v3; la `nota` aclara que el dato es un compuesto de tomas de 2000 a 2013).

| Variable | Unidad |
|---|---|
| `altura_media_m`, `altura_min_m`, `altura_max_m` | m |
| `pendiente_media_pct` | % |
| `superficie_bajo_ha`, `superficie_media_loma_ha`, `superficie_loma_ha` | ha |

`nota` aclara: que es ASTER GDEM v3 de la NASA y el METI, que es un modelo de **superficie** (incluye árboles y construcciones), el compuesto 2000-2013, los píxeles usados y, en los ambientes, el umbral de 1 m como supuesto.

## Reglas

1. Nunca inventar: píxeles sin dato no cuentan. Si el lote no tiene píxeles válidos, todas las variables quedan `null` + `descartada`.
2. Menos de 10 píxeles válidos (lote menor a ~1 ha) → `dudosa`.
3. Altura fuera de -500 a 9000 m o igual al relleno -9999 → el píxel se descarta.
4. Si CMR no devuelve mosaicos para el lugar (lote en el mar), el conector falla con un mensaje claro.
5. Si LP DAAC niega el acceso (401/403), el conector lo dice claro: hay que autorizar la aplicación LP DAAC en la cuenta de Earthdata.

## Dónde entra

- **Consulta en el momento (spec 012) y actualización nocturna (spec 004/005):** `Satelite("NASADEM:ASTER", …, respaldo_de="NASADEM", estatico=True, orden=2)`. Solo se pide cuando **NASADEM y Copernicus DEM** terminan en error, porque entra con `orden=2` (después de Copernicus DEM, `orden=1`).
- **`combinar=true`:** ASTER tiene prioridad de respaldo (2, igual que Copernicus DEM y MERRA-2), por debajo de NASADEM (1).
- Sin endpoint propio: el endpoint de la app es `POST /altimetria` de NASADEM, y el respaldo entra por el núcleo.
- No toca ningún archivo de otro satélite (spec 009). Edita del núcleo solo `"ASTER"` en el literal `Fuente` de `contrato.py` y `"ASTER": 2` en `PRIORIDAD` de `base.py`.

## Criterios de aceptación

- [x] Con el lote de prueba real (25,7 ha en -33,70; -65,30) se obtienen las 7 variables de ASTER GDEM, todas `buena`, en GitHub Actions (PR #53, 15/10/2026, workflow "Probar ASTER GDEM (altimetría de respaldo)" en verde): 324 de 324 píxeles de ~31 × 26 m con dato, altura media 487,7 m (de 479 a 493), pendiente media 6,94 %, fecha 2019-08-05.
- [x] Las superficies de los tres ambientes suman la superficie del lote: 7,78 + 7,38 + 10,56 = 25,72 ha (lote 25,7 ha).
- [x] Comparación con NASADEM (spec 008) en el mismo lote:

  | Variable | ASTER GDEM | NASADEM | Diferencia |
  |---|---|---|---|
  | Altura media | 487,7 m | 488,4 m | -0,7 m |
  | Altura mínima | 479 m | 485 m | -6 m |
  | Altura máxima | 493 m | 492 m | +1 m |
  | Pendiente media | 6,94 % | 2,76 % | +4,18 |
  | Bajo | 7,78 ha | 8,28 ha | -0,50 ha |
  | Media loma | 7,38 ha | 10,86 ha | -3,48 ha |
  | Loma | 10,56 ha | 6,58 ha | +3,98 ha |

  La altura coincide dentro de ~1 m con NASADEM en promedio (hasta 6 m en la mínima). La **pendiente sale bastante más alta** (6,94 % contra 2,76 %) y los ambientes se corren hacia "loma": es el ruido píxel a píxel propio de ASTER (sensor óptico, compuesto), que infla la pendiente. Por eso ASTER va **detrás** de Copernicus DEM (menos ruidoso) en la cadena de respaldo; como último recurso da una altura y una idea de relieve razonables, no una pendiente fina.
- [x] Tests sin internet con CMR + Earthdata simulados y mosaicos GeoTIFF sintéticos (23 tests en `tests/test_aster.py`, incluye lote que cruza dos mosaicos, píxeles inválidos, lote chico, acceso negado y sin credenciales); pasan junto con `tests/test_nucleo.py` (aislamiento de la spec 009).
- [x] El conector no importa a ningún otro satélite y el núcleo no lo nombra (lo verifica `tests/test_nucleo.py`).

## Riesgos conocidos

- **Superficie, no terreno:** árboles, galpones y silos suben la altura (igual que Copernicus DEM).
- **Más ruido que los otros dos:** ASTER es óptico y compuesto; sobre nubes/sombras puede tener artefactos. Por eso va **detrás** de Copernicus DEM, no delante.
- La precisión vertical en llanura es del orden del metro o más, parecida al umbral de 1 m: los ambientes son **orientativos** hasta calibrarlos.
- Depende de Earthdata/LP DAAC igual que NASADEM; si los dos caen a la vez, este respaldo cae con ellos (por eso Copernicus DEM, en otra infraestructura, va primero).

## Fuera de alcance

Las capas auxiliares de ASTER GDEM (número de escenas, máscara de agua), el modelo ASTER GWBD de cuerpos de agua, suavizado del relieve y un modelo de terreno (DTM) que quite la vegetación.
