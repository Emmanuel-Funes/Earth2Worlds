# Spec 039 · El Niño / La Niña de NOAA CPC como aviso de la campaña

**Estado:** aprobada por Hernán ("Ok a los 3") · **Origen:** investigación 033, propuesta aprobada con "Todo" · **Rama:** `NOAA-el_nino_la_nina` · Se escribió como spec 035; pasó a 039 porque la 035 también la usa el respaldo de heladas de MODIS

## 1. Objetivo

Que el motor de recomendación (spec 027) avise en qué fase del Pacífico arranca la campaña: El Niño, La Niña o neutral, con su intensidad y la probabilidad que da NOAA. Es un **aviso**: no cambia la viabilidad de ningún cultivo.

En la región pampeana, El Niño suele venir con más lluvia de primavera y verano, y La Niña con menos. Para el productor de San Luis es el dato de largo plazo que más pesa al planificar la campaña de verano.

## 2. Fuente

| | |
|---|---|
| Principal | NOAA Climate Prediction Center (agencia socia permitida, spec 008) |
| Índice | ONI (Oceanic Niño Index): anomalía de temperatura del mar en la región Niño 3.4, en trimestres móviles. `https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt`, texto plano, sin cuenta |
| Pronóstico | La sinopsis de la discusión oficial de ENSO, que se publica el segundo jueves de cada mes: `https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml` |
| Respaldo | El índice Niño 3.4 mensual de NOAA PSL (`https://psl.noaa.gov/data/correlation/nina34.anom.data`). Es otro servidor de NOAA. Probado: responde, y su pie dice **ERSST V6, anomalía frente a 1981-2010** (no V5 como se suponía); la `nota` copia lo que diga el pie. La alternativa `psl.noaa.gov/gcos_wgsp/Timeseries/Data/nino34.long.anom.data` da 404, así que quedó la primera |
| Escala | Un solo valor para todo el planeta: no depende del lote |
| Verificado | 14/10/2026 (investigación 033) y 15/10/2026 (prueba real): ONI de jul-sep 2026 = **+2,16**. La sinopsis de NOAA dice que El Niño será fuerte a muy fuerte hasta enero-marzo de 2027, con más de 83 % de probabilidad |

## 3. Entrada

El pedido de cualquier satélite (lote y período), para respetar el contrato. El índice no depende del lote; el `lote_id` se copia a la salida. El lugar y el período pedidos se ignoran: siempre sale el último dato publicado.

## 4. Proceso

1. Bajar `oni.ascii.txt` y tomar el último trimestre publicado (columnas `SEAS`, `YR`, `ANOM`).
2. Clasificar con los umbrales de NOAA: ONI ≥ +0,5 es El Niño y ≤ −0,5 es La Niña; si no, neutral. Intensidad por el valor absoluto: débil hasta 0,9, moderado de 1,0 a 1,4, fuerte de 1,5 a 1,9 y muy fuerte desde 2,0. Como hace NOAA, el ONI se redondea a un decimal antes de clasificar (+0,45 ya es El Niño débil). La lógica está en funciones puras (`fase(oni)`, `intensidad(oni)`) que el motor puede copiar: devuelven, por ejemplo, "El Niño muy fuerte", "La Niña moderada" o "neutral".
3. Bajar la discusión y extraer la sinopsis (el párrafo que empieza con "Synopsis:"), el estado de alerta ("ENSO Alert System Status") y la fecha de publicación ("issued by CLIMATE PREDICTION CENTER … 8 October 2026"). Si no se puede leer, el índice igual sale, sin pronóstico, y la `nota` lo dice.
   - No hay traductor: la `nota` arma un resumen en castellano con datos estructurados. El estado de alerta se traduce con un mapa fijo ("El Niño Advisory" → "Aviso de El Niño", "La Niña Advisory" → "Aviso de La Niña", "El Niño Watch" → "Vigilancia de El Niño", "La Niña Watch" → "Vigilancia de La Niña", "Final El Niño/La Niña Advisory" → "Aviso final de El Niño/La Niña", "Not Active" → "Sin alerta"). La probabilidad y su período se sacan de la sinopsis con una expresión regular ("greater than an 83% chance" → "más de 83 %"; "through January-March 2027" → "hasta ene-mar 2027"). La sinopsis original va entre comillas, en inglés.
