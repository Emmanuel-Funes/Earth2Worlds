# Spec 019 · ET de referencia FAO-56 con NASA POWER (último respaldo de la evapotranspiración)

**Estado:** aprobada por Hernán ("Sumar lo necesario para cubrir lo que hace falta") y verificada con datos reales · **Etapa:** pipeline satélite → API → app · **Requiere:** nada (la API de NASA POWER es pública, sin usuario ni contraseña)

## Objetivo

Que el lote siempre tenga un dato de **cuánta agua pide la atmósfera por día**, aunque fallen la ET principal y ECOSTRESS. Es el **último respaldo** de la evapotranspiración: ET → ECOSTRESS → **FAO-56 con POWER**.

**Importante:** este dato es la **ET de referencia** (ET0): lo que evapotranspiraría un pasto corto, bien regado, que cubre todo el suelo. **No es la ET real del cultivo del lote.** Para pasar a la ET del cultivo hace falta multiplicar por el coeficiente del cultivo (ET cultivo = Kc × ET0, FAO-56 capítulo 6), y si el cultivo sufre falta de agua, además por el coeficiente de estrés (Ks). Por eso se guarda con otro nombre de variable (`et0_mm_dia`) y no se mezcla con la ET real al combinar fuentes.

## Fuente

| Qué | Detalle |
|---|---|
| Agencia | NASA (Langley Research Center), proyecto POWER |
| Servicio | `https://power.larc.nasa.gov/api/temporal/daily/point`, comunidad `AG`, formato JSON, sin credenciales |
| Punto | Centro del lote (`lat`, `lon` que guarda la base) |
| Grilla | ~0,5° × 0,625° (meteorología, MERRA-2) y 1° (radiación, CERES): dato regional, `resolucion_m` = 55000 |
| Parámetros | `T2M_MAX`, `T2M_MIN` (°C), `T2MDEW` (punto de rocío, °C), `RH2M` (humedad relativa media, %), `WS2M` (viento a 2 m, m/s), `ALLSKY_SFC_SW_DWN` (radiación solar, MJ/m²/día) |
| Altura | La elevación de la celda que devuelve POWER en `geometry.coordinates[2]` (m) |
| Relleno | `-999` (dato que falta; también cuando POWER todavía no publicó la fecha, que suele tener unos días de atraso) |

No se usa el código del conector POWER de clima (spec 001): este conector pide sus propios parámetros (spec 009, satélites independientes).

## Proceso (FAO-56, Allen et al. 1998)

Para cada día:

1. **Presión** por altitud (ec. 7): P = 101,3 × ((293 − 0,0065 z) / 293)^5,26 kPa. **Constante psicrométrica** (ec. 8): γ = 0,000665 × P.
2. **Temperatura media** = (T máx + T mín) / 2 (ec. 9).
3. **Presión de vapor de saturación** es = (e°(T máx) + e°(T mín)) / 2 (ecs. 11 y 12). **Pendiente** Δ con la temperatura media (ec. 13).
4. **Presión de vapor real** ea:
   - con el punto de rocío: ea = e°(T rocío) (ec. 14), el método que FAO-56 pone primero;
   - si falta el punto de rocío, con la humedad relativa media: ea = HR media / 100 × es (ec. 19). La `nota` dice cuál se usó.
5. **Radiación extraterrestre** Ra por latitud y día del año (ecs. 21 a 25) y **de cielo despejado** Rso = (0,75 + 2×10⁻⁵ z) Ra (ec. 37).
6. **Radiación neta de onda corta** Rns = (1 − 0,23) Rs (ec. 38, albedo del pasto de referencia 0,23).
7. **Radiación neta de onda larga** Rnl = σ × (T máx,K⁴ + T mín,K⁴)/2 × (0,34 − 0,14 √ea) × (1,35 Rs/Rso − 0,35) (ec. 39), con Rs/Rso limitado a 1,0 como indica FAO-56.
8. **Radiación neta** Rn = Rns − Rnl (ec. 40). **Flujo de calor del suelo** G = 0 (paso diario, ec. 42).
9. **ET0** (ec. 6): ET0 = [0,408 Δ (Rn − G) + γ × 900/(T + 273) × u2 × (es − ea)] / [Δ + γ (1 + 0,34 u2)].

El viento de POWER ya está a 2 m (`WS2M`), así que no hace falta la corrección de altura (ec. 47).

## Salida (contrato común)

