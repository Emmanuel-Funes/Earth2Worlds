# Spec 012 · Los respaldos también entran cuando la app consulta en el momento

**Estado:** aprobada por Hernán (tarjeta "¿Hago que los respaldos entren solos…?", opción "Sí, hacerlo") · **Etapa:** pipeline satélite → API → app · **Completa:** spec 010 (la app espera a la NASA) y spec 005 (respaldos)

## Objetivo

Que la app reciba el dato del respaldo, marcado con su fuente, cuando el satélite principal falla en la consulta en el momento, en lugar de recibir un error. Ejemplo: HLS falla → VIIRS → MODIS.

| Antes (spec 010) | Después |
|---|---|
| Los respaldos solo entraban en la copia nocturna, que necesita base de datos | Entran también en la consulta en el momento, sin base de datos |
| Si HLS fallaba, la app recibía un error | La app recibe el NDVI de VIIRS o MODIS, con `fuente` y el motivo |

## Entrada

`POST /consulta`, un endpoint del núcleo que sirve para cualquier satélite unido (el núcleo no nombra a ninguno, spec 009):

```json
{"satelite": "HLS", "lote_id": "lote-7", "poligono": {"type": "Polygon", "coordinates": [...]},
 "desde": "2026-01-01", "hasta": "2026-01-31"}
```

- `satelite`: el principal, tal como figura en `GET /satelites` (ej. `POWER`, `HLS`, `SMAP`, `IMERG`, `NASADEM`).
- `poligono`: el lote, GeoJSON `Polygon` en EPSG:4326. Es lo único que identifica al lote.
- `lote_id`: **opcional** (si no viene, vale `"lote"`). Es una etiqueta libre que se copia en cada observación; no se guarda ni se busca en ninguna base. Antes era obligatorio, y el equipo del frontend señaló que pedirlo sin usarlo era una contradicción.
- El centro del lote (lat/lon, para los satélites que piden un punto) se calcula del polígono.
- Rango máximo: 366 días (el mismo límite que los conectores).

`GET /satelites` lista los satélites unidos y sus respaldos en orden, para que la app sepa qué pedir.

## Proceso

1. Se pide el período al satélite principal.
2. Si falla, sigue pendiente en la NASA o no trae ningún dato, entran sus respaldos **en orden** (`orden=` de cada respaldo, spec 005) hasta que uno traiga datos.
3. Se usa la misma regla que la actualización nocturna, con una sola función del núcleo para los dos casos.
4. No se mezclan fuentes: la respuesta trae las observaciones de **una sola** fuente, la primera que respondió con datos.

## Salida

```json
{"fuente_usada": "HLS:VIIRS",
 "observaciones": [{"lote_id": "lote-7", "fecha": "2026-01-14", "variable": "ndvi", "valor": 0.51,
                    "fuente": "VIIRS", "...": "contrato común"}],
 "intentos": [{"satelite": "HLS", "resultado": "error", "mensaje": "ErrorHLS: ..."},
              {"satelite": "HLS:VIIRS", "resultado": "ok", "filas": 6, "mensaje": ""}]}
```

- `intentos` muestra a quién se le pidió y qué pasó, para que la app pueda avisar "dato de respaldo".
- Si nadie trae datos: `502` con los intentos en el detalle. Si faltan las credenciales de Earthdata: `503`. Satélite desconocido: `404`. Pedido inválido: `422`.
- **Nunca se inventa un valor.**

## Reglas de calidad

- Un principal que responde con algún dato útil (aunque otros estén `descartada` por nubes) **no** activa el respaldo. Si **todas** sus observaciones vienen descartadas, cuenta como `sin_datos` y entra el respaldo; si nadie trae nada útil, vuelven las descartadas de la primera fuente (spec 041, parte B, aprobada por Hernán).
- Los respaldos marcados `al_dia` no entran en esta cadena: después de ella completan los últimos días que la respuesta todavía no tiene, variable por variable, y la respuesta lo dice en `completada_con` (spec 043, aprobada por Hernán). `GET /satelites` los lista aparte, en `del_dia`.
- La espera puede ser de minutos (HLS, AppEEARS): la app tiene que mostrar que está esperando (spec 010).

## Criterios de aceptación

- [x] Si el principal falla, entra el primer respaldo; si ese tampoco trae datos, el siguiente (tests sin internet con satélites de prueba, `tests/test_consulta.py`: 14 pasan).
- [x] Si el principal trae datos, no se consulta ningún respaldo.
- [x] Si nadie trae datos, `502` con los intentos; satélite desconocido `404`; faltan credenciales `503`.
- [x] Funciona sin base de datos.
- [x] La actualización nocturna y la consulta usan la misma función para ordenar los respaldos (`registro.respaldos_en_orden`).
- [x] El núcleo sigue sin nombrar a ningún satélite (`tests/test_nucleo.py`).
- [x] `lote_id` es opcional: sin él la consulta responde igual (`test_api_no_exige_lote_id`).
- [ ] Con satélites reales unidos, HLS caído → la app recibe NDVI de VIIRS (se verifica cuando Hernán una los satélites).
