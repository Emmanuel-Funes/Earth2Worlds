# Banco de semillas de Rotaterra: informe completo y fuentes

**Fecha de corte:** 04/11/2026 · **Equipo:** Earth2Worlds (Rotaterra, NASA Space Apps) · **Hilo:** "Armar el banco de semillas para San Luis"

Este informe cuenta qué se armó, de dónde sale cada dato y qué falta. El **Anexo** lista **todas** las fuentes que usa la base, sacadas automáticamente de la base misma (no a mano), con la cantidad de datos que aporta cada una.

## 1. Resumen
- **Qué es:** una base de variedades de cultivos extensivos de Argentina obtenidas por **entes públicos** (INTA, EEAOC, universidades, CONICET, ministerios provinciales), con ficha técnica por variedad, ensayos de rendimiento, manejo por cultivo y requerimientos de ambiente por especie.
- **Tamaño:** 547 variedades públicas en 27 cultivos (de 8.145 cultivares del registro oficial del INASE). Las variedades de empresas privadas están en la base pero **ocultas** en esta etapa, por decisión de Hernán.
- **Fichas:** 296 variedades con datos técnicos (ensayos, ciclo, sanidad, calidad, etc.); 251 solo con la ficha básica del registro del INASE (nombre, obtentor, año, especie). 4.417 datos de ficha en total, cada uno con fuente y link.
- **Huecos:** quedan **558 secciones de ficha sin dato** (de 6 secciones por variedad). Casi todo son maíces y sorgos viejos del INTA, porotos de la EEAOC, clones viejos de caña y papas, sin nada publicado.
- **¿Es confiable?** Sí: la identidad de cada variedad sale del registro legal (INASE), y cada valor tiene su fuente y link. Lo extranjero (EE.UU., FAO) va marcado. Lo que no se encontró dice "sin dato"; **no se inventó ningún número**.
- **¿Es completa?** No. La cobertura es parcial, aunque cada dato es trazable. Para cerrar huecos hace falta que el INTA pase sus fichas internas (ver §7).
- **Dónde está:** página web https://claude.ai/artifact/8zsoaG49rC1NedjcM9ayx2 (versión 34); base SQLite dentro de la API (`GET /semillas…`); archivos en `/mnt/project-files/rotaterra/semillas/`. Código en GitHub: PR #85 (base) y PR #84 (API). **Nada en main ni en Render** con estos últimos cambios: espera tu OK.


## 2. Cobertura por cultivo

| Cultivo | Variedades públicas | Con datos técnicos |
|---|---:|---:|
| Maíz | 66 | 9 |
| Sorgo | 60 | 19 |
| Porotos (negro, alubia, colorado) | 56 | 16 |
| Trigo | 43 | 38 |
| Avena | 40 | 38 |
| Caña de azúcar | 38 | 5 |
| Girasol | 33 | 16 |
| Cebada | 27 | 20 |
| Alfalfa | 27 | 26 |
| Papa | 25 | 10 |
| Centeno | 23 | 18 |
| Lino | 22 | 16 |
| Soja | 20 | 20 |
| Triticale | 16 | 11 |
| Arroz | 12 | 11 |
| Maní | 7 | 6 |
| Garbanzo | 7 | 4 |
| Algodón | 7 | 5 |
| Mijo | 3 | 0 |
| Lenteja | 3 | 1 |
| Colza/Canola | 3 | 3 |
| Quinoa | 2 | 2 |
| Caupí | 2 | 0 |
| Arveja | 2 | 1 |
| Mostazas (carinata, juncea) | 1 | 1 |
| Cáñamo industrial | 1 | 0 |
| Cártamo | 1 | 0 |

## 3. Cómo se armó (cronología)
| Fecha | Qué se hizo |
|---|---|
| 27/10 | Base desde el **Catálogo Nacional de Cultivares del INASE** (spec 049): 7.850 cultivares extensivos, 27 eventos transgénicos. Primeros ensayos del INTA San Luis 2025/26 (Villa Mercedes, Tilisarao, Granville). |
| 28/10 | Catálogo de variedades del INTA (planilla pública) cruzado con el INASE. Redes nacionales de ensayos: **RECSO soja 2025/26** (351 ensayos, OCR del informe), **RET trigo INASE 2018-2026** (878 ensayos, 24.270 rindes), **girasol INTA-ASAGIR 2023-2026**, **maíz INTA Marcos Juárez y Villegas**, **sorgo INTA Manfredi 2024/25**. |
| 29/10 | Base SQLite dentro de la API (spec 057) y página web. Hernán: solo variedades del INTA y solo cultivos extensivos (banco_inta, 460 variedades). |
| 30/10 | Tabla de fichas técnicas por variedad y tabla de **manejo por cultivo** (17 temas, de libros de la UNLP, SciELO, argentina.gob.ar). |
| 31/10 | Dossier de ambiente por especie (spec 061, `requerimientos_ambientales`, 1.597 datos; 279 cotejados contra los PDF originales). Hernán amplía: información de cultivos puede salir de cualquier sitio si la respalda un ente reconocido. |
| 01/11 | USDA GRIN-Global para fichas (marcado "medido en EE.UU."). Ficha básica del INASE para las que no tienen nada. Planilla de ficha técnica completa. Tandas de PDF que Hernán bajó a mano (alfalfa, trigo, girasol, sorgo, garbanzo, avena, cebada). |
| 02-03/11 | Tanda 3 (44 PDF) y tanda 4: caña (catálogo INTA), lino UNNE, papa, sorgo, garbanzo Kabuli NOA. |
| 04/11 | Hernán amplía el banco a **todos los entes públicos nacionales y provinciales** (547 variedades). Revisión de los **368 archivos** que subió: OCR de los escaneados; carga de triticale, centeno, trigo fideo, papa, verdeos, garbanzo TUC 450 (EEAOC), arveja, colza. Huecos de 589 a 558. pH por cultivo (3 búsquedas). **Auditoría de la matriz de pH v1** (3 errores, 5 mejoras argentinas). Tesis de la UNSL: 7 datos de San Luis cargados. |

## 4. Qué tiene cada parte de la base
| Tabla | Qué guarda | Filas | Fuente principal |
|---|---|---:|---|
| cultivares | Todos los cultivares extensivos del registro | 8.145 | INASE, Catálogo Nacional de Cultivares (descarga 28/10/2026, SHA-256 f264d33f…) |
| banco_inta | Variedades de entes públicos (lo que muestra la app) | 547 | INASE + catálogo de variedades del INTA |
| fichas_inta | Ficha técnica por variedad (6 secciones) | 4.417 | ver Anexo A |
| recso_* | Red de ensayos de soja 2025/26 | 3.618 rindes | RECSO / INTA |
| ret_* | Red de ensayos de trigo 2018-2026 | 24.270 rindes | INASE (RET) |
| girasol_* | Red girasol 2023-2026 | 1.583 rindes | INTA-ASAGIR |
| maiz_* | Ensayos de maíz 2024-2026 | 797 rindes | INTA Marcos Juárez y Villegas |
| sorgo_* | Sorgo granífero 2024/25 | 40 rindes | INTA Manfredi |
| san_luis_* | Ensayos INTA EEA San Luis 2025/26 | 59 rindes | INTA San Luis (IT 211 y 213) |
| manejo_cultivos | Buenas prácticas por cultivo | 534 | ver Anexo B |
| requerimientos_ambientales | Heladas, calor, suelo, sales, pH, Kc, raíces por especie | 1.604 | ver Anexo C (664 Argentina, 93 San Luis, 847 global marcados) |
| eventos_ogm | Eventos transgénicos | 27 | INASE / SAGyP |

## 5. Reglas de calidad que se aplicaron
1. Cada valor lleva **fuente y link**; los tests automáticos rechazan una ficha sin fuente o sin URL, o de un sitio fuera de la lista permitida salvo que diga "No oficial".
2. **No se inventa ningún número.** Lo que no se encontró dice "sin dato verificado".
3. Lo extranjero o global (USDA GRIN, FAO, EcoCrop) va marcado y **nunca sirve para descartar** un cultivo.
4. **Nivel de verificación** en cada dato: "texto leído" (PDF abierto), "resumen del buscador" (falta leer) o "falta fuente".
5. Los nombres de variedad se cruzan con especie y nombre exacto (se corrigió, por ejemplo, el choque de nombre entre mijo y cebada TRINIDAD INTA).
6. pH: siempre **de referencia**; manda el pH de laboratorio del productor.
7. No se saltó ningún control de acceso: lo bloqueado lo bajó Hernán a mano.

## 6. pH por cultivo (resumen)
Fuentes argentinas encontradas: **alfalfa** 6,5–7,5 (INTA Manfredi) y 6,8–7,2 (INTA Esquel); **avena** tolera 4,5–6; **cebada** se adapta a suelos alcalinos (INTA Valle Inferior); **sorgo** ensayo a pH 9 (Instituto de Suelos INTA); **maní** 5,8–6,5, con falta de manganeso por encima de 6,5 (INTA Manfredi); **colza** 5,5–8,3 y **lino** 6–7 (UNLP); **caña** 5–8 (EEAOC); **garbanzo** 6–9 (INASE/SISA). Para soja, maíz, trigo y girasol **no hay un pH máximo argentino**: con pH alto el riesgo es la falta de micronutrientes (clorosis férrica en soja, INTA Pergamino) y la sodicidad (maíz, INTA Cuenca del Salado). Detalle en `reports/pH adaptable por cultivo - hallazgos 04-11.md` y `reports/Auditoria tabla pH Cultivos v1 - 04-11.md`.

## 7. Qué falta y cómo seguir
- 558 secciones sin dato. Ya tenés armado el pedido para el INTA: `semillas/Pedido-de-fichas-al-INTA.md` (245 variedades).
- Mail a Jorge Mercau (INTA San Luis): esperando respuesta.
- No hay ensayos en el sur de San Luis (Dupuy, Buena Esperanza).
- Para pasar a Render y a main hace falta tu OK.

## 8. Archivos del trabajo
- Página: https://claude.ai/artifact/8zsoaG49rC1NedjcM9ayx2
- `/mnt/project-files/rotaterra/semillas/semillas.sqlite`, `Ficha-tecnica-completa-variedades-INTA.xlsx`, `base_semillas_extensivas.xlsx`, `fichas_inta.csv`, `manifiesto.json`
- Informes: `/mnt/project-files/rotaterra/reports/` (pH, auditoría, tesis)
- Bitácora: `/mnt/project-files/rotaterra/BITACORA-avances-y-como-replicar.md`

---
# Anexos: todas las fuentes usadas
Sacadas de la base al 04/11/2026. "Datos" = cantidad de filas que aporta cada fuente.

## Fuentes institucionales de la base (tabla `fuentes`)
| Fuente | Organismo | Qué aporta | Link |
|---|---|---|---|
| Catálogo Nacional de Cultivares (RNC/RNPC) | INASE | Denominación oficial, especie, condición genética, grupo, fechas RNC/RNPC, validez RNPC, país, características (GM, TR, CL, AO), evento transgénico declarado, s | https://gestion.inase.gob.ar/registroCultivares/publico/catalogo |
| Registro Nacional de Cultivares: alcance registral | INASE | Qué significa estar inscripto en RNC (habilita comercializar) y en RNPC (propiedad) | https://www.argentina.gob.ar/inase/registro-nacional-cultivares |
| Catálogo nacional de cultivares RNC/RNPC (datos abiertos) | INASE / Datos Argentina | Instantánea a septiembre de 2019 del catálogo | https://datos.gob.ar/dataset/agroindustria-inase---catalogo-nacional-cultivares---rnc-rnpc |
| Descripciones de variedades | INASE | Descriptores morfológicos y perfiles moleculares de algunas especies | https://www.argentina.gob.ar/inase/variedades-vegetales/descripciones-de-variedades |
| Rotulado de semillas | INASE | Clase/categoría de rotulado exigida por especie (fiscalizada, identificada) | https://www.argentina.gob.ar/inase/rotulado-de-semillas |
| Eventos vegetales con autorización comercial | SAGyP / Biotecnología | Evento (código OCDE), especie, característica, solicitante, resolución y fecha | https://www.argentina.gob.ar/economia/agricultura/subsecretaria-de-produccion-agropecuaria-y-forestal-0/ogm-vegetal-eventos-con |
| Documentos de decisión de CONABIA | CONABIA | Decisión de bioseguridad por evento | https://www.argentina.gob.ar/agricultura/bioeconomia/biotecnologia/documentos-de-decision-conabia |
| Catálogo de variedades vegetales INTA | INTA | Ficha técnica, situación de registro y licenciamiento de materiales INTA | https://www.argentina.gob.ar/inta/variedades |
| Semillas comercializadas por INTeA | INTeA | Listas por especie de materiales que INTeA comercializa o licencia | https://www.argentina.gob.ar/intea/servicios/regalias/semillas |
| Cultivares de maní Runner | INTA | ASEM 353, 400, 450-RS, 451-RC, 452-RC INTA y vinculación comercial | https://www.argentina.gob.ar/inta/tecnologias/cultivares-de-mani-runner |
| Catálogo de variedades de caña de azúcar | INTA | Perfiles de 6 variedades INTA (TUC, CP, NA) | https://www.argentina.gob.ar/noticias/catalogo-de-variedades-de-cana-de-azucar-de-inta |
| SISA: reportes de variedades declaradas por campaña | SAGyP / ARCA | Qué cultivares se declararon y en cuánta superficie, por campaña | https://www.argentina.gob.ar/sites/default/files/sisa_algodon_24_25.pdf |
| Red Nacional de Evaluación de Cultivares de Soja (RECSO) y SoyVar | INTA / ASA | 2025/26: 88 cultivares, 66 localidades, más de 350 ensayos (según comunicado 07/07/2026) | https://www.recsoargentina.com/ |
| Red de Ensayos Comparativos de Trigo (RET) – visualizador | INTA / INASE | Resultados 2005/06 a 2024/25 por cultivar, subregión y campaña | https://www.argentina.gob.ar/noticias/nueva-herramienta-interactiva-para-consultar-los-resultados-de-la-red-de-ensayos |
| Red Nacional de Cultivares de Girasol INTA-ASAGIR | INTA / ASAGIR | Rinde, aceite y rinde ajustado por híbrido y localidad, una planilla por ensayo | https://asagir.org.ar/acerca-de-red-de-ensayos-de-girasol-inta-asagir-463 |
| Red de híbridos de maíz en siembra temprana, INTA Marcos Juárez | INTA | 30 a 41 híbridos en 9 a 10 sitios del centro-sur de Córdoba (incluye Mattaldi, Río Cuarto y Laboulaye) | https://www.argentina.gob.ar/inta/cr-cordoba/red-de-evaluacion-de-hibridos-de-maiz-en-siembra-temprana-inta-marcos-juarez-informe |
| Red de evaluación de híbridos de maíz del norte de Buenos Aires | INTA | Híbridos en fecha temprana y tardía en 9 de Julio, Bolívar, Chivilcoy, Gral. Villegas, Junín, Pergamino y S. A. de Areco | https://www.argentina.gob.ar/inta/cr-buenosaires-norte/red-de-evaluacion-de-hibridos-de-maiz-del-norte-de-buenos-aires/resultados |
| Ensayo comparativo de híbridos de sorgo granífero, INTA EEA Manfredi | INTA | 40 híbridos graníferos y doble propósito: rinde, ciclo, tanino, floración, altura y peso hectolítrico | https://repositorio.inta.gob.ar/handle/20.500.12123/22621 |
| Híbridos de maíz en San Marcos Sud | INTA | Rinde de híbridos comerciales en siembra temprana (1 sitio) | https://www.argentina.gob.ar/inta/cr-cordoba/evaluacion-del-rendimiento-de-hibridos-de-maiz-en-san-marcos-sud-campana-20252026 |
| Maíz de segunda en Morrison | INTA | Rinde de híbridos de segunda; 332 mm de agua útil inicial y 387 mm en el ciclo | https://www.argentina.gob.ar/inta/cr-cordoba/evaluacion-del-rendimiento-de-hibridos-de-maiz-de-segunda-en-morrison-20252026 |
| Evaluación de cultivares de trigo pan, INTA Marcos Juárez | INTA | Rinde y calidad de cultivares de trigo pan, campaña 2025 | https://repositorio.inta.gob.ar/bitstream/handle/20.500.12123/25851/INTA_CRCordoba_EEAMarcosJuarez_G%C3%B3mez_D_Evaluaci%C3%B3n_cultivares_trigo_pan.pdf?isAllowed=y&sequence=1 |
| Ensayos agrícolas en San Luis 2025/26: maíz, sorgo, soja, trigo y algodón | INTA EEA San Luis + FICA-UNSL | Maíz en Villa Mercedes (2 densidades) y Tilisarao (23 híbridos), trigo Klein en Villa Mercedes, sorgo y algodón | https://repositorio.inta.gob.ar/xmlui/handle/20.500.12123/27891 |
| Ensayos agrícolas en San Luis: maíz, soja, sorgo y algodón | INTA EEA San Luis | Ensayos de campañas anteriores (incluida 2022/23) en la provincia del piloto | https://repositorio.inta.gob.ar/bitstream/handle/20.500.12123/16825/INTA_CR_LaPampa-SanLuis_EEASanLuis_Bravo%2CM.B._Ensayos%20agricolas%20en%20la%20provincia%20de%20San%20Luis.%20Ma%C3%ADz%2C%20Soja%2C%20Sorgo%2C%20Algodon.pdf?isAllowed=y&sequence=1 |
| Ensayo multisitio de arveja y lenteja 2024/25 (PMP 64) | INTA / FCA-UNR | Arveja multisitio; lentejas Silvina y Turca y líneas en desarrollo | https://www.argentina.gob.ar/sites/default/files/2025/12/pmp_64_web.pdf |
| Cotizaciones de semilleros y cooperativas | Proveedores | Stock, categoría de semilla, precio y fecha por campaña y región |  |

## Anexo A. Fichas técnicas por variedad (309 fuentes distintas)

### INTA (2387 datos)

