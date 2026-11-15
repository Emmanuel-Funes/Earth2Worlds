# Working in this Repository

Guidelines for any developer or AI agent touching the Rotaterra (Earth2Worlds) data pipeline.

## 1. Spec First (SDD)

- Every new piece starts with a specification in `docs/specs/NNN-topic.md`: objective, source, input, process, output, quality rules, and acceptance criteria.
- Code is only written once the spec is approved.
- An acceptance criterion is checked (`[x]`) only after verification, ideally with real data and recorded values.
- If code changes anything described in the spec, the spec must be updated in the same PR.

## 2. NASA Data Only

All primary and fallback data sources originate from NASA. The only intended exceptions are producer-supplied data and INTA soil surveys (GeoINTA), as detailed in the Technical Guide.

## 3. Common Contract

Every source delivers a list of `Observacion` (`rotaterra/contrato.py`):

```json
{"lote_id": "lote-7", "fecha": "2026-11-14", "variable": "lluvia_mm", "valor": 22.5,
 "unidad": "mm/day", "fuente": "IMERG", "resolucion_m": 10000, "calidad": "buena", "nota": "..."}
```

- **Never invent a value.** If data is missing, use `valor: null` + `calidad: "descartada"`, and the `nota` explains why.
- Always specify the unit, source, and date.
- The working area is the field polygon in GeoJSON (EPSG:4326).
- Assumptions (thresholds, scales) must be documented in the `nota` and the spec.

## 4. The Application Awaits NASA (Spec 010)

The application requests NASA data in real time and awaits the response via satellite endpoints: `/clima`, `/ndvi`, `/humedad-suelo`, `/lluvia`, and `/altimetria`. Response times range from seconds to minutes (HLS, AppEEARS), so the app must indicate wait states. To allow fallbacks if a primary satellite fails, the app uses `POST /consulta` (Spec 012).

The database and nightly batch update (`rotaterra/actualizar.py`, `GET /lotes/{id}/observaciones`) serve as an optional complement when a database is provisioned.

## 5. Self-Explanatory Naming Conventions

| Item | Format | Example |
|---|---|---|
| Branch | `satelite-<satellite>-<info>` | `satelite-gpm-imerg-lluvia`, `satelite-nasadem-relieve` |
| PR Title | `SATELLITE - What it provides` | `MODIS - 250m NASA NDVI as fallback for HLS` |
| Test Workflow | `Test SATELLITE (info)` | `Test SMAP (soil moisture)` |
| Spec | `NNN-topic.md` | `006-lluvia-imerg-y-respaldo-merra2.md` |

Every PR description begins with "Before:" and "After:" in plain language.

## 6. Secrets Management

`EARTHDATA_USERNAME`, `EARTHDATA_PASSWORD`, and `DATABASE_URL` reside **exclusively** in GitHub Secrets (Settings → Secrets and variables → Actions). Never commit them to code, commits, logs, or chats.

## 7. Testing

- `pytest`: Offline tests with mocked NASA HTTP responses (`httpx.MockTransport`). Executed on every PR, with SQLite and PostgreSQL.
- Real integration tests: One `Test ...` workflow per source, run on PRs modifying that connector and triggerable manually.

## 8. Independent Satellites (Spec 009)

- `main` contains solely the **core**: contract, database, geometry, updates, API, `registro.py`, and `earthdata.py`.
- Each satellite and fallback lives in **its own branch**, merging into `main` only upon approval.
- A satellite **never** imports code from another satellite, and the core never explicitly names a satellite. `tests/test_nucleo.py` enforces this.

## 9. Adding a New Satellite

1. Write the spec, defining the source and its NASA fallback.
2. Create branch `satelite-<satellite>-<info>` from `main` (after merging core).
3. Write connector in `rotaterra/fuentes/<satellite>.py`:
   - May only use core modules (`contrato`, `geo`, `earthdata`, `registro`).
   - Declares `SATELITES = [Satelite(...)]` at the end, with `respaldo_de=` if it is a fallback, and optionally a test `router`.
4. Write offline tests in `tests/test_<satellite>.py`.
5. Add `probar_<satellite>.py` and its corresponding test workflow.
6. Open the PR. Do not touch core files, except `PRIORIDAD` in `base.py` if source confidence rank changes.

---

## 10. Earth2Worlds Web Platform Architecture (`app/` and `static/`)

### Full-Stack Team Roles
1. **Database Specialist (`app/database.py`, `app/models.py`, `app/init_db.py`)**:
   - Manages SQLAlchemy 2.0 schema on `earth2worlds.db` (`usuarios` and `campos`), ORM relations, idempotent Admin seeding (`Admin` / `admin@earth2worlds.com`) without preloaded legacy data, and extension slots (`geometria_geojson` and `configuracion_extra`).
2. **Backend Specialist (`app/auth.py`, `app/schemas.py`, `app/data/argentina_geo.py`, `app/main.py`)**:
   - Manages JWT HS256 + Bcrypt security, Pydantic v2 validation, geographic catalog for the 23 Argentine provinces + CABA, live schema introspection (`GET /api/database/schema`), and strict RBAC matrix (`admin`, `propietario`, `operador`).
3. **Frontend Specialist (`static/index.html`, `static/login.html`, `static/registro.html`, `static/mapa_secciones.html`, `static/diagrama_db.html`, `static/js/*`)**:
   - Manages the Dark Mode Single Page Application (Tailwind CSS + Vanilla JS ES6+ with `escapeHtml()` sanitization), preserving clean module slots `<!-- [SLOT-MODULO-MAPA] -->` (`#slotModuloMapa`, `#slotModalMapa`) and `<!-- [SLOT-MODULO-TELEMETRIA] -->` (`#slotModuloTelemetria`).

### Section Synchronization Rule
Whenever a section `[SEC-XX]` or controller `[JS-XX]` is added, modified, or restructured in `static/index.html`, the file `static/mapa_secciones.html` must be updated in the same change to keep the Master Section Map accurate.

---

## 11. Document & README Synchronization Rule (`README.md` and specs)

To prevent local vs. remote editing conflicts and maintain continuous collaboration synchronization:

1. **Additive Merging Without Destructive Overwriting**:
   - Whenever changes are pulled or merged from remote branches, compare modified sections of remote documentation with local working copies.
   - If a version introduces technical details, satellite tables, instructions, or rules, integrate those additions while preserving existing structure.
   - **Never** discard or truncate valid contributor content solely due to timestamp discrepancies.
2. **Buffer/Editor Synchronization**:
   - If an open documentation file (`README.md`, `docs/specs/*`, `AGENTS.md`) experiences desynchronization from concurrent Git updates, run granular diff comparison (`git diff`), integrate updates coherently, and update Git index to sync cleanly without manual intervention.
