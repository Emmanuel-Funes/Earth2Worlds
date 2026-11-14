# Spec 011 · NDVI de respaldo con VIIRS (continuidad de MODIS)

**Estado:** aprobada por Hernán (opción "VIIRS y MODIS") y verificada con datos reales · **Etapa:** pipeline satélite → API → app · **Requiere:** cuenta NASA Earthdata · **Origen:** archivo "Info Satelital FODA"

## Objetivo

Que el lote siga teniendo NDVI de la NASA cuando HLS falla, después de que MODIS deje de recibir datos nuevos. Según el archivo FODA, Aqua termina hacia septiembre de 2026 y Terra está en retiro, y la NASA recomienda pasar a VIIRS de NOAA-20/21.

## Fuente

| Producto | Satélite | Grilla | Frecuencia | Capas a usar |
|---|---|---|---|---|
| `VJ113A1` | VIIRS en NOAA-20 | 500 m, sinusoidal (como MODIS) | compuesto de 16 días | NDVI, confiabilidad del píxel, día de adquisición |
| `VJ213A1` | VIIRS en NOAA-21 | igual | compuesto de 16 días | igual |

`VNP13A1` (Suomi NPP) **queda afuera**: deja de entregar datos el 1/11/2026.

**Verificado en la prueba real:**
- Los dos productos existen en CMR con esos nombres y tienen OPeNDAP: se lee solo la ventana del lote.
- Las capas están en `/HDFEOS/GRIDS/VIIRS_Grid_16Day_VI_500m/Data_Fields/` (`_500_m_16_days_NDVI`, `..._pixel_reliability`, `..._composite_day_of_the_year`).
- Cada satélite publica un compuesto nuevo cada 8 días (ventanas de 16 días que se superponen), así que NOAA-20 solo ya alcanza; NOAA-21 suma fechas.

**Falta verificar:** si traen la reflectancia SWIR. Si la traen, VIIRS también puede ser **respaldo del NDMI**, que hoy no tiene respaldo.

## Proceso

Igual que MODIS (spec 007), cambiando 250 m por 500 m:

1. Buscar en CMR los compuestos que tocan el lote en el período.
2. Leer solo la ventana de la grilla sinusoidal que cubre el lote.
3. Tomar los píxeles cuyo centro cae dentro del lote. Si ninguno cae adentro (lote de menos de 25 ha, un píxel), usar el que contiene el centro y aclararlo en la `nota`.
4. Píxel válido = confiabilidad buena o marginal.
5. Valor del lote = mediana del NDVI de los píxeles válidos.
6. Fecha = mediana del día de adquisición.

## Salida (contrato común)

```json
{"lote_id": "lote-7", "fecha": "2026-01-09", "variable": "ndvi", "valor": 0.60,
 "unidad": "índice (-1 a 1)", "fuente": "VIIRS", "resolucion_m": 500, "calidad": "buena",
 "nota": "Respaldo de HLS · VJ113A1 (NOAA-20) compuesto del 2026-01-01 · 2 píxeles de 500 m · válidos 100%"}
```

Calidad con los mismos umbrales que HLS y MODIS (60 % / 20 %). Nunca se inventa un valor.

## Dónde entra

Hernán eligió **VIIRS y MODIS**: si falla HLS entra VIIRS, y si VIIRS tampoco trae datos entra MODIS (HLS → VIIRS → MODIS). Para eso el núcleo acepta varios respaldos en orden (`orden=` en `Satelite`, rama `NUCLEO-varios_respaldos_en_orden`). El 4/10/2026 se sumó Sentinel-2 (ESA) como primer respaldo (spec 014), así que el orden quedó HLS → Sentinel-2 → VIIRS → MODIS: VIIRS se registra como `Satelite("HLS:VIIRS", ..., respaldo_de="HLS", orden=2)` y MODIS con `orden=3`.

Detalles del conector (`rotaterra/fuentes/viirs.py`):
- Los nombres exactos de las capas se leen de los metadatos del archivo (`.dmr`), buscando NDVI, *pixel reliability* y *day of the year* de 500 m, para no depender de cómo los escriba la NASA.
- Latitud y longitud de cada píxel se calculan con la fórmula de la grilla sinusoidal (no se piden al archivo).
- NDVI crudo válido entre -10000 y 10000 (escala 0,0001); afuera es relleno. **Supuesto:** confiabilidad 0 = buena y 1 = aceptable; se verifica en la prueba real.
- Si NOAA-20 y NOAA-21 caen el mismo día, queda el compuesto con más píxeles válidos. Si uno de los dos no está en CMR, se usa el otro.

- Es un satélite independiente (spec 009): rama `VIIRS-NDVI_respaldo`, sin unir a `main` hasta la orden de Hernán.
- Con la spec 010, el respaldo entra en la copia nocturna. Al consultar en el momento, `/ndvi` responde solo con HLS.

## Criterios de aceptación

- [x] Con el lote de prueba real (San Luis, enero de 2026) se obtiene NDVI de VIIRS por fecha, con su % de píxeles válidos, y se anotan los números. 1 al 31 de enero de 2026, en 12 segundos: 0,39 (3/1), 0,41 (4/1), 0,51 (14/1), 0,50 (16/1, NOAA-21), 0,54 (20/1) y 0,66 (30/1), todas con 100 % válido; el 17/1 (NOAA-21) quedó descartado por nubes. El lote de prueba (~25 ha) cae en 1 píxel de 500 m.
- [x] Los valores quedan cerca de los de HLS y MODIS para las mismas fechas (se anota la diferencia). Sigue la misma curva de crecimiento, pero **unos 0,07 a 0,14 más bajo**: 30/1 VIIRS 0,66 contra HLS 0,73 (-0,07); 3/1 VIIRS 0,39 contra MODIS 0,53 (-0,14); fin de enero VIIRS 0,66 contra MODIS 0,76 (28/1). Causa probable: el píxel de 500 m mezcla el lote con lo que lo rodea. Por eso VIIRS sirve para seguir la tendencia, no para comparar valores absolutos con HLS.
- [x] Si HLS falla, entra VIIRS para el mismo período (tests del núcleo con varios respaldos en orden, rama `NUCLEO-varios_respaldos_en_orden`).
- [x] VIIRS no importa código de ningún otro satélite (`tests/test_nucleo.py` en verde).
- [x] Tests sin internet (17 en `tests/test_viirs.py`); prueba real "Probar VIIRS (NDVI de respaldo)" verde, con un clic y en cada PR que toque el conector.

## Fuera de alcance

Incendios activos de VIIRS (375 m), luces nocturnas y productos de Suomi NPP.