| Fuente | Datos | Link |
|---|---:|---|
| INTA EEA Marcos Juárez, Donaire G. y col., «Comportamiento productivo de cereales de invierno en INTA EEA Marcos Juárez durante la campaña agrícola 2024» (PDF del repositorio INTA subido por Hernán el 04/11/2026) | 76 | https://repositorio.inta.gob.ar/handle/20.500.12123/21682 |
| INTA EEA Marcos Juárez, Donaire G. y col., «Comportamiento productivo de cereales de invierno en INTA EEA Marcos Juárez. Año 2025» (PDF del repositorio INTA subido por Hernán el 04/11/2026) | 75 | https://repositorio.inta.gob.ar/handle/20.500.12123/25634 |
| INTA EEA Bordenave, González G. y col., «Evaluación de cultivares de verdeos de invierno para producción de forraje en INTA EEA Bordenave. Campaña 2023» (PDF del repositorio INTA subido por Hernán el 31/10/2026) | 74 | https://repositorio.inta.gob.ar/xmlui/handle/20.500.12123/16679 |
| INTA EEA Corrientes, «Proyecto Arroz: resultados de la campaña 2025-26», ensayos regionales en 6 sitios (PDF subido por Hernán el 04/11/2026) | 56 | https://repositorio.inta.gob.ar/ |
| Perlo Gallio A., Porta Siota F. y col. (INTA EEA Anguil y CIALP), «Evaluación de cultivares de triticale para diferentes usos, año 2021»; handle no identificado | 55 | https://repositorio.inta.gob.ar/ |
| Dietz (UNLP, dir. M. R. Simón), Características de sanidad, rendimiento y calidad en genotipos de avena en filiales avanzadas de un programa de mejoramiento, tesis de maestría FCAyF-UNLP (2018); ensayos en EEA J. Hirschhörn (La Plata) y EEA INTA Bordenave | 48 | https://sedici.unlp.edu.ar/handle/10915/68021 |
| INTA EEA Marcos Juárez, Donaire G. y col., «Comportamiento productivo de cereales de invierno en INTA EEA Marcos Juárez. Campaña agrícola 2022» (PDF del repositorio INTA subido por Hernán el 04/11/2026) | 48 | https://repositorio.inta.gob.ar/handle/20.500.12123/14348 |
| INTA EEA Anguil, Cereales invernales. Resultados de ensayos de evaluación de cultivares y manejo en trigo, cebada, centeno, avena y triticale. Campaña 2021 | 45 | https://repositorio.inta.gob.ar/handle/20.500.12123/11873 |
| INTA, noticia: El INTA desarrolló dos nuevas variedades de caña de azúcar (INTA Famaillá) | 38 | https://www.argentina.gob.ar/noticias/el-inta-desarrollo-dos-nuevas-variedades-de-cana-de-azucar-0 |
| No oficial (revista técnica): Giorda L.M. y col. (INTA EEA Manfredi), «Nuevos desarrollos: híbridos y variedades graníferos y forrajeros 2017», Engormix (25/10/2017) | 38 | https://www.engormix.com/agricultura/sorgo-granifero/nuevos-desarrollos-hibridos-variedades_a41376/ |
| Wehrhahne N.L., «Evaluación de parámetros de calidad molinera de avenas en Argentina», tesis Universidad Nacional del Sur, ensayos en la Chacra Experimental Integrada Barrow (INTA-MAA) 2004-2005 (PDF subido por Hernán el 04/11/2026) | 36 | https://repositorio.inta.gob.ar/handle/20.500.12123/5925 |
| INTA EEA Rafaela, «Información técnica de cultivos de invierno, campaña 2018» (Año 1 Nº 6; PDF subido por Hernán el 04/11/2026; handle del repositorio no identificado) | 27 | https://repositorio.inta.gob.ar/ |
| Donaire G. y col. (INTA EEA Marcos Juárez), «Evaluación de cultivares de trigo fideo, campaña 2023»; handle no identificado | 26 | https://repositorio.inta.gob.ar/ |
| Arolfo y Odorizzi (INTA EEA Manfredi), «Evaluación de cultivares y panorama varietal», cap. 8 en Basigalup (comp.), Investigación, producción e industrialización de la alfalfa en Argentina, Ediciones INTA 2022, Tabla 3 (red INTA 2004-2018) | 25 | https://repositorio.inta.gob.ar/handle/20.500.12123/18718 |
| Donaire, Reartes, Conde y González (INTA EEA Marcos Juárez y Bordenave), Evaluación de cultivares de centeno y cebada forrajera para producción de forraje, campaña 2022 (año seco, 70 heladas) | 24 | https://repositorio.inta.gob.ar/handle/20.500.12123/14309 |
| Wehrhahne (INTA Chacra Experimental Integrada Barrow), La Chacra Experimental de Barrow y la obtención de nuevos cultivares de avena, revista AgroBarrow 56, mayo 2015, pp. 14-15 | 24 | https://repositorio.inta.gob.ar/handle/20.500.12123/3261 |
| Di Nucci, Formento y Díaz (INTA EEA Paraná), «Avena: producción y comportamiento a roya de la hoja en la campaña 2003», 2004 (copia en produccion-animal.com.ar) | 23 | https://produccion-animal.com.ar/produccion_y_manejo_pasturas/pasturas_combate_de_plagas_y_malezas/40-roya_de_la_hoja_en_avena.pdf |
| INTA, Oferta tecnológica: cultivares de maní runner (INTA Manfredi) | 23 | https://www.argentina.gob.ar/inta/tecnologias/cultivares-de-mani-runner |
| Donaire, Reartes y col. (INTA EEA Marcos Juárez), Evaluación de cultivares de cebada forrajera y centeno, año 2025 | 22 | https://repositorio.inta.gob.ar/handle/20.500.12123/25574 |
| INTA, noticia: INTA y Seedar SA, más de 20 años de trabajo articulado (10/07/2023) | 22 | https://www.argentina.gob.ar/noticias/inta-y-seedar-sa-mas-de-20-anos-de-trabajo-articulado |
| Macro Seed (licenciatario de INTA), catálogo de productos (macroseed.com.ar/file/catalogo-ms.pdf) | 22 | https://www.macroseed.com.ar/file/catalogo-ms.pdf |
| INTA EEA Marcos Juárez, Donaire G. y col., «Comportamiento productivo de cereales de invierno para doble propósito en la EEA Marcos Juárez.» (PDF del repositorio INTA subido por Hernán el 04/11/2026) | 20 | https://repositorio.inta.gob.ar/handle/20.500.12123/6040 |
| Wehrhahne (INTA CHEI Barrow), Evaluación de parámetros de calidad molinera de avenas en Argentina, tesis de Magíster, Universidad Nacional del Sur, 2009 (ensayos en Barrow 2004 y 2005, 10 cultivares) | 20 | https://repositorio.inta.gob.ar/handle/20.500.12123/5925 |
| Donaire, Reartes y col. (INTA EEA Marcos Juárez), Evaluación de cultivares comerciales de avena y cebada forrajera para producción de forraje, campaña 2020 | 19 | https://repositorio.inta.gob.ar/handle/20.500.12123/9722 |
| INTA, noticia: Algodón, desarrollan tres nuevas variedades de alta calidad | 19 | https://www.argentina.gob.ar/noticias/algodon-desarrollan-tres-nuevas-variedades-de-alta-calidad |
| Cerdá C.C. y col. (INTA EEA Bordenave), Verdeos de invierno para la producción de forraje: campaña 2024 (ficha de divulgación) | 18 | https://repositorio.inta.gob.ar/handle/20.500.12123/21297 |
| Gallego J.J. y col. (INTA EEA Valle Inferior, convenio Provincia de Río Negro), «Verdeos de invierno: producción de forraje de cultivares de avena, cebada, centeno, triticale y raigrás anual»; handle no identificado | 18 | https://repositorio.inta.gob.ar/ |
| INTA, noticia: Genética aplicada al campo, la propuesta del INTA en Expoagro (12/03/2026) | 18 | https://www.argentina.gob.ar/noticias/genetica-aplicada-al-campo-la-propuesta-del-inta-en-expoagro |
| INTA EEA Bordenave, red de evaluación de cultivares de avena 1990-2004 (Bordenave, Barrow, Marcos Juárez, Paraná, Anguil), publicado en Engormix | 17 | https://www.engormix.com/lecheria/avena-manejo/adaptabilidad-estabilidad-productiva-cultivares_a27134/ |
| Rev. Fac. Agron. La Plata 122 (2023), «Comportamiento de variedades de lino oleaginoso en el sudeste de Buenos Aires, Argentina» (EEA Balcarce, campañas 2015, 2019 y 2020; PDF subido por Hernán el 04/11/2026) | 17 | https://repositorio.inta.gob.ar/handle/20.500.12123/16983 |
| Romero (INTA EEA Rafaela), Producción anual y total de cultivares de alfalfa de latencia intermedia y sin latencia, Red Nacional de Cultivares de Alfalfa, marzo 2022 (DGC α=0,05) | 17 | https://repositorio.inta.gob.ar/xmlui/handle/20.500.12123/18589 |
| Basigalup (comp.), Investigación, producción e industrialización de la alfalfa en Argentina, Ediciones INTA 2022, cap. «Mejoramiento genético y desarrollo de variedades» (copia del libro aportada por Hernán) | 16 | https://repositorio.inta.gob.ar/handle/20.500.12123/18465 |
| Bodega, Di Battista y col. (FCA-UNMdP, Balcarce), «Comportamiento de variedades de lino oleaginoso en el sudeste de Buenos Aires», Rev. Fac. Agron. La Plata 122 (2023); ensayos en EEA INTA Balcarce 2015, 2019 y 2020 | 16 | https://revistas.unlp.edu.ar/revagro/article/download/13800/14937/64385 |
| INTA EEA Marcos Juárez, Donaire G. y col., «Comportamiento productivo de cereales de invierno en INTA EEA Marcos Juárez durante la campaña agrícola 2024.» (PDF del repositorio INTA subido por Hernán el 04/11/2026) | 16 | https://repositorio.inta.gob.ar/handle/20.500.12123/21682 |
| INTA EEA Marcos Juárez, Donaire G. y col., «Evaluación de cultivares de triticale para producción de forraje y de grano en INTA EEA Marcos Juárez. Campaña agrícola 2022» (PDF subido por Hernán) | 16 | http://hdl.handle.net/20.500.12123/14405 |
| No oficial (prensa: Infocampo 21/03/2013, cita a Daniel Basigalup, INTA Manfredi, obtentor) | 16 | https://www.infocampo.com.ar/alfalfa-tres-opciones-mas-para-la-ganaderia/ |
| Alvarez, Mazzalay y Heinz (INTA EEA Manfredi, Mejoramiento de Girasol), Evaluación del comportamiento de híbridos de girasol aceiteros, campaña 2020/21 (20 híbridos, siembra 22/12/2020, 45.000 pl/ha) | 15 | https://core.ac.uk/download/525024589.pdf |
| Donaire, Reartes y col. (INTA EEA Marcos Juárez), Evaluación de cultivares de avena para producción de forraje, campaña 2025 | 15 | https://repositorio.inta.gob.ar/handle/20.500.12123/25292 |
| INTA EEA Marcos Juárez, Donaire G. y col., «Comportamiento productivo de cereales de invierno en INTA EEA Marcos Juárez. Año 2025.» (PDF del repositorio INTA subido por Hernán el 04/11/2026) | 15 | https://repositorio.inta.gob.ar/handle/20.500.12123/25634 |
| INTA San Juan, ficha técnica Morrillos INTA (Oferta tecnológica) | 15 | https://www.argentina.gob.ar/inta/tecnologias/quinoa-chenopodium-quinoa-willd-morrillos-inta |
| INTA, Programa de Mejoramiento Genético de Caña de Azúcar (EEA Famaillá), «Catálogo de nuevas variedades de caña de azúcar INTA» (2024; variedades inscriptas en 2015; ratings S=susceptible, MS=medianamente susceptible, MT=medianamente tolerante, T=tolerante; período de cosecha leído de la barra del gráfico) | 15 | https://argentina.gob.ar/sites/default/files/2024/07/catalogo_de_nuevas_variedades_de_cana_de_azucar_inta.pdf |
| Pachecoy, Dirchwolf, Fontana y col. (INTA EEA Corrientes y AER San Javier), Ensayos Regionales de Cultivares de arroz, campaña 2025-26, en Proyecto Arroz: resultados campaña 2025/2026, Ediciones INTA | 15 | https://repositorio.inta.gob.ar/handle/20.500.12123/27743 |
| Arolfo V. y Odorizzi A. (INTA Manfredi), «Evaluación de cultivares y panorama varietal», cap. 8 del libro de alfalfa, Tabla 3 (PDF subido por Hernán el 04/11/2026) | 14 | https://repositorio.inta.gob.ar/handle/20.500.12123/14007 |
| Donaire, Reartes y col. (INTA EEA Marcos Juárez), Evaluación de cultivares de avena para producción de forraje, campaña 2024 | 14 | https://repositorio.inta.gob.ar/handle/20.500.12123/21681 |
| Donaire, Reartes y col. (INTA EEA Marcos Juárez), Evaluación de cultivares de cebada forrajera y centeno para producción de forraje, año 2025 | 14 | https://repositorio.inta.gob.ar/handle/20.500.12123/25574 |
| No oficial (prensa que cita al INTA Marcos Juárez, obtentor C. Bainotti): Infocampo (19/10/2017) | 14 | https://www.infocampo.com.ar/?p=383263 |
| Donaire, Reartes y col. (INTA EEA Marcos Juárez), Evaluación de cultivares comerciales de avena para producción de forraje, campaña 2022 | 13 | https://repositorio.inta.gob.ar/handle/20.500.12123/14531 |
| Donaire, Reartes y col. (INTA EEA Marcos Juárez), Evaluación de cultivares comerciales de avena, campaña 2022 | 13 | https://repositorio.inta.gob.ar/handle/20.500.12123/14531 |
| Donaire, Reartes y col. (INTA EEA Marcos Juárez), Evaluación de cultivares de cebada para producción de forraje, año 2024 | 13 | https://repositorio.inta.gob.ar/handle/20.500.12123/21680 |
| Formento y Kuttel (INTA EEA Paraná), Comportamiento de avenas comerciales frente a roya de la hoja y roya del tallo. Resultados del año 2022, Hoja informativa (siembra 19/04/2022, evaluación en septiembre) | 13 | https://repositorio.inta.gob.ar/handle/20.500.12123/15739 |
| INTA EEA Marcos Juárez, Donaire G. y col., «Evaluación de cultivares de triticale para producción de forraje y de grano en INTA EEA Marcos Juárez durante el año 2020» (PDF subido por Hernán) | 13 | http://hdl.handle.net/20.500.12123/9709 |
| INTA, Catálogo de variedades: Maíz Bautista INTA (EEA Cerro Azul) | 13 | https://www.argentina.gob.ar/inta/relaciones-estrategicas-del-inta/maiz-bautista-inta |
| INTA, noticia: Triticale, presentan tres nuevas variedades del cereal forrajero (21/05/2019) | 13 | https://www.argentina.gob.ar/noticias/triticale-presentan-tres-nuevas-variedades-del-cereal-forrajero |
| Rodríguez Pardina P.E. et al. (IPAVE-CIAP-INTA / IIACS-INTA), «Evaluación del comportamiento de cultivares y líneas experimentales de poroto común frente a infecciones naturales de virus», Horticultura Argentina 37(94), 2018 (Leales, Tucumán, 2013-2016; escala CIAT 1 = sin síntomas a 9 = muy grave) | 13 | https://repositorio.inta.gob.ar/handle/20.500.12123/4429 |
| Royo y Brach (INTA EEA Reconquista), Producción y calidad nutricional de avenas en la cadena forrajera, Voces y Ecos 37 (campaña 2016, norte de Santa Fe) | 13 | https://repositorio.inta.gob.ar/handle/20.500.12123/3482 |
| Donaire, Reartes y col. (INTA EEA Marcos Juárez), Evaluación de cultivares comerciales de avena para producción de forraje, campaña 2021 | 12 | https://repositorio.inta.gob.ar/handle/20.500.12123/14110 |
| Donaire, Reartes y col. (INTA EEA Marcos Juárez), Evaluación de cultivares comerciales de avena para producción de forraje, campaña 2023 | 12 | https://repositorio.inta.gob.ar/handle/20.500.12123/17457 |
| Donaire, Reartes y col. (INTA EEA Marcos Juárez), Evaluación de cultivares de cebada forrajera y centeno para producción de forraje, campaña 2023 | 12 | https://repositorio.inta.gob.ar/handle/20.500.12123/17428 |
| INTA EEA Corrientes, «Proyecto Arroz. Campaña 2023-2024», Vol. XXXII, Ediciones INTA 2024 | 12 | https://argentina.gob.ar/sites/default/files/2024/10/arroz_resultados_campana_2023-24_0.pdf |
| INTA, noticia: Cebada, apuntes para planificar la próxima campaña (Chacra Barrow) (28/05/2020) | 12 | https://www.argentina.gob.ar/noticias/cebada-apuntes-para-planificar-la-proxima-campana |
| INTA, noticia: El INTA presenta una nueva cebada cervecera, Beatriz INTA (14/04/2026) | 12 | https://www.argentina.gob.ar/noticias/el-inta-presenta-una-nueva-cebada-cervecera |
| INTA, noticia: Presentan una cebada diseñada para el pastoreo directo (sección sobre cultivares del INTA Bordenave) (22/04/2019) | 12 | https://www.argentina.gob.ar/noticias/presentan-una-cebada-disenada-para-el-pastoreo-directo |
| INTA, noticia: Presentan una cebada diseñada para el pastoreo directo, Trinidad INTA (22/04/2019) | 12 | https://www.argentina.gob.ar/noticias/presentan-una-cebada-disenada-para-el-pastoreo-directo |
| INTA, noticia: Triticale, una especie en expansión con dos nuevos cultivares del INTA (29/12/2025) | 12 | https://www.argentina.gob.ar/noticias/triticale-una-especie-en-expansion-con-dos-nuevos-cultivares-desarrollados-por-el-inta |
| Vaccaro M.E., Valentinuz E., Formento Á.N. (INTA EEA Paraná/AER Gualeguay), en Serie de Extensión INTA Paraná N.º 92 (2024), «Comportamiento a enfermedades (mancha amarilla y roya estriada) y rendimiento de cultivares de trigo, ciclo 2023/24, Gualeguay» (PDF subido por Hernán el 04/11/2026) | 12 | https://repositorio.inta.gob.ar/ |
| Formento N. y Kuttel W. (INTA EEA Paraná), «Comportamiento de cultivares comerciales de avena a la roya de la hoja (Puccinia coronata)», Serie Extensión INTA Paraná N.º 87 (2022) (PDF subido por Hernán el 04/11/2026) | 11 | https://repositorio.inta.gob.ar/handle/20.500.12123/11520 |
| INTA EEA Bordenave, Giménez F., González G.A. y González A., «Producción de forraje de los cultivares de avena en la EEA Bordenave, año 2022» (PDF del repositorio INTA subido por Hernán el 31/10/2026) | 11 | https://repositorio.inta.gob.ar/xmlui/handle/20.500.12123/14161 |
| INTA, noticia: El INTA lidera el mejoramiento genético de la papa | 11 | https://www.argentina.gob.ar/noticias/el-inta-lidera-el-mejoramiento-genetico-de-la-papa |
| INTA, noticia: Presentan una nueva cebada forrajera, Nacira INTA (21/01/2025) | 11 | https://www.argentina.gob.ar/noticias/presentan-una-nueva-cebada-forrajera |
| No oficial (prensa): La Voz del Pueblo, «El INTA presentó dos cultivares de avena resistentes a roya de la hoja» (27/12/2021), citando a INTA Bordenave e INTA Paraná | 11 | https://www.lavozdelpueblo.com.ar/2021-12-27-el-inta-presento-dos-cultivares-de-avena-resistentes-a-roya-de-la-hoja |
| Cerdá C.C., Gómez D. y Rifai A. (INTA EEA Bordenave), Resultados verdeos de invierno con destino de silaje en un ambiente semiárido, campaña 2024 (ficha de divulgación) | 10 | https://repositorio.inta.gob.ar/handle/20.500.12123/22569 |
| INTA EEA Abra Pampa, Informe técnico 'Evaluación de variedades comerciales de papa 2021-2025' (Castro et al., 2025) e INTA Balcarce/UNMDP, Bedogni 2025 (Visión Rural); handle no identificado | 10 | https://repositorio.inta.gob.ar/ |
| INTA, Catálogo de variedades: Avena Florencia INTA (EEA Bordenave) | 10 | https://www.argentina.gob.ar/inta/relaciones-estrategicas-del-inta/avena-florencia-inta |
| INTA, noticia: El INTA desarrolló dos nuevos cultivares de soja (INTA Paraná) | 10 | https://www.argentina.gob.ar/noticias/el-inta-desarrollo-dos-nuevos-cultivares-de-soja |
| Ministerio de Desarrollo Agrario de la Provincia de Buenos Aires (coobtentor con el INTA, CEI Barrow), «Registró dos nuevas variedades de trigo candeal» (ene. 2021) | 10 | https://www.gba.gob.ar/desarrollo_agrario/Noticias/el_ministerio_de_desarrollo_agrario_registr%C3%B3_dos_nuevas_variedades_de |
| No oficial (prensa): Infocampo, «Nuevas variedades de porotos desarrolladas por el INTA» (10/05/2011), citando a INTA Cerrillos (Salta) | 10 | https://www.infocampo.com.ar/?p=246208 |
| No oficial (prensa: Infocampo 27/12/2007, describe la inscripción del INTA Manfredi en el RNC) | 10 | https://www.infocampo.com.ar/inscribieron-nuevas-lineas-de-sorgo-azucarado/ |
| Balbo, Carreras y otros (UNC, INTA EEA Manfredi y CEPROCOR), Calidad nutricional y potencial productivo de genotipos de garbanzo Kabuli y Desi en ambientes de Argentina, Nexo Agropecuario, edición especial 1, 2024, Fig. 1 (valores leídos del gráfico, aproximados) | 9 | https://revistas.unc.edu.ar/index.php/nexoagro/article/download/45191/45172/182838 |
| Fraschina et al. (INTA EEA Marcos Juárez y Pergamino), Evaluación de cultivares de trigo en campo de productores durante el año 2019 (6 localidades: Pergamino, Bragado, Corral de Bustos, Marcos Juárez, Los Molinos, Monte Buey) | 9 | https://core.ac.uk/download/335290279.pdf |
| INTA Informa (INTA Bordenave), «Emilio INTA, sinónimo de más pasto y más granos» (25/07/2011) | 9 | https://intainforma.inta.gob.ar/emilio-inta-sinonimo-de-mas-pasto-y-mas-granos/ |
| INTA, Catálogo de variedades: Lino Aguará INTA (EEA Paraná) | 9 | https://www.argentina.gob.ar/inta/relaciones-estrategicas-del-inta/lino-aguara-inta |
| INTA, noticia: Nueva variedad de avena, Camila INTA (11/12/2025) | 9 | https://www.argentina.gob.ar/noticias/nueva-variedad-de-avena-camila-inta |
| INTA, noticia: Presentan una nueva avena con potencial forrajero (30/04/2026) | 9 | https://www.argentina.gob.ar/noticias/presentan-una-nueva-avena-con-potencial-forrajero |
| Moreyra (INTA Bordenave) y Abbate (INTA Balcarce), Rendimiento y estabilidad de los cultivares de cebada en Argentina, Ediciones INTA | 9 | https://repositorio.inta.gob.ar/handle/20.500.12123/19529 |
| No oficial (semillero licenciatario): Guasch Semillas, ficha «Maíz Amancay INTA» (INTA EEA Pergamino + Guasch) | 9 | https://guasch.com.ar/website/pages/interior_productos.php?idVariedad=413 |
| No oficial (semillero licenciatario): Porosem SRL, ficha comercial de Leales B30 INTA (consultada 31/10/2026) | 9 | https://www.porosem.com.ar/semillas/leales-b30-inta |
| No oficial (semillero licenciatario): Porosem SRL, ficha comercial de Leales B40 INTA (consultada 31/10/2026) | 9 | https://www.porosem.com.ar/semillas/leales-b40-inta |
| No oficial (semillero licenciatario): Porosem SRL, ficha comercial de Leales C1 INTA (consultada 31/10/2026) | 9 | https://www.porosem.com.ar/semillas/leales-c1-inta |
| No oficial (semillero licenciatario): Porosem SRL, ficha comercial de Leales Cr5 INTA (consultada 31/10/2026) | 9 | https://www.porosem.com.ar/semillas/leales-cr5-inta |
| No oficial (semillero licenciatario): Porosem SRL, ficha comercial de Leales R4 INTA (consultada 31/10/2026) | 9 | https://www.porosem.com.ar/semillas/leales-r4-inta |
| Vaccaro M.E. et al., «Evaluación comparativa de cultivares de avena en Gualeguay, Entre Ríos», Serie Extensión INTA Paraná N° 89, 2023 (siembra 10/05/2022, lote de tambo, 5 cultivares en franjas) | 9 | https://repositorio.inta.gob.ar/handle/20.500.12123/14603 |
| Donaire, Reartes y col. (INTA EEA Marcos Juárez), Evaluación de cultivares de avena y cebada forrajera, campaña 2020 | 8 | https://repositorio.inta.gob.ar/handle/20.500.12123/9722 |
| Donaire, Reartes y col. (INTA EEA Marcos Juárez), Evaluación de cultivares de centeno para producción de forraje, campaña 2024 | 8 | https://repositorio.inta.gob.ar/handle/20.500.12123/21642 |
| INTA EEA Marcos Juárez, Donaire G. y col., «Comportamiento productivo de cereales de invierno en INTA EEA Marcos Juárez. Campaña agrícola 2022.» (PDF del repositorio INTA subido por Hernán el 04/11/2026) | 8 | https://repositorio.inta.gob.ar/handle/20.500.12123/14348 |
| INTA Marcos Juárez y Paraná, oferta tecnológica «Variedades de soja No-OGM con calidad diferencial (specialty)» (características del grupo de variedades ALIM) | 8 | https://www.argentina.gob.ar/inta/tecnologias/variedades-de-soja-no-ogm-con-calidad-diferencial-specialty |
| INTA Paraná (nota firmada «Por INTA» en Agrofy News, 30/10/2014; cita a H. Milisich) | 8 | https://news.agrofy.com.ar/noticia/144574/se-obtuvieron-dos-nuevos-cultivares-lino |
| INTA, Catálogo de variedades: Garbanzo Kiara INTA (EEA Salta) | 8 | https://www.argentina.gob.ar/inta/relaciones-estrategicas-del-inta/garbanzo-kiara-inta |
| INTA, noticia: Cinco claves para optimizar la siembra de arroz (INTA Corrientes) (09/09/2019) | 8 | https://www.argentina.gob.ar/noticias/cinco-claves-para-optimizar-la-siembra-de-arroz |
| INTA, noticia: Inscriben una nueva variedad de avena multipropósito, Paloma INTA (13/02/2020) | 8 | https://www.argentina.gob.ar/noticias/inscriben-una-nueva-variedad-de-avena-multiproposito |
| INTA, noticia: Nuevos girasoles con más aceite y mejor rendimiento (06/08/2020) | 8 | https://www.argentina.gob.ar/noticias/nuevos-girasoles-con-mas-aceite-y-mejor-rendimiento |
| INTA, noticia: Presentan una nueva variedad de cebada cervecera, Verónica INTA (22/05/2025) | 8 | https://www.argentina.gob.ar/noticias/presentan-una-nueva-variedad-de-cebada-cervecera |
| INTA, noticia: Presentan una variedad de avena todo terreno, Pía INTA (08/01/2025) | 8 | https://www.argentina.gob.ar/noticias/presentan-una-variedad-de-avena-todo-terreno |
| No oficial (revista técnica): Bainotti C. (Mejoramiento de Trigo, INTA Marcos Juárez), «Dos nuevas variedades», Engormix (10/05/2008) | 8 | https://www.engormix.com/agricultura/siembra-trigo-cebada/argentina-dos-nuevas-variedades_n12536/ |
| No oficial (revista técnica): Giorda L.M. (INTA EEA Manfredi), «Nuevos híbridos forrajeros para pastoreo y silo», Engormix (08/05/2007) | 8 | https://www.engormix.com/ganaderia/sorgo-forrajero/nuevos-hibridos-forrajeros-pastoreo_a27106/ |
| No oficial (semillero licenciatario): Porosem SRL, ficha comercial de Leales 15 INTA (consultada 31/10/2026) | 8 | https://www.porosem.com.ar/semillas/leales-15-inta |
| No oficial (semillero licenciatario): Porosem SRL, ficha comercial de Leales 24 INTA (consultada 31/10/2026) | 8 | https://www.porosem.com.ar/semillas/leales-24-inta |
| Canteros F.H., Parrado J. y Aragón R.E. (INTA Famaillá / UNT), «Cuatero INTA, nuevo cultivar de maíz para el subtrópico argentino», Rev. Agron. Noroeste Argent. 41(2): 85-92 (2021) (PDF subido por Hernán el 31/10/2026) | 7 | https://repositorio.inta.gob.ar/xmlui/handle/20.500.12123/11219 |
| INTA / MAGyP, noticia: Investigadores del INTA obtuvieron un nuevo grano de arroz largo fino (Memby Porá INTA CL) (02/12/2020) | 7 | https://www.argentina.gob.ar/noticias/investigadores-del-inta-obtuvieron-un-nuevo-grano-de-arroz-largo-fino |
| INTA EEA Corrientes, Hoja Informativa N° 2, «El arroz argentino se renueva: Alfredo INTA y Vicente INTA» (28/11/2024) | 7 | https://www.argentina.gob.ar/noticias/hoja-informativa-no-2-inta-eea-corrientes-el-arroz-argentino-se-renueva-inta-corrientes |
| INTA, Catálogo de variedades: Poroto Cegro INTA (EEA Salta) | 7 | https://www.argentina.gob.ar/inta/relaciones-estrategicas-del-inta/poroto-cegro-inta |
| INTA, noticia: Alfalfa, desarrollan una variedad ideal para pastoreo directo (Maltén PV INTA) (25/09/2023) | 7 | https://www.argentina.gob.ar/noticias/alfalfa-desarrollan-una-variedad-ideal-para-pastoreo-directo |
| INTA, noticia: Lanzan híbrido de girasol con genes de resistencia a herbicidas (22/05/2019) | 7 | https://www.argentina.gob.ar/noticias/lanzan-hibrido-de-girasol-con-genes-de-resistencia-herbicidas |
| INTA, noticia: Presentan nuevas variedades de trigo pan con alto rendimiento y resistencia | 7 | https://www.argentina.gob.ar/noticias/presentan-nuevas-variedades-de-trigo-pan-con-alto-rendimiento-y-resistencia |
| Macro Seed (licenciatario de INTA), ficha del producto en macroseed.com.ar | 7 | https://www.macroseed.com.ar/productos/trigo/23 |
| Macro Seed (licenciatario de INTA), ficha del producto en macroseed.com.ar | 7 | https://www.macroseed.com.ar/productos/trigo/25 |
| Macro Seed (licenciatario de INTA), ficha del producto en macroseed.com.ar | 7 | https://www.macroseed.com.ar/productos/trigo/35 |
| Macro Seed (licenciatario de INTA), ficha del producto en macroseed.com.ar | 7 | https://www.macroseed.com.ar/productos/trigo/36 |
| Macro Seed (licenciatario de INTA), ficha del producto en macroseed.com.ar | 7 | https://www.macroseed.com.ar/productos/trigo/37 |
| Macro Seed (licenciatario de INTA), ficha del producto en macroseed.com.ar | 7 | https://www.macroseed.com.ar/productos/trigo/38 |
| No oficial (prensa que cita al INTA Marcos Juárez, G. Donaire): Infocampo (14/05/2025) | 7 | https://www.infocampo.com.ar/?p=578514 |
| No oficial (prensa): Todoagro, «Don Tomaso, el nuevo centeno multipropósito del INTA» (nota del INTA Bordenave, dic. 2021) | 7 | https://www.todoagro.com.ar/don-tomaso-el-nuevo-centeno-multiproposito-del-inta/ |
| No oficial (semillero licenciatario): Porosem SRL, ficha comercial de Leales 10 INTA (consultada 31/10/2026) | 7 | https://www.porosem.com.ar/semillas/leales-10-inta |
| No oficial (semillero licenciatario): Porosem SRL, ficha comercial de Leales 17 INTA (consultada 31/10/2026) | 7 | https://www.porosem.com.ar/semillas/leales-17-inta |
| No oficial (semillero licenciatario): Porosem SRL, ficha comercial de Leales 22 INTA (consultada 31/10/2026) | 7 | https://www.porosem.com.ar/semillas/leales-22-inta |
| Basigalup D.H. (INTA EEA Manfredi), «Presente y futuro en mejoramiento de alfalfa», 2007, publicado en Engormix | 6 | https://www.engormix.com/lecheria/manejo-alfalfa/presente-futuro-mejoramiento-alfalfa_a26970/ |
| INTA, noticia: El INTA desarrolló dos nuevos cultivares de colza | 6 | https://www.argentina.gob.ar/noticias/el-inta-desarrollo-dos-nuevos-cultivares-de-colza |
| INTA, noticia: Garbanzos, la importancia de elegir semilla certificada (INTA Salta) | 6 | https://www.argentina.gob.ar/noticias/garbanzos-la-importancia-de-elegir-semilla-certificada |
| INTA, noticia: INTA Paraná 6000, un cultivar de soja todo terreno | 6 | https://www.argentina.gob.ar/noticias/inta-parana-6000-un-cultivar-de-soja-todo-terreno |
| INTA, noticia: Lino, la fertilización como herramienta para mejorar el rendimiento (INTA Paraná) | 6 | https://www.argentina.gob.ar/noticias/lino-la-fertilizacion-como-herramienta-para-mejorar-el-rendimiento |
| INTA, noticia: Presentan una soja que tolera la falta de agua (Rosana INTA 3.9 STS) | 6 | https://www.argentina.gob.ar/noticias/presentan-una-soja-que-tolera-la-falta-de-agua |
| INTA, noticia: Presentan una variedad de algodón tolerante al estrés hídrico (Arandú) | 6 | https://www.argentina.gob.ar/noticias/presentan-una-variedad-de-algodon-tolerante-al-estres-hidrico |
| INTA, noticia: Soja, presentan variedad con alto potencial de rendimiento (Marina INTA 3.8 STS) | 6 | https://www.argentina.gob.ar/noticias/soja-presentan-variedad-con-alto-potencial-de-rendimiento |
| INTA, «El INTA lidera el mejoramiento genético de la papa» (entrevista a M.C. Bedogni, INTA Balcarce; 05/04/2023) | 6 | https://www.argentina.gob.ar/node/371532 |
| No oficial (prensa que cita al INTA Bordenave, obtentor J.C. Tomaso): Infocampo (11/03/2011) | 6 | https://www.infocampo.com.ar/?p=245192 |
| No oficial (prensa que cita al INTA Manfredi, J. Baldessari): Infocampo (07/03/2013) | 6 | https://www.infocampo.com.ar/?p=275214 |
| No oficial (prensa que publica el relevamiento del INTA Famaillá, Grupo Caña de Azúcar): La Gaceta (12/06/2026) | 6 | https://www.lagaceta.com.ar/nota/1140883/economia/canaverales-se-desacelero-ritmo-madurativo-pero-buen-nivel-acumulacion-general.html |
| No oficial (prensa): Diario de Cuyo, «Siembra de alfalfa: la época y las variedades convenientes» (17/04/2014; cita al INTA Manfredi) | 6 | https://www.diariodecuyo.com.ar/suplementos/Siembra-de-alfalfa-la-epoca-y-las-variedades-convenientes-20140417-0111.html |
| Universidad Nacional de La Pampa: Picca A. y col., «Producción de bioetanol a escala de laboratorio a partir de sorgo granífero», Semiárida 29(1):11-17 (2019), semilla cedida por INTA Manfredi | 6 | https://cerac.unlpam.edu.ar/index.php/semiarida/article/download/4046/4115/ |
| Alberdi B., Tacaliti M.S. y Tocho E. (CISaV-FCAyF UNLP, con material del INTA Bordenave), «Caracterización fenotípica del daño ocasionado por el pulgón verde de los cereales en variedades de triticale», Investigación Joven 9(2), 2022; escala visual de 1 (sin daño) a 9 (planta muerta) | 5 | https://sedici.unlp.edu.ar/handle/10915/150824 |
| Bedogni y Ceroli (INTA Balcarce - FCA UNMdP), Evaluación de parámetros de calidad postcosecha y rendimiento en genotipos de papa bajo estrés hídrico, Investigación Joven 10(2), UNLP (2023); resumen, sin cifras por variedad | 5 | https://sedici.unlp.edu.ar/handle/10915/166923 |
| Bodega J.L., Di Battista E., Róvere N. et al. (FCA-UNMdP / INTA Balcarce), «Comportamiento de variedades de lino oleaginoso en el sudeste de Buenos Aires», Rev. Fac. Agron. La Plata 122 (2023); siembras 10/07/2015, 17/07/2019 y 18/08/2020, secano | 5 | https://sedici.unlp.edu.ar/handle/10915/164161 |
| Fernández P. (INTA EEA Cesáreo Naredo), Evaluación de cultivares de alfalfa en el sudoeste bonaerense (Guaminí), Red Nacional de alfalfa 2018-2020 (2021) | 5 | https://repositorio.inta.gob.ar/handle/20.500.12123/9326 |
| Gallego y Neira (INTA EEA Valle Inferior), Resultados del comportamiento productivo de alfalfa en el Valle Inferior del Río Negro, período 2018-2024, Informa Nº 99 (2025) | 5 | https://repositorio.inta.gob.ar/handle/20.500.12123/21542 |
| Herber L.G. y Colazo J. (INTA C. del Uruguay), «Desempeño productivo y calidad industrial de Karandú INTA CL bajo fertilización nitrogenada», en Proyecto Arroz campaña 2025-26, EEA Corrientes (PDF subido por Hernán el 04/11/2026) | 5 | https://repositorio.inta.gob.ar/ |
| INTA Manfredi (Ing. Daniel Álvarez), «Girasol: inscriben nuevo híbrido con alto oleico», Engormix (22/11/2008) | 5 | https://www.engormix.com/agricultura/girasol-alto-oleico/argentina-girasol-inscriben-nuevo_n13799/ |
| INTA, Catálogo de variedades: Arveja Primogénita FCA-INTA | 5 | https://www.argentina.gob.ar/inta/relaciones-estrategicas-del-inta/arveja-primogenita-fca-inta |
| INTA, Catálogo de variedades: Girasol Chané CL INTA (EEA Manfredi) | 5 | https://www.argentina.gob.ar/inta/relaciones-estrategicas-del-inta/girasol-chane-inta |
| INTA, noticia: Alfalfa, nuevas variedades para distintos desafíos ganaderos (14/01/2026) | 5 | https://www.argentina.gob.ar/noticias/alfalfa-nuevas-variedades-para-distintos-desafios-ganaderos |
| INTA, noticia: Patagónica INTA, una cebada diseñada a la medida de la región (24/10/2023) | 5 | https://www.argentina.gob.ar/noticias/patagonica-inta-una-cebada-disenada-la-medida-de-las-necesidades-de-la-region-0 |
| INTA, noticia: Presentan dos nuevas variedades de arroz adaptadas a los sistemas productivos nacionales (06/11/2025) | 5 | https://www.argentina.gob.ar/noticias/presentan-dos-nuevas-variedades-de-arroz-adaptadas-los-sistemas-productivos-nacionales |
| INTA, noticia: Presentan una nueva variedad de avena, Liliana INTA (20/03/2025) | 5 | https://www.argentina.gob.ar/noticias/presentan-una-nueva-variedad-de-avena-0 |
| INTA, noticia: Presentan una variedad inédita de soja que resiste la roya asiática | 5 | https://www.argentina.gob.ar/noticias/presentan-una-variedad-inedita-de-soja-que-resiste-la-roya-asiatica |
| Molas, Torroba y Paccapelo (INTA EEA Anguil y UNLPam), Revista de Investigaciones Agropecuarias (INTA) 27(1):47-59, 1996; red de ensayos comparativos EEA Anguil (resumen reeditado por UNLPam) | 5 | https://cerac.unlpam.edu.ar/index.php/semiarida/article/download/4773/4893 |
| No oficial (prensa con nota del INTA Paraná, L. Gieco): Agrofy News (12/12/2016) | 5 | https://news.agrofy.com.ar/noticia/162657/presentan-primera-variedad-colza-pais |
| No oficial (prensa que cita a la Chacra Experimental Integrada Barrow, INTA-MDA, F. Di Pane): Infocampo (30/05/2016) | 5 | https://www.infocampo.com.ar/?p=350359 |
| No oficial (prensa que cita al INTA Bordenave): Agrofy News, «Cómo es la nueva cebada que presentó el INTA» (25/05/2021) | 5 | https://news.agrofy.com.ar/noticia/193827/como-es-nueva-cebada-que-presento-inta |
| No oficial (prensa que cita al INTA Bordenave): Infocampo, «El INTA presentó una nueva cebada para múltiples propósitos» (27/04/2017) | 5 | https://www.infocampo.com.ar/?p=368265 |
| No oficial (prensa que cita al INTA Bordenave): Infocampo, «Silera INTA: una cebada que produce forraje de calidad» (04/07/2016) | 5 | https://www.infocampo.com.ar/?p=351798 |
| No oficial (prensa que cita al INTA Bordenave, F. Giménez): Infocampo (18/06/2015) | 5 | https://www.infocampo.com.ar/?p=331871 |
| No oficial (revista técnica): Giorda L.M. (INTA EEA Manfredi), «Variedades e híbridos forrajeros en sorgo», Congreso Aapresid 2018, Engormix (15/09/2018) | 5 | https://www.engormix.com/agricultura/genetica-sorgo/variedades-hibridos-forrajeros-sorgo_a42668/ |
| Sardiña M.C. y col. (INTA EEA General Villegas), Evaluación de cultivares de alfalfa (Medicago sativa L.), ensayos implantados en 2012 y 2014, período 2014/15 | 5 | https://repositorio.inta.gob.ar/handle/20.500.12123/19622 |
| Basigalup (comp.), Investigación, producción e industrialización de la alfalfa en Argentina, Ediciones INTA 2022 (copia del libro aportada por Hernán) | 4 | https://repositorio.inta.gob.ar/handle/20.500.12123/18465 |
| Canteros F., Parrado J. y Aragón R.E. (INTA Famaillá / UNT), «Cuatero INTA, nuevo cultivar de maíz para el subtrópico argentino», Revista agronómica del noroeste argentino 41(2): 85-92 (2021), resumen en el repositorio del SICyT | 4 | https://repositoriosdigitales.sicyt.gob.ar/vufind/Record/INTADig_61bb878981422beab37a03cf7c1ca3da |
| Cicchino y col. (INTA AER Chascomús, EEA Cuenca del Salado), Sorgo: ensayo comparativo de rendimiento para silaje planta entera, campaña 2021/22 | 4 | https://repositorio.inta.gob.ar/handle/20.500.12123/19055 |
| Cicchino y col. (INTA AER Chascomús, EEA Cuenca del Salado), Sorgo: ensayo comparativo de rendimiento para silaje planta entera, campaña 2024/25 | 4 | https://repositorio.inta.gob.ar/handle/20.500.12123/22203 |
| Dillchneider, Guillot Giraudo, Funaro y col. (INTA EEA Anguil - UNLPam), Resultados ensayo comparativo de rendimientos de sorgos graníferos, forrajeros y sileros (2022/23) | 4 | https://repositorio.inta.gob.ar/handle/20.500.12123/15122 |
| González Alazard, Venanzi, Lauric y Mascaro (INTA AER Pigüé, AER Bahía Blanca, EEA Bordenave y Escuela Agropecuaria Nº 1 Goyena), Evaluación del comportamiento de verdeos de invierno en el partido de Saavedra, campaña 2024 | 4 | https://repositorio.inta.gob.ar/handle/20.500.12123/22684 |
| INTA EEA Corrientes, «Proyecto Arroz. Resultados Campaña 2017-2018» (ensayos regionales Corrientes y Santa Fe) | 4 | https://repositorio.inta.gob.ar/handle/20500.12123/17771 |
| INTA EEA Manfredi, Rosas B., Senn A., Ortiz D. y Maguire V., «Ensayo comparativo de rendimiento de híbridos de sorgo silero, campaña 2024-25» (PDF del repositorio INTA subido por Hernán el 31/10/2026) | 4 | https://repositorio.inta.gob.ar/xmlui/handle/20.500.12123/23264 |
| INTA, noticia: Evaluación de los daños post-heladas en germoplasma élite de caña de azúcar (Famaillá, julio 2024, -2 °C) | 4 | https://www.argentina.gob.ar/noticias/evaluacion-de-los-danos-post-heladas-en-germoplasma-elite-de-cana-de-azucar-saccharum-spp |
| INTA, noticia: Nueva variedad de trigo pan MS INTA MDA Bonaerense 625 | 4 | https://www.argentina.gob.ar/noticias/nueva-variedad-de-trigo-pan-ms-inta-mda-bonaerense-625 |
| INTA, noticia: Presentan una nueva variedad de maíz amarillo, ideal para hacer harina (15/08/2024) | 4 | https://www.argentina.gob.ar/noticias/presentan-una-nueva-variedad-de-maiz-amarillo-ideal-para-hacer-harina |
| INTA, «Presentan dos nuevas variedades de arroz adaptadas a los sistemas productivos nacionales» (Karandú INTA CL e Ivaté INTA CL; J. Colazo, INTA Concepción del Uruguay; 06/11/2025) | 4 | https://www.argentina.gob.ar/node/484343 |
| No oficial (prensa que cita al INTA Manfredi): Infocampo (02/01/2008) | 4 | https://www.infocampo.com.ar/?p=232540 |
| No oficial (prensa: Infocampo 27/04/2017, nota de Bioceres Semillas, licenciatario de las BioINTA) | 4 | https://www.infocampo.com.ar/bioceres-semillas-continua-incorporando-biotecnologia-al-cultivo-de-trigo/ |
| No oficial (revista técnica): Basigalup D. (INTA EEA General Villegas), «Evaluación en pastoreo de la productividad primaria y secundaria del cultivar de alfalfa ProINTA Carmina», Engormix (22/02/2010) | 4 | https://www.engormix.com/ganaderia/timpanismo/evaluacion-pastoreo-productividad-primaria_a28324/ |
| No oficial (revista técnica): Giorda L.M. y col. (INTA EEA Manfredi), «Programa de mejoramiento genético de sorgo», Engormix (16/05/2017) | 4 | https://www.engormix.com/agricultura/genetica-sorgo/programa-mejoramiento-genetico-sorgo_a41659/ |
| No oficial (revista técnica): Presello D. (INTA EEA Pergamino), condensado de Martínez, Llovet y Presello (2018) RTA 10(37), Engormix (24/03/2019) | 4 | https://www.engormix.com/agricultura/genetica-maiz/maiz-uso-variedades-polinizacion_a43474/ |
| Ortiz y Rosas (INTA EEA Manfredi), Ensayo comparativo de híbridos de sorgo para ensilaje, campaña 2021-22, Cartilla Digital Manfredi 2022/09 | 4 | https://repositorio.inta.gob.ar/handle/20.500.12123/12389 |
| Cavalieri (INTA EEA Las Breñas), Evaluación de cultivares de alfalfa en Las Breñas, Red Nacional de alfalfa, serie ALFA SR 2018, ciclo 2019/20 (2021) | 3 | https://repositorio.inta.gob.ar/handle/20.500.12123/8971 |
| Cavalieri y Borelli (INTA AER General Pinedo y EEA Las Breñas), Uso de la relación hoja/tallo como estimador de calidad en cultivares de alfalfa, comunicación RAPA (Red Nacional de alfalfa) | 3 | https://repositorio.inta.gob.ar/handle/20.500.12123/18953 |
| Donaire, Reartes y col. (INTA EEA Marcos Juárez), Evaluación de cultivares de centeno, campaña 2024 | 3 | https://repositorio.inta.gob.ar/handle/20.500.12123/21642 |
| Fariza, Heck, De Lucía y Blaszchik (INTA EEA Cerro Azul), Caracterización preliminar de cultivares comerciales de sorgo silero en Misiones, campaña 2016/17, Informe de Avance 8/2017 (13 cultivares) | 3 | https://core.ac.uk/download/479928074.pdf |
| Giorda L.M. et al. (INTA EEA Manfredi), «Programa de mejoramiento genético de sorgo» (texto institucional reproducido en Engormix; no oficial: reproducción web de un texto del INTA) | 3 | https://www.engormix.com/agricultura/genetica-sorgo/programa-mejoramiento-genetico-sorgo_a41659/ |
| INTA EEA Cerro Azul (Misiones), Evaluación agronómica de cultivares de sorgo granífero, campañas 2013/14 y 2014/15, Informe Técnico 101/2017 (7 cultivares) | 3 | https://core.ac.uk/download/479928075.pdf |
| INTA EEA Pergamino, Oyenard M.E., «Experiencia en el cultivo de mostaza en Chacabuco, campaña 2023» (resumen del repositorio INTA) | 3 | http://hdl.handle.net/20.500.12123/16696 |
| INTA, Oferta tecnológica: Cultivares de maní runner (INTA Manfredi) | 3 | https://www.argentina.gob.ar/inta/tecnologias/cultivares-de-mani-runner |
| INTA, noticia: Algodón, un cultivo prometedor para el noreste de San Luis | 3 | https://www.argentina.gob.ar/noticias/algodon-un-cultivo-prometedor-para-el-noreste-de-san-luis |
| INTA, noticia: Nueva variedad de trigo pan MS INTA MDA Bonaerense 324 | 3 | https://www.argentina.gob.ar/noticias/nueva-variedad-de-trigo-pan-ms-inta-mda-bonaerense-324 |
| INTA, noticia: Nueva variedad de trigo pan MS INTA MDA Bonaerense 423 | 3 | https://www.argentina.gob.ar/noticias/nueva-variedad-de-trigo-pan-ms-inta-mda-bonaerense-423 |
| INTA, noticia: Nueva variedad de trigo pan MS INTA MDA Bonaerense 526 | 3 | https://www.argentina.gob.ar/noticias/nueva-variedad-de-trigo-pan-ms-inta-mda-bonaerense-526 |
| INTA, noticia: presentación de Arandú INTA BGRR IMIcott (11/06/2026) | 3 | https://www.argentina.gob.ar/node/504223 |
| No oficial (actas de congreso, autores INTA EEA Paraná): Velazquez P.D. y Coll L., 3º Simposio Latino Americano de Canola, Atas e resumos, 2025, cap. 5.2.24 | 3 | https://slac.abrascanola.com.br/pt-br/anais |
| No oficial (prensa que cita al INTA Famaillá, AER Simoca): La Gaceta, «Buscan mejorar cultivos en Taco Ralo» | 3 | https://www.lagaceta.com.ar/nota/468726/rural/buscan-mejorar-cultivos-taco-ralo.html |
| No oficial (prensa: Bichos de Campo 14/01/2026, presentación del INTA de sus variedades) | 3 | https://bichosdecampo.com/resistencia-suelos-salinos-menor-riesgo-de-empaste-y-calidad-de-forraje-premium-el-inta-presento-tres-nuevas-variedades-de-alfalfa-para-distintos-desafios-ganaderos/ |
| No oficial (revista técnica): Presello D. (INTA EEA Pergamino), «Maíz: uso de variedades de polinización abierta», Engormix (2019), condensado de Martínez, Llovet y Presello, RTA 10(37), 2018 | 3 | https://www.engormix.com/agricultura/genetica-maiz/maiz-uso-variedades-polinizacion_a43474/ |
| Prieto G. y col. (INTA y otros), «Rendimiento de cultivares de arveja en diferentes ambientes de la República Argentina, campaña 2021/22», Para Mejorar la Producción 61, INTA EEA Oliveros 2022; handle no identificado | 3 | https://repositorio.inta.gob.ar/ |
| Red de ensayos de girasol INTA-ASAGIR 2000-2025, tablero HelioSelector (ASAGIR; S. Zuil), pestaña Adaptabilidad Finlay-Wilkinson, consultado 01/11/2026; rinde relativo calculado sobre los puntos del gráfico | 3 | https://sebazuil.shinyapps.io/app_girasol/ |
| Rosas y Ortiz (INTA EEA Manfredi), Ensayo comparativo de híbridos de sorgo granífero, campaña 2022-23, Cartilla Digital Manfredi 2023/06 | 3 | https://repositorio.inta.gob.ar/handle/20.500.12123/14879 |
| Sánchez Angonova P.A. (INTA EEA Hilario Ascasubi), Nuevas variedades de papa en el sudoeste bonaerense. Ensayo comparativo de rendimiento, campaña 2022-2023 | 3 | https://repositorio.inta.gob.ar/handle/20.500.12123/16704 |
| Brach y Lacelli (INTA EEA Reconquista), Ensayos de avenas en la EEA Reconquista, Voces y Ecos 43 (campaña 2020, muy seca; 3 fechas de siembra) | 2 | https://repositorio.inta.gob.ar/handle/20.500.12123/18323 |
| Bravo B. et al. 2024, INTA Información Técnica 201 'Ensayos agrícolas en la provincia de San Luis' (EEA San Luis y UNSL); handle no identificado | 2 | https://repositorio.inta.gob.ar/ |
| Cicchino y col. (INTA AER Chascomús, EEA Cuenca del Salado), Sorgo: ensayo comparativo de rendimiento para silaje planta entera, campaña 2020/21 | 2 | https://repositorio.inta.gob.ar/handle/20.500.12123/18977 |
| Donaire, Reartes y col. (INTA EEA Marcos Juárez), Evaluación de cultivares de centeno y cebada forrajera, campaña 2022 | 2 | https://repositorio.inta.gob.ar/handle/20.500.12123/14309 |
| INTA (Santa Cruz), «Establecimiento y producción de forraje de cereales de invierno en la Patagonia austral» (resumen del repositorio INTA) | 2 | http://hdl.handle.net/20.500.12123/11569 |
| INTA Bordenave y UBA, «Efecto de la variedad de centeno cultivado en la Argentina en el contenido de fibras y proteínas», 2019 (resumen del repositorio INTA) | 2 | http://hdl.handle.net/20.500.12123/11738 |
| INTA EEA Corrientes, Hoja Informativa N° 10, «Alfredo INTA y Vicente INTA, nitrógeno a medida» (ensayo Mercedes, Corrientes, 2024/25; 25/07/2025) | 2 | https://www.argentina.gob.ar/noticias/cultivo-de-arroz-alfredo-inta-y-vicente-inta-nitrogeno-medida-para-alcanzar-altos |
| INTA EEA Manfredi y EEA Santiago del Estero, «Evaluación de la virosis del achaparramiento de la alfalfa en dos ambientes contrastantes de Argentina», 2017 (resumen del repositorio INTA) | 2 | http://hdl.handle.net/20.500.12123/4618 |
| INTA EEA Manfredi, Ensayo comparativo de rendimiento de híbridos de sorgo silero, campaña 2020-21, Cartilla Digital Manfredi 2021/07 | 2 | https://repositorio.inta.gob.ar/handle/20.500.12123/10036 |
| INTA EEA Oliveros, «Red de cultivares comerciales de trigo del centro-sur de Santa Fe, campaña 2020-2021» (planilla xlsx); handle no identificado | 2 | https://repositorio.inta.gob.ar/ |
| INTA, evaluación de poblaciones de alfalfa SIMA frente a gorgojos, campañas 2008/09 y 2009/10 (resumen del repositorio INTA) | 2 | http://hdl.handle.net/20.500.12123/509 |
| INTA, noticia: Arandú, la genética que abre una nueva etapa para el algodón argentino | 2 | https://www.argentina.gob.ar/noticias/arandu-la-genetica-que-abre-una-nueva-etapa-para-el-algodon-argentino |
| INTA, noticia: El INTA desarrolla una nueva papa ideal para chips (Piru INTA) | 2 | https://www.argentina.gob.ar/noticias/el-inta-desarrolla-una-nueva-papa-ideal-para-chips |
| INTA, noticia: Kira INTA, el arroz que conquista los mercados premium del mundo (04/03/2026) | 2 | https://www.argentina.gob.ar/noticias/kira-inta-el-arroz-que-conquista-los-mercados-premium-del-mundo |
| INTA, noticia: Presentan la primera variedad de papa editada del país (OLI INTA) | 2 | https://www.argentina.gob.ar/noticias/presentan-la-primera-variedad-de-papa-editada-del-pais |
| INTA, noticia: Presentan una nueva variedad de arroz de alta calidad culinaria (Angiru INTA CL) (12/06/2024) | 2 | https://www.argentina.gob.ar/noticias/presentan-una-nueva-variedad-de-arroz-de-alta-calidad-culinaria |
| INTA, noticia: Se presentó la primera avena apta celíacos de la Argentina (18/10/2024) | 2 | https://www.argentina.gob.ar/noticias/se-presento-la-primera-avena-apta-celiacos-de-la-argentina |
| INTA, oferta tecnológica: Quinoa Chenopodium quinoa Willd: Morrillos INTA | 2 | https://www.argentina.gob.ar/node/427519 |
| INTA, «El INTA lidera el mejoramiento genético de colza» (Lucrecia Gieco) | 2 | https://www.argentina.gob.ar/noticias/el-inta-lidera-el-mejoramiento-genetico-de-colza |
| INTA, «El INTA lidera el mejoramiento genético de la papa» (cita a M. C. Bedogni, INTA Balcarce) | 2 | https://www.argentina.gob.ar/node/371532 |
| Melilli, Tellería, Conti y otros (INTA Junín - UNNOBA), Evaluación de cultivares de cebada cervecera en Junín, campaña 2020, Informe Técnico junio 2021 | 2 | https://repositorio.inta.gob.ar/handle/20.500.12123/9879 |
| Milisich H. (INTA Paraná), «BioInta 3006, la espiga de oro», Infocampo (14/06/2012; no oficial: prensa que cita al obtentor del INTA) | 2 | https://www.infocampo.com.ar/?p=258565 |
| No oficial (prensa que cita al INTA Añatuya): Bichos de Campo (11/03/2022) | 2 | https://bichosdecampo.com/?p=95746 |
| No oficial (prensa que cita al INTA Cerrillos, S. García Medina y A. Fekete): Infocampo (10/05/2011) | 2 | https://www.infocampo.com.ar/?p=246208 |
| No oficial (prensa que cita al INTA Manfredi, obtentor J. Baldessari): Infocampo (19/05/2016) | 2 | https://www.infocampo.com.ar/?p=349993 |
| No oficial (prensa): Diario de Cuyo, «La quinua en San Juan tiene rindes de hasta 1.250 kg/ha» (15/09/2017; INTA San Juan, Red Quinua). Figura como «Los Hornillos», antes de su inscripción en 2019: se asume que es el mismo material por el nombre | 2 | https://www.diariodecuyo.com.ar/suplementos/La-quinua-en-San-Juan-tiene-rindes-de-hasta-1-250-kg-ha-20170915-0100.html |
| No oficial (prensa, nota del INTA Salta): Infocampo, «INTA Salta: trabajo continuo en porotos alubias con calidad de exportación» (31/08/2020) | 2 | https://www.infocampo.com.ar/inta-salta-trabajo-continuo-en-porotos-alubias-con-calidad-de-exportacion/ |
| Red de ensayos de girasol INTA-ASAGIR 2000-2025, tablero HelioSelector (ASAGIR; S. Zuil), pestaña Adaptabilidad Finlay-Wilkinson, consultado 31/10/2026; rinde relativo calculado sobre los puntos del gráfico | 2 | https://sebazuil.shinyapps.io/app_girasol/ |
| Tagliotti, Giuliano, Puricelli, Zambelli y Bedogni (INTA Balcarce - UNMdP), Differential behavior to drought of two elite potato cultivars grown in southeastern pampean region of Argentina, Potato Journal 50(2):113-122 (2023) | 2 | https://repositorio.inta.gob.ar/handle/20.500.12123/20593 |
| Bichos de Campo, nota sobre el lanzamiento INTA Manfredi-Palo Verde con Arolfo, Odorizzi y Cornacchione (INTA) (14/01/2026) | 1 | https://bichosdecampo.com/resistencia-suelos-salinos-menor-riesgo-de-empaste-y-calidad-de-forraje-premium-el-inta-presento-tres-nuevas-variedades-de-alfalfa-para-distintos-desafios-ganaderos/ |
| CONICET/INTA, ensayo de tolerancia a la alcalinidad y a la deficiencia de hierro en 8 genotipos de sorgo (resumen del repositorio INTA) | 1 | http://hdl.handle.net/20.500.12123/3661 |
| Giorda L.M. et al. (INTA EEA Manfredi), «Nuevos desarrollos: híbridos y variedades de sorgo granífero y forrajero» (Engormix; no oficial: reproducción web de un texto del INTA), ensayos Manfredi 2014/15-2016/17 | 1 | https://www.engormix.com/agricultura/sorgo-granifero/nuevos-desarrollos-hibridos-variedades_a41376/ |
| INTA EEA Anguil, Dillchneider A. y col., «Resultados ensayo comparativo de rendimiento de sorgos graníferos, forrajeros y sileros 2022/23», Tabla 6 (PDF del repositorio INTA subido por Hernán el 31/10/2026) | 1 | https://repositorio.inta.gob.ar/bitstream/handle/20.500.12123/15122 |
| INTA EEA Barrow, Larsen A.O. y col., nota de trigo candeal 2015 (resumen del repositorio INTA) | 1 | http://hdl.handle.net/20.500.12123/3256 |
| INTA EEA Concepción del Uruguay (AER Gualeguaychú), Gorelik Zonis Y.G. y col., «Evaluación de especies y cultivares de verdeos de invierno para silaje de planta entera», 2025 (resumen del repositorio INTA) | 1 | http://hdl.handle.net/20.500.12123/26229 |
| INTA EEA Manfredi, Vigliano, Baldessari y col., composición química del grano de maní según genotipo y ambiente (resumen del repositorio INTA) | 1 | http://hdl.handle.net/20.500.12123/27582 |
| INTA EEA Montecarlo, Evaluación de cultivares de sorgo en la Provincia de Misiones, campaña 2025/26 | 1 | https://repositorio.inta.gob.ar/handle/20.500.12123/27608 |
| INTA EEA Pergamino y FAUBA, Menes, Galizia, Presello y col., «Mejoramiento de la capacidad de establecimiento en maíz», 2° Simposio de Mejoramiento Genético Vegetal, 2023 (resumen del repositorio INTA) | 1 | http://hdl.handle.net/20.500.12123/18513 |
| INTA EEA San Pedro, Pángaro, Taibo y Paunero, «Cocinemos con mostaza», 2012 (resumen del repositorio INTA) | 1 | http://hdl.handle.net/20.500.12123/17824 |
| INTA, biofortificación con selenio de alfalfa ProINTA Super Monarca GR9, 2025 (resumen del repositorio INTA) | 1 | http://hdl.handle.net/20.500.12123/21517 |
| INTA, capítulo «Evaluación de cultivares y panorama varietal» (libro de alfalfa INTA, 2022; resumen del repositorio INTA) | 1 | http://hdl.handle.net/20.500.12123/18718 |
| INTA, ensayos 1996-1999 de curvas estacionales de forraje de 15 gramíneas y leguminosas (resumen del repositorio INTA) | 1 | http://hdl.handle.net/20.500.12123/10855 |
| INTA, noticia: Con mejoramiento genético amplían la tolerancia al anegamiento de la alfalfa (19/02/2026) | 1 | https://www.argentina.gob.ar/noticias/con-mejoramiento-genetico-amplian-la-tolerancia-al-anegamiento-de-la-alfalfa |
| INTA, noticia: La Cooperativa Agrícola Avellaneda comenzó a comercializar semilla de alfalfa certificada (26/06/2026) | 1 | https://www.argentina.gob.ar/noticias/la-cooperativa-agricola-avellaneda-comenzo-comercializar-semilla-de-alfalfa-certificada |
| INTA, «Presentan dos nuevas variedades de arroz adaptadas a los sistemas productivos nacionales» (06/11/2025) | 1 | https://www.argentina.gob.ar/node/484343 |
| Iacopini, Carassai y Picco (INTA EEA Rafaela), Ensayo comparativo de rendimiento de sorgo para silaje, campaña 2024/25 | 1 | https://repositorio.inta.gob.ar/handle/20.500.12123/24276 |
| No oficial (prensa que cita a la Chacra Experimental Integrada Barrow, INTA-MDA, N. Rodríguez): Bichos de Campo (19/04/2026) | 1 | https://bichosdecampo.com/luego-de-17-anos-lola-asoma-cabeza-los-detalles-de-la-nueva-avena-del-inta-barrow-que-promete-mas-pasto-y-mejores-rindes-pero-a-la-vez-ser-implacable-con-la-roya/ |
| No oficial (prensa que cita al INTA Bordenave): Bichos de Campo (22/05/2025) | 1 | https://bichosdecampo.com/?p=228341 |
| No oficial (prensa que cita al INTA El Colorado, obtentor Arsenio Aguinaga): La Nación (19/08/2024) | 1 | https://www.lanacion.com.ar/economia/campo/apto-para-celiacos-desarrollaron-una-nueva-variedad-de-maiz-amarillo-ideal-para-hacer-harina-nid19082024/ |
| No oficial (prensa): Agritotal, «Amapola INTA, la nueva variedad de avena blanca» (19/08/2025, sobre el Boletín Oficial) | 1 | https://www.agritotal.com/nota/amapola-inta-la-nueva-variedad-de-avena-blanca/ |
| No oficial (prensa): Agroperfiles, «El INTA presentó en Expoagro la variedad extralarga Alhue» (INTA Sáenz Peña, 2026) | 1 | https://agroperfiles.com.ar/el-inta-presento-en-expoagro-la-variedad-extralarga-alue/ |
| Royo y Brach (INTA EEA Reconquista), Producción y calidad nutricional de avenas en la cadena forrajera, Voces y Ecos 37 (campaña 2016) | 1 | https://repositorio.inta.gob.ar/handle/20.500.12123/3482 |
| Veneciano (INTA EEA San Luis) y Cerdá (UNSL), revista Semiárida (UNLPam) | 1 | https://cerac.unlpam.edu.ar/index.php/semiarida/article/view/4936 |
| Veneciano, Funes (INTA EEA San Luis) y Corral (UNSL), revista Semiárida (UNLPam) | 1 | https://cerac.unlpam.edu.ar/index.php/semiarida/article/view/4935 |

