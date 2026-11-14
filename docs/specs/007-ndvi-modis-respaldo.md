# Spec 007 · NDVI de respaldo con MODIS

**Estado:** aprobada por Hernán (tarjeta "Solo NASA") · **Etapa:** pipeline satélite → API → app (sin interfaz) · **Requiere:** cuenta NASA Earthdata

## Objetivo

Que el lote siga teniendo NDVI de la NASA cuando HLS falla. MODIS es más grueso que HLS (250 m contra 30 m), pero pasa todos los días y la NASA publica un compuesto limpio cada 16 días.

## Fuente

| Producto | Satélite | Grilla | Frecuencia | Capas usadas |
|---|---|---|---|---|
| `MOD13Q1` v061 | Terra | 250 m, sinusoidal | compuesto de 16 días | NDVI, confiabilidad del píxel, día de adquisición, latitud y longitud de cada píxel |

Se lee por **OPeNDAP de la NASA** solo la ventana de píxeles que cubre el lote. El gemelo de Aqua (`MYD13Q1`) daría un dato cada 8 días, pero la NASA no le ofrece OPeNDAP (verificado): queda afuera hasta que lo habilite.

## Entrada

`lote_id`, `poligono` (GeoJSON Polygon, EPSG:4326), `desde`, `hasta` (máximo 366 días), igual que HLS.

## Proceso

1. Buscar en CMR los compuestos de MOD13Q1 que tocan el lote en el período (incluido el que empezó hasta 15 días antes).
2. Pasar el polígono a la grilla sinusoidal de MODIS (mosaico `hXXvYY`, fila y columna) y leer la ventana que lo cubre.
3. Quedarse con los píxeles cuyo **centro cae dentro del lote** (la NASA da la latitud y longitud de cada píxel). Si ninguno cae adentro (lote menor a un píxel de 6 ha), se usa el píxel que contiene el centro del lote y se aclara en `nota`.
4. Píxel válido = confiabilidad 0 (buena) o 1 (marginal). Nubes, nieve o relleno no cuentan.
5. Valor del lote = **mediana** del NDVI de los píxeles válidos (escala 0,0001).
6. Fecha = mediana del **día de adquisición** de esos píxeles, no el inicio del compuesto.

## Salida (contrato común)

```json
{"lote_id": "lote-7", "fecha": "2026-01-09", "variable": "ndvi", "valor": 0.61,
 "unidad": "índice (-1 a 1)", "fuente": "MODIS", "resolucion_m": 250, "calidad": "buena",
 "nota": "Respaldo de HLS · MOD13Q1 compuesto del 2026-01-01 · 14 píxeles de 250 m · válidos 100%"}
```

## Reglas de calidad (las mismas umbrales que HLS)

| % de píxeles válidos | `calidad` |
|---|---|
| 60 % o más | `buena` |
| 20 % a 60 % | `dudosa` |
| menos de 20 % | `descartada`, `valor: null` |

Nunca se inventa un valor. NDVI fuera de -1 a 1 se descarta.

## Dónde entra

- **Respaldo (spec 005):** si HLS falla en la actualización nocturna, se pide el mismo período a MODIS (`HLS:MODIS` en `actualizaciones`).
- **Segundo respaldo:** el orden es HLS → Sentinel-2 → VIIRS → MODIS (`orden=3`; Sentinel-2 se sumó, spec 014). MODIS entra solo si Sentinel-2 y VIIRS tampoco traen datos, porque MODIS está en fin de misión. Si VIIRS no está unido a `main`, MODIS entra directo después de HLS.
- **`combinar=true`:** HLS gana sobre VIIRS y VIIRS sobre MODIS en la misma fecha; MODIS solo rellena.
- NDMI no tiene respaldo: MODIS 13Q1 no trae la banda SWIR necesaria a 250 m.

## Criterios de aceptación

- [x] Con el lote de prueba real se obtiene NDVI MODIS por fecha, con su % de píxeles válidos (1 al 31 de enero de 2026: 0,53 el 3/1, 0,55 el 7/1 y 0,76 el 28/1, 4 píxeles de 250 m, válidos 100 %, en 5 segundos).
- [x] Píxeles nublados o de relleno no cuentan; la calidad sigue la tabla.
- [x] HLS caído → entra MODIS para el mismo período.
- [x] Tests sin internet; prueba real con un clic y automática en cada PR que toque el conector.

## Fuera de alcance

NDMI de respaldo, NDVI diario de MODIS (MOD09GQ), estimación del cultivo por curva de NDVI (spec propia).
