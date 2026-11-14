# Spec 036 · Respaldo de humedad del suelo con FLDAS

**Estado:** aprobada por Hernán el 15/10/2026 ("Listo, sigamos con los que dijiste") y verificada con datos reales · **Etapa:** pipeline satélite → API → app · **Requiere:** credenciales de Earthdata (ya cargadas) · **Rama:** `FLDAS-humedad_respaldo` · **Depende de:** PR #24 (`NUCLEO-varios_respaldos_en_orden`)

## Objetivo

Sumar un **último respaldo** a la humedad del suelo, detrás de SMAP → AppEEARS → SMAP L3 → GLDAS. Si ninguno de esos trae dato, entra FLDAS y la app igual muestra una humedad de referencia (regional y mensual) con su fuente clara.

La fuente es **FLDAS Noah 0.1°** (`FLDAS_NOAH01_C_GL_M`), un modelo de superficie de la NASA (GES DISC), hermano de GLDAS pero con grilla más fina (~11 km) y paso **mensual**. En la investigación del barrido dio, sobre el lote de San Luis, humedad superficial ~0,234 m³/m³, bien cerca de GLDAS (0,267) y de SMAP.

## Fuente

| Producto | Agencia | Qué da | Grilla | Paso | Demora | Acceso |
|---|---|---|---|---|---|---|
| `FLDAS_NOAH01_C_GL_M`, capas `SoilMoi00_10cm_tavg`, `SoilMoi10_40cm_tavg`, `SoilMoi40_100cm_tavg` | NASA (GES DISC) | Humedad del suelo por capas, en m³/m³ | 0,1° (~11 km) | mensual | ~1 mes | CMR + OPeNDAP de Earthdata (patrón de GLDAS) |

## Entrada

El lote: `lote["id"]`, su centro `lote["lat"]`/`lote["lon"]` y el período `desde`–`hasta` (máximo 24 meses). Al ser un dato regional, se lee el píxel del centro del lote.

## Proceso

1. Validar el pedido (coordenadas y rango, máximo 24 meses). Un pedido inválido no llama a la NASA.
2. Pedir a CMR los archivos mensuales del período y leer por OPeNDAP (`.dmr` + `.dap.csv`) solo el píxel del lote. La última dimensión pide 2 celdas (el servidor de la NASA devuelve vacío si pide una sola).
3. Por mes: `humedad_superficial` = capa de 0–10 cm; `humedad_zona_raiz` = promedio ponderado por espesor de las capas 0–10, 10–40 y 40–100 cm (0 a 100 cm). Las capas ya vienen en m³/m³.
4. Una observación por mes y variable, fechada el día 1 del mes.

## Salida (contrato común)

```json
{"lote_id": "lote-7", "fecha": "2026-02-01", "variable": "humedad_superficial", "valor": 0.234,
 "unidad": "m³/m³", "fuente": "FLDAS", "resolucion_m": 11000, "calidad": "dudosa",
 "nota": "Respaldo · humedad del suelo de 0 a 10 cm del modelo FLDAS Noah de la NASA (GES DISC) · promedio del mes · píxel de 0,1° (~11 km), dato REGIONAL y MENSUAL de modelo, no una medición del lote"}
```

- `fuente: "FLDAS"` es nueva en el contrato (se agrega al `Literal`, único cambio de núcleo permitido por la Guía pt 9, junto con su prioridad). Variables `humedad_superficial` y `humedad_zona_raiz`, las mismas de SMAP.

## Reglas de calidad

1. **Nunca inventar.** Capa con relleno (-9999) queda sin dato; si falta una capa de la zona de raíces, no se promedia (queda `descartada`).
2. **Calidad siempre `dudosa`:** es un promedio **mensual** de un modelo **regional** (~11 km), nunca una medición del día ni del lote. Valor fuera del rango físico (0 a 1 m³/m³) también es `dudosa`, avisando en la nota.
3. Entra **último** (orden 4): solo si SMAP, AppEEARS, SMAP L3 y GLDAS no trajeron dato.

## Dónde entra

- **Registro (spec 009):** `SATELITES = [Satelite("SMAP:FLDAS", pedir, respaldo_de="SMAP", orden=4)]`.
- **Consulta en el momento (spec 012):** entra solo cuando los respaldos anteriores de humedad fallan.
- **Núcleo:** se agrega `"FLDAS"` al `Literal` del contrato y `"FLDAS": 6` en `base.PRIORIDAD` (menos confianza que GLDAS, por ser mensual). Nada más del núcleo se toca.

## Prueba real

Workflow `Probar FLDAS (humedad)` (`.github/workflows/probar-fldas.yml`, `probar_fldas.py`). Por defecto: lote de San Luis, de noviembre 2025 a febrero 2026. Corre en cada PR que toque estos archivos y a mano con un clic.

## Resultado de la prueba real

Workflow `Probar FLDAS (humedad)` en el PR #52 (15/10/2026, en verde), lote de prueba (centro -33,7025; -65,2975), últimos 4 meses de FLDAS (noviembre 2025 a febrero 2026). 8 observaciones, todas `dudosa` (dato regional y mensual de modelo):

| Mes | Superficial (0-10 cm) | Zona de raíces (0-100 cm) |
|---|---|---|
| nov 2025 | 0,262 | 0,211 |
| dic 2025 | 0,253 | 0,185 |
| ene 2026 | 0,195 | 0,155 |
| feb 2026 | 0,234 | 0,165 |

En m³/m³. La humedad superficial queda en el orden de **0,2 m³/m³**, coincidiendo con GLDAS (~0,267) y con SMAP en el mismo lote: FLDAS es un respaldo consistente de la humedad del suelo. La zona de raíces sale algo más seca que la superficie, como corresponde en una campaña seca.

## Criterios de aceptación

- [x] Lee las dimensiones del `.dmr` y arma el recorte con 2 celdas en la última dimensión (tests `test_esquema_lee_dimensiones`, `test_expresion_pide_dos_celdas_en_la_ultima_dimension`).
- [x] La zona de raíces es el promedio ponderado por espesor de las 3 capas (test `test_zona_raiz_es_el_promedio_ponderado_por_espesor`).
- [x] Relleno o capa faltante no inventan dato (tests `test_relleno_es_sin_dato`, `test_capa_faltante_se_descarta_sin_inventar`).
- [x] Fuera del rango físico es `dudosa` con aviso (test `test_fuera_de_rango_es_dudoso`).
- [x] De punta a punta devuelve las dos variables en m³/m³ y pide el píxel del lote; dos meses dan dos observaciones por variable (tests `test_humedad_de_punta_a_punta`, `test_dos_meses_dan_dos_observaciones_por_variable`).
- [x] Si la NASA no publicó el mes, avisa para que siga el pipeline (test `test_sin_meses_publicados_avisa_para_el_siguiente_respaldo`).
- [x] Pedido inválido no llama a la NASA; sin credenciales las pide (tests `test_pedido_invalido_no_llama_a_la_nasa`, `test_sin_credenciales_pide_credenciales`).
- [x] Se anuncia como respaldo de SMAP con orden 4 (test `test_se_anuncia_como_respaldo_de_smap`).
- [x] No importa a ningún otro satélite y el núcleo no lo nombra (test `test_nucleo.py`).
- [x] Prueba real sobre el lote de San Luis (PR #52, workflow en verde): humedad superficial del orden de 0,2 m³/m³ (feb 2026 = 0,234), cerca de GLDAS (~0,267) y SMAP. Valores por mes en "Resultado de la prueba real".
