# Spec 022 · La API publicada en internet, con clave para el frontend

**Estado:** aprobada por Hernán el 4/10/2026: primero eligió Google Cloud Run en la tarjeta y a las 16:42 decidió "Lo voy a subir a Render de momento". Se publica en **Render** ahora; Cloud Run queda para más adelante (§6). El PR no se une sin su orden.
**Etapa:** pipeline satélite → API → app · **Completa:** spec 010 (la app espera a la NASA) y spec 012 (`POST /consulta`)
**Pedido:** Daniel (frontend), por medio de Hernán, el 4/10/2026: "ejecutar la API desde GitHub o algún contenedor asociado" y que "solo mi frontend pueda preguntar", "codificado con una key".

## 1. Objetivo

Que el frontend de Daniel pueda pedir datos a la API de Rotaterra por internet, y que nadie más pueda hacerlo.

| Antes | Después |
|---|---|
| La API solo corre en una computadora o dentro de una prueba de GitHub Actions, que se apaga al terminar | La API queda prendida en Render, con una dirección fija (`https://….onrender.com`) |
| Cualquiera que llegue a la API puede consultarla | Cada pedido tiene que traer la clave en el encabezado `X-API-Key`; sin clave responde `401` |
| Se publica a mano | Render la vuelve a publicar sola cada vez que cambia la rama que sigue |

## 2. Por qué no alcanza con GitHub solo

- **GitHub Actions** corre tareas que terminan (pruebas, publicaciones). Una tarea dura como máximo 6 horas y no tiene una dirección pública a la que el frontend pueda llamar. Sirve para **publicar** la API, no para **tenerla prendida**.
- **GitHub Codespaces** puede abrir un puerto público, pero se apaga cuando nadie lo usa. Sirve para una prueba de un rato entre Daniel y nosotros, no para la app.
- Hace falta un **servicio** que mantenga la API prendida. Render se conecta al repositorio y la vuelve a publicar cuando cambia la rama.
- **Se puede migrar:** la API no depende de Render. Pasar a Cloud Run u otro servicio es cambiar la forma de publicar y darle a Daniel la dirección nueva; el código no se toca.

## 3. Entrada

Los mismos endpoints de hoy (`POST /consulta`, `GET /satelites` y el endpoint de prueba de cada satélite unido), con un encabezado más:

```
POST https://<dirección-de-la-api>/consulta
X-API-Key: <clave de Daniel>
Content-Type: application/json

{"satelite": "HLS", "lote_id": "lote-7", "poligono": {...}, "desde": "2026-01-01", "hasta": "2026-01-31"}
```

## 4. Proceso

1. **Clave:** la API lee las claves válidas de la variable `ROTATERRA_API_KEYS` (una o varias, separadas por coma, para poder dar una por cliente y cambiarlas sin cortar a los demás).
   - Pedido sin clave o con una clave que no está → `401`.
   - Se comparan en tiempo constante (`hmac.compare_digest`), para no dar pistas de la clave.
   - Si la variable no está configurada, la API **rechaza todo** con `503` ("falta configurar la clave"). Nunca queda abierta por olvido.
   - Solo `GET /salud` (nuevo, devuelve `{"ok": true}`) responde sin clave, para que el servicio sepa que la API está viva. No devuelve datos.
   - La documentación automática (`/docs`) se puede abrir sin clave porque solo muestra cómo son los pedidos, no datos. Trae un botón **Authorize** para cargar la clave y probar.
   - Los endpoints de prueba de cada satélite unido también piden la clave.
2. **Origen del pedido (CORS):** la API solo acepta pedidos de navegador que vengan de las direcciones de `ROTATERRA_ORIGENES` (por ejemplo, la del frontend de Daniel). Es una segunda barrera, no reemplaza la clave.
3. **Esperas largas:** la consulta puede tardar minutos (HLS, AppEEARS). El servicio elegido tiene que dejar que un pedido dure al menos 30 minutos. Si no lo deja, hace falta otra spec para cambiar a "pedido + preguntar el estado".
4. **Publicación en Render:** el archivo `render.yaml` del núcleo describe el servicio: instala `requirements.txt`, arranca `uvicorn rotaterra.api:app` y usa `/salud` para saber si está viva. Render la vuelve a publicar sola cuando cambia la rama elegida.
5. **Prueba de arranque:** en cada PR, GitHub Actions arranca la API como lo hace Render y comprueba `/salud`, el `401` sin clave y el `200` con clave.
6. **Secretos:** `EARTHDATA_USERNAME`, `EARTHDATA_PASSWORD` y `ROTATERRA_API_KEYS` viven solo en GitHub y en el servicio (en Render, en **Environment**). Nunca en el código, los commits, los logs ni los chats (AGENTS §6). La clave se le pasa a Daniel por un canal privado, no por este chat.

## 5. Dónde guarda Daniel la clave