### INASE (1790 datos)

| Fuente | Datos | Link |
|---|---:|---|
| INASE, Catálogo Nacional de Cultivares (28/10/2026): ficha básica del registro, sin datos de ensayo publicados | 1388 | https://www.argentina.gob.ar/inase |
| INASE, descripciones morfológicas de soja (declaradas al inscribir) | 215 | https://www.argentina.gob.ar/sites/default/files/descripciones_morfologicas_soja_24-06-2026.xlsx |
| INTA EEA Marcos Juárez, comportamiento sanitario de variedades de trigo 2024-25 (Red INASE) | 30 | https://www.argentina.gob.ar/sites/default/files/2025/04/inta_crcordoba_eeamarcosjuarez_alberione_e_comportamiento.pdf |
| INASE, Comité de Cereales de Invierno: grupos de calidad de trigo pan (2025) | 24 | https://www.argentina.gob.ar/inase/red-de-ensayos-comparativos-de-variedades-de-trigo/grupo-de-calidad-de-trigo-pan |
| INASE, Catálogo Nacional de Cultivares (28/10/2026), campo características | 23 | https://www.argentina.gob.ar/inase |
| INASE, Comité de Cereales de Invierno: grupos de calidad de trigo pan (2018) | 18 | https://www.argentina.gob.ar/inase/red-de-ensayos-comparativos-de-variedades-de-trigo/grupo-de-calidad-de-trigo-pan |
| INTA EEA Anguil, Cereales invernales campaña 2021, Tablas 1-4: RET-INASE Anguil 2021-2022 (misma subregión triguera que el este de San Luis) | 18 | https://repositorio.inta.gob.ar/handle/20.500.12123/11873 |
| Alberione, Campos, Couretot y Schutt (INTA EEAs Marcos Juárez, Bordenave, Pergamino y Paraná), Comportamiento sanitario de variedades de trigo, campaña 2019-20, Cuadro 1 (fuente INASE-RET e INTA) | 14 | https://core.ac.uk/download/427482442.pdf |
| Franco, Molina Favero, Cabral Farías y Besteiro (INTA Balcarce), Segundo informe sanitario de la RET-INASE de INTA Balcarce al 20-nov-2025, Boletín Técnico INTA Balcarce vol. 17 | 14 | https://repositorio.inta.gob.ar/handle/20.500.12123/24612 |
| González, Lauric, Giménez y González (INTA EEA Bordenave), Alcance e impacto de la genética de avena desarrollada por INTA Bordenave, Informe Técnico, octubre 2026 (datos de semilla fiscalizada INASE 2025/26) | 12 | https://repositorio.inta.gob.ar/handle/20.500.12123/28084 |
| INASE, Comité de Cereales de Invierno: grupos de calidad de trigo pan (2019) | 8 | https://www.argentina.gob.ar/inase/red-de-ensayos-comparativos-de-variedades-de-trigo/grupo-de-calidad-de-trigo-pan |
| INASE, Comité de Cereales de Invierno: grupos de calidad de trigo pan (2024) | 8 | https://www.argentina.gob.ar/inase/red-de-ensayos-comparativos-de-variedades-de-trigo/grupo-de-calidad-de-trigo-pan |
| No oficial (prensa que cita la presentación del INTA ante INASE, Res. 145/2021): Agrofy News (15/04/2021) | 5 | https://news.agrofy.com.ar/noticia/193142/inta-registro-nuevas-variedades-semillas-avena-y-centeno |
| INASE, Comité de Cereales de Invierno: grupos de calidad de trigo pan (2012) | 4 | https://www.argentina.gob.ar/inase/red-de-ensayos-comparativos-de-variedades-de-trigo/grupo-de-calidad-de-trigo-pan |
| No oficial (prensa: Agrofy News 23/06/2021, cita la presentación del INTA al INASE) | 3 | https://news.agrofy.com.ar/noticia/194352/inta-apuesta-produccion-organica-y-desarrollo-maiz-buena-respuesta-enfermedades-hoja |
| Arolfo y Odorizzi (INTA EEA Manfredi), cap. 8 en Basigalup (comp.), Ediciones INTA 2022, Tabla 1 (grupos de reposo invernal y testigos INASE) | 2 | https://repositorio.inta.gob.ar/handle/20.500.12123/18718 |
| INASE, Comité de Cereales de Invierno: grupos de calidad de trigo pan (2020) | 2 | https://www.argentina.gob.ar/inase/red-de-ensayos-comparativos-de-variedades-de-trigo/grupo-de-calidad-de-trigo-pan |
| No oficial (prensa que cita al INTA y a INASE): Bichos de Campo (23/06/2026) | 1 | https://bichosdecampo.com/papa-aguantadora-se-aprobo-una-variedad-del-tuberculo-desarrollada-por-el-inta-que-no-se-mancha-por-los-golpes/ |
| No oficial (prensa): Puntobiz, «El INTA logró registrar nuevas variedades de centeno y avena» (Res. INASE 145/2021, 15/04/2021) | 1 | https://puntobiz.com.ar/agro/2021-4-15-9-39-0-el-inta-logro-registrar-nuevas-variedades-de-centeno-y-avena |

