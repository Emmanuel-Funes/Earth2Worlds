# Spec 017 · Evapotranspiración real del lote (fuente principal de ET)

**Estado:** aprobada por Hernán el 4/10/2026 ("Sumar lo necesario para cubrir lo que hace falta") · **Etapa:** pipeline satélite → API → app · **Requiere:** cuenta NASA Earthdata · **Rama:** `MODIS-evapotranspiracion`

## Objetivo

Saber **cuánta agua pierde el lote** por evaporación del suelo y transpiración del cultivo (evapotranspiración real, ET), y cuánta perdería si no le faltara agua (evapotranspiración potencial, PET). La diferencia entre las dos muestra el **estrés hídrico**: si la ET real queda muy por debajo de la potencial, el cultivo está pasando sed. Era lo que faltaba del plan original (README: "Evapotranspiración y estrés hídrico · Pendiente").

## Fuente (NASA)

Producto de evapotranspiración de 500 m y 8 días de la NASA (LP DAAC), algoritmo MOD16 (Penman-Monteith), en la grilla sinusoidal de MODIS.

**Elección con datos reales de CMR (prueba del 4/10/2026, mosaico h12v12, enero de 2026):**

| Producto | Satélite | En CMR | OPeNDAP | Último archivo publicado |
|---|---|---|---|---|
| `VJ116A2` | VIIRS en NOAA-20 | **no está** | — | — |
| `VJ216A2` | VIIRS en NOAA-21 | **no está** | — | — |
| `VNP16A2` | VIIRS en Suomi NPP | **no está** | — | — |
| `MOD16A2` v061 (`C2343113232-LPCLOUD`) | MODIS en Terra | sí | sí (4 de 4 archivos de enero) | `A2026257` (14/9/2026) |
| `MYD16A2` v061 (`C2565794064-LPCLOUD`) | MODIS en Aqua | sí | sí (4 de 4 archivos de enero) | `A2026257` (14/9/2026) |
| `MOD16A2GF` v061 | Terra, *gap-filled* anual | sí | — (0 archivos de 2026) | `A2025361`: sale una vez por año, después de que el año termina |

La NASA **todavía no publica la ET de VIIRS**, así que la fuente principal queda en **MODIS** y el conector lee, en este orden:

| Orden | Producto | `fuente` | Para qué |
|---|---|---|---|
| 1 | `MOD16A2` | `MODIS` | principal (Terra) |
| 2 | `MYD16A2` | `MODIS` | mismo producto desde Aqua, para los compuestos que Terra no trae |
| 3 | `VJ116A2` | `VIIRS` | continuidad: si la NASA lo publica, completa lo que MODIS ya no traiga, sin tocar el código |

Los tres usan el mismo calendario de compuestos (días 1, 9, 17, … de cada año), así que **para cada compuesto** se usa el primer producto de la lista que traiga un valor válido; los siguientes solo se consultan para los compuestos que siguen sin dato. La `fuente` de cada observación es la real.

**Riesgo:** Terra y Aqua están en fin de misión. Cuando dejen de publicar, el conector da error (no hay archivos) y entran sus respaldos (`ET:ECOSTRESS`, `ET:FAO56`), hasta que la NASA publique `VJ116A2`.

## Entrada

- Polígono del lote en GeoJSON (EPSG:4326).
- Rango de fechas `desde` – `hasta` (máximo 366 días).

## Proceso

Igual que el NDVI de VIIRS (spec 011):

1. Calcular el mosaico (h, v) de la grilla sinusoidal (2400 × 2400 píxeles de ~463 m) y la ventana de píxeles que cubre el lote, con un píxel de margen.
2. Buscar en CMR los compuestos de 8 días que tocan el período y el mosaico del lote.
3. Leer por OPeNDAP (`earthdata.leer_csv`) solo esa ventana de tres capas: **ET**, **PET** y su control de calidad. Los nombres exactos, la escala (`scale_factor`) y el rango válido (`valid_range`) se leen de los metadatos del archivo (`.dmr`). En MOD16A2 v061 son `/MOD_Grid_MOD16A2/Data_Fields/ET_500m`, `PET_500m` y `ET_QC_500m`, con escala 0,1 y máximo válido 32700 (verificado).
4. Tomar los píxeles cuyo centro cae dentro del lote. Si ninguno cae adentro (lote de menos de ~21 ha), usar el que contiene el centro y aclararlo en la `nota`.
5. Píxel válido = valor dentro del rango válido del producto. Los códigos de relleno (≥ 32761) se descartan y la `nota` dice qué significan:
   32761 sin clasificar · 32762 urbano · 32763 humedal permanente · 32764 nieve o hielo permanente · 32765 suelo desnudo · 32766 agua · 32767 sin dato.
6. Valor del lote = **promedio** de los píxeles válidos × escala (0,1 kg/m² = 0,1 mm), dividido por los días del compuesto.
7. Días del compuesto = 8, salvo el último del año, que va del día 361 al 31 de diciembre (5 días, o 6 en año bisiesto). La capa es la *suma* del período del compuesto (guía de usuario de MOD16).

**Supuestos** (se aclaran en la `nota`):
- Escala 0,1 y rango válido hasta 32700 si el archivo no trae `scale_factor` o `valid_range`.
- Control de calidad como en MOD15 (FPAR/LAI): bits 5-7 = algoritmo usado. 0 o 1 = algoritmo principal; 2 o 3 = algoritmo de respaldo (nubes o geometría).

