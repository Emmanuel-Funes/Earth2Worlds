# Spec 055 · Productividad diaria con SMAP L4 Carbono

**Estado:** construida y probada con datos reales · **Aprobada por:** Hernán ("Okey, avanzamos", sobre el informe de satélites nuevos) · **Rama:** `SMAP-productividad_carbono` · **Depende de:** (`NUCLEO-varios_respaldos_en_orden`) · **Requiere:** Earthdata (ya cargado)

## Objetivo

Saber **cuánto carbono fija la vegetación de la zona cada día** (productividad primaria bruta, GPP) y si el ecosistema gana o pierde carbono (NEE). La productividad de MODIS (MOD17) se apaga con MODIS. SMAP L4 Carbono sale todos los días y no depende de MODIS para su humedad.

Es un dato **regional**. Una celda de 9 km tiene ~8.100 ha, así que el lote de 25 ha es una parte chica. Sirve para:

- comparar la campaña actual con las anteriores en la zona;
- ver el arranque de la primavera (cuándo la vegetación empieza a fijar más de lo que respira);
- dar contexto al motor (fase 2) junto al NDVI del lote.

**No es rinde** ni la productividad del lote.

## Fuente

| Producto | Agencia | Qué da | Grilla | Atraso | Acceso |
|---|---|---|---|---|---|
| `SPL4CMDL` (la versión más nueva en CMR; hoy la 008) | NASA (GMAO / NSIDC) | GPP y NEE diarios en g C/m²/día, también por tipo de vegetación (cereales = PFT 7, latifoliadas = PFT 8) | EASE-Grid 2.0 global de 9 km | ~4 días (último dato al 28/10: 23/10) | CMR + OPeNDAP de Earthdata, **un solo pedido por día** |

Cada archivo pesa ~140 MB. El conector no lo baja: pide por OPeNDAP solo las 4 capas de la celda del lote en un único pedido.

## Entrada

`lote["id"]`, `lote["poligono"]` (GeoJSON EPSG:4326), `desde`–`hasta` (máximo 366 días).

## Proceso

1. Validar el pedido. Un pedido inválido no llama a la NASA.
2. Ubicar el **centro del lote** en la grilla EASE-Grid 2.0 de 9 km (EPSG:6933, 1624 × 3856 celdas). Para el lote de prueba da fila 1262, columna 1228, y se verificó contra la latitud y longitud del archivo real.
3. Pedir a CMR los archivos diarios del período y, por cada día, un recorte OPeNDAP con `GPP/gpp_mean`, `NEE/nee_mean`, `GPP/gpp_pft7_mean` (cereales) y `GPP/gpp_pft8_mean` (latifoliadas). Se piden 2 columnas porque el servidor no responde con un solo valor, como en GLDAS y FLDAS.
4. Si OPeNDAP corta el pedido (502 o conexión cerrada), se reintenta hasta 3 veces.
5. Hasta 8 días se piden en paralelo.

## Salida (contrato común)

```json
{"lote_id": "lote-prueba", "fecha": "2026-10-15", "variable": "gpp_g_c_m2_dia", "valor": 2.037,
 "unidad": "g C/m²/día", "fuente": "SMAP", "resolucion_m": 9000, "calidad": "buena",
 "nota": "SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 2.05 · latifoliadas 1.88 · celda fila 1262, columna 1228 · SMAP_L4_C_mdl_20261015T000000_Vv8043_001.h5_PpqDJbbz"}
{"variable": "nee_g_c_m2_dia", "valor": 0.718, "...": "positivo = la zona pierde carbono (respira más de lo que fija)"}
```

- Variables nuevas: `gpp_g_c_m2_dia` y `nee_g_c_m2_dia`.
- No cambia el contrato: `fuente: "SMAP"` ya existe.

## Reglas de calidad

1. **Nunca inventar.** Relleno (−9999), valores no numéricos o fuera de rango (GPP fuera de 0 a 30, NEE fuera de −30 a 30) → `descartada`, con `valor: null`.
2. Valor válido → `buena`. La nota siempre aclara que es **dato regional de 9 km, no del lote**.
3. **Supuesto:** 30 g C/m²/día es el techo físico para un cultivo (el maíz en pleno verano anda en 15 a 20).
4. **Supuesto:** lotes más grandes que una celda usan la celda del centro. Para lotes del tamaño de la prueba (25 ha) da igual.
5. **Riesgo:** SMAP figura entre las misiones con riesgo de presupuesto desde 2027. Si deja de salir, el conector devuelve vacío y no inventa.

## Dónde entra

- **Registro (spec 009):** `SATELITES = [Satelite("SMAP_L4C", pedir)]`. Es una fuente propia, no un respaldo, y no toca el núcleo.
- **Ruta de prueba:** `POST /productividad`.
- No toca Render hasta que Hernán lo pida.

## Prueba real

Workflow `Probar SMAP (productividad)` y `probar_smap_carbono.py`. Por defecto usa el lote de prueba de San Luis, del 1/8 al 27/10/2026.

## Resultado de la prueba real

Corrida desde el entorno NASA (GitHub Actions sigue pausado). Lote de prueba, celda fila 1262, columna 1228. Del 1/8 al 27/10/2026: **84 días, 84 con dato, 70 s.** El último día publicado es el 23/10.

| Mes | Días | GPP media | GPP mín.–máx. | NEE media |
|---|---|---|---|---|
| Agosto | 31 | 1,82 | 0,70 – 2,37 | +0,56 |
| Septiembre | 30 | 2,10 | 0,38 – 3,17 | +0,60 |
| Octubre (al 23) | 23 | 1,94 | 0,78 – 3,25 | +0,91 |

*(g C/m²/día)*

**Lectura:** la productividad de la zona sube de agosto a septiembre y tiene su máximo el **5/10 (3,25)**, con la primavera. La NEE es **positiva todo el período**: la zona respira más carbono del que fija. Eso es lo esperable con lotes en barbecho y verdeos de invierno antes de la siembra gruesa. Cuando los cultivos de verano cierren el surco (diciembre-enero), la NEE debería pasar a negativa. El 15/10 el dato coincidió con la lectura directa del archivo HDF5 del informe del 27/10 (GPP 2,037).

Una primera versión leía el archivo por pedazos (~12 MB y ~8 s por día) y tardó 9 min con cortes 502. Con OPeNDAP es un pedido por día. 15 tests sin internet en verde.
