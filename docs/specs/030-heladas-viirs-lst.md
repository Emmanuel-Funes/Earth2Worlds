# Spec 030 · Alerta de heladas con VIIRS LST nocturna

**Estado:** propuesta (investigación 028, aprobada por Hernán: "Si, arranca con el tema de las heladas") · **Etapa:** pipeline satélite → API → app · **Requiere:** credenciales de Earthdata (`EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD`, ya cargadas) · **Rama:** `VIIRS-heladas` · **Depende de:** (`NUCLEO-varios_respaldos_en_orden`)

## Objetivo

Dar una señal de **riesgo de helada** en el lote: la temperatura de la **superficie** durante la noche, que es cuando hiela. Es un dato nuevo que hoy el pipeline no tiene (clima, NDVI, lluvia, humedad, relieve, ET y suelo, pero no temperatura nocturna del suelo). La helada define ventanas de siembra y puede arruinar un cultivo, así que es de las señales más útiles para la rotación.

La fuente es **VIIRS LST** (Land Surface Temperature) nocturna de 1 km, de NOAA (agencia socia permitida, spec 008), la misma familia de satélites que ya usamos para el NDVI de respaldo (spec 011). Se verificó en la investigación 028: la noche del 22/9/2026 en el lote de San Luis dio **−3,0 °C** de superficie.

## Fuente

| Producto | Agencia | Qué da | Grilla | Demora | Acceso |
|---|---|---|---|---|---|
| VJ121A1N (NOAA-20) y VJ221A1N (NOAA-21), capa `LST_1KM` del paso nocturno | NOAA / NASA | Temperatura de la superficie de noche (~1:30 AM local), diaria | sinusoidal de 1 km | ~1 a 2 días | CMR + OPeNDAP de Earthdata (igual que VIIRS NDVI) |

Suomi NPP (VNP21A1N) queda afuera: deja de entregar datos el 1/11/2026. Con dos satélites hay hasta dos pasos por noche, y entra el más despejado.

## Entrada

El lote como lo recibe cualquier satélite: `lote["id"]`, `lote["poligono"]` (GeoJSON, EPSG:4326) y el período `desde`–`hasta` (máximo 366 días).

## Proceso

1. Validar el pedido (polígono y fechas, máximo 366 días). Un pedido inválido no llama a la NASA.
2. Ubicar el lote en la grilla sinusoidal de 1 km (mosaico `h`/`v` y ventana de píxeles con un píxel de margen), con la misma matemática que el VIIRS de NDVI (spec 011), repetida acá porque un satélite no importa a otro (spec 009).
3. Por cada satélite, pedir a CMR los archivos del mosaico en el período y leer por OPeNDAP (`.dmr` para la ruta de `LST_1KM`, `.dap.csv` para el recorte) solo la ventana del lote.
4. Para cada noche: pasar el crudo a °C (`crudo × 0,02 − 273,15`), quedarse con los píxeles válidos del lote y devolver la temperatura de superficie **mínima** (la del punto más frío, que es donde primero hiela). Si dos satélites cubren la misma noche, gana el que tiene más píxeles despejados.

## Salida (contrato común)

```json
{"lote_id": "lote-7", "fecha": "2026-09-22", "variable": "temp_sup_min_c", "valor": -3.0,
 "unidad": "°C", "fuente": "VIIRS", "resolucion_m": 1000, "calidad": "buena",
 "nota": "VIIRS LST nocturna (temperatura de superficie, no del aire) · VJ121A1N (NOAA-20) · noche del 2026-09-22 · 1 píxeles de 1 km · válidos 100% · riesgo de helada (≤ 0 °C de superficie)"}
```

- `variable: "temp_sup_min_c"` es nueva (temperatura de superficie mínima nocturna, en °C). No cambia el contrato: `variable` es texto libre y `fuente: "VIIRS"` ya existe.
- Cuando la temperatura de superficie es ≤ 0 °C, la `nota` agrega "riesgo de helada".

## Reglas de calidad

1. **Nunca inventar.** Píxel con nubes (crudo 0) o fuera del rango físico (150–400 K) no cuenta; si el lote queda con menos del 20 % de píxeles válidos, la noche es `descartada` con `valor: null`.
2. Calidad por nubosidad, igual que NDVI (spec 011): válidos ≥ 60 % → `buena`, ≥ 20 % → `dudosa`, < 20 % → `descartada`.
3. **Supuesto agronómico (clave):** es la temperatura de la **superficie**, no la del aire a 1,5 m que miden los pluviómetros. De noche la superficie suele estar más fría que el aire, así que es una alerta temprana, no la helada meteorológica oficial; el productor confirma. La `nota` lo aclara.
4. Supuesto: el lote suele ser más chico que un píxel de 1 km; en ese caso se usa el píxel que contiene su centro, y la `nota` lo dice.

## Dónde entra

