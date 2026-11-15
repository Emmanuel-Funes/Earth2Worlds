# Cómo se trabaja en este repositorio

Reglas para cualquier persona o agente de IA que toque el pipeline de datos de Rotaterra (Earth2Worlds).

## 1. Primero la spec (SDD)

- Cada pieza nueva arranca con una especificación en `docs/specs/NNN-tema.md`: objetivo, fuente, entrada, proceso, salida, reglas de calidad y criterios de aceptación.
- El código se escribe recién con la spec aprobada.
- Un criterio de aceptación se tilda (`[x]`) solo cuando se verificó, idealmente con datos reales y anotando los números obtenidos.
- Si el código cambia algo que la spec describe, se actualiza la spec en el mismo PR.

## 2. Solo datos de la NASA

Todas las fuentes y todos los respaldos son de la NASA. Las excepciones previstas son los datos del productor y las cartas de suelo del INTA (GeoINTA), que figuran en la Guía técnica.

## 3. Contrato común

Toda fuente entrega una lista de `Observacion` (`rotaterra/contrato.py`):

```json
{"lote_id": "lote-7", "fecha": "2026-11-14", "variable": "lluvia_mm", "valor": 22.5,
 "unidad": "mm/día", "fuente": "IMERG", "resolucion_m": 10000, "calidad": "buena", "nota": "..."}
```

- **Nunca inventar un valor.** Si falta el dato, se usa `valor: null` + `calidad: "descartada"`, y la `nota` dice por qué.
- Siempre se indican la unidad, la fuente y la fecha.
- El área de trabajo es el polígono del lote en GeoJSON (EPSG:4326).
- Los supuestos (umbrales, escalas) se aclaran en la `nota` y en la spec.

## 4. La app espera a la NASA (spec 010)

La app pide los datos a la NASA en el momento y espera la respuesta. Lo hace con los endpoints que trae cada satélite: `/clima`, `/ndvi`, `/humedad-suelo`, `/lluvia` y `/altimetria`. La espera va de segundos a minutos (HLS, y AppEEARS si entra), así que la app tiene que mostrar que está esperando. Para que entren los respaldos si el satélite falla, la app usa `POST /consulta` (spec 012).

La base de datos y la actualización nocturna (`rotaterra/actualizar.py`, `GET /lotes/{id}/observaciones`) quedan como complemento opcional para cuando haya una base.

## 5. Nombres que se entienden a primera vista

| Qué | Formato | Ejemplo |
|---|---|---|
| Rama | `satelite-<satelite>-<informacion>` | `satelite-gpm-imerg-lluvia`, `satelite-nasadem-relieve` |
| Título del PR | `SATÉLITE - qué aporta, en castellano` | `MODIS - NDVI de 250 m de la NASA como respaldo de HLS` |
| Workflow de prueba | `Probar SATÉLITE (información)` | `Probar SMAP (humedad del suelo)` |
| Spec | `NNN-tema.md` | `006-lluvia-imerg-y-respaldo-merra2.md` |

La descripción de cada PR arranca con "Antes:" y "Después:", en lenguaje simple.

## 6. Secretos

`EARTHDATA_USERNAME`, `EARTHDATA_PASSWORD` y `DATABASE_URL` viven **solo** en GitHub (Settings → Secrets and variables → Actions). Nunca van en el código, los commits, los logs ni los chats.

## 7. Pruebas

- `pytest`: tests sin internet, con respuestas de la NASA simuladas (`httpx.MockTransport`). Corren en cada PR, con SQLite y con PostgreSQL.
- Pruebas reales: un workflow `Probar …` por fuente, que corre solo en cada PR que toque ese conector y también se puede lanzar a mano con un clic.

## 8. Satélites independientes (spec 009)

- `main` tiene solo el **núcleo**: contrato, base, geo, actualización, API, `registro.py` y `earthdata.py`.
- Cada satélite y cada respaldo vive en **su propia rama**, y se une a `main` solo cuando Hernán aprueba su PR.
- Un satélite **nunca** importa código de otro satélite, y el núcleo nunca nombra a un satélite. `tests/test_nucleo.py` lo verifica.

