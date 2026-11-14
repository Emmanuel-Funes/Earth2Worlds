# Spec 058 · Clima futuro de la zona con NEX-GDDP-CMIP6

**Estado:** construida y probada con datos reales · **Aprobada por:** Hernán ("Vamos con la partes de satelites y obtencion de datos que es lo mio, avancemos", sobre los faltantes del desafío Field Shift) · **Rama:** `NEX_GDDP-clima_futuro_CMIP6` · **Depende de:** (`NUCLEO-varios_respaldos_en_orden`) · **Requiere:** nada (el servidor de la NASA es público)

## Objetivo

El desafío pide herramientas para **adaptar los campos a condiciones cambiantes** y nombra el estrés por calor y las lluvias extremas. Hoy Rotaterra mira solo el pasado (35 años de POWER). Esta fuente agrega **cómo viene el clima a 2041-2060** en la zona del lote, para probar cada rotación contra el clima que viene y no solo contra el que fue.

Es una **proyección de modelos, no un pronóstico**, y un dato **regional de ~25 km**.

## Fuente

| Producto | Agencia | Qué da | Grilla | Acceso |
|---|---|---|---|---|
| NEX-GDDP-CMIP6 | NASA (Ames, NEX; servido por el NCCS) | Máxima, mínima y lluvia diarias de los modelos CMIP6, corregidas por sesgo y bajadas de escala | 0,25° (~25 km), diario, 1950-2100 | THREDDS público del NCCS, servicio NCSS, un año y una variable por pedido, solo la celda del lote |

- **Modelos:** ACCESS-CM2, MPI-ESM1-2-HR y MRI-ESM2-0 (miembro r1i1p1f1). Cubren de un modelo cálido a uno templado.
- **Períodos:** línea de base 1995-2014 (`historical`) y 2041-2060 con dos escenarios: **SSP2-4.5** (emisiones intermedias) y **SSP5-8.5** (emisiones altas).
- **Archivo por año:** si hay varias versiones (`_v1.1`, `_v2.0`), se usa la más nueva.

## Entrada

`lote["id"]`, `lote["lat"]`, `lote["lon"]` (el centro del lote). No usa el período del pedido: es un dato fijo.

## Proceso

1. Ubicar la celda de 0,25° que contiene el centro del lote (para el lote de prueba: −33,625; −65,375).
2. Leer del catálogo del NCCS qué archivo corresponde a cada modelo, escenario, variable y año.
3. Pedir los **540 años-variable** (3 modelos × 3 variables × 60 años), de a 4 a la vez. Con 16 a la vez el servidor corta conexiones. Cada pedido se reintenta hasta 3 veces.
4. Por cada modelo y período, calcular los indicadores año por año y promediarlos.
5. Juntar los modelos: **mediana** como valor, y en la nota el valor de cada modelo y el **cambio contra 1995-2014 del mismo modelo**.
6. Guardar el resultado de la celda en memoria: los datos no cambian, así que la segunda consulta de la misma celda contesta al instante.

## Indicadores

| Variable | Unidad | Qué es |
|---|---|---|
| `dias_calor_35_<período>` | días/año | Días con máxima del aire ≥ 35 °C (estrés por calor en floración) |
| `tmax_verano_c_<período>` | °C | Máxima media de diciembre a febrero |
| `dias_helada_aire_<período>` | días/año | Días con mínima del aire ≤ 0 °C |
| `lluvia_anual_mm_<período>` | mm | Lluvia del año |
| `lluvia_campana_mm_<período>` | mm | Lluvia de octubre a marzo |
| `dias_lluvia_extrema_50_<período>` | días/año | Días con lluvia ≥ 50 mm |
| `racha_seca_campana_dias_<período>` | días | Racha más larga de días con menos de 1 mm, de octubre a marzo |

`<período>` = `historico`, `ssp245` o `ssp585`. La `fecha` de cada observación es el último día del período (31/12/2014 o 31/12/2060).

## Salida (contrato común)

