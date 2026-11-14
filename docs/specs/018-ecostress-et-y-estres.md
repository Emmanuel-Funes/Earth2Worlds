# Spec 018 · Evapotranspiración y estrés hídrico de 70 m con ECOSTRESS

**Estado:** aprobada por Hernán ("Sumar lo necesario para cubrir lo que hace falta") y verificada con datos reales · **Etapa:** pipeline satélite → API → app · **Requiere:** cuenta NASA Earthdata · **Rama:** `ECOSTRESS-evapotranspiracion_estres`

## Objetivo

Que el lote tenga **cuánta agua pierde el cultivo por día** (evapotranspiración, ET) y **cuánto estrés hídrico tiene** (índice de estrés evaporativo, ESI), con el detalle de 70 m de ECOSTRESS, la cámara térmica de la NASA en la Estación Espacial Internacional. Es lo que la Guía técnica pedía como "V2" (ver `docs/RESUMEN-pipeline-satelital.md`).

Dentro de la cadena de respaldos de la ET es el **primer respaldo**: si la ET principal (`"ET"`, otra rama) falla, entra ECOSTRESS; si ECOSTRESS tampoco trae datos, entra la ET calculada con FAO-56 (`"ET:FAO56"`, orden 2).

## Fuente y agencia

NASA, LP DAAC (Earthdata Cloud), ECOSTRESS en mosaicos (productos "T", grilla MGRS, la misma de Sentinel-2), GeoTIFF optimizados para la nube (COG), 70 m. El conector toma siempre **la versión más nueva que tenga CMR**.

| Producto | Qué trae | Capa que se usa | Unidad |
|---|---|---|---|
| `ECO_L3T_JET` | Evapotranspiración, ensamble JET de la NASA-JPL | `ETdaily` (ET del día de la pasada) | mm/día |
| `ECO_L4T_ESI` | Índice de estrés evaporativo (ESI = ET real / ET potencial, de PT-JPL-SM) | `ESI` | adimensional, 0 a 1 |

Además, las capas `cloud` (nube) y `water` (agua) del mismo gránulo se usan como máscara. Si un gránulo no las trae, se usan solo los píxeles con valor (la NASA ya deja en blanco los de nube).

**Verificado en la prueba real:**
- La versión vigente en CMR es la **003**: `ECO_L3T_JET` = `C4057232489-LPCLOUD`, `ECO_L4T_ESI` = `C4057232495-LPCLOUD`; gránulos `ECOv003_L3T_JET_…` y `ECOv003_L4T_ESI_…`.
- El lote de prueba cae en el mosaico **20HKH**.
- Capas de `ECO_L3T_JET`: `ETdaily`, `ETuncertainty`, `PTJPLSMinst`, `PTJPLSMdaily`, `PTJPLSMcanopy`, `PTJPLSMsoil`, `PTJPLSMinterception`, `STICJPLinst`, `STICJPLdaily`, `STICJPLcanopy`, `BESSJPLdaily`, `PMJPLdaily`, `cloud`, `water`.
- Capas de `ECO_L4T_ESI`: `ESI`, `PET`, `cloud`, `water`.
- LP DAAC redirige a CloudFront; con el enlace firmado resuelto por httpx, GDAL lee sin problemas.

**Pasadas irregulares:** la Estación Espacial no pasa a la misma hora ni todos los días. Hay días sin pasada, días con dos y pasadas de madrugada o de tarde. ECOSTRESS solo sirve de respaldo en los días en que pasó.

## Entrada

Polígono del lote (GeoJSON, EPSG:4326) y período `desde`–`hasta` (máximo 366 días).

## Proceso

