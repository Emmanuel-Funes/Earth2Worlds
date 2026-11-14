# Spec 035 · Respaldo de heladas con MODIS LST nocturna

**Estado:** aprobada por Hernán ("Listo, sigamos con los que dijiste") y verificada con datos reales · **Etapa:** pipeline satélite → API → app · **Requiere:** credenciales de Earthdata (`EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD`, ya cargadas) · **Rama:** `MODIS-heladas_respaldo` · **Depende de:** (`NUCLEO-varios_respaldos_en_orden`)

## Objetivo

Darle un **respaldo** a la alerta de heladas (spec 030), que hoy depende de un solo satélite: VIIRS LST nocturna de NOAA-20/21. Si VIIRS no trae dato para el lote y las fechas (nubes, hueco de publicación), entra MODIS y la app igual puede avisar el riesgo de helada. Es exactamente el respaldo que la spec 030 dejó anotado ("MODIS MOD11A1 LST podría sumarse").

La fuente es **MODIS LST** nocturna de 1 km: MOD11A1 (Terra) y MYD11A1 (Aqua), de la NASA (colección 6.1). Mismo tipo de dato que VIIRS (temperatura de la **superficie** de noche), misma grilla sinusoidal de 1 km. Es respaldo y no principal porque MODIS está en fin de misión (Terra y Aqua se retiran).

## Fuente

| Producto | Agencia | Qué da | Grilla | Demora | Acceso |
|---|---|---|---|---|---|
| MOD11A1 (Terra) y MYD11A1 (Aqua), capa `LST_Night_1km` | NASA | Temperatura de la superficie de noche (~1:30 AM local), diaria | sinusoidal de 1 km | ~1 a 2 días | CMR + OPeNDAP de Earthdata (igual que VIIRS heladas) |

Con dos satélites hay hasta dos pasos por noche, y entra el más despejado.

## Entrada

El lote como lo recibe cualquier satélite: `lote["id"]`, `lote["poligono"]` (GeoJSON, EPSG:4326) y el período `desde`–`hasta` (máximo 366 días).

## Proceso

1. Validar el pedido (polígono y fechas, máximo 366 días). Un pedido inválido no llama a la NASA.
2. Ubicar el lote en la grilla sinusoidal de 1 km (mosaico `h`/`v` y ventana de píxeles con un píxel de margen), con la misma matemática que VIIRS de heladas (spec 030), repetida acá porque un satélite no importa a otro (spec 009).
3. Por cada satélite, pedir a CMR los archivos del mosaico en el período y leer por OPeNDAP (`.dmr` para la ruta de `LST_Night_1km`, `.dap.csv` para el recorte) solo la ventana del lote.
4. Para cada noche: pasar el crudo a °C (`crudo × 0,02 − 273,15`), quedarse con los píxeles válidos del lote y devolver la temperatura de superficie **mínima** (el punto más frío). Si Terra y Aqua cubren la misma noche, gana el que tiene más píxeles despejados.

## Salida (contrato común)

```json
{"lote_id": "lote-7", "fecha": "2026-09-22", "variable": "temp_sup_min_c", "valor": -3.0,
 "unidad": "°C", "fuente": "MODIS", "resolucion_m": 1000, "calidad": "buena",
 "nota": "Respaldo · MODIS LST nocturna (temperatura de superficie, no del aire) · MOD11A1 (Terra) · noche del 2026-09-22 · 1 píxeles de 1 km · válidos 100% · riesgo de helada (≤ 0 °C de superficie)"}
```

- `variable: "temp_sup_min_c"` es la misma de la spec 030; `fuente: "MODIS"` ya existe en el contrato.
- Cuando la temperatura de superficie es ≤ 0 °C, la `nota` agrega "riesgo de helada".

## Reglas de calidad

1. **Nunca inventar.** Píxel con nubes (crudo 0) o fuera del rango físico (150–400 K) no cuenta; si el lote queda con menos del 20 % de píxeles válidos, la noche es `descartada` con `valor: null`.
2. Calidad por nubosidad, igual que VIIRS (spec 030): válidos ≥ 60 % → `buena`, ≥ 20 % → `dudosa`, < 20 % → `descartada`.
3. **Supuesto agronómico (clave):** es la temperatura de la **superficie**, no la del aire a 1,5 m. De noche la superficie suele estar más fría que el aire, así que es alerta temprana, no la helada meteorológica oficial; el productor confirma. La `nota` lo aclara.
4. Supuesto: el lote suele ser más chico que un píxel de 1 km; en ese caso se usa el píxel que contiene su centro, y la `nota` lo dice.

