# Spec 013 · Lluvia de respaldo con NASA POWER (cuando IMERG falla)

**Estado:** aprobada por Hernán ("Sumar lo necesario para cubrir lo que hace falta") · **Etapa:** pipeline satélite → API → app · **Requiere:** nada (API pública de la NASA, sin cuenta) · **Rama:** `POWER-lluvia_respaldo` · **Depende de:** (`NUCLEO-varios_respaldos_en_orden`)

## Objetivo

Que la lluvia del lote siga llegando de la NASA cuando **GPM IMERG** (spec 006), la fuente principal de `lluvia_mm`, falla: Earthdata caído, credenciales vencidas, OPeNDAP de GES DISC sin responder. Hoy IMERG no tiene respaldo automático propio: si falla, la consulta en el momento (spec 012) y la actualización nocturna (spec 004) se quedan sin lluvia.

El respaldo es **NASA POWER**, que da la lluvia diaria corregida (`PRECTOTCORR`) para cualquier punto, sin credenciales y desde otro centro de la NASA (Langley), así que no comparte las causas de falla de IMERG.

## Fuente

| Producto | Agencia | Qué da | Grilla | Demora | Acceso |
|---|---|---|---|---|---|
| NASA POWER, parámetro `PRECTOTCORR`, comunidad `AG` | NASA (Langley Research Center) | Lluvia diaria total corregida, en mm/día | 0,5° × 0,625° (~55 km) | ~2 a 7 días | `https://power.larc.nasa.gov/api/temporal/daily/point`, público, sin cuenta |

`PRECTOTCORR` es la lluvia de MERRA-2 corregida con observaciones (en los años recientes, con IMERG). Por eso es más gruesa que IMERG (celda de ~55 km contra ~10 km), pero es de la NASA y está siempre disponible.

## Entrada

El lote como lo recibe cualquier satélite: `lote["id"]`, `lote["lat"]`, `lote["lon"]` (centro del lote, EPSG:4326) y el período `desde`–`hasta` (máximo 366 días).

## Proceso

1. Validar el pedido (latitud, longitud, fechas, máximo 366 días). Un pedido inválido no llama a la NASA.
2. Un solo pedido a POWER: `parameters=PRECTOTCORR`, `community=AG`, el punto del centro del lote, `start`/`end` en `AAAAMMDD`, `format=JSON` y `time-standard=UTC` (el día UTC, igual que IMERG, para que las dos series se puedan comparar día por día).
3. Devolver **un valor por día pedido**, igual que IMERG. Un día que POWER no devuelve queda como descartado.

Es un pedido propio: no importa el conector `power.py` de la rama `POWER-clima` (spec 009, satélites independientes).

## Salida (contrato común)

```json
{"lote_id": "lote-7", "fecha": "2026-01-13", "variable": "lluvia_mm", "valor": 12.4,
 "unidad": "mm/día", "fuente": "POWER", "resolucion_m": 55000, "calidad": "buena",
 "nota": "Respaldo de IMERG · NASA POWER (MERRA-2/IMERG corregido) · celda de 0,5°"}
```

- `variable` y `unidad` son **las mismas que IMERG** (`lluvia_mm`, `mm/día`), así la app recibe la misma serie venga de donde venga.
- `fuente: "POWER"` y `resolucion_m: 55000` dicen que es un dato regional, no del lote.

## Reglas de calidad

1. **Nunca inventar.** Valor de relleno de POWER (`-999`) o día que POWER no devolvió → `valor: null`, `calidad: "descartada"`, y la `nota` dice por qué.
2. Rango físico 0 a 500 mm/día (el mismo que IMERG). Fuera de rango → `calidad: "dudosa"`, sin corregir el valor.
3. Supuesto: la lluvia de POWER es un promedio de una celda de ~55 km. En tormentas locales puede dar menos que IMERG en el día del chaparrón y algo de lluvia en días que el lote no tuvo. La `nota` lo aclara con "celda de 0,5°".

## Dónde entra

