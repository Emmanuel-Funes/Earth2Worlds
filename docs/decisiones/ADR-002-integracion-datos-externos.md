# ADR-002 — Integración de datos satelitales mediante API propia

## Estado

Aprobada

## Contexto

Con la selección de terrenos completada en SPEC-001, SPEC-002 incorpora la consulta de observaciones de NDVI («Estado de vegetación») para un terreno y período determinados. Es necesario proteger las credenciales del proveedor satelital, desacoplar al cliente web de los detalles de sensores/satélites y mantener el sistema libre de persistencia innecesaria.

## Decisiones

1. **Separación de `frontend/` y `backend/`**: La API propia reside en `backend/` y se implementa con Node.js, TypeScript y Fastify.
2. **API intermediaria y catálogo funcional propio**:
   - `GET /api/v1/catalog`: publica conceptos funcionales para el usuario (`ndvi` — «Estado de vegetación»), ocultando nombres de satélites o sensores.
   - `POST /api/v1/queries`: recibe `itemId`, `geometry` (GeoJSON `Polygon`) y `period` (`from`, `to`).
3. **Resolución interna y adaptador satelital**:
   - El backend traduce `ndvi` a una consulta `HLS` hacia el endpoint externo `POST /consulta` autenticado con `X-API-Key`.
   - En cada petición genera un `lote_id` UUID v4 efímero mediante `node:crypto`.
4. **Consulta síncrona con timeout controlado**:
   - La solicitud se mantiene síncrona con un timeout máximo de 240 segundos (`AbortSignal.timeout(240_000)`), sin colas ni polling.
5. **Filtrado y normalización de observaciones**:
   - Aunque el proveedor devuelva múltiples variables (por ejemplo `ndvi` y `ndmi`), el adaptador filtra exclusivamente `variable === "ndvi"` y ordena las observaciones por fecha ascendente sin promediarlas.
   - Normaliza los estados de calidad (`buena`, `dudosa`, `descartada`), asegurando que las observaciones descartadas tengan `value: null` y se presenten como «Sin dato».
6. **Protección de secretos y errores seguros**:
   - `ROTATERRA_API_KEY` sólo existe en el entorno del servidor. Cualquier coincidencia accidental en textos del proveedor se redacta con `[redacted]`.
   - Los errores externos (`401`, `422`, `502`, `503` o timeouts) se traducen a errores propios (`502 PROVIDER_QUERY_FAILED` o `503 PROVIDER_UNAVAILABLE`).
7. **CORS con allowlist explícita**:
   - Configurado con `@fastify/cors` autorizando el origen de producción y, fuera de `NODE_ENV=production`, `http://localhost:5173`.
