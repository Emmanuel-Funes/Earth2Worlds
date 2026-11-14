# Spec 014 · NDVI y NDMI de respaldo con Sentinel-2 L2A (ESA)

**Estado:** aprobada por Hernán ("Sumar lo necesario para cubrir lo que hace falta") y verificada con datos reales · **Etapa:** pipeline satélite → API → app · **Requiere:** nada (acceso público, sin cuenta) · **Rama:** `SENTINEL2-NDVI_NDMI_respaldo`

## Objetivo

Que el lote siga teniendo **NDVI y NDMI** cuando HLS falla. Hoy el NDMI no tiene ningún respaldo (VIIRS y MODIS solo dan NDVI). Sentinel-2 L2A de la ESA mide lo mismo que HLS (de hecho HLS usa Sentinel-2 como una de sus dos fuentes), con más detalle (10-20 m) y una pasada cada 2 a 5 días. Entra **primero** entre los respaldos: HLS → **Sentinel-2** → VIIRS → MODIS.

## Fuente

| | |
|---|---|
| Agencia | **ESA** (Agencia Espacial Europea, programa Copernicus), socia de la NASA |
| Producto | Sentinel-2 Nivel 2A (reflectancia de superficie, corregida por la atmósfera), satélites Sentinel-2B y 2C |
| Distribuidor | **AWS Open Data** ("Sentinel-2 Cloud-Optimized GeoTIFFs"), bucket público `sentinel-cogs`. Los datos son los de la ESA/Copernicus pasados a COG, sin cambiar los valores salvo el offset (ver abajo). Licencia: aviso legal de datos Sentinel (uso libre) |
| Catálogo | STAC público **Earth Search** de Element 84: `https://earth-search.aws.element84.com/v1`, colección `sentinel-2-l2a`. Si un día no devuelve nada, se prueba `sentinel-2-c1-l2a` (la "colección 1" que la reemplaza) |
| Credenciales | Ninguna |
| Bandas | B04 rojo (10 m), B08 infrarrojo cercano (10 m), B8A infrarrojo cercano angosto (20 m), B11 infrarrojo de onda corta (20 m), SCL clasificación de la escena (20 m) |

**Verificado** leyendo el bucket público desde esta máquina: el lote de prueba cae en el mosaico MGRS **20HKH**, con 14 escenas en enero de 2026 (Sentinel-2B y 2C, una cada 2-5 días), línea de base de procesamiento 05.11.

## Escala y offset de la reflectancia

Desde la línea de base 04.00 (enero de 2022) la ESA guarda la reflectancia con un **offset de −1000** (`BOA_ADD_OFFSET`): reflectancia = (DN − 1000) / 10000. Earth Search marca cada escena con `earthsearch:boa_offset_applied`:

- `true`: **Element 84 ya restó el offset en los píxeles**. Reflectancia = DN × 0,0001. Ojo: los metadatos `raster:bands` igual dicen `offset: -0.1`; **no hay que aplicarlo otra vez**. Verificado con datos reales (20HKH, 1/1/2026): el rojo de la vegetación del lote vale DN ≈ 270-300 (reflectancia 0,027-0,030, normal); si se restara 1000 daría negativa, imposible. Y el NDVI del 16/1 da 0,49 sin offset (HLS: 0,51 el 14/1) contra 0,99 si se resta dos veces.
- `false` o sin la marca: se usa el `offset` de `raster:bands` de la banda; si no está, −0,1 para línea de base ≥ 04.00 y 0 para las anteriores.

Verificado en la prueba real: las 13 escenas de enero de 2026 en `sentinel-2-l2a` traen `boa_offset_applied: true` (se usa escala 0,0001 y offset 0). En la colección de respaldo `sentinel-2-c1-l2a` las mismas escenas vienen **sin** la marca y con `offset: -0.1`, y sus píxeles valen exactamente 1000 más (rojo del lote el 28/1: mediana 1556 contra 556): con −0,1 las dos colecciones dan la misma reflectancia.

La `nota` no repite esto; el conector lo resuelve escena por escena.

## Entrada

