# Spec 057 · El banco de semillas como base de datos de la API

**Estado:** aprobada por Hernán. En la tarjeta "¿Cómo dejamos el banco de semillas para que lo use la app en Render?" eligió **"Archivo SQLite dentro de la API"**. El PR no se une sin su orden y no se sube a Render sin su OK.
**Etapa:** banco de semillas (spec 049) → API (spec 022) → app · **Rama:** `SEMILLAS-consultas_en_la_api` (sale de `NUCLEO-api_publicada_con_clave`)
**Pedido:** Hernán: "Quiero que quede como base de datos para que lo tome nuestra app en render".

## 1. Objetivo

Que la app consulte el banco de semillas desde la API de Render: los cultivares del catálogo nacional y cómo rindió cada uno en los ensayos cerca de San Luis.

| Antes | Después |
|---|---|
| El banco es un Excel y CSV sueltos en la carpeta del proyecto | Un archivo `rotaterra/datos/semillas.sqlite` (13 MB) viaja con la API |
| La app no puede preguntar nada | Endpoints `GET /semillas…` con la misma clave `X-API-Key` |

## 2. Por qué un archivo SQLite

- Hernán eligió no tener un servidor de base de datos. Para las capas de suelo ya se usa GeoPackage, que también es SQLite.
- Es gratis y no hay nada aparte que mantener. Render lo despliega con el código.
- Es de **solo lectura**: la API lo abre en modo `ro` y no escribe. Por eso no le afecta que el disco de Render se borre al reiniciar.
- Si más adelante hace falta un servidor (Postgres), las mismas tablas se cargan ahí sin cambiar los endpoints.

## 3. Cómo se arma el archivo

En la rama de semillas (spec 049):

```
python -m semillas.construir_base semillas/datos/raw/inase/catalogo_inase_2026-10-28.csv salida/ --fecha-corte 2026-10-28
python -m semillas.exportar_sqlite salida/ semillas.sqlite
```

Después se copia en `rotaterra/datos/semillas.sqlite` de esta rama.

- Cada CSV pasa a ser una tabla con el mismo nombre (27 tablas, 48.157 filas).
- Una columna queda como número solo si todas sus filas lo son. Un nombre como "0357 CL" queda como texto.
- El manifiesto de la salida va en la tabla `_manifiesto`, con la fecha de corte y el SHA-256 del CSV de INASE.

## 4. Endpoints (todos piden `X-API-Key`)

| Endpoint | Qué devuelve |
|---|---|
| `GET /semillas` | Fecha de corte de INASE, cultivares por cultivo (y cuántos son del INTA), cultivos con ensayos, aviso de que inscripto no es stock |
| `GET /semillas/cultivares?cultivo=Maíz&texto=471&solo_inta=false&limite=50&desde=0` | Cultivares del catálogo, paginados |
| `GET /semillas/cultivares/{cultivar_id}` | Un cultivar, su ficha de cultivo (`ficha`) y, si se ensayó, su resumen en cada red |
| `GET /semillas/fichas?cultivo=Avena&atributo=epoca_siembra&cultivar_id=` | Condiciones de cultivo por variedad del INTA, una fila por dato con su fuente, y cuántas variedades de cada cultivo tienen ficha |
| `GET /semillas/ensayos/{cultivo}` | Resumen por cultivar de la red (`soja`, `trigo`, `girasol`, `maiz`, `sorgo`) |
| `GET /semillas/ensayos/{cultivo}/rindes?cultivar=&cerca_de_san_luis=true` | Cada cultivar en cada ensayo. Por defecto solo San Luis y zonas vecinas |
| `GET /semillas/fuentes` | De dónde sale cada dato y en qué estado está |

Errores:
- Un cultivo sin ensayos o un id que no existe responden `404`.
- Si el archivo no está, la respuesta es `503`.

## 5. Reglas

