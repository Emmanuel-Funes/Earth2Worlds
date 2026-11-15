# Spec 061 · Requerimientos ambientales por especie (capa del dossier)

**Estado:** implementada en ramas, sin Render ni main
**Origen:** Hernán subió el dossier `Rotaterra_Dossier_Maestro_Investigacion_Claude_2026-10-31.md` (investigación hecha con ChatGPT, ampliaciones 06 a 10 y libro de 59 pestañas transcripto) y eligió en una tarjeta **"Argentino + FAO marcado global"**.

## 1. Objetivo

Sumar al banco de semillas lo que necesita cada especie de su ambiente: temperatura de suelo para sembrar, temperatura base y grados-día, heladas y calor por etapa, suelo, sales (ECe), sodio (PSI), pH óptimo, Kc, raíces, nutrientes. También el ambiente medido en San Luis (clima de Villa Mercedes 2016/17 y 2017/18, agua útil de las series Buena Esperanza, Cramer y Granville) y los ensayos del dossier.

Es una capa **aparte** de las fichas por variedad (`fichas_inta`) y del manejo por cultivo (`manejo_cultivos`). Un dato de especie no completa la ficha de una variedad.

## 2. Entrada

- `semillas/datos/raw/dossier_2026-10-31/dossier_maestro_2026-10-31.md` (SHA-256 `0d4044391d3c94824de66d461f1996fa3ac6176e0fb6cb39db30449839ffe1a9`).
- Las 59 pestañas del anexo A, extraídas sin cambios a `A01_…csv` … `A59_…csv` en la misma carpeta.

## 3. Proceso (`semillas/ambiente.py`)

Se pasan a una tabla larga (una fila por dato) solo las pestañas con datos. No entran:
- índices, listas de fuentes, auditorías y coberturas (son resúmenes del dossier);
- los ejemplos de cálculo de FAO-56;
- el índice de productividad de Salta.

Reglas:
- Los valores se copian tal cual vienen; no se convierte ninguna unidad.
- Los huecos que el dossier anotó ("sin dato verificado", "no asignar…") no son datos y no entran.
- Del agua útil de San Luis entra solo lo informado: el agua útil "inicial" por escenario es una cuenta del dossier y no entra.
- El centeno de San Luis que se repite en `L09_regional` se toma una sola vez, desde `L09_datos`, que trae fuente.
- La temperatura de EcoCrop y la temperatura base vienen de `EcoCrop_especies` y de `Emergencia_Raiz`. De `Temperatura` se toma solo la temperatura de suelo para sembrar.
- `cultivo_banco` une con el nombre del banco. Lupino, haba, arveja fresca y *Brassica rapa* no están en el banco y quedan vacíos.

## 4. Salida: tabla `requerimientos_ambientales`

| Columna | Qué es |
|---|---|
| `capa` | `especie`, `ensayo`, `zona` (clima o suelo de un lugar) o `criterio` (umbral general de diagnóstico de suelo) |
| `cultivo`, `cultivo_banco`, `especie`, `cultivar` | Nombre en el dossier, nombre en el banco, nombre científico y material del ensayo |
| `variable`, `valor`, `unidad`, `etapa` | El dato tal como está en la fuente |
| `sitio`, `campana`, `metodo` | Dónde, cuándo y cómo se midió |
| `nivel` | `San Luis` (el sitio es de San Luis o Villa Mercedes), `Argentina` (todas las fuentes son de dominios .ar) o `global` (FAO, EcoCrop o estudios de otros países) |
| `nivel_original` | La calificación que puso el dossier (A, B, C…) o sus alertas de calidad |
| `fuente`, `fuente_url`, `advertencia`, `pestana` | De dónde sale, el límite de uso y la pestaña del dossier |
| `verificacion` | "dossier ChatGPT 14/11/2026, sin releer el original", salvo las pestañas cotejadas con el documento original (`LEIDAS`) y las filas de `cotejo_originales.csv` |

Resultado: **1.597 datos**.
- Por nivel: 86 de San Luis, 664 de Argentina y 847 globales.
- Por capa: especie, ensayo, zona y criterio.

## 5. Reglas de uso

1. **El motor no la usa para descartar cultivos.** Los datos `global` son referencia de poco peso. El pH "óptimo" de FAO (por ejemplo, 5,5 a 7 en soja) no es un límite: los suelos de San Luis tienen pH de 7,6 a 8,6.
2. No se mezclan métricas distintas:
   - ECe con CE 1:5 o con la CE del agua;
   - PSI con RAS;
   - lluvia anual de EcoCrop con lluvia del ciclo;
   - temperatura del aire con la del suelo;
   - nutrientes por tonelada con dosis de fertilizante.
