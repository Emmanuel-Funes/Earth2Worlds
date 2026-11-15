# Spec 062 · Selector de Usuarios (Básico vs. Avanzado), Sesiones Efímeras y Flujo de Recomendación

# Spec 062 · Selector de Usuarios (Agricultor vs. Técnico Agropecuario), Sesiones Efímeras y Flujo de Recomendación

**Estado:** Borrador para revisión y aprobación · **Etapa:** UI / Sesiones / Pipeline interactivo · **Aplica a:** `app/`, `static/`, `rotaterra/`
**Estado:** Aprobado e Implementado · **Etapa:** UI / Sesiones / Pipeline interactivo · **Aplica a:** `app/`, `static/`, `rotaterra/`

## Objetivo

Simplificar el acceso a la plataforma Earth2Worlds eliminando el muro de registro/login obligatorio tradicional para pruebas, proveyendo al iniciar un **Selector de Experiencia de Usuario**:

1. **Modo Básico**: Flujo guiado tipo asistente en 3 pasos (1: dibujar un único lote en cualquier parte del mundo sin catastro; 2: declarar la última plantación; 3: visualizar el lote, telemetría histórica satelital NASA de 5 años y slot para el nuevo motor de recomendación de rotación de cultivos).
2. **Modo Avanzado**: Acceso total a todas las herramientas preexistentes de Earth2Worlds (visor GIS, panel de capas, dock satelital, 6 tarjetas de telemetría y gráficos históricos interactivos Chart.js).
3. **Agricultor** (antes Básico): Flujo guiado tipo asistente en 3 pasos (1: delimitar un único lote en el territorio argentino con alerta en vivo de frontera nacional; 2: declarar el cultivo previo entre 5 opciones clave: Maíz, Soja, Girasol, Sorgo, Maní; 3: visualizar el lote, telemetría histórica satelital NASA de 5 años con carga progresiva inmediata y slot para el nuevo motor de recomendación de rotación de cultivos).
4. **Técnico Agropecuario** (antes Avanzado): Acceso total a todas las herramientas territoriales de Earth2Worlds (visor GIS, panel de capas, dock satelital, 6 tarjetas de telemetría y gráficos históricos interactivos Chart.js).
5. **Acceso Administrador**: Botón independiente con autenticación para el usuario permanente del sistema.
6. **Persistencia limpia y efímera**: Limpiar la base de datos de usuarios de prueba, conservando exclusivamente al `Admin`. Los usuarios Básico y Avanzado operan con credenciales/sesiones efímeras (en memoria/cliente) sin ensuciar la base de datos `earth2worlds.db`.
7. **Persistencia limpia y efímera**: Limpiar la base de datos de usuarios de prueba, conservando exclusivamente al `Admin`. Los perfiles de Agricultor y Técnico Agropecuario operan con credenciales/sesiones efímeras (en memoria/cliente) sin ensuciar la base de datos `earth2worlds.db`.

---

## Comparativa: Antes vs. Después