## Salida (contrato común)

Dos observaciones por compuesto, con nombres fijos (los usan los respaldos ECOSTRESS y FAO-56):

```json
{"lote_id": "lote-7", "fecha": "2026-01-01", "variable": "et_mm_dia", "valor": 1.26,
 "unidad": "mm/día", "fuente": "MODIS", "resolucion_m": 500, "calidad": "buena",
 "nota": "MOD16A2 (MODIS Terra) · fecha = inicio del compuesto de 8 días (2026-01-01 al 2026-01-08) · promedio diario = suma 10.1 mm / 8 días · 1 píxeles de 500 m · válidos 100% · algoritmo principal 100% · escala 0.1"}
{"lote_id": "lote-7", "fecha": "2026-01-01", "variable": "pet_mm_dia", "valor": 8.14, "unidad": "mm/día", ...}
```

- `et_mm_dia`: evapotranspiración real, promedio diario del compuesto (suma ÷ días).
- `pet_mm_dia`: evapotranspiración potencial, igual.
- `fecha`: **inicio** del compuesto de 8 días (se aclara en la `nota`). Se devuelven los compuestos que se superponen con el período pedido, así que el primero puede empezar hasta 7 días antes de `desde`.
- Calidad: `descartada` si menos del 20 % de los píxeles del lote es válido (valor `null`, la nota dice por qué); `buena` si al menos el 60 % es válido y la mayoría salió del algoritmo principal; si no, `dudosa`. Mismos umbrales que el NDVI.
- Nunca se inventa un valor.

## Errores

- Si CMR no tiene ningún compuesto con OPeNDAP para el lote y el período, o si **ningún** compuesto trae un valor válido (por ejemplo, el píxel es urbano o agua), el conector da error. Así el núcleo pasa a los respaldos en orden: `ET:ECOSTRESS` (orden 1) y `ET:FAO56` (orden 2).
- Sin credenciales de Earthdata: error claro, sin mostrar ningún secreto.

## Dónde entra

- Satélite independiente (spec 009): `rotaterra/fuentes/et.py`, registrado como `Satelite("ET", pedir)` (principal). No importa ningún otro satélite.
- Endpoint de prueba `POST /evapotranspiracion` (spec 010): la app lo llama y espera la respuesta (segundos).
- Prueba real: workflow "Probar MODIS (evapotranspiración)" (`.github/workflows/probar-et.yml`, `probar_et.py`), lote de ejemplo de San Luis y enero de 2026. Además de los valores, imprime qué productos de ET encuentra CMR, con OPeNDAP o sin él, y busca por palabra clave si la NASA ya publicó la ET de VIIRS.

## Criterios de aceptación

- [x] Con el lote de prueba real (San Luis, enero de 2026) se obtiene la ET real y potencial por compuesto de 8 días y se anotan los números. *(1 al 31 de enero de 2026, en 4 segundos, todo de `MOD16A2` Terra, 1 píxel de 500 m, 100 % válido y algoritmo principal, calidad buena. ET real: 1,26 (1/1), 1,90 (9/1), 2,71 (17/1) y 3,55 mm/día (25/1). PET: 8,14, 7,68, 7,99 y 6,58 mm/día.)*
- [x] Los valores son razonables para un cultivo de verano en San Luis (ET real de 1 a 7 mm/día; PET mayor o igual que ET). *(ET real entre 1,26 y 3,55 mm/día, en subida a lo largo de enero, como el NDVI del mismo lote (0,39 → 0,66 en VIIRS); PET entre 6,58 y 8,14, siempre mayor que la ET real: el lote arrancó enero con fuerte demanda de agua sin cubrir (ET/PET 0,15) y la brecha se achicó a fin de mes (0,54).)*
- [x] Se verifica en CMR qué producto existe con OPeNDAP y se deja anotado cuál quedó como principal. *(Tabla de arriba: VIIRS no está publicado; principal `MOD16A2` v061, alternativa `MYD16A2` v061.)*
- [x] Los códigos de relleno y los compuestos sin dato quedan `descartada` con `valor: null` y el motivo (tests `test_relleno_se_descarta_y_dice_por_que`, `test_sin_dato_se_descarta`, `test_compuesto_sin_dato_en_ningun_producto_queda_descartado`).
- [x] Si no hay ningún dato, el conector da error para que entren los respaldos (tests `test_sin_archivos_es_error_para_que_entren_los_respaldos` y `test_todo_relleno_es_error_para_que_entren_los_respaldos`).
- [x] El conector no importa código de ningún otro satélite (`tests/test_nucleo.py` en verde).
- [x] Tests sin internet en `tests/test_et.py`; prueba real "Probar MODIS (evapotranspiración)" verde en el PR. *(24 tests en `tests/test_et.py`, 68 en total en local; en el PR #35, `tests`, `tests-postgres` y "Probar MODIS (evapotranspiración)" en verde. La búsqueda por palabra clave en CMR confirmó que de VIIRS solo hay productividad (`VJ117A2`, `VNP17A2`), no evapotranspiración.)*

## Fuera de alcance

Calor latente (LE, PLE), versiones *gap-filled* anuales, ET de 70 m de ECOSTRESS (otro conector, respaldo de este) y el cálculo FAO-56 (otro conector).
