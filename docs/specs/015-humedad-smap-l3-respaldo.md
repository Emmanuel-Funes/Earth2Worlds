# Spec 015 · Humedad del suelo observada por SMAP L3 como segundo respaldo de SMAP L4

**Estado:** aprobada por Hernán el 4/10/2026 ("Sumar lo necesario para cubrir lo que hace falta") y verificada con datos reales · **Etapa:** pipeline satélite → API → app · **Requiere:** cuenta NASA Earthdata

## Objetivo

Que el lote siga teniendo humedad del suelo de la NASA cuando el producto SMAP L4 (`SPL4SMGP`) no está disponible por ninguno de sus dos caminos (directo y AppEEARS, spec 005). El L4 es un **modelo** que asimila las mediciones de SMAP; el L3 es la **observación satelital** misma, sin modelo. Si el L4 se atrasa o se corta, el L3 sigue dando la humedad de superficie medida por el radiómetro.

Orden de la humedad del suelo: SMAP L4 directo → SMAP L4 vía AppEEARS (`orden=1`, mismo producto) → **SMAP L3** (`orden=2`).

## Fuente

| Producto | Agencia | Grilla | Frecuencia | Qué se usa |
|---|---|---|---|---|
| `SPL3SMP_E` (SMAP Enhanced L3 Radiometer Global Daily 9 km EASE-Grid Soil Moisture), versión vigente en CMR | NASA (NSIDC DAAC, Earthdata) | EASE-Grid 2.0 global de 9 km (EPSG:6933), 3856 columnas × 1624 filas, la misma del L4 | un archivo por día (UTC) con dos pasadas: AM (descendente, ~6 h local) y PM (ascendente, ~18 h local) | humedad de superficie (`soil_moisture`, `soil_moisture_pm`) y su bandera de calidad (`retrieval_qual_flag`, `retrieval_qual_flag_pm`) |

- Se busca la colección en CMR en el proveedor de la nube de NSIDC (`NSIDC_CPRD`, el mismo del L4); si no aparece ahí, se usa `earthdata.coleccion_vigente`.
- Se lee **solo la celda del lote** por OPeNDAP (`earthdata.archivos` + `earthdata.leer_csv`), como el camino directo del L4.
- Las rutas exactas de las capas se leen de los metadatos del archivo (`.dmr`): grupo `Soil_Moisture_Retrieval_Data_AM` (variables sin sufijo) y `Soil_Moisture_Retrieval_Data_PM` (variables con `_pm`). Los grupos polares se ignoran.
- **Solo superficie (0-5 cm).** El L3 no trae zona de raíces: este respaldo no entrega `humedad_zona_raiz`.

## Entrada

Lote con su centro (`lat`, `lon`, EPSG:4326, el que guarda el núcleo) y un período `desde`–`hasta` (máximo 366 días).

## Proceso

1. Token de Earthdata con `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD`.
2. Colección `SPL3SMP_E` vigente y sus archivos diarios del período (CMR, con la caja del punto). La fecha del día sale del nombre del archivo (`SMAP_L3_SM_P_E_AAAAMMDD_…`).
3. Fila y columna de la celda de 9 km que contiene el punto, con la fórmula de EASE-Grid 2.0 (la misma del L4: el lote de prueba cae en la fila 1262, columna 1228). Se verifica con la latitud y longitud que trae el propio archivo para esa celda.
4. Por cada día se piden por OPeNDAP, para AM y PM: humedad, bandera de calidad, latitud y longitud de la celda (se piden 2 columnas porque el servidor no devuelve un solo valor; se usa la primera).
5. Calidad de cada pasada (`retrieval_qual_flag`, bit 0 = "calidad recomendada"):
   - **recomendada**: hay humedad (no es relleno `-9999`) y el bit 0 está en 0.
   - **no recomendada**: hay humedad pero el bit 0 está en 1 (p. ej. vegetación densa, agua, suelo congelado o interferencia de radio).
   - **sin dato**: humedad `-9999` (ese día la órbita no pasó sobre la celda o no se pudo calcular).
6. Valor del día = promedio de las pasadas recomendadas. Si no hay ninguna recomendada, promedio de las no recomendadas.

## Salida (contrato común)

Una observación por día del período, aunque la NASA no tenga dato ese día.

```json
{"lote_id": "lote-7", "fecha": "2026-01-09", "variable": "humedad_superficial", "valor": 0.118,
 "unidad": "m³/m³", "fuente": "SMAP", "resolucion_m": 9000, "calidad": "buena",
 "nota": "Respaldo de SMAP L4 · observación satelital SMAP L3 (SPL3SMP_E), celda de 9 km: contexto regional, no dato del lote · solo superficie 0-5 cm (el L3 no trae zona de raíces) · pasada AM 0,118 (recomendada) · PM sin pasada"}
```

- `variable`: `humedad_superficial`, la misma que usa el L4 para la capa 0-5 cm (`sm_surface`), así la serie sigue sin saltos de nombre.
- `fuente`: `SMAP` (es la misma misión; la `nota` aclara que es el L3 observado y no el L4 modelado).

## Reglas de calidad

| Calidad | Cuándo |
|---|---|
| `buena` | Al menos una pasada recomendada y el valor dentro del rango físico (0 a 0,6 m³/m³) |
| `dudosa` | Solo pasadas no recomendadas, o el valor fuera del rango físico |
| `descartada` (`valor: null`) | Ninguna pasada con dato ese día, o la NASA no publicó el archivo del día. La `nota` dice el motivo |