Igual que HLS: `lote_id`, polígono GeoJSON (EPSG:4326), `desde`, `hasta` (máximo 366 días) y nubosidad máxima de la escena (70 % por defecto, como HLS).

## Proceso

1. Buscar en Earth Search las escenas de `sentinel-2-l2a` que tocan el rectángulo del lote en el período (reintenta 3 veces). Se dejan afuera las de más de 70 % de nubes en todo el mosaico.
2. De cada escena leer **solo la ventana del lote** de cada banda con rasterio (COG por HTTP, sin bajar el archivo).
3. **Máscara con SCL** (clasificación de la ESA). Píxel válido = **4 vegetación** o **5 suelo desnudo**. Se descartan 0 sin dato, 1 saturado o defectuoso, 2 zonas oscuras / sombra del relieve, 3 sombra de nube, 6 agua (igual que HLS, que también saca el agua), 7 sin clasificar, 8 y 9 nubes, 10 cirros, 11 nieve. También se descartan los píxeles con DN 0 (sin dato) en cualquier banda.
4. **NDVI = (B08 − B04) / (B08 + B04)** a **10 m**. La SCL de 20 m se lleva a 10 m por vecino más cercano (cada píxel de 20 m cubre 4 de 10 m).
5. **NDMI = (B8A − B11) / (B8A + B11)** a **20 m**. Se usa **B8A** en vez de B08 porque está a 20 m como B11 (no hay que remuestrear la banda de onda corta) y es el mismo par que usa HLS para Sentinel-2 (`HLSS30`: B8A y B11).
6. Valor del lote = **mediana** de los píxeles válidos dentro del polígono; la `nota` lleva media, p10, p90 y % válido.
7. Si dos escenas caen el mismo día (por ejemplo dos mosaicos vecinos u otra versión de procesamiento), queda **la más limpia** (más % de píxeles válidos), por variable.

## Salida (contrato común)

```json
{"lote_id": "lote-7", "fecha": "2026-01-16", "variable": "ndvi", "valor": 0.495,
 "unidad": "índice (-1 a 1)", "fuente": "SENTINEL2", "resolucion_m": 10, "calidad": "buena",
 "nota": "Respaldo de HLS · Sentinel-2 L2A (ESA) · S2C 20HKH · media 0.55 · p10 0.41 · p90 0.73 · válidos 100%"}
```

Una fecha tapada (dato real del 26/1/2026):

```json
{"lote_id": "lote-7", "fecha": "2026-01-26", "variable": "ndvi", "valor": null,
 "unidad": "índice (-1 a 1)", "fuente": "SENTINEL2", "resolucion_m": 10, "calidad": "descartada",
 "nota": "Respaldo de HLS · Sentinel-2 L2A (ESA) · S2C 20HKH · solo 0% de píxeles limpios · SCL: cirros 93%, sombra de nube 7%"}
```

- Variables y unidad iguales a HLS: `ndvi` y `ndmi`, `índice (-1 a 1)`. `resolucion_m`: 10 para NDVI, 20 para NDMI.
- Calidad con los mismos umbrales que HLS: ≥ 60 % de píxeles válidos = `buena`; 20-60 % = `dudosa` (y la nota dice "Lote parcialmente cubierto"); < 20 % = `descartada` con `valor: null` y la nota dice qué clases de la SCL taparon el lote (por ejemplo "nube densa 100%"). **Nunca se inventa un valor.**

## Dónde entra

- Satélite independiente (spec 009): `rotaterra/fuentes/sentinel2.py`, solo usa el núcleo. Se registra como `Satelite("HLS:SENTINEL2", ..., respaldo_de="HLS", orden=1)`: si HLS falla en la actualización nocturna, entra primero Sentinel-2; si también falla o no trae nada, VIIRS (orden 2) y después MODIS (orden 3). Depende del núcleo de la rama `NUCLEO-varios_respaldos_en_orden`.
- En `combinar=true`, `SENTINEL2` tiene prioridad 2 (respaldo), por debajo de HLS y por encima de VIIRS y MODIS (ya está en `base.PRIORIDAD`).
- Endpoint de prueba: `POST /ndvi/sentinel2` (mismo pedido que `/ndvi` de HLS). Responde 422 si el pedido es inválido y 502 si Earth Search o las escenas no responden.
- Prueba real con un clic: GitHub → Actions → **"Probar Sentinel-2 (NDVI y NDMI de respaldo)"** (`probar_sentinel2.py`), lote de ejemplo y enero de 2026. También corre en cada PR que toque el conector.

