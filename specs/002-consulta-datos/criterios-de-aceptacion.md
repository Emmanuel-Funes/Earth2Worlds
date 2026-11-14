# Criterios de aceptación — SPEC-002

## CA-001 — Catálogo funcional propio
**Dado** que el backend de Earth2Worlds está disponible, **cuando** el frontend solicita `GET /api/v1/catalog`, **entonces** recibe el catálogo funcional propio donde `ndvi` figura como «Estado de vegetación», sin exponer nombres de satélites.

## CA-002 — Selección funcional y terreno requerido
**Dado** que el usuario desea consultar datos, **cuando** selecciona NDVI, **entonces** la interfaz exige un terreno seleccionado y un período desde/hasta antes de habilitar el envío.

## CA-003 — Contrato de petición propio
**Dado** que existe un terreno seleccionado y un período válido, **cuando** el usuario inicia la consulta, **entonces** el frontend envía `itemId`, `geometry` (GeoJSON `Polygon`) y `period` (`YYYY-MM-DD`) a `POST /api/v1/queries`, sin enviar satélite, `lote_id` ni `X-API-Key`.

## CA-004 — Validación y adaptación en el backend
**Dado** que la API propia recibe una consulta, **cuando** la valida y adapta, **entonces** exige un polígono GeoJSON EPSG:4326 con anillo cerrado y fechas válidas ordenadas, genera un UUID v4 efímero como `lote_id`, fija `satelite = "HLS"` y envía `POST /consulta` con `X-API-Key` únicamente desde el servidor.

## CA-005 — Consulta síncrona y timeout
**Dado** que el usuario inicia una consulta, **cuando** el backend aguarda respuesta del proveedor, **entonces** la solicitud permanece síncrona mostrando estado de carga, con un timeout máximo de 240 segundos traducido a `503 PROVIDER_UNAVAILABLE` sin reintentos automáticos.

## CA-006 — Serie de observaciones sin promedio temporal
**Dado** que el proveedor devuelve observaciones para el período, **cuando** el backend normaliza el resultado, **entonces** conserva únicamente las observaciones con `variable === "ndvi"` ordenadas cronológicamente, descartando otras variables como `ndmi` y sin promediar valores.

## CA-007 — Representación de calidad y ausencia de dato
**Dado** que una observación tiene calidad `buena`, `dudosa` o `descartada`, **cuando** se presenta en la interfaz, **entonces** `buena` se muestra normalmente, `dudosa` incluye la advertencia «Calidad dudosa», y `descartada` o valor `null` se muestra como «Sin dato» (nunca cero).

## CA-008 — Procedencia desacoplada de la vista general
**Dado** que el proveedor informa `fuente_usada`, `intentos` y `fuente` por observación, **cuando** el backend normaliza la respuesta, **entonces** conserva dichos metadatos sin exponerlos como controles ni detalles técnicos en la vista principal.

## CA-009 — Traducción segura de errores
**Dado** que la petición es inválida o el proveedor devuelve error (`401`, `422`, `502`, `503`), **cuando** la API propia responde, **entonces** entrega un código estable (`422 INVALID_QUERY`, `404 ITEM_NOT_FOUND`, `502 PROVIDER_QUERY_FAILED`, `503 PROVIDER_UNAVAILABLE`) sin filtrar detalles internos ni credenciales.

## CA-010 — Estado efímero en memoria
**Dado** que se completa una consulta, **entonces** no se persisten polígonos, UUIDs ni respuestas en base de datos o caché.

## CA-011 — Protección de credenciales
**Dado** que el backend se comunica con el proveedor externo, **entonces** `ROTATERRA_API_KEY` reside sólo en el entorno del servidor y cualquier aparición en textos o errores es redactada antes de responder o registrar logs.
