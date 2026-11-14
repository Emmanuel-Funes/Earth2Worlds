# Spec 034 · Clima de la campaña con NASA POWER (heladas, lluvia esperada, grados-día y suelo para sembrar)

**Estado:** aprobada por Hernán ("Ok a los 3", con 0 °C como umbral de helada) · **Origen:** investigación 033 · **Rama:** `POWER-clima_de_campana`

## 1. Objetivo

Darle al motor de recomendación (spec 027) los datos de clima histórico que hoy le faltan, calculados con 35 años de NASA POWER sobre el lote:

- los días libres de heladas, que piden las reglas del maní (≥ 120) y del algodón (≥ 150);
- las fechas de helada con riesgo del 20 %;
- la lluvia esperada de octubre a marzo;
- los grados-día de la campaña;
- la fecha en que el suelo supera 14 °C de forma sostenida.

## 2. Fuente

| | |
|---|---|
| Principal | NASA POWER, API diaria por punto (`/api/temporal/daily/point`, comunidad `AG`), sin cuenta |
| Parámetros | `T2M_MIN`, `T2M_MAX` y `PRECTOTCORR` (1991-2025); `TSOIL1` (0-10 cm, 2001-2025) |
| Resolución | Celda de ~0,5° (MERRA-2): es un dato **regional** |
| Respaldo | MERRA-2 horario (`M2T1NXSLV`, `T2M`) por el servicio de series de tiempo de Giovanni (`api.giovanni.earthdata.nasa.gov/timeseries`, GES DISC, con el token de Earthdata), en 7 tramos de 5 años. Da la mínima y la máxima de cada día UTC. Solo da heladas y grados-día; la lluvia y el suelo quedan sin respaldo y salen descartados. El servicio viejo de GES DISC (`hydro1…/timeseries.cgi`) hoy devuelve una página web, por eso no se usa. POWER toma su meteorología de MERRA-2, así que el respaldo protege de una caída del servidor de POWER, no da una mirada independiente |
| Verificado | 15/10/2026, corrida real: POWER respondió en 1,3 s y MERRA-2 por Giovanni en 16 s |

## 3. Entrada

El polígono del lote. Se usa su centro. No hace falta fecha: es una climatología, y siempre usa los 35 años completos más recientes.

## 4. Proceso

1. Pedir a POWER la serie diaria del centro del lote.
2. **Heladas:** para cada campaña de 1991/92 a 2024/25, se toman la última helada de primavera (julio a diciembre) y la primera de otoño (enero a junio del año siguiente). Una helada es un día con mínima ≤ 0 °C. Se calcula también con ≤ −2 °C, que va en la `nota`.
3. **Días libres de heladas** = días entre esas dos fechas. Se informan la mediana y el valor que se supera en 8 de cada 10 años (percentil 20). Este segundo valor es el que usa el motor, porque es el conservador.
4. **Lluvia de octubre a marzo:** mediana, año seco (percentil 20) y año húmedo (percentil 80).
5. **Grados-día base 10 °C** de octubre a marzo: la mediana.
6. **Suelo para sembrar:** la primera fecha después del 15/7 en que `TSOIL1` queda 10 días seguidos ≥ 10 °C y ≥ 14 °C. Se informan la mediana y la fecha al 80 %.

## 5. Salida

Lista de `Observacion`, todas con `fuente: "POWER"`, `resolucion_m: 55000`, `calidad: "buena"` y la `fecha` del último día usado (31/12/2025).

| `variable` | `unidad` | Ejemplo del lote de San Luis |
|---|---|---|
| `dias_libres_heladas` | días | 257 (8 de cada 10 años; mediana 282 en la `nota`) |
| `ultima_helada_primavera_p80` | día del año | 250 (7/9) |
| `primera_helada_otono_p20` | día del año | 136 (16/5) |
| `lluvia_campana_mm_p50` | mm | 597 |
| `lluvia_campana_mm_p20` | mm | 507 |
| `grados_dia_campana` | °C·día | 2128 |
| `suelo_14c_fecha_mediana` | día del año | 278 (5/10) |

La `nota` de cada dato explica que es aire a 2 m (o suelo de 0-10 cm), que es regional y cuántos años se usaron.

## 6. Cambios en el motor (spec 027)

- **Perfil:** suma `dias_libres_heladas` desde `dias_libres_heladas` (escala regional).
- **Regla de heladas:** hoy queda en "faltan datos". Con el dato regional queda en `cumple_regional` o `sin_dato_del_lote`, igual que el pH regional. Un dato regional nunca descarta un cultivo.
- **Riesgos:** suma la lluvia esperada contra la demanda del catálogo, solo como texto. El método de comparación sigue abierto (decisión 6 de la spec 027).

## 7. Reglas de calidad

- POWER marca con −999 el día sin dato. Para las heladas, una campaña con más del 5 % de días sin dato no cuenta. Para las sumas (lluvia y grados-día), la campaña tiene que estar completa, porque un día faltante achicaría la suma sin avisar. Si quedan menos de 20 campañas, el dato sale `dudosa` y la `nota` dice cuántas hubo.
- Si POWER no devuelve la temperatura del suelo, el resto del clima sale igual y el dato del suelo sale descartado con el motivo.
- Nunca se inventa una fecha: sin heladas en una temporada se usa el borde de la temporada (1/7 o 30/6), y la `nota` lo dice.