| Si el frontend… | Entonces | Seguridad |
|---|---|---|
| Tiene un servidor propio (por ejemplo Next.js con rutas de servidor, o un backend) | La clave vive en un secreto de **su** servidor, que llama a la API. El navegador nunca la ve. | Recomendado |
| Corre solo en el navegador | Cualquier persona que abra las herramientas del navegador puede leer la clave. La clave más CORS frenan a curiosos, pero no a alguien decidido. | Aceptable solo para probar |

**Supuesto de esta spec:** el frontend de Daniel llama a la API desde su servidor. Hay que confirmarlo con él.

## 6. Dónde se publica

| Servicio | Estado | Por qué |
|---|---|---|
| **Render** | Elegido por Hernán para empezar (4/10/2026, 16:42) | Muy simple: se conecta al repositorio de GitHub y publica solo |
| Google Cloud Run | Para más adelante | Mejor con mucho tráfico: se apaga sin uso, escala solo y acepta pedidos de hasta 60 minutos (§6.2) |
| Codespaces | Solo prueba | Se apaga solo y la dirección cambia |

### 6.1 Render (ahora)

- **Configuración:** `render.yaml`, con el plan gratis y la región `oregon`. Los datos de la NASA en la nube (Earthdata Cloud) están en Oregón, y la API es la que más les habla; la distancia al frontend de Daniel pesa poco frente a los minutos de la NASA. Es un supuesto; se puede cambiar.
- **Python:** 3.11, el mismo de los tests.
- **Variables que carga Hernán en Render** (Environment): `EARTHDATA_USERNAME`, `EARTHDATA_PASSWORD`, `ROTATERRA_API_KEYS` y `ROTATERRA_ORIGENES`. Render las marca como secretas (`sync: false`), así que nunca quedan en el repositorio.
- **Riesgos del plan gratis, a medir en la prueba real:**
  - Se duerme después de un rato sin uso, y el primer pedido después tarda en despertarla.
  - Tiene poca memoria. Una consulta de HLS de un mes procesa varias imágenes y podría no entrar.
  - Falta confirmar cuánto deja durar un pedido. Si corta antes de que la NASA conteste, hace falta un plan pago, Cloud Run, o cambiar a "pedido + preguntar el estado" con otra spec.

### 6.2 Cloud Run (más adelante)

- Hernán lo había elegido primero, pensando en el tráfico: las consultas son irregulares (picos en siembra y cosecha) y pasan minutos esperando a la NASA. Cloud Run se apaga sin uso, prende más copias en los picos y acepta pedidos de hasta 60 minutos.
- Región `us-west1` (Oregón), por la misma razón que en Render.
- Al migrar: una spec corta con el contenedor (`Dockerfile`) y el workflow que publica.
- **Límite real con mucho tráfico:** la NASA, no el servicio. Con muchos usuarios va a hacer falta guardar las respuestas para no pedir dos veces lo mismo (la base de datos que Hernán dejó para más adelante).

## 7. Qué ve la app si algo falla

| Caso | Respuesta |
|---|---|
| Sin clave o clave equivocada | `401` `{"detail": "Falta la clave o no es válida (encabezado X-API-Key)"}` |
| La API no tiene claves configuradas | `503` `{"detail": "La API no tiene una clave configurada"}` |
| Satélite no unido | `404` (como hoy, spec 012) |
| Ni el satélite ni sus respaldos trajeron datos | `502` o `503` con los intentos (como hoy, spec 012) |

## 8. Reglas de calidad

- La clave nunca aparece en logs, respuestas ni mensajes de error.
- El núcleo sigue sin nombrar a ningún satélite (spec 009).
- Sin base de datos: la consulta en el momento no la necesita (spec 010).

## 9. Ojo: qué datos va a tener la API publicada

La API publica lo que está en `main`. Hoy en `main` está solo el núcleo, **sin ningún satélite**, así que la API respondería que no hay satélites. Para que Daniel reciba datos hay que unir antes, como mínimo, el #24, el #26 y los satélites que quiera usar (ver el orden en `Proyect-context.md` §6). Mientras tanto, Render sigue la rama de prueba `RENDER-api_con_todos_los_satelites`, que junta este PR con todos los satélites sin tocar `main`. Esa rama nunca se une: se rearma cuando cambia un satélite y se borra cuando todo esté en `main`.

## 10. Lotes grandes (prueba del 6/10/2026)

La API no limita la superficie del lote. Para ver si aguanta lotes grandes se pidió cada fuente con tres lotes de San Luis: el de prueba de 25,7 ha, un cuadrado de 903 ha y una parcela real del Catastro de 944 ha (partida 01-95687, 23 vértices). Se usó el workflow `Probar lotes grandes (900 ha)` de la rama de prueba `PRUEBA-lotes_de_900_ha`, que no se une.

