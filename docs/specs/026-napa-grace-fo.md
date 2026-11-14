# Spec 026 · GRACE-FO: napa y agua profunda de la región

**Estado:** aprobada por Hernán ("Doy ok") · **Etapa:** pipeline satélite → API → app · **Requiere:** los secretos de Earthdata (`EARTHDATA_USERNAME`, `EARTHDATA_PASSWORD`) · **Rama:** `GRACE-napa_y_agua_profunda`

## 1. Objetivo

Dar el estado del **agua subterránea (napa)** y del agua de la zona de raíces alrededor del lote. Ningún otro satélite del pipeline la mide: SMAP llega a 1 m, y SEPA y el balance propio llegan a 2 m.

Hernán lo pidió ("Si, hazlo") después de preguntar si usábamos GRACE y GRACE-FO. El SDD de la plataforma de recomendación que pasó Leandro pide la profundidad de napa como dato del lote (cuestionario, "Profundidad de napa"). Este dato no la reemplaza: da el contexto regional cuando el productor no la conoce.

**Qué NO es:** no es un dato del lote. GRACE-FO mide la gravedad con una resolución real de unos 300 km. El producto de abajo lo baja a una grilla de 0,25° (~25 km) con un modelo, pero sigue describiendo la región. Sirve para saber si la zona viene en recarga o en pérdida de agua profunda, no para saber a cuántos metros está la napa en el lote.

## 2. Fuente

| | Principal: `GRACE` | Respaldo: `GRACE:MASCON` |
|---|---|---|
| Producto | GRACE and GRACE-FO Data Assimilation Drought Indicators, `GRACEDADM_CLSM025GL_7D` versión 3.0 | JPL GRACE/GRACE-FO Mascon CRI, `TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4` |
| Agencia | NASA (Goddard, GES DISC) | NASA (JPL, PO.DAAC) |
| Qué da | Percentil de agua subterránea, de humedad en la zona de raíces y de humedad superficial | Anomalía del agua total (napa + suelo + lagunas), en cm de agua |
| Grilla | 0,25°, de 60° S a 90° N (San Luis entra) | 0,5° (señal real de ~300 km) |
| Frecuencia | Semanal (un dato por lunes) | Mensual |
| Desde | 3/2/2003 | 4/2002 |
| Atraso | 3 a 6 meses. En la prueba, el último archivo era la semana del 29/6 al 5/7/2026 | Unos 2 meses |
| Acceso | CMR + OPeNDAP (`opendap.earthdata.nasa.gov`, colección C2283200566-GES_DISC) con el núcleo `earthdata` | CMR + descarga del archivo de PO.DAAC con el token de Earthdata. Es un solo NetCDF de ~44 MB con todos los meses; se baja una vez y se guarda hasta que JPL publique otro. PO.DAAC no lo sirve por OPeNDAP (la NASA responde 404, verificado) |

Verificado en CMR: las dos colecciones existen, cubren San Luis y el principal tiene archivos semanales hasta julio de 2026.

Variables del principal, según el README de GES DISC (`README_GRACEDADM3GL.pdf`):

| En el archivo | Variable del contrato | Unidad |
|---|---|---|
| `gws_inst` | `napa_percentil` | % |
| `rtzsm_inst` | `humedad_raices_percentil` | % |
| `sfsm_inst` | `humedad_superficial_percentil` | % |

El percentil dice qué tan húmeda está la zona comparada con todas las semanas iguales de 1948 a 2014: 50 es lo normal, 10 quiere decir que solo el 10 % de esas semanas estuvo más seco.

## 3. Entrada

- El lote como lo recibe cualquier satélite: `lote["id"]`, `lote["lat"]`, `lote["lon"]` (centro, EPSG:4326). Se usa el centro, porque un lote entra entero en un píxel.
- El período `desde`–`hasta` (máximo 366 días).

## 4. Proceso

1. Validar el pedido (coordenadas, fechas, máximo 366 días). Un pedido inválido no llama a la NASA.
2. Buscar en CMR los archivos semanales cuyo lunes cae entre `desde` y `hasta`.
3. Leer con OPeNDAP solo el píxel del centro del lote en las tres variables, sin bajar el archivo entero.
4. Una observación por semana y por variable, con fecha el lunes de esa semana.
5. Las semanas que la NASA todavía no publicó (por el atraso) salen con `valor null`, `calidad: "descartada"` y una nota que dice cuál es la última semana publicada. Si **ninguna** semana del período está publicada, el principal avisa con un error que dice la última semana publicada, y la consulta prueba el respaldo, que llega con menos atraso.
6. Si el píxel no tiene dato (mar o hielo), `valor null` + `descartada`.
7. **Respaldo** (`GRACE:MASCON`), si el principal no responde: baja (una vez) el archivo de mascons y lee los meses del período en el píxel de 0,5° y entrega `agua_total_anomalia_cm` (cm, anomalía contra el promedio de 2004 a 2009 que usa JPL). Es otra variable, como pasa con la ET0 de FAO-56 (spec 019), porque mide otra cosa: no se mezcla con el percentil.

