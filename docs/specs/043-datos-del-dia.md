# Spec 043 · Datos del día

**Estado:** aprobada por Hernán ("Si") · **Pedida:** ("¿Qué podría hacer para tener datos del hoy en todas? ¿Hay opciones en otros satélites que sean al día o que al menos no tengan más de un día de retraso?") · **Completa:** spec 009 (satélites en ramas), spec 012 (respaldos en la consulta) y spec 041 parte B (respaldo si todo viene descartado)

## Objetivo

Que la app tenga el dato de hoy, o a lo sumo de ayer, en todo lo que cambia día a día, sin dejar de usar la fuente fina de siempre.

| Antes | Después |
|---|---|
| Si POWER todavía no publicó los últimos 4 días, la app no tiene clima de esos días | Los días que la principal todavía no publicó los completa una fuente "del día", y cada valor dice de qué fuente vino |
| Un respaldo entra solo si la principal falla entera | Además, un respaldo marcado "del día" completa la cola de días que le falta a la principal |
| Clima con 4 días de atraso, radiación con 7, humedad con 2, lluvia y heladas con 1 a 2 | Clima con 9 horas, lluvia con 9 horas, heladas con menos de 1 hora, humedad con 3 horas, NDVI con 1 día |

## Lo medido

| Dato | Hoy en la app | Atraso | Fuente del día propuesta | Atraso | Píxel |
|---|---|---|---|---|---|
| Clima (temp. máx./mín.) | POWER | 4 días | NASA GEOS-FP | 9 h | 25 km |
| Radiación | POWER | 7 días | NASA GEOS-FP | 9 h | 25 km |
| Lluvia | IMERG Late diario | 1 día | IMERG Early media hora | 9 h | 10 km |
| Heladas (temp. de superficie mínima) | VIIRS | 1 a 2 días | NOAA GOES-19 LST | 50 min | 10 km |
| Humedad del suelo | SMAP L4 | 2 días | SMAP L2 tiempo casi real (NRT) | 2,6 h | 36 km |
| NDVI | HLS | 2 a 5 días, o nada con nubes | MODIS NDVI "8 días que se actualiza todos los días" (LANCE NRT) | 1 día | 250 m |
| Evapotranspiración | MODIS ET | 8 días o más | NASA GEOS-FP (evaporación del modelo) | 9 h | 25 km |

Detalle de la medición: `/mnt/project-files/rotaterra/datos-al-dia.md` y rama `INVESTIGACION-datos_al_dia` (solo para investigar, no se une a nada).

No entran: relieve y suelo (no cambian), napa GRACE y El Niño (se publican por semana o por mes; no existe versión diaria).

## Parte A · Núcleo: completar la cola de días (cambia la spec 012)

1. `Satelite` suma un campo opcional `al_dia: bool = False`. Solo lo usan los respaldos nuevos de esta spec, así que los respaldos que ya existen se comportan igual que hoy.
2. En `POST /consulta`, después de la cadena de siempre (principal y respaldos comunes), el núcleo mira, **variable por variable**, cuál es el último día con valor útil. Si es anterior a `hasta`, pide los días que faltan (desde el más temprano de esos días hasta `hasta`) a los respaldos `al_dia` de esa cadena, en su orden. Si ninguna fuente trajo nada útil, la cola es todo el período (así un pedido de "solo hoy" lo contesta el respaldo del día). Los respaldos `al_dia` no entran en la cadena común.
3. Del respaldo del día se guardan solo:
   - los días posteriores al último día útil de esa variable (no se rellenan huecos del medio, como los días en que HLS no pasó); un día que la principal mandó como `-999` descartado se reemplaza;
   - las variables que la respuesta ya traía, para que tenga la misma forma (si no traía ninguna, todas las del respaldo del día).
   - Si hay dos respaldos del día, el segundo pone solo lo que el primero no pudo (ej. IMERG Early hasta ayer, otro para hoy).
