# Spec 054 · Radar NISAR sobre el lote (20 m, con nubes o sin nubes)

**Estado:** construida y probada con datos reales · **Aprobada por:** Hernán ("Okey, avanzamos", sobre el informe de satélites nuevos) · **Rama:** `NISAR-radar_del_lote` · **Depende de:** (`NUCLEO-varios_respaldos_en_orden`) · **Requiere:** Earthdata (ya cargado)

## Objetivo

Tener un dato del lote que **no dependa de las nubes**. HLS (NDVI) queda en blanco cuando está nublado, justo en las semanas de lluvia. El radar de NISAR (misión NASA-ISRO) atraviesa las nubes y mide cuánto "rebota" la señal en el suelo y en la planta:

- **HH** sube con el **suelo mojado** y la rugosidad (labranza, rastrojo).
- **HV** sube con la **biomasa** del cultivo (hojas y tallos que desordenan la señal).
- **HV − HH** sirve como indicador de cobertura: más alto, más planta.

Es dato **de apoyo**: se lee como "sube o baja" entre fechas. No da todavía humedad en m³/m³ ni biomasa en kg.

## Fuente

| Producto | Agencia | Qué da | Píxel | Pasadas sobre el lote | Acceso |
|---|---|---|---|---|---|
| `NISAR_L2_GCOV_V1` (validado, cuando exista) y si no `NISAR_L2_GCOV_PROVISIONAL_V1` | NASA-ISRO (ASF DAAC) | Retrodispersión gamma0 HH y HV, corregida por relieve | 20 m, UTM | 2 cada 12 días (traza 118 ascendente a las 10:19 UTC, traza 140 descendente a las 22:24 UTC) | CMR + HDF5 leído por pedazos por HTTP |

Cada archivo pesa ~1,8 GB y cubre unos 300 km. El conector **no lo baja**: lee solo los pedazos de ~1 MB que caen sobre el lote (14 a 22 MB por pasada en la prueba).

## Entrada

`lote["id"]`, `lote["poligono"]` (GeoJSON EPSG:4326), `desde`–`hasta` (máximo 366 días).

## Proceso

1. Validar el pedido. Un pedido inválido no llama a la NASA.
2. Buscar en CMR las imágenes que tocan el lote: primero el producto validado y, si no hay, el provisional.
3. Resolver el enlace firmado de ASF (el token de Earthdata no viaja a CloudFront) y leer por rangos HTTP: la proyección, los ejes x/y, la máscara y el recorte de HH y HV sobre el lote.
4. Píxeles del lote: los que tienen su centro adentro del polígono. Si el lote es más chico que un píxel, el más cercano al centro.
5. Un píxel vale si tiene potencia positiva y la máscara no es relleno (255). Se toma la **mediana de la potencia** y recién después se pasa a dB.
6. La fecha es el día en hora solar del lote. Si dos imágenes caen el mismo día, gana la que más cubre el lote.

## Salida (contrato común)

```json
{"lote_id": "lote-prueba", "fecha": "2026-10-09", "variable": "radar_hh_db", "valor": -8.1, "unidad": "dB",
 "fuente": "NISAR", "resolucion_m": 20, "calidad": "dudosa",
 "nota": "válidos 100% · HV − HH -7.9 dB (más alto = más planta) · NISAR banda L, gamma0 corregido por relieve · producto PROVISIONAL de la NASA · órbita descendente, traza 140 · pasada 2026-10-09 22:24 UTC · leídos 14 MB del archivo · NISAR_L2_PR_GCOV_..."}
{"variable": "radar_hv_db", "valor": -15.98, "...": "misma fecha, calidad y nota"}
```

- Variables nuevas: `radar_hh_db` y `radar_hv_db`.
- **Cambio en el núcleo:** se suma `"NISAR"` a `Fuente` en `contrato.py`, igual que hicieron FLDAS, ASTER y PERSIANN. No cambia nada más.
- Dependencia nueva: `h5py` (lectura de HDF5).

## Reglas de calidad

1. **Nunca inventar.** Con menos del 20 % de píxeles válidos, o con el lote fuera de la imagen, la fecha queda `descartada` con `valor: null`.
2. **Producto provisional → como mucho `dudosa`.** Cuando la NASA publique la versión validada, el conector la toma sola. Ahí se revisa si puede llegar a `buena`.
3. Válidos entre 20 % y 60 % → la nota agrega "lote parcialmente cubierto".
4. **Supuesto:** las dos órbitas (ascendente a la mañana y descendente a la tarde) miran el lote desde lados distintos y dan valores algo distintos. Por eso la nota dice la órbita y la traza, y conviene comparar fechas **de la misma traza**.

## Dónde entra

- **Registro (spec 009):** `SATELITES = [Satelite("NISAR", pedir)]`. Es una fuente propia, no un respaldo.
- **Ruta de prueba:** `POST /radar`.
- No toca Render hasta que Hernán lo pida.

## Prueba real

Workflow `Probar NISAR (radar)` y `probar_nisar.py`. Por defecto usa el lote de prueba de San Luis, del 1/8 al 27/10/2026.

## Resultado de la prueba real

Corrida desde el entorno NASA (GitHub Actions sigue pausado). Lote de prueba, del 1/8 al 27/10/2026. **12 pasadas, 12 con dato, 100 % de píxeles válidos, respuesta en 83 s.**

| Fecha | Traza | HH dB | HV dB | HV − HH |
|---|---|---|---|---|
| 10/8 | 140 desc. | −13,44 | −22,62 | −9,2 |
| 21/8 | 118 asc. | −13,51 | −22,56 | −9,1 |
| 2/9 | 118 asc. | −13,44 | −22,11 | −8,7 |
| 3/9 | 140 desc. | −14,47 | −22,90 | −8,4 |
| **14/9** | 118 asc. | **−9,29** | **−17,93** | −8,6 |
| 15/9 | 140 desc. | −13,53 | −22,12 | −8,6 |
| 26/9 | 118 asc. | −13,71 | −22,63 | −8,9 |
| 27/9 | 140 desc. | −14,40 | −22,99 | −8,6 |
| 8/10 | 118 asc. | −11,10 | −19,93 | −8,8 |
| **9/10** | 140 desc. | **−8,10** | **−15,98** | −7,9 |
| 20/10 | 118 asc. | −12,46 | −21,78 | −9,3 |
| 21/10 | 140 desc. | −13,42 | −21,92 | −8,5 |

**Lectura:** en seco, el lote está estable en unos −13,5 dB de HH. Hay dos saltos de 4 a 5 dB: el **14/9** y el **9/10**, este último en medio de las lluvias del 8 al 12/10. Es lo que se espera del suelo mojado. Doce días después vuelve a su valor de base. HV − HH se mantiene cerca de −9 dB, que es lo esperable para un lote en barbecho o con poca cobertura en primavera.

11 tests sin internet en verde (incluye la lectura por rangos con un servidor simulado y la redirección sin token).
