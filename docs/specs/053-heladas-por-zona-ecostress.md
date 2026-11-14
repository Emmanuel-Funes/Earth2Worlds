# Spec 053 · Heladas por zona del lote con ECOSTRESS (70 m, de noche)

**Estado:** construida y probada con datos reales · **Aprobada por:** Hernán ("Okey, avanzamos", sobre el informe de satélites nuevos) · **Rama:** `ECOSTRESS-heladas_por_zona` · **Depende de:** (`NUCLEO-varios_respaldos_en_orden`) · **Requiere:** Earthdata (ya cargado)

## Objetivo

Mostrar **en qué parte del lote** hiela. VIIRS (spec 030) da todas las noches un solo píxel de 1 km para todo el lote. ECOSTRESS mide la temperatura de superficie a **70 m**, así que en un lote de 25 ha ve unos 50 píxeles y marca los bajos donde se junta el aire frío. Cruzado con el relieve (NASADEM: bajo, media loma, loma) sirve para decidir dónde sembrar primero y dónde no poner cultivos sensibles.

## Fuente

| Producto | Agencia | Qué da | Píxel | Pasadas | Acceso |
|---|---|---|---|---|---|
| `ECO_L2T_LSTE` (la versión más nueva en CMR; hoy la 003), capas `LST`, `cloud`, `water` | NASA (JPL, Estación Espacial) | Temperatura de superficie en kelvin | 70 m, mosaicos UTM | Sin horario fijo: entre el 1/8 y hubo 13 noches con pasada sobre el lote | CMR + GeoTIFF por HTTP (enlace firmado de LP DAAC, igual que el ECOSTRESS de la ET) |

## Entrada

`lote["id"]`, `lote["poligono"]` (GeoJSON EPSG:4326), `desde`–`hasta` (máximo 366 días).

## Proceso

1. Validar el pedido. Un pedido inválido no llama a la NASA.
2. Buscar en CMR los mosaicos que tocan el lote (un día de margen a cada lado) y quedarse con las pasadas **de noche**: de 20 a 8 h **hora solar** (UTC + longitud/15).
3. Fechar cada pasada por **la madrugada**: una de 22 h cuenta para la noche que termina al día siguiente.
4. Leer solo la ventana del lote de `LST`, `cloud` y `water`. Un píxel vale si: hay temperatura, está entre −25 y 70 °C, la máscara de nube no es 1 y la de agua no es 1. Una máscara en 255 no es nube: es que la franja del satélite no pasó por ahí.
5. Con los píxeles del lote que valen: mínima, mediana, máxima, % a 0 °C o menos y coordenadas del punto más frío.
6. Si hay dos pasadas la misma noche, gana la que tiene más píxeles válidos.

## Salida (contrato común, dos variables nuevas)

```json
{"lote_id": "lote-prueba", "fecha": "2026-10-08", "variable": "temp_sup_min_70m_c", "valor": -0.2,
 "unidad": "°C", "fuente": "ECOSTRESS", "resolucion_m": 70, "calidad": "buena",
 "nota": "ECOSTRESS LST nocturna a 70 m (temperatura de superficie, no del aire) · mínima -0.2 · mediana 3.2 · máxima 4.0 °C · 2% del lote a 0 °C o menos · punto más frío en -33.70465, -65.2958 · válidos 98% · riesgo de helada (≤ 0 °C de superficie) · pasada 2026-10-08 07:54 UTC (03:32 hora solar) · ECOv003_L2T_LSTE_..."}
{"variable": "helada_superficie_pct", "valor": 2.0, "unidad": "%", "...": "misma fecha, calidad y nota"}
```

- `temp_sup_min_70m_c`: temperatura de superficie del píxel más frío del lote.
- `helada_superficie_pct`: qué parte del lote quedó a 0 °C o menos.
- No cambia el contrato: `variable` es texto libre y `fuente: "ECOSTRESS"` ya existe.

## Reglas de calidad

1. **Nunca inventar.** Con menos del 20 % de píxeles válidos, la noche queda `descartada` con `valor: null`, y la nota dice qué parte del lote tenía nube y qué parte no tenía medición.
2. Válidos ≥ 60 % → `buena`; ≥ 20 % → `dudosa`.
3. **Supuesto agronómico:** es temperatura de **superficie**, no del aire a 1,5 m. De noche y despejado suele dar 2 a 5 °C menos que el abrigo. Es una alerta y un mapa de zonas, no la helada meteorológica oficial.
4. **Supuesto:** −25 °C es el piso físico. Más frío es una nube que se escapó a la máscara (en la prueba aparecieron −33 °C con nube marcada).
5. ECOSTRESS **no pasa todas las noches**. La app sigue usando VIIRS para la alerta diaria; ECOSTRESS suma el detalle las noches que hay.

## Dónde entra

- **Registro (spec 009):** `SATELITES = [Satelite("ECOSTRESS_LST", pedir)]`. Es una fuente propia, no un respaldo, y no toca el núcleo.
- **Ruta de prueba:** `POST /heladas-por-zona` (igual que los demás satélites, para probar desde `/docs`).
- No toca Render hasta que Hernán lo pida.

## Prueba real

Workflow `Probar ECOSTRESS (heladas por zona)` y `probar_ecostress_heladas.py`. Por defecto usa el lote de prueba de San Luis, con un período automático que se cuenta desde el día en que corre.

## Resultado de la prueba real

Corrida desde el entorno NASA (GitHub Actions sigue pausado por facturación). Lote de prueba (-33,700; -65,300)–(-33,705; -65,295). Del 1/8 al 27/10/2026, respuesta en **27 s**:

| Noche | Mínima del lote | % del lote ≤ 0 °C | Mediana | Calidad |
|---|---|---|---|---|
| 1/8 (22:42 h solar) | 6,7 °C | 0 % | 7,6 °C | buena (100 % válidos) |
| **8/10 (03:32 h solar)** | **−0,2 °C** | **2 %** | 3,2 °C (máx. 4,0) | buena (98 %) |
| 24/10 (21:22 h solar) | 3,4 °C | 0 % | 3,7 °C | dudosa (31 %) |
| otras 10 noches | — | — | — | descartadas (nubes o franja al costado del lote) |

- 13 noches con pasada, **3 con dato**, 1 con riesgo de helada. Ese mismo 8/10, NASA POWER dio 9,5 °C de mínima del aire a 55 km de grilla.
- Dentro del lote hubo **4,2 °C de diferencia** entre el punto más frío (esquina sur, -33,70465; -65,2958) y el más templado. Afuera del polígono, a menos de 300 m, la misma pasada llegó a −2,9 °C (informe del 27/10, ventana de 7×7 píxeles).
- 17 tests sin internet en verde.
