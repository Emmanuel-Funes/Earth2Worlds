# Spec 001 · Conector de clima NASA POWER

**Estado:** implementada y verificada (PR #2) · **Etapa:** pipeline satélite → API → app (sin interfaz)

## Objetivo

Que la app pueda pedir el clima diario de un lote (temperatura máxima y mínima, lluvia y radiación) y recibirlo en el **contrato JSON común** de Rotaterra.

## Por qué empezar por POWER

- No requiere cuenta ni credenciales.
- Tiene datos diarios desde 1981, base para los riesgos climáticos del motor de rotación.
- Sirve para validar el contrato común y la API antes de sumar HLS, SMAP y ECOSTRESS, que sí requieren cuenta NASA Earthdata.

## Entrada

| Campo | Tipo | Ejemplo |
|---|---|---|
| `lote_id` | texto | `lote-7` |
| `lat`, `lon` | grados decimales (EPSG:4326), centro del lote | `-33.68`, `-65.46` |
| `desde`, `hasta` | fecha `AAAA-MM-DD` | `2026-09-01` |

## Salida

Lista de observaciones, una por fecha y variable, con este formato:

```json
{
  "lote_id": "lote-7",
  "fecha": "2026-09-01",
  "variable": "temp_max",
  "valor": 21.4,
  "unidad": "°C",
  "fuente": "POWER",
  "resolucion_m": 55000,
  "calidad": "buena",
  "nota": ""
}
```

| Variable Rotaterra | Parámetro POWER | Unidad |
|---|---|---|
| `temp_max` | `T2M_MAX` | °C |
| `temp_min` | `T2M_MIN` | °C |
| `lluvia_mm` | `PRECTOTCORR` | mm/día |
| `radiacion` | `ALLSKY_SFC_SW_DWN` | MJ/m²/día |

## Reglas

1. **Nunca inventar un valor.** Si POWER devuelve su valor de relleno (`-999`), se entrega `valor: null`, `calidad: "descartada"` y el motivo en `nota`.
2. Valores fuera de rango físico (lluvia negativa, temperatura fuera de -40 a 60 °C) se marcan `dudosa` con nota; no se corrigen en silencio.
3. La resolución de POWER es ~0,5° (~55 km): es dato regional, no del lote. Se informa en `resolucion_m`.
4. Rango máximo por consulta: 366 días. `desde` no puede ser posterior a `hasta`.

## API

`GET /clima?lote_id=…&lat=…&lon=…&desde=…&hasta=…` → `200` con la lista de observaciones; `422` si los parámetros son inválidos; `502` si POWER no responde.

## Criterios de aceptación

- [x] Con una respuesta real de POWER se obtienen 4 observaciones por día (-33,68; -65,46, del 1 al 10 de septiembre de 2026: 40 valores, 39 buenos).
- [x] Un `-999` se convierte en `null` + `descartada` (en la prueba real, la radiación del 7 de septiembre).
- [x] Coordenadas o fechas inválidas devuelven error claro, sin llamar a POWER.
- [x] Hay una prueba que se corre desde GitHub con un clic, sin instalar nada.

## Fuera de alcance

Corrección con estaciones locales (SMN/INTA), cálculo de riesgos (heladas, golpe de calor), base de datos y guardado. Van en specs siguientes.