## 9. Cómo sumar un satélite nuevo

1. Escribir la spec, con la fuente y su respaldo de la NASA.
2. Crear la rama `satelite-<satelite>-<informacion>` desde `main` (después de unir el núcleo).
3. Escribir el conector en `rotaterra/fuentes/<satelite>.py`:
   - Solo puede usar el núcleo (`contrato`, `geo`, `earthdata`, `registro`).
   - Al final declara `SATELITES = [Satelite(...)]`, con `respaldo_de=` si es un respaldo, y opcionalmente un `router` con su endpoint de prueba.
4. Escribir los tests sin internet en `tests/test_<satelite>.py`.
5. Agregar `probar_<satelite>.py` y su workflow `Probar …`.
6. Abrir el PR. No se toca ningún archivo del núcleo, salvo `PRIORIDAD` en `base.py` si cambia la confianza de la fuente.

---

## 10. Arquitectura de la Plataforma Web Earth2Worlds (`app/` y `static/`)

### Especialistas del Equipo Full-Stack
1. **Database Specialist (`app/database.py`, `app/models.py`, `app/init_db.py`)**:
   - Responsable del esquema SQLAlchemy 2.0 sobre `earth2worlds.db` (`usuarios` y `campos`), relaciones ORM, inicialización idempotente del Administrador (`Admin` / `admin@earth2worlds.com`) sin datos pre-cargados previos al 14/11/2026, y slots de extensión (`geometria_geojson` y `configuracion_extra`).
2. **Backend Specialist (`app/auth.py`, `app/schemas.py`, `app/data/argentina_geo.py`, `app/main.py`)**:
   - Responsable de la seguridad JWT HS256 + Bcrypt, validaciones Pydantic v2, catálogo geográfico de las 23 provincias argentinas + CABA, introspección en vivo del esquema (`GET /api/database/schema`) y matriz estricta RBAC (`admin`, `propietario`, `operador`).
3. **Frontend Specialist (`static/index.html`, `static/login.html`, `static/registro.html`, `static/mapa_secciones.html`, `static/diagrama_db.html`, `static/js/*`)**:
   - Responsable de la SPA en Modo Oscuro (Tailwind CSS + Vanilla JS ES6+ con sanitización `escapeHtml()`), preservando los contenedores limpios `<!-- [SLOT-MODULO-MAPA] -->` (`#slotModuloMapa`, `#slotModalMapa`) y `<!-- [SLOT-MODULO-TELEMETRIA] -->` (`#slotModuloTelemetria`).

### Regla Obligatoria de Sincronización de Secciones
Cada vez que se agregue, modifique o reestructure una sección `[SEC-XX]` o un controlador `[JS-XX]` en `static/index.html`, es **obligatorio** actualizar en el mismo cambio el archivo `static/mapa_secciones.html` para que el Mapa Maestro de Secciones refleje fielmente la estructura vigente.

---

## 11. Regla Automática de Fusión de Documentos y README (`README.md` y specs)

Para evitar conflictos de edición local vs. remoto en el editor y mantener la sincronización continua entre colaboradores (Hernán Firmapaz y equipo):

1. **Fusión Aditiva sin Sobreescritura Destructiva**:
   - Cada vez que se integren cambios de ramas remotas (`git fetch` / `git merge`), el agente debe comparar las secciones modificadas del `README.md` remoto con el `README.md` de trabajo local.
   - Si una versión añade información técnica, tablas de satélites, instrucciones o reglas, se incorporan esas novedades conservando la estructura y aportes preexistentes.
   - **Nunca** descartar ni truncar contenido válido de un colaborador por discrepancia de fecha o timestamp de archivo.
2. **Resolución Automática de Discrepancias de Buffer/Editor**:
   - Si un archivo de documentación abierto en el editor (`README.md`, `docs/specs/*`, `AGENTS.md`) presenta desincronización por cambios concurrentes en Git, el agente ejecuta una comparación de diff granular (`git diff`), integra las líneas nuevas de forma coherente en el archivo y actualiza el índice de Git para que el editor sincronice el buffer automáticamente sin requerir comparación manual del usuario.
