# Spec 024 · Balance hídrico propio con datos de la NASA (respaldo del balance de SEPA)

**Estado:** aprobada por Hernán ("Aprobar balance propio"); calibrada contra todo el historial de SEPA · **Etapa:** pipeline satélite → API → app · **Requiere:** los secretos de Earthdata para la lluvia de IMERG (sin ellos, usa solo POWER y sale `dudosa`) · **Rama:** `POWER-balance_hidrico_respaldo` · **Respalda a:** `SEPA_INTA` (spec 023)

## Objetivo

Tener el agua del suelo del lote aunque SEPA (INTA) no esté disponible: porque su servidor se cae (pasó), porque el INTA no autoriza el uso comercial (spec 023 §5.3) o porque el lote queda fuera de su mapa.

Hernán lo pidió: "Si, hacerlo" (balance propio como respaldo) y "Si sigue caído, no considerarlo, ver la forma de costearlos nosotros mismos".

## Fuente

| Dato | Producto | Agencia | Grilla | Acceso |
|---|---|---|---|---|
| Lluvia diaria | NASA POWER `PRECTOTCORR` (MERRA-2 corregido) | NASA (Langley) | 0,5° × 0,625° (~55 km) | `https://power.larc.nasa.gov/api/temporal/daily/point`, público |
| Lluvia diaria (control) | GPM IMERG Final (`GPM_3IMERGDF`) y, donde todavía no salió, Late (`GPM_3IMERGDL`) | NASA / JAXA | 0,1° (~10 km) | CMR + OPeNDAP con el núcleo `earthdata` (secretos de Earthdata). Solo los días en que POWER marca lluvia |
| Clima para la ET0 | NASA POWER `T2M_MAX`, `T2M_MIN`, `T2MDEW`, `RH2M`, `WS2M`, `ALLSKY_SFC_SW_DWN` | NASA (Langley) | ídem | ídem, en el mismo pedido |
| Altura del punto | La que devuelve POWER en `geometry.coordinates[2]` | NASA | ídem | ídem |
| Capacidad de agua del suelo | Textura del lote (GeoINTA, productor o análisis), pasada como dato | INTA / productor | — | parámetro `textura` |

El clima sale de **un solo pedido a POWER**. La lluvia de IMERG se lee con el núcleo `earthdata`, solo para los días en que POWER marca lluvia (en San Luis, unos 150 de 400 días: 35 a 50 s). El conector no importa otros satélites (spec 009): repite las ecuaciones FAO-56 del conector de ET0 (spec 019) y la lectura de IMERG (spec 006) en su propio archivo.

## Entrada

- El lote como lo recibe cualquier satélite: `lote["id"]`, `lote["lat"]`, `lote["lon"]` (centro, EPSG:4326). Opcional `lote["textura"]` y `lote["kc"]`.
- El período `desde`–`hasta` (máximo 366 días).
- `textura` (opcional): una de las clases de la tabla de abajo, con o sin tilde.
- `kc` (opcional, de 0,1 a 1,3): coeficiente de cultivo de octubre a mayo. Por defecto **0,5**, elegido contra todo el historial de SEPA (ver "Comparación con todo el historial de SEPA"). De junio a septiembre se usa la mitad. Antes fue 0,7 y después 1,0.

## Proceso