### USDA GRIN-Global (EE.UU.) (177 datos)

| Fuente | Datos | Link |
|---|---:|---|
| USDA-ARS GRIN-Global, accesión PI 378893 (medido por el USDA en EE.UU., no en Argentina) | 19 | https://npgsweb.ars-grin.gov/gringlobal/accessiondetail?id=1283850 |
| USDA-ARS GRIN-Global, accesión PI 378895 (medido por el USDA en EE.UU., no en Argentina) | 19 | https://npgsweb.ars-grin.gov/gringlobal/accessiondetail?id=1283852 |
| USDA-ARS GRIN-Global, accesión PI 378896 (medido por el USDA en EE.UU., no en Argentina) | 18 | https://npgsweb.ars-grin.gov/gringlobal/accessiondetail?id=1283853 |
| USDA-ARS GRIN-Global, accesión PI 378894 (medido por el USDA en EE.UU., no en Argentina) | 17 | https://npgsweb.ars-grin.gov/gringlobal/accessiondetail?id=1283851 |
| USDA-ARS GRIN-Global, accesión PI 650541 (medido por el USDA en EE.UU., no en Argentina) | 14 | https://npgsweb.ars-grin.gov/gringlobal/accessiondetail?id=1024777 |
| USDA-ARS GRIN-Global, accesión PI 468067 (medido por el USDA en EE.UU., no en Argentina) | 8 | https://npgsweb.ars-grin.gov/gringlobal/accessiondetail?id=1363003 |
| USDA-ARS GRIN-Global, accesión PI 468068 (medido por el USDA en EE.UU., no en Argentina) | 8 | https://npgsweb.ars-grin.gov/gringlobal/accessiondetail?id=1363004 |
| USDA-ARS GRIN-Global, accesión PI 468070 (medido por el USDA en EE.UU., no en Argentina) | 8 | https://npgsweb.ars-grin.gov/gringlobal/accessiondetail?id=1363006 |
| USDA-ARS GRIN-Global, accesión PI 468071 (medido por el USDA en EE.UU., no en Argentina) | 8 | https://npgsweb.ars-grin.gov/gringlobal/accessiondetail?id=1363007 |
| USDA-ARS GRIN-Global, accesión PI 494091 (medido por el USDA en EE.UU., no en Argentina) | 8 | https://npgsweb.ars-grin.gov/gringlobal/accessiondetail?id=1389027 |
| USDA-ARS GRIN-Global, accesión PI 494092 (medido por el USDA en EE.UU., no en Argentina) | 8 | https://npgsweb.ars-grin.gov/gringlobal/accessiondetail?id=1389028 |
| USDA-ARS GRIN-Global, accesión PI 598141 (medido por el USDA en EE.UU., no en Argentina) | 7 | https://npgsweb.ars-grin.gov/gringlobal/accessiondetail?id=1545626 |
| USDA-ARS GRIN-Global, accesión PI 598174 (medido por el USDA en EE.UU., no en Argentina) | 7 | https://npgsweb.ars-grin.gov/gringlobal/accessiondetail?id=1545659 |
| USDA-ARS GRIN-Global, accesión PI 534951 (medido por el USDA en EE.UU., no en Argentina) | 6 | https://npgsweb.ars-grin.gov/gringlobal/accessiondetail?id=1429887 |
| USDA-ARS GRIN-Global, accesión PI 534958 (medido por el USDA en EE.UU., no en Argentina) | 6 | https://npgsweb.ars-grin.gov/gringlobal/accessiondetail?id=1429894 |
| USDA-ARS GRIN-Global, accesión PI 535182 (medido por el USDA en EE.UU., no en Argentina) | 6 | https://npgsweb.ars-grin.gov/gringlobal/accessiondetail?id=1430118 |
| USDA-ARS GRIN-Global, accesión PI 535193 (medido por el USDA en EE.UU., no en Argentina) | 6 | https://npgsweb.ars-grin.gov/gringlobal/accessiondetail?id=1430129 |
| USDA-ARS GRIN-Global, accesión PI 650796 (medido por el USDA en EE.UU., no en Argentina) | 4 | https://npgsweb.ars-grin.gov/gringlobal/accessiondetail?id=1490530 |

