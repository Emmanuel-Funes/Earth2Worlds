# Spec 064: Motor de recomendación para agrónomos

**Estado:** implementado en rama, sin merge ni Render (14/11/2026, durante el hackatón)
**Pedido por:** Hernán, 14/11/2026: "Este sería el motor de recomendación para agrónomos; luego tendríamos otro motor de rotación completo como ya lo teníamos".
**Base:** ficha técnica de los 5 cultivos (14/11/2026) y el criterio agronómico del equipo (14/11/2026).

## 1. Qué hace

Toma **un lote y una campaña**. Para cada cultivo (maíz de primera, maíz tardío, soja, sorgo, maní y girasol) dice si es
**Recomendable**, **Con cuidado** o **No recomendable**, y lista cada regla de la ficha con:

- el dato del lote;
- el umbral;
- la fuente;
- el resultado: ok, aviso, no o sin dato.

**Qué no hace:** no arma rotaciones de varios años. Eso sigue siendo el motor de rotación (spec 062), que no cambia.

## 2. Entrada

`POST /agronomos/recomendacion`, con la misma X-API-Key que el resto de la API.

| Campo | Qué es |
|---|---|
| `latitud`, `longitud` | Ubicación del lote. |
| `sistema` | `secano` o `riego`. Con riego se carga también `riego_mm_campana`. |
| `textura`, `capas_textura`, `profundidad_cm` | Si no vienen, salen de las `observaciones` de `POST /consulta` (GeoINTA por capas). |
| `analisis_suelo` | `ph`, `laboratorio`, `fecha`, `ce_ds_m` y `arcilla_pct`. |
| `agua_util_siembra_pct` | Agua útil medida a la siembra. Si viene, manda sobre la estimada. Si no, `agua_util_mayo_pct` arranca el balance. |
| `fechas_siembra` | Fecha por cultivo, `"MM-DD"`. Si falta, se usa la fecha típica del catálogo. |
| `cultivos` | Qué cultivos evaluar. |
| `power` | Serie diaria de NASA POWER. Si no viene, la API la pide y espera. |

## 3. Reglas

Todas las reglas y sus fuentes están en `rotaterra/agronomos/catalogo_agronomos.json`.

Cada regla se evalúa en **todas las campañas de la serie** (1991/92 a 2024/25) y se cuenta en cuántas se cumple. "Aviso" quiere decir que falla en 1 de cada 5 campañas o más, la misma regla de presentación del motor de rotación.

| # | Regla | Qué mira | Resultado | Fuente |
|---|---|---|---|---|
| 1 | Temperatura del suelo | Los 3 días antes de la siembra con TSOIL1 (0–10 cm) por encima del mínimo. Da la fecha desde la que se cumple en 8 de cada 10 campañas. | Aviso. Descarta si ni al 31/01 se cumple en la mitad de las campañas. | Criterio agronómico del equipo; INTA San Luis IT 183 (sorgo); ASAGIR (girasol) |
| 2 | Grados día | Suma ((Tmáx+Tmín)/2 − Tb), con Tmáx tope 30 °C en maíz, hasta el ciclo mínimo, antes de una helada que mata o del 30/04. | Aviso | Criterio agronómico del equipo (totales); Tb: MAIZAR, UNRC, INTA SL, ASAGIR |
| 3 | Humedad a la siembra | % del agua útil **de 2 a 8 cm** (Hernán, 14/11): la medida o un balance diario de la capa de 0 a 8 cm (lluvia y evaporación de barbecho con rastrojo, Ke 0,9, FAO-56). Como se siembra después de una lluvia, mira si hay al menos un día con humedad suficiente en los 15 días antes o después de la fecha. | Aviso | Criterio agronómico del equipo (sin fuente publicada) |
| 4 | Agua del ciclo | Agua útil a la siembra + lluvia del ciclo + riego, contra el 60 % de la demanda. | Descarta en secano si no llega en el año medio. Avisa si falla en 3 de cada 10 campañas. | Criterio agronómico del equipo; descarte confirmado por Hernán (14/11) |
| 5 | Textura y profundidad | Arenoso de 0 a 30 cm en maíz y soja de secano (solo la clase arenoso, código 1 de GeoINTA; areno franco no descarta, Hernán 14/11); maní con más de 35 % de arcilla (franco arcilloso avisa); girasol con menos de 40 cm de suelo. | Descarta | Criterio agronómico del equipo; definido por Hernán; ASAGIR (profundidad) |
| 6 | pH | Regla escalonada del motor de rotación (`ph_del_lote.evaluar_ph`): el laboratorio decide, el mapa solo avisa, tolerancia de 0,3. | Descarta o avisa | FAO Ecocrop; UNLP; INTA |
| 7 | Sales | Maíz con más de 2 dS/m. Soja con más de 0,5 dS/m y pH mayor de 8. | Aviso | INTA SL IT 188; INTA Marcos Juárez |
| 8 | Helada y calor | Helada en los 20 días después de sembrar; días de más de 35 °C en el período crítico. | Riesgo del clima: no cambia el estado | INTA Ascasubi BT 36; Riglos 2023; INTA SL IT 183 (sorgo, 38 °C) |