- **Registro (spec 009):** `SATELITES = [Satelite("VIIRS_LST", pedir)]`. Es una **fuente propia** de la variable `temp_sup_min_c`, no el respaldo de nadie. Todavía sin respaldo (MODIS MOD11A1 LST podría sumarse cuando MODIS siga vivo; la investigación 028 lo deja anotado).
- **Consulta en el momento (spec 012) y actualización nocturna (spec 004):** al ser la única fuente de su variable, se pide siempre que se pida esa variable; no compite con otras en `combinar`.
- No toca el núcleo: `fuente "VIIRS"` ya está en el contrato y no hace falta cambiar `base.py` (una sola fuente para la variable).

## Prueba real

Workflow `Probar VIIRS (heladas)` (`.github/workflows/probar-viirs-heladas.yml`, `probar_viirs_heladas.py`). Por defecto: lote de prueba de San Luis y del 15 al 30 de septiembre de 2026, la quincena con la helada del 22/9 que vio la investigación 028. Corre en cada PR que toque estos archivos y a mano con un clic. Necesita las credenciales de Earthdata (ya cargadas como secrets).

## Resultado de la prueba real

Workflow `Probar VIIRS (heladas)`, lote de prueba (centro -33,7025; -65,2975), del 15 al 30 de septiembre de 2026, respuesta en 16 s:

| Noche | 15/9 | 16/9 | 19/9 | 21/9 | **22/9** | 23/9 | 24/9 | 25/9 | 26/9 | 27/9 |
|---|---|---|---|---|---|---|---|---|---|---|
| T sup °C | 2,6 | 5,2 | 11,0 | 7,9 | **−3,0** | 10,3 | 7,7 | 8,4 | 10,3 | 17,0 |

De 16 noches, **10 con dato** y 6 descartadas por nubes. La **noche más fría fue el 22/9 con −3,0 °C**, marcada con "riesgo de helada" — el mismo valor que vio la investigación 028. NOAA-21 (VJ221A1N) también respondió (trajo el 23/9), así que los dos satélites resuelven. Variable `temp_sup_min_c` en °C, fuente `VIIRS`, 1000 m. La capa real está en el grupo `VIIRS_Grid_Daily_1km_LST21/Data_Fields/LST_1KM` (el buscador de la ruta la encontró igual).

## Criterios de aceptación

- [x] La celda del lote en la grilla de 1 km es la mitad que la del VIIRS de NDVI de 500 m, y las coordenadas de la ventana vuelven al mismo píxel (tests `test_celda_del_lote_es_la_mitad_que_en_viirs_ndvi`, `test_coordenadas_vuelven_al_mismo_pixel`).
- [x] La ruta de `LST_1KM` sale de los metadatos y, si falta, avisa (tests `test_ruta_lst_sale_de_los_metadatos`, `test_metadatos_sin_lst_avisan`).
- [x] Una noche despejada da la temperatura de superficie mínima en °C, `buena`; una helada agrega el aviso en la nota; nubes (crudo 0) y valores fuera de rango no se inventan (tests `test_noche_limpia_es_buena_y_devuelve_celsius`, `test_helada_lleva_el_aviso_en_la_nota`, `test_nubes_crudo_cero_descartan_sin_inventar`, `test_valor_fuera_del_rango_fisico_no_cuenta`).
- [x] Se toma el píxel más frío del lote; un lote menor a un píxel usa el del centro (tests `test_toma_el_pixel_mas_frio_del_lote`, `test_lote_menor_a_un_pixel_usa_el_del_centro`).
- [x] Junta NOAA-20 y NOAA-21, por noche gana el más despejado, y un satélite sin colección no frena al otro; un pedido inválido no llama a la NASA; sin credenciales pide credenciales (tests `test_obtener_heladas_junta_noaa20_y_noaa21`, `test_mismo_dia_gana_la_noche_mas_limpia`, `test_un_satelite_sin_coleccion_no_frena_al_otro`, `test_pedido_invalido_no_llama_a_la_nasa`, `test_sin_credenciales_pide_credenciales`).
- [x] Se anuncia como `VIIRS_LST`, fuente propia (sin `respaldo_de`), y no importa ningún otro satélite (`test_se_anuncia_como_fuente_propia_sin_respaldo` y `tests/test_nucleo.py`).
- [x] Tests sin internet verdes (63 pasan en local, incluidos los de heladas).
- [x] Prueba real con un clic y automática en cada PR que toque el conector (`Probar VIIRS (heladas)` en verde): 10 de 16 noches con dato, la más fría el 22/9 con −3,0 °C (riesgo de helada), en 16 s, con NOAA-20 y NOAA-21 resolviendo.

## Fuera de alcance

Convertir la temperatura de superficie a temperatura del aire. Un respaldo de esta variable (MODIS MOD11A1). Avisar la helada por fuera de la app.