```json
{"lote_id": "lote-7", "fecha": "2026-11-14", "variable": "et0_mm_dia", "valor": 6.87,
 "unidad": "mm/día", "fuente": "POWER", "resolucion_m": 55000, "calidad": "buena",
 "nota": "ET de referencia de pasto (FAO-56 Penman-Monteith), NO es la ET real del cultivo: ET cultivo = Kc × ET0 · NASA POWER: T 36,3/19,6 °C, rocío 13,8 °C, viento 0,9 m/s, Rs 31,6 MJ/m², altura 568 m · Rn 18,1 MJ/m² · último respaldo de la ET"}
```

## Reglas de calidad

| Caso | `valor` | `calidad` | `nota` |
|---|---|---|---|
| Algún insumo con `-999` (T máx, T mín, viento, radiación, o punto de rocío **y** humedad a la vez) o la altura sin dato | `null` | `descartada` | Qué parámetros faltan |
| T máx menor que T mín | `null` | `descartada` | Insumos incoherentes |
| ET0 menor que 0 o mayor que 15 mm/día | el calculado | `dudosa` | Fuera del rango esperado (supuesto: 0 a 15 mm/día) |
| ea mayor que es (aire "sobresaturado" en el promedio diario) | el calculado | `dudosa` | Humedad incoherente con la temperatura |
| Resto | el calculado | `buena` | Insumos usados y método de humedad |

Nunca se inventa un valor: si falta un insumo, el día queda descartado y no se rellena con promedios.

## Dónde entra

- Satélite independiente (spec 009): rama `POWER-ET0_FAO56_respaldo`, archivo `rotaterra/fuentes/et0_fao56.py`, sin unir a `main` hasta la orden de Hernán.
- Se registra como `Satelite("ET:FAO56", pedir, respaldo_de="ET", orden=2)`: entra en la actualización nocturna solo si la ET principal (`"ET"`) falla y ECOSTRESS (`"ET:ECOSTRESS"`, `orden=1`) también falla o no trae datos. Usa el campo `orden` de la rama `NUCLEO-varios_respaldos_en_orden`.
- Unido sin la ET principal, queda en espera y no se consulta (spec 009).
- Endpoint de prueba `GET /et0?lote_id&lat&lon&desde&hasta`, para consultarlo en el momento (spec 010).
- `fuente` = `POWER`, que en `PRIORIDAD` ya es una fuente principal; como la variable es otra (`et0_mm_dia`), al combinar no reemplaza a la ET real.

## Criterios de aceptación

- [x] El cálculo reproduce el **ejemplo 18 de FAO-56** (Bruselas, 6 de julio: ET0 = 3,9 mm/día) y los ejemplos intermedios. Obtenido: ET0 3,88 mm/día, es 1,997 kPa, Δ 0,122, γ 0,0666, Ra 41,09, Rso 30,90, Rns 16,99, Rnl 3,71 y Rn 13,28 MJ/m²/día; además presión a 1800 m 81,8 kPa y γ 0,054 (ej. 2), Ra a 20° S el 3/9 32,2 (ej. 8), Rnl 3,5 (ej. 11) y ea con HR media 1,78 kPa (ej. 5).
- [x] Con el lote de prueba real (San Luis, 1 al 14 de enero de 2026) se obtiene ET0 diaria de POWER y se anotan los números. Centro del lote (-33,7025; -65,2975), altura de la celda de POWER 568 m, respuesta en 0,6 s, los 14 días `buena`: 6,34 · 6,70 · 6,42 · 6,38 · 6,87 · 4,94 · 6,83 · **1,83** (8/1, nublado: Rs 6,9 MJ/m²) · 3,02 · 6,10 · 6,66 · 6,65 · 3,56 · 6,87 mm/día. Media 5,66 mm/día, total 79,2 mm en 14 días: valores normales para el verano de San Luis. El viento de POWER fue bajo (0,5 a 1,4 m/s), así que el término de radiación pesa más que el aerodinámico.
- [x] Un insumo con `-999` deja el día `descartada`, con el motivo en la `nota` (tests `test_un_insumo_con_relleno_descarta_el_dia_y_dice_cual`, `test_sin_rocio_ni_humedad_se_descarta`, `test_sin_elevacion_no_se_inventa_la_altura`).
- [x] La `nota` aclara que es ET de referencia y no la ET real del cultivo (en todos los días, también los descartados).
- [x] El conector no importa código de ningún otro satélite (`tests/test_nucleo.py` en verde).
- [x] Tests sin internet (30 en `tests/test_et0_fao56.py`); prueba real "Probar POWER (ET de referencia FAO-56)" verde, con un clic y en cada PR que toque el conector.

## Fuera de alcance

Coeficientes de cultivo (Kc) y de estrés (Ks), balance de agua del suelo, y ET0 horaria.
