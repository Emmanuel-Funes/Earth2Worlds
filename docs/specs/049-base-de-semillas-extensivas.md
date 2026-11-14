# 049 · Base de fuentes de semillas de cultivos extensivos

**Estado:** borrador para aprobación de Hernán
**Origen:** documento "SSD Agrícola Argentina — Arquitectura funcional, técnica y de datos" v1.4, secciones 4.5–4.13, 5.1, 14, 15 y 16.

## 1. Objetivo

Tener en un solo lugar, con fecha y origen de cada dato, **qué cultivares de cultivos extensivos están inscriptos en Argentina**, quién los obtuvo, si declaran eventos OGM, si tienen propiedad vigente, y **qué fuentes oficiales** hay que consultar para completar cada cultivo (eventos, fichas INTA, ensayos, uso por campaña, disponibilidad).

Es la "Fase 0 — Catálogo y datos" del documento SSD. No recomienda ninguna semilla: deja la base para que el comparador de cultivares lo haga después con evidencia.

## 2. Fuentes

| Fuente | Rol | Estado |
|---|---|---|
| INASE · Catálogo Nacional de Cultivares (exportación CSV) | Maestra: identidad y registro | **Ingerida** (archivo descargado de la consulta pública de INASE, SHA-256 en `manifiesto.json`) |
| SAGyP · Eventos con autorización comercial; CONABIA | Maestra para eventos OGM | Localizada, falta contrastar |
| INTA variedades, INTeA, INASE descripciones y rotulado | Fichas, licencias, calidad | Localizadas |
| SISA, RECSO, RET, redes INTA (Marcos Juárez, San Luis, etc.) | Uso y ensayos por campaña | Localizadas |
| Datos abiertos INASE 2019 | Solo histórico | No usar como vigente |

El registro completo, con URL, qué aporta, acceso y frecuencia, está en `semillas/fuentes.py` y sale como `fuentes.csv`.

## 3. Entrada

El CSV que genera el botón "Exportar a CSV" del catálogo público de INASE, guardado sin tocar en `semillas/datos/raw/inase/catalogo_inase_AAAA-MM-DD.csv`. Si cambian las columnas, el armador se frena y avisa.

## 4. Proceso (`python -m semillas.construir_base <csv> <carpeta>`)

1. Lee el CSV y calcula su SHA-256.
2. Asigna cada especie de INASE a uno de los 24 perfiles del documento SSD, o a un grupo **complementario** de cultivos cuya cosecha se vende (alfalfa, haba, caupí, camelina, mostazas, sésamo, chía, quinoa, mijo, alpiste, amaranto, tártago, cáñamo industrial).
3. Marca subtipo, destino y si es extensivo, **solo con lo que dice INASE** (especie, grupo y condición genética). Ejemplos: el maíz choclo/dulce y el poroto chaucha quedan fuera; el sorgo forrajero y el granífero quedan separados.
4. Separa los eventos apilados en eventos únicos y arma la tabla cultivar–evento.
5. Calcula el estado de propiedad (RNPC) contra la fecha de corte.
6. Busca en INASE los materiales INTA que lista el documento SSD: exacto, a revisión o no encontrado. **Nunca une dos nombres solo porque se parecen.**
7. Genera los controles de calidad y el Excel.

## 5. Salida

| Archivo | Contenido |
|---|---|
| `perfiles.csv` | Un renglón por cultivo: registros, híbridos/variedades, OGM, RNPC vigente, INTA, nuevos 2022–2026, obtentores |
| `cultivares.csv` | Cada cultivar con sus 17 columnas originales de INASE más las derivadas |
| `eventos_ogm.csv`, `cultivar_evento.csv` | Eventos declarados y su vínculo con cada cultivar |
| `obtentores.csv` | Solicitante RNC por cultivo |
| `candidatos_inta.csv` | Conciliación de los materiales INTA del documento SSD |
| `fuentes.csv`, `ensayos_por_perfil.csv` | Registro de fuentes y ensayos localizados |
| `oferta_comercial.csv` | Lo que las empresas dicen ofrecer, lo más sembrado (SISA) y los ensayos, cruzado con INASE. Entrada a mano: `semillas/datos/oferta_comercial_2026_27.csv`, con link y fecha en cada fila |
| `control_calidad.csv` | Registros para revisar antes de usar |
| `manifiesto.json`, `base_semillas_extensivas.xlsx` | Trazabilidad y todo junto en Excel |

## 6. Reglas de calidad

- Nunca se inventa un valor: lo que la fuente no dice queda `sin dato verificado`.
- "Sin evento declarado en este registro" **no** es "convencional confirmada".
- "Inscripto en RNC" **no** es "hay semilla para comprar": `disponibilidad_comercial` queda sin dato hasta tener una cotización con proveedor, región, campaña y fecha.
- CL (Clearfield), STS y alto oleico no son eventos OGM.
- El tipo comercial del poroto (negro, alubia, colorado) no se adivina por el nombre: INASE no lo trae.
- El estado de autorización de cada evento queda "pendiente de contrastar" con la lista de SAGyP.

## 7. Criterios de aceptación

- [x] Los 22 grupos de cultivo del catálogo (24 perfiles; los 3 porotos comparten especie) tienen renglón en `perfiles.csv`. Verificado: 7.850 cultivares de 14.369 filas.
- [x] Cada cultivar conserva el dato original de INASE y su `cultivar_id` (`INASE-<número>`).
- [x] Los eventos OGM están en tabla aparte: 27 eventos únicos, 3.185 pares cultivar–evento.
- [x] Ningún cultivar tiene disponibilidad comercial verificada inventada (0 en todos los cultivos).
- [x] La conciliación INTA no fusiona por parecido: 97 exactos, 10 a revisión, 13 no encontrados de 120.
- [x] Tests sin internet (`tests/test_semillas.py`).
- [x] Oferta 2026/27 cruzada con INASE: 92 materiales; 52 con el mismo nombre, 27 para revisar, 13 no encontrados. Nada queda marcado como disponible sin precio ni stock.
- [ ] Eventos contrastados con la lista oficial de SAGyP (los sitios .gob.ar no fueron accesibles desde el entorno que armó la base).
- [ ] Ensayos extraídos a filas (empezar por INTA EEA San Luis para el piloto).
- [ ] Fecha exacta de descarga del CSV anotada por quien lo bajó.

## Ampliación

- La fuente maestra pasa a ser `semillas/datos/raw/inase/catalogo_inase_2026-10-28.csv`, descargado de la consulta pública de INASE ("Exportar a CSV" sin filtros). Se construye con `--fecha-corte 2026-10-28`. El archivo del 23/10 queda como respaldo.
- Los registros sin inscripción RNC (solo RNPC) se conservan con `estado_registral = SOLO_RNPC…` y `extensivo = REVISAR`. La condición genética "LINEA" se informa como "Línea (parental de híbridos)".
- Criterio de Hernán: solo cultivos cuya cosecha se vende. Quedan fuera las pasturas (grupo FO) y los forrajes que se consumen en el campo: vicias, moha, mijo perla, colza forrajera, tricepiro, trigopiro y poroto de campo. La alfalfa queda porque el motor la evalúa y el fardo y la semilla se venden.
- Se suman como complementarios el amaranto, la mostaza y el tártago.
- El catálogo público de variedades del INTA (`semillas/datos/raw/inta/catalogo_inta_2026-10-28.csv`) agrega la unidad, la licencia y el licenciatario de cada cultivar INTA (hojas "Cultivares INTA" y "INTA sin cruzar").