- **Solo INTA y de todo el país.** Hernán: "preciso que me traiga todo lo que se siembra en argentina … toda la info que me traigas sea del INTA, no me interesan las semillas de empresas privadas". Por eso:
  - `/semillas` y `/semillas/cultivares` leen la tabla `banco_inta`: 460 cultivares del INTA de 27 cultivos extensivos, como trigo, maíz, sorgo, caña de azúcar, arveja y lenteja. Hernán: "de nada me sirven rosas, solo cultivos extensivos". El filtro `grupo` sirve para acotar.
  - En los ensayos solo aparecen los materiales del INTA. El rinde relativo se calcula contra la media de todo el ensayo.
  - Lo privado queda en el archivo y solo aparece con `incluir_privadas=true`, para una etapa posterior.
  - Nueva red `san_luis`: ensayos INTA EEA San Luis + UNSL 2025/26 dentro de la provincia.

- No se inventa nada. Lo que la fuente no dice viene como "sin dato verificado".
- Precio y stock no forman parte de esto. Hernán dijo que la app no los necesita por ahora.
- "Cerca de San Luis" es `referencia_san_luis` distinto de `OTRA_REGION`. Las vecinas las propuso Claude y Hernán todavía no las confirmó.

- Fichas de cultivo (Hernán: "trae lo de todos los cultivos, va a ser de suma utilidad para la aplicación"): tabla `fichas_inta`, una fila por (variedad, dato) con `fuente` y `fuente_url`. Sale de la planilla de descriptores de soja de INASE, los grupos de calidad y ciclo del trigo (INASE), el reposo invernal de la alfalfa (catálogo INASE) y lo que publican el INTA y sus noticias oficiales (ciclo, época de siembra, zona, suelo, sanidad, tolerancias). Al 30/10/2026: 151 de 460 variedades. Si una variedad no tiene filas, la ficha dice "sin dato verificado": no se completa con datos de otra variedad.

## 6. Criterios de aceptación

- [x] `GET /semillas` sobre el archivo real: más de 8.000 cultivares, fecha de corte 2026-10-28 (test `test_el_archivo_real_viaja_con_la_api`).
- [x] Los 5 cultivos con ensayos devuelven resultados. EXP-G66 (sorgo) figura como del INTA.
- [x] El filtro de cercanía a San Luis deja afuera `OTRA_REGION`.
- [x] Un id de cultivar no se confunde con otro que empieza igual (INASE-3 contra INASE-30).
- [x] Sin clave responde `401`. Sin archivo responde `503`.
- [ ] Probado en Render con la clave real (después del OK de Hernán).

### Manejo por cultivo

Hernán pidió adaptar a Argentina una guía práctica de maní (BPM) para todos los cultivos del banco.
`GET /semillas/manejo?cultivo=&tema=&solo_con_dato=` lee la tabla `manejo_cultivos`: una fila por
cultivo y tema de la guía (clima, agua, época de siembra, suelo, pH, rotación, preparación, distancia
entre surcos, densidad, profundidad, ciclo, fertilización, plagas, malezas, enfermedades, cosecha,
secado y almacenaje). Cada dato trae `fuente`, `fuente_url` (INTA, SENASA o norma argentina) y
`verificacion` ("texto leído" o "resumen del buscador", cuando el PDF del INTA no se pudo abrir).
Los temas sin fuente dicen "sin dato verificado". 404 si el cultivo no existe.

### Ambiente por especie

`GET /semillas/ambiente?cultivo=&variable=&nivel=&capa=` lee la tabla `requerimientos_ambientales`, que sale del dossier
de investigación. Trae heladas y calor por etapa, temperatura de suelo, suelo, sales, sodio, pH, Kc, raíces,
nutrientes, ensayos y el clima y los suelos medidos en San Luis. Cada dato trae fuente, sitio y `nivel` (`San Luis`,
`Argentina` o `global`). Hernán eligió sumar FAO y los estudios de otros países solo como `global`. Es referencia
y no sirve para descartar cultivos. Responde 400 si el nivel no existe y 404 si el cultivo no tiene datos.
La spec completa está en `docs/specs/061-requerimientos-ambientales-por-especie.md`, en la rama de semillas.
