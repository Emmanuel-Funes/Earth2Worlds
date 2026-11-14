# Rotaterra · Resumen de semillas en SDD

**Hilo:** "Armar el banco de semillas para San Luis"

Este resumen junta todo el trabajo de semillas que está escrito como spec (SDD) y lo que se agregó después.

## 1. Las specs

| Spec | Qué define | Dónde está | Estado |
|---|---|---|---|
| **049 · Base de fuentes de semillas de cultivos extensivos** (27/10, ampliada 28/10) | Base de todos los cultivares inscriptos en INASE, quién los obtuvo, eventos OGM y fuentes oficiales. Sale de tu documento "SSD Agrícola Argentina" v1.4. Es la "Fase 0: catálogo y datos" y todavía no recomienda ninguna semilla. | `docs/specs/049-base-de-semillas-extensivas.md`, PR #68 | Sin mergear a main, espera tu orden |
| **057 · El banco de semillas como base de datos de la API** (29/10, ampliada 30/10) | El banco va dentro de la API de Render como un archivo SQLite de solo lectura, sin servidor de base de datos. Define los endpoints `/semillas`. | `docs/specs/057-banco-de-semillas-en-la-api.md`, PR #84 | En Render desde el 29/10. Lo del 30/10 todavía no está subido |
| **SDD del agente agronómico** (tu archivo del 30/10) | Plan para investigar lenteja, caupí y mijo: fuentes INTA, SIB, Bolsas, CREA y Aapresid; solo Argentina; unidades métricas; nombre científico verificado | Lo ejecuté a mano dentro de la spec 057 (tabla de manejo) | Hecho el 30/10 |

Las demás partes (banco solo INTA, fichas por variedad, manejo por cultivo) se agregaron como ampliaciones de la 057 y en el LEEME, sin spec nueva.

## 2. Tus decisiones (son las reglas del banco)

- **Solo semillas del INTA** en esta etapa. Las de empresas privadas quedan guardadas pero ocultas, para una etapa posterior (27/10 y 29/10).
- **Todos los cultivos extensivos de Argentina**, sin filtrar por San Luis. Quedan afuera rosas, frutales y hortalizas (29/10).
- **Solo cultivos cuya cosecha se vende**: quedan afuera las pasturas y los forrajes que se comen en el campo. La alfalfa queda (28/10).
- **Archivo SQLite dentro de la API**, sin servidor de base de datos (29/10).
- La app por ahora no necesita stock ni precios (29/10).
- Cada dato tiene fuente y fecha, y nunca se inventa. Si falta un dato, dice "sin dato verificado".
- Nada va a main ni a Render sin tu OK.

## 3. Qué tiene hoy el banco

Base armada con el catálogo de INASE del 14/11/2026.

| Parte | Cantidad | De dónde sale |
|---|---|---|
| Catálogo completo de cultivares (todas las empresas) | 8.145 cultivares | INASE, Catálogo Nacional de Cultivares |
| **Banco INTA** (lo que muestra la app) | **460 variedades del INTA en 27 cultivos** | INASE + catálogo de variedades del INTA |
| Fichas de cultivo por variedad (`fichas_inta`) | 752 datos; 151 de las 460 variedades tienen ficha | Descriptores de INASE y notas del INTA |
| Manejo por cultivo (`manejo_cultivos`) | 276 datos con fuente, en 17 temas por cultivo | Guía de maní adaptada, libros de la UNLP y la UNC, SciELO, INTA, Agricultura |
| Ensayos de soja (RECSO 2025/26) | 351 ensayos, 3.618 rindes | Informe RECSO |
| Ensayos de trigo (RET 2018/19 a 2025/26) | 878 ensayos, 24.270 rindes | INASE |
| Ensayos de girasol (INTA-ASAGIR 2023-2026) | 44 ensayos, 1.583 rindes | ASAGIR |
| Ensayos de maíz (redes INTA 2024-2026) | 22 ensayos, 758 rindes | INTA Marcos Juárez y norte de Buenos Aires |
| Ensayos de sorgo (INTA Manfredi 2024/25) | 40 híbridos | PDF del INTA que subiste |
| Ensayos INTA San Luis 2025/26 | Maíz (Villa Mercedes y Tilisarao), trigo, sorgo y algodón | PDFs del INTA que subiste |
| Fuentes registradas | 25 | `semillas/fuentes.py` |

El archivo de la API tiene 32 tablas y unas 50.000 filas.

## 4. Lo que la API muestra (spec 057)

Todos los endpoints piden la clave `X-API-Key`.

| Endpoint | Qué devuelve | ¿En Render? |
|---|---|---|
| `GET /semillas` | Resumen: cultivares por cultivo y cultivos con ensayos | Sí |
| `GET /semillas/cultivares` | Lista de variedades, con buscador | Sí |
| `GET /semillas/cultivares/{id}` | Una variedad, su ficha y sus ensayos | Sí, pero sin la ficha |
| `GET /semillas/ensayos/{cultivo}` y `/rindes` | Resultados de los ensayos, por defecto San Luis y zonas vecinas | Sí |
| `GET /semillas/fuentes` | De dónde sale cada dato | Sí |
| `GET /semillas/fichas` | Condiciones de cultivo de cada variedad | **No, espera tu OK** |
| `GET /semillas/manejo` | Manejo por cultivo (clima, agua, siembra, suelo, pH, plagas, cosecha, etc.) | **No, espera tu OK** |

Lo que está en Render es la versión del 29/10 (RENDER `e012560`). El banco solo INTA, las fichas y el manejo están listos en la rama `SEMILLAS-consultas_en_la_api` (PR #84, pruebas en verde), pero no se subieron.

## 5. Ramas y PRs

| PR | Rama | Qué tiene | Estado |
|---|---|---|---|
| #68 | `claude/project-thread-gygacf` → main | Spec 049 y la base | Abierto, espera tu orden de merge |
| #85 | `claude/project-thread-2m22ft` → gygacf | Banco INTA, fichas y manejo (último commit `d5bd209`) | Abierto, pruebas en verde |
| #84 | `SEMILLAS-consultas_en_la_api` | Spec 057 y los endpoints de la API (último commit `e83de11`) | Abierto, pruebas en verde |

## 6. Lo que falta

- **Tu OK para subir a Render** el banco solo INTA, las fichas y el manejo.
- **Tu orden de merge** del PR #68.
- **Datos que siguen bloqueados**, porque el repositorio del INTA no abre desde la nube:
  - densidad y profundidad de siembra de la lenteja;
  - casi todo el manejo del caupí;
  - fichas de sorgo, maíz y porotos (casi ninguna variedad tiene ficha publicada).
  Si bajás esos PDFs y los subís al chat, los cargo.
- Contrastar los eventos OGM con la lista de Agricultura (spec 049, pendiente).

## 7. Archivos para mirar

- Página del banco: https://claude.ai/artifact/8zsoaG49rC1NedjcM9ayx2 (copia en `rotaterra/semillas/vista/banco-de-semillas.html`)
- Base completa: `rotaterra/semillas/base_semillas_extensivas.xlsx` y `semillas.sqlite`
- Manejo por cultivo: `rotaterra/semillas/manejo_cultivos.csv`
- Explicación larga: `rotaterra/semillas/LEEME-base-de-semillas.md`
- Bitácora: `rotaterra/BITACORA-avances-y-como-replicar.md`
