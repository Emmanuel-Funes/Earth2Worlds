# Banco de semillas de Rotaterra

**Rama:** `semillas-banco-de-semillas-completo` · **Specs:** `docs/specs/049-base-de-semillas-extensivas.md`, `docs/specs/057-banco-de-semillas-en-la-api.md`, `docs/specs/061-requerimientos-ambientales-por-especie.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué trae

| Pieza | Dónde | Qué hace |
|---|---|---|
| Armado de la base | `semillas/construir_base.py`, `fichas.py`, `ficha_tecnica.py`, `manejo.py`, `ambiente.py`, `fuentes.py` | Lee el catálogo público de INASE y las fuentes oficiales y arma la base en CSV con `manifiesto.json` (spec 049) |
| Paso a SQLite | `semillas/exportar_sqlite.py` | Junta todo en un solo archivo para la API (spec 057) |
| Datos de entrada | `semillas/datos/` | Catálogo INASE, catálogo INTA, ensayos (INTA San Luis, RECSO soja, RET trigo, INTA-ASAGIR girasol, redes INTA de maíz, sorgo Manfredi), fichas transcriptas, manejo por cultivo, ambiente por especie (dossier) |
| Herramientas de lectura | `semillas/herramientas/` | Los scripts con los que se pasaron a filas los cuadros de cada red de ensayos |
| Base lista | `rotaterra/datos/semillas.sqlite` | 34 tablas: 8.145 cultivares extensivos, 547 variedades de organismos públicos (`banco_inta`), 4.417 datos de fichas, 534 de manejo, 1.621 de ambiente por especie, 25 fuentes |
| Consultas en la API | `rotaterra/semillas.py` | `GET /semillas`, `/semillas/cultivares`, `/semillas/cultivares/{id}`, `/semillas/fichas`, `/semillas/manejo`, `/semillas/ambiente`, `/semillas/ensayos/{cultivo}`, `/semillas/ensayos/{cultivo}/rindes`, `/semillas/fuentes`. Todas piden `X-API-Key` |
| Informes | `docs/semillas/` | Cómo está armada la base, el informe completo con cada fuente, la lista de cultivares del INTA y los huecos que faltan pedir al INTA |

Reglas de la base: lo que la fuente no dice queda como "sin dato verificado"; estar inscripto en INASE no es tener semilla a la venta; por defecto solo salen variedades de organismos públicos (INTA, universidades, EEAOC), y las de empresas privadas solo con `incluir_privadas=true`.

## Qué no se sube

- **PDF originales.** Cada dato guarda su fuente y su enlace; los PDF quedan fuera del repositorio. El trabajo de Abdala, Otegui y Di Mauro (2026, Field Crops Research 351) va solo como cita y con los valores de su tabla 2 que se usan.
- **Claves.** La API lee `ROTATERRA_API_KEYS` del entorno; no hay ninguna clave en el código.
- **La recomendación de semillas para cada plan** (`variedades.py`) es parte del motor de rotación y viaja con él.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_semillas_construccion.py tests/test_semillas_api.py` (39 pruebas).
- Volver a armar la base desde cero y comparar con la que viaja:

```bash
python -m semillas.construir_base semillas/datos/raw/inase/catalogo_inase_2026-10-28.csv salida --fecha-corte 2026-10-28
python -m semillas.exportar_sqlite salida salida/semillas.sqlite
```

Armada de nuevo el 14/11/2026: las 34 tablas salen con la misma cantidad de filas que `rotaterra/datos/semillas.sqlite`.