## 8. Pruebas

- **Sin internet** (`tests/test_power_campana.py`, 20 pruebas): una serie sintética con heladas conocidas da los días libres y los percentiles esperados; sin heladas se usa el borde; los datos −999 se descartan; con pocas campañas el dato sale `dudosa`; el suelo caído no frena el resto; el respaldo de MERRA-2 simulado da heladas y grados-día.
- **Real:** workflow `Probar POWER (clima de la campaña)` con el lote de San Luis (`probar_power_campana.py`). Endpoints de prueba: `GET /clima-campana` y `GET /clima-campana/merra2`, con `lat` y `lon`. En `/consulta` el satélite se llama `POWER_CAMPANA` y su respaldo `POWER_CAMPANA:MERRA2`.

## 9. Criterios de aceptación

- [x] Con el lote de San Luis, `dias_libres_heladas` da 257 (percentil 20) y la mediana de 282 figura en la `nota`, como en la investigación 033. Corrida 38660394067: 257 y 282; última helada al 80 % el 7/9 (día 250), primera de otoño al 20 % el 16/5 (día 136); con −2 °C, mediana 307 días.
- [x] La lluvia de octubre a marzo da 597 mm de mediana y 507 mm en año seco. Corrida 38660394067: 597 y 507 mm (año húmedo 741, rango 460 a 978). Grados-día 2128 y suelo a 14 °C el 5/10 (día 278).
- [x] El motor pasa la regla de heladas del maní y del algodón de "faltan datos" a "cumple (regional)". Verificado con la prueba sin internet del motor usando el valor real de 257 días (rama `MOTOR-recomendacion_de_cultivos`).
- [x] `pytest` pasa sin internet (61 pruebas de la rama).
- [x] El workflow real pasa: corrida real. El respaldo de MERRA-2 dio los mismos días libres y fechas de helada que POWER (257, 7/9 y 16/5) y 2158 grados-día (+30).
- [x] Hernán aprobó esta spec ("Ok a los 3").

## 10. Preguntas abiertas

- ~~¿El umbral de helada para el motor es 0 °C o −2 °C?~~ Hernán aprobó 0 °C.
- El algodón pasa la regla de heladas, pero en San Luis no es un cultivo de la zona. ¿Hace falta una regla de grados-día? Es una pregunta para Leandro o el agrónomo.

## 11. Parte B · Calor, lluvias extremas y racha seca

**Aprobada por:** Hernán ("Vamos con la partes de satelites y obtencion de datos que es lo mio, avancemos", sobre los faltantes del desafío Field Shift: estrés por calor, lluvias extremas y tendencias largas). Usa las mismas series de POWER que ya se piden: **no agrega ningún pedido**.

| `variable` | `unidad` | Qué es |
|---|---|---|
| `dias_calor_35_anio` | días | Días por año con máxima del aire ≥ 35 °C (estrés por calor en floración) |
| `dias_lluvia_extrema_50_anio` | días | Días por año con lluvia ≥ 50 mm |
| `racha_seca_campana_dias` | días | Racha más larga de días seguidos con menos de 1 mm, de octubre a marzo |

- Valor = mediana de los años. La nota suma el año malo (1 de cada 5 años, percentil 80), el máximo con su año y la **tendencia**: promedio de los primeros 10 años contra los últimos 10.
- Un año (o campaña) con más del 5 % de días sin dato no cuenta.
- POWER suaviza las tormentas en su celda de ~50 km: la lluvia extrema es un piso, y la nota lo dice.
- El respaldo MERRA-2 da el calor (tiene la máxima) y deja la lluvia extrema y la racha `descartada`, como ya pasa con la lluvia.
- Para el futuro de los mismos indicadores está la spec 058 (NEX-GDDP-CMIP6).

**Prueba real** (`probar_power_campana.py -33.7025 -65.2975`, 29 s con el respaldo):

| Indicador | Mediana 1991-2025 | 1 de cada 5 años | Máximo | 1991-2000 → 2016-2025 |
|---|---|---|---|---|
| Días ≥ 35 °C | **24** | 31 o más | 44 en 2025 | **15,2 → 31,9** |
| Días con lluvia ≥ 50 mm | 1 | 1 o más | 3 en 2024 | 0,7 → 1,0 |
| Racha seca oct-mar | 14 días | 17 o más | 24 en 2003 | 12,7 → 14,2 (1991-2000 → 2015-2024) |

MERRA-2 da los mismos 24 días de calor (diferencia 0). **Lectura:** los días de calor fuerte **se duplicaron** entre la primera y la última década. Es el dato medido que respalda la proyección de la spec 058 (38 a 43 días a 2041-2060).

- [x] Tests sin internet (63 de la rama, 2 nuevos: extremos y tendencia).
- [x] Prueba real con POWER y MERRA-2.
