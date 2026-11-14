# Spec 002 · Conector HLS: NDVI y NDMI del lote

**Estado:** implementada y verificada (PR #3 y #5) · **Etapa:** pipeline satélite → API → app (sin interfaz) · **Requiere:** cuenta NASA Earthdata

## Objetivo

Que la app pueda pedir la serie de **NDVI** (vigor del cultivo) y **NDMI** (humedad de la vegetación) de un lote, a **30 m**, y recibirla en el contrato JSON común.

## Fuente

HLS v2.0 (Harmonized Landsat Sentinel-2), colecciones `HLSL30` (Landsat 8/9) y `HLSS30` (Sentinel-2), buscadas en el catálogo STAC de NASA (`https://cmr.earthdata.nasa.gov/stac/LPCLOUD`). Revisita combinada de 2 a 3 días.

| Índice | Fórmula | Bandas L30 | Bandas S30 |
|---|---|---|---|
| NDVI | (NIR − Rojo) / (NIR + Rojo) | B05, B04 | B8A, B04 |
| NDMI | (NIR − SWIR1) / (NIR + SWIR1) | B05, B06 | B8A, B11 |

Reflectancias con factor de escala 0,0001.

## Entrada

| Campo | Tipo | Ejemplo |
|---|---|---|
| `lote_id` | texto | `lote-7` |
| `poligono` | GeoJSON Polygon, EPSG:4326 | contorno del lote |
| `desde`, `hasta` | fecha `AAAA-MM-DD` | campaña |
| `nubosidad_max` | % de la escena, opcional (por defecto 70) | `70` |

## Proceso

1. Buscar escenas L30 y S30 que toquen el polígono en el período.
2. Leer solo la ventana del lote de cada banda (sin bajar la imagen entera).
3. Enmascarar con **Fmask**: nube, nube adyacente, sombra de nube, nieve/hielo y agua.
4. Calcular NDVI y NDMI por píxel válido dentro del polígono.
5. Resumir por fecha: **mediana** (valor), media, percentiles 10 y 90, % de píxeles válidos.
6. Si dos escenas caen el mismo día, quedarse con la de mayor % de píxeles válidos.

## Salida

Una observación por fecha e índice:

```json
{
  "lote_id": "lote-7", "fecha": "2026-01-15", "variable": "ndvi",
  "valor": 0.82, "unidad": "índice (-1 a 1)", "fuente": "HLS",
  "resolucion_m": 30, "calidad": "buena",
  "nota": "media 0.80 · p10 0.71 · p90 0.87 · válidos 96% · HLSS30"
}
```

## Reglas de calidad

| % píxeles válidos | Calidad | Valor |
|---|---|---|
| ≥ 60 % | `buena` | mediana |
| 20 a 60 % | `dudosa` | mediana, con motivo en `nota` |
| < 20 % | `descartada` | `null` |

Nunca se inventa un valor ni se interpola entre fechas en este conector.

## Credenciales

Usuario y contraseña de Earthdata se leen de las variables de entorno `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (en GitHub, como secretos). Nunca se escriben en el código ni en los logs. Con ellos se pide un token de Earthdata (`earthdata.cliente_autorizado`, el mismo del núcleo). Con ese token se pide cada archivo a LP DAAC, que responde con un enlace firmado de CloudFront; GDAL lee ese enlace directo, sin credenciales. Desde el 3 de octubre de 2026 GDAL no logra seguir esa redirección por su cuenta ("not recognized as being in a supported file format"), aunque la NASA entrega el GeoTIFF bien (verificado: HTTP 206, `image/tiff`).

## API

`POST /ndvi` con `{lote_id, poligono, desde, hasta}` → lista de observaciones. `422` si el polígono o las fechas son inválidos; `502` si NASA no responde; `503` si faltan credenciales.

## Criterios de aceptación

- [x] Con un lote real de prueba, se obtiene NDVI y NDMI por fecha con su % de píxeles válidos (lote de ~25 ha en -33,70; -65,30, enero de 2026: 14 fechas, 11 despejadas, NDVI de 0,32 a 0,73).
- [x] Fechas nubladas quedan `dudosa` o `descartada` según la tabla.
- [x] Los cálculos de índices y máscara tienen tests con datos sintéticos (sin internet).
- [x] Prueba real con un clic desde Actions, usando los secretos.

## Fuera de alcance

Estimación de cultivo por campaña a partir de la curva (spec propia), guardado en base de datos, mapas por píxel.