1. Validar el pedido (coordenadas, fechas, máximo 366 días, textura conocida, `kc` en rango). Un pedido inválido no llama a la NASA.
2. Pedir a POWER los siete parámetros desde **365 días antes de `desde`** hasta `hasta` (arranque del balance).
3. Arrancar el agua disponible en el **50 %** de la capacidad, 365 días antes. Un año de arranque borra casi todo el efecto de ese supuesto.
4. Pedir a IMERG la lluvia de los días en que POWER marca 0,1 mm o más. Si IMERG no responde o faltan los secretos, se sigue solo con POWER y todo sale `dudosa`.
5. Para cada día:
   - **Lluvia = la menor entre POWER e IMERG.** POWER marca lluvias de invierno que no ven ni IMERG ni SEPA (151 mm en junio de 2025 y 220 mm en julio de 2026, contra 7 y 6 mm de IMERG); IMERG Late exagera algunas lluvias de verano. Tomar la menor descarta las que un solo satélite ve. Si IMERG no tiene ese día, se usa la de POWER y la década sale `dudosa`.
   - `ET0` FAO-56 Penman-Monteith (Allen et al. 1998, ec. 6), igual que la spec 019.
   - `ETc = Kc × ET0`, con el Kc a la mitad de junio a septiembre (cultivo o pasto parado).
   - `Ks = 1` si el agua disponible está por encima del 30 % de la capacidad (p = 0,7, dentro del rango 0,3 a 0,8 de FAO-56 tabla 22); si no, `Ks = agua ÷ (0,3 × capacidad)`.
   - `ETR = Ks × ETc`.
   - `agua = agua + lluvia − ETR`. Lo que pasa la capacidad es **excedente** (drenaje) y el agua queda en la capacidad. Nunca baja de 0.
6. Datos que le faltan a POWER (relleno −999), con los métodos que da FAO-56 para datos faltantes:
   - Radiación: Hargreaves (FAO-56 ec. 50, kRs 0,16 para el interior).
   - Viento: 2 m/s (FAO-56 cap. 3).
   - Humedad: rocío igual a la mínima (FAO-56 ec. 48).
   - La década con algún día estimado sale `dudosa`, y la `nota` dice qué se estimó y cuántos días del balance llevan datos estimados.
   - Sin temperatura o sin lluvia no se puede seguir: el balance **se corta ahí**. Las décadas desde ese día en adelante salen `descartada`, con la fecha y el parámetro que falta (también pasa con los días recientes que POWER todavía no publicó).
7. Resumir por **década**, igual que SEPA: del 1 al 10, del 11 al 20 y del 21 a fin de mes. Sale una década si su último día cae entre `desde` y `hasta`.

### Capacidad de agua disponible hasta 2 m, según la textura

FAO-56, tabla 19: el centro del rango de agua útil (capacidad de campo menos punto de marchitez) por 2.000 mm de suelo, por el **70 %** que exploran las raíces (no exploran parejo los 2 m). El 70 % sale de la comparación con SEPA: SEPA usa 220 mm en el lote de San Luis (agua disponible ÷ % de agua) y el balance anda mejor entre 160 y 200 mm. La diferencia con SEPA cambia muy poco entre 120 y 220 mm.

| Textura | Agua útil (m³/m³) | Capacidad en 2 m (× 0,7) |
|---|---|---|
| arenoso | 0,08 | 112 mm |
| arenoso franco | 0,09 | 126 mm |
| franco arenoso | 0,13 | 182 mm |
| franco | 0,155 | 217 mm |
| franco limoso | 0,16 | 224 mm |
| limoso | 0,18 | 252 mm |
| franco arcillo limoso | 0,155 | 217 mm |
| arcillo limoso | 0,16 | 224 mm |
| arcilloso | 0,16 | 224 mm |

Sin textura se usa **franco (217 mm)** y los valores salen con calidad `dudosa`.

## Salida (contrato común), una por década

| Variable | Unidad | Qué es | Igual que SEPA |
|---|---|---|---|
| `agua_disponible_2m` | mm | Agua disponible hasta 2 m al último día de la década | Sí, mismo nombre |
| `agua_suelo_porcentaje` | % | Esa agua en % de la capacidad | Sí, mismo nombre |
| `excedente_balance_mm` | mm | Excedente (drenaje) sumado en la década | Parecido a `agua_excedente_inta` |
| `confort_hidrico_balance` | % | ETR ÷ ETc de la década × 100 | Parecido a `confort_hidrico_inta` |
| `agua_relativa_balance` | % | Agua del último día en % entre lo más seco (0) y lo más húmedo (100) del último año del balance: el valor "equiparado" | No (sirve para comparar con cualquier fuente) |

