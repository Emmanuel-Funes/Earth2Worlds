# SPEC-001 — Mapa inicial

## Objetivo

Mostrar un mapa interactivo sobre el cual el usuario pueda seleccionar un terreno agrícola mediante un polígono, sirviendo como base espacial para la consulta de información satelital.

## Alcance

- Mostrar un mapa navegable con teselas estándar de OpenStreetMap.
- Permitir desplazarse y acercar/alejar el mapa (controles `+/-`, rueda y gestos táctiles).
- Iniciar explícitamente el trazado mediante el botón «Dibujar terreno».
- Crear, cancelar y visualizar un único terreno seleccionado mediante un polígono.
- Obtener programáticamente sus coordenadas en formato GeoJSON / WGS 84 (`EPSG:4326`), sin mostrarlas en texto al usuario.
- Mantener visible la atribución del mapa base separada de los controles de negocio.
- Solicitar confirmación explícita antes de reemplazar un terreno existente mediante «Nuevo terreno».

## Flujo principal

1. El usuario abre la aplicación y visualiza el mapa centrado inicialmente en `-33.8, -66.1`, zoom `7`.
2. El usuario se desplaza hasta la zona de interés y pulsa «Dibujar terreno».
3. Marca los vértices del terreno sobre el mapa y cierra el polígono (o pulsa «Cancelar dibujo» para descartar el borrador).
4. Al cerrar el polígono, queda visible con borde y relleno verde translúcido, mostrándose el indicador «Terreno seleccionado».
5. La aplicación captura internamente su geometría GeoJSON `Polygon` en WGS 84.
6. Si el usuario pulsa «Nuevo terreno», se abre un diálogo modal de confirmación: al cancelar se conserva el terreno actual; al confirmar se elimina el terreno anterior y se inicia el nuevo dibujo.