## Criterios de aceptación

- [x] Con el lote de prueba real (San Luis, enero de 2026) se obtiene NDVI y NDMI de Sentinel-2 por fecha, con su % de píxeles válidos, y se anotan los números. 1 al 31 de enero de 2026, en **13 segundos**, mosaico 20HKH: Earth Search dio 13 escenas; 4 quedaron afuera por más de 70 % de nubes en el mosaico (6, 8, 13 y 31/1) y quedaron **9 fechas, 7 con el lote despejado (100 % válido)**. NDVI: 0,24 (1/1), 0,30 (3/1), 0,37 (11/1), 0,49 (16/1), 0,57 (21/1), 0,59 (23/1), 0,70 (28/1). NDMI: −0,13 (1/1), −0,11 (3/1), −0,08 (11/1), 0,00 (16/1), 0,07 (21/1), 0,08 (23/1), 0,15 (28/1). Descartadas: 18/1 (SCL: nube densa 100 %) y 26/1 (SCL: cirros 93 %, sombra de nube 7 %).
- [x] Los valores quedan cerca de los de HLS para fechas parecidas y se anota la diferencia. Sigue la misma curva de crecimiento. NDVI: 16/1 Sentinel-2 0,49 contra HLS 0,51 el 14/1 (−0,02); 28/1 Sentinel-2 0,70 contra HLS 0,73 el 30/1 (−0,03); 1/1 Sentinel-2 0,24 contra HLS 0,32 (−0,08, la mayor diferencia). NDMI: Sentinel-2 de −0,13 a 0,15 contra HLS de −0,09 a 0,18 (unos 0,03-0,04 más bajo). Causa probable de la diferencia de principios de enero: el lote estaba muy desparejo (a 10 m, p10 0,20 y p90 0,73 el 1/1) y la mediana de píxeles de 10 m pesa más las manchas peladas que los de 30 m de HLS, que las mezclan; además HLS usa B8A para el NDVI y acá se usa B08. Para seguir la tendencia sirve igual; a fin de mes la diferencia es de 0,02-0,03.
- [x] La escala y el offset de la reflectancia se aplican bien según lo que entrega Earth Search (verificado con píxeles reales del 1/1, 16/1 y 28/1/2026 y en las dos colecciones, ver arriba).
- [x] Sin credenciales: la prueba real anda sin `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD` (el workflow no los pasa).
- [x] Sentinel-2 no importa código de ningún otro satélite (`tests/test_nucleo.py` en verde).
- [x] Tests sin internet (48 casos en `tests/test_sentinel2.py`, 92 en total en verde); prueba real "Probar Sentinel-2 (NDVI y NDMI de respaldo)" verde.

## Para tener en cuenta

- **Cirros:** la SCL de la ESA marcó el 26/1 todo el lote como "cirros" (nube fina), y se descartó como pide esta spec. El Fmask de HLS, en cambio, **no** descarta los cirros, así que en días así HLS puede tener dato y Sentinel-2 no. Es el lado conservador: no se guarda un valor que puede venir bajado por la nube fina.
- **Escenas muy nubladas en el mosaico:** se saltean (más de 70 % de nubes en los 110 × 110 km), igual que HLS, aunque el lote en sí pudiera estar despejado. Se puede subir `nubosidad_max` en el endpoint de prueba.
- **Earth Search** es un catálogo de Element 84 (empresa) sobre AWS Open Data; los datos son de la ESA sin cambios salvo el offset ya restado. Si `sentinel-2-l2a` deja de actualizarse, el conector pasa solo a `sentinel-2-c1-l2a`, que la prueba real mostró con las mismas 13 escenas.

## Fuera de alcance

Otros índices (NDRE, EVI), Sentinel-2 Nivel 1C, y usar Sentinel-2 como fuente principal. La consulta en el momento (`/ndvi`, spec 010) sigue respondiendo solo con HLS.
