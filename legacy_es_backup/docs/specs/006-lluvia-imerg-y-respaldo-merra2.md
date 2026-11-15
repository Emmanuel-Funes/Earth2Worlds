# Spec 006 · Lluvia GPM IMERG y respaldo MERRA-2 para el clima

**Estado:** aprobada por Hernán (tarjeta "Solo NASA"; IMERG figura como fuente del MVP en la Guía técnica) · **Etapa:** pipeline satélite → API → app (sin interfaz) · **Requiere:** cuenta NASA Earthdata con la aplicación "NASA GESDISC DATA ARCHIVE" autorizada

## Objetivo

1. Sumar la **lluvia diaria de GPM IMERG**, la mejor estimación satelital de lluvia de la NASA, como fuente principal de `lluvia_mm`.
2. Darle a NASA POWER un **respaldo de la NASA** para temperatura y radiación: **MERRA-2**.

Así la lluvia tiene dos fuentes NASA a la vez (IMERG y POWER): si una falla, la otra ya está guardada.

## Fuentes

| Producto | Qué da | Grilla | Demora de publicación | Variables Rotaterra |
|---|---|---|---|---|
| IMERG Final diario (`GPM_3IMERGDF`) | Lluvia corregida con pluviómetros | 0,1° (~10 km) | ~3,5 meses | `lluvia_mm` |
| IMERG Late diario (`GPM_3IMERGDL`) | Lluvia sin corregir con pluviómetros | 0,1° (~10 km) | ~1 a 2 días | `lluvia_mm` |
| MERRA-2 diario (`M2SDNXSLV`) | Temperatura máxima y mínima a 2 m | 0,5° × 0,625° (~55 km) | ~1 mes | `temp_max`, `temp_min` |
| MERRA-2 radiación (`M2T1NXRAD`) | Radiación solar en superficie, horaria | 0,5° × 0,625° | ~1 mes | `radiacion` |

Todo se lee por **OPeNDAP de la NASA** (solo el punto del lote), con un token de Earthdata.

## Entrada

`lote_id`, `lat`, `lon` (centro del lote, EPSG:4326), `desde`, `hasta` (máximo 366 días), igual que POWER.

## Proceso

**IMERG**
1. Para cada día se usa **Final** si ya está publicado; si no, **Late**. La `nota` dice cuál (`IMERG Final, corregido con pluviómetros` o `IMERG Late, sin corregir con pluviómetros`).
2. Se lee la celda de 0,1° que contiene el centro del lote. El día es el día UTC del archivo.

**MERRA-2**
1. `temp_max` y `temp_min`: `T2MMAX` y `T2MMIN` del día, de Kelvin a °C.
2. `radiacion`: promedio de las 24 horas de `SWGDN` (W/m²) × 0,0864 = MJ/m²/día, la misma unidad que POWER.
3. Se usa la celda más cercana al centro del lote.
4. Los días que MERRA-2 todavía no publicó no se devuelven (no se inventan).
5. Si la NASA lista el archivo de un día pero OPeNDAP no lo entrega (404), ese día vuelve con `valor: null`, `calidad: "descartada"` y la `nota` lo dice, y los demás días siguen. Antes ese único día hacía caer todo el pedido: lo encontró el control diario de las fuentes (spec 042) con el archivo del 14/11/2026.

## Salida (contrato común)

```json
{"lote_id": "lote-7", "fecha": "2026-11-14", "variable": "lluvia_mm", "valor": 22.3,
 "unidad": "mm/día", "fuente": "IMERG", "resolucion_m": 10000, "calidad": "buena",
 "nota": "IMERG Late, sin corregir con pluviómetros · celda de 0,1°"}
```

MERRA-2 sale con `fuente: "MERRA2"` y `resolucion_m: 55000`.

## Reglas

1. **Nunca inventar.** Valor de relleno (`-9999.9` en IMERG, `1e15` en MERRA-2) o día sin archivo → `valor: null`, `calidad: "descartada"` (IMERG) o día omitido (MERRA-2).
2. Rango físico: lluvia 0 a 500 mm/día; temperatura -40 a 60 °C; radiación 0 a 50 MJ/m²/día. Fuera de rango → `dudosa`, sin corregir.
3. IMERG Late → `calidad: "buena"` pero la `nota` aclara que no está corregido con pluviómetros.

## Dónde entra

- **Actualización nocturna (spec 004):** IMERG es una fuente más (`POWER`, `HLS`, `SMAP`, `IMERG`).
- **Respaldo (spec 005):** si POWER falla, se pide el mismo período a MERRA-2 (`POWER:MERRA2` en `actualizaciones`). La lluvia no necesita respaldo aparte: IMERG ya la guarda.
- **`combinar=true`:** para `lluvia_mm` gana IMERG sobre POWER (es un producto específico de lluvia); para el resto gana POWER sobre MERRA-2.

## API

`GET /lluvia?lote_id=…&lat=…&lon=…&desde=…&hasta=…` → lista de observaciones de IMERG. `422` parámetros inválidos, `503` faltan credenciales, `502` la NASA no responde. La app lo llama y espera la respuesta (spec 010).

## Criterios de aceptación

- [x] Con un punto real se obtiene la lluvia de IMERG por día, con Final o Late según corresponda (lote de prueba, 1 al 14 de enero de 2026: 32 mm, IMERG Late, en 4 segundos).
- [x] Con un punto real MERRA-2 da temperatura máxima, mínima y radiación por día (mismo lote y período, 14 días completos).
- [x] Relleno y rangos se marcan según las reglas.
- [x] POWER caído → entra MERRA-2 para el mismo período.
- [x] `combinar=true` prefiere IMERG para la lluvia.
- [x] Tests sin internet; prueba real con un clic y automática en cada PR que toque estos conectores.

## Fuera de alcance

Anomalía de lluvia frente al histórico y balance hídrico (specs propias). Corrección con pluviómetros del productor.
