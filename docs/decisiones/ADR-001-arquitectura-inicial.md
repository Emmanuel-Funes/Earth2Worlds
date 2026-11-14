# ADR-001 — Arquitectura inicial del frontend

## Estado

Aprobada

## Contexto

SPEC-001 establece el primer alcance funcional de Earth2Worlds: mostrar un mapa interactivo, permitir su navegación y zoom, dibujar un polígono para delimitar un terreno agrícola y obtener sus coordenadas geográficas internamente. La integración cartográfica debe mantenerse aislada del resto de la interfaz para facilitar su mantenimiento y permitir sustituir el proveedor de teselas en el futuro.

## Decisiones

1. **Frontend con React + TypeScript + Vite**: Estructura modular y tipada con empaquetado rápido.
2. **Biblioteca cartográfica Leaflet**: Provee la navegación del mapa, atribución y controles de zoom.
3. **Dibujo de polígonos con Leaflet-Geoman**: Permite trazar el polígono del terreno de forma programática sin exponer barras de herramientas permanentes.
4. **Geometría en GeoJSON / WGS 84 (`EPSG:4326`)**: Formato estándar e interoperable para comunicar el polígono seleccionado.
5. **Mapa base OpenStreetMap**: Uso de teselas estándar respetando la visibilidad de su atribución en una zona separada de los controles de negocio.
6. **Aislamiento en `frontend/src/map/`**: Ningún componente fuera de `frontend/src/map/` importa directamente Leaflet ni Leaflet-Geoman.

## Consecuencias

- El módulo cartográfico queda encapsulado tras una interfaz imperativa mínima (`startDrawing`, `startNewTerrain`, `cancelDrawing`, `destroy`) y callbacks de estado.
- Las coordenadas GeoJSON generadas por el mapa pueden consumirse directamente por las funcionalidades de consulta de SPEC-002.