### Universidades nacionales (41 datos)

| Fuente | Datos | Link |
|---|---:|---|
| Toha C.G. (FCAyF-UNLP; dir. M.R. Simon, co-dir. J.I. Dietz), «Rendimiento y sanidad de líneas y cultivares de avena», Trabajo final de carrera, 2016; EE J. Hirschhorn, Los Hornos (La Plata), 13 variedades comerciales y 7 líneas | 10 | https://sedici.unlp.edu.ar/handle/10915/58447 |
| Ferrero A.R., García P.A. y Balbi C.N. (Cátedra de Cultivos 1, FCA-UNNE), «Rendimiento de cultivares de linos oleaginosos en dos series de suelos del noroeste de Corrientes», Revista de Ciencias Agrarias UNNE, siembra 15-20/06, 1993-1995, 800 semillas/m² | 8 | https://revistas.unne.edu.ar/index.php/agr/article/view/491 |
| Bozzani H.F. (2016) Trabajo final, FCAyF-UNLP, ensayo de 20 genotipos de avena, EE J. Hirschhorn, Los Hornos (La Plata), campaña 2015 | 7 | https://sedici.unlp.edu.ar/handle/10915/56090 |
| Cardelli M.G. (FCAyF-UNLP), «Biomasa y rendimiento en grano de diversos cultivares y líneas de avena», Trabajo final, 2014; ensayo en La Plata con 3 cortes, 5 variedades comerciales y 6 líneas | 5 | https://sedici.unlp.edu.ar/handle/10915/70617 |
| Dietz (UNLP), Determinación del período crítico y requerimientos de fotoperíodo y vernalización en avena, tesis doctoral FCAyF-UNLP (2021) | 5 | https://sedici.unlp.edu.ar/handle/10915/116959 |
| UNLP, tesis de maestría de Bustos Painii R.D. (dir. Yanniccari, Giménez y otros), «Sensibilidad de cultivares de avena a herbicidas inhibidores de la ALS/AHAS», 2019 (resumen en SEDICI) | 2 | https://repositoriosdigitales.sicyt.gob.ar/vufind/Record/SEDICI_ca3268f02f6df081e16b5b900acaa8df |
| Ayoub y otros (Facultad de Ciencias Agropecuarias, UNC), Respuesta del cultivo garbanzo a la inoculación con Mesorhizobium ciceri, Nexo Agropecuario | 1 | https://revistas.unc.edu.ar/index.php/nexoagro/article/download/36965/38391/139966 |
| Jecke F.A. (FCAyF-UNLP; dir. M.R. Simón), «Caracterización de nuevos aislados de Drechslera tritici-repentis y su efecto sobre el comportamiento de cultivares de trigo», Tesis de maestría | 1 | https://sedici.unlp.edu.ar/handle/10915/66478 |
| UNLP, tesis de grado de Da Silva L.V. (dir. Simón y Dietz), «Requerimientos de vernalización y fotoperiodo en genotipos argentinos de avena», 2019 (resumen en SEDICI) | 1 | https://repositoriosdigitales.sicyt.gob.ar/vufind/Record/SEDICI_c54e7ba5f187e3c35e948ddece9a86ff |
| Uranga J.P. (FCAyF-UNLP; dir. M.R. Simón), «Resistencia a la mancha de la hoja en cultivares argentinos de trigo en comparación con líneas diferenciales de resistencia al patógeno», Trabajo final de carrera, 18/11/2013; ensayos a campo y en maceta | 1 | https://sedici.unlp.edu.ar/handle/10915/67705 |

### EEAOC (Tucumán) (13 datos)

| Fuente | Datos | Link |
|---|---:|---|
| No oficial (revista técnica de la EEAOC, ente público de Tucumán): Vizgarra O.N. y col., «TUC 450: primera variedad de garbanzo tipo Desi para la región del Noroeste Argentino», Rev. Ind. y Agríc. de Tucumán 96(2):31-36 (2019) | 7 | https://www.eeaoc.gob.ar/ |
| Vizgarra O.N. et al. (EEAOC, 2017) TUC 403 y TUC 464, dos nuevas variedades de garbanzo Kabuli para el NOA. Rev. ind. agríc. Tucumán 94(1) | 6 | https://www.scielo.org.ar/scielo.php?script=sci_arttext&pid=S1851-30182017000100005 |

