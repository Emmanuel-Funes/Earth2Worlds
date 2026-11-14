# Spec 041 · Control cruzado: el respaldo revisa al satélite principal

**Estado:** Parte B aprobada por Hernán el 15/10/2026 ("Si, en ese caso necesito el respaldo") y construida; Parte A (control cruzado) propuesta, espera su aprobación · **Etapa:** pipeline satélite → API → app · **Completa:** spec 012 (respaldos en la consulta) y spec 005 (respaldos en orden)

## Objetivo

Usar los respaldos que ya están construidos para **avisar cuando el dato del satélite principal no es confiable**, sin promediar fuentes y sin cambiar ningún número.

Hoy un respaldo solo entra si el principal falla. Si el principal contesta con un dato raro, la app lo recibe como bueno. Con el control cruzado, la app puede pedir que un respaldo lo revise: si los dos se alejan más de lo razonable, el dato del principal sale marcado como `dudosa` y la `nota` dice cuánto dio el otro.

| Antes (spec 012) | Después |
|---|---|
| El respaldo solo contesta si el principal falla | Si la app lo pide, el primer respaldo que contesta también revisa al principal |
| Un dato raro del principal llega como `buena` | Llega como `dudosa`, con el valor del respaldo en la `nota` |
| — | La respuesta trae un resumen del control: con quién se comparó y qué se encontró |

## Por qué no un promedio

Lo decidió Hernán el 15/10/2026 ("Perfecto" a la recomendación del hilo de investigación):

- Las fuentes miran **distinto tamaño de terreno**: HLS ve el lote a 30 m, MODIS a 250 m y CPC a 55 km. Un promedio diluye el dato fino del lote con el de los vecinos.
- Algunas tienen **un sesgo fijo conocido**: VIIRS da el NDVI 0,07 a 0,14 más bajo que HLS. Promediar mete ese sesgo en el dato bueno.
- Se pierde **de dónde salió el dato**: el contrato pide una `fuente` por observación, y un promedio no es de ningún satélite.

Combinar fuentes sigue siendo posible donde se pruebe contra un dato de suelo. Ya se hizo en el balance hídrico: el mínimo diario de POWER e IMERG bajó el error contra SEPA de 54 a 16 mm (spec 024). Una combinación para la lluvia, si se quiere, va en otra spec y validada contra el INTA, no en esta.

## Fuente

No suma ninguna fuente. Usa los satélites y respaldos unidos a la rama, con su `orden=` (spec 005). Todos son de la NASA o de agencias socias.

## Entrada

`POST /consulta` con un campo nuevo **opcional**:

```json
{"satelite": "IMERG", "poligono": {"type": "Polygon", "coordinates": [...]},
 "desde": "2026-01-01", "hasta": "2026-01-14", "control": true}
```

- `control`: `false` si no viene. Así la consulta de hoy sigue igual, con el mismo tiempo de espera, y el frontend de Daniel no tiene que cambiar nada.
- Con `control: true` la consulta tarda lo que tarda el principal **más** lo que tarda un respaldo.

## Proceso

1. Se consulta igual que hoy (spec 012). Si el principal falla y contesta un respaldo, **no hay control**: no hay a quién revisar, y la respuesta lo dice.
2. Si el principal contestó y `control` es `true`, se busca un **testigo**: se prueban sus respaldos en orden y el primero que trae datos de **otra fuente** es el testigo. Si un respaldo queda pendiente, falla, o trae datos con la misma `fuente` que el principal, se pasa al siguiente. Solo hay un testigo, para no multiplicar la espera.
   - **Misma fuente no sirve de testigo:** AppEEARS y SMAP L3 son el mismo satélite SMAP por otro camino (sus observaciones dicen `fuente: "SMAP"`), así que siempre coincidirían. Se reconocen por el campo `fuente` de las observaciones, sin nombrar satélites en el núcleo. Para SMAP, el testigo termina siendo GLDAS.
   - **Testigo mucho más grueso, solo informa:** si la `resolucion_m` del testigo es más de 10 veces la del principal, la comparación se informa en `control` pero **no** baja la calidad. Ejemplo: si Sentinel-2 falla y el testigo del NDVI de HLS (30 m) es VIIRS (500 m), su sesgo fijo de 0,07 a 0,14 marcaría casi todo como dudoso sin que HLS esté mal. Con IMERG (10 km) y POWER (55 km), o SMAP (9 km) y GLDAS (25 km), la relación es menor a 10 y el control sí marca.