## Dónde entra

- **Registro (spec 009):** `SATELITES = [Satelite("VIIRS_LST:MODIS", pedir, respaldo_de="VIIRS_LST", orden=1)]`. Es el **respaldo** de la señal de heladas (variable `temp_sup_min_c`), el primero y por ahora único.
- **Consulta en el momento (spec 012):** entra solo cuando VIIRS_LST no devuelve dato para el lote y las fechas.
- No toca el núcleo: `fuente "MODIS"` ya está en el contrato y no hace falta cambiar `base.py`.

## Prueba real

Workflow `Probar MODIS (heladas)` (`.github/workflows/probar-modis-heladas.yml`, `probar_modis_heladas.py`). Por defecto: lote de prueba de San Luis y del 15 al 30 de septiembre de 2026, la quincena con la helada del 22/9 que vieron la investigación 028 y la spec 030. Corre en cada PR que toque estos archivos y a mano con un clic. Necesita las credenciales de Earthdata (ya cargadas como secrets).

## Resultado de la prueba real

Workflow `Probar MODIS (heladas)`, lote de prueba (centro -33,7025; -65,2975), 16 noches de septiembre de 2026. 11 noches con dato `buena` y 5 `descartada` por nubes (MODIS no ve a través de nubes, como VIIRS). Píxel de 1 km.

- **Noche más fría: 22/9/2026, 0,1 °C de superficie** (la misma noche que VIIRS marcó como la más fría).
- 0 noches con riesgo de helada según el umbral de ≤ 0 °C de superficie.
- Algunas noches con dato: 24/9 7,2 °C · 25/9 10,3 °C · 26/9 11,2 °C · 27/9 17,8 °C.

**Ojo con la comparación VIIRS vs MODIS:** VIIRS marcó esa misma noche del 22/9 en **−3,0 °C** y MODIS la lee en **+0,1 °C**. Coinciden en *cuál* es la noche más fría, pero no en el número: son dos sensores con horas de paso distintas (VIIRS ~01:30; Terra ~22:30 y Aqua ~01:30) y, sobre todo, **LST es temperatura de la superficie, no del aire** — puede estar varios grados por debajo o por encima del aire a 1,5 m. Por eso este respaldo sirve para *ordenar* las noches frías y dar una señal de alerta, no para afirmar un valor exacto de helada; la decisión agronómica fina necesita temperatura del aire.

## Criterios de aceptación

- [x] La celda del lote cae en la grilla sinusoidal de 1 km y las coordenadas de la ventana vuelven al mismo píxel (tests `test_celda_del_lote_en_la_grilla_de_1km`, `test_coordenadas_vuelven_al_mismo_pixel`).
- [x] La ruta de `LST_Night_1km` sale de los metadatos y, si falta, avisa (tests `test_ruta_lst_sale_de_los_metadatos`, `test_metadatos_sin_lst_avisan`).
- [x] Una noche limpia da °C con calidad `buena`; a ≤ 0 °C agrega "riesgo de helada" (tests `test_noche_limpia_es_buena_y_devuelve_celsius`, `test_helada_lleva_el_aviso_en_la_nota`).
- [x] Nubes (crudo 0) o valor fuera de rango no inventan: `descartada` con `valor: null` (tests `test_nubes_crudo_cero_descartan_sin_inventar`, `test_valor_fuera_del_rango_fisico_no_cuenta`).
- [x] Toma el píxel más frío del lote, y si el lote es menor a un píxel usa el del centro (tests `test_toma_el_pixel_mas_frio_del_lote`, `test_lote_menor_a_un_pixel_usa_el_del_centro`).
- [x] Terra y Aqua se juntan y por noche gana el más limpio; un satélite sin colección no frena al otro (tests `test_obtener_heladas_junta_terra_y_aqua`, `test_mismo_dia_gana_la_noche_mas_limpia`, `test_un_satelite_sin_coleccion_no_frena_al_otro`).
- [x] Se anuncia como respaldo de VIIRS_LST con orden 1 (test `test_se_anuncia_como_respaldo_de_viirs_lst`).
- [x] No importa a ningún otro satélite y el núcleo no lo nombra (test `test_nucleo.py`).
- [x] Prueba real sobre el lote de San Luis (PR #51, workflow en verde): la noche más fría es el **22/9**, la misma que marcó VIIRS. El valor difiere (MODIS 0,1 °C vs VIIRS −3,0 °C) porque son sensores distintos y LST no es temperatura del aire; ver "Resultado de la prueba real".
