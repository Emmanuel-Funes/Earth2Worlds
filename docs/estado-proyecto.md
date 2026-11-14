# Estado del proyecto — Earth2Worlds

## Estado general

- **SPEC-001 — Mapa inicial**: Completada y verificada (`CA-001` a `CA-008`).
- **SPEC-002 — Consulta de datos**: Completada y verificada (`CA-001` a `CA-011`).

## Componentes verificados

### Frontend (`frontend/`)
- Integración cartográfica encapsulada en `frontend/src/map/createBaseMap.ts` y `frontend/src/map/MapView.tsx`.
- Teselas estándar de OpenStreetMap con atribución visible y controles de zoom.
- Dibujo, cancelación y reemplazo confirmado de polígono único con extracción automática de GeoJSON `Polygon` (WGS 84).
- Panel de consulta sincronizado con el catálogo propio (`GET /api/v1/catalog`) y envío de consultas (`POST /api/v1/queries`).
- Visualización cronológica de observaciones NDVI con soporte para estados `buena`, `dudosa` y `descartada` («Sin dato»).

### Backend (`backend/`)
- Servidor Fastify (`backend/src/app.ts`, `backend/src/server.ts`) con política CORS de lista blanca estricta.
- Validación rigurosa de entrada (cuerpo JSON, identificador de catálogo, anillo cerrado GeoJSON y rango de fechas).
- Adaptador satelital (`backend/src/rotaterra.ts`) con generación de UUID efímero, timeout de 240 segundos, filtrado por variable `ndvi`, sanitización de secretos y traducción segura de errores.
- Suite de pruebas de integración automatizadas (`backend/test/integration.test.ts`) con cobertura de todos los casos de éxito, filtrado, ordenamiento, CORS y manejo de errores.