4. Cada observación conserva su `fuente`. La respuesta suma un campo `completada_con` (lista de fuentes que completaron días; vacía si nadie completó) y los `intentos` muestran al respaldo del día con resultado `completo` y cuántas filas puso. `fuente_usada` sigue siendo la que contestó en la cadena común; solo si nadie contestó pasa a ser el respaldo del día. `GET /satelites` suma la lista `del_dia` de cada principal. Así no se rompe nada de lo que ya usa Daniel.
5. Si el respaldo del día falla o no trae nada, la respuesta queda como hoy, con su intento marcado `error` o `sin_datos`.
6. El núcleo no nombra a ningún satélite (spec 009): solo mira `al_dia` y `respaldo_de`.

## Parte B · Fuentes nuevas, cada una en su rama (spec 009)

Cada una es un respaldo `al_dia=True` de la cadena que corresponde, con su conector, tests sin internet y workflow `Probar …`. Ninguna importa a otro satélite.

| Rama | Respaldo de | Variables | Cómo se lee | Calidad |
|---|---|---|---|---|
| `GEOS_FP-clima_del_dia` | POWER | `temp_max`, `temp_min` (°C), `radiacion` (MJ/m²/día) | OPeNDAP público de la NASA (`opendap.nccs.nasa.gov`, colecciones horarias `tavg1_2d_slv_Nx` y `tavg1_2d_rad_Nx`), celda del centro del lote, día local argentino (UTC−3) | `buena` si el día está completo, `dudosa` si es el día en curso (la `nota` dice hasta qué hora hay datos) |
| `GEOS_FP-evapotranspiracion_del_dia` | ET | `et_mm_dia` | mismo servidor, colección horaria `tavg1_2d_lnd_Nx`, `evland` (kg/m²/s), suma de las 24 horas del día local | `dudosa`: es un modelo de 28 km; la `nota` lo dice. El día en curso se descarta (la suma quedaría corta) |
| `IMERG_EARLY-lluvia_del_dia` | IMERG | `lluvia_mm` | GES DISC con Earthdata, `GPM_3IMERGHHE` (media hora), suma del día local | `buena` con el día completo, `dudosa` si es el día en curso |
| `GOES-heladas_del_dia` | VIIRS_LST | `temp_sup_min_c` | bucket abierto de la NOAA, `ABI-L2-LSTF`, mínimo entre las 4 y las 7 de la mañana con el control de calidad del producto (igual criterio que el GOES de la spec 023) | `buena` con calidad del producto buena; con nubes, `descartada` |
| `SMAP_NRT-humedad_del_dia` | SMAP | `humedad_superficial` (m³/m³) | NSIDC con Earthdata, `SPL2SMP_NRT`: CMR busca las pasadas sobre el punto del lote en los días locales pedidos y se baja cada archivo HDF5 entero (~1,5 MB, NSIDC lo entrega desde `*.cloudfront.net`). Se lee la celda EASE-2 de 36 km cuyo centro está más cerca (a menos de 30 km). Si la NASA rehizo una pasada (`_002`), se usa la más nueva. Cada pasada sale ~2 h después (6-7 h o 19-20 h de Argentina), y no todos los días pasa sobre el lote. Día local UTC−3; con dos pasadas, el promedio | siempre `dudosa`: píxel de 36 km, regional. `descartada` si la NASA no recomienda el valor (bit 0 de `retrieval_qual_flag`), si queda fuera de 0,02 a 0,5 o si no hubo pasada |
| `MODIS_NRT-ndvi_del_dia` | HLS | `ndvi` | LANCE (`nrt3.modaps.eosdis.nasa.gov`) con Earthdata, `MOD13Q4N` (Terra, 250 m). No tiene OPeNDAP: se baja el archivo HDF4 del mosaico entero (~215 MB, 9 a 13 s desde la nube) y se lee solo el recorte del lote. Cada archivo es un compuesto de 8 días que se rehace todos los días (sale ~1,5 h después de terminar el día UTC); se usa el más nuevo hasta `hasta` y cada píxel trae el día en que lo vio el satélite, así que da un valor por día visto. Los días anteriores a esos 8 quedan para los respaldos comunes de HLS. Píxeles válidos: confiabilidad 0 o 1 | `dudosa`: 250 m y lee 0,07 a 0,14 distinto que HLS (como VIIRS); la `nota` lo dice. Con menos del 20 % del lote visible, `descartada` (nubes) |