### Otras (marcadas) (9 datos)

| Fuente | Datos | Link |
|---|---:|---|
| UNNE (FCA), Ferrero, García y Balbi, «Rendimiento de cultivares de linos oleaginosos en dos series de suelos del noroeste de Corrientes», Agrotecnia 4, 1998 | 3 | https://repositoriosdigitales.sicyt.gob.ar/vufind/Record/RIUNNE_703d578840437469845712a5ce193ea8 |
| No oficial (prensa): Infosudoeste, «Trigo candeal: un nicho donde la calidad no se negocia» (CEI Barrow, 24/04/2026) | 2 | https://infosudoeste.com.ar/2026/04/24/trigo-candeal-un-nicho-donde-la-calidad-no-se-negocia/ |
| No oficial (empresa): AgroSpray, «Cultivo de arroz: guía completa» | 1 | https://agrospray.com.ar/blog/cultivo-de-arroz/ |
| No oficial (prensa agropecuaria): Agroempresario, «Lens culinaris» (nota técnica sobre el cultivo en Argentina) | 1 | https://agroempresario.com/publicacion/28073/lens-culinaris/?cat=2260001 |
| UBA (Facultad de Farmacia y Bioquímica), tesis de Gómez Castro M.L., «Revalorización del grano de centeno cultivado en la provincia de Buenos Aires» (resumen en el repositorio UBA) | 1 | https://repositoriosdigitales.sicyt.gob.ar/vufind/Record/RDIUBA_2f1db14fff481780b91d77e003a83d45 |
| UNRN, tesis de grado de Isaja M., «Evaluación preliminar del rendimiento de dos variedades de mostaza blanca», 2021 (Comarca Andina del Paralelo 42°) | 1 | https://repositoriosdigitales.sicyt.gob.ar/vufind/Record/RIDUNRN_585c8fec12e4fe434766700ebe3d0bc7 |

## Anexo B. Manejo por cultivo (109 fuentes distintas)

### INTA (154 datos)

| Fuente | Datos | Link |
|---|---:|---|
| INTA EEA Bordenave, Mijo y Moha: generalidades, producción y calidad (Bolletta, Venanzi, Krüger, Lagrange y Larrea, abril 2009; copia en produccion-animal.com.ar) | 9 | https://www.produccion-animal.com.ar/produccion_y_manejo_pasturas/pasturas%20artificiales/182-Mijo_y_Moha.pdf |
| INTA EEA Manfredi, Pedelini y Monetti: Maní, guía práctica para su cultivo (Boletín de divulgación técnica N° 2, 7ª ed., 2022) | 8 | https://repositorio.inta.gob.ar/bitstream/handle/20.500.12123/12519/INTA_CRCordoba_EEAManfredi_Pedelini_R_Mani_guia_practica_para_su_cultivo.pdf |
| INTA Pergamino, AER Chacabuco: Experiencia en el cultivo de mostaza blanca Delfina INTA en Chacabuco | 7 | https://www.argentina.gob.ar/sites/default/files/2024/01/inta_crbsasnorte_eeapergamino_experiencia_en_el_cultivo_de_mostaza_en_chacabuco.pdf |
| INTA San Luis, noticia: Soja, claves para maximizar rendimientos en ambientes semiáridos (07/10/2025) | 6 | https://www.argentina.gob.ar/noticias/soja-claves-para-maximizar-rendimientos-en-ambientes-semiaridos |
| INTA Las Breñas, noticia: Girasol, pautas para una campaña con alto potencial (08/07/2025) | 5 | https://www.argentina.gob.ar/noticias/girasol-pautas-para-una-campana-con-alto-potencial |
| INTA Marcos Juárez, noticia: Trigo, cómo planificar una estrategia de siembra eficiente (03/06/2019) | 5 | https://www.argentina.gob.ar/noticias/trigo-como-planificar-una-estrategia-de-siembra-eficiente |
| INTA Villa Dolores, noticia: En Traslasierra, incorporan riego por goteo subterráneo en papa | 5 | https://www.argentina.gob.ar/noticias/en-traslasierra-incorporan-riego-por-goteo-subterraneo-en-papa |
| INTA Arroyo Seco, noticia: Arvejas, una alternativa rentable en la rotación de cultivos (G. Prieto) | 4 | https://www.argentina.gob.ar/noticias/arvejas-una-alternativa-rentable-en-la-rotacion-de-cultivos |
| INTA Famaillá, póster: Cáñamo industrial en Tucumán, primeros avances de la Red de Ensayos del INTA | 4 | https://www.argentina.gob.ar/sites/default/files/2025/05/poster_canamo_congreso_internacional.pdf |
| INTA Pergamino y San Antonio de Areco, RTA: Evaluación de fuentes nitrógeno-azufradas en carinata (Jecke, Ferraris y otros) | 4 | https://www.argentina.gob.ar/sites/default/files/2024/06/02.pdf |
| INTA Quines y EEA San Luis con la UNSL, noticia: Algodón, un cultivo prometedor para el noreste de San Luis | 4 | https://www.argentina.gob.ar/noticias/algodon-un-cultivo-prometedor-para-el-noreste-de-san-luis |
| INTA San Luis, noticia: El sorgo demuestra su potencial productivo en el centro de San Luis (16/09/2026) | 4 | https://www.argentina.gob.ar/noticias/el-sorgo-demuestra-su-potencial-productivo-en-el-centro-de-san-luis |
| INTA San Luis, noticia: Evolución y perspectivas del girasol en San Luis (23/04/2025) | 4 | https://www.argentina.gob.ar/noticias/evolucion-y-perspectivas-del-girasol-en-san-luis |
| UNR, CONICET e INTA Oliveros, Bermejo y otros, Aplicación de diferentes metodologías en el mejoramiento de lenteja (Lens culinaris Medik), J. Basic Appl. Genet. 32(2), 2021 | 4 | https://www.scielo.org.ar/scielo.php?script=sci_arttext&pid=S1852-62332021000300033 |
| INTA Famaillá, noticia: El INTA desarrolló dos nuevas variedades de caña de azúcar | 3 | https://www.argentina.gob.ar/noticias/el-inta-desarrollo-dos-nuevas-variedades-de-cana-de-azucar |
| INTA Las Breñas, noticia: Sembrar soja en febrero puede reducir hasta 38 % de rendimiento (Red de Soja NEA) | 3 | https://www.argentina.gob.ar/noticias/sembrar-soja-en-febrero-puede-reducir-hasta-38-de-rendimiento |
| INTA San Luis, noticia: San Luis, incorporan centeno para controlar la erosión | 3 | https://www.argentina.gob.ar/noticias/san-luis-incorporan-centeno-para-controlar-la-erosion |
| INTA San Luis, noticia: San Luis, incorporan centeno para controlar la erosión (02/12/2025) | 3 | https://www.argentina.gob.ar/noticias/san-luis-incorporan-centeno-para-controlar-la-erosion |
| INTA AER Chivilcoy, noticia: La elección del híbrido puede modificar la respuesta del girasol a la fecha de siembra | 2 | https://www.argentina.gob.ar/noticias/la-eleccion-del-hibrido-puede-modificar-la-respuesta-del-girasol-la-fecha-de-siembra |
| INTA Anguil, noticia: Estudian estrategias de manejo para mejorar la alfalfa (01/07/2025) | 2 | https://www.argentina.gob.ar/noticias/estudian-estrategias-de-manejo-para-mejorar-la-alfalfa |
| INTA Bordenave, noticia: Triticale, una especie en expansión con dos nuevos cultivares desarrollados por el INTA | 2 | https://www.argentina.gob.ar/noticias/triticale-una-especie-en-expansion-con-dos-nuevos-cultivares-desarrollados-por-el-inta |
| INTA EEA Anguil, Corró Molas A.: Ensayos comparativos de rendimiento de maíz 2020-2021 | 2 | https://repositorio.inta.gob.ar/xmlui/bitstream/handle/20.500.12123/9996/INTA_CRLaPampa-SanLuis_EEAAnguil_CorroMolas_A._Ensayos_Comparativos_de_Rendimiento_de_Ma%C3%ADz_2020_2021.pdf |
| INTA EEA Anguil, Dillchneider A.: Ensayos comparativos de sorgos graníferos, forrajeros y sileros, campaña 2023-2024 | 2 | https://repositorio.inta.gob.ar/bitstream/handle/20.500.12123/18094/INTA_CR_LaPampa-SanLuis_EEAAnguil_Dillchneider_A._Ensayos%20comparativos%20de%20rendimientos%20de%20sorgos%20graniferos,%20forrajeros%20y%20sileros.%20Campa%C3%B1a%202023-2024.pdf?sequence=4&isAllowed=y |
| INTA EEA Anguil, Porta Siota F.: Variación del rendimiento según fechas de siembra en variedades de trigo en La Pampa (2021) | 2 | https://repositorio.inta.gob.ar/xmlui/bitstream/handle/20.500.12123/12039/INTA_CRLaPampa-SanLuis_EEAAnguil_PortaSiota_F._Variaci%C3%B3n%20del%20rendimiento%20seg%C3%BAn%20distintas%20fechas%20de%20siembra%20en%20variedades%20de%20trigo%20en%20La%20Pampa%20.pdf?sequence=1&isAllowed=y |
| INTA EEA Bordenave, Moreyra F. y otros: Verdeos de invierno | 2 | https://repositorio.inta.gob.ar/xmlui/bitstream/handle/20.500.12123/15508/INTA_CRBuenosAiresSur_EEABordenave_Moreyra_F_Verdeos_Invierno.pdf?sequence=1&isAllowed=y |
| INTA EEA Corrientes y FCA-UNNE (Grancic, Rey Montoya y Paredes), Cultivos de cobertura y efectos en las propiedades físicas en un Argiudol ácuico, nota INTA 28/4/2026 | 2 | https://www.argentina.gob.ar/noticias/cultivos-de-cobertura-y-efectos-en-las-propiedades-fisicas-en-un-argiudol-acuico |
| INTA EEA Esquel, Bobadilla S.E.: Alfalfa en el noroeste de Chubut | 2 | https://repositorio.inta.gob.ar/bitstream/handle/20.500.12123/11956/INTA_CRPatagoniaSur_EEAEsquel_Bobadilla,%20Segundo%20Evaristo_Alfalfa_en_el_noroeste_de_chubut.pdf?sequence=1 |
| INTA EEA Manfredi, Bongiovanni (ed.): Buenas prácticas agrícolas para la producción de maní (2012) | 2 | https://repositorio.inta.gob.ar/xmlui/bitstream/handle/20.500.12123/15722/INTA_CRCordoba_EEAManfredi_Bongiovanni_R_Buenas_practicas_agricolas_produccion_mani.pdf |
| INTA EEA Manfredi, Olivo S.: Establecimiento de alfalfa, aspectos ecofisiológicos y agronómicos (cap. 5) | 2 | https://repositorio.inta.gob.ar/xmlui/bitstream/handle/20.500.12123/18704/INTA_CRC%C3%B3rdoba_EEAManfredi_Olivo_Silvia_Establecimiento_de_alfalfa_aspectos_ecofisiol%C3%B3gicos.pdf?sequence=1&isAllowed=y |
| INTA Famaillá, noticia: Qué tener en cuenta para el control de malezas en los cañaverales | 2 | https://www.argentina.gob.ar/noticias/que-tener-en-cuenta-para-el-control-de-malezas-en-los-canaverales |
| INTA IPAF NOA: Quinoa Morrillos INTA | 2 | https://www.argentina.gob.ar/inta/tecnologias/quinoa-chenopodium-quinoa-willd-morrillos-inta |
| INTA Junín, noticia: INTA Junín determina densidades de siembra para el girasol en la región (02/10/2026) | 2 | https://www.argentina.gob.ar/noticias/inta-junin-determina-densidades-de-siembra-para-el-girasol-en-la-region |
| INTA Manfredi / Marcos Juárez, noticia: Cultivo de soja, fecha de siembra y grupo de madurez para potenciar el rendimiento (19/08/2026) | 2 | https://www.argentina.gob.ar/noticias/cultivo-de-soja-fecha-de-siembra-y-grupo-de-madurez-para-potenciar-el-rendimiento |
| INTA Marcos Juárez, noticia: Triticale, presentan tres nuevas variedades del cereal forrajero | 2 | https://www.argentina.gob.ar/noticias/triticale-presentan-tres-nuevas-variedades-del-cereal-forrajero |
| INTA Pergamino, noticia: Trigo y cebada, qué hacer frente a las enfermedades foliares (05/10/2023) | 2 | https://www.argentina.gob.ar/noticias/trigo-y-cebada-que-hacer-frente-las-enfermedades-foliares |
| INTA Reconquista, noticia: La fecha de siembra, un factor clave para impulsar el rendimiento (03/05/2024) | 2 | https://www.argentina.gob.ar/noticias/la-fecha-de-siembra-un-factor-clave-para-impulsar-el-rendimiento |
| INTA San Luis, noticia: Estudian estrategias para optimizar la producción de maíz en ambientes semiáridos (13/12/2024) | 2 | https://www.argentina.gob.ar/noticias/estudian-estrategias-para-optimizar-la-produccion-de-maiz-en-ambientes-semiaridos |
| INTA, noticia: Siembra de maíz, qué hacer en cada región (29/08/2024) | 2 | https://www.argentina.gob.ar/noticias/siembra-de-maiz-que-hacer-en-cada-region |
| INTA, noticia: Soja de primavera, claves para definir la siembra en el Chaco | 2 | https://www.argentina.gob.ar/noticias/soja-de-primavera-claves-para-definir-la-siembra-en-el-chaco |
| INTA Aguilares, noticia: Papa, manejo del tizón tardío para aumentar la producción (06/09/2022) | 1 | https://www.argentina.gob.ar/noticias/papa-manejo-del-tizon-tardio-para-aumentar-la-produccion |
| INTA Balcarce, noticia: Recomendaciones para el almacenamiento seguro del girasol (25/02/2019) | 1 | https://www.argentina.gob.ar/noticias/recomendaciones-para-el-almacenamiento-seguro-del-girasol |
| INTA CIAP: La rabia del garbanzo, una enfermedad para estar alerta | 1 | https://www.argentina.gob.ar/inta/ciap/la-rabia-del-garbanzo-una-enfermedad-para-estar-alerta |
| INTA EEA Anguil, Corró Molas A.: Ensayos comparativos de rendimiento de girasol 2020/21 | 1 | https://repositorio.inta.gob.ar/bitstream/handle/20.500.12123/12052/INTA_CRLaPampa_SanLuis_EEAAnguil_CorroMolas_A_Ensayos_Comparativos_de_Rendimiento.pdf?sequence=5 |
| INTA EEA Balcarce y UNLP, Odriozola y otros, Fotosensibilización espontánea por consumo de mijo (Panicum miliaceum L.) en terneras, Rev. Med. Vet. 90 (2009) | 1 | https://sedici.unlp.edu.ar/bitstream/handle/10915/142103/Documento_completo.pdf?sequence=1 |
| INTA EEA Balcarce, Carpaneto B.B.: Red de evaluación de cultivares de cebada cervecera | 1 | https://repositorio.inta.gob.ar/bitstream/handle/20.500.12123/9701/INTA_CRBsAsSur_EEABalcarce_Carpaneto_BB_Red_evaluaci%C3%B3n_cultivares_cebada.pdf?sequence=1&isAllowed=y |
| INTA EEA La Consulta, Burba J.L.: Manejo de suelos y preparación | 1 | https://repositorio.inta.gob.ar/xmlui/bitstream/handle/20.500.12123/10415/INTA_CRMendoza-SanJuan_EEALaConsulta_Burba_JL_Manejo_de_suelos_y_preparaci%C3%B3n.pdf |
| INTA Famaillá, noticia: Cosechar caña en el 2025 con eficiencia y calidad (13/05/2025) | 1 | https://www.argentina.gob.ar/noticias/cosechar-cana-en-el-2025-con-eficiencia-y-calidad |
| INTA Famaillá, noticia: Costos de producción de papa consumo en Tucumán (2024) | 1 | https://www.argentina.gob.ar/noticias/costos-de-produccion-de-papa-consumo-en-tucuman-2024 |
| INTA Famaillá, noticia: Fertilización con nitrógeno para maximizar la producción de caña de azúcar | 1 | https://www.argentina.gob.ar/noticias/fertilizacion-con-nitrogeno-para-maximizar-la-produccion-de-cana-de-azucar |
| INTA Junín, noticia: INTA Junín determina densidades de siembra para el girasol en la región (campaña 2025/26) | 1 | https://www.argentina.gob.ar/noticias/inta-junin-determina-densidades-de-siembra-para-el-girasol-en-la-region |
| INTA Marcos Juárez, noticia: Claves para manejar las principales enfermedades del maíz (14/08/2026) | 1 | https://www.argentina.gob.ar/noticias/claves-para-manejar-las-principales-enfermedades-del-maiz |
| INTA Paraná, noticia: Colza, carinata y camelina, alternativas para diversificar las rotaciones agrícolas (L. Coll) | 1 | https://www.argentina.gob.ar/noticias/colza-carinata-y-camelina-alternativas-para-diversificar-las-rotaciones-agricolas |
| INTA Paraná, noticia: Soja, cómo minimizar la pérdida de granos durante la cosecha | 1 | https://www.argentina.gob.ar/noticias/soja-como-minimizar-la-perdida-de-granos-durante-la-cosecha |
| INTA Pergamino y Lares SRL: Guía técnica de control químico de malezas en colza-canola y carinata (2026) | 1 | https://www.argentina.gob.ar/sites/default/files/2026/05/inta_crbsasnorte_eeapergamino_guia_tecnica_malezas_colzacarinata.pdf |
| INTA Pergamino, indicadores económicos: margen bruto del cultivo de arveja verde (Paolilli, Prieto y otros) | 1 | https://www.argentina.gob.ar/inta/cr-buenosaires-norte/indicadores-economicos-e-informes-tecnicos/indicadores-economicos-de |
| INTA Pergamino, informe: Ajuste de dosis de fosfato monoamónico en Brassica carinata (Ferraris, Jecke y otros) | 1 | https://www.argentina.gob.ar/inta/cr-buenosaires-norte/ajuste-de-dosis-de-fosfato-monoamonico-en-brassica-carinata |
| INTA Pergamino, noticia: Fertilización en el sorgo granífero aumentó considerablemente su rendimiento (02/10/2023) | 1 | https://www.argentina.gob.ar/noticias/fertilizacion-en-el-sorgo-granifero-aumento-considerablemente-su-rendimiento |
| INTA Pergamino, noticia: Fertilización en maíz, cómo maximizar el aprovechamiento de los nutrientes del suelo (22/09/2023) | 1 | https://www.argentina.gob.ar/noticias/fertilizacion-en-maiz-como-maximizar-el-aprovechamiento-de-los-nutrientes-del-suelo |
| INTA Rafaela, noticia: Integrar colmenas aumenta un 37 % el rendimiento de carinata | 1 | https://www.argentina.gob.ar/noticias/integrar-colmenas-aumenta-un-37-el-rendimiento-de-carinata |
| INTA Reconquista, Intensificar las secuencias de cultivos mejora los rendimientos en algodón, nota INTA 12/2/2025 | 1 | https://www.argentina.gob.ar/noticias/intensificar-las-secuencias-de-cultivos-mejora-los-rendimientos-en-algodon |
| INTA, Caracterización de aislados de Nothopassalora personata, agente causal de la viruela tardía del maní | 1 | https://www.argentina.gob.ar/inta/ciap/caracterizacion-de-aislados-de-nothopassalora-personata-agente-causal-de-la-viruela-tardia |
| INTA, noticia: Cultivos de cobertura para mitigar la erosión del viento (06/05/2026) | 1 | https://www.argentina.gob.ar/noticias/cultivos-de-cobertura-para-mitigar-la-erosion-del-viento |
| INTA, noticia: El INTA presenta una nueva cebada cervecera | 1 | https://www.argentina.gob.ar/noticias/el-inta-presenta-una-nueva-cebada-cervecera |
| INTA, noticia: La fertilización nitrogenada mejora el desempeño del sorgo en suelos con restricciones (25/09/2026) | 1 | https://www.argentina.gob.ar/noticias/la-fertilizacion-nitrogenada-mejora-el-desempeno-del-sorgo-en-suelos-con-restricciones |
| INTA, noticia: Maní, utilizan biotecnología para acelerar la resistencia a enfermedades (03/09/2025) | 1 | https://www.argentina.gob.ar/noticias/mani-utilizan-biotecnologia-para-acelerar-la-resistencia-enfermedades |
| Kurtz D.B. y col. (INTA Corrientes), capítulo Corrientes del «Manual de Buenas Prácticas de Conservación del Suelo y del Agua en Áreas de Secano» (Casas y Damiano eds., 2019), tabla 1 de abonos verdes | 1 | https://fecic.org.ar/wp-content/uploads/2023/12/Provincia-de-Corrientes-para-web.pdf |

