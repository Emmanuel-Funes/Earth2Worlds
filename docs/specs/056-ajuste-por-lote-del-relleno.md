# Spec 056 · Ajuste por lote del satélite que rellena huecos

**Estado:** aprobada por Hernán el 28/10/2026 ("Dale, hacelo") · **Etapa:** núcleo (consulta en el momento) · **Rama:** `NUCLEO-ajuste_por_lote` · **Depende de:** spec 052 (`NUCLEO-rellenar_huecos_por_detalle`)

## Problema

Con la spec 052, los huecos de más de 2 días del NDVI los rellena el siguiente satélite de la cadena. En la prueba real de enero de 2026 Sentinel-3 rellenó 4 días con un NDVI entre 0,08 y 0,16 **más alto** que el HLS de los días vecinos (10/1: 0,572 contra 0,414 de HLS el 11/1). La serie mostraba saltos que no eran del cultivo.

Causa: un píxel de Sentinel-3 mide 300 × 300 m (9 ha) y el lote de prueba ~25 ha; el píxel mezcla el lote con lo que lo rodea. El desvío depende de los vecinos de cada lote y de la época, así que **no sirve un número fijo para todos**: hay que medirlo lote por lote.

## Solución

La misma idea con la que la NASA armó HLS (que Landsat y Sentinel-2 se lean igual), pero hecha para cada lote y cada consulta:

1. Al satélite que rellena se le pide **todo el período** de la consulta (antes, solo el tramo de los huecos), para tener días comparables con la fuente que contestó (HLS).
2. **Pares:** cada observación útil del satélite que rellena, con la observación útil de HLS más cercana a **no más de 1 día** (`AJUSTE_DIAS_PAR`).
3. **Corrimiento del lote** = **mediana** de (satélite − HLS) en los pares a **±10 días** del valor que se ajusta (`AJUSTE_VENTANA_DIAS`). La mediana no se deja llevar por un par raro (una nube parcial, un día de riego). Si en esa ventana no hay 5 pares, se usa la mediana de todos los pares del período.
4. Con **5 pares o más** (`AJUSTE_MIN_PARES`): a cada valor de relleno se le descuenta el corrimiento. La `nota` dice el ajuste, cuántos pares y el valor original, por ejemplo: "ajustado al lote: −0,120 (mediana de 7 pares con HLS a ±1 día), valor original 0,572".
5. Con **menos de 5 pares**: el valor **no se ajusta** y queda `calidad: "dudosa"`, con la `nota` "sin ajuste al lote: solo N pares…".

Vale para cualquier satélite que rellene (Sentinel-2, Sentinel-3, VIIRS, MODIS): el núcleo no nombra satélites. Cada uno se compara contra la fuente que contestó, no contra otro relleno.

Por qué una ventana de ±10 días: el desvío **cambia con la época**. En enero de 2026, los pares de Sentinel-3 contra HLS dieron +0,06 a +0,16 en la primera quincena y −0,08 a +0,03 en la segunda (16 pares; el cultivo vecino y el del lote no crecen al mismo ritmo). Un solo número para todo el mes (mediana +0,044) dejaba los rellenos de principios de mes todavía altos. Supuesto: dentro de ±10 días el corrimiento es aditivo y parejo.

## Costo

Pedir el período completo hace que Sentinel-3 tarde lo de un mes entero (~6 min, spec 050) en vez del tramo de los huecos. Con la spec 052 a 2 días, Sentinel-3 ya entraba casi todos los meses, así que la diferencia es chica.

## Criterios de aceptación

- [x] Los pares toman el HLS más cercano a ±1 día y no cuentan días sin HLS cerca (test `test_pares_toma_el_hls_mas_cercano_a_un_dia`).
- [x] El corrimiento es la mediana de los pares a ±10 días; si no alcanzan, la del período; con menos de 5 pares no hay corrimiento (tests `test_corrimiento_usa_la_ventana_y_la_mediana`, `test_con_pocos_pares_no_hay_corrimiento`).
- [x] El ajuste descuenta el corrimiento, deja el valor original en la nota y, sin pares suficientes, marca `dudosa` sin tocar el valor (test `test_ajustar_descuenta_y_deja_el_original_en_la_nota`).
- [x] De punta a punta: un relleno que lee +0,15 queda igual a HLS (test `test_el_relleno_viene_ajustado_al_lote`).
- [x] A cada respaldo se le pide el período completo; los tests de las specs 012, 041, 043 y 052 siguen en verde.
- [x] Prueba real sobre el lote de San Luis, enero y febrero de 2026 (ver abajo).

## Resultado de la prueba real

28/10/2026, desde la máquina de trabajo, con todos los satélites de la rama de Render más las specs 052 y 056, lote de prueba de San Luis, `POST /consulta` de HLS.

**Enero de 2026**: Sentinel-3 rellenó 4 días (Sentinel-2 no tenía nada útil en los huecos):

| Día | Sentinel-3 original | Ajuste (pares a ±10 días) | Ajustado | HLS de los días vecinos |
|---|---|---|---|---|
| 7/1 | 0,452 | −0,084 (9) | **0,368** | 5/1 0,371 · 11/1 0,414 |
| 10/1 | 0,572 | −0,083 (10) | **0,489** | 11/1 0,414 · 14/1 0,506 |
| 17/1 | 0,615 | −0,031 (9) | **0,584** | 16/1 0,531 · 21/1 0,600 |
| 20/1 | 0,631 | −0,024 (12) | **0,607** | 21/1 0,600 |

Con un solo ajuste para todo el mes (primera versión, mediana de 16 pares, −0,044) los rellenos quedaban en 0,408 · 0,528 · 0,572 · 0,588: los de principios de mes seguían altos. Con la ventana de ±10 días, 3 de los 4 caen entre los HLS vecinos. El 10/1 queda +0,075 sobre el HLS del 11/1: ese día Sentinel-3 ya leía +0,156 contra HLS, más que sus vecinos (una nube fina o una sombra que la máscara no vio, supuesto). El ajuste lo baja pero no lo puede saber.

**Febrero de 2026** (primera versión del ajuste; ese día HLS dio un error 502 de la NASA y contestó Sentinel-2): Sentinel-3 rellenó el 3, 16 y 28/2 con un ajuste de +0,009 (10 pares con Sentinel-2): en febrero los dos ya coinciden.

**Tiempo:** enero tardó entre 9 y 15 minutos (548 y 886 s), más que los ~6 de la spec 052, porque a Sentinel-3 se le pide el mes completo y la nube de la NASA varía de velocidad.
