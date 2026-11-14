# Contexto técnico del proyecto — Earth2Worlds

## 1. Resumen arquitectónico

Earth2Worlds es una aplicación web para planificar terrenos agrícolas y consultar indicadores satelitales de vegetación desarrollada bajo Spec-Driven Development (SDD):

- **SPEC-001 — Mapa inicial**: implementada y verificada en `frontend/`.
- **SPEC-002 — Consulta de datos**: implementada y verificada en `backend/` y `frontend/`.

Flujo general de arquitectura:

```text
frontend → API propia (/api/v1/*) → catálogo propio → adaptador satelital → proveedor externo
```

- **Frontend**: React 19 + TypeScript + Vite, con Leaflet, Leaflet-Geoman y teselas estándar de OpenStreetMap aislados en `frontend/src/map/`.
- **Backend**: Node.js + TypeScript + Fastify bajo `backend/`, exponiendo `GET /api/v1/catalog` y `POST /api/v1/queries`.
- **Seguridad de credenciales**: `ROTATERRA_API_KEY` reside exclusivamente en el entorno privado del backend; nunca se expone al navegador ni en variables `VITE_*`.
- **Estado efímero**: El polígono seleccionado y las consultas viven únicamente en memoria durante la sesión activa de la página, sin base de datos ni caché.

## 2. Especificaciones vigentes

### SPEC-001 — Mapa inicial
- Muestra el mapa navegable centrado inicialmente en `-33.8, -66.1`, zoom `7` (referencia regional en San Luis, Argentina).
- Mantiene atribución de OpenStreetMap visible y separada de los controles de negocio.
- Activa el dibujo de polígono únicamente mediante la acción explícita «Dibujar terreno» (sin barra de herramientas permanente de Geoman).
- Captura internamente el GeoJSON `Polygon` en coordenadas WGS 84 (`EPSG:4326`).
- Con un terreno activo, «Nuevo terreno» solicita confirmación en un diálogo modal antes de descartar el polígono existente.

### SPEC-002 — Consulta de datos
- El frontend consulta `GET /api/v1/catalog` y presenta `ndvi` («Estado de vegetación»).
- Al enviar `POST /api/v1/queries`, el backend valida la geometría GeoJSON `Polygon` (anillo cerrado, coordenadas `[longitud, latitud]` válidas) y el período ISO `YYYY-MM-DD`.
- El backend genera un UUID v4 efímero como `lote_id`, resuelve `ndvi` hacia `satelite = "HLS"` y realiza la petición `POST` al proveedor con header `X-API-Key` y timeout máximo de 240 segundos.
- Filtra exclusivamente observaciones con `variable === "ndvi"`, las ordena cronológicamente sin promediarlas y normaliza la calidad:
  - `buena`: muestra valor y unidad.
  - `dudosa`: muestra valor, unidad y advertencia (`Calidad dudosa`).
  - `descartada` o valor `null`: muestra «Sin dato», nunca cero.
- Redacta cualquier aparición accidental de la clave privada en metadatos o notas (`[redacted]`) y traduce fallos externos a códigos propios seguros (`404 ITEM_NOT_FOUND`, `422 INVALID_QUERY`, `502 PROVIDER_QUERY_FAILED`, `503 PROVIDER_UNAVAILABLE`).

## 3. Fuera del alcance actual

- Persistencia de terrenos o consultas, base de datos, historial o caché.
- Colas, trabajos asíncronos (`202 Accepted`), polling o reintentos automáticos.
- Capas raster, mapas de calor u overlays espaciales sobre el mapa.
- Selección manual de satélite o sensor por parte del usuario.
- Autenticación de usuarios finales.