### Universidades nacionales (70 datos)

| Fuente | Datos | Link |
|---|---:|---|
| UNLP FCAF, libro de cátedra Cereales de verano (Simón y Golik, coords., EDULP 2018), cap. 13 Sorgo: siembra, época y densidad (S. Golik) | 9 | https://libros.unlp.edu.ar/index.php/unlp/catalog/book/935 |
| UNLP FCAF, libro de cátedra Lino, colza y cártamo (Sánchez Vallduví y Chamorro, coords., EDULP), cap. 6 Manejo tecnológico del cultivo de colza | 9 | https://sedici.unlp.edu.ar/handle/10915/158439 |
| UNLP FCAF, libro de cátedra Lino, colza y cártamo (Sánchez Vallduví y Chamorro, coords., EDULP), cap. 4 Manejo tecnológico del cultivo de lino | 8 | https://sedici.unlp.edu.ar/handle/10915/158558 |
| UNLP FCAF, libro de cátedra Lino, colza y cártamo (Sánchez Vallduví y Chamorro, coords., EDULP), cap. 8 Manejo tecnológico del cultivo de cártamo | 8 | https://sedici.unlp.edu.ar/handle/10915/153903 |
| UNLP FCAF, libro de cátedra Cereales de invierno (Simón y Golik, coords., EDULP), cap. 4 Trigo: siembra y densidad (S. Golik) | 6 | https://sedici.unlp.edu.ar/handle/10915/154685 |
| UNLP FCAF, libro de cátedra Cereales de verano (Simón y Golik, coords., EDULP 2018), cap. 3 Maíz: época y densidad de siembra (Simón, Schierenbeck y Dietz) | 5 | https://libros.unlp.edu.ar/index.php/unlp/catalog/book/935 |
| UNLP FCAF, libro de cátedra Cereales de invierno (Simón y Golik, coords., EDULP), cap. 15 Cebada cervecera: época y densidad de siembra (Da Silva y Dietz) | 3 | https://sedici.unlp.edu.ar/handle/10915/154685 |
| UNLP FCAF, libro de cátedra Cereales de verano (Simón y Golik, coords., EDULP 2018), cap. 23 Arroz: época y densidad de siembra (A. Vidal) | 3 | https://libros.unlp.edu.ar/index.php/unlp/catalog/book/935 |
| UNLP FCAF, libro de cátedra Cereales de verano (Simón y Golik, coords., EDULP 2018), cap. 24 Arroz: fertilización y rotaciones (R. Bezus) | 2 | https://libros.unlp.edu.ar/index.php/unlp/catalog/book/935 |
| UNLP FCAF, libro de cátedra Cereales de verano (Simón y Golik, coords., EDULP 2018), cap. 28 Arroz: zonas de cultivo (A. Vidal) | 2 | https://libros.unlp.edu.ar/index.php/unlp/catalog/book/935 |
| UNLP FCAF, libro de cátedra Cereales de verano (Simón y Golik, coords., EDULP 2018), cap. 6 Maíz: manejo de plagas | 2 | https://libros.unlp.edu.ar/index.php/unlp/catalog/book/935 |
| UNLP FCAF, libro de cátedra Lino, colza y cártamo (Sánchez Vallduví y Chamorro, coords., EDULP), cap. 3 Morfología y ecofisiología del cultivo de lino | 2 | https://sedici.unlp.edu.ar/handle/10915/153903 |
| UNLP FCAF, libro de cátedra Cereales de invierno (Simón y Golik, coords., EDULP), cap. 17 Cebada cervecera: fertilización (C. Weber) | 1 | https://sedici.unlp.edu.ar/handle/10915/154685 |
| UNLP FCAF, libro de cátedra Cereales de invierno (Simón y Golik, coords., EDULP), cap. 6 Enfermedades de trigo (Simón y Fleitas) | 1 | https://sedici.unlp.edu.ar/handle/10915/154685 |
| UNLP FCAF, libro de cátedra Cereales de invierno (Simón y Golik, coords., EDULP), cap. 7 Trigo: manejo de plagas (Uranga y Voisin) | 1 | https://sedici.unlp.edu.ar/handle/10915/154685 |
| UNLP FCAF, libro de cátedra Cereales de invierno (Simón y Golik, coords., EDULP), cap. 8 Trigo: manejo de malezas (Voisin y Uranga) | 1 | https://sedici.unlp.edu.ar/handle/10915/154685 |
| UNLP FCAF, libro de cátedra Cereales de verano (Simón y Golik, coords., EDULP 2018), cap. 14 Sorgo: fertilización y rotaciones (Golik y Fleitas) | 1 | https://libros.unlp.edu.ar/index.php/unlp/catalog/book/935 |
| UNLP FCAF, libro de cátedra Cereales de verano (Simón y Golik, coords., EDULP 2018), cap. 15 Sorgo: manejo de enfermedades | 1 | https://libros.unlp.edu.ar/index.php/unlp/catalog/book/935 |
| UNLP FCAF, libro de cátedra Cereales de verano (Simón y Golik, coords., EDULP 2018), cap. 16 Sorgo: manejo de plagas (M. R. Simón) | 1 | https://libros.unlp.edu.ar/index.php/unlp/catalog/book/935 |
| UNLP FCAF, libro de cátedra Cereales de verano (Simón y Golik, coords., EDULP 2018), cap. 27 Arroz: manejo de malezas (R. Bezus) | 1 | https://libros.unlp.edu.ar/index.php/unlp/catalog/book/935 |
| UNLP FCAF, libro de cátedra Cereales de verano (Simón y Golik, coords., EDULP 2018), cap. 4 Maíz: fertilización y rotaciones (Golik y Fleitas) | 1 | https://libros.unlp.edu.ar/index.php/unlp/catalog/book/935 |
| UNLP FCAF, libro de cátedra Cereales de verano (Simón y Golik, coords., EDULP 2018), cap. 5 Maíz y cap. 15 Sorgo: manejo de enfermedades | 1 | https://libros.unlp.edu.ar/index.php/unlp/catalog/book/935 |
| UNLP FCAF, libro de cátedra Cereales de verano (Simón y Golik, coords., EDULP 2018), cap. 5 Maíz: manejo de enfermedades | 1 | https://libros.unlp.edu.ar/index.php/unlp/catalog/book/935 |

### Gobierno nacional (argentina.gob.ar) (22 datos)

| Fuente | Datos | Link |
|---|---:|---|
| SAGyP, Resolución 1075/1994 (texto actualizado): normas de calidad para la comercialización de granos | 13 | https://www.argentina.gob.ar/normativa/nacional/resoluci%C3%B3n-1075-1994-28301/actualizacion |
| Ministerio de Hacienda, Informe productivo provincial Salta (año 2, n° 12, marzo 2017) | 4 | https://www.argentina.gob.ar/sites/default/files/informe_productivo_salta.pdf |
| SENASA, noticia: Fechas límite para la siembra de algodón y evitar la dispersión del picudo algodonero (27/09/2022; Res. SENASA 74/2010) | 2 | https://www.argentina.gob.ar/noticias/fechas-limite-para-la-siembra-de-algodon-y-evitar-la-dispersion-del-picudo-algodonero |
| Secretaría de Agricultura, Dirección de Producción Agrícola, informe Legumbres: evolución de la producción (enero 2023) | 2 | https://www.argentina.gob.ar/sites/default/files/informe-legumbres-enero-2023-02.pdf |
| SAGyP, Resolución 225/1997: norma de calidad del maní | 1 | https://www.argentina.gob.ar/normativa/nacional/resoluci%C3%B3n-225-1997-42751/texto |

### Otras (marcadas) (19 datos)

| Fuente | Datos | Link |
|---|---:|---|
| UNC, libro El cultivo de garbanzo en Argentina (Carreras, Mazzuferi y Karlin, eds., 2016, ISBN 978-950-33-1251-3; copia en bichosdecampo.com), cap. 5 Ecofisiología | 5 | https://bichosdecampo.com/wp-content/uploads/2020/05/Cultivo_garbanzo.pdf |
| No oficial (ONG técnica): ECHO, Ficha de información sobre plantas «Vigna unguiculata (caupí)» (guía general, no argentina) | 3 | https://www.echocommunity.org/es/resources/d9f09c50-0194-41ea-9695-96fa96004706.pdf |
| No oficial (prensa agropecuaria): Agroempresario, «Lens culinaris» (nota técnica sobre el cultivo en Argentina) | 3 | https://agroempresario.com/publicacion/28073/lens-culinaris/?cat=2260001 |
| UNC, libro El cultivo de garbanzo en Argentina (Carreras, Mazzuferi y Karlin, eds., 2016, ISBN 978-950-33-1251-3; copia en bichosdecampo.com), cap. 3 Manejo de suelo (M. Karlin) | 3 | https://bichosdecampo.com/wp-content/uploads/2020/05/Cultivo_garbanzo.pdf |
| UNC, libro El cultivo de garbanzo en Argentina (Carreras, Mazzuferi y Karlin, eds., 2016, ISBN 978-950-33-1251-3; copia en bichosdecampo.com), cap. 13 Santa Fe (Albrecht) y Salta | 2 | https://bichosdecampo.com/wp-content/uploads/2020/05/Cultivo_garbanzo.pdf |
| No oficial (banco de germoplasma): Dumet, Adeleke y Faloye (IITA), «Guías para la regeneración de germoplasma: Caupí», CGIAR Genebanks (parcelas de multiplicación, no producción) | 1 | https://genebanks.cgiar.org/resources/publications/cowpea-sp |
| UNC, libro El cultivo de garbanzo en Argentina (Carreras, Mazzuferi y Karlin, eds., 2016, ISBN 978-950-33-1251-3; copia en bichosdecampo.com), cap. 10 Producción de semilla | 1 | https://bichosdecampo.com/wp-content/uploads/2020/05/Cultivo_garbanzo.pdf |
| UNC, libro El cultivo de garbanzo en Argentina (Carreras, Mazzuferi y Karlin, eds., 2016, ISBN 978-950-33-1251-3; copia en bichosdecampo.com), cap. 9 Enfermedades de origen fúngico | 1 | https://bichosdecampo.com/wp-content/uploads/2020/05/Cultivo_garbanzo.pdf |

### INASE (11 datos)

| Fuente | Datos | Link |
|---|---:|---|
| INASE, Resolución 473/2024, anexo: densidad de siembra promedio en kilos de semilla por hectárea | 8 | https://www.argentina.gob.ar/sites/default/files/infoleg/404577/res473.pdf |
| INASE, informe del cultivo de arveja campaña 2021/22 | 2 | https://www.argentina.gob.ar/sites/default/files/inase_if_arvejas_21_22.pdf |
| INASE, noticia: Garbanzo, semilla de clase fiscalizada a partir de enero 2024 | 1 | https://www.argentina.gob.ar/noticias/garbanzo-semilla-de-clase-fiscalizada-partir-de-enero-2024 |

### SciELO / revistas científicas (4 datos)

| Fuente | Datos | Link |
|---|---:|---|
| Lilloa 53(1) 2016 (SciELO): Efectos de la densidad de siembra sobre quinoa var. CICA en Amaicha del Valle, Tucumán | 2 | https://www.scielo.org.ar/scielo.php?script=sci_arttext&pid=S2346-96412016000100002 |
| UNR, Evaluation of a lentil collection (Lens culinaris Medik) using morphological traits and digital phenotyping, Rev. FCA UNCuyo 52(1), 2020 | 2 | https://www.scielo.org.ar/scielo.php?script=sci_arttext&pid=S1853-86652020000100001&lang=es |

### EEAOC (Tucumán) (3 datos)

| Fuente | Datos | Link |
|---|---:|---|
| EEAOC, Rev. Ind. y Agríc. de Tucumán (SciELO 2012): TUC 300, nueva variedad de poroto negro de ciclo corto para el NOA | 3 | https://www.scielo.org.ar/scielo.php?script=sci_arttext&pid=S1851-30182012000200004 |

### MAGyP / Ministerios (1 datos)

| Fuente | Datos | Link |
|---|---:|---|
| SAGPyA, Resolución 151/2008: norma de calidad para la comercialización de soja | 1 | https://magyp.gob.ar/sitio/areas/d_recursos_humanos/concurso/normativa/_archivos//000001_Resoluciones/000000_RESOLUCI%C3%93N%20151-2008%20Apru%C3%A9banse%20Normas%20de%20Calidad%20para%20la%20Comercializaci%C3%B3n%20de%20Soja..pdf |

## Anexo C. Requerimientos de ambiente por especie (117 fuentes distintas)

### FAO (794 datos)

| Fuente | Datos | Link |
|---|---:|---|
| FAO Irrigation and Drainage Paper 56, Chapter 6, Table 12 | 96 | https://www.fao.org/4/x0490e/x0490e0b.htm |
| FAO / Maas & Grattan, Annex 1, Table A1.1 | 71 | https://www.fao.org/4/y4263e/y4263e0e.htm |
| FAO Irrigation and Drainage Paper 56, Chapter 8, Table 22 | 44 | https://www.fao.org/4/x0490e/x0490e0e.htm |
| FAO, Frost Protection: fundamentals, practice and economics, vol. 1, tabla 4.5; tabla atribuida a Ventskevich (1958) | 28 | https://www.fao.org/4/y7223s/y7223s.pdf |
| FAO Plant Nutrition for Food Security (2006), Figure 18 | 24 | https://www.fao.org/docrep/pdf/009/a0443e/a0443e.pdf |
| FAO EcoCrop (OpenCLIM v1.0 y ficha FAO) | 19 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=1191 |
| FAO EcoCrop (OpenCLIM v1.0 y ficha FAO) | 19 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=1232 |
| FAO EcoCrop (OpenCLIM v1.0 y ficha FAO) | 19 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=1721 |
| FAO EcoCrop (OpenCLIM v1.0 y ficha FAO) | 19 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=1929 |
| FAO EcoCrop (OpenCLIM v1.0 y ficha FAO) | 19 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=1971 |
| FAO EcoCrop (OpenCLIM v1.0 y ficha FAO) | 19 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=2114 |
| FAO EcoCrop (OpenCLIM v1.0 y ficha FAO) | 19 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=2153 |
| FAO EcoCrop (OpenCLIM v1.0 y ficha FAO) | 19 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=2479 |
| FAO EcoCrop (OpenCLIM v1.0 y ficha FAO) | 19 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=2509 |
| FAO EcoCrop (OpenCLIM v1.0 y ficha FAO) | 19 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=2514 |
| FAO EcoCrop (OpenCLIM v1.0 y ficha FAO) | 19 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=481 |
| FAO EcoCrop (OpenCLIM v1.0 y ficha FAO) | 19 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=549 |
| FAO EcoCrop (OpenCLIM v1.0 y ficha FAO) | 19 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=7336 |
| FAO EcoCrop (OpenCLIM v1.0 y ficha FAO) | 18 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=548 |
| FAO EcoCrop (OpenCLIM v1.0 y ficha FAO) | 17 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=10582 |
| FAO EcoCrop (OpenCLIM v1.0 y ficha FAO) | 17 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=1150 |
| FAO EcoCrop (OpenCLIM v1.0 y ficha FAO) | 17 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=1160 |
| FAO EcoCrop (OpenCLIM v1.0 y ficha FAO) | 17 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=1574 |
| FAO EcoCrop (OpenCLIM v1.0 y ficha FAO) | 17 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=1668 |
| FAO EcoCrop (OpenCLIM v1.0 y ficha FAO) | 17 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=2146 |
| FAO EcoCrop (OpenCLIM v1.0 y ficha FAO) | 17 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=2199 |
| FAO EcoCrop (OpenCLIM v1.0 y ficha FAO) | 17 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=48747 |
| FAO EcoCrop (OpenCLIM v1.0 y ficha FAO) | 17 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=7209 |
| FAO Plant Nutrition for Food Security (2006), Table 26 | 17 | https://www.fao.org/docrep/pdf/009/a0443e/a0443e.pdf |
| FAO EcoCrop (OpenCLIM v1.0 y ficha FAO) | 14 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=2175 |
| FAO EcoCrop (OpenCLIM v1.0 y ficha FAO) | 14 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=3568 |
| ECO_ALGODON | 5 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=1160 |
| ECO_ARROZ | 5 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=1574 |
| ECO_ARVEJA | 5 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=1721 |
| ECO_AVENA | 5 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=481 |
| ECO_CARTAMO | 5 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=2514 |
| ECO_CAUPI | 5 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=2153 |
| ECO_CEBADA | 5 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=1232 |
| ECO_CENTENO | 5 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=1929 |
| ECO_COLZA | 5 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=549 |
| ECO_GARBANZO | 5 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=2479 |
| ECO_LINO | 5 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=7336 |
| ECO_MANI | 5 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=2199 |
| ECO_TRIGO | 5 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=2114 |
| ECO_CANA | 3 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=1884 |

### INTA (653 datos)

