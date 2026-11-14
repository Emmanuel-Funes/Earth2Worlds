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
{"lote_id": "lote-7", "fecha": "2026-01-13", "variable": "lluvia_mm", "valor": 22.5,
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
