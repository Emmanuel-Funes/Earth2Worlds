# Criterios de aceptación — SPEC-001

## CA-001 — Inicio de la aplicación
**Dado** que el usuario inicia la aplicación, **cuando** termina de cargar, **entonces** se muestra el mapa con la atribución de OpenStreetMap visible en una zona separada de los controles de la aplicación.

## CA-002 — Navegación del mapa
**Dado** que el mapa está visible, **cuando** el usuario arrastra el mapa, **entonces** el mapa se desplaza fluidamente.

## CA-003 — Zoom
**Dado** que el mapa está visible, **cuando** el usuario utiliza los controles de zoom, la rueda del ratón o gestos táctiles, **entonces** el nivel de zoom aumenta o disminuye.

## CA-004 — Creación de un polígono
**Dado** que el mapa está visible, **cuando** el usuario selecciona «Dibujar terreno» y marca varios vértices sobre el mapa, **entonces** puede cerrar un polígono viendo una representación provisional durante el trazado.

## CA-005 — Visualización del polígono
**Dado** que el usuario ha cerrado un polígono, **entonces** permanece visible como terreno seleccionado con estilo verde translúcido e indicación de estado «Terreno seleccionado».

## CA-006 — Coordenadas GeoJSON
**Dado** que existe un polígono seleccionado, **entonces** la aplicación obtiene programáticamente sus coordenadas en formato GeoJSON `Polygon` (WGS 84) sin exponerlas como texto en la interfaz.

## CA-007 — Cancelación de dibujo
**Dado** que el usuario está dibujando un polígono, **cuando** cancela la operación mediante «Cancelar dibujo», **entonces** se descarta el borrador sin crear ningún polígono.

## CA-008 — Confirmación para nuevo terreno
**Dado** que hay un terreno seleccionado, **cuando** el usuario selecciona «Nuevo terreno», **entonces** la aplicación pide confirmación modal antes de eliminarlo: si rechaza, conserva el terreno actual; si confirma, elimina el anterior e inicia el modo de dibujo nuevo.
