# Spec 005 · Respaldos de la NASA

**Estado:** aprobada por Hernán (tarjeta "Solo NASA") · **Pedido por:** Hernán ("¿se podrían agregar backups a los satélites?" y "los respaldos tienen que ser también de la NASA")

## Objetivo

Que cada dato tenga un **respaldo de la NASA** que entra solo cuando la fuente principal falla, para que la app siempre tenga datos de la NASA guardados. Nunca se usan fuentes que no sean de la NASA.

| Dato | Principal | Respaldos, en orden | Rama |
|---|---|---|---|
| Humedad del suelo | SMAP L4 leído **directo** de la NASA (CMR + OPeNDAP) | 1.º el mismo SMAP L4 pedido a **AppEEARS**; 2.º SMAP L3 observado (9 km, sin zona de raíces) | `SMAP-humedad_suelo` y `SMAP_L3-humedad_respaldo` (spec 015) |
| Lluvia | GPM IMERG (lluvia diaria, ~10 km) | NASA POWER (`PRECTOTCORR`, ~55 km) | `IMERG-lluvia` (spec 006) y `POWER-lluvia_respaldo` (spec 013) |
| Temperatura y radiación | NASA POWER | MERRA-2 (solo hasta ~1 mes atrás: la NASA lo publica con ese retraso) | `MERRA2-clima_respaldo` (spec 006) |
| NDVI y NDMI | HLS (30 m) | 1.º Sentinel-2 L2A de la ESA (10-20 m, NDVI y NDMI); 2.º VIIRS de NOAA-20/21 (500 m, 16 días); 3.º MODIS MOD13Q1 de Terra (250 m, 16 días; fin de misión en 2026) | `SENTINEL2-NDVI_NDMI_respaldo` (spec 014), `VIIRS-NDVI_respaldo` (spec 011) y `MODIS-NDVI_respaldo` (spec 007) |
| Altura, pendiente y ambientes | NASADEM (30 m) | Copernicus DEM de la ESA (30 m) | `NASADEM-altimetria` y `COPDEM-altimetria_respaldo` (spec 016) |
| Evapotranspiración | MODIS MOD16A2/MYD16A2 (500 m, 8 días) | 1.º ECOSTRESS (70 m, también da el estrés hídrico ESI); 2.º ET de referencia FAO-56 calculada con POWER (otra variable: `et0_mm_dia`) | `MODIS-evapotranspiracion` (spec 017), `ECOSTRESS-evapotranspiracion_estres` (spec 018) y `POWER-ET0_FAO56_respaldo` (spec 019) |
| Suelo del lote | Cartas de suelo del INTA (GeoINTA) | Sin respaldo: es un dato fijo | `GeoINTA-suelos` (spec 020) |

Se descartó Open-Meteo: no es de la NASA, y en la prueba real su humedad estaba en otra escala que SMAP (San Luis, 1 al 14 de enero de 2026: 0,30 a 0,33 contra 0,05 a 0,06 m³/m³).

## SMAP: dos caminos al mismo dato

| | Directo (principal) | AppEEARS (respaldo) |
|---|---|---|
| Cómo | Busca en CMR los archivos de 3 h de cada día y lee **solo el píxel del lote** por OPeNDAP | Crea un pedido por punto y espera que la NASA lo procese |
| Demora | ~1,5 s por archivo, 8 en paralelo | De 5 a 40 minutos, según la fila |
| Dato | `SPL4SMGP` versión vigente, celda EASE-Grid 2.0 de 9 km | El mismo |
| `nota` | `… · vía NASA directo` | `… · vía AppEEARS` |

Ambos se guardan con `fuente: "SMAP"`: es el mismo producto, por eso no hay saltos al pasar de uno a otro.

Detalles del camino directo:
1. Token de Earthdata con `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD`.
2. Colección `SPL4SMGP` más nueva del proveedor `NSIDC_CPRD` en CMR.
3. Un día = los 8 archivos cuya hora central cae en ese día (UTC), igual que AppEEARS.
4. Fila y columna de la celda con la fórmula de EASE-Grid 2.0 (EPSG:6933). Verificado: el lote de prueba (-33,70; -65,30) cae en la celda 1262, 1228, de centro -33,67; -65,31.
5. Mismas reglas de calidad que la spec 003.

Si AppEEARS queda `pendiente`, a la noche siguiente se **reusa el mismo pedido** (mismo lote, punto y fecha de inicio) aunque la fecha final haya avanzado un día.

## Cuándo entra un respaldo

En la actualización nocturna (spec 004), por lote y por fuente:
- Si la principal termina en `error`, se pide **el mismo período** al respaldo.
- Si una principal tiene **varios respaldos**, entran en orden (campo `orden` del `Satelite`, el menor primero) hasta que uno guarde datos. Si un respaldo falla o no trae nada, entra el siguiente. Ejemplo: HLS → Sentinel-2 → VIIRS → MODIS (VIIRS y MODIS: decisión de Hernán; Sentinel-2 se sumó, "sumar lo necesario para cubrir lo que hace falta", con los socios de la NASA habilitados).
- Si la principal anduvo bien, el respaldo **no se consulta**.
- El resultado queda en `actualizaciones` con el nombre `FUENTE:camino` (por ejemplo `SMAP:AppEEARS`), y `/lotes/{id}/estado` muestra su última fecha con dato.
- Una principal caída **con** su respaldo guardado no marca la corrida como fallida.

## Cómo se lee

- `GET /lotes/{id}/observaciones` devuelve todo lo guardado, cada valor con su `fuente`.
- `GET /lotes/{id}/observaciones?combinar=true` devuelve **una serie por variable**: por fecha, la fuente más confiable que tenga valor. Orden: productor > principal (POWER, HLS, SMAP, IMERG, ECOSTRESS, NASADEM, GeoINTA) > respaldo (Sentinel-2, MERRA-2, Copernicus DEM) > VIIRS > MODIS. Excepción por variable (`PRIORIDAD_POR_VARIABLE`): en la ET real (`et_mm_dia`) MODIS es la principal y le gana a ECOSTRESS.

## Criterios de aceptación

- [x] SMAP directo da el mismo valor que AppEEARS para el mismo día y punto (lote de prueba, 1 al 14 de enero de 2026: idénticos a 3 decimales; 14 días en 29 segundos).
- [x] SMAP directo caído → entra AppEEARS para el mismo período y se guarda como `SMAP`.
- [x] AppEEARS pendiente se retoma con el mismo pedido la noche siguiente.
- [x] Principal OK → el respaldo no se consulta.
- [x] `combinar=true` elige la principal y rellena con el respaldo solo donde falta.
- [x] Tests sin internet; prueba real con un clic y automática en cada PR que toque el conector.
- [x] Lluvia IMERG y temperatura MERRA-2 como respaldo de POWER (spec 006, verificado con datos reales).
- [x] NDVI MODIS como respaldo de HLS (spec 007, verificado con datos reales).
- [x] La ET real prefiere MODIS sobre ECOSTRESS al combinar, y el productor sigue ganando a todos (test `test_combinar_prefiere_modis_sobre_ecostress_para_la_et`).
- [x] Varios respaldos en orden: si el primero cubre, el segundo no se pide; si falla o no trae datos, entra el siguiente (tests `test_varios_respaldos_entran_en_orden_hasta_que_uno_cubre` y `test_si_el_primer_respaldo_falla_o_no_trae_datos_entra_el_siguiente`).

## Fuera de alcance

Corrección con estaciones locales (SMN, INTA) y datos del productor.