| Fuente | Datos | Link |
|---|---:|---|
| Riglos (2023), tesis doctoral UBA/FAUBA-INTA, Cuadro 2.3 | 217 | https://ri.agro.uba.ar/files/download/tesis/doctorado/2024riglosmiguelmaximiliano.pdf |
| INTA EEA Marcos Juárez — Evaluación de cultivares de triticale para producción de forraje y grano (2020) | 53 | https://repositorio.inta.gob.ar/bitstream/handle/20.500.12123/9709/INTA_CRCordoba_EEAMarcosJuarez_Donaire_G_evaluacion_cultivares_triticale_produccion_forrajes.pdf?isAllowed=y&sequence=1 |
| Evaluación de cultivares de triticale para producción de forraje y grano en INTA EEA Marcos Juárez | 32 | https://repositorio.inta.gob.ar/bitstream/handle/20.500.12123/14405/INTA_CRCordoba_EEAMarcosJuarez_Donaire_G_Evaluacion_triticale_campa%C3%B1a_2022.pdf?isAllowed=y&sequence=1 |
| Resultados ensayo comparativo de rendimientos de sorgos graníferos, forrajeros y sileros | 27 | https://repositorio.inta.gob.ar/bitstream/handle/20.500.12123/15122/INTA_CR_LaPampa-SanLuis_EEAAnguil_Dillchneider_A._Resultados%20ensayo%20corporativo%20de%20rendimiento%20de%20sorgo%20gran%C3%ADferos%2C%20forrajeros%20y%20sileros.pdf?isAllowed=y&sequence=1 |
| INTA / Chacra Experimental Integrada Barrow — Fechas de siembra y densidad en el cultivo de lupino | 24 | https://visionrural.ar/wp-content/uploads/2026/07/Fechas-de-siembra-y-desnsidad-en-el-cultivo-de-lupino.pdf |
| Información técnica de cultivos de invierno 2018 — ensayo de arveja campaña 2017 | 24 | https://repositorio.inta.gob.ar/bitstream/handle/20.500.12123/3318/INTA_CRSantaFe_EEARafaela_Informaci%C3%B3n%20T%C3%A9cnica_de_cultivos_de_invierno_2018.pdf?isAllowed=y&sequence=1 |
| Evaluación de cultivares comerciales de avena para producción de forraje | 22 | https://repositorio.inta.gob.ar/bitstream/handle/20.500.12123/14531/INTA_CRCordoba_EEAMarcosJuarez_Donaire_G_Evaluacion_avena_forraje.pdf?isAllowed=y&sequence=1 |
| INTA Hilario Ascasubi, Boletín Técnico 36 (diciembre 2022), tabla 1 | 21 | https://repositorio.inta.gob.ar/bitstream/handle/20.500.12123/13881/INTA_CRBsAsSur_EEAHilarioAscasubi_Pezzola_A_Heladas_tardias_noviembre2022.pdf?isAllowed=y&sequence=1 |
| Aplicación de biofertilizantes en el cultivo de papa en la provincia de Tucumán | 18 | https://repositorio.inta.gob.ar/xmlui/bitstream/handle/20.500.12123/24648/INTA_CRTucum%C3%A1n-SantiagodelEstero_EEAFamaill%C3%A1_Quiroga_RJ_Aplicaci%C3%B3n_biofertilizantes_cultivo_papa_Tucum%C3%A1n.pdf?isAllowed=y&sequence=1 |
| Red de evaluación de cultivares de girasol — documento rotulado campaña 2023-2024 | 17 | https://repositorio.inta.gob.ar/bitstream/handle/20.500.12123/17713/INTA_CR_LaPampa-SanLuis_EEAAnguil_Dillchneider_A._Red%20de%20evaluaci%C3%B3n%20de%20cultivares%20de%20girasol.%20Campa%C3%B1a%202023-2024.pdf?isAllowed=y&sequence=1 |
| Appella & Gutiérrez, INTA CEI Barrow (2025) | 16 | https://repositorio.inta.gob.ar/xmlui/bitstream/handle/20.500.12123/22394/INTA_CRBsAsSur_EEABarrow_Appella_C_Fecha_siembra_densidad.pdf?isAllowed=y&sequence=4 |
| Comportamiento de variedades de lino oleaginoso en Balcarce | 13 | https://repositorio.inta.gob.ar/xmlui/bitstream/handle/20.500.12123/16983/INTA_CREntreRios_EEAParana_Gallardo_M_Comportamiento_de_variedades_de_lino_oleaginoso.pdf?isAllowed=y&sequence=1 |
| Fecha de siembra y ciclo de colza afectan el rendimiento | 12 | https://repositorio.inta.gob.ar/xmlui/bitstream/handle/20.500.12123/17460/INTA_CREntreRios_EEAParana_Coll_L_fecha_siembra_ciclo_colza_afectan_rendimiento.pdf?isAllowed=y&sequence=1 |
| INTA Balcarce / IPADS-UNMdP-CONICET: Cómo aprovechar la lluvia para potenciar los rindes (26/10/2026) | 11 | https://www.argentina.gob.ar/noticias/como-aprovechar-la-lluvia-para-potenciar-los-rindes |
| INTA EEA Marcos Juárez — Comportamiento productivo de cereales de invierno durante campaña 2024 | 11 | https://www.argentina.gob.ar/sites/default/files/2025/03/inta_crcordoba_eeamarcosjuarez_donaire_g_comportamiento.pdf |
| ECO_SOJA; ORA_MAPAS_2018; INTA_SUELO_FISICO_2024; INTA_MARCOSJUAREZ_2024 | 10 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=1150  ·  https://www.argentina.gob.ar/sites/default/files/publicacion1-mapasareasaptas.pdf  ·  https://www.argentina.gob.ar/node/419263  ·  https://www.argentina.gob.ar/sites/default/files/2024/08/inta_crcordoba_eeamarcosjuarez_baigorria_t_boletin.pdf |
| Producción de garbanzo en la región semiárida pampeana | 10 | https://repositorio.inta.gob.ar/bitstream/handle/20.500.12123/9552/INTA_CR_LaPampa_SanLuis_EEAAnguil_Zamora%3B_D._Producci%C3%B3n%20de%20garbanzo%20en%20la%20regi%C3%B3n%20semi%C3%A1rida%20pampeana.pdf?isAllowed=y&sequence=1 |
| INTA / Argentina.gob.ar — San Luis: incorporan centeno para controlar la erosión | 9 | https://www.argentina.gob.ar/node/485480 |
| Manual de fertilidad y evaluación de suelos, EEA Anguil, INTA (2012) | 9 | https://repositorio.inta.gob.ar/xmlui/bitstream/handle/20.500.12123/14650/INTA_CRLaPampa-SanLuis_EEAAnguil_Manual_de_Fertilidad_Suelos.pdf?isAllowed=y&sequence=1 |
| INTA / FCA-UNNE — Baja radiación en prefloración y posfloración: consecuencias en el rendimiento de cultivares de arroz | 8 | https://www.argentina.gob.ar/noticias/baja-radiacion-en-prefloracion-y-posfloracion-consecuencias-en-el-rendimiento-de-cultivares |
| INTA EEA Anguil, Manual de fertilidad y evaluación de suelos | 8 | https://repositorio.inta.gob.ar/xmlui/bitstream/handle/20.500.12123/14650/INTA_CRLaPampa-SanLuis_EEAAnguil_Manual_de_Fertilidad_Suelos.pdf?isAllowed=y&sequence=1 |
| INTA EEA San Pedro — Sanidad en cultivos intensivos 2013, Módulo 3 (arveja y lenteja) | 7 | https://repositorio.inta.gob.ar/bitstream/handle/20.500.12123/2692/INTA_CRBsAsNorte_EEASanPedro_Mitidieri_Francescangeli_eds_Curso_Sanidad_cvoIntens_mod3.pdf?isAllowed=y&sequence=2 |
| Riglos (2023), tesis doctoral UBA/FAUBA-INTA; Riglos et al., análisis de maní y soja en semiárido central | 6 | https://ri.agro.uba.ar/files/download/tesis/doctorado/2024riglosmiguelmaximiliano.pdf |
| ECO_GIRASOL; UNRC_SUELO_PLANTA_2017; INTA_SUELO_FISICO_2024 | 5 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=1191 |
| ECO_LUPINO; INTA_LUPINO_2025; INTA_LUPINO_EXP | 5 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=2519  ·  https://repositorio.inta.gob.ar/xmlui/bitstream/handle/20.500.12123/22394/INTA_CRBsAsSur_EEABarrow_Appella_C_Fecha_siembra_densidad.pdf?isAllowed=y&sequence=4 |
| ECO_PAPA; INTA_SUELO_FISICO_2024 | 5 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=1971  ·  https://www.argentina.gob.ar/node/419263 |
| ECO_SORGO; INTA_SUELO_FISICO_2024 | 5 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=48747  ·  https://www.argentina.gob.ar/node/419263 |
| INTA Alto Valle, revista F&D #98, artículo de rehabilitación de suelos salino-sódicos | 5 | https://www.argentina.gob.ar/sites/default/files/2025/07/inta_revista-fd_98.pdf |
| Mitidieri y Francescangeli (eds.), Curso Sanidad en Cultivos Intensivos, módulo de legumbres | 5 | https://repositorio.inta.gob.ar/bitstream/handle/20.500.12123/2692/INTA_CRBsAsNorte_EEASanPedro_Mitidieri_Francescangeli_eds_Curso_Sanidad_cvoIntens_mod3.pdf?isAllowed=y&sequence=2 |
| INTA EEA Famaillá: Uso de nutrientes en diferentes estadios del cultivo de maní, campaña 2024–2025 | 4 | https://www.argentina.gob.ar/sites/default/files/2025/08/informe_uso_de_nutrientes_en_diferentes_estadios_del_cultivo_de_mani.pdf |
| INTA San Luis - Evalúan cuatro cultivos de verano frente a la variabilidad del clima y del suelo | 4 | https://www.argentina.gob.ar/noticias/evaluan-cuatro-cultivos-de-verano-frente-la-variabilidad-del-clima-y-del-suelo |
| Riglos (2023), tesis doctoral FAUBA/UBA-INTA, metodología y abreviaturas | 4 | https://ri.agro.uba.ar/files/download/tesis/doctorado/2024riglosmiguelmaximiliano.pdf |
| INTA Barrow: mínimo 15 °C; óptimo 18–20 °C en 10 cm superiores durante ≥3 días; emergencia 3–4 días. | 3 | https://repositorio.inta.gob.ar/xmlui/bitstream/handle/20.500.12123/15503/INTA_CRBuenos%20AiresSur_EEABarrow_Carrasco_N_Manual_sorgo.pdf?isAllowed=y&sequence=1  ·  https://www.unirioeditora.com.ar/wp-content/uploads/2018/08/978-987-688-204-0.pdf |
| INTA EEA Anguil, Avances de la agricultura por ambientes en la región semiárida pampeana | 3 | https://repositorio.inta.gob.ar/bitstream/handle/20.500.12123/14987/INTA_CR_LaPampa-SanLuis_AERGeneraPico_Corro%20Molas_A._Avances%20de%20la%20agricultura%20por%20ambientes.pdf?isAllowed=y&sequence=1 |
| INTA/Capítulo técnico sobre arroz cita literatura: mínimo 6–8 °C, óptimo ~37 °C, máximo 41–44 °C; plántula óptima 22–31 °C. No convertir en fecha de siembra. | 3 | https://www.fao.org/4/y2778s/y2778s04.htm  ·  https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=1574  ·  https://www.unirioeditora.com.ar/wp-content/uploads/2018/08/978-987-688-204-0.pdf |
| INTA_MARCOSJUAREZ_2024 | 3 | https://www.argentina.gob.ar/sites/default/files/2024/08/inta_crcordoba_eeamarcosjuarez_baigorria_t_boletin.pdf |
| Quiroga y Bono (eds.), Manual de fertilidad y evaluación de suelos, EEA INTA Anguil | 3 | https://repositorio.inta.gob.ar/xmlui/bitstream/handle/20.500.12123/14650/INTA_CRLaPampa-SanLuis_EEAAnguil_Manual_de_Fertilidad_Suelos.pdf?isAllowed=y&sequence=1 |
| INTA: suelo alrededor de 22 °C favorece emergencia rápida; <18 °C retrasa; >35–38 °C reduce emergencia, especialmente con déficit hídrico. EcoCrop aparte. | 2 | https://www.argentina.gob.ar/noticias/soja-de-primavera-claves-para-definir-la-siembra-en-el-chaco  ·  https://www.unirioeditora.com.ar/wp-content/uploads/2018/08/978-987-688-204-0.pdf |
| INTA EEA Corrientes — Proyecto Arroz: resultados campaña 2025/2026 | 1 | https://repositoriosdigitales.sicyt.gob.ar/vufind/Record/INTADig_2e5b07992b3c0dd4ec5e79bd12cc3f9c |
| INTA_DRENAJE_2015 | 1 | https://www.argentina.gob.ar/sites/default/files/2022/09/24_drenaje_de_suelos_para_uso_agricola.pdf |
| INTA_SUDOESTE_2019 | 1 | https://www.argentina.gob.ar/sites/default/files/guia_criterios_basicos_prod_agropecuaria.pdf |
| INTA_SUELO_FISICO_2024 | 1 | https://www.argentina.gob.ar/node/419263 |
| INTA_SUELO_FISICO_KIT_2024 | 1 | https://www.argentina.gob.ar/node/443961 |
| INTA_SUELO_LAMINAR_2026 | 1 | https://www.argentina.gob.ar/noticias/la-estructura-laminar-una-limitante-silenciosa-que-desafia-la-salud-del-suelo |
| López de Sabando, Propiedades de suelo y producción de trigo según estrategias de delimitación de zonas de manejo | 1 | https://repositorio.inta.gob.ar/xmlui/bitstream/handle/20.500.12123/6122/INTA_CRBsAsNorte_EEAPergamino_LopezdeSabando_MJ_Propiedades_de_suelo_y_producci%C3%B3n_de_trigo.pdf?isAllowed=y&sequence=1 |
| ORA_MAPAS_2018; INTA_DRENAJE_2015 | 1 | https://www.argentina.gob.ar/sites/default/files/publicacion1-mapasareasaptas.pdf  ·  https://www.argentina.gob.ar/sites/default/files/2022/09/24_drenaje_de_suelos_para_uso_agricola.pdf |
| Schulz et al., Aplicación del índice de productividad unificado para la hoja Lajitas, Salta | 1 | https://repositorio.inta.gob.ar/bitstream/handle/20.500.12123/17619/INTA_CIRN_InstitutodeSuelos_Schulz_Aplicaci%C3%B3n_del_indice_de_productividad_unificado.pdf?isAllowed=y&sequence=2 |

### EEAOC (Tucumán) (62 datos)

| Fuente | Datos | Link |
|---|---:|---|
| EEAOC — Lenteja, una alternativa de cultivo invernal para el noroeste argentino | 17 | https://www.eeaoc.org.ar/wp-content/uploads/2018/12/37-3-5.pdf |
| ECO_POROTO; EEAOC_POROTO_2021; UNRC_SUELO_PLANTA_2017 | 15 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=1668  ·  https://www.avance.eeaoc.gob.ar/?articulo=cultivo-de-poroto |
| EEAOC - Guía Técnica del Cañero | 10 | https://publicaciones.srt.gob.ar/Publicaciones%20Ext/C005.pdf |
| EEAOC - Cultivo de poroto: consideraciones al momento de siembra | 8 | https://www.avance.eeaoc.gob.ar/?articulo=cultivo-de-poroto |
| ECO_LENTEJA; EEAOC_LENTEJA_2017 | 5 | https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=7209  ·  https://www.eeaoc.gob.ar/wp-content/uploads/2018/12/37-3-5.pdf |
| EEAOC — Jornada de cultivos invernales: colza, carinata, camelina, cártamo y garbanzo | 4 | https://www.eeaoc.gob.ar/la-eeaoc-presento-alternativas-para-diversificar-la-produccion-de-cultivos-invernales-en-la-region/ |
| https://www.eeaoc.org.ar/wp-content/uploads/2018/12/37-3-5.pdf | 2 | https://www.eeaoc.org.ar/wp-content/uploads/2018/12/37-3-5.pdf |
| https://www.eeaoc.gob.ar/la-eeaoc-presento-alternativas-para-diversificar-la-produccion-de-cultivos-invernales-en-la-region/ | 1 | https://www.eeaoc.gob.ar/la-eeaoc-presento-alternativas-para-diversificar-la-produccion-de-cultivos-invernales-en-la-region/ |

### Universidades nacionales (22 datos)

| Fuente | Datos | Link |
|---|---:|---|
| UNLP - Lino, colza y cártamo, cap. 7 | 7 | https://sedici.unlp.edu.ar/bitstream/handle/10915/158495/Documento_completo.pdf-PDFA.pdf?sequence=1&isAllowed=y |
| UNR - El lupino: una alternativa productiva | 6 | https://fcagr.unr.edu.ar/Extension/Agromensajes/03/3AM3.htm |
| UNSL-FICA, Tello (2024), trabajo final: Comportamiento productivo de un cultivo de soja a la aplicación de un bioestimulante foliar | 4 | https://dspace.fica.unsl.edu.ar/handle/123456789/28 |
| UNSL-FICA, Lujan (2024), trabajo final: Análisis ecofisiológico comparativo entre maíz y sorgo en la región semiárida central | 3 | https://dspace.fica.unsl.edu.ar/handle/123456789/32 |
| UNLP - Lino, colza y cártamo, cap. 7 | 2 | https://sedici.unlp.edu.ar/bitstream/handle/10915/158495/Documento_completo.pdf?sequence=1&isAllowed=y |

### Otras (marcadas) (21 datos)

| Fuente | Datos | Link |
|---|---:|---|
| Bonadeo et al., Sistema suelo-planta (2017), tabla 8.2 | 12 | https://www.unirioeditora.com.ar/wp-content/uploads/2018/08/978-987-688-204-0.pdf |
| Bonadeo et al., Sistema suelo-planta (2017), tabla 8.4 | 8 | https://www.unirioeditora.com.ar/wp-content/uploads/2018/08/978-987-688-204-0.pdf |
| https://visionrural.ar/wp-content/uploads/2026/07/Fechas-de-siembra-y-desnsidad-en-el-cultivo-de-lupino.pdf | 1 | https://visionrural.ar/wp-content/uploads/2026/07/Fechas-de-siembra-y-desnsidad-en-el-cultivo-de-lupino.pdf |

### INASE (19 datos)

| Fuente | Datos | Link |
|---|---:|---|
| INASE/SISA - Informe fitosanitario Garbanzo 2023/24 | 10 | https://www.argentina.gob.ar/sites/default/files/inase_sisa_if_garbanzo_23_24.pdf |
| INASE/SISA — Informe de arveja campaña 2023/2024 | 9 | https://www.argentina.gob.ar/sites/default/files/informe_sisa_arveja_23_24_rv01.pdf |

### MAGyP / Ministerios (15 datos)

| Fuente | Datos | Link |
|---|---:|---|
| Manual de Buenas Prácticas Agrícolas para Legumbres, MAGyP (2015) | 15 | https://alimentosargentinos.magyp.gob.ar/bpa/bibliografia/BPA_Legumbres.pdf |

### Gobierno nacional (argentina.gob.ar) (15 datos)

| Fuente | Datos | Link |
|---|---:|---|
| MAGyP: Fertilidad y Nutrición de Suelos – 200 Millones de Toneladas (2021), datos ReTAA 2018/19 | 6 | https://www.argentina.gob.ar/sites/default/files/informe-fertilidad-nutricion-suelos-200mt-magyp.pdf |
| Oficina de Riesgo Agropecuario (ORA), mapas de áreas aptas | 4 | https://www.argentina.gob.ar/sites/default/files/publicacion1-mapasareasaptas.pdf |
| ORA_MAPAS_2018 | 2 | https://www.argentina.gob.ar/sites/default/files/publicacion1-mapasareasaptas.pdf |
| https://www.argentina.gob.ar/sites/default/files/informe_sisa_arveja_23_24_rv01.pdf | 2 | https://www.argentina.gob.ar/sites/default/files/informe_sisa_arveja_23_24_rv01.pdf |
| https://www.argentina.gob.ar/noticias/baja-radiacion-en-prefloracion-y-posfloracion-consecuencias-en-el-rendimiento-de-cultivares | 1 | https://www.argentina.gob.ar/noticias/baja-radiacion-en-prefloracion-y-posfloracion-consecuencias-en-el-rendimiento-de-cultivares |

### ASAGIR (3 datos)

| Fuente | Datos | Link |
|---|---:|---|
| ASAGIR: umbral de suelo 8–10 °C a 0–5 cm; germinación óptima cercana a 26 °C; mínimas 3–6 °C y máxima 40 °C. | 3 | https://www.asagir.org.ar/descargar-archivo-45/archivos-01e3a1a53c235fd1484651587412a506  ·  https://www.unirioeditora.com.ar/wp-content/uploads/2018/08/978-987-688-204-0.pdf |
