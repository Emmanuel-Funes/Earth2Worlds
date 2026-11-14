# Spec 032 · Respaldo de humedad del suelo y ET con GLDAS de la NASA

**Estado:** propuesta (investigación 028, aprobada por Hernán: "Bueno, sigamos con el proyecto, acepto lo que decías") · **Etapa:** pipeline satélite → API → app · **Requiere:** credenciales de Earthdata (`EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD`, ya cargadas) · **Rama:** `GLDAS-humedad_y_ET_respaldo` · **Depende de:** (`NUCLEO-varios_respaldos_en_orden`)

## Objetivo

Darle un respaldo más a dos datos que hoy dependen de misiones con riesgo presupuestario para 2027:

1. **Humedad del suelo**, hoy SMAP (L4 directo → AppEEARS → L3). GLDAS entra como respaldo final.
2. **Evapotranspiración real (ET)**, hoy MODIS → ECOSTRESS → ET0 FAO-56. GLDAS entra después de ECOSTRESS. Cuando MODIS se apague (fines de 2026 / principios de 2027), ECOSTRESS pasa a principal y GLDAS da continuidad.

La fuente es **GLDAS Noah 0.25°** (`GLDAS_NOAH025_3H`, con su producto temprano `_EP` para los días recientes), un modelo de superficie de la NASA (GES DISC) que combina satélite y estaciones. Da humedad del suelo por capas (0–10, 10–40, 40–100 y 100–200 cm) y ET, cada 3 horas, en una grilla de ~25 km, con ~1 mes de atraso. Es la **única** fuente del pipeline con humedad hasta 2 m, como nuestro balance hídrico (spec 024). Se verificó en la investigación 028: septiembre de 2026 en el lote dio ET de 0,09 a 0,41 mm/día (lote en reposo invernal).

Es un **respaldo**, no una fuente nueva: entrega las mismas variables que SMAP y que la ET, con menor prioridad.

## Fuente

| Producto | Agencia | Qué da | Grilla | Demora | Acceso |
|---|---|---|---|---|---|
| `GLDAS_NOAH025_3H` (+ `GLDAS_NOAH025_3H_EP` para lo reciente), variables `SoilMoi0_10cm_inst`, `RootMoist_inst`, `Evap_tavg` | NASA (GES DISC) | Humedad del suelo y ET, cada 3 h | 0,25° (~25 km) | ~1 mes | CMR + OPeNDAP de la NASA, solo el píxel del lote |

Se lee por OPeNDAP (`.dmr` para los metadatos, `.dap.csv` para el recorte), solo el píxel que contiene el centro del lote, igual que GRACE (spec 026). Los 8 pasos de 3 h de cada día se promedian a un valor diario.

## Entrada

El lote como lo reciben los satélites: `lote["id"]`, su centro (`lat`/`lon`) y el período `desde`–`hasta` (máximo 92 días, para acotar la cantidad de archivos).

## Proceso

1. Validar el pedido (lat/lon y fechas, máximo 92 días). Un pedido inválido no llama a la NASA.
2. Pedir a CMR los archivos de 3 h del período, del producto final y del temprano (`_EP`); si un paso está en los dos, gana el final.
3. Por cada archivo, leer por OPeNDAP solo el píxel del centro del lote.
4. Agrupar los pasos por día y promediar:
   - **Humedad superficial** (`humedad_superficial`): `SoilMoi0_10cm_inst` (kg/m² en 100 mm) ÷ 100 → m³/m³.
   - **Humedad de la zona de raíces** (`humedad_zona_raiz`): `RootMoist_inst` (kg/m² en ~1 m) ÷ 1000 → m³/m³.
   - **ET real** (`et_mm_dia`): `Evap_tavg` (kg/m²/s) × 86400 → mm/día.
5. Un día con los 8 pasos y dentro del rango físico es `buena`; con menos pasos o fuera de rango, `dudosa`; sin ningún paso, `descartada` con `valor: null`.

## Salida (contrato común)

```json
{"lote_id": "lote-7", "fecha": "2026-09-22", "variable": "et_mm_dia", "valor": 0.3,
 "unidad": "mm/día", "fuente": "GLDAS", "resolucion_m": 25000, "calidad": "buena",
 "nota": "Respaldo · ET del modelo GLDAS Noah de la NASA (GES DISC), promedio de 8 pasos de 3 h · píxel de 0,25° (~25 km), dato REGIONAL de modelo, no una medición del lote"}
```

- Las variables y unidades son las mismas que SMAP (`humedad_superficial`, `humedad_zona_raiz`, m³/m³) y la ET (`et_mm_dia`, mm/día), para que el núcleo lo trate como respaldo.
- `fuente: "GLDAS"` es nueva en el contrato. En `base.py` se le da prioridad 5 para la humedad (por debajo de SMAP, que es 1) y 3 para `et_mm_dia` (después de ECOSTRESS, que es 2).

## Reglas de calidad