1. Token de Earthdata con `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD` (`earthdata.cliente_autorizado`).
2. En CMR, la versión vigente de cada producto y los gránulos cuyo mosaico toca el rectángulo del lote en el período (un día de margen a cada lado, por el cambio de fecha UTC → hora local).
3. De cada gránulo se toman los enlaces de descarga (`GET DATA`, https) de sus capas (`…_ETdaily.tif`, `…_ESI.tif`, `…_cloud.tif`, `…_water.tif`).
4. LP DAAC redirige cada archivo a un enlace firmado de CloudFront: se resuelve con httpx y el token, y GDAL (rasterio) lee el enlace firmado sin credenciales (mismo problema que HLS, spec 002). La parte firmada del enlace nunca se guarda ni se muestra.
5. Se lee **solo la ventana del lote** de cada capa (el mosaico está en UTM; el polígono se transforma). Hasta 4 archivos en paralelo.
6. Píxel válido = centro dentro del lote, valor finito y en el rango físico, sin nube y sin agua. Si ningún centro de píxel cae dentro del lote (lote más chico que un píxel), se usan los píxeles que el lote toca, y se aclara en la `nota`.
7. Valor del lote = **mediana** de los píxeles válidos; en la `nota` van media, p10, p90, % de válidos, el gránulo y la hora de la pasada (UTC y solar).
8. **Fecha = día de la pasada en hora solar local** (hora UTC + longitud / 15). En San Luis (−65,3°) son unas 4 h 21 min menos que UTC: una pasada a las 02:00 UTC es del día anterior.
9. Si hay dos pasadas el mismo día (o el lote cae en dos mosaicos que se superponen), queda la que tiene **más píxeles válidos** y la `nota` dice cuántas hubo.
10. Si un archivo no se puede leer, esa pasada queda `descartada` con el motivo; si no se puede leer ninguno, es un error (y entra el siguiente respaldo).

## Salida (contrato común)

Ejemplo real (lote de prueba, 14/11/2026):

```json
{"lote_id": "lote-7", "fecha": "2026-11-14", "variable": "et_mm_dia", "valor": 4.88,
 "unidad": "mm/día", "fuente": "ECOSTRESS", "resolucion_m": 70, "calidad": "buena",
 "nota": "Respaldo de la ET · ET del día de la pasada (ensamble JET) · media 5.01 · p10 4.42 · p90 5.63 · válidos 90% · ECO_L3T_JET ETdaily · pasada 19:18 UTC (14:56 hora solar) · máscaras: cloud, water · ECOv003_L3T_JET_43235_004_20HKH_20260219T191801_02 · 2 pasadas ese día, queda la más limpia"}
{"lote_id": "lote-7", "fecha": "2026-11-14", "variable": "esi", "valor": 0.59,
 "unidad": "índice (0 a 1)", "fuente": "ECOSTRESS", "resolucion_m": 70, "calidad": "buena",
 "nota": "Respaldo de la ET · ESI = ET real / ET potencial: 0 = estrés máximo, 1 = sin estrés · …"}
```

- `et_mm_dia` usa **el mismo nombre y la misma unidad** que la ET principal (`mm/día`), para que la serie combinada no tenga saltos.
- `esi` es exclusivo de ECOSTRESS: **0 = el cultivo no transpira nada (estrés máximo), 1 = transpira todo lo que la atmósfera le pide (sin estrés)**.

## Reglas de calidad

- Mismos umbrales que HLS: válidos ≥ 60 % → `buena`; entre 20 % y 60 % → `dudosa` ("lote parcialmente cubierto"); < 20 % → `descartada` con `valor: null` y la `nota` dice por qué (nube, agua o sin dato).
- **Pasada con poco sol** (supuesto, agregado tras la prueba real): si la pasada fue antes de las 9 o después de las 16 hora solar, el valor queda **a lo sumo `dudosa`**, porque la NASA estima el día entero desde una hora con poco sol. La prueba real mostró pasadas a las 05:30, 06:16 y 18:54 hora solar.
- **Supuestos de rango físico** (fuera de rango = píxel inválido, no se corrige): ET entre 0 y 20 mm/día; ESI entre 0 y 2 (puede pasar apenas de 1 cuando la ET real supera a la potencial; valores mayores son artefactos).
- Si el archivo trae factor de escala, se aplica; los archivos vienen en valores físicos.
- Una pasada sin el archivo de una capa no inventa esa variable: simplemente no se informa para ese día.
- Nunca se inventa un valor.