| Aspecto | Antes (Specs 004, 022) | Después (Spec 062) |
| --- | --- | --- |
| **Acceso inicial** | Redirección obligatoria a `/login` o `/registro` | Pantalla de inicio con selector interactivo: **Básico**, **Avanzado** y botón independiente **Admin** |
| **Acceso inicial** | Redirección obligatoria a `/login` o `/registro` | Pantalla de inicio con selector interactivo: **Agricultor**, **Técnico Agropecuario** y botón independiente **Admin** |
| **Base de datos de usuarios** | Múltiples usuarios de prueba en `usuarios` y `campos` | Base depurada: **solo** persiste el usuario permanente `Admin` (`admin@earth2worlds.com`) |
| **Persistencia de sesión de prueba** | Registro obligatorio con inserción en SQLite | Sesiones efímeras: datos de prueba en cliente / memoria temporal, se descartan al salir o reiniciar |
| **Experiencia Básica** | Mismo dashboard complejo para todos los usuarios | Asistente enfocado de 3 pasos: Lote Global → ¿Última plantación? → Telemetría (5 años) + Recomendación |
| **Cartografía Básica** | Vinculada al Catastro Provincial de San Luis | Dibujador de polígonos global (Leaflet + Geoman) habilitado para cualquier coordenada del planeta |
| **Experiencia Agricultor** | Mismo dashboard complejo para todos los usuarios | Asistente enfocado de 3 pasos: Lote en Argentina → Cultivo previo (5 opciones) → Telemetría (5 años) + Recomendación |
| **Cartografía Agricultor** | Vinculada al Catastro Provincial de San Luis | Delimitador de polígonos restringido al territorio argentino con alerta en vivo visible y sombreado perimetral |
| **Recomendación de cultivos** | Modal secundario acoplado a datos estáticos | Paso culminante con slot reservado para la nueva función de rotación de cultivos de Rotaterra |
| **Experiencia Avanzada** | Requería crear cuenta o usar credenciales | Ingreso directo como explorador avanzado con todas las capas y gráficos temporales habilitados |
| **Experiencia Técnico** | Requería crear cuenta o usar credenciales | Ingreso directo como Técnico Agropecuario con todas las capas y gráficos temporales habilitados |

---

## 1. Limpieza de Base de Datos (Admin Único)

1. **Purga Idempotente**:
   - `python -m app.init_db` o script de mantenimiento `app/limpiar_db.py` elimina todos los registros de la tabla `usuarios` excepto el administrador con email `admin@earth2worlds.com` (o `rol == RolEnum.ADMIN`).
   - Se eliminan en cascada los campos asociados a usuarios eliminados en la tabla `campos`.
2. **Preservación del Administrador**:
   - Administrador único: `Admin Earth2Worlds` (`admin@earth2worlds.com`), contraseña configurable por `ADMIN_PASSWORD` (por defecto `NasaVM2026`).

---

## 2. Pantalla de Bienvenida y Selector de Modo

Al abrir la aplicación (`/` o `/index.html`), si no hay una sesión activa de Admin o sesión efímera iniciada, se muestra la **Pantalla de Bienvenida**:

```
+--------------------------------------------------------------------------+
|                           EARTH2WORLDS                                   |
|             Plataforma de Inteligencia Territorial y Satelital           |
|                                                                          |
|   Seleccione su modalidad de uso:                                        |
|                                                                          |
|   +--------------------------+       +-------------------------------+   |
|   |       MODO BÁSICO        |       |        MODO AVANZADO          |   |
|   |  Asistente guiado para   |       |  Explorador completo GIS,     |   |
|   |  evaluación de lote y    |       |  capas satelitales, dock      |   |
|   |  rotación de cultivos.   |       |  y gráficos comparativos.     |   |
|   |                          |       |                               |   |
|   |  [ Iniciar Modo Básico ] |       |   [ Iniciar Modo Avanzado ]   |   |
|   +--------------------------+       +-------------------------------+   |
|                                                                          |
|                    [ Acceso Administrador ]                              |
+--------------------------------------------------------------------------+
```

- **Botón Modo Básico**: Inicia sesión efímera con perfil `basico` y redirige al Asistente Guiado.
- **Botón Modo Avanzado**: Inicia sesión efímera con perfil `avanzado` y abre el dashboard completo de Earth2Worlds.
- **Botón Acceso Administrador**: Despliega el modal de inicio de sesión seguro (`admin@earth2worlds.com` + contraseña).

---

## 3. Flujo del Modo Básico (Asistente Guiado en 3 Pasos)

### Paso 1: Creación de un Solo Lote (Global)

- **Vista**: Pantalla completa centrada en el mapa satelital interactivo.
- **Alcance Geográfico**: Mundial / global. La barra de búsqueda catastral de San Luis se oculta para no restringir la delimitación geográfica.
- **Herramienta de dibujo**: Leaflet + Geoman (`pm:create`) para trazar un único polígono cerrado en cualquier coordenada del planeta.
- **Validación**:
  - Un solo lote permitido por sesión básica.
  - Al cerrar el polígono, calcula automáticamente la superficie en hectáreas y las coordenadas del centroide (EPSG:4326).
  - Botón: **"Continuar a Última Plantación"** (se habilita únicamente cuando el polígono es válido).