```json
{"lote_id": "lote-7", "fecha": "2026-11-14", "variable": "agua_disponible_2m", "valor": 87.3,
 "unidad": "mm", "fuente": "POWER", "resolucion_m": 55000, "calidad": "buena",
 "nota": "Balance propio (spec 024), respaldo de SEPA · década 2 de 09/2026: lluvia 11,3 mm, ETc 9,7 mm, ETR 9,7 mm · suelo franco arenoso, 182 mm de agua útil en 2 m · Kc 0,5 (de junio a septiembre 0,25) · arranque 50% el 14/11/2026 · lluvia: la menor entre POWER (0,5°) e IMERG (0,1°) de cada día; ET0 FAO-56 con POWER · calibrado contra 87 décadas de SEPA en San Luis, diferencia media 16 mm (spec 024)"}
```

- `agua_disponible_2m` y `agua_suelo_porcentaje` tienen **el mismo nombre que en SEPA**: si SEPA falla, la app recibe la misma serie venga de donde venga.
- `fuente: "POWER"` y `resolucion_m: 55000` dicen que es un dato regional calculado, no medido en el lote.

## Reglas de calidad

1. **Nunca inventar.** Sin temperatura o lluvia de POWER: `valor: null`, `calidad: "descartada"`, y la `nota` dice desde qué día y qué parámetro falta. Lo que se completa con FAO-56 queda `dudosa` y dicho en la `nota`.
2. Sin textura: `calidad: "dudosa"` y la `nota` lo dice.
3. **Calibrado contra SEPA** (`CALIBRADO = True` desde, diferencia media 16 mm en San Luis): sale `buena` si hay textura y lluvia de IMERG. Si IMERG no respondió, todo sale `dudosa`; si IMERG no tiene algún día de la década, esa década sale `dudosa`. Las dos cosas quedan dichas en la `nota`.
4. Supuestos escritos en cada `nota`: Kc (y el de invierno), textura y capacidad, arranque al 50 %, de dónde salió la lluvia, y contra qué se calibró.
5. Límites del modelo (en la spec, no en la nota):
   - Es un balance de un solo balde de 2 m, sin escorrentía ni ascenso capilar (se probó escurrimiento con número de curva y casi no cambia nada).
   - El Kc tiene dos valores por año (octubre a mayo y junio a septiembre). No sigue el crecimiento del cultivo ni el barbecho de cada lote.
   - La calibración es de un solo lote (San Luis, franco arenoso). En otras zonas hay que volver a comparar con SEPA.
   - La lluvia es de satélite (10 y 55 km), no de un pluviómetro del lote.
   - Sirve para la tendencia y para reemplazar a SEPA cuando no está, no para decidir un riego al milímetro.

## Dónde entra

- **Registro (spec 009):** `SATELITES = [Satelite("SEPA_INTA:BALANCE", pedir, respaldo_de="SEPA_INTA")]`. Si SEPA falla o no trae agua, el núcleo pide este respaldo (con el, en la consulta en el momento). Unido sin SEPA, queda en espera.
- **Endpoint de prueba:** `GET /balance-hidrico?lote_id&lat&lon&desde&hasta[&textura][&kc]`.
- No toca ningún archivo del núcleo.

## Prueba real

- **Workflow:** `Probar POWER (balance hídrico propio)` (`.github/workflows/probar-balance-hidrico.yml`, `probar_balance_hidrico.py`).
- **Lote:** el de San Luis (-33,700; -65,300), textura franco arenoso.
- **Períodos:**
  - 25/8 a 14/11/2026, comparable con SEPA del 31/8 al 20/9: 92,1 → 86,0 → 83,9 mm, y 41,8 → 39,1 → 38,2 %.
  - Enero de 2025, comparable con SEPA (los 6 píxeles del lote): 89,4 → 59,4 → 30,0 mm. Antes se anotó 58,1 → 39,2 → 25,9, que era de un solo píxel, antes de arreglar la ventana del conector de SEPA.
- **Cuándo corre:** en cada PR que toque estos archivos y a mano con un clic.

## Resultado de la prueba real