## 5. Salida

`Observacion` con `fuente: "GRACE"`, `resolucion_m: 25000` en el principal y `55000` en el respaldo.

La `nota` siempre dice:

- que es un dato **regional**, con señal real de unos 300 km;
- el percentil y su categoría (tabla de abajo);
- la semana publicada y el atraso.

| Percentil | Categoría (la escala de los mapas de sequía GRACE de la NASA) |
|---|---|
| ≤ 2 | Sequía excepcional |
| ≤ 5 | Sequía extrema |
| ≤ 10 | Sequía severa |
| ≤ 20 | Sequía moderada |
| ≤ 30 | Anormalmente seco |
| 30 a 70 | Normal |
| > 70 | Más húmedo que lo normal |

El corte de 70 para "más húmedo" es un supuesto nuestro, simétrico al de 30. Se aclara en la nota.

## 6. Reglas de calidad

- Nunca inventar un valor: lo que no está publicado sale `null` + `descartada`.
- `calidad: "buena"` cuando el valor está entre 0 y 100. Fuera de ese rango, `dudosa`.
- Toda observación avisa en la nota que no es un dato del lote.
- El conector no importa otros satélites (spec 009). Usa solo `contrato`, `geo`, `earthdata` y `registro`.

## 7. Cambios en el núcleo

Se suma `GRACE` al tipo `Fuente` (`contrato.py`) y a `PRIORIDAD` (`base.py`), con prioridad 2 por ser un dato regional. Ningún otro archivo del núcleo cambia.

## 8. Pruebas

- `tests/test_grace.py`, sin internet, con las respuestas de CMR y OPeNDAP simuladas (`httpx.MockTransport`): lectura de las tres variables, semanas no publicadas, píxel sin dato, categoría en la nota y respaldo.
- `probar_grace.py` y el workflow `Probar GRACE (napa y agua profunda)`, con el lote de San Luis.

## 9. Criterios de aceptación

- [x] Con el lote de San Luis, de enero a junio de 2026, devuelve una observación semanal por variable (unas 26 semanas × 3 variables), con percentiles entre 0 y 100. *Verificado: 26 semanas × 3 = 78 observaciones buenas en 21 s. Napa 0,2 a 3,7 (sequía extrema o excepcional todo el semestre); raíces 2,4 a 71,3; superficie 0,2 a 92,1.*
- [x] Una semana todavía no publicada sale `descartada` y la nota dice cuál es la última publicada. *Verificado (junio a septiembre): 5 semanas publicadas (napa 2,6 → 1,1, de sequía extrema a excepcional) y 13 semanas desde el 6/7 descartadas con la última publicada (29/6/2026); 54 observaciones: 15 buenas y 39 descartadas.*
- [x] El respaldo `GRACE:MASCON` devuelve la anomalía mensual en cm para el mismo lote. *Verificado: enero a junio, 6 meses en 4 s (−22,4; −23,4; −23,0; −21,0; −20,8; −21,6 cm); junio a septiembre, 2 meses (−21,6 y −21,0 cm, julio es el último que publicó JPL).*
- [x] La nota de cada dato dice que es regional y da la categoría de sequía. *Ejemplo real: "Percentil de agua subterránea (napa): 2.6 = sequía extrema · … · dato REGIONAL, no del lote: GRACE-FO mide la gravedad con una resolución real de unos 300 km".*
- [x] `pytest` pasa sin internet. *20 pruebas de `tests/test_grace.py`; la suite completa, 61 pasadas.*
- [x] El workflow `Probar GRACE (napa y agua profunda)` pasa con datos reales. *Corridas 38490185626 y 38490286427 en verde.*
- [x] Hernán aprobó esta spec.

## 10. Preguntas abiertas

1. **Atraso.** El archivo oficial de la NASA llega con 3 a 6 meses de atraso: sirve para la historia y la tendencia del año, no para la semana actual. El mismo indicador se publica cada semana, con 2 a 9 días de atraso, en `nasagrace.unl.edu` (Centro Nacional de Mitigación de Sequías, Universidad de Nebraska, con la NASA). No es una agencia, así que queda afuera hasta que Hernán diga si se acepta. Tampoco se verificó todavía si ese sitio deja bajar los datos globales.
2. **Napa medida por el productor.** Cuando el productor carga la profundidad de napa (cuestionario del SDD de Leandro), ese dato manda sobre el de GRACE, que queda solo como contexto.
