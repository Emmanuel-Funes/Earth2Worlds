# Spec 040 · Rindes de referencia del departamento, del Ministerio de Agricultura

**Estado:** aprobada por Hernán ("Ok a los 3") · **Origen:** investigación 033. Hernán aprobó con "Todo" sumar el Ministerio de Agricultura como fuente aceptada, igual que el INTA · **Rama:** `MAGYP-rindes_de_referencia` · Se escribió como spec 036; pasó a 040 porque la 036 también la usa el respaldo de humedad de FLDAS

## 1. Objetivo

Darle al motor de recomendación (spec 027) un rinde de referencia por cultivo cuando el productor no carga su propio historial. Hoy el motor deja el historial de rindes en "faltan datos".

El dato es **del departamento, no del lote**. Sirve para comparar cultivos entre sí y para tener un orden de magnitud. No reemplaza el historial del productor.

## 2. Fuente

| | |
|---|---|
| Fuente | Estimaciones Agrícolas del Ministerio de Agricultura, Ganadería y Pesca de la Nación (MAGyP), en el portal de datos abiertos `datos.magyp.gob.ar` |
| Excepción | No es una agencia espacial. Entra como excepción aprobada por Hernán, junto al INTA y al Catastro de San Luis |
| Acceso | La API del portal (`/api/3/action/package_search?q=estimaciones agricolas`) da el CSV vigente (hoy `estimaciones-agricolas-2026-03.csv`). Sin cuenta |
| Copia en el repo | Desde el servidor del Ministerio (la misma máquina atiende `datos`, `datosestimaciones`, `geoportal` y `www.magyp.gob.ar`) no responde desde fuera del país, y Render está en Estados Unidos. Por eso la app lee una **copia del CSV vigente guardada en el repo** (`rotaterra/fuentes/datos/magyp_rindes.csv.gz`, 0,44 MB: los cultivos del catálogo desde 2000/01, 36.333 filas, con las mismas columnas) y su ficha (`magyp_rindes.json`: archivo, URL del Ministerio, de dónde se bajó y fecha de la copia). El dato cambia una o dos veces por año |
| Renovar la copia | Workflow `Actualizar copia de MAGyP (rindes de referencia)` (`actualizar_copia_magyp.py`), a mano cuando el Ministerio publica otro archivo: busca el CSV vigente en el portal del Ministerio (si no contesta, en el portal nacional `datos.gob.ar`, que lista el mismo recurso), lo baja del Ministerio y, si no contesta, baja **el mismo archivo** guardado en el Archivo de Internet (`web.archive.org`). Solo esta herramienta usa esos caminos; la app nunca. La copia salió del Archivo de Internet (foto del 24/4/2026 de `estimaciones-agricolas-2026-03.csv`) |
| Columnas | cultivo, anio, campania, provincia, provincia_id, departamento, departamento_id, superficie_sembrada_ha, superficie_cosechada_ha, produccion_tm, rendimiento_kgxha |
| Cobertura | Todo el país, por departamento, desde 1969/70 hasta 2024/25 |
| Respaldo | No hay otra fuente oficial con rindes por departamento (la API de series de tiempo del Estado, `apis.datos.gob.ar/series`, tiene rindes del país, no del departamento). Si falta la copia o Georef no responde, el conector avisa con un error (`ErrorMAGyP`, HTTP 502 en el endpoint de prueba) y no se inventa nada. La productividad de MODIS (MOD17, investigación 033) muestra una tendencia, pero no es un rinde, así que no lo reemplaza |
| Verificado | 14/10/2026 (investigación 033): General Pedernera (San Luis) tiene 1969/70 a 2024/25 |

## 3. Entrada

El polígono del lote. Para saber el departamento:

1. Si el pedido trae `departamento_id` (el código del INDEC que usa el CSV), se usa ese.
2. Si no, se le pregunta a la API Georef del Estado nacional (`apis.datos.gob.ar/georef/api/ubicacion?lat=…&lon=…`) con el centro del lote. Georef es del mismo portal de datos abiertos del Estado y devuelve la provincia y el departamento con el mismo código (`ubicacion.departamento.id`, 5 dígitos). Hernán aprobó usarla ("Ok a los 3").