4. Si CPC no da el índice, usar el respaldo de PSL: el promedio de los tres últimos meses publicados (tienen que ser seguidos; si no, sale descartado). PSL usa otra base de anomalías (1981-2010) que el ONI (bases móviles de 30 años), así que da valores parecidos pero no iguales. El respaldo también intenta leer la discusión de CPC para sumar el pronóstico.

## 5. Salida

Una `Observacion`:

| Campo | Valor en el ejemplo |
|---|---|
| `variable` | `enso_oni` |
| `valor` | 2.16 |
| `unidad` | °C (anomalía) |
| `fuente` | `CPC` (el mismo nombre que usa la lluvia de CPC) |
| `fecha` | último día del trimestre (30/9/2026 para jul-sep); en el respaldo, último día del último mes usado |
| `resolucion_m` | 0 (índice global, no tiene píxel) |
| `calidad` | `buena`; `dudosa` si salió del respaldo o si el último trimestre terminó hace más de 3 meses |
| `nota` | "El Niño muy fuerte (ONI jul-sep 2026: +2,16 °C, trimestre JAS 2026). NOAA CPC, discusión: Aviso de El Niño; probabilidad de más de 83 % hasta ene-mar 2027. Sinopsis original: "El Niño continues to strengthen, …". Índice del Pacífico, no del lote." |

En el conector (`rotaterra/fuentes/noaa_enso.py`): principal `NOAA_ENSO` (ONI de CPC + discusión) y respaldo `NOAA_ENSO:PSL`. Endpoints de prueba: `GET /enso` (CPC, con PSL si CPC falla y descartado si fallan los dos; `lote_id` opcional, por defecto "consulta"; no pide lugar) y `GET /enso/psl` (solo el respaldo).

## 6. Cambios en el motor (spec 027)

- La respuesta suma un campo `aviso_campana` con la fase, la intensidad, la sinopsis de NOAA y esta frase: "En la región pampeana, El Niño suele traer más lluvia de primavera y verano. Es un patrón histórico, no un pronóstico del lote."
- La viabilidad y los riesgos de cada cultivo **no cambian**.
- El cambio del motor se suma a su rama (`MOTOR-recomendacion_de_cultivos`), y la spec 027 se actualiza en el mismo PR.

## 7. Reglas de calidad

- Nunca se inventa la fase: si no hay índice ni respaldo, sale `valor: null`, `calidad: "descartada"` y el motor no muestra el aviso.
- El texto de la sinopsis se cita con su fecha de publicación, para que no parezca más nuevo de lo que es.

## 8. Pruebas

- **Sin internet** (`tests/test_noaa_enso.py`): un `oni.ascii.txt` simulado da la fase y la intensidad correctas en los bordes (+0,5, −0,5, 1,5, 2,0); una discusión sin "Synopsis:" deja el índice sin pronóstico; CPC caído pasa al respaldo y la calidad queda `dudosa`.
- **Real:** workflow `Probar NOAA (El Niño / La Niña)`.

## 9. Criterios de aceptación

- [x] El índice real de jul-sep 2026 sale +2,16 y la fase "El Niño muy fuerte", como en la investigación 033. Prueba real: `enso_oni` = 2,16, fecha 30/9/2026, calidad `buena`.
- [x] La `nota` lleva un resumen en castellano armado con datos estructurados (fase, trimestre, estado de alerta traducido con un mapa fijo, probabilidad y período sacados de la sinopsis, fecha de publicación de la discusión) y la sinopsis original entre comillas en inglés, y termina con "Índice del Pacífico, no del lote." Prueba real: discusión, "Aviso de El Niño", más de 83 % hasta ene-mar 2027.
- [x] El respaldo de PSL responde en la prueba real y da un valor parecido al ONI (diferencia menor a 0,3 °C). Prueba real: promedio jul-sep 2026 de PSL = +1,90 °C ("El Niño fuerte") contra ONI +2,16: diferencia 0,26 °C.
- [x] El motor muestra `aviso_campana` y ninguna viabilidad cambia. Verificado con la prueba sin internet del motor usando el ONI real de +2,16 ("El Niño muy fuerte"; rama `MOTOR-recomendacion_de_cultivos`).
- [x] `pytest` pasa sin internet (75 tests, 34 de este conector).
- [x] Hernán aprobó esta spec:, con "Ok a los 3".

## 10. Preguntas abiertas

- ¿Vale la pena medir el efecto en el propio lote? Con la lluvia de POWER (spec 034) se puede calcular cuánto llovió de octubre a marzo en los años El Niño y en el resto. Se propone dejarlo para una fase siguiente.