1. **Nunca inventar.** Píxel sin dato, relleno o fuera de rango físico (humedad fuera de 0–1 m³/m³, ET fuera de 0–20 mm/día) → `descartada` con `valor: null`, y la nota dice por qué.
2. **Dato REGIONAL:** el píxel de 25 km cubre miles de hectáreas; es un respaldo regional, no una medición del lote. La nota lo aclara siempre.
3. GLDAS llega con ~1 mes de atraso; los días que la NASA todavía no publicó quedan sin dato (no se inventan).

## Dónde entra

- **Registro (spec 009):** dos entradas en `SATELITES`:
  - `Satelite("SMAP:GLDAS", pedir_humedad, respaldo_de="SMAP", orden=3)` — respaldo final de humedad.
  - `Satelite("ET:GLDAS", pedir_et, respaldo_de="ET", orden=3)` — respaldo de ET, después de ECOSTRESS.
- **Consulta en el momento (spec 012):** GLDAS responde solo si el principal y los respaldos anteriores fallan o no traen datos.
- **Núcleo:** `"GLDAS"` en el contrato y, en `base.py`, `"GLDAS": 5` en `PRIORIDAD` y `"GLDAS": 3` en `PRIORIDAD_POR_VARIABLE["et_mm_dia"]` (único cambio de núcleo permitido por la Guía, punto 9). No toca otro archivo del núcleo ni a otro satélite.

## Prueba real

Workflow `Probar GLDAS (humedad y ET)` (`.github/workflows/probar-gldas.yml`, `probar_gldas.py`). Por defecto, el lote de prueba de San Luis, con un período automático que se cuenta desde el día en que corre. Corre en cada PR que toque estos archivos y a mano con un clic. Necesita las credenciales de Earthdata (ya cargadas como secrets).

## Resultado de la prueba real

Workflow `Probar GLDAS (humedad y ET)`, lote de prueba (centro −33,7025; −65,2975), del 15 al 21 de septiembre de 2026, respuesta en 8 s cada una, píxel de 0,25° (~25 km):

| Fecha | humedad_superficial | humedad_zona_raiz | et_mm_dia |
|---|---|---|---|
| 15/9 | 0,267 m³/m³ (buena) | 0,265 m³/m³ (buena) | 1,52 mm/día (buena) |
| 16/9 | 0,255 m³/m³ (buena) | 0,263 m³/m³ (buena) | 1,76 mm/día (buena) |
| 17–21/9 | — (descartada) | — (descartada) | — (descartada) |

De los 7 días, los 2 primeros (15 y 16/9) tienen dato completo (8 pasos de 3 h, calidad `buena`); del 17/9 en adelante la NASA todavía no había publicado al 14/10 (el atraso de ~1 mes), así que quedan `descartada` con `valor: null`, sin inventar. Las conversiones de unidad quedaron bien: humedad ~0,26 m³/m³ (suelo arenoso con algo de humedad) y ET de 1,5 a 1,8 mm/día (primavera temprana). **Nota:** la ET es más alta que el rango que había anotado la investigación 028 para septiembre (0,09–0,41 mm/día); la diferencia es por las fechas y el producto exactos, y 1,5–1,8 mm/día es un valor físicamente razonable para esos días; conviene que el productor/Leandro lo contraste.

## Criterios de aceptación

- [x] El píxel del lote en la grilla de 0,25° se ubica por lat/lon y vuelve el valor correcto (tests con OPeNDAP simulado; prueba real: fila 105, columna 458).
- [x] Los 8 pasos de 3 h de un día se promedian; `SoilMoi0_10cm_inst` ÷ 100 y `RootMoist_inst` ÷ 1000 dan m³/m³, y `Evap_tavg` × 86400 da mm/día (tests `test_humedad_convierte_a_m3_m3`, `test_dia_completo_es_buena_y_convierte_la_unidad` y prueba real).
- [x] Un día completo dentro de rango es `buena`; con pocos pasos o fuera de rango, `dudosa`; sin pasos, `descartada` sin inventar (tests y prueba real: 15–16/9 `buena`, 17–21/9 `descartada`).
- [x] El producto final gana sobre el temprano (`_EP`) cuando los dos tienen el mismo paso (`test_el_producto_final_pisa_al_temprano`).
- [x] Se anuncia como `SMAP:GLDAS` (respaldo de SMAP) y `ET:GLDAS` (respaldo de ET), y no importa ningún otro satélite (`test_se_anuncia_como_respaldo_de_smap_y_de_et`, `tests/test_nucleo.py`).
- [x] Un pedido inválido no llama a la NASA; sin credenciales pide credenciales (`test_pedido_invalido_no_llama_a_la_nasa`, `test_sin_credenciales_pide_credenciales`).
- [x] Tests sin internet verdes (60 en total, incluidos los de GLDAS).
- [x] Prueba real con un clic y automática en cada PR que toque el conector (`Probar GLDAS (humedad y ET)` en verde): humedad y ET con dato en 15–16/9, en 8 s.

## Fuera de alcance

- La humedad de 100–200 cm como variable propia (GLDAS es el único que la tiene; se deja anotada para sumarla al balance hídrico en una etapa posterior).
- La ET potencial de GLDAS (`PotEvap_tavg`): la ET potencial ya la da MODIS (`pet_mm_dia`).
