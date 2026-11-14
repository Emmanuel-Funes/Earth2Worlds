# Base de fuentes de semillas extensivas · Argentina

**Corte:** catálogo INASE descargado el **28/10/2026** · **Spec:** 049
**Archivo principal:** `base_semillas_extensivas.xlsx` (la hoja LEEME explica cada pestaña). Los mismos datos están en CSV en esta carpeta.

---

## 1. Qué hay en la base

| Pieza | Cantidad | De dónde sale |
|---|---:|---|
| Filas del catálogo INASE leídas | 14.875 | `catalogo_inase_2026-10-28.csv`, bajado de la consulta pública de INASE (SHA-256 `f264d33f…bac341a`) |
| **Cultivares de cultivos extensivos y afines** | **8.145** | 22 grupos de los 24 perfiles SSD + 13 complementarios con venta de cosecha |
| Eventos OGM únicos declarados | 27 | Campo "evento transgénico" de INASE |
| Pares cultivar–evento | 3.215 | Eventos apilados separados uno por uno |
| Obtentores por cultivo | 1.306 renglones | Solicitante RNC |
| Fuentes oficiales registradas | 21 | INASE, SAGyP, CONABIA, INTA, INTeA, SISA, RECSO, RET y redes INTA |
| Registros a revisar | 982 | Controles automáticos (incluye 321 registros solo RNPC) |

### Ampliación

- **Solo cultivos cuya cosecha se vende** (pedido de Hernán, 28/10): quedan fuera las pasturas y los forrajes que se consumen en el campo (vicias, moha, mijo perla, colza forrajera, tricepiro, trigopiro, poroto de campo). La alfalfa queda porque el motor la evalúa y el fardo y la semilla se venden. Las variedades forrajeras de sorgo, maíz y avena siguen dentro de su cultivo, marcadas en la columna `destino`.
- **Complementarios nuevos:** amaranto 6, mostaza 4, tártago 2.
- **Catálogo INASE nuevo:** bajado el 28/10 sin filtros. Trae 506 registros más que el archivo anterior y todos son **solo RNPC**: material protegido que no está inscripto en el RNC, casi siempre líneas parentales de híbridos de maíz, girasol y sorgo. Quedan en la base marcados `SOLO_RNPC` y extensivo `REVISAR`, porque no se venden como semilla. No hubo bajas ni cambios en los registros que ya estaban.

## 2. Panorama por cultivo (solo cultivares extensivos)

| Cultivo | Cultivares | Con evento OGM | RNPC vigente | Del INTA | Nuevos 2022–26 | Lectura rápida |
|---|---:|---:|---:|---:|---:|---|
| **Maíz** | 2.630 | 1.289 | 6 | 41 | 267 | 2.412 graníferos, 175 pisingallo, 43 forrajeros. 9 de cada 10 nuevos traen evento |
| **Sorgo** | 1.469 | 0 | 11 | 45 | 180 | 765 graníferos y 665 forrajeros: **no mezclar en un ranking** |
| **Girasol** | 1.038 | 0 | 0 | 24 | 90 | 135 Clearfield y 47 alto oleico (no son OGM) |
| **Soja** | 648 | 593 | 594 | 12 | 185 | GM IV (227), V (127) y VI (123) dominan; lo nuevo va a Enlist (DAS‑44406‑6) y Conkesta |
| **Trigo** | 282 | 5 (HB4) | 218 | 36 | 84 | 236 pan, 43 candeal |
| Porotos | 205 | 0 | 22 | 29 | 5 | INASE **no dice** si es negro, alubia o colorado |
| Colza/Canola | 143 | 0 | 13 | 3 | 30 | 19 Clearfield |
| Papa | 99 | 1 | 28 | 17 | 15 | Evento TIC‑AR233‑5 (virosis) en 1 registro |
| Avena · Cebada · Centeno · Triticale | 72 · 67 · 31 · 31 | 0 | 28 · 45 · 8 · 7 | 34 · 24 · 19 · 12 | 14 · 16 · 3 · 3 | |
| Arroz · Caña · Lino · Maní | 41 · 37 · 29 · 27 | 0 | 22 · 13 · 2 · 26 | 10 · 5 · 19 · 7 | 18 · 5 · 0 · 6 | |
| Arveja · Cártamo · Garbanzo · Algodón | 27 · 19 · 11 · 11 | 0 · 0 · 0 · 8 | 25 · 1 · 6 · 6 | 2 · 1 · 3 · 7 | 12 · 4 · 6 · 2 | |
| Lenteja · Lupino | 4 · 1 | 0 | 0 · 0 | 3 · 0 | 0 · 1 | Lupino: solo ALUPROT‑CGNA (2025) |

Complementarios útiles para rotar: **alfalfa (476)**, camelina (24, casi todas nuevas), cáñamo industrial (15), vicias (12), moha (11), mijo perla (9) y otros.

## 3. Hallazgos que cambian decisiones