Workflow **Probar POWER (balance hídrico propio)**, lote de San Luis (-33,7025; -65,2975), franco arenoso (260 mm en 2 m), Kc 0,7. Cada corrida tarda 1 s (un solo pedido a POWER con el año de arranque).

| Década | Balance propio (mm) | % | Lluvia POWER en la década | SEPA (mm) |
|---|---|---|---|---|
| 14/11/2026 | 260,0 | 100 | 121,7 mm | 92,1 |
| 14/11/2026 | 238,3 | 91,6 | 3,5 mm | 86,0 |
| 14/11/2026 | 231,4 | 89,0 | 20,4 mm | 83,9 |
| 14/11/2026 | 227,1 | 87,3 | 29,9 mm | 84,0 |
| 14/11/2026 | 227,4 | 87,5 | 38,1 mm | 58,1 |
| 14/11/2026 | 214,8 | 82,6 | 25,9 mm | 39,2 |
| 14/11/2026 | 186,9 | 71,9 | 14,6 mm | 25,9 |

Con Kc 0,9: 231 → 216 → 202 mm en septiembre y 127 → 110 → 83 mm en enero de 2025.

**Comparación con SEPA:**
- La tendencia coincide: baja en septiembre de 2026 y baja más fuerte en enero de 2025.
- El nivel no coincide: el balance propio da **entre 140 y 170 mm más** que SEPA.
- Causas probables:
  - Lluvia de POWER: 121,7 mm a fines de agosto de 2026, mientras SEPA marca que el agua bajó esa década.
  - Kc fijo de 0,7, bajo para un verano con cultivo.
  - La celda de 55 km contra los píxeles de 500 m de SEPA.

**Decisión técnica:** el balance queda `dudosa` hasta calibrarlo.

**Próximo paso propuesto:** comparar década por década con todo el historial de SEPA (desde mayo de 2024), cuando el servidor del INTA responda. Probar también la lluvia de IMERG (10 km) en lugar de la de POWER, y el Kc.

POWER tuvo huecos de radiación el 7/9 y el 14/11/2026, que se completaron con Hargreaves (FAO-56 ec. 50).

## Si el INTA no responde: otras fuentes y cómo equiparar

Hernán pidió "ver más formas de equiparar datos, de dónde podemos sacar datos si no nos responde el INTA". Se exploró con el workflow **Explorar agua del suelo de la NASA (comparación con SEPA)** (`explorar_agua_suelo_nasa.py`), en el lote de San Luis.