| Fuente | 25 ha | 900 y 944 ha | Memoria máxima |
|---|---|---|---|
| POWER, IMERG→POWER, FAO-56 | menos de 1 s | igual | menos de 100 MB |
| MERRA-2 | 16 a 18 s | igual | menos de 150 MB |
| IMERG | 6 a 8 s | igual | menos de 150 MB |
| HLS (NDVI/NDMI) | 62 s | 50 a 61 s | 138 MB |
| Sentinel-2 | 23,5 s | 19 a 22 s | 150 MB |
| VIIRS | 13 s | 13 a 16 s (1 → 46 píxeles) | menos de 150 MB |
| MODIS NDVI | 5 a 7 s | igual (4 → 176 píxeles) | menos de 150 MB |
| SMAP, SMAP L3 | 22 a 30 s, 10 a 13 s | igual | menos de 150 MB |
| NASADEM, Copernicus DEM | 2 a 3 s | igual (289 → 11.923 píxeles) | 133 MB |
| ET MODIS, ECOSTRESS | 4 s, 7 a 8,5 s | igual | 125 MB |
| GeoINTA | 12 a 13 s | igual | menos de 150 MB |
| Balance propio | 18 a 23 s | igual | menos de 150 MB |
| GOES-19 | 3,5 s | igual | 148 MB |
| SEPA INTA | 213 s | 210 s (944 ha, 65 píxeles) | 115 MB |

- No se probó el respaldo AppEEARS de SMAP, que arma un pedido en cola de 5 a 20 minutos.
- El tamaño no cambia el tiempo: las fuentes leen solo la ventana del lote, y un lote de 900 ha tiene unos pocos miles de píxeles. La memoria nunca pasó de 150 MB; el plan gratis de Render tiene 512 MB.
- En la primera vuelta HLS falló con los tres lotes, también con el de 25 ha, por un error 502 de la NASA. Repetido una hora después, anduvo con los tres.
- **SEPA tarda unos 3,5 minutos con cualquier lote y, después de un pedido completo, el servidor del INTA deja de contestar** (`ConnectError`) por un rato. Se probó al revés (944 ha primero): el primer pedido anduvo y los dos siguientes, de 900 ha y de 25 ha, no. El límite es del servidor del INTA, no del tamaño. La API lo maneja: avisa que SEPA no responde y entrega el Q de trigo en 11 s. Si SEPA se suma a Render, cada pedido supera los ~100 s que Render puede cortar.

## 11. Criterios de aceptación

- [x] Sin `X-API-Key` → `401`; con una clave válida → responde (`tests/test_clave.py`, sin internet).
- [x] Con dos claves en `ROTATERRA_API_KEYS`, las dos funcionan; una inventada no (test).
- [x] Sin `ROTATERRA_API_KEYS` → `503` en todo, salvo `GET /salud` (test).
- [x] Un pedido de navegador desde un origen que no está en `ROTATERRA_ORIGENES` no recibe el permiso CORS; el del frontend autorizado sí (test).
- [x] La clave equivocada no aparece en la respuesta (test). La API no registra encabezados en sus logs.
- [x] Los endpoints de los satélites unidos también piden la clave (probado con un endpoint de prueba; los tests de cada satélite la saltean con `tests/conftest.py`).
- [x] La API arranca como en Render y responde `GET /salud` en GitHub Actions; sin clave da `401` y con clave `200` (job `tests` del PR #38, 4/10/2026).
- [x] Rama de prueba `RENDER-api_con_todos_los_satelites`: el núcleo con la clave más los 16 satélites y respaldos se unen sin conflictos, pasan los 451 tests, `GET /satelites` lista los 7 principales con sus respaldos, y los endpoints de los satélites (`/clima`, `/lluvia`, `/humedad-suelo`…) dan `401` sin clave.
- [x] Publicada en Render (`https://rotaterra-api.onrender.com`, plan gratis, rama `RENDER-api_con_todos_los_satelites`), probada por Hernán desde `/docs` con su clave el 4/10/2026:
  - `GET /salud` → `{"ok": true}`.
  - `POST /consulta` POWER, lote de San Luis, 1 al 10/9/2026 → `200`, `fuente_usada: POWER`, máxima de 24,88 °C el 1/9 y 28,7 °C el 2/9, calidad buena.
  - `POST /consulta` HLS, 1 al 15/1/2026 → `200`, `fuente_usada: HLS`. El 1/1 dio NDVI 0,322 y NDMI -0,089, con 100 % de píxeles válidos (HLSS30), igual que la prueba real de la spec 002. El plan gratis aguantó la consulta más pesada.
- [x] Lotes de 900 ha: las 19 fuentes probadas responden con el cuadrado de 903 ha y la parcela de 944 ha, en el mismo tiempo que con 25 ha y con menos de 150 MB de memoria (6/10/2026, §10). SEPA solo anda con un pedido por vez, sea cual sea el tamaño.
- [ ] Daniel confirma que su frontend recibe la respuesta.
- [x] Hernán aprobó esta spec y eligió el servicio (Render, 4/10/2026).