1. **Varios cultivares que cita el documento SSD ya no figuran en el catálogo actual.** De los 120 materiales INTA que nombra: 97 están exactos, 10 quedan a revisión por nombre parecido (ej. "MJ 42 STS" ↔ "INTA MJ42‑STS", "7302 INTA" ↔ "INTA 7302") y **13 no aparecen**. Entre ellos están **ASEM 505, 484, 485, 447, Florman y Manfredi 393 (maní)**, Camba y Puitá (arroz; "Ñu Poty" figura como "Ñu Poti INTA CL"), TUC 03‑663 y 03‑617 (caña), Lucía INTA (cebada) y Turca (lenteja). El ejemplo del maní del documento SSD tiene que actualizarse.
2. **No hay soja HB4 en el catálogo.** El evento IND‑00410‑5 está autorizado, pero ningún cultivar de soja lo declara en INASE. En trigo, el HB4 (IND‑00412‑7) aparece en 5 cultivares.
3. **Cártamo y lupino sí tienen cultivares inscriptos**, aunque el documento SSD decía que no se había confirmado lista: cártamo 19 (Ipora Guazú INTA, líneas de la UNS, CW, S‑) y lupino 1.
4. **En girasol, sorgo, maní, cebada y colza no hay ningún evento OGM declarado.** El comparador tiene que comparar convencionales entre sí y no fabricar una opción OGM.
5. **Ningún cultivar tiene disponibilidad comercial verificada.** Estar inscripto no quiere decir que haya bolsa en Villa Mercedes esta campaña. Hace falta una cotización con fecha.

## 4. Para el piloto de San Luis (cultivos del motor)

Maíz, soja, sorgo, girasol, maní y trigo suman **6.094 cultivares**. Solo hay una fuente de ensayos **de la provincia**: *Ensayos agrícolas en San Luis* (INTA EEA San Luis, hasta 2022/23). Es la primera que conviene pasar a filas.

## 5. Reglas (para no engañarnos)

- **Dato** = lo que dice INASE, tal cual. **Derivado** = subtipo, destino, estado RNPC y eventos separados, calculados con reglas que se pueden auditar. **Pendiente** = todo lo que queda en "sin dato verificado".
- "Sin evento declarado en este registro" **no** es "convencional confirmada".
- CL, STS, AO **no** son OGM.
- La autorización de cada evento queda "pendiente de contrastar" con la lista de SAGyP.

## 6. Qué falta y quién lo hace

| Paso | Quién | Por qué |
|---|---|---|
| Contrastar los 27 eventos con la lista oficial de SAGyP | Claude, en un hilo con acceso a sitios .gob.ar | Desde este entorno los sitios .gob.ar no responden |
| Anotar la fecha exacta en que bajaste el CSV de INASE | Hernán | Hoy solo sabemos que es del 23/10/2026 o posterior |
| Revisar los 10 nombres "a revisión" y los 13 "no encontrados" | Claude + Hernán | No se unen solos por parecido |
| Extraer ensayos (San Luis, RECSO, RET, Marcos Juárez) | Claude | Para pasar de "inscripto" a "rinde en tu ambiente" |
| Cotizaciones de semilleros de la zona | Hernán | Única forma de marcar disponibilidad y precio |

---

## 7. Oferta comercial 2026/27

Hoja **"Oferta 2026-27"** del Excel (`oferta_comercial.csv`). Junta lo que las empresas dicen vender, lo que más se sembró según SISA y los ensayos publicados, y cruza cada material con INASE.

| Qué | Cantidad |
|---|---:|
| Materiales relevados | **92** (156 desde la sección 8), de 7 cultivos (soja, maíz, girasol, sorgo, trigo, cebada, maní) y 40 fuentes |
| Con el mismo nombre en INASE | 52 |
| Con el mismo código y otra sigla de tecnología (ej. "LT 722 VT3 PRO" ↔ "LT722VT3P") | 27, a revisar |
| Sin inscripción con ese nombre | 13. Entre ellos hay 7 lanzamientos 2026/27: DM 64R64 STS, DM 67K67 SCE, P61A26 SE, BASF 5282 VIP3, IS 7575 VIP3, BRV L210 CP y Klein Zinc |
| Con "oferta declarada" | 72 (**no** hay precio ni stock verificado) |

**De dónde salen los datos.** Todo viene de un buscador web, porque desde este entorno no se pueden abrir las páginas de empresas ni las del Gobierno. Por eso cada fila trae su link, y donde no se pudo confirmar quién dijo qué, la columna `nota` dice "atribución a confirmar". Nivel de evidencia: dato de la empresa o de prensa. No reemplaza un ensayo.

### Lo que sirve para el piloto de San Luis

| Material | Qué se sabe | En INASE |
|---|---|---|
| LT 722 VT3 PRO, LT 723 TRE | Maíz: más de 9.000 kg/ha con alta densidad, ensayo INTA San Luis en secano, Villa Mercedes 2025/26 | LT722VT3P (2015), LT723TRE (2022) |
| NK 835 VIP3, ARG 7718 VT3 PRO | Destacados en el mismo ensayo. Promedio general: 7.408 kg/ha con alta densidad y 5.825 con baja | NK835 VIPTERA3 (2023), ARG 7718 (2021) |
| Sorgo, 10 materiales | Ensayo en Villa Mercedes sembrado el 02/12/2025 sobre alfalfa, sin fertilizar. La nota no da los nombres | Hay que pedir el informe a INTA San Luis |
| Soja | El ensayo de Villa Mercedes **se perdió** por la falta de lluvia en diciembre y enero. En Granville rindió cerca de 4.000 kg/ha | — |