- **Registro (spec 009):** `SATELITES = [Satelite("IMERG:POWER", pedir, respaldo_de="IMERG")]`, único respaldo de IMERG (`orden=1`).
- **Consulta en el momento (spec 012) y actualización nocturna (spec 004):** si IMERG falla, queda pendiente o no trae nada, se pide el mismo período a este respaldo. Si IMERG anda, este respaldo **no se consulta**. Unido sin IMERG, queda en espera.
- **`combinar=true`:** para `lluvia_mm` gana IMERG donde tiene valor (`PREFERIDA` en `base.py`); POWER rellena solo donde IMERG falta. No hace falta tocar el núcleo.
- Si también se une `POWER-clima`, las dos guardan la misma lluvia de POWER con la misma clave (lote, fecha, variable, fuente): se reemplaza, no se duplica.
- No trae endpoint de prueba propio: la app pide la lluvia a IMERG y el núcleo pasa a este respaldo solo.

## Prueba real

Workflow `Probar POWER (lluvia de respaldo)` (`.github/workflows/probar-power-lluvia.yml`, `probar_power_lluvia.py`). Por defecto: lote de prueba de San Luis (esquinas `-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300`, centro -33,7025; -65,2975) y del 1 al 14 de enero de 2026, el mismo período en que IMERG dio **32,0 mm** en total, con **22,5 mm el 13/1**. Corre en cada PR que toque estos archivos y a mano con un clic.

## Resultado de la prueba real

Workflow `Probar POWER (lluvia de respaldo)`, lote de prueba (centro -33,7025; -65,2975), 1 al 14 de enero de 2026, día UTC (`time-standard=UTC` aceptado por POWER), respuesta en 0,4 s:

| Fecha | 1/1 | 2/1 | 3-5/1 | 6/1 | 7/1 | 8/1 | 9/1 | 10/1 | 11-12/1 | 13/1 | 14/1 | Total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| POWER (mm) | 0,13 | 0,01 | 0,00 | 0,46 | 0,12 | 6,41 | 1,94 | 0,18 | 0,00 | **4,29** | 0,07 | **13,6** |
| IMERG (mm, spec 006) | | | | | | | | | | **22,5** | | **32,0** |

**Comparación con IMERG:** POWER da **13,6 mm** en los 14 días contra **32,0 mm** de IMERG (42 %), y **4,3 mm el 13/1** contra **22,5 mm**. Ve la misma tormenta del 13/1 y la lluvia del 8-9/1, pero repartida en una celda de ~55 km: subestima los chaparrones locales y marca lloviznas de décimas en días secos. Sirve para no quedarse sin dato cuando IMERG falla, no para reemplazarlo; por eso entra solo como respaldo y `combinar=true` prefiere IMERG.

## Criterios de aceptación

- [x] Con el punto del lote de prueba se obtiene la lluvia de POWER por día, un valor por día pedido (1 al 14 de enero de 2026: 14 días, los 14 `buena`, `lluvia_mm` en `mm/día`, fuente `POWER`, 55000 m, en 0,4 s).
- [x] Comparación con IMERG en el mismo período anotada acá (POWER 13,6 mm contra IMERG 32,0 mm; 13/1: 4,3 contra 22,5 mm).
- [x] Relleno `-999` y días faltantes → `descartada` con `valor: null`; fuera de rango → `dudosa` (tests `test_relleno_menos_999_no_se_inventa`, `test_dia_que_power_no_devuelve_queda_descartado`, `test_fuera_de_rango_es_dudosa_sin_corregir`).
- [x] Se anuncia como `IMERG:POWER`, respaldo de IMERG, orden 1, y no importa ningún otro satélite (`test_se_anuncia_como_unico_respaldo_de_imerg` y `tests/test_nucleo.py`).
- [x] IMERG caído → entra este respaldo por el mismo período; IMERG OK → no se consulta; sin IMERG unido → queda en espera (tests con la actualización de la spec 004: `test_imerg_caido_entra_power_por_el_mismo_periodo`, `test_imerg_ok_no_consulta_el_respaldo`, `test_sin_imerg_unido_queda_en_espera`). La consulta en el momento (spec 012) usa la misma lista de respaldos y todavía no está en esta rama base.
- [x] Tests sin internet (64 pasan en local; `Tests` en verde); prueba real con un clic y automática en cada PR que toque el conector (`Probar POWER (lluvia de respaldo)` en verde).

## Fuera de alcance

Corregir POWER con pluviómetros del productor o del INTA. Un segundo respaldo de la lluvia.