3. Se comparan solo los pares que se pueden comparar:
   - la misma `variable` y la misma `fecha`;
   - los dos con valor, y ninguno `descartada`.
   Las variables que el testigo no da (ej. el respaldo FAO-56 da `et0_mm_dia` y no `et_mm_dia`) no se comparan, y la respuesta las lista.
4. La **lluvia** se compara sumada en el período, no día por día. La lluvia por satélite suele caer en el día equivocado: el 13/1/2026 IMERG marcó 22,5 mm y CPC 0, pero los dos vieron la lluvia de esa semana. Comparar por día marcaría casi todo como dudoso.
5. Si la diferencia pasa el umbral de la tabla, las observaciones del principal en ese par:
   - **no cambian de `valor`** (nunca se inventa ni se corrige un número);
   - bajan de `buena` a `dudosa` (las que ya son `dudosa` quedan igual);
   - suman a la `nota`: `"Control cruzado: <testigo> dio <valor> <unidad> (diferencia <d>)"`.
   En la lluvia se marcan todos los días del período, porque la diferencia es del total.

### Umbrales (supuestos, a calibrar con la prueba real)

| Variable | Se marca dudosa si la diferencia supera | Por qué |
|---|---|---|
| `lluvia_mm` (suma del período) | 10 mm **y** el 40 % del mayor de los dos | Las lluvias chicas difieren mucho en %, las grandes en mm |
| `ndvi`, `ndmi` | 0,15 | VIIRS ya difiere 0,07 a 0,14 por sesgo propio; más que eso es otra cosa (nube, sombra) |
| `humedad_superficial`, `humedad_zona_raiz` | 0,10 m³/m³ | Un tercio del rango habitual en San Luis (0,05 a 0,35) |
| `temp_max`, `temp_min` | 3 °C | Error típico de un modelo de clima contra estación |
| `temp_sup_min_c` | 4 °C | VIIRS y MODIS pasan a distinta hora: el 22/9/2026 difirieron 3,1 °C |
| `et_mm_dia` | 1,5 mm/día | La mitad de la ET típica de primavera |
| `altura_media_m` | 10 m | NASADEM y ASTER difieren menos de 1 m en el lote de San Luis |
| Otras | no se comparan | Hasta tener un umbral con fundamento |

Los umbrales viven en una tabla del núcleo, por **variable** (no por satélite), así el núcleo sigue sin nombrar a ningún satélite (spec 009).

## Parte B (aprobada y construida): un principal todo descartado deja pasar al respaldo

Antes, si el principal contestaba pero **todas** sus observaciones vienen `descartada` (ej. HLS con todas las imágenes del mes nubladas), la consulta lo daba por bueno y no probaba los respaldos: la app recibía todo `null`. Hernán lo aprobó el 15/10/2026.

Ahora ese intento cuenta como `sin_datos` y entra el respaldo siguiente, como si el principal hubiera fallado. Si ningún respaldo trae algo útil, se devuelve la primera fuente con sus descartadas y su `nota` (nunca un 502 por esto). Una observación cuenta como descartada si trae `valor: null` o `calidad: "descartada"`; con un solo dato útil, el principal alcanza. El `mensaje` del intento copia la `nota` de la primera descartada (ej. "todas las imágenes nubladas").

Va en la misma rama porque toca el mismo código (`rotaterra/consulta.py`), pero se aprobó por separado: el control cruzado (Parte A, arriba) no depende de esto. También cambia la regla de la spec 012, que se actualizó en el mismo PR.

Efecto en fuentes reales: HLS todo nublado → Sentinel-2/VIIRS/MODIS; GRACE con todas las semanas sin publicar → mascons de JPL; SEPA con el INTA caído → balance hídrico propio. Las fuentes sin respaldo (GOES-19, MAGyP) siguen devolviendo sus descartadas como hasta ahora.

