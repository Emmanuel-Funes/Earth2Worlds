# Spec 003 · Conector SMAP: humedad del suelo

**Estado:** implementada y verificada (PR #6 y #9) · **Etapa:** pipeline satélite → API → app (sin interfaz) · **Requiere:** cuenta NASA Earthdata

## Objetivo

Que la app pueda pedir la humedad del suelo diaria de un lote, en superficie y en la zona de raíces, y recibirla en el contrato JSON común. Es el insumo del balance hídrico (agua útil) que viene después.

## Fuente

**SMAP L4** (`SPL4SMGP`, la versión vigente): humedad modelada con asimilación del satélite SMAP, cada 3 horas, grilla de **9 km**. Hay dos caminos al mismo dato, los dos de la NASA y con la cuenta Earthdata (detalle en la spec 005):

- **Directo (principal):** CMR + OPeNDAP, se lee solo el píxel del lote en cada archivo de 3 h. Tarda segundos.
- **AppEEARS (respaldo):** servicio de la NASA que recorta productos por punto. Tarda minutos por la fila de espera.

| Variable Rotaterra | Capa SMAP | Profundidad | Unidad |
|---|---|---|---|
| `humedad_superficial` | `sm_surface` | 0 a 5 cm | m³/m³ |
| `humedad_zona_raiz` | `sm_rootzone` | 0 a 100 cm | m³/m³ |

m³/m³ es la fracción del volumen de suelo ocupada por agua: 0,25 equivale a 25 % en volumen.

## Entrada

| Campo | Tipo | Ejemplo |
|---|---|---|
| `lote_id` | texto | `lote-7` |
| `lat`, `lon` | centro del lote, EPSG:4326 | `-33.70`, `-65.30` |
| `desde`, `hasta` | fecha `AAAA-MM-DD` | campaña |

## Proceso

Camino directo (principal):
1. Pedir un token de Earthdata con usuario y contraseña (secretos `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD`).
2. Buscar en CMR los archivos de 3 h del período y leer por OPeNDAP solo la celda de 9 km que contiene el centro del lote.

Camino AppEEARS (respaldo):
1. Iniciar sesión en AppEEARS, averiguar la versión vigente de `SPL4SMGP` y el nombre exacto de sus capas.
2. Crear un pedido por punto, esperar a que termine y bajar el CSV de resultados.
3. Si ya existe un pedido del mismo lote, punto y fecha de inicio en la fila o terminado, se reusa en vez de crear otro.

En los dos caminos:
- Se promedian los 8 valores de 3 horas de cada día (UTC). Si falta alguno, se promedian los que hay y se aclara en `nota`.
- Todos los días pedidos aparecen en la respuesta: un día sin archivos queda `null` + `descartada`.
- La `nota` dice por qué camino llegó el dato (`vía NASA directo` o `vía AppEEARS`).

## Salida

```json
{
  "lote_id": "lote-7", "fecha": "2026-01-15", "variable": "humedad_zona_raiz",
  "valor": 0.214, "unidad": "m³/m³", "fuente": "SMAP",
  "resolucion_m": 9000, "calidad": "buena",
  "nota": "Promedio de 8 valores de 3 h · celda de 9 km: contexto regional, no dato del lote · vía NASA directo"
}
```

## Reglas

1. **Nunca inventar un valor.** Valor de relleno (`-9999`) o día sin datos → `valor: null`, `calidad: "descartada"`.
2. Fuera de rango físico (menor a 0 o mayor a 0,6 m³/m³) → `dudosa`, sin corregir.
3. Día con menos de 8 valores de 3 h → `dudosa`, con la cantidad en `nota`. Si además está fuera de rango, la `nota` dice los dos motivos.
4. SMAP es **contexto regional** (9 km): la `nota` siempre lo aclara. No reemplaza la medición del lote.
5. Rango máximo por consulta: 366 días.

## API

`GET /humedad-suelo?lote_id=…&lat=…&lon=…&desde=…&hasta=…` → lista de observaciones, por el camino directo. `422` parámetros inválidos, `503` faltan credenciales, `502` NASA no responde. La app lo llama y espera la respuesta (spec 010).

## Criterios de aceptación

- [x] Con un punto real se obtienen las dos variables por día (-33,70; -65,30, del 1 al 14 de enero de 2026: 28 de 28 valores buenos, en 25 segundos por el camino directo).
- [x] Relleno, rango y días incompletos se marcan según las reglas.
- [x] Todo el diálogo con AppEEARS y con CMR/OPeNDAP tiene tests con respuestas simuladas (sin internet).
- [x] Prueba real con un clic desde Actions, y automática en cada PR que toque el conector.

## Fuera de alcance

Balance hídrico y agua útil en mm (requiere suelo de GeoINTA), anomalía frente al histórico, semáforo seco/normal/húmedo. Van en specs propias.