Si CMR no tiene **ningún** archivo del período (por ejemplo, un pedido de días que la NASA todavía no publicó), el conector termina en error con ese motivo en lugar de devolver una lista de descartes, igual que VIIRS: así la actualización lo muestra como `error` y no como "ok".

Nunca se inventa un valor: un día sin pasada **no** se rellena con el día anterior ni con el L4. Es normal que el L3 tenga días sin pasada: en la prueba real hubo una pasada casi todos los días (AM y PM alternadas) y faltó una de cada 14.

Supuestos (se anotan en la `nota`): bit 0 de `retrieval_qual_flag` como criterio de calidad recomendada (documentación de NSIDC del SPL3SMP_E); rango físico 0 a 0,6 m³/m³, el mismo del L4.

## Dónde entra

- Registro: `SATELITES = [Satelite("SMAP:L3", pedir, respaldo_de="SMAP", orden=2)]`. Entra en la actualización nocturna solo si fallan el L4 directo y el L4 vía AppEEARS (spec 005).
- Es un satélite independiente (spec 009): rama `SMAP_L3-humedad_respaldo`, sin unir a `main` hasta la orden de Hernán. Depende del núcleo con varios respaldos en orden (rama `NUCLEO-varios_respaldos_en_orden`, PR #24).
- Endpoint de prueba: `GET /humedad-suelo/l3?lote_id=…&lat=…&lon=…&desde=…&hasta=…`. En la consulta en el momento (spec 010), `/humedad-suelo` sigue respondiendo con el L4.

## Comparación con el L4 (referencia)

SMAP L4 0-5 cm en el lote de prueba (spec 003/005): 0,049 el 1/1/2026 … 0,098 el 8/1, 0,120 el 9/1, 0,127 el 14/1. El L3 tiene que seguir la misma tendencia en los días con pasada (se anotan los números de la prueba real).

## Verificado en la prueba real (4/10/2026, PR #30)

- CMR tiene `SPL3SMP_E` en la nube de NSIDC (colección `C2938664763-NSIDC_CPRD`) con OPeNDAP: 14 archivos diarios del 1 al 14 de enero de 2026, leídos en 11 segundos.
- Las capas están donde dice la spec: `/Soil_Moisture_Retrieval_Data_AM/soil_moisture`, `retrieval_qual_flag`, `latitude`, `longitude` y en `/Soil_Moisture_Retrieval_Data_PM/` las mismas con `_pm`.
- Bandera real: **8** en las pasadas con dato (bit 0 en 0 = recomendada; el bit 3 prendido no afecta la humedad) y **7** cuando no hubo pasada (bits 0, 1 y 2: no recomendada, no intentada, no lograda), con humedad `-9999`.

## Criterios de aceptación

- [x] Con el lote de prueba real (San Luis, 1 al 14 de enero de 2026) se obtiene la humedad de superficie de SMAP L3 en los días con pasada, con su calidad, y se anotan los números. *13 días `buena` y 1 `descartada`, en m³/m³: 0,064 (1/1 AM), 0,058 (2/1 PM), 0,070 (3/1 AM), 0,052 (4/1 AM), 0,063 (5/1 PM), 0,041 (6/1 AM), 0,062 (7/1 PM), sin pasada el 8/1, 0,194 (9/1 AM), 0,128 (10/1 PM), 0,1205 (11/1 AM), 0,067 (12/1 AM), 0,174 (13/1 PM), 0,192 (14/1 AM). Una sola pasada por día: AM y PM se alternan.*
- [x] La celda de 9 km calculada coincide con la latitud y longitud que trae el archivo de la NASA. *Centro del lote (-33,7025; -65,2975) → fila 1262, columna 1228; el archivo da para esa celda el centro (-33,6715; -65,306), a 3,5 km del punto (media celda son ~4,5 km). Es la misma celda del L4 (spec 005).*
- [x] Los días sin pasada quedan `descartada` con el motivo, sin inventar valores. *El 8/1 (AM y PM con `-9999`, bandera 7): `valor: null`, nota "Ese día SMAP no pasó sobre la celda o no pudo medir".*
- [x] Los valores siguen la tendencia del L4 en los mismos días (se anota la diferencia). *Los dos muestran el suelo seco la primera semana y el humedecimiento desde el 9/1. El L3 da más alto y salta más: 1/1 L3 0,064 contra L4 0,049 (+0,015); 9/1 0,194 contra 0,120 (+0,074); 14/1 0,192 contra 0,127 (+0,065); el 8/1 (L4 0,098) el L3 no pasó. Es esperable: el L3 mide la capa superficial en el momento de la pasada (reacciona enseguida a la lluvia, como el 13/1), mientras que el L4 es el promedio diario de un modelo que suaviza. Por eso el L3 sirve para seguir la tendencia, no para comparar valores absolutos con el L4.*
- [x] SMAP L3 no importa código de ningún otro satélite (`tests/test_nucleo.py` en verde). *Workflow `Tests` verde en el PR #30; 69 pasan en local.*
- [x] Tests sin internet en `tests/test_smap_l3.py`; prueba real "Probar SMAP L3 (humedad de respaldo)" verde en el PR, con un clic y en cada PR que toque el conector. *25 tests sin internet; prueba real verde en el PR #30.*

## Fuera de alcance

Zona de raíces (el L3 no la tiene), los grupos polares, el producto de 36 km (`SPL3SMP`) y la humedad del radar de Sentinel-1 combinada con SMAP (`SPL2SMAP_S`).
