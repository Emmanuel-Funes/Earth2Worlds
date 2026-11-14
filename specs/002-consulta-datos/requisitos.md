# SPEC-002 — Consulta de datos satelitales

## Objetivo

Permitir que el usuario consulte observaciones de NDVI («Estado de vegetación») del terreno seleccionado para un período de fechas, a través del catálogo y la API propios de Earth2Worlds.

## Alcance

- Publicar el catálogo funcional en `GET /api/v1/catalog` con el elemento `ndvi` («NDVI — Estado de vegetación»).
- Requerir un terreno seleccionado en el mapa y un período válido (`desde` / `hasta`) para ejecutar la consulta.
- Enviar desde el frontend `itemId`, `geometry` (GeoJSON `Polygon` EPSG:4326) y `period` (`from`, `to`) a `POST /api/v1/queries`.
- Validar en el backend la geometría (anillo cerrado, coordenadas `[longitud, latitud]`), el identificador de catálogo y el orden cronológico del período.
- Generar en el backend un `lote_id` UUID v4 efímero por consulta y resolver `ndvi` mediante `satelite: "HLS"` hacia `POST /consulta` autenticado con header `X-API-Key`.
- Mantener la consulta síncrona con un timeout máximo de 240 segundos e informar en la interfaz mientras se procesa.
- Filtrar únicamente las observaciones cuya `variable` sea `"ndvi"`, ordenarlas cronológicamente sin calcular promedios temporales y normalizar su calidad:
  - `buena`: valor numérico y unidad.
  - `dudosa`: valor numérico, unidad y advertencia `Calidad dudosa`.
  - `descartada` o valor `null`: mostrar «Sin dato», nunca cero.
- Mantener `ROTATERRA_API_KEY` exclusivamente en el backend, redactar cualquier aparición accidental en textos del proveedor (`[redacted]`) y traducir los errores externos a códigos propios seguros (`404 ITEM_NOT_FOUND`, `422 INVALID_QUERY`, `502 PROVIDER_QUERY_FAILED`, `503 PROVIDER_UNAVAILABLE`).