3. Un ensayo de otra zona no vale para San Luis; el `sitio` lo dice siempre.
4. Las alertas del dossier sobre EcoCrop quedan en `nivel_original` y `advertencia`. Por ejemplo: la lluvia es anual y no del ciclo, y la temperatura letal en reposo no es la letal en crecimiento.

## 6. API

`GET /semillas/ambiente?cultivo=&variable=&nivel=&capa=` (pide `X-API-Key`):
- `cultivo` busca por el nombre del banco;
- `variable` busca por texto;
- `nivel` acepta `San Luis`, `Argentina` o `global`.

Devuelve `{"filas", "por_nivel", "aviso"}`. Responde 404 si el cultivo no existe en esa tabla y 400 si el nivel no es válido.

## 7. Criterios de aceptación

- Cada fila tiene valor, fuente, pestaña, nivel válido y la marca de verificación.
- Todo dato con URL de fao.org es `global`.
- Agua útil hasta 210 cm: Buena Esperanza 150 mm, Cramer 216 mm, Granville 237 mm, con nivel `San Luis`.
- No entra ningún "sin dato verificado".
- Lupino queda sin `cultivo_banco`.
- Nada se sube a Render ni a main sin el OK de Hernán.

## 8. Cotejo con originales

- **Tesis Riglos (2023)**, en PDF que Hernán bajó porque el sitio de la UBA tenía el certificado vencido:
  - Los 217 valores del clima mes a mes (cuadro 2.3) coinciden número por número con el dossier. Son 2 campañas, 7 meses y 3 regiones: Villa Mercedes, Manfredi y Pergamino.
  - Arena media de 87, 82 y 71 % y agua útil hasta 2,10 m de 150, 216 y 237 mm (Buena Esperanza, Cramer y Granville), según el cap. 5.
  - La tesis llama "evapotranspiración potencial (ETo)" a lo que el dossier rotula "de referencia".
- **Fuentes que abren desde la nube**, bajadas y cotejadas número por número; todas coinciden:
  - UNRC, *Sistema suelo-planta* (2018): tablas 8.2 (Tb y grados-día a emergencia de 6 especies) y 8.4 (temperatura de raíz). Pestaña `Emergencia_Raiz`.
  - ORA 2018, *Mapas de áreas aptas*, cuadro 2 (períodos críticos de maíz y soja). Pestaña `Stress_hidrico_ORA`.
  - Nota del INTA San Luis sobre maíz, sorgo, soja y maní (Riglos). Pestaña `Lote06_SanLuis`.
  - Revista INTA *Fruticultura & Diversificación* n.º 98 (2025): CE ≥ 4 dS/m, PSI > 15 %, RAS > 13, pH > 8,5 y 77.040.300 ha (27,6 %). Pestaña `Lote06_salino`.
  - Con esto quedan 256 datos cotejados y 1.341 sin releer.
- **PDFs que Hernán bajó y subió** (19 de los 20 pedidos; la lenteja de la EEAOC ya no existe en esa dirección). El cotejo es fila por fila y queda en `semillas/datos/raw/dossier_2026-10-31/cotejo_originales.csv`, que `ambiente.armar()` aplica. Reglas:
  - Un dato queda "cotejado con el original" cuando todos sus números están juntos en el documento. En los documentos largos (manual de fertilidad, guía del cañero, sanidad, Rafaela, agricultura por ambientes, manual de sorgo y BPA) un número suelto puede aparecer por casualidad. Por eso ahí solo vale el cotejo automático si los números aparecen juntos; si no, el dato se revisó a mano o sigue "sin releer".
  - Los datos con más de una fuente (por ejemplo, EcoCrop más un documento argentino) siguen "sin releer", porque EcoCrop no se releyó.
  - Resultado: 279 datos cotejados (50 a mano), 8 que no se pueden cotejar porque están en tablas de imagen del manual de fertilidad (tablas 2, 3 y 5) y 47 datos sin números que siguen para leer a mano.
  - **Corregido:** lluvia del ciclo del lupino en Barrow (2024) = 535 mm. El dossier puso 524, que es el promedio histórico 1994-2023.
  - **Corregido:** la demanda de nutrientes del garbanzo (INTA Anguil) traía un nombre de variable roto. El original dice N 80, P 10 y K 40 kg por tonelada.
- La lista de documentos bloqueados que Hernán tiene que bajar está en `/mnt/project-files/rotaterra/semillas/Links-para-bajar-y-pasarme.md`.

## 9. Pendiente
- Muchas fuentes están en repositorio.inta.gob.ar, que está bloqueado desde la nube. Esas filas siguen como "sin releer".