Estos rindes vienen de la prensa, sin repeticiones ni estadística. Sirven de orientación, no para el ranking.

### Qué usa la gente (SISA, según la prensa)

- **Soja 2025/26:** DM 46I20 IPRO fue la más sembrada, con el 15,8% del área. Se declararon 589 cultivares. Enlist creció a 3,685 millones de ha (+42%). Las no transgénicas más sembradas: K 46C25, K 6501 y BK 44P41.
- **Trigo 2024/25:** Baguette 620, Catalpa, Pehuen y Baguette 750 sumaron el 40% del área. Escorpión (de uso libre) tuvo el 4,5%, pero **no aparece en el CSV de INASE**: hay que verificarlo.
- **Cebada 2025/26:** Montoya le sacó el primer lugar a Andreia. Tres cultivares cubren el 80,7% del área.

### Tendencias del mercado

- En soja, casi toda la oferta nueva lleva **Enlist (DAS-44406-6)**, sola o con **Conkesta**. Pasa en DonMario, Nidera, Neogen, NK, Brevant y Stine, y lo confirman los eventos inscriptos en INASE.
- En maíz, los lanzamientos traen Viptera3 y PowerCore Ultra. Hay híbridos tolerantes a Spiroplasma (achaparramiento) para el norte.
- En sorgo, Advanta suma aphix (tolerancia al pulgón amarillo) e igrowth (control de malezas). En el semiárido esto importa por la presión del pulgón.
- En girasol se esperan 3 millones de ha y hay faltantes puntuales de híbridos alto oleico.
- Trigo HB4: Bioceres anuncia 5 variedades con venta por multiplicadores. En la red INTA-INASE 2025/26 no superaron con claridad a las convencionales.

## 8. Ensayos INTA San Luis 2025/26

**Decisión de Hernán (27/10):** por ahora se trabaja **solo con INTA** (nacional). La app y el estudio son para **toda la provincia de San Luis**.