```json
{"lote_id": "lote-prueba", "fecha": "2060-12-31", "variable": "dias_calor_35_ssp245", "valor": 12.4,
 "unidad": "días/año", "fuente": "NEX_GDDP", "resolucion_m": 25000, "calidad": "dudosa",
 "nota": "Días por año con máxima del aire ≥ 35 °C (estrés por calor) · SSP2-4.5 (emisiones intermedias) 2041-2060 · mediana de 3 modelos: ACCESS-CM2 …, MPI-ESM1-2-HR …, MRI-ESM2-0 … · cambio contra 1995-2014 del mismo modelo: +… · NEX-GDDP-CMIP6 (NASA) · celda centrada en -33.625, -65.375 · proyección de modelos corregidos, no pronóstico · dato REGIONAL de la celda de 0,25° (~25 km), no del lote"}
```

- Contrato: se suma `"NEX_GDDP"` a la lista de fuentes.

## Reglas de calidad

1. **Nunca inventar.** Un año con días sin dato no cuenta (un hueco achicaría una suma sin avisar). Un modelo con menos de 18 de 20 años completos queda afuera de ese período y la nota lo dice. Sin ningún modelo → `descartada`, `valor: null`.
2. Todo lo demás sale **`dudosa`**: es una proyección regional, no una medición.
3. La línea de base 1995-2014 es **de los modelos**, no lo observado. Para comparar con lo medido está el clima de la campaña de POWER (spec 034).
4. **Supuesto:** 3 modelos alcanzan para mostrar la dirección y el rango del cambio. Sumar más modelos alarga la primera consulta (~5 min por modelo).
5. **Supuesto:** umbrales de 35 °C (calor), 0 °C (helada del aire), 50 mm (lluvia extrema) y 1 mm (día seco). A validar con un agrónomo.

## Tiempo

- Primera consulta de una celda: **~15 minutos** (540 pedidos de ~7 s, de a 4). Ver la prueba real abajo.
- Después: al instante (memoria). Si Render se reinicia, se vuelve a calcular.

## Dónde entra

- **Registro (spec 009):** `SATELITES = [Satelite("NEX_GDDP", pedir, estatico=True)]`. Fuente propia, no respaldo; no toca el núcleo.
- **Ruta de prueba:** `GET /clima-futuro?lat=…&lon=…`.

## Criterios de aceptación

- [x] Tests sin internet: celda, versión de archivo, lectura de CSV y unidades, indicadores, huecos, modelos faltantes, memoria por celda, sin datos no inventa, ruta que valida el punto.
- [x] Prueba real sobre el lote de San Luis con los 3 períodos y los 7 indicadores (resultado abajo).
- [ ] Revisión de los umbrales con un agrónomo.

## Prueba real

Corrida a las 01:06 UTC desde el entorno de la nube (`probar_nex_gddp.py -33.7025 -65.2975`). Celda centrada en −33,625; −65,375. **978 s (16 min)**, los 540 pedidos con dato, ningún modelo afuera.

| Indicador | 1995-2014 (modelos) | SSP2-4.5 2041-2060 | SSP5-8.5 2041-2060 | Cambio SSP2-4.5 (rango de modelos) |
|---|---|---|---|---|
| Días con máxima ≥ 35 °C | 29,6 | **38,5** | **43,2** | +10,0 (+2,7 a +12,0) |
| Máxima media dic-feb | 31,7 °C | 32,9 °C | 32,9 °C | +1,2 (+0,5 a +1,4) |
| Días con mínima ≤ 0 °C | 28,9 | 19,1 | 19,0 | −7,1 (−9,8 a −4,6) |
| Lluvia del año | 649 mm | 709 mm | 720 mm | +36 (+6 a +135) |
| Lluvia oct-mar | 516 mm | 556 mm | 564 mm | +32 (+2 a +75) |
| Días con lluvia ≥ 50 mm | 0,2 | 0,25 | 0,35 | +0,10 (−0,20 a +0,15) |
| Racha seca más larga oct-mar | 17 días | 17 días | 17 días | 0 (−1 a 0) |

**Lectura:** a mitad de siglo la zona tiene **~10 días más por año de calor fuerte** (≥ 35 °C) y **~7 heladas del aire menos**. Los tres modelos coinciden en el signo. La lluvia sube un poco en la mediana, pero los modelos no se ponen de acuerdo en cuánto (de +6 a +135 mm). Las lluvias de ≥ 50 mm siguen siendo raras en una celda de 25 km (un día cada 3 a 5 años): el modelo suaviza las tormentas, así que este indicador subestima lo que pasa en un lote. Para el motor, lo firme es el calor: pesa sobre cultivos que florecen en enero (maíz de primera, girasol) y favorece fechas de siembra que corran la floración.

