# Spec 048 · pH de los perfiles medidos del INTA (SISINTA) como segunda referencia

**Estado:** Hernán lo pidió ("Daaale, eso también me sirve"), después de ver que los perfiles medidos del INTA dan una capa arable menos alcalina que los mapas · **Etapa:** pipeline fuente → API → motor · **Completa:** spec 021 (GeoINTA) y spec 027 §14 (pH de referencia)

## Objetivo

Que la app muestre, al lado del pH del mapa del INTA, el pH **medido en laboratorio** en los perfiles de suelo del INTA más cercanos al lote. Los dos son solo referencia: la última palabra la tiene el análisis del productor.

| Antes | Después |
|---|---|
| La única referencia de pH es el mapa del INTA (GeoINTA, 1 km), que en los 4 puntos del piloto da 0,25 a 0,65 unidades más que los perfiles medidos cerca | La app muestra también la mediana de los perfiles medidos del INTA a 10 km del lote (o a 25 km si no hay), con cuántos son, de qué años y el más cercano |
| Villa Mercedes: mapa 8,43 | Villa Mercedes: mapa 8,43 y perfiles 7,88 (7 perfiles a 10 km, 1975-2012) |

## Fuente

**SISINTA**, la base nacional de perfiles de suelo del INTA, publicada en GeoINTA como capa de puntos "Perfiles de Suelos Sisinta" (id 702). Se lee por WFS del nodo 05 (`geonode:rehecho`), sin clave. El catálogo la marca como **dominio público**. Cada fila es un horizonte de un perfil, con su profundidad y su pH en agua (`ph h2o`). Es una fuente del INTA, permitida por la regla de fuentes.

## Entrada

El polígono del lote (GeoJSON, EPSG:4326), como todas las fuentes.

## Proceso

1. **Pedido.** Se piden al WFS (versión 1.0.0, `bbox` en orden longitud, latitud) los horizontes dentro de un recuadro de ±25 km alrededor del centroide del lote. Un solo pedido por lote, con 60 s de espera. Con la versión 1.1.0 el INTA espera latitud, longitud y devuelve 0 horizontes sin avisar (probado).
2. **Solo perfiles públicos y con dato.** Solo entran perfiles con `s_publico` = 1. Casi todo llega como texto y el faltante es el texto `NA`: se descartan horizontes sin profundidad o con pH fuera de 3 a 11. No se intenta leer perfiles privados.
3. **pH de cada perfil por tramo.** Para 0-30 cm y 30-100 cm, el pH en agua promedio del perfil, pesado por el espesor de cada horizonte dentro del tramo. Solo cuenta si el perfil tiene dato en al menos la mitad del tramo (el mismo cálculo del informe).
4. **Radio.** Se usan los perfiles a 10 km o menos del centro del lote. Si no hay ninguno, los de 25 km. Si tampoco, la observación sale `valor: null`, `calidad: "descartada"` y la nota dice que no hay perfiles medidos cerca.
5. **Valor.** La mediana de los perfiles del radio usado. `resolucion_m` es el radio (10.000 o 25.000).
6. **Calidad.** Siempre `dudosa`: son mediciones puntuales, en su mayoría de 1975-1988, de lotes vecinos y no del lote. *(Supuesto: el pH en agua de SISINTA es 1:2,5, el estándar del INTA; la capa no lo dice.)*
7. **Fecha.** La del perfil más nuevo que entra en la mediana.
8. **Nota.** Dice cuántos perfiles, a qué radio, el rango (mín-máx), los años, y el perfil más cercano con su distancia, su serie y su pH. Termina con "solo de referencia: la última palabra la tiene el análisis de suelo del productor".
9. **Memoria.** Los perfiles no cambian: la respuesta completa de cada lote se guarda en memoria 30 días, como el suelo de GeoINTA (spec 044). Una respuesta con error no se guarda.

## Salida

Dos observaciones del contrato común:

```json
{"lote_id": "lote-7", "fecha": "1983-10-06", "variable": "suelo_ph_perfiles_0_30cm", "valor": 7.88,
 "unidad": "pH", "fuente": "SISINTA", "resolucion_m": 10000, "calidad": "dudosa",
 "nota": "Mediana de 5 perfiles medidos del INTA a 10 km o menos, 0-30 cm (de 7.22 a 8.71), años 1979-1983 · más cercano: perfil 4902, serie Cramer, a 7.2 km, 8.71 · pH en agua (relación 1:2,5 supuesta, la capa no la dice) · SISINTA (GeoINTA, capa 702) · solo de referencia: la última palabra la tiene el análisis de suelo del productor"}
```

y `suelo_ph_perfiles_30_100cm` igual. El motor (spec 027) suma `perfil_lote.ph_referencia_perfiles` con el dato de 0-30 cm. **Nunca decide**: no entra en ninguna regla del catálogo, igual que `ph_referencia`.

Además, `POST /suelo/ph-perfiles` (endpoint de prueba del conector) y la fuente `SISINTA` en `POST /consulta`.

## Reglas de calidad

- Nunca se inventa un perfil ni un valor. Sin perfiles cerca: `null` y `descartada`.
- No es una medición del lote: siempre `dudosa`.
- No importa ningún otro satélite (spec 009); no toca el conector de GeoINTA.

## Pruebas sin internet (`tests/test_sisinta.py`)

Con una respuesta real del WFS guardada (recuadro de 25 km alrededor del lote de prueba):

- Lote de prueba → 0-30 cm: mediana 7,88 con 5 perfiles a 10 km (los números del informe).
- Promedio pesado por espesor y regla de "al menos la mitad del tramo".
- Sin perfiles a 10 km pero sí a 25 km → usa 25 km y `resolucion_m` 25.000.
- Sin perfiles → `null`, `descartada`, nota clara.
- pH fuera de rango y horizontes sin profundidad se ignoran.
- WFS caído → error del conector (502 en el endpoint), no se guarda en memoria.
- Motor: `ph_referencia_perfiles` aparece con fuente SISINTA y no cambia la viabilidad de ningún cultivo.

## Criterios de aceptación

- [x] El lote de prueba da 7,88 en 0-30 cm (5 perfiles a 10 km, de 7,22 a 8,71), igual que el informe. *Verificado sin internet con la respuesta real del WFS guardada (63 horizontes de 16 perfiles, 14 con pH): `tests/test_sisinta.py`.*
- [x] Probado con el INTA real en los 3 lotes del piloto, anotando valor, cantidad de perfiles y tiempo. *20/10/2026 10:54 UTC, `probar_sisinta.py` desde el entorno de la nube con acceso al INTA (Actions frenado por facturación), 1,8 a 2,7 s por lote:*

| Lote | 0-30 cm (perfiles a 10 km) | 30-100 cm (perfiles) | Perfil más cercano | Años |
|---|---|---|---|---|
| Lote de prueba | 7,88 (5) | 8,62 (4) | 4902, Cramer, 7,2 km | 1979-1983 |
| Villa Mercedes 01-90230 | 7,88 (7) | 8,60 (7) | 4931, Cramer, 5,4 km | 1975-1983 |
| Justo Daract 06-924206 | 7,38 (1) | 8,86 (1) | 3692, Río Quinto 1, 3,7 km | 1980 |
| Buena Esperanza 02-950571 | 6,95 (6) | 7,86 (3) | 3685, Agustinillo, 5,2 km | 1979 |

*Coinciden con los valores a 10 km del informe de pH.*
- [x] El motor muestra la referencia y ningún cultivo cambia de estado por ella. *Verificado sin internet: `test_ph_de_los_perfiles_del_inta_es_segunda_referencia_y_no_decide` (rama del motor).*
- [ ] Hernán aprobó esta spec.