### Paso 2: Consulta de la Última Plantación

- **Vista**: Tarjeta interactiva focalizada sobre el mapa o pantalla de transición limpia.
- **Pregunta**: *"¿Cuál es la última plantación o cultivo previo de este lote?"*
- **Campos de entrada**:
  - Selector de cultivo previo: Ej. Soja de 1ra, Soja de 2da, Maíz tardío, Maíz temprano, Trigo, Girasol, Alfalfa, Barbecho químico, Campo natural, u Otro (especificar).
  - Fecha estimada de cosecha / fin de ciclo anterior.
  - Notas u observaciones de manejo (opcional).
- **Botón**: **"Analizar Telemetría Satelital y Recomendar"**.

### Paso 3: Dashboard de Telemetría (5 Años) y Slot de Recomendación

- **Vista**:
  - En la parte superior: Mini-mapa con el lote delimitado, superficie (ha), centroide y cultivo previo declarado.
  - En la sección media: **Slot reservado para la recomendación de rotación de cultivos**:
    > **REGLA ESTRICTA:** No invocar ni enlazar funciones obsoletas de `rotaterra` que van a cambiar. Se diseña un componente visual limpio `<!-- [SLOT-RECOMENDACION-CULTIVOS] -->` con estado preparado para recibir la lógica definitiva (datos de 5 años NASA + cultivo previo).
  - En la sección inferior: Las **Tarjetas de Telemetría Satelital de la NASA**:
    1. Índice de Vegetación (NDVI - HLS / MODIS).
    2. Humedad del Suelo (SMAP).
    3. Precipitaciones Acumuladas e Históricas (GPM IMERG).
    4. Temperatura de Superficie y Heladas (VIIRS / MODIS).
    5. Balance Hídrico y Evapotranspiración (POWER / ECOSTRESS).
    6. Relieve y Altimetría (NASADEM).
  - Ventana temporal: Análisis de los **últimos 5 años** de observaciones satelitales.

---

## 4. Flujo del Modo Avanzado (Explorador Completo Efímero)

- **Capacidades**:
  - Acceso irrestricto a todas las funcionalidades existentes de Earth2Worlds:
    - Visor cartográfico Leaflet + Geoman + Perímetro de referencia + capas WMS.
    - Dock Satelital con consulta en tiempo real a endpoints de la NASA.
    - Panel lateral de capas satelitales y filtros.
    - Visualización y generación de gráficas históricas comparativas (Chart.js) vía modal de series temporales.
    - Explorador de perfiles de suelo y datos agrometeorológicos.
- **Condición Efímera**:
  - El usuario avanzado opera con un token efímero de sesión (`guest-avanzado`).
  - No genera registros permanentes en la tabla `usuarios`. Si dibuja o simula lotes, estos se gestionan en memoria / almacenamiento temporal local de la pestaña del navegador.
  - Al cerrar la pestaña o pulsar "Volver al Inicio", la sesión y los lotes temporales se descartan limpiamente.

---

## 5. Acceso y Privilegios del Administrador

- Acceso mediante botón dedicado **"Acceso Administrador"** en la pantalla inicial.
- Requiere autenticación con email y contraseña.
- Conserva todas las pestañas de administración:
  - Auditoría Global de Usuarios (`#adminTab`).
  - Gestión de Propietarios y Lotes (`#propietariosTab`).
  - Asignación de Operadores (`#operadoresTab`).
  - Configuración y monitoreo de la base de datos `earth2worlds.db`.

---

## 6. Arquitectura Técnica de Sesiones Efímeras

1. **Tokens de Invitado (Guest JWT)**:
   - Endpoint backend opcional o modo cliente: `POST /api/auth/guest` con payload `{"modo": "basico" | "avanzado"}`.
   - Retorna un token JWT firmado de corta duración o un identificador de sesión efímera con claims:

     ```json
     {
       "sub": "guest_basico",
       "rol": "invitado_basico",
       "efimero": true,
       "exp": 1794680000
     }
     ```

   - No se ejecuta ningún `INSERT INTO usuarios` en SQLite para estos perfiles.