Verificado: para (-33,7025; -65,2975) Georef responde `{"departamento": {"id": "74035", "nombre": "General Pedernera"}, "provincia": {"id": "74", "nombre": "San Luis"}}`.

## 4. Proceso

1. Leer la copia del repo (sección 2). Al renovarla, el CSV vigente es el recurso CSV más nuevo cuyo nombre o URL dice "estimaciones-agricolas"; se lee en UTF-8 o, si no se puede, en Latin-1; los números aceptan coma decimal y las celdas vacías son "sin dato".
2. Filtrar las filas del departamento. El código se compara como número: el CSV puede traer `departamento_id` = "74035", o "35" con `provincia_id` = "74".
3. Para cada cultivo del catálogo, tomar las **últimas 10 campañas con rinde** y calcular la mediana (redondeada a kg enteros), el mínimo y el máximo.
4. Pasar los nombres del Ministerio a los del catálogo (en minúsculas y sin tildes; "X total" cuenta como X): Maíz → `maiz`, Soja 1ra → `soja`, Sorgo → `sorgo`, Maní → `mani`, Girasol → `girasol`, Trigo (o Trigo total) → `trigo`, Alfalfa → `alfalfa`, Algodón → `algodon`. La soja de segunda queda aparte (`soja_2da`), porque rinde menos y no es la misma decisión. "Soja total" no se usa: mezcla primera y segunda.
5. Alfalfa y algodón no están en el archivo de General Pedernera: salen descartados con esa nota.

## 5. Salida

Una `Observacion` por cada cultivo del catálogo (`maiz`, `soja`, `soja_2da`, `sorgo`, `mani`, `girasol`, `trigo`, `alfalfa`, `algodon`), siempre las nueve, con `fuente: "MAGyP"`, `unidad: "kg/ha"`, `resolucion_m: 100000` (escala de departamento) y `fecha` del 30/6 del año en que termina la última campaña usada (2024/25 → 30/6/2025). Un cultivo descartado lleva el 30/6 del año en que termina la campaña más nueva del archivo.

| `variable` | Ejemplo, General Pedernera (mediana de 2015/16 a 2024/25) |
|---|---|
| `rinde_referencia_maiz_kg_ha` | 4950 (de 3300 a 7200) |
| `rinde_referencia_soja_kg_ha` | 2100 (de 1200 a 3200) |
| `rinde_referencia_sorgo_kg_ha` | 3650 (de 2700 a 5300) |
| `rinde_referencia_mani_kg_ha` | 3055 (de 2200 a 4200) |
| `rinde_referencia_girasol_kg_ha` | 1850 (de 1700 a 2462) |
| `rinde_referencia_trigo_kg_ha` | 1450 (de 900 a 2600) |
| `rinde_referencia_soja_2da_kg_ha` | 1400 (de 600 a 2200; 9 campañas, la última 2021/22) |
| `rinde_referencia_alfalfa_kg_ha` | null, descartada: sin datos en el departamento |
| `rinde_referencia_algodon_kg_ha` | null, descartada: sin datos en el departamento |

La `nota` dice el departamento, las campañas usadas, el rango y que es un promedio del departamento, no del lote:

> Mediana de 10 campañas (2015/16 a 2024/25) en General Pedernera, San Luis: de 3300 a 7200 kg/ha. Promedio del departamento, no del lote (Estimaciones Agrícolas, Ministerio de Agricultura, archivo estimaciones-agricolas-2026-03.csv).

Si hubo pérdidas totales desde la primera campaña usada, se agrega " · <k> campañas con pérdida total". Un cultivo sin filas en el departamento dice "Sin datos en el departamento (…)"; uno con filas pero sin ningún rinde, "Sin campañas con rinde en el departamento (…)".

Endpoint de prueba: `GET /rindes-referencia`, además de la entrada por `POST /consulta`.

