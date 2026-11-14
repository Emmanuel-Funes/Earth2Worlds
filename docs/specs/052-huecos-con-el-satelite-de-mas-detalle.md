# Spec 052 · Los huecos largos del NDVI los rellena el satélite de más detalle que haya pasado

**Estado:** pedida por Hernán ("lo que yo pedía es que traiga el que más cercano de la tierra nos dé el resultado, así también considerar cada cuánto tiempo pasa"); umbral elegido por Hernán: **más de 2 días** ("Rellenar huecos con más de 2 días") · **Etapa:** núcleo (consulta en el momento) · **Rama:** `NUCLEO-rellenar_huecos_por_detalle` · **Depende de:** `TIEMPO_REAL-datos_del_dia` (spec 043)

## Objetivo

Hoy la consulta (spec 012) usa **un solo satélite**: si HLS trae algún dato útil, la respuesta es HLS aunque el lote haya quedado 20 días seguidos nublado en el medio. Los respaldos solo entran si HLS no trae nada (spec 041 B), y los del día solo completan la cola (spec 043, que dejó explícito "no se rellenan huecos del medio").

Hernán pide que, día por día, el dato venga del satélite **que más detalle da del suelo** y que se tenga en cuenta **cada cuánto pasa** cada uno. Con esta spec, cuando el lote se queda **más de 2 días seguidos** sin un NDVI útil, ese hueco lo rellena el siguiente satélite de la cadena que sí haya pasado despejado, en orden de detalle:

| Orden | Satélite | Detalle | Cada cuánto pasa por el lote |
|---|---|---|---|
| principal | HLS | 30 m | 2-3 días (Landsat + Sentinel-2) |
| 1 | Sentinel-2 | 10 m | 2-5 días |
| 2 | Sentinel-3 | 300 m | todos los días (3A + 3B) |
| 3 | VIIRS | 500 m | compuesto de 16 días |
| 4 | MODIS | 250 m | compuesto de 16 días, fin de misión |

**Nunca se promedia** (decisión de Hernán del 15/10, spec 041): cada día queda con una sola fuente, y cada observación dice cuál.

## Por qué 2 días

Hernán eligió 2 días. La tarjeta proponía 5 (el NDVI cambia lento y Sentinel-3 tarda ~6 min por mes); con 2, la serie queda casi sin huecos a cambio de una consulta más lenta (ver la prueba real). El número vive en `HUECO_MAXIMO_DIAS` y se cambia en una línea.

## Proceso

1. Igual que antes: el principal contesta, o el primer respaldo que traiga algo (specs 012 y 041).
2. **Nuevo:** para cada variable de `HUECO_MAXIMO_DIAS` (`ndvi` y `ndmi`, 2 días), buscar los tramos de más de 2 días seguidos sin dato útil dentro del período, contando el principio y el final.
3. Pedirle al **siguiente** satélite de la cadena (el que viene después del que contestó) **solo el tramo** entre el primer y el último hueco. De lo que trae se toma solo lo que cae dentro de un hueco; un día que ya tiene dato no se toca.
4. Recalcular los huecos y seguir con el siguiente satélite mientras queden huecos largos. Un satélite caído o sin datos deja el hueco para el que sigue.
5. Después, como siempre, los respaldos del día completan la cola (spec 043).

El núcleo sigue sin nombrar satélites: usa el orden que cada uno declara (`orden=`) y nombra solo variables, como ya hace `PRIORIDAD_POR_VARIABLE`.

## Salida

La respuesta de `POST /consulta` suma `rellenada_con`: la lista de respaldos que rellenaron huecos (vacía si no hizo falta). Cada uno aparece en `intentos` con `resultado: "relleno"` y un mensaje como "rellenó 10 días de huecos entre el 2026-01-16 y el 2026-01-25". `fuente_usada` sigue siendo el satélite que contestó primero.

## Criterios de aceptación

- [x] Los huecos se cuentan al principio, en el medio y al final; un dato cada 5 días no deja huecos (test `test_huecos_cuenta_principio_medio_y_final`).
- [x] Un hueco largo lo rellena primero el de más detalle y solo ahí; lo que sigue faltando lo rellena el siguiente; a cada uno se le pide solo el tramo (test `test_hueco_largo_lo_rellena_el_de_mas_detalle_y_solo_ahi`).
- [x] Sin huecos largos no se pide ningún respaldo; las variables sin regla (clima, lluvia, etc.) no cambian (tests `test_sin_huecos_largos_no_se_pide_ningun_respaldo`, `test_variable_sin_regla_de_huecos_no_se_rellena`).
- [x] Un respaldo caído deja el hueco al siguiente; si contestó un respaldo, rellenan solo los que vienen después (tests `test_respaldo_caido_deja_el_hueco_para_el_siguiente`, `test_si_contesto_un_respaldo_rellenan_solo_los_que_vienen_despues`).
- [x] La API devuelve `rellenada_con` (test `test_api_dice_quien_relleno`).
- [x] Los tests de siempre de la consulta siguen en verde (spec 012, 041 B y 043).
- [x] Prueba real sobre el lote de San Luis con todos los satélites (ver abajo).

## Resultado de la prueba real

**Con 2 días (lo elegido)**, mismo lote y método:

- **Enero de 2026** (372 s, antes 133 s): HLS 12 días; Sentinel-2 no tenía nada útil en los huecos; **Sentinel-3 rellenó el 7, 10, 17 y 20/1** (0,452 · 0,572 · 0,615 · 0,631). VIIRS cortó la conexión (error, no frenó nada) y MODIS no tenía nada.
- **Febrero de 2026** (433 s, antes 111 s): **Sentinel-2 rellenó el 10 y 12/2; Sentinel-3 el 3, 16 y 28/2** (0,666 · 0,798 · 0,775). Quedan 12 días con dato contra 7 de HLS solo.
- **Ojo agronómico:** en enero Sentinel-3 da NDVI más alto que el HLS de los días vecinos (10/1 0,572 contra 0,414 el 11/1 en HLS; 17/1 0,615 contra 0,531 el 16/1): +0,08 a +0,16, como ya se vio en la spec 050 (+0,08 el 1/1). La serie mezclada muestra saltos que no son del cultivo; cada punto dice su fuente para poder separarlos. En febrero la diferencia es chica (16/2 0,798 contra 0,783 el 17/2).

**Primera prueba, con 5 días**:

Desde la máquina de trabajo (entorno con acceso a la NASA), con todos los satélites de la rama de Render más esta spec, lote de prueba de San Luis (-33,700/-65,300 a -33,705/-65,295), `POST /consulta` de HLS:

- **Enero de 2026** (133 s): HLS tuvo 12 días con dato; el hueco más largo fue del 6 al 10/1 (5 días, dentro del margen). **No se pidió ningún respaldo**: la consulta tardó lo mismo que antes.
- **Febrero de 2026** (111 s): HLS quedó nublado del 8 al 16/2 (9 días). **Sentinel-2 rellenó el 10/2 (NDVI 0,723, `buena`) y el 12/2 (0,531, `dudosa`)**; los huecos que quedaron (13-16/2 y 26-28/2) son de 4 y 3 días, así que Sentinel-3, VIIRS y MODIS no hicieron falta. Resultado: 7 días de HLS + 2 de Sentinel-2, cada uno con su fuente.