**Evapotranspiración y compuestos de 8 días:** MODIS da un promedio diario por compuesto de 8 días con la fecha del primer día. El respaldo del día empieza al día siguiente de esa fecha, así que sus primeros días caen dentro del último compuesto de MODIS. Se deja así porque el núcleo no sabe de compuestos (spec 009); cada fila dice su fuente y la `nota` de MODIS dice qué días cubre. Para sumar el agua de un período, no se suman las dos.

Prioridad de armado: primero GEOS-FP clima, IMERG Early y GOES heladas (lo que más cambia en el campo de un día para otro); después SMAP NRT, MODIS NRT y GEOS-FP evapotranspiración.

`Fuente` en `contrato.py` y `PRIORIDAD` en `base.py` suman `GEOS_FP`, `IMERG_EARLY`, `SMAP_NRT` y `MODIS_NRT` (GOES ya está). Su prioridad queda por debajo de la principal de su cadena.

## Reglas de calidad

- Nunca se inventa un valor: si la fuente del día no tiene el dato, `valor: null`, `calidad: "descartada"` y la `nota` dice por qué.
- El día en curso nunca es `buena`: está incompleto y la `nota` dice hasta qué hora UTC llegan los datos.
- Las fuentes de píxel grande (GEOS-FP, SMAP NRT) dicen en la `nota` que son regionales.
- Cuando la principal publica esos días, la próxima consulta los trae de la principal y el respaldo del día ya no entra.

## Lo que esto cambia en otras specs

- **Spec 012:** se suma la regla de completar la cola (parte A).
- **Spec 041 parte A (control cruzado, sin aprobar):** los días completados no se comparan contra un testigo, porque no hay principal para ese día.
- **Spec 042 (control diario):** suma el atraso normal de cada fuente nueva: 1 día para todas.
- **Guía de la API para Daniel:** explica `completada_con` y que el último día puede venir de otra fuente.

## Criterios de aceptación