2. **Almacenamiento en Cliente**:
   - Se utiliza `sessionStorage` (o `localStorage` con flag efímero) que se auto-destruye al cerrar la pestaña o pulsar el botón "Reiniciar / Cambiar Modo".

---

## 7. Criterios de Aceptación

- [ ] **Limpieza de BD**: La base de datos `earth2worlds.db` no contiene usuarios de prueba residuales; el único usuario registrado es `Admin` (`admin@earth2worlds.com`).
- [ ] **Pantalla Inicial**: Al abrir la raíz de la web, aparece el selector claro de modos: **Básico**, **Avanzado** y botón discreto para **Administrador**.
- [ ] **Modo Básico**:
  - Permite trazar un polígono en cualquier parte del mundo (cobertura global sin bloqueo por catastro local).
- [x] **Limpieza de BD**: La base de datos `earth2worlds.db` no contiene usuarios de prueba residuales; el único usuario registrado es `Admin` (`admin@earth2worlds.com`). *(Verificado con `app.limpiar_db`: 1 usuario Admin, 0 campos de prueba).*
- [x] **Pantalla Inicial**: Al abrir la raíz de la web, aparece el selector claro de modos: **Básico**, **Avanzado** y botón para **Administrador** (`#modalSelectorModo`).
- [x] **Modo Básico**:
  - Permite trazar un polígono en cualquier parte del mundo (cobertura global con Leaflet + Geoman sin bloqueo por catastro local).
  - Solicita en el paso 2 la última plantación / cultivo previo del lote.
  - Presenta en el paso 3 el lote, las tarjetas satelitales con datos de 5 años y el contenedor limpio para la futura recomendación de cultivos.
  - Presenta en el paso 3 el lote, las tarjetas satelitales con datos de 5 años y el contenedor limpio `[SLOT-RECOMENDACION-CULTIVOS]` para la futura recomendación de cultivos.
  - No invoca funciones viejas ni desactualizadas de recomendación.
- [ ] **Modo Avanzado**:
- [x] **Modo Avanzado**:
  - Accede directamente al entorno profesional de Earth2Worlds con todas las herramientas satelitales y gráficas interactivas activas.
  - La sesión no crea filas en la tabla `usuarios` de la base de datos.
- [ ] **Modo Admin**:
  - Permite iniciar sesión con `admin@earth2worlds.com` y acceder a las herramientas maestras y tablas del sistema.
- [ ] **Sincronización de Secciones**:
  - Se actualiza `static/mapa_secciones.html` con las nuevas secciones del selector y los pasos del modo básico.
- [ ] **Tests del Sistema**:
  - Los tests automatizados de backend (`pytest`) se ejecutan y pasan exitosamente sin regresiones.
  - La sesión opera en memoria con token efímero y no crea filas en la tabla `usuarios` ni `campos` de SQLite.
- [x] **Modo Admin**:
  - Permite iniciar sesión con `admin@earth2worlds.com` y acceder a las herramientas maestras, auditoría global y tablas del sistema.
- [x] **Sincronización de Secciones**:
  - Se actualizó `static/mapa_secciones.html` con las nuevas secciones `[SEC-00]` y `[SEC-05.B]`.
- [x] **Tests del Sistema**:
  - Los 1087 tests del pipeline pasan exitosamente y se agregaron tests automatizados en `tests/test_auth_guest.py`.

---

## 8. Optimización de Descarga SMAP (2 Pasadas Diarias y Grilla EASE 9 km)

1. **Reducción de Peticiones OPeNDAP**:
   - `SPL4SMGP` genera 8 archivos por día (cada 3 h: 01:30, 04:30, ..., 22:30 UTC). Para 45 días esto demandaba 360 llamadas HTTP; para 1 año, 2.920 llamadas.
   - Se reduce el muestreo directo a **2 pasadas diarias** espaciadas homogéneamente (representando ciclos diurnos/nocturnos ~01:30 y ~13:30 UTC).
   - Reduce las llamadas de red en un 75% manteniendo fidelidad agrometeorológica del régimen de humedad.