## 6. Cambios en el motor (spec 027)

- Cada cultivo de la respuesta suma `rinde_referencia` con la mediana, el rango, las campañas y la escala `regional`.
- **No cuenta como historial de rindes.** El nivel de completitud C sigue pidiendo el historial del productor, y "historial de rindes" sigue en los faltantes. El rinde de referencia solo se muestra.
- Si el lote tiene clase de capacidad de uso V o peor, el motor agrega: "Un lote de esta clase suele rendir por debajo del promedio del departamento."
- El cambio del motor se suma a su rama (`MOTOR-recomendacion_de_cultivos`), y la spec 027 se actualiza en el mismo PR.

## 7. Reglas de calidad

- Una campaña sin rinde, o con rinde 0 por pérdida total, no cuenta para la mediana. Las pérdidas totales (superficie sembrada > 0 y rinde 0 o superficie cosechada 0) se cuentan desde la primera campaña usada y la `nota` dice cuántas hubo, porque son un dato de riesgo. Una campaña sembrada con el rinde vacío y sin superficie cosechada (todavía sin cosechar) no es pérdida total.
- Si quedan menos de 5 campañas con rinde, el dato sale `dudosa`.
- Nunca se inventa un rinde: sin filas del departamento, sale `valor: null` y `calidad: "descartada"`.

## 8. Pruebas

- **Sin internet** (`tests/test_magyp_rindes.py`): un CSV simulado da las medianas esperadas; las campañas con rinde 0 o vacío no cuentan; con 4 campañas sale `dudosa`; sin filas del departamento sale descartada; Georef simulado da el código del departamento; la copia guarda solo los cultivos del catálogo desde 2000/01 y da los mismos rindes que el archivo completo; la copia del repo existe y se lee; sin la copia, el conector avisa con un error.
- **Real:** workflow `Probar MAGyP (rindes de referencia)` con el lote de San Luis: Georef en vivo, rindes de la copia, y un diagnóstico (que no corta la prueba) de si el portal del Ministerio responde y si su CSV vigente sigue siendo el de la copia.

## 9. Criterios de aceptación

- [x] Con el lote de San Luis, el departamento sale General Pedernera. Verificado en la prueba real (corridas 38670025488 y 38671001505): Georef devolvió `74035`, General Pedernera, San Luis, para (-33,7025; -65,2975).
- [x] Las medianas dan las de la tabla de la sección 5 (maíz 4950, soja 2100, sorgo 3650, maní 3055). Verificado con la copia del CSV real `estimaciones-agricolas-2026-03.csv`: maíz 4950, soja 2100, sorgo 3650, maní 3055, girasol 1850 y trigo 1450, iguales a la investigación 033; soja de segunda 1400; alfalfa y algodón descartados.
- [x] El motor muestra el rinde de referencia por cultivo y el nivel de completitud no cambia. Verificado con la prueba sin internet del motor (rama `MOTOR-recomendacion_de_cultivos`): maíz 4950 kg/ha, escala regional, aviso por clase VI, y "historial de rindes" sigue en los faltantes.
- [x] `pytest` pasa sin internet (15/10/2026: 64 tests en verde, 23 de este conector).
- [x] El workflow real pasa. 15/10/2026, corrida real: Georef en vivo da 74035 (General Pedernera) y las seis medianas de la copia coinciden con la investigación 033. El portal del Ministerio seguía sin responder desde GitHub.
- [x] Hernán aprobó esta spec: "Ok a los 3" (incluye usar Georef).

## 10. Preguntas abiertas

1. **Resuelta: sí, Hernán aprobó Georef ("Ok a los 3").** ¿Usamos Georef para saber el departamento del lote? Se propone que sí: es del mismo portal de datos abiertos del Estado que el Ministerio. La otra opción es que el productor elija el departamento en la app.
2. ¿Se ajusta el rinde por la clase de capacidad de uso del lote? Se propone que no, hasta que Leandro o el agrónomo den un criterio. Por ahora solo se muestra el aviso de la sección 6.