- [x] Una consulta de clima de los últimos días sobre el lote de San Luis trae todos los días: los que POWER no publicó vienen de GEOS-FP, con `completada_con: ["POWER:GEOS_FP"]`. Prueba real (workflow `Probar datos del día`, rama `PRUEBA-datos_del_dia`), del 10 al 15/10: POWER tenía temperatura hasta el 12 y ninguna radiación; GEOS-FP completó 14 valores. Máx./mín. del 13 al 15: 15,0/10,1 · 17,1/9,5 · 17,5/7,9 °C (el 15 `dudosa`, 12 de 24 horas). Radiación del 10 al 14: 17,6 · 10,1 · 8,4 · 7,2 · 9,8 MJ/m²; la del 15 queda descartada (día incompleto). Donde coinciden, GEOS-FP y POWER dan parecido: máxima del 11, 20,1 contra 20,6 °C; del 12, 17,4 contra 16,1 °C. Tardó 90 s.
- [x] Una consulta de lluvia hasta hoy trae el día de hoy desde IMERG Early, marcado `dudosa` y con la hora en la nota: IMERG Late llegó hasta el 14/10 y IMERG Early puso el 15/10, 0,0 mm "hasta las 14:30 UTC (20 de 48 medias horas)". Tardó 54 s.
- [x] Una consulta de heladas hasta hoy trae la mínima de esta madrugada desde GOES-19: VIIRS llegó hasta el 11/10 y GOES-19 completó del 12 al 15 (15/10: 5,9 °C, `buena`). Tardó 20 s. Los días 12 y 13 solo hubo lecturas dudosas de GOES-19 (−4,8 y −5,7 °C con el aire a 10 °C según GEOS-FP, 14,8 mm de lluvia del modelo el 13): son bordes de nube. Por eso una lectura dudosa solo se usa si esa madrugada no hay ninguna buena, y la nota dice "posible nube".
- [x] La evapotranspiración del día de GEOS-FP trae los días completos sobre el lote de San Luis (−33,70, −65,30). Prueba real a las 14:10 UTC con `probar_geos_fp.py`, desde un hilo con acceso a la NASA (rama `GEOS_FP-evapotranspiracion_del_dia`), del 13 al 17/10: 0,8 · 0,8 · 1,2 · 1,3 mm/día del 13 al 16, todos `dudosa`; el 17 queda `descartada` (la última hora publicada era 02:30 UTC). Tardó 9 s. Son valores bajos y creíbles para un suelo seco después de la sequía; el clima del modelo esos días: máx./mín. 15,0/10,1 · 17,1/9,5 · 19,5/7,9 · 18,9/8,0 °C y 14,8 mm de lluvia el 13. El día 15, que el 16/10 había salido `dudosa` con 17,5 °C (12 de 24 horas), ya completo da 19,5 °C: confirma que el día en curso no puede ser `buena`.
- [x] El NDVI del día de LANCE MODIS NRT se lee del archivo real (prueba con `probar_modis_nrt.py`, rama `MODIS_NRT-ndvi_del_dia`, archivo `MOD13Q4N.A2026289.h12v12`, compuesto del 9 al 16/10, publicado el 17/10 a la 01:37 UTC). Sobre el lote de San Luis (−33,70, −65,30, 16 píxeles) vino `descartada`: toda la semana nublada (en la zona, 95 % de los píxeles con nube después de la lluvia del 13). En un lote despejado del sur de San Luis (−34,351, −66,577) dio 0,402 `dudosa`, visto el 16/10. Cada prueba tardó 12 a 13 s. Tests sin internet: 18 nuevos, 104 en total verdes.
- [x] La humedad del día de SMAP NRT se lee de los archivos reales (prueba a las 15:00 UTC con `probar_smap_nrt.py`, rama `SMAP_NRT-humedad_del_dia`) sobre el lote de San Luis (−33,70, −65,30; centro de la celda a 15 km), del 13 al 17/10: 0,192 · 0,214 · descartada (la NASA no recomienda la pasada del 15) · 0,183 m³/m³ · el 17 sin pasada todavía. Tardó 5 s. SMAP L4 (la principal) llegaba hasta el 14: 0,159 y 0,153 m³/m³ el 13 y el 14, así que la celda de 36 km lee 0,03 a 0,06 más húmedo que la de 9 km. Por eso es `dudosa` y sirve para la tendencia de los últimos días. Tests sin internet: 14 nuevos, 100 en total verdes.
- [x] Una consulta donde la principal ya tiene todos los días no llama a ningún respaldo del día (test sin internet, `tests/test_consulta.py`).
- [x] Un hueco en el medio del período (día sin pasada de HLS) no se rellena (test sin internet).
- [x] Cada variable se completa desde su propio último día (POWER: temperatura desde el 13, radiación desde el 10), y el respaldo común sigue entrando antes que el del día (tests sin internet: 10 nuevos, 85 del núcleo verdes).
- [x] Los respaldos que ya existen se comportan igual que antes (tests actuales verdes).
- [x] Los tests sin internet de cada conector nuevo pasan, y su workflow `Probar …` da verde con datos reales (PRs #59 GEOS-FP, #60 IMERG Early, #61 GOES-19). Lo que encontraron las pruebas reales: el servidor de GEOS-FP da 504 si se le piden más de ~24 horas juntas (se pide de a 12) y deja una línea en blanco entre horas.
- [x] Todas las ramas juntas (Render + las tres fuentes del día): 877 tests sin internet verdes.
- [x] `tests/test_nucleo.py` sigue verde: el núcleo no nombra a ningún satélite.

## Fuera de esta spec

- No se une nada a `main` ni se suma nada a Render sin el OK de Hernán.
- No hay NDVI de 30 m al día: HLS depende de que pase el satélite sin nubes.
- La lluvia instantánea de GOES-19 (20 minutos de atraso) se deja para otra spec: es una estimación sin pluviómetros, buena para "está lloviendo ahora" pero no para sumar milímetros del día.
