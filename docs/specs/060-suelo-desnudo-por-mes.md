# Spec 060 · Meses de suelo desnudo del lote con MODIS

**Estado:** construida y probada con datos reales · **Aprobada por:** Hernán ("Vamos con la partes de satelites y obtencion de datos que es lo mio, avancemos", sobre los faltantes del desafío Field Shift) · **Rama:** `MODIS-suelo_desnudo_por_mes` · **Depende de:** (`NUCLEO-varios_respaldos_en_orden`) · **Requiere:** Earthdata (ya cargado)

## Objetivo

El desafío pide mostrar **cuándo los lotes quedan típicamente desnudos**. En los suelos arenosos de San Luis es cuando el viento se lleva el suelo, se pierde agua por evaporación y no se suma carbono. Es el hueco donde puede entrar un cultivo de servicio o un verdeo, y es un dato clave para comparar rotaciones.

## Fuente

| Producto | Agencia | Qué da | Píxel | Acceso |
|---|---|---|---|---|
| `MOD13Q1` (la versión más nueva en CMR; hoy la 061) | NASA (MODIS Terra, LP DAAC) | NDVI de compuestos de 16 días con confiabilidad por píxel | 250 m | CMR + OPeNDAP de Earthdata, solo la ventana del lote |

- **Período: los últimos 48 meses completos** (por ejemplo, del 1/10/2022 al 30/9/2026). El OPeNDAP de la NASA sirve MOD13Q1 recién desde mediados de 2022: los compuestos anteriores dan 404 (probado año por año, de 2015 a 2026).
- Satélite independiente (spec 009): repite a propósito la lectura de MODIS del conector de NDVI y no lo importa.

## Proceso

1. Validar el polígono. Ubicar el mosaico y la ventana de píxeles del lote, con un píxel de margen.
2. Pedir a CMR los compuestos del período y leer, de a 4 a la vez, NDVI, confiabilidad, día de cada píxel, latitud y longitud.
3. Por compuesto: mediana del NDVI de los píxeles del lote con confiabilidad 0 o 1. Si se ve menos de la mitad del lote, el compuesto no cuenta. La fecha es la mediana del día de adquisición.
4. Por mes y por año: mediana de los compuestos de ese mes.
5. Por mes: **en qué porcentaje de los años el lote estuvo desnudo** (NDVI < 0,25) y con **cobertura baja** (NDVI < 0,30).
6. Resumen: los meses en que eso pasó en la mitad de los años o más.
7. Memoria por lote hasta el mes siguiente.

## Salida (contrato común)

| Variable | Unidad | Qué es |
|---|---|---|
| `meses_suelo_desnudo` | meses | Cuántos meses el lote suele quedar desnudo; la nota dice cuáles |
| `meses_cobertura_baja` | meses | Cuántos meses suele quedar con cobertura baja; la nota dice cuáles |
| `suelo_desnudo_mes_01_pct` … `_12_pct` | % de los años | En qué porcentaje de los años ese mes el lote estuvo desnudo; la nota trae la cobertura baja y el NDVI de cada año |

`fuente: "MODIS"`, `resolucion_m: 250`, `fecha` = último día del período.

## Reglas de calidad

1. **Nunca inventar.** Un mes con menos de 3 años con el lote visible → `descartada`. Sin ningún compuesto → `descartada`. Si ningún compuesto llega, es un error (502), no un "nunca desnudo".
2. Un mes con 3 años o más → `buena`. El resumen es `dudosa` si falta algún mes.
3. **Supuesto:** NDVI < 0,25 = suelo desnudo o rastrojo ralo; < 0,30 = cobertura baja. Un pastizal muy seco también puede caer abajo. A validar con un agrónomo.
4. **Supuesto:** un píxel de 250 m (6 ha) mezcla el lote con sus bordes. En lotes de menos de 6 ha se usa el píxel del centro.
5. **Riesgo:** MODIS Terra está terminando su vida útil. El reemplazo natural es el NDVI de VIIRS (500 m).

## Tiempo

**~100 s** la primera vez (91 compuestos en la prueba). Después, al instante.

## Dónde entra

- **Registro (spec 009):** `SATELITES = [Satelite("SUELO_DESNUDO", pedir)]`. Fuente propia; no toca el núcleo.
- **Ruta de prueba:** `POST /suelo-desnudo` con `lote_id` y `poligono`.

## Criterios de aceptación

- [x] Tests sin internet: período de 48 meses, ventana del lote, NDVI del lote y nubes, compuesto que cruza el año, agrupado por mes, porcentajes y resumen, sin datos no inventa, memoria, solo el mosaico del lote, ningún compuesto es error, ruta que valida el polígono.
- [x] Prueba real sobre el lote de San Luis.
- [ ] Validar los umbrales de 0,25 y 0,30 con un agrónomo.

## Prueba real

Desde el entorno de la nube (`probar_suelo_desnudo.py` con el lote de prueba de 25 ha), del 10/2022 al 09/2026. **100 s.** 91 de 117 compuestos con el lote visible.

| Mes | NDVI mediano | Cobertura baja (% de los años) |
|---|---|---|
| Enero a abril | 0,56 a 0,85 | 0 % |
| Mayo | 0,42 | 0 % |
| Junio y julio | 0,31 a 0,36 | 0 a 25 % |
| **Agosto** | 0,29 | **50 %** |
| Septiembre | 0,31 | 25 % |
| **Octubre** | 0,31 | **50 %** |
| Noviembre | 0,33 | 25 % |
| **Diciembre** | 0,34 | **50 %** |

**Lectura:** el lote no queda nunca del todo desnudo, pero de **agosto a diciembre** tiene cobertura baja la mitad de los años, justo en la época de los vientos de primavera. Es la ventana para un cultivo de servicio o un verdeo de invierno que llegue a primavera con el suelo tapado.