| Fuente | Agencia | Qué da | Escala | Demora | Probado |
|---|---|---|---|---|---|
| Balance propio (esta spec) | NASA POWER | Agua útil hasta 2 m, por década | ~55 km | ~4 días | Sí, desde 2024 |
| SMAP L4 zona de raíces (`SMAP-humedad_suelo`, #19) | NASA | Humedad 0-100 cm en m³/m³ | 9 km | ~3 días | Sí (spec 003) |
| GLDAS 2.2 Catchment con GRACE | NASA | Agua en la zona de raíces y en el perfil, en mm | 25 km | **~3 meses** (último dato: 14/11/2026) | Sí, por OPeNDAP |
| GLDAS 2.1 Noah | NASA | Agua 0-100 cm, en mm | 25 km | ~3 meses | Sí, por OPeNDAP |
| SAOCOM: mapa de humedad del perfil (MSM) y visor de series (VST) | CONAE (socia) | Agua hasta 2 m en capas de 10 cm, diaria | Zonas homogéneas, nodos cada 3,5 km o más | Diaria | **No**: cubre solo Buenos Aires, Córdoba, Entre Ríos, La Pampa y Santa Fe (San Luis queda afuera). Se ve gratis; el CSV pide registrarse. |

Resultado de la comparación:
- GLDAS da agua **total** (≈210 mm en la zona de raíces, ≈930 mm en el perfil), no agua útil. Por eso no se compara en mm con SEPA ni con el balance.
- **Equiparar** = llevar cada serie a % entre su mínimo y su máximo del período. Así se compara la forma de la curva:
  - Septiembre de 2026: SEPA 100 → 90,8 → 87,7 → 87,8 y balance propio 100 → 88,5 → 84,8 → 82,5. **Coinciden.**
  - Enero de 2025: SEPA 48,6 → 20,1 → 0 y balance 82,7 → 76,0 → 61,1. Los dos bajan, pero SEPA mucho más.
  - Septiembre de 2024: el balance y los dos GLDAS marcan el punto más seco (0 %) el 14/11/2026 y el humedecimiento de octubre.

Formas de equiparar, en orden:
1. **Entregar también el % equiparado** (o el percentil de cada década en su historia). Sirve para comparar fuentes con escalas distintas. **Hecho:** variable `agua_relativa_balance`.
2. **Calibrar el balance con fuentes de la NASA**, sin depender del INTA: Kc contra SMAP L4 (al día) y GLDAS (historia). **Hecho:** Kc 1,0 (ver Calibración).
3. **Usar la lluvia de IMERG** (10 km) en lugar de la de POWER (55 km).
4. Contrastar con SEPA cuando responda, y con SAOCOM en lotes de la región pampeana.

## Calibración con la NASA

Se corrió con el workflow **Calibrar balance hídrico propio (NASA)** (`calibrar_balance.py`).
- **Lote y período:** San Luis, decádicas de mayo de 2024 a septiembre de 2026.
- **Combinaciones:** 8 valores de Kc (0,5 a 1,2) × 3 texturas, todas sobre el mismo clima de POWER.
- **Referencias:**
  - SMAP L4, zona de raíces: 87 décadas.
  - GLDAS 2.2: 78 décadas, hasta junio de 2026.
  - SEPA: las 7 décadas ya leídas.
- **Cómo se compara:** por la forma de la curva, con la correlación (r) y el error después de equiparar.

| Textura | Kc | SMAP L4 | GLDAS 2.2 | SEPA |
|---|---|---|---|---|
| franco arenoso (la del lote) | 0,7 (anterior) | r 0,27 · error 31 | r 0,17 · error 42 | r 0,89 · error 15 |
| franco arenoso | 0,8 | r 0,36 · error 24 | r 0,12 · error 36 | **r 0,98 · error 8** |
| franco arenoso | 0,9 | r 0,42 · error 22 | r 0,19 · error 31 | r 0,97 · error 10 |
| franco arenoso | **1,0 (nuevo)** | **r 0,46 · error 21** | r 0,26 · error 27 | r 0,96 · error 12 |
| franco arenoso | 1,1 | r 0,46 · error 20 | r 0,30 · error 24 | r 0,95 · error 14 |
| arenoso franco | 1,0 | r 0,51 · error 19 | r 0,31 · error 22 | r 0,93 · error 15 |

Conclusiones:
- Con **Kc 0,7 el balance era demasiado húmedo**. Con Kc 0,9 a 1,1 la forma de la curva queda más cerca de SMAP L4 y de SEPA.
- Se elige **Kc 1,0**: es el que mejor acompaña a SMAP L4 sin perder a SEPA, y es el Kc del pasto de referencia de FAO-56, un valor estándar y no un ajuste fino. La textura no se calibra: es un dato del lote (GeoINTA).
- La forma coincide muy bien con SEPA, aunque son solo 7 décadas. Con SMAP L4 coincide a medias (r ≈ 0,5) y con GLDAS poco (r ≈ 0,3). GLDAS casi no se mueve (≈210 mm todo el año).
- **Prueba real con Kc 1,0 y la textura del lote** (franco arenoso, workflow **Probar POWER (balance hídrico propio)**):

| Década | Balance Kc 1,0 (mm) | % equiparado | SEPA (mm) | Diferencia |
|---|---|---|---|---|
| 14/11/2026 | 105,5 | 36,4 | 58,1 | +47 |
| 14/11/2026 | 91,6 | 31,4 | 39,2 | +52 |
| 14/11/2026 | 68,1 | 23,0 | 25,9 | +42 |
| 14/11/2026 | 227,5 | 86,5 | 86,0 | +142 |
| 14/11/2026 | 208,9 | 78,8 | 83,9 | +125 |
| 14/11/2026 | 190,0 | 70,9 | 84,0 | +106 |

  - Enero de 2025 bajó de 227 → 215 → 187 mm (Kc 0,7) a 106 → 92 → 68 mm: la diferencia con SEPA pasó de unos 170 mm a unos 47 mm.
  - Septiembre de 2026 sigue unos 100 a 140 mm arriba. La causa probable es la lluvia de POWER de fines de agosto de 2026 (121,7 mm en la década del 31/8), que llena el perfil y SEPA no muestra. Probar la lluvia de IMERG en lugar de la de POWER es el próximo paso.
- En esa tabla, SEPA de enero de 2025 era de un solo píxel. Con los 6 píxeles del lote da 89,4 → 59,4 → 30,0 mm.
- Quedaba `dudosa`: faltaba comparar en mm con todo el historial de SEPA. Se hizo el mismo día (sección siguiente).

## Comparación con todo el historial de SEPA

Hernán pidió "seguir comparando y trayendo comparativas hasta llegar a la mínima diferencia posible". Se hizo con el workflow **Comparar balance hídrico propio con SEPA** (`comparar_balance_sepa.py`), en el lote de San Luis.

- **SEPA:** agua disponible y % de agua de las **87 décadas** desde mayo de 2024, en los 6 píxeles del lote (232 s). Con agua ÷ % sale la capacidad que usa SEPA en el lote: **220 mm** (de 213 a 228).
- **Lluvia:** POWER e IMERG día por día, de mayo de 2022 a septiembre de 2026 (IMERG: 1.248 días en 249 s).
- **Medida:** la diferencia media en mm contra SEPA, década por década. Para no sobreajustar, también el error de cada año por separado (mayo de 2024 a septiembre de 2025, y octubre de 2025 a septiembre de 2026).
- Las lecturas se guardan entre corridas (cache de Actions), así cada ronda tarda unos segundos.

**Lluvia por mes que no coincide** (mm):

| Mes | POWER | IMERG | Qué hizo SEPA |
|---|---|---|---|
| junio de 2025 | 151,1 | 7,0 | casi no subió (10,9 mm a fin de mes) |
| julio de 2026 | 220,1 | 6,1 | bajó de 113 a 105 mm |
| agosto de 2026 | 128,2 | 17,7 | bajó de 105 a 92 mm |
| febrero de 2026 | 94,3 | 239,8 (Late) | subió poco (de 12 a 39 mm) |

La lluvia de invierno de POWER es la causa principal de que el balance diera 100 a 170 mm de más.

**Rondas:**

| Ronda | Qué se probó | Combinaciones | Diferencia media con SEPA |
|---|---|---|---|
| Antes | POWER, Kc 1,0 todo el año, 260 mm, p 0,5 | 1 | **54,4 mm** (sesgo +52,5) |
| 1 | Lluvia de POWER o de IMERG, Kc 0,6 a 1,3, capacidad 120 a 350 mm, p 0,3 a 0,7, escurrimiento, arranque | 4.608 | 20,7 mm (IMERG) · 21,4 mm (POWER) |
| 2 | Kc de invierno, lluvia promedio y la menor de las dos | 16.380 | 17,0 mm |
| 3 | Ajuste fino, mezclas 25/75 %, meses de invierno | ~37.000 | 15,8 mm |
| 4 | Kc más bajos (0,3 a 0,45) y balance corrido como la app | 17.910 | 15,8 mm (no mejora: es el piso con estos datos) |
| 5 | Kc que sigue al NDVI de MODIS del lote (250 m, 99 compuestos), como SEPA con la cobertura verde | 2.736 | 15,9 mm; corrido como la app, 17,2 mm (no mejora) |

**Elegida** (la que entra en el conector): lluvia = la menor entre POWER e IMERG, Kc 0,5 de octubre a mayo y 0,25 de junio a septiembre, 182 mm (70 % del agua útil de la tabla), p 0,7, sin escurrimiento.

| | Diferencia media | Sesgo | r | Año 1 | Año 2 |
|---|---|---|---|---|---|
| Antes (POWER, Kc 1,0) | 54,4 mm | +52,5 | 0,47 | 66,9 | 36,7 |
| Elegida (180 mm en la grilla) | **15,8 mm** | +0,1 | 0,89 | 18,0 | 12,6 |
| Elegida, corrida como la app (cada mes con su año de arranque) | **15,7 mm** | | | | |

- Las mejores 15 combinaciones dan todas entre 15,8 y 16,3 mm, con Kc 0,5 a 0,55, Kc de invierno 0,25 a 0,35 y capacidad de 160 a 220 mm. Es un piso, no un ajuste fino de un solo valor.
- Con un año de arranque alcanza: corrido como la app da lo mismo que con dos años (15,7 contra 15,8 mm).
- Con un solo Kc todo el año, lo mejor es 17,5 mm. Con solo la lluvia de POWER, 21,5 mm. Con solo IMERG, 17,6 mm.
- Lo que queda (16 mm) viene sobre todo de lluvias que SEPA ve más fuertes que los satélites (octubre y noviembre de 2024, octubre a diciembre de 2025).
- **Ronda 5, Kc con NDVI:** Kc = 0,2 sin verde a 0,6 con el máximo verde del lote da 15,9 mm (más parejo entre años: 15,7 y 16,3), pero corrido como la app da 17,2 mm. No mejora al Kc de dos temporadas y obligaría a leer otro satélite en cada pedido, así que **no se usa**.
- Con datos de satélite, 16 mm es el piso. Lo único que podría bajarlo es una lluvia medida en el lote: el pluviómetro del productor (fuente permitida, "datos del productor").

**Prueba real del conector con la combinación elegida** (workflow **Probar POWER (balance hídrico propio)**, 14/11/2026, franco arenoso, 182 mm). IMERG se leyó en 35 s (161 días con lluvia) y 50 s (147 días):

| Década | Balance propio | SEPA | Diferencia |
|---|---|---|---|
| 14/11/2026 | 92,3 mm | 92,1 mm | +0,2 |
| 14/11/2026 | 85,8 mm | 86,0 mm | −0,2 |
| 14/11/2026 | 87,3 mm | 83,9 mm | +3,4 |
| 14/11/2026 | 84,7 mm | 84,0 mm | +0,7 |
| 14/11/2026 | 62,6 mm | 89,4 mm | −26,8 |
| 14/11/2026 | 49,6 mm | 59,4 mm | −9,8 |
| 14/11/2026 | 33,7 mm | 30,0 mm | +3,7 |

Con Kc 0,4 da unos 40 mm más, y con Kc 0,6 unos 30 mm menos: el Kc es lo que más mueve el resultado.

## Criterios de aceptación

- [x] Existe `rotaterra/fuentes/balance_hidrico.py`, no importa otros satélites y los tests del núcleo siguen pasando.
- [x] Tests sin internet (26, más los del núcleo: 67 en total): ET0 contra el ejemplo 18 de FAO-56, balance a mano de pocos días (lluvia, consumo, Ks, excedente, piso en 0), corte por hueco de POWER, radiación y viento estimados con FAO-56, décadas, textura desconocida rechazada, sin textura `dudosa`, Kc de invierno, la menor lluvia entre POWER e IMERG, IMERG solo para días con lluvia, sin IMERG `dudosa`, IMERG sin credenciales.
- [x] Prueba real con NASA POWER en el lote de San Luis: devuelve agua en mm y % por década (tabla de arriba).
- [x] Comparación con SEPA anotada: misma tendencia, pero entre 140 y 170 mm más de agua. Queda `dudosa` hasta calibrar.
- [x] Calibrado contra el historial de SEPA (diferencia media menor a 30 mm), y recién ahí `CALIBRADO = True`: 15,7 mm en 87 décadas de San Luis, corrido como la app.
- [x] Prueba real con la lluvia de IMERG: septiembre de 2026 a menos de 4 mm de SEPA en las cuatro décadas.
- [x] Hernán aprobó la spec.