**Fuentes (PDF subidos por Hernán, copia en `/mnt/project-files/rotaterra/inta/informes-2025-26/`):**
- *Ensayos agrícolas en la provincia de San Luis. Campaña 2025-2026. Maíz, sorgo, soja, trigo y algodón*, EEA INTA San Luis + UNSL, sep-2026, 81 págs. ([repositorio](https://repositorio.inta.gob.ar/xmlui/handle/20.500.12123/27891))
- *Maíz: Evaluación de híbridos comerciales bajo dos densidades de siembra en secano*, Información Técnica N.º 211, Riglos, jul-2026, 12 págs. ([repositorio](https://repositorio.inta.gob.ar/xmlui/handle/20.500.12123/26986))

### Qué parte de San Luis cubren

| Sitio | Ensayos | Ambiente |
|---|---|---|
| **Villa Mercedes** (EEA INTA) | Maíz × densidad, sorgo, soja (perdida), trigo con riego (UNSL), chicharrita | Ustipsament típico areno-franco (serie Cramer), MO 0,8%, P 12 ppm, pH 6,8; 593 mm sep–may |
| **Tilisarao** ("Don Andrés", UNSL) | Maíz 23 híbridos, maíz × fertilización N, algodón | Haplustol éntico franco (serie Naschel); 751 mm en la campaña |
| **Comandante Granville** | Soja RECSO, 60 cultivares | Antecesor maíz; lluvias mejor repartidas que en Villa Mercedes (a ~50 km) |

**Hueco para toda la provincia:** no hay ensayos 2025/26 en el **sur** (Buena Esperanza, Dupuy), ni en el **noreste** ni en el **oeste**. Para el sorgo esto pesa: el informe dice que Pedernera, Pringles, Chacabuco y Dupuy concentran ~80% del área, y Dupuy no tiene ensayo. Hasta que haya datos de esas zonas, un rinde de ensayo **no se puede trasladar** a lotes del sur: sirve como referencia del centro-este con su fuente, nunca como valor del lote.

### Resultados por cultivo

| Cultivo | Dato clave | Estadística | Lectura agronómica |
|---|---|---|---|
| **Maíz × densidad** (VM, 8 híbridos, siembra 17/12, secano, sin fertilizar, 5 años de alfalfa) | LT 722 VT3 PRO **9.053** / 6.675; LT 723 TRE **9.031** / 6.725; NK 835 VIP3 8.181 / **7.313** (el mejor a baja densidad); ARG 7718 VT3 PRO 7.863 / 4.563 (+72%); NK 842 VIP3 6.991 / 6.338; ARG 7726 6.481 / 5.188; Genesis 152 RR BT 6.354 / 5.513; ARG 7714 VT3 PRO CL 5.313 / 4.288 (kg/ha a 85.000 / 50.000 pl/ha) | **No reporta repeticiones ni prueba estadística** | Subir densidad pagó porque llovió en el período crítico (feb–mar 207 mm). NK 835 y NK 842 responden poco a la densidad: son los **más estables** si el año viene seco |
| **Maíz comparativo** (Tilisarao, 23 híbridos, siembra 05/12, 43.000 pl/ha) | P 1804 PWUE 10.242; NK 855 VIP3 9.786; ADV 8122 VT3PRO 9.360 … SEMITROP 123 BTRR 6.579. Media 8.522 (CV 9,7%) | **Sin diferencias significativas** (DGC α=0,05), testigos apareados | Con ~120 mm a la siembra y 366 mm en el período crítico y el llenado, todos rindieron cerca del techo de la zona |
| **Maíz × N** (Tilisarao) | Urea 50 kg N 10.453; N Duo 10.145; Nitrur 9.271; testigo 9.092 | DMS 1.383 kg/ha, **sin diferencias** | +15% numérico en un año húmedo; no alcanza para recomendar dosis |
| **Sorgo** (VM, 10 materiales, siembra 02/12) | Graníferos 4.300–4.600 kg/ha (Nufam, Argenetics); silero Genesis 9.508 kg MS/ha; doble propósito RAGT 10.183 kg MS/ha | Franjas con 4 muestras o microparcelas con 3 repeticiones; CV 4,9–32% | **El informe no publica los nombres comerciales**, solo número y empresa. Igual al promedio provincial 2000–2025 |
| **Soja RECSO** (Granville, siembra 05/11) | Por grupo de madurez: 4C **4.354**; 3C 4.093; 3L 4.000; 5C 3.986; 4L 3.751 kg/ha | CV 10–13,5% | Los GM largos cayeron en el período crítico más seco (fin de febrero). Villa Mercedes se perdió (dic–ene secos, roedores y hormigas) |
| **Trigo** (VM, UNSL, **con riego**) | Klein Potro 7.026; Ballesta 6.606; Leyenda 6.587; Extremo 6.250; Emblema 6.127; Litio 5.551 kg/ha | **Sin diferencias** (DGC α=0,05) | Techo con agua y nutrientes; no comparable con secano |
| **Algodón** (Tilisarao, Guaraní BG/RR) | Surco 1,05 m: 1.828 kg/ha bruto; 0,525 m: 1.228 | Granizo 14/12 (−60% de plantas) | El surco ancho compensó mejor |
| **Chicharrita** (VM) | Primeros individuos a principios de marzo, con el maíz en grano lechoso | — | Llegó tarde y no afectó el rinde monitoreado |

Los rindes por cultivar de soja en Granville ahora salen del **informe nacional RECSO** (sección 8 bis). Los 22 valores que se habían tomado de la nota de prensa coinciden con el informe; solo había dos nombres mal escritos, ya corregidos (DM 33E22 SE y NEO 35S23 SE).

**Hoja "Oferta 2026-27":** ahora tiene **156 filas**. Se agregaron los 8 híbridos del ensayo de densidad con los dos rindes, los 10 sorgos (sin nombre, no se unen con INASE) y los 6 trigos Klein, y la fuente de Tilisarao pasó a ser el informe INTA. En el cruce con INASE: 75 con el mismo nombre, 38 a revisar y 43 sin inscripción con ese nombre.

## 8 bis. Red nacional de soja del INTA (RECSO 2025/26), cargada completa

**Fuente:** Informe RECSO 2025/26 (INTA EEA Marcos Juárez + ASA), 456 páginas, [PDF](https://www.recsoargentina.com/_files/ugd/7ecdbe_ba67e0407e0d49459c087bd8f2d861b4.pdf). Las planillas vienen como imagen, así que se leyeron con OCR y se controlaron una por una.

**Qué hay:** 351 ensayos en 64 localidades de 12 provincias, 88 cultivares de los grupos de madurez III corto a VII-VIII, y 3.618 rindes (un cultivar en un ensayo). Cada ensayo trae sitio, subregión, fechas, antecesor, suelo (MO, pH, P cuando el informe lo da), media, CV y LSD.

**Control:** en los 351 ensayos el promedio de lo leído coincide con la MEDIA impresa (345 a menos de 0,5% y el resto a menos de 2%), y ningún cultivar se repite en un ensayo. 26 ensayos que el INTA dejó fuera del análisis conjunto se cargan marcados y **no entran en los promedios**.

**Cómo se filtra para San Luis:** cada ensayo lleva `referencia_san_luis`:
- **SAN_LUIS:** Comandante Granville (5 ensayos, MO 1,6%, pH 7,6).
- **SUBREGION_LIMITROFE:** las subregiones RECSO que tocan San Luis. II-3: Berrotarán, Gral. Cabrera, La Carlota, Hernando. II-5: Gral. Pico (MO 1,4%, pH 6,5), Gral. Villegas y Mattaldi. Son 39 ensayos.
- **OTRA_REGION:** el resto del país, que sirve para conocer el cultivar pero no para decidir en San Luis.

**Lo mejor en San Luis y sus vecinas** (rinde relativo a la media de cada ensayo; solo cultivares con 3 ensayos o más ahí):

| Grupo | 1.º | 2.º | 3.º |
|---|---|---|---|
| III corto | STINE 31EC21 103% (8 ensayos) | NEO 35S23 SE 103% (8) | BRV3325SE 101% (8) |
| III largo | DM 38E26 SE 102% (7) | P38A01SE 101% (7) | STINE 38EF52 STS 100% (7) |
| IV corto | CZ 4021 STS 107% (8) | STINE 43EE53 STS 107% (7) | NEO 42S25 RR STS 104% (8) |
| IV largo | NEO 46S25 SE 105% (9) | DM 46R25 105% (9) | NEO 47S25 SE 105% (9) |
| V corto | NEO 50S23 RR STS 105% (9) | STINE50EE59 STS 103% (9) | 4924 E STS NS 103% (9) |

Los grupos V largo a VII-VIII no se ensayan en San Luis ni en sus vecinas (son del norte). Las diferencias entre los primeros son chicas, de 2 a 7%, y es **una sola campaña**: sirven para armar la lista corta, no para elegir un ganador.


**Tres campañas (2023/24 a 2025/26):** el mismo informe trae, por subregión, el rinde de cada cultivar relativo al testigo en 1, 2 y 3 campañas (Tablas 1 a 9). Se cargaron completas, son 1.443 valores (hoja `Soja RECSO 3 campañas`), y el resumen por cultivar muestra los de II-3 (la de Granville) y II-5. Los que más repiten arriba del testigo en II-3:
- III corto: STINE 31EC21 y NEO 35S23 SE, 107% en 3 campañas (12 ensayos).
- IV corto: STINE 40EC53, 104% en 3 campañas. En 2 campañas: DM 40E25 SE 115%, DM 40R26 108% y BRV4124SE 107%.
- IV largo: STINE 48EC53, 106% en 3 campañas. En 2 campañas: NEO 47S25 SE 105%.
- V corto: NEO 50S23 RR STS, 103% en 3 campañas.

Ojo, II-3 y II-5 no se comportan igual. STINE 31EC21 da 107% en II-3 y 96% en II-5. Por eso, para el sur de San Luis, que se parece más a II-5, no conviene copiar el ranking de Granville.

**Cruce con INASE:** 55 de los 88 cultivares están con el mismo nombre o código. 23 están inscriptos sin la marca (por ejemplo "4021" por CZ 4021 STS) y quedan a revisar. 10 no aparecen con ese nombre.

**Tablas nuevas** en el Excel y en CSV: `Soja RECSO por cultivar` (recso_resumen_cultivar.csv), `Soja RECSO 3 campañas` (recso_multianual.csv), `Soja RECSO ensayos` (recso_ensayos.csv) y `Soja RECSO rindes` (recso_rindes.csv). Los cultivares de la RECSO son de empresas, pero la red y los datos son del INTA.

## 8 ter. Red nacional de trigo (RET de INASE), 8 campañas

**Fuente:** las planillas oficiales AnaDataRET de cada ensayo que INASE publica en [Red de Ensayos de Trigo](https://www.argentina.gob.ar/inase/red-variedades-de-trigo), campañas 2018/19 a 2025/26. Son 201 archivos; las planillas viejas (.xls y .zip) se pasaron a .xlsx. La lista con el SHA-256 de cada archivo está en `semillas/herramientas/ret_trigo/archivos_fuente.csv`. Las campañas 2005/06 a 2017/18 siguen en la web y no se cargaron: sus cultivares ya casi no se venden.

**Qué hay:** 878 ensayos en 37 sitios y 24.270 rindes de 323 cultivares. Cada ensayo es una combinación de sitio, campaña, época o ciclo de siembra y manejo con o sin fungicida. Los nombres se unificaron ("K. EMBLEMA", "KLEINEMBLEMA", "Klein Emblema") y el original queda en `nombre_en_planilla`. Las 3 campañas que ya estaban dan exactamente los mismos rindes que antes.

**Dónde cae San Luis:** con el mapa oficial de subregiones trigueras de INASE de 2021, cruzado con las 17.976 parcelas rurales del Catastro, el este de la provincia es la **subregión 9, Pampa semiárida central (PSC)**: Villa Mercedes, Granville y Buena Esperanza. Es la misma subregión de **Anguil** (La Pampa). El resto cae en Valles serranos (7.121 parcelas) y Llanos cuyanos (5.352), donde la RET no tiene ensayos. Anguil tiene ensayos en 2019/20 (año muy seco, unos 550 kg/ha de media), 2023/24 y 2024/25; las otras campañas no publicaron Anguil. Las vecinas semiáridas son la 8 (Manfredi) y la 10 (Bordenave, Carhué, Cabildo, Hilario Ascasubi). En total hay 129 ensayos en la zona semiárida.

**Lo mejor en la Pampa semiárida (8, 9 y 10), con 25 ensayos o más en las 8 campañas:**
- SY 109: 114% de la media (39 ensayos). Desde 2023: 113%.
- Buck Fulgor: 110% (28). Desde 2023: 113%.
- ACA 308: 110% (29).
- ACA 502: 110% (27).
- ACA 363: 110% (25).
- ACA 921: 108% (25).
- Pehuén: 108% (42 ensayos, el más probado).

**Los del INTA (MS INTA, de Macro Seed, y BIOINTA):** en la zona semiárida, **BIOINTA 1006** rinde 106% (15 ensayos) y **MS INTA Bonaerense 215** 102% (30). **MS INTA Mda Bonaerense 324** rinde como la media (101%, 22 ensayos) pero en Anguil llega a 115%. El resto queda por debajo de la media en esta zona.

Los rindes relativos sirven para comparar cultivares, no para estimar el rinde de un lote. Los ensayos con menos de 5 cultivares no entran en los promedios. La tabla por cultivar ahora trae también el rinde desde 2023 y la última campaña en que se ensayó, para no elegir uno que ya no se siembra.

**Tablas:** `Trigo RET por cultivar`, `Trigo RET ensayos` y `Trigo RET rindes`.

## 8 quater. Red nacional de girasol (INTA-ASAGIR), 3 campañas

**Fuente:** las planillas de cada ensayo que publica la [Red de Ensayos de Girasol INTA-ASAGIR](https://asagir.org.ar/acerca-de-red-de-ensayos-de-girasol-inta-asagir-463), campañas 2023/24, 2024/25 y 2025/26. La red la conduce el INTA junto con ASAGIR.

**Qué hay:** 44 ensayos en 33 sitios y 1.583 rindes de 84 híbridos, con rinde, porcentaje de aceite y rinde ajustado por aceite. Los nombres venían escritos de muchas formas ("NS 1115", "Ns 1115 CL", "NS1115 CL") y se unificaron; el nombre original queda en `nombre_en_planilla`. Los "Testigo 1 a 5" (o "T1 a T5") son híbridos sin nombre y no entran en los promedios. De los 84 híbridos, 40 figuran en INASE con el mismo nombre; el resto puede ser experimental o nombre comercial.

**Dónde cae San Luis:** no hay ningún ensayo en San Luis. Se tomaron como vecinas semiáridas **Anguil y General Pico** (La Pampa) y **Laboulaye** (sur de Córdoba): 6 ensayos con rinde. Anguil 2024/25 no publicó rinde. Trenque Lauquen, Salliqueló y Pehuajó quedan aparte como oeste bonaerense, más húmedo.

**Lo mejor en las vecinas, con 3 ensayos o más** (rinde relativo a la media del ensayo):
- LID6060L (Agrality): 122% (3 ensayos), 49% de aceite.
- NS 1115 CL (Nidera): 111% (4), 53% de aceite.
- InSun 2277 CL (BASF): 111% (4), 57% de aceite.
- ORISOL 740 CLDM: 111% (3).
- ACA 220 CLDM: 109% (6 ensayos, el más probado en la zona).
- Nusol 4175 CL: 106% (6).

**Del INTA:** el único híbrido del INTA en la red es **FEBO 817 CL INTA** (de Los Algarrobos). En todo el país rinde como la media (101%) y en las vecinas tiene un solo ensayo, con 110%. Hace falta más de un ensayo para decir algo.

Con 3 a 6 ensayos por híbrido en la zona, esto es una primera lista, no una recomendación.

**Tablas nuevas:** `Girasol por cultivar`, `Girasol ensayos` y `Girasol rindes`.

## 8 quinquies. Maíz de las redes del INTA más cercanas a San Luis

**No hay una red nacional única de maíz.** Cada estación del INTA arma la suya y la publica en PDF. Se cargaron las que tienen sitios parecidos a San Luis y están en argentina.gob.ar:
- [Red de híbridos de maíz de INTA Marcos Juárez](https://www.argentina.gob.ar/inta/cr-cordoba/red-de-evaluacion-de-hibridos-de-maiz-en-siembra-temprana-inta-marcos-juarez-informe), siembra temprana, campañas 2024/25 (41 híbridos, 10 sitios) y 2025/26 (30 híbridos, 9 sitios), más el ensayo de siembra tardía de La Carlota 2025/26.
- [Red del norte de Buenos Aires](https://www.argentina.gob.ar/inta/cr-buenosaires-norte/red-de-evaluacion-de-hibridos-de-maiz-del-norte-de-buenos-aires/resultados) 2024/25: solo **General Villegas**, temprana y tardía, que es el sitio semiárido de esa red.

**Qué hay:** 22 ensayos y 758 rindes de 71 híbridos. La tabla de 2024/25 de Marcos Juárez venía como imagen; se leyó con OCR y cada fila cuadra con el promedio impreso. Las de Villegas se copiaron a mano y su media coincide con la impresa. En Mattaldi 2024/25 faltan dos híbridos (la celda está vacía en el informe). Canals y Laboulaye 2024/25 quedaron fuera del análisis de la red por vuelco y cosecha tardía; están cargados pero con esa nota.

**Vecinas de San Luis:** **Río Cuarto** (la más cercana), **Mattaldi** y **Laboulaye** (sur de Córdoba) y **General Villegas** (noroeste bonaerense). No hay ensayo de maíz publicado en San Luis.

**Lo mejor en las vecinas, con 4 ensayos o más:**
- BASF 5575 VT3P: 112% de la media (5 ensayos).
- LT 3-02 TRE (La Tijereta): 111% (4).
- ST 9939 (Stine): 107% (5).
- EQS 75-03 EVO (QSeeds): 107% (5).
- ACA 471 VT3P: 106% (7 ensayos, el más probado en la zona).
- DK 7447 Trecepta: 106% (5).
- BRV 8380 PWUE (Brevant): 106% (5).

**Del INTA:** ningún híbrido de estas redes es del INTA. 31 de los 71 figuran en INASE con el mismo nombre; el resto suele estar inscripto con otra forma del nombre (sin la marca o la biotecnología).

Son dos campañas como mucho. Sirve para armar una lista corta, no para elegir un híbrido.

**Tablas nuevas:** `Maíz por híbrido`, `Maíz ensayos` y `Maíz rindes`.

**Sorgo:** ver la sección 8 sexies (ensayo de Manfredi 2024/25, que bajó Hernán).

## 8 sexies. Sorgo granífero: ensayo INTA EEA Manfredi 2024/25

**Fuente:** *Ensayo comparativo de rendimiento de híbridos de sorgo granífero, campaña 2024-25 en INTA EEA Manfredi* (Rosas, Senn, Ortiz y Maguire, Cartilla Digital Manfredi 2025/02, [repositorio INTA](https://repositorio.inta.gob.ar/handle/20.500.12123/22621)). Lo bajó Hernán y está en `/mnt/project-files/rotaterra/inta/informes-2024-25/`. No hay red nacional de sorgo con planillas públicas; este es el ensayo del INTA más completo y más cercano a San Luis que se consiguió.

**Qué hay:** 40 híbridos graníferos y doble propósito de 13 empresas más uno del INTA, con rinde, ciclo, tanino, días a floración, panojas por hectárea, altura y peso hectolítrico. Un solo sitio (Manfredi, centro de Córdoba, zona semiárida norte), siembra 30/10/2024 sobre soja, 594 mm en el ciclo, alfa látice con 3 repeticiones. Media 6.798 kg/ha. La diferencia mínima significativa es **1.344 kg/ha**: los **19 híbridos** que quedan a menos de eso del mejor no se distinguen entre sí.

**Arriba en rinde** (todos sin diferencia significativa entre sí):
- Santa Ana (Radixagro, doble propósito): 8.235 kg/ha, 121% de la media.
- TOB 49 T (Tobin): 8.217, 121%.
- **EXP-G66 (INTA)**: 7.920, 117%. Es el único material del INTA y todavía es experimental: no está inscripto en INASE.
- SYT 70-G70: 7.743, 114%.
- TOB 63 T: 7.683, 113%.

**Cruce con INASE:** 18 de los 40 están inscriptos con el mismo nombre, 9 son experimentales y 13 no aparecen con ese nombre (por ejemplo los TOB, que INASE puede tener sin la "T" o con otra marca). Hoja nueva `Sorgo Manfredi`, con la columna `sin_diferencia_con_el_mejor`.

**Con el ensayo de Villa Mercedes 2025/26** (sección 8): allá los graníferos de Nufarm y Argenetics dieron 4.300 a 4.600 kg/ha, pero el informe no da nombres, así que no se pueden unir. En Manfredi, los de Nufarm (Nugrain 311 AB 109%, Nugrain 30N50 P 99%, Spring T60 96%) y Argenetics (Argensor 135 T 95%, Malón 95%) quedaron en la media o un poco arriba. Es una pista, no un dato del mismo material.

## 9. Próximos pasos

| Paso | Quién |
|---|---|
| Nombres de los 10 sorgos de Villa Mercedes: se pidieron a la EEA San Luis sin respuesta (29/10). Opcional: quedan "sin nombre" y para elegir híbrido se usa Manfredi | opcional |
| Buscar ensayos INTA del **sur** (Buena Esperanza / Dupuy) y de otras zonas, o de campañas anteriores en esos lugares | Claude |
| Cargar series de años anteriores (informes 2023-24 y 2024-25 del mismo repositorio) para no decidir con una sola campaña | Claude |
| RECSO: los otros dos informes públicos (2023/24 y 2024/25) son solo del norte (GM V a VIII), no traen Granville; las 3 campañas de la zona ya están en las Tablas 1 a 9 | hecho |
| Trigo RET: hecho para 2018/19 a 2025/26. Las de 2005/06 a 2017/18 están en la misma página si hacen falta | hecho |
| Girasol INTA-ASAGIR: hecho para 2023/24 a 2025/26 | hecho |
| Maíz: redes INTA Marcos Juárez y norte de Buenos Aires (Villegas), 2024/25 y 2025/26 | hecho |
| Sorgo Manfredi 2024/25: cargado. Sirven los de 2022/23 y 2023/24 del mismo grupo si se consiguen | Hernán (descarga) |

## 8 septies. Solo INTA y de todo el país

Hernán: "preciso que me traiga todo lo que se siembra en argentina, luego si se adapta a las condiciones del suelo es otra cuestion … toda la info que me traigas sea del INTA, no me interesan las semillas de empresas privadas".

- Tabla nueva **`banco_inta`** (hoja "Banco INTA"). Tiene 460 cultivares del INTA de 27 cultivos extensivos de todo el país, entre ellos trigo, maíz, sorgo, soja, girasol, avena, cebada, porotos, papa, arroz, algodón, maní, caña de azúcar, arveja, lenteja, garbanzo y alfalfa.
  - Hernán: "Eliminar todas aquellas que no sean de cultivos extensivos, de nada me sirven rosas". Por eso no entran frutales, hortalizas, forestales ni ornamentales.
  - Un cultivar es del INTA cuando pasa una de estas cuatro cosas: el INTA es el solicitante, es de Barrow (convenio), lleva "INTA" en el nombre o figura en el catálogo de variedades del INTA.
- Las tablas de privados siguen en el archivo para una etapa posterior. La API y la página muestran solo lo del INTA.
- En los ensayos cargados aparecen estos materiales del INTA:
  - Trigo: 24 (RET).
  - Girasol: 1 (FEBO 817 CL INTA).
  - Sorgo: 1 (EXP-G66).
  - Algodón: Guaraní INTA BGRR (San Luis).
  - Soja (RECSO 2025/26) y maíz: ninguno.

## 8 octies. Ensayos INTA EEA San Luis + UNSL 2025/26

El informe es la Información Técnica N.º 213 (sep. 2026, 81 págs., [repositorio](https://repositorio.inta.gob.ar/xmlui/handle/20.500.12123/27891)). La copia está en `rotaterra/inta/informes-2025-26/ensayos-agricolas-san-luis-2025-26.pdf`. Son ensayos hechos dentro de la provincia y van a las tablas `san_luis_ensayos` y `san_luis_rindes`.

| Ensayo | Materiales | Media impresa (control) |
|---|---|---|
| Maíz Villa Mercedes, dos densidades | 8 híbridos | 7.408 (alta) y 5.825 (baja) kg/ha |
| Maíz Tilisarao | 23 híbridos | 8.522 kg/ha |
| Trigo Villa Mercedes (riego) | 6 Klein | 6.357 kg/ha (figura 7) |
| Sorgo Villa Mercedes | 10 materiales sin nombre en el informe | 3.912 kg/ha de grano (figura 3) |
| Algodón Tilisarao | Guaraní INTA BGRR, dos distancias | 1.227,5 y 1.828,4 kg/ha en bruto |

- El maíz entra también en las tablas de maíz (ahora 25 ensayos).
- La soja de Comandante Granville ya estaba en la RECSO. La de Villa Mercedes se perdió.
- Herramienta: `semillas/herramientas/san_luis/`.

## 8 nonies. Ficha de cultivo por variedad del INTA

Hernán: "trae lo de todos los cultivos, va a ser de suma utilidad para la aplicación".

- Tabla nueva `fichas_inta.csv` (hoja "Fichas INTA" del Excel y tabla del mismo nombre en `semillas.sqlite`): una fila por dato de cada variedad (ciclo, época de siembra, zona recomendada, suelo, sanidad, tolerancias a sequía/heladas/salinidad/herbicidas, aptitud, rinde publicado, comercializador), siempre con `fuente` y `fuente_url`.
- Fuentes: planilla de descriptores de soja de INASE (24/06/2026), grupos de calidad y ciclo del trigo pan (Comité de Cereales de Invierno, INASE, 2012 a 2025), grupo de reposo de la alfalfa (catálogo INASE), fichas del catálogo INTA, oferta tecnológica INTA y noticias oficiales del INTA en argentina.gob.ar (con su fecha).
- Cobertura: 151 de 460 variedades. Completas o casi: soja 15/15, trigo 31/40, alfalfa 22/27, garbanzo 3/3, arroz 8/11, triticale 7/12, papa 10/24, avena 13/40, cebada 10/25, caña 5/7, maní 5/7, algodón 4/7. Casi sin datos publicados: sorgo 2/60, maíz 2/54, porotos 1/33, centeno 2/22; sin nada: mijo, lenteja, caupí, cártamo, mostaza, cáñamo. Son sobre todo variedades viejas (años 80-90) de las que el INTA no publica ficha en línea.
- Sin dato verificado = no hay fila. No se copia el dato de otra variedad. El código es `semillas/fichas.py` y lo transcripto a mano está en `semillas/datos/fichas_transcriptas.csv`.
- API: `GET /semillas/fichas` y campo `ficha` en `GET /semillas/cultivares/{id}` (rama SEMILLAS-consultas_en_la_api, todavía no en Render).

## 8 decies. Manejo por cultivo: la guía de maní adaptada a Argentina

Hernán subió una guía práctica de maní (Colombia, variedad Tatuí 76) y pidió adaptarla a Argentina para todos
los cultivos. Se usan sus temas como plantilla y se llenan solo con fuentes argentinas (INTA, SENASA, normas de
comercialización). Tabla `manejo_cultivos` (archivo fuente `semillas/datos/manejo_cultivos.csv`): una fila por
cultivo y tema, con `fuente`, `fuente_url` y `verificacion` ("texto leído" o "resumen del buscador" cuando el PDF
del INTA no abre desde la nube). Lo que no tiene fuente dice "sin dato verificado". 100 datos; los cultivos con más
temas cubiertos son maní, soja, girasol, trigo y sorgo; arveja, lenteja, caupí, quinoa, mostaza, triticale y cáñamo
todavía sin datos. Muchos números vienen de ensayos de una zona: son referencia, no receta.

Ampliación (Hernán pidió fuentes verificadas o papers): 251 datos con fuente, 222 con el texto leído.
Se sumaron los libros de cátedra de la UNLP (SEDICI / libros.unlp.edu.ar), el libro "El cultivo de garbanzo en
Argentina" (UNC 2016; se bajó de la copia de bichosdecampo.com porque el servidor de Córdoba no abre), artículos
de SciELO y la Res. INASE 473/2024. El repositorio del INTA y los PDF de CONICET no abren desde la nube.
Lenteja, caupí y mijo siguen sin datos públicos.