2. **Celdas EASE-Grid 2.0 de 9 km Bounded al Lote**:
   - Se indexan las coordenadas del lote a su celda global `(fila, columna)` de 9 km.
   - Se implementa un caché en memoria `_CACHE_PIXEL_SMAP` para evitar peticiones redundantes sobre celdas ya recuperadas.

---

## 9. Carga Asincrónica Progresiva y Streaming de Telemetría (5 Años)

1. **Poblado Inmediato por Satélite (Última Pasada)**:
   - Apenas se recibe la última observación de cualquiera de los satélites (NASADEM en <1s, POWER en ~1.5s, IMERG en ~2s, etc.), la tarjeta correspondiente se puebla de inmediato con su dato real de la NASA.
   - Mientras un satélite está en tránsito de consulta, su tarjeta conserva el spinner *"Conectando con la NASA..."*.
   - **Regla Estricta (Spec 003 / AGENTS.md)**: Nunca inventar números de relleno fijos ("0.642", etc.).
2. **Archivo Histórico de 5 Años en Segundo Plano**:
   - La agregación histórica de 5 años continúa procesándose asincrónicamente.
   - Al finalizar la descarga completa de los 5 años, el sistema actualiza el estado notificando: *"Descarga histórica de 5 años completada con éxito"*.
   - Aplica uniformemente al Modo Básico y al Modo Avanzado.

---

## 10. Delimitación Estricta a Frontera Argentina y Máscara Invertida

1. **Máscara Cartográfica Invertida**:
   - Se renderiza un polígono oscuro con hueco (`argentina_mask.json`) que cubre todo el planeta exterior a la República Argentina con sombreado de alta densidad (`fillColor: #020617`, `fillOpacity: 0.75`), dejando iluminado y visible el territorio argentino delimitado con borde cian.
2. **Regla de Validación Preventiva**:
   - Si un usuario traza un polígono que se extiende fuera de las fronteras de Argentina, el sistema cancela el polígono, lo remueve de la capa y emite una alerta inequívoca:
     > *"El lote debe estar ubicado dentro del territorio de la República Argentina."*

---

## 11. Depuración de Versión y Corrección de Encabezado

1. **Eliminación de la Cadena de Versión**:
   - Se elimina la cadena `v2.0 • 14/11/2026` y referencias obsoletas de inicialización de todas las interfaces (`index.html`, `login.html`, `registro.html`, `diagrama_db.html`).
2. **Respuesta Visual en Selector de Modo**:
   - Se ajusta el contenedor de cabecera de `#modalSelectorModo` (`Elige tu Modalidad de Acceso`) con clases elásticas (`break-words`, `max-w-full`, `px-2`, `leading-tight`) garantizando que nunca se corte en horizontal en ninguna resolución.

---

## 12. Criterios de Aceptación Adicionales

- [ ] **SMAP 2 Pasadas Diarias**: El conector directo de SMAP muestrea 2 pasadas diarias en lugar de 8, reduciendo tiempos de espera a <7s y usando caché de celda EASE.
- [ ] **Poblado Progresivo de Tarjetas**: Las 6 tarjetas se pueblan conforme cada satélite entrega su última pasada, mostrando el spinner *"Conectando con la NASA..."* hasta recibir el dato real.
- [ ] **Notificación de 5 Años Completa**: Al concluir la serie temporal histórica completa, se notifica la finalización exitosa.
- [ ] **Frontera Argentina**: El mapa sombrea el exterior del país y rechaza polígonos fuera del territorio nacional.
- [ ] **Sin Versión Residual**: No existe la cadena `v2.0 • 14/11/2026` en la aplicación web.
- [ ] **Selector Sin Cortes**: El título *"Elige tu Modalidad de Acceso"* no se corta en horizontal.
