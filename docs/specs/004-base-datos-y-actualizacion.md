# Spec 004 · Base de datos y actualización nocturna

**Estado:** implementada; falta que Hernán elija dónde vive la base · **Etapa:** pipeline satélite → API → app · **Pedido por:** Hernán ("la app no debería tardar en devolver información")

> **Reemplazada en parte por la spec 010:** Hernán decidió que la app sí espera a la NASA y consulta en el momento. Esta base y la actualización nocturna quedan como complemento opcional para cuando haya una base de datos.

## Objetivo

Que la app **nunca espere a la NASA**. Los datos de cada lote se bajan por adelantado, se guardan en una base de datos y la app lee lo guardado en menos de 1 segundo.

| Antes | Después |
|---|---|
| La app pide a la NASA y espera (segundos a 20+ minutos con SMAP) | La app lee la base: < 1 s |
| Cada consulta baja todo otra vez | Se baja una vez; después solo lo nuevo |
| Si la NASA se cae, la app no tiene datos | La app muestra lo último guardado, con su fecha |

## Tablas

| Tabla | Qué guarda | Clave |
|---|---|---|
| `lotes` | id, nombre, polígono (GeoJSON), centro (lat, lon), fecha de alta | `id` |
| `observaciones` | el contrato JSON común, más `actualizado` (cuándo se guardó) | `lote_id + fecha + variable + fuente` |
| `actualizaciones` | por lote y fuente: última corrida, resultado (`ok`, `pendiente`, `error`), mensaje | `lote_id + fuente` |

- Una observación nueva para la misma clave **reemplaza** a la anterior (POWER corrige sus últimos días; HLS puede reprocesar escenas).
- Se guardan estadísticas por lote, **nunca imágenes**.

## Actualización (`rotaterra/actualizar.py`)

Participan solo los satélites unidos a `main` (spec 009); cada uno se anuncia solo.

Para cada lote y cada fuente:

1. Calcular el período a pedir:
   - **Primera vez:** historial desde `HISTORIAL_DIAS` atrás (por defecto 365).
   - **Siguientes:** los últimos `SOLAPE_DIAS` días con dato guardado (por defecto 5, contando el último, para tomar correcciones de la NASA) hasta ayer. Ejemplo: si lo último guardado es de ayer, se piden de nuevo los últimos 5 días.
   - **Al día:** si no hay nada que pedir (ya está guardado hasta ayer y no hay solape posible), la fuente queda `al_dia` sin llamar a la NASA. Las fuentes fijas como NASADEM (spec 008) quedan `al_dia` apenas tienen un dato guardado.
   - **Corrida manual:** nunca se pide más atrás que `HISTORIAL_DIAS`.
2. Pedir a la fuente y guardar.
3. **Una fuente que falla no frena a las demás.** El error queda en `actualizaciones` y se reintenta la noche siguiente.
4. **SMAP** espera como máximo `SMAP_ESPERA_MIN` (por defecto 10). Si AppEEARS no terminó, queda `pendiente`: a la noche siguiente se retoma el mismo pedido (spec 003) sin volver a la fila.

Al terminar imprime un resumen: lote, fuente, filas guardadas, resultado.

## Cuándo corre

Workflow de GitHub Actions **"Actualizar datos (nocturno)"**: todos los días a las 03:00 hora argentina, más un botón para correrlo a mano. Usa los secretos `EARTHDATA_USERNAME`, `EARTHDATA_PASSWORD` y `DATABASE_URL`. Si `DATABASE_URL` no está cargado, avisa y no hace nada.

## Dónde vive la base

El código funciona con **SQLite** (archivo local, para tests y pruebas) y con **PostgreSQL** (Supabase u otro), según `DATABASE_URL`. El lugar definitivo lo elige Hernán.

## API (lo que usa la app)

| Endpoint | Devuelve |
|---|---|
| `GET /lotes` | lotes cargados |
| `POST /lotes` | alta o corrección de lote (id, nombre, polígono). Si el id ya existe, se reemplazan nombre y polígono. El centro se calcula solo |
| `GET /lotes/{id}/observaciones?variable=&fuente=&desde=&hasta=` | observaciones guardadas, en el contrato común |
| `GET /lotes/{id}/estado` | por fuente: última actualización, resultado y última fecha con dato |

Los endpoints directos a la NASA (`/clima`, `/ndvi`, `/humedad-suelo`) son el camino principal de la app desde la spec 010; los de arriba sirven cuando hay base de datos.

## Criterios de aceptación

- [x] Consultar observaciones guardadas responde sin llamar a ninguna fuente externa.
- [x] La segunda actualización pide solo los últimos días (solape) en adelante.
- [x] Guardar dos veces el mismo dato no lo duplica.
- [x] Una fuente caída no impide guardar las otras, y queda registrada como `error`.
- [x] SMAP demorado queda `pendiente` y no rompe la corrida.
- [x] Todo testeado con SQLite y fuentes simuladas, sin internet.

## Fuera de alcance

ECOSTRESS, usuarios y permisos, borrado de lotes.
