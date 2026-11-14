# Spec 010 · La app espera a la NASA

**Estado:** aprobada por Hernán ("en realidad sí debe esperar a la NASA") · **Etapa:** pipeline satélite → API → app · **Reemplaza:** la regla "la app nunca espera a la NASA" de la spec 004

## Objetivo

Que la app pida los datos a la NASA **en el momento** en que los necesita y **espere la respuesta**, en lugar de leer una copia guardada de noche.

| Antes (spec 004) | Después |
|---|---|
| La NASA se consultaba de noche y la app leía la base | La app consulta a la NASA al pedir y espera |
| Los endpoints directos eran solo para pruebas internas | Los endpoints directos son el camino principal de la app |
| Sin base de datos, la app no tenía datos | Funciona sin base de datos (Hernán postergó la base) |

## Cómo pide la app

Cada satélite unido a `main` trae su endpoint (spec 009). La app lo llama y espera:

| Endpoint | Satélite | Espera típica (supuesto, medido en las pruebas reales) |
|---|---|---|
| `GET /clima` | POWER | segundos |
| `POST /ndvi` | HLS | 1 a 3 minutos por mes de imágenes |
| `GET /humedad-suelo` | SMAP | segundos por el camino directo; 5 a 20+ minutos si entra AppEEARS |
| `GET /lluvia` | IMERG | segundos |
| `POST /altimetria` | NASADEM | segundos |

## Reglas

- **Nunca se inventa un valor**, aunque la NASA tarde o falle: si no hay dato, `null` + `descartada` con el motivo en la `nota`.
- Si la NASA no responde, el endpoint devuelve `502` con el motivo. Si faltan las credenciales de Earthdata, devuelve `503`.
- La app tiene que mostrar que está esperando (la NASA puede tardar minutos, sobre todo HLS y AppEEARS).
- **Respaldos:** con `POST /consulta` (spec 012) los respaldos entran también en la consulta en el momento, en orden, sin base de datos. Los endpoints propios de cada satélite (`/ndvi`, `/clima`, …) responden solo con ese satélite; SMAP es la excepción, porque pasa solo a AppEEARS si falla el camino directo.
- **Base de datos y actualización nocturna:** quedan en el núcleo como complemento opcional para cuando Hernán elija una base. No son necesarias para que la app funcione.

## Criterios de aceptación

- [x] `AGENTS.md`, el README, el resumen y las specs 003, 004, 006 y 008 dicen que la app espera a la NASA. *(Verificado: ninguna línea de `main` dice "nunca espera" ni "solo para pruebas internas" sin aclarar que fue reemplazado.)*
- [x] Los tests del núcleo siguen pasando: el cambio es de instrucciones, no de comportamiento. *(40 pasan, 1 omitido.)*
- [ ] Con un satélite unido, la app obtiene sus datos llamando a su endpoint y esperando la respuesta (se verifica cuando Hernán una el primer satélite).