## Dónde entra

- Satélite independiente (spec 009): `rotaterra/fuentes/ecostress.py`, solo usa el núcleo.
- Registro: `SATELITES = [Satelite("ET:ECOSTRESS", pedir, respaldo_de="ET", orden=1)]`. Unido sin la ET principal, queda en espera (spec 009).
- Endpoint de prueba: `POST /estres-hidrico` (lote_id, polígono, desde, hasta) → lista de observaciones `et_mm_dia` y `esi`. `422` pedido inválido, `503` faltan credenciales, `502` la NASA no responde.
- Prueba real: workflow "Probar ECOSTRESS (evapotranspiración y estrés)" (`probar_ecostress.py`), lote de prueba de San Luis, enero de 2026. Si en el período no hay ninguna pasada, la prueba se amplía sola a diciembre 2025 – febrero 2026 y lo dice; si tampoco hay, falla.
- En `PRIORIDAD` (`base.py`, núcleo) ECOSTRESS figura con prioridad 1, como las principales. Como acá es respaldo de la ET, si la ET principal también tiene prioridad 1, al combinar no queda claro cuál gana: conviene bajar ECOSTRESS a 2 en el PR del núcleo (no se toca desde esta rama).

## Criterios de aceptación

- [x] Con el lote de prueba real (San Luis, enero de 2026) se obtienen `et_mm_dia` y `esi` de ECOSTRESS por fecha de pasada, con su % de píxeles válidos, y se anotan los números. **Enero de 2026** (8 s): 3 fechas con pasada; 11/1 ET 2,89 mm/día y ESI 0,38 (100 % válido, `dudosa` por pasada a las 06:16 hora solar); 2/1 y 14/1 descartadas (0 % válido). **Diciembre 2025 – febrero 2026** (32 s, 14 gránulos por producto): 11 fechas; con el lote despejado: 18/12 ET 1,93 · ESI 0,29; 22/12 ET 2,29 · ESI 0,29; 19/2 ET 4,88 · ESI 0,59 (90 % válido). `dudosa` por poco sol: 10/12 ET 0,39 · ESI 0,20 (18:54 hora solar) y 11/1. Descartadas: 25/12, 29/12, 2/1, 14/1, 23/2 y 27/2. El lote es desparejo: el 18/12 la ET va de 1,02 (p10) a 5,92 (p90) mm/día.
- [x] Se verifican en CMR los nombres reales de los productos y de las capas (ET diaria, ESI, nube, agua) y se anotan (ver "Verificado en la prueba real": versión 003, capas `ETdaily`, `ESI`, `cloud`, `water`).
- [x] Varias pasadas el mismo día quedan en una sola fecha (la más limpia) y la `nota` lo dice: test `test_dos_pasadas_el_mismo_dia_queda_la_mas_limpia` y casos reales del 22/12, 2/1 y 19/2 ("2 pasadas ese día").
- [x] Pasada con nube sobre el lote → `descartada` con `valor: null`: test `test_nube_sobre_el_lote_queda_descartada` y 6 fechas reales (por ejemplo 25/12 y 23/2, 0 % válido).
- [x] El enlace firmado de LP DAAC se resuelve antes de que GDAL lea: tests `test_enlace_firmado_*` y la prueba real leyó los archivos por el enlace firmado (22 observaciones de diciembre a febrero en 32 s, ninguna con error de lectura).
- [x] ECOSTRESS no importa código de ningún otro satélite (`tests/test_nucleo.py` en verde).
- [x] Tests sin internet (36 en `tests/test_ecostress.py`); prueba real "Probar ECOSTRESS (evapotranspiración y estrés)" verde, con un clic y en cada PR que toque el conector.

## Fuera de alcance

Temperatura de superficie (L2T LSTE), eficiencia en el uso del agua (L4T WUE), versiones viejas (colección 1), las otras estimaciones de ET del ensamble (PT-JPL-SM, STIC, BESS, PM) y relleno de días sin pasada (interpolación).
