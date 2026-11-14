# Spec 008 · Altimetría y ambientes del lote con NASADEM

**Estado:** implementada · **Origen:** la Guía técnica pone NASADEM en el MVP y Hernán pidió guiarse por ella · **Etapa:** pipeline satélite → API → app (sin interfaz) · **Requiere:** cuenta NASA Earthdata

## Objetivo

Saber el relieve de cada lote: altura, pendiente y qué parte es loma, media loma o bajo. Es el dato que separa ambientes y marca los bajos anegables, y lo usa después el balance de agua.

## Fuente

**NASADEM** (`NASADEM_HGT` v001, LP DAAC): modelo de elevación de la NASA a partir de la misión SRTM (febrero de 2000), reprocesado. Grilla de 1 segundo de arco (~30 m). Es **estático**: se baja una sola vez por lote.

## Entrada

`lote_id`, `poligono` (GeoJSON Polygon, EPSG:4326).

## Proceso

1. Buscar en CMR el mosaico de 1° × 1° que cubre el lote (por ejemplo `s34w066`). Si el lote cruza dos mosaicos, se leen los dos.
2. Bajar el ZIP del mosaico con el token de Earthdata (una sola vez por lote; si varios lotes comparten mosaico, se baja una vez por corrida).
3. Quedarse con los píxeles cuyo centro cae dentro del lote.
4. Calcular:
   - altura media, mínima y máxima (m);
   - pendiente media (%), con el tamaño real del píxel en metros a esa latitud;
   - ambientes por altura relativa a la media del lote: **bajo** si está más de 1 m por debajo, **loma** si está más de 1 m por encima, **media loma** el resto. Superficie de cada uno = proporción de píxeles × superficie del polígono, en hectáreas.

El umbral de 1 m es un **supuesto** de arranque para lotes de llanura; tiene que calibrarse con asesores locales.

## Salida (contrato común)

Una observación por variable, con `fecha: "2026-11-14"` (fecha de la misión SRTM), `fuente: "NASADEM"`, `resolucion_m: 30`.

| Variable | Unidad |
|---|---|
| `altura_media_m`, `altura_min_m`, `altura_max_m` | m |
| `pendiente_media_pct` | % |
| `superficie_bajo_ha`, `superficie_media_loma_ha`, `superficie_loma_ha` | ha |

`nota` aclara los píxeles usados y, en los ambientes, el umbral de 1 m como supuesto.

## Reglas

1. Nunca inventar: píxeles sin dato (relleno) no cuentan. Si el lote no tiene píxeles válidos, todas las variables quedan `null` + `descartada`.
2. Menos de 10 píxeles válidos (lote menor a ~1 ha) → `dudosa`.
3. Altura fuera de -500 a 9000 m → el píxel se descarta.

## API

`POST /altimetria` con `{"lote_id": …, "poligono": …}` → las 7 observaciones. `422` polígono inválido, `503` faltan credenciales, `502` la NASA no responde. La app lo llama y espera la respuesta (spec 010).

## Dónde entra

- **Actualización nocturna (spec 004):** `NASADEM` es una fuente más, pero como es estática, una vez guardada queda `al_dia` y no se vuelve a pedir.
- Sin respaldo: es un dato fijo de la NASA; si falla, se reintenta la noche siguiente.

## Criterios de aceptación

- [x] Con el lote de prueba real se obtienen las 7 variables (lote de 25,7 ha en -33,70; -65,30: altura media 488,4 m, de 485 a 492 m, pendiente media 2,76 %, 289 de 289 píxeles con dato, en 3 segundos).
- [x] Las superficies de los tres ambientes suman la superficie del lote (8,28 + 10,86 + 6,58 = 25,72 ha).
- [x] Una vez guardado, la actualización nocturna no lo vuelve a pedir.
- [x] Tests sin internet con un modelo de elevación sintético; prueba real con un clic y automática en cada PR que toque el conector.

## Riesgos conocidos

- La precisión vertical de NASADEM en llanura es de unos pocos metros, más que el umbral de 1 m. Por eso los ambientes son **orientativos** hasta calibrarlos con el productor, un mapa de rinde o un relevamiento RTK.
- El ruido de píxel a píxel infla la pendiente media. En el lote de prueba da 2,76 %, cuando el desnivel total (7 m en unos 600 m) sugiere alrededor de 1 %. Para comparar lotes entre sí sirve; como pendiente absoluta, no. Si hiciera falta, se puede suavizar el relieve antes de calcularla (cambio de spec).

## Fuera de alcance

Cartas de suelo INTA, napa, escurrimiento y zonas de anegamiento por modelado hidrológico.
