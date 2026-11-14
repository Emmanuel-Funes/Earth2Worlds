# Visión del proyecto — Earth2Worlds

## Objetivo

Desarrollar una aplicación web que combine información proporcionada por el usuario con datos satelitales para ayudar en el análisis y planificación de la rotación de cultivos de un terreno agrícola.

El proyecto se organiza mediante Spec-Driven Development (SDD), asegurando trazabilidad entre especificaciones, decisiones de arquitectura e implementación verificable.

## Principios rectores

- **Spec-Driven Development (SDD)**: Toda funcionalidad parte de una especificación explícita y criterios de aceptación medibles.
- **Desarrollo incremental**: Cada entrega mantiene el sistema en un estado funcional y verificable.
- **Simplicidad técnica**: Se evitan dependencias, capas de persistencia o servicios innecesarios para el alcance vigente.
- **Arquitectura modular**: Los proveedores de datos satelitales se mantienen desacoplados de la lógica principal mediante adaptadores y un contrato propio.
- **Infraestructura accesible**: Se priorizan servicios con capa gratuita y separación clara entre cliente web y API.

## Plataforma y requisitos de interfaz

- Aplicación web responsive para escritorio, tablets y teléfonos móviles.
- Separación estricta entre `frontend/` y `backend/`.
- Interfaz ligera, accesible y de bajo consumo de recursos.

## Alcance funcional implementado

1. **SPEC-001 — Mapa inicial**: Navegación cartográfica sobre OpenStreetMap con Leaflet y selección de un único terreno agrícola mediante polígono GeoJSON (WGS 84) con Leaflet-Geoman aislado en `frontend/src/map/`.
2. **SPEC-002 — Consulta de datos**: Catálogo funcional propio (`GET /api/v1/catalog`) y consulta síncrona de serie de observaciones NDVI (`POST /api/v1/queries`) a través del backend Fastify, manteniendo las credenciales externas exclusivamente en el servidor.