Hay dos datos que no coincidían con lo publicado. Hernán los decidió el 14/11

- **Temperatura base del maní:** 11 °C (UNRC). Decidido por Hernán el 14/11; el documento proponía 15 °C.
- **Grados día del girasol:** 1.600–1.700 °Cd de ASAGIR. Decidido por Hernán el 14/11; el documento proponía 1.300–1.550.

## 4. Límites

- **TSOIL1** es una media diaria de un modelo (MERRA-2). No es la medida que se toma a las 10 de la mañana en el lote.
- **Humedad estimada:** el balance de la capa de siembra es simple (sin escurrimiento ni ascenso desde abajo). Conviene cargar la humedad medida de 2 a 8 cm.
- **Floración:** se ubica con una fracción de los grados día del ciclo. Es aproximada.
- **Sin dato de San Luis:** sorgo, maní y girasol no tienen umbral argentino de sales.

## 5. Prueba con un lote real

Lote cerca de Villa Mercedes (−33,70; −65,42). Franco arenoso, 120 cm, pH 7,9 de laboratorio. NASA POWER, 34 campañas.

| Estado | Cultivos |
|---|---|
| Recomendable | Maíz de primera y maíz tardío |
| Con cuidado | Soja, sorgo, girasol y maní (por pH, según los rangos de la UNLP) |

En el maní además avisa el suelo frío al 05/11. Los 18 °C se dan en 8 de cada 10 campañas desde el 20/11. En el sorgo, los 18 °C también llegan desde el 20/11, y la guía del INTA San Luis dice "desde la 1ª quincena de noviembre".

## 6. Pruebas

`tests/test_agronomos.py`: 23 casos con clima sintético (lluvia en pulsos semanales).

## 7. Cambios con la tabla final del equipo (14/11/2026)

Tabla de parámetros duros por cultivo. Se cargó en `catalogo_agronomos.json` (fuente `criterio_agronomico_equipo`):

- **Temperatura del suelo:** se agrega el óptimo de cada cultivo como dato (maíz 22, soja 22, sorgo 19, maní 28 y girasol 15 °C). El mínimo del maní queda en 18 °C, el valor que ya estaba (Hernán: conservar los datos anteriores y agregar solo lo nuevo); la tabla proponía 16 °C.
- **Calor por cultivo, con temperatura letal:**

  | Cultivo | Umbral | Letal |
  |---|---|---|
  | Maíz | >35 °C | 45 °C |
  | Soja | >35 °C, 2 días seguidos | 38 °C |
  | Sorgo | >38 °C | 40 °C |
  | Maní | >36 °C | 39 °C |
  | Girasol | >35 °C, 3 días seguidos | 45 °C |

  Sigue siendo un riesgo del clima y no cambia el estado.
- **Agua del ciclo:** se agregan el óptimo y el máximo. Si el año medio pasa el máximo, avisa por exceso.
- **pH:** mínimo y máximo de la tabla (maíz 5,0–8,5; soja 5,0–8,4; sorgo 5,0–8,8; maní 5,5–8,5; girasol 5,5–8,7), con la misma tolerancia de 0,3. Reemplazan a los topes de FAO Ecocrop **solo en este motor**.
- **Regla 1 en 3 (no repetir la especie):** maíz, soja, sorgo y girasol con 2 campañas libres; maní con 3. Usa el nuevo campo `historial`. Si no hay historial, la regla queda como "falta el dato".
- **Texturas:** coinciden con lo que ya estaba. La fuente OpenLandMap sigue rechazada, y la textura sale de GeoINTA o del análisis del productor.
- **Temperaturas base y grados día:** quedan los anteriores con las decisiones de Hernán (maní Tb 11; girasol 1.600–1.700 de ASAGIR). No se usan los de la tabla final (maíz Tb 10; sorgo 10,6; maní 13,3; girasol 1.300 con Tb 6).

## 8. Fuentes sin nombres de personas (Hernán, 14/11/2026)

En el motor ya no aparecen nombres de personas como fuente. Los datos del equipo quedan con la fuente publicada que los respalda
cuando el valor coincide (INTA San Luis IT 183 para el calor del sorgo, ASAGIR para el suelo del girasol, Riglos 2023 para el calor
del maíz, MAIZAR/UNRC para las temperaturas base). Lo que ningún documento publicado respalda queda como
"Criterio agronómico del equipo Rotaterra, sin fuente publicada". No se atribuye al INTA nada que el INTA no publicó.