(Idea traída del hilo "Conexión satélites a la app", que había abierto una spec parecida, PR #56, ya cerrado.)

### Resultado de la prueba real (Parte B)

15/10/2026, workflow "Probar respaldo si el principal viene todo descartado (spec 041)" (run 38820685773, rama `PRUEBA-respaldo_si_todo_descartado`, con el mismo código que publica Render), lote de San Luis (-33,700 a -33,705; -65,295 a -65,300), NASA real.

- HLS en enero y febrero de 2026: 25 días con imagen, 19 con dato y **6 todo descartados** por nubes (18/1, 29/1, 6/2, 10/2, 12/2 y 14/2).
- **Tramo del 8 al 16/2/2026**, sin ninguna pasada limpia de HLS (3 pasadas, la mejor con 2 % de píxeles limpios): antes la app recibía todo `null`. Ahora el intento de HLS sale `sin_datos` y **contesta Sentinel-2**: NDVI **0,723** (`buena`) y NDMI 0,216, más una pasada con el lote parcialmente cubierto (NDVI 0,531, `dudosa`).
- **Días sueltos nublados** (18/1 y 29/1): se prueban Sentinel-2, VIIRS y MODIS en orden, y ninguno tiene dato útil. Sentinel-2 también estaba nublado o no pasó, y VIIRS (8 días) y MODIS (16 días) son compuestos que no caen en un solo día. La app recibe las descartadas de HLS con su nota, sin error.
- **Día con dato** (1/1/2026): contesta HLS como siempre (NDVI 0,322) y no se pide ningún respaldo.

Conclusión: la regla funciona con datos reales. El respaldo ayuda cuando el período pedido es de varios días; en un día suelto nublado lo normal es que tampoco haya otro satélite con dato.

## Salida

La respuesta de `/consulta` suma un bloque `control` (vale `null` si no se pidió):

```json
{
  "fuente_usada": "IMERG",
  "observaciones": [ ... ],
  "intentos": [ ... ],
  "control": {
    "testigo": "IMERG:POWER",
    "comparados": 1,
    "discrepancias": [
      {"variable": "lluvia_mm", "desde": "2026-01-01", "hasta": "2026-01-14",
       "principal": 32.0, "testigo": 13.6, "diferencia": 18.4, "umbral": "10 mm y 40 %"}
    ],
    "sin_comparar": [],
    "mensaje": "El total de lluvia de IMERG se aleja del de POWER: los días quedan como dudosos"
  }
}
```

Si no hubo testigo, `control.testigo` es `null` y `mensaje` dice por qué (el principal falló, o ningún respaldo trajo datos).

## Reglas de calidad

- Nunca se cambia un `valor`. El control solo baja la `calidad` y agrega a la `nota`.
- Nunca sube una calidad: un dato `dudosa` o `descartada` queda igual.
- Las observaciones del testigo **no** se devuelven como datos del lote; solo aparecen en el resumen `control`.
- Un respaldo regional (GLDAS, FLDAS, HWSD) sirve de testigo, pero la nota aclara que es regional.

## Qué se toca

Es un cambio del **núcleo**, no de un satélite: `rotaterra/consulta.py` (el control), `rotaterra/api.py` (el campo `control` del pedido y de la respuesta) y la tabla de umbrales. Ningún satélite cambia. Rama `NUCLEO-control_cruzado`, sobre `NUCLEO-api_publicada_con_clave` (PR #38).

## Criterios de aceptación

- [ ] Sin `control`, `/consulta` responde exactamente igual que hoy (mismos campos, más `control: null`).
- [ ] Con `control: true` y el principal OK, el primer respaldo con datos de otra `fuente` queda como testigo; uno pendiente, caído o de la misma fuente se saltea.
- [ ] Un testigo con resolución más de 10 veces más gruesa que el principal solo informa y no baja la calidad.
- [x] (Parte B) Un principal con todas sus observaciones `descartada` deja pasar al respaldo; si nadie trae nada útil, vuelve la primera fuente con sus descartadas. Verificado sin internet: 5 tests nuevos en `tests/test_consulta.py` (20 en total en ese archivo), y la suite completa con los 39 PRs unidos da 841 verdes.
- [x] (Parte B) Prueba real con HLS en un período todo nublado sobre el lote de San Luis. Ver "Resultado de la prueba real (Parte B)".
- [ ] Con el principal caído, no hay control y `control.mensaje` lo dice.
- [ ] Una diferencia mayor al umbral baja `buena` a `dudosa` y suma la nota; el `valor` no cambia.
- [ ] La lluvia se compara sumada en el período.
- [ ] Las variables sin umbral o sin par en el testigo quedan en `sin_comparar`.
- [ ] Tests sin internet con satélites simulados, y `tests/test_nucleo.py` sigue verde (el núcleo no nombra satélites).
- [ ] Prueba real en el lote de San Luis con IMERG (1 al 14/1/2026), HLS (enero 2026) y NASADEM, anotando acá los valores, el testigo de cada uno, las discrepancias y cuánto se alarga la espera.
- [ ] Umbrales revisados con los números de la prueba real antes de publicarlo en Render.
- [ ] Hernán aprobó la spec.

## Preguntas abiertas para Hernán

1. ¿Los umbrales de la tabla te parecen bien para arrancar? Se ajustan con la prueba real.
2. Para la lluvia, el primer respaldo es POWER, que es un modelo. ¿Preferís que el testigo de la lluvia sea CPC, que sale de pluviómetros? Es cambiar el orden de los respaldos de IMERG, y la pregunta ya quedó abierta en la spec 029.
