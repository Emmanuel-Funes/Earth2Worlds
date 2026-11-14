# Spec 021 — Integración ampliada de GeoINTA / Catálogo INTA

**Proyecto:** Rotaterra (Earth2Worlds)  
**Repositorio:** `hernanfirmapaz-ops/N4-4-1.2`  
**Estado:** **Aprobada por Hernán** ("aprubo el spec021", 19:35), incluidas las tablas de códigos y los supuestos de §23. La implementación de prioridad 1 y 2 también la aprobó él ese día. El PR no se une sin su orden explícita.  
**Fecha:** 4 de octubre de 2026  
**Dependencia:** Spec 020 — GeoINTA  
**Fuente:** https://geo-backend.inta.gob.ar/catalogue/

---

## 1. Propósito

Ampliar la integración de INTA dentro del pipeline de datos de Rotaterra utilizando el catálogo GeoINTA como fuente de información territorial y agroambiental complementaria a las fuentes satelitales y climáticas ya implementadas.

Esta spec **no crea un nuevo sistema satelital**.

GeoINTA debe considerarse una fuente institucional de información geográfica/agronómica de INTA que puede aportar:

- información de suelos;
- aptitud y capacidad de uso;
- zonificación agroecológica;
- información territorial;
- cartografía temática;
- otras capas oficiales de INTA que sean verificadas y relevantes para la rotación.

La integración debe mantener el principio actual:

```text
Fuentes externas
      ↓
conector independiente
      ↓
contrato Observacion
      ↓
pipeline Rotaterra
      ↓
app / motor de rotación
```

---

## 2. Estado actual que esta spec debe respetar

El proyecto ya posee un conector de GeoINTA en la Spec 020.

La implementación verificada actual registra para San Luis:

- índice de productividad: 50;
- no se obtuvo clase de uso porque no existe carta 1:50.000 disponible para ese lote;
- el lote de control de Pergamino obtuvo índice 95 y clase I.

Por lo tanto, esta spec **no reemplaza la Spec 020**.

Su objetivo es descubrir, validar y eventualmente incorporar datasets adicionales del catálogo GeoINTA sin romper el contrato existente.

---

## 3. Principios obligatorios

### 3.1 Fuente institucional

GeoINTA/INTA está permitido por la política actual de fuentes del proyecto.

No debe reemplazarse por SoilGrids ni por otra fuente no autorizada.

### 3.2 No inventar cobertura

Que un dataset aparezca en el catálogo no significa que:

- cubra todo el territorio argentino;
- tenga cobertura para el lote consultado;
- tenga resolución suficiente;
- esté disponible mediante una API pública;
- pueda consultarse automáticamente;
- tenga una escala adecuada para decisiones a nivel de lote.

Cada dataset debe verificarse antes de incorporarse.

### 3.3 No confundir escala regional con información de lote

La resolución o escala de cada capa debe conservarse.

Una capa regional puede utilizarse como contexto, pero no debe presentarse como medición directa del lote.

### 3.4 Mantener trazabilidad

Cada observación debe indicar su fuente y, cuando corresponda, dataset/capa.

---

# 4. Objetivo funcional

Cuando Rotaterra consulte información territorial/agronómica para un lote:

1. identificar la geometría del lote;
2. identificar qué datasets de GeoINTA podrían cubrirlo;
3. consultar únicamente datasets previamente verificados;
4. extraer la información disponible;
5. convertirla al contrato común de Rotaterra;
6. registrar fuente, dataset, fecha y calidad;
7. devolver `null` cuando el dato no esté disponible;
8. conservar la razón de descarte o ausencia.

---

# 5. Fase 1 — Inventario del catálogo

Antes de programar nuevos conectores se debe realizar un inventario de GeoINTA.

Para cada dataset se debe registrar:

| Campo | Descripción |
|---|---|
| `dataset_id` | Identificador del dataset |
| `nombre` | Nombre oficial |
| `descripcion` | Descripción oficial |
| `organismo` | INTA / unidad responsable |
| `tipo` | vector, raster, documento, mapa, etc. |
| `variable` | qué representa |
| `cobertura` | área geográfica |
| `escala` | escala publicada |
| `resolucion` | resolución espacial, si existe |
| `fecha` | fecha o período |
| `formato` | GeoTIFF, Shapefile, WMS, WFS, API, etc. |
| `acceso` | público/restringido |
| `endpoint` | URL técnica, si existe |
| `automatizable` | sí/no |
| `utilidad_rotacion` | alta/media/baja |
| `estado_verificacion` | pendiente/verificado/descartado |

**Importante:** no completar campos técnicos mediante suposiciones.

---

# 6. Fase 2 — Clasificación para Rotaterra

Los datasets descubiertos deben clasificarse en cuatro grupos.

## A. Suelo

Ejemplos potenciales:

- índice de productividad;
- capacidad de uso;
- clases de suelo;
- textura;
- limitaciones;
- profundidad;
- salinidad;
- sodicidad;
- materia orgánica, si existe y está oficialmente disponible.

## B. Agroecología

Ejemplos potenciales:

- zonificación agroecológica;
- aptitud de tierras;
- ambientes productivos;
- regiones agroecológicas.

## C. Territorio

Ejemplos potenciales:

- límites;
- unidades cartográficas;
- coberturas;
- información geográfica auxiliar.

## D. Contexto

Información útil para análisis, pero que no debe convertirse automáticamente en una recomendación agronómica.

---

# 7. Modelo de datos

El conector debe adaptarse al contrato ya existente:

```python
Observacion(
    lote_id,
    fecha,
    variable,
    valor,
    unidad,
    fuente,
    resolucion_m,
    calidad,
    nota
)
```

No crear un segundo contrato paralelo.

Cuando el dato sea categórico, `valor` puede representar el valor normalizado y `nota` conservar la descripción oficial.

Ejemplo conceptual:

```json
{
  "lote_id": "SANLUIS-001",
  "fecha": null,
  "variable": "indice_productividad_suelo",
  "valor": 50,
  "unidad": "indice",
  "fuente": "GeoINTA",
  "resolucion_m": null,
  "calidad": "verificada",
  "nota": "Dataset y escala registrados en metadata de GeoINTA"
}
```

Si no existe el dato:

```json
{
  "valor": null,
  "calidad": "descartada",
  "nota": "No existe cobertura disponible para el lote consultado"
}
```

---

# 8. Identidad de la fuente

No usar simplemente:

```text
fuente = "INTA"
```

cuando sea posible especificar el dataset.

Preferir:

```text
fuente = "GeoINTA:<dataset>"
```

o la convención que finalmente defina el conector.

Esto permite distinguir, por ejemplo:

```text
GeoINTA:indice_productividad
GeoINTA:capacidad_uso
GeoINTA:zonificacion_agroecologica
```

---

# 9. Arquitectura

GeoINTA debe seguir el mismo patrón de fuentes independientes.

```text
rotaterra/
└── fuentes/
    └── geointa.py
```

Si la Spec 020 ya contiene este archivo, **no crear otro conector paralelo**.

En ese caso:

```text
Spec 020
   ↓
conector GeoINTA existente
   ↓
Spec 021
   ↓
extensiones / nuevos datasets verificados
```

La integración debe permanecer desacoplada del núcleo.

El núcleo no debe conocer nombres internos de datasets de GeoINTA.

---

# 10. Descubrimiento vs. integración

Esta spec separa explícitamente dos actividades.

## Descubrimiento

Determinar:

- qué datasets existen;
- qué representan;
- dónde cubren;
- qué escala tienen;
- cómo se acceden;
- si tienen interfaz automatizable;
- si son útiles para Rotaterra.

## Integración

Solamente después de verificar un dataset:

```text
Catálogo
  ↓
Dataset identificado
  ↓
Metadata verificada
  ↓
Cobertura verificada
  ↓
Acceso técnico verificado
  ↓
Prueba con lote real
  ↓
Contrato Observacion
  ↓
PR
```

---

# 11. Criterios de aceptación

## SAT-INTA-001 — Catálogo identificado

**DADO** el catálogo oficial de GeoINTA  
**CUANDO** se realiza el inventario  
**ENTONCES** cada dataset candidato debe tener nombre, descripción, cobertura y mecanismo de acceso documentados.

## SAT-INTA-002 — Cobertura

**DADO** un dataset candidato  
**CUANDO** se consulta el lote de prueba  
**ENTONCES** el sistema debe determinar si existe cobertura real para ese lote.

## SAT-INTA-003 — Fuente

**DADO** un valor obtenido desde GeoINTA  
**CUANDO** se genera `Observacion`  
**ENTONCES** debe conservarse la identificación de GeoINTA y del dataset cuando esté disponible.

## SAT-INTA-004 — Ausencia

**DADO** que GeoINTA no posee información aplicable al lote  
**CUANDO** se realiza la consulta  
**ENTONCES** el resultado debe ser `valor: null`, `calidad: "descartada"` y una `nota` explicativa.

## SAT-INTA-005 — Escala

**DADO** un dataset con escala insuficiente para representar el lote  
**CUANDO** se procesa  
**ENTONCES** el sistema no debe presentarlo como medición directa del lote.

## SAT-INTA-006 — Datos reales

Ningún criterio debe marcarse como `[x]` hasta haber sido probado con datos reales y documentado con los valores obtenidos.

---

# 12. Variables prioritarias

La prioridad inicial será:

### Prioridad 1

- índice de productividad del suelo;
- capacidad de uso;
- clases/aptitud de suelo;
- información edáfica directamente aplicable al lote.

### Prioridad 2

- zonificación agroecológica;
- limitaciones del suelo;
- unidades ambientales.

### Prioridad 3

- otras capas de INTA que aporten información útil al modelo de rotación.

No se debe incorporar una variable solamente porque esté disponible.

Debe responder a una necesidad del modelo de rotación.

---

# 13. Integración con el pipeline existente

El resultado final debe poder combinarse con las fuentes actuales:

```text
                    ROTATERRA
                        │
              ┌─────────┴─────────┐
              │                   │
       Datos satelitales     Datos territoriales
              │                   │
       ┌──────┴──────┐       ┌────┴─────┐
       │             │       │          │
   Sentinel-2      HLS     GeoINTA    DEM
   Landsat        VIIRS      │
   MODIS                    suelo
   SMAP                     aptitud
   ECOSTRESS                etc.
       │                      │
       └──────────┬───────────┘
                  ↓
          Observacion común
                  ↓
        información del lote
                  ↓
          Motor de rotación
```

---

# 14. Relación con la IA

GeoINTA **no debe generar directamente la recomendación de cultivo**.

Su función es proporcionar variables de contexto.

Por ejemplo:

```text
GeoINTA
   ↓
Suelo / aptitud / ambiente
   ↓
Feature del lote
   ↓
Modelo de rotación
```

La recomendación final deberá combinar esta información con:

- historial de cultivos;
- clima;
- precipitaciones;
- humedad;
- índices de vegetación;
- evapotranspiración;
- manejo;
- rendimiento;
- reglas agronómicas;
- restricciones definidas por el productor/agronomía.

---

# 15. Compatibilidad con las reglas actuales

Esta spec debe respetar:

- primero spec, después código;
- ningún PR se une sin autorización explícita;
- no crear base de datos ahora;
- fuentes independientes;
- pruebas unitarias sin internet;
- pruebas reales separadas;
- secretos únicamente en GitHub;
- no inventar valores;
- mantener trazabilidad;
- actualizar `Proyect-context.md` en el mismo PR.

---

# 16. Rama y PR

Si la implementación se aprueba:

**Rama:**

```text
GEOINTA-INFORMACIÓN
```

**Título:**

```text
GEOINTA - capas territoriales y agronómicas verificadas
```

**Workflow:**

```text
Probar GEOINTA (información)
```

La descripción del PR debe comenzar con:

```text
Antes:
GeoINTA aporta únicamente las variables verificadas en Spec 020.

Después:
Se incorporan únicamente los datasets adicionales de GeoINTA
que fueron descubiertos, documentados y probados con datos reales.
```

---

# 17. Tareas

## TASK-001 — Inventariar GeoINTA

- [x] Revisar catálogo.
- [x] Registrar datasets candidatos.
- [x] Registrar metadata.
- [x] Registrar cobertura.
- [x] Registrar escala.
- [x] Registrar acceso técnico.
- [x] No implementar todavía.

## TASK-002 — Seleccionar datasets

- [x] Clasificar por suelo/agroecología/territorio/contexto.
- [x] Seleccionar variables relevantes para rotación.
- [x] Justificar cada selección.

## TASK-003 — Verificar acceso

- [x] Determinar si existe API.
- [x] Determinar si existe WMS/WFS.
- [x] Determinar si existe descarga.
- [x] Verificar autenticación.
- [x] Documentar mecanismo real.

## TASK-004 — Probar con lote real

Usar el lote de prueba actual:

```text
San Luis
esquinas:
-33,700 / -65,300
-33,705 / -65,295

superficie:
25,7 ha
```

## TASK-005 — Extender conector

Solo para datasets aprobados.

## TASK-006 — Tests

- [x] tests sin internet;
- [x] respuestas simuladas;
- [x] cobertura inexistente;
- [x] `null` correcto;
- [x] metadata correcta;
- [x] fuente correcta.

## TASK-007 — Prueba real

Ejecutar workflow real en GitHub Actions.

Registrar:

- fecha;
- dataset;
- lote;
- valores;
- resolución/escala;
- resultado;
- errores;
- limitaciones.

## TASK-008 — Actualizar contexto

Actualizar `Proyect-context.md` con:

- nuevos datasets;
- resultados reales;
- PR;
- limitaciones;
- nuevas variables;
- cambios de arquitectura.

---

# 18. Lo que NO hace esta spec

Esta spec no:

- crea una base de datos;
- cambia el contrato `Observacion`;
- reemplaza Sentinel-2;
- reemplaza NASA;
- agrega SoilGrids;
- crea un modelo de IA;
- genera recomendaciones de cultivo;
- modifica la arquitectura principal;
- une PR automáticamente.

---

# 19. Definición de terminado

La integración se considera terminada cuando:

- [x] el dataset está identificado oficialmente;
- [x] su cobertura está verificada;
- [x] su escala/resolución está documentada;
- [x] su acceso técnico está probado;
- [x] el lote de prueba fue consultado;
- [x] los valores reales están documentados;
- [x] el dato se adapta a `Observacion`;
- [x] existen tests sin internet;
- [x] existe una prueba real;
- [x] la fuente queda identificada;
- [x] las limitaciones quedan documentadas;
- [x] `Proyect-context.md` fue actualizado;
- [x] Hernán revisó el PR y aprobó la spec;
- [ ] Hernán autorizó explícitamente la unión (todavía no: por ahora no quiere unir nada a `main`).

---

# 20. Resultado esperado

El resultado de esta etapa no es simplemente “tener INTA conectado”.

El resultado esperado es que Rotaterra pueda construir una representación más completa de cada lote:

```text
                 LOTE
                  │
        ┌─────────┼─────────┐
        ↓         ↓         ↓
    Satélite   Clima     GeoINTA
        │         │         │
        ↓         ↓         ↓
 Vegetación   Agua/temp   Suelo
        │         │       Aptitud
        │         │       Ambiente
        └─────────┼─────────┘
                  ↓
          PERFIL DEL LOTE
                  ↓
        MOTOR DE ROTACIÓN
                  ↓
        RECOMENDACIÓN
```

GeoINTA aporta el componente territorial/agronómico que no debe confundirse con una observación satelital.

El objetivo final es que las fuentes puedan evolucionar independientemente sin modificar el núcleo de Rotaterra.

---

# 21. Notas para que encaje con el repositorio

Se agregaron al sumar la spec. No cambian lo que pide la spec; aclaran cómo se aplica con el contrato y las convenciones que ya existen.

| Punto de la spec | Cómo se aplica | Por qué |
|---|---|---|
| §7: `"calidad": "verificada"` | Se usa `buena`, `dudosa` o `descartada`. | Son los únicos valores que acepta `Observacion` (`rotaterra/contrato.py`). |
| §7: `"fecha": null` | La fecha es la de la versión digital de la carta, como en la spec 020 (Atlas: 2013-01-07; Buenos Aires: 2023-04-17). | `fecha` es obligatoria en el contrato. |
| §7: `"resolucion_m": null` | Se calcula desde la escala: 0,5 mm del mapa (1:500.000 da 250 m; 1:50.000 da 25 m), como en la spec 020. | `resolucion_m` es obligatoria. La regla queda anotada como supuesto en la `nota`. |
| §8: `fuente = "GeoINTA:<dataset>"` | `fuente` sigue siendo `"GeoINTA"`. El dataset queda en el nombre de la `variable` y en la `nota` (capa, escala y versión). | `fuente` es una lista cerrada del contrato, y `PRIORIDAD` la usa para combinar. Cambiarla tocaría el núcleo, cosa que esta spec descarta (§9 y §18). La spec deja elegir la convención del conector. |
| §16: rama `GEOINTA-INFORMACIÓN` | Rama `GeoINTA-capas_verificadas`, con el mismo nombre de fuente que la spec 020. | Convención `SATÉLITE-INFORMACIÓN`. |
| §17 TASK-001 a 004 | Se hacen con el workflow `Probar GeoINTA (inventario del catálogo)` (`inventariar_geointa.py`). Solo lee el catálogo y los servicios OGC, y no integra nada. | El entorno de la IA no llega a los servidores del INTA (el proxy responde 403), así que todo lo real corre en GitHub Actions. |

# 22. Inventario (fase 1)

Hecho con el workflow `Probar GeoINTA (inventario del catálogo)`, que solo lee. Corrida final: [37209660091](https://github.com/hernanfirmapaz-ops/N4-4-1.2/actions/runs/37209660091) (la primera, 37209193021, contó el catálogo). Lote de prueba: San Luis, centro -33,7025 / -65,2975.

Lo que el catálogo no publica queda como "no publicado". Los valores del lote son los que devolvió el servidor, sin redondear ni interpretar más allá de la leyenda que publica la misma capa.

## 22.1 Qué hay en el catálogo

| Dato | Resultado |
|---|---|
| Recursos publicados | 237 (`/api/v2/resources`) |
| Por tipo | 83 ráster, 59 remotos (servidos por otros nodos del INTA), 31 vectoriales, 39 presentaciones, 25 archivos |
| Servicios del nodo central | 30 capas WFS y 66 coberturas WCS en `https://geo-backend.inta.gob.ar/geoserver/ows`; WMS para todas las capas |
| Nodos remotos con capas | `geo-nodo05`, `geo-nodo08` y `geo-nodo15.inta.gob.ar/geoserver/ows` (WMS) |
| Autenticación | Ninguna. Todo se consultó sin usuario ni clave. |
| Fuera de la extensión del lote | 94 recursos (su recuadro no incluye el lote) |
| No automatizables | Las 64 presentaciones y archivos (informes, PDF, descargas sueltas) |

## 22.2 Candidatos con dato real en el lote

"Valor en el lote" es la respuesta del servidor en el centro del lote (WMS `GetFeatureInfo`) o las unidades que tocan el polígono (WFS con filtro `INTERSECTS`).

| id | Dataset | Grupo | Variable | Escala / resolución | Fecha | Acceso | Valor en el lote | Utilidad para la rotación |
|---|---|---|---|---|---|---|---|---|
| 750 | Suelos Villa Mercedes, San Luis | Suelo | unidad, capacidad de uso, índice de productividad | 1:100.000 | 2025-09-22 (alta en el catálogo) | WMS `geo-nodo15`, capa `geonode:villamercedes_v0` | UC `Cr`, capacidad de uso **VIes**, IP **50** | Alta |
| 230 | Suelos de la República Argentina (Atlas v9) | Suelo | unidad, IP, limitaciones, suelo dominante | 1:500.000 | 2013-01-07 | WFS y WMS central (ya usado en la spec 020) | `EPtc-1`, Ustortentes típico, franco arenosa, drenaje algo excesivo, limitación climática y erosión eólica, IP 50 | Alta (ya integrado) |
| 692, 693, 691, 694 | Clases texturales 0-15, 15-30, 30-60 y 60-100 cm | Suelo | clase textural | no publicada | 2024-12-10 | WMS `geo-nodo05` | código 8, 8, 9 y 8: **franco arenoso** en las cuatro (la capa de 30-60 cm usa otra leyenda, donde 9 es franco arenoso) | Alta |
| 689, 690 | Mapa de pH del suelo 0-30 y 30-100 cm | Suelo | pH | píxel de 1 km; ajuste RMSE 0,84, R² 0,456 | 2024-12-09 | WMS `geo-nodo05` | **8,56** y **8,48** | Media (modelo de 1 km con error de ±0,84) |
| 487 | Almacenamiento de carbono 2023 | Suelo | carbono orgánico del suelo | no publicada | 2023-10-27 | WMS y WCS central | 37,13 (unidad no publicada en el resumen) | Media |
| 700 | Almacenamiento de carbono 2018 | Suelo | carbono orgánico 0-30 cm | no publicada | 2024-12-30 | WMS `geo-nodo05` | 30,94 Mg/ha | Baja (lo reemplaza el de 2023) |
| 479, 481, 482, 488 a 491, 496, 497, 687, 688 | Mapa Nacional de Cultivos 2018/19 a verano 2023/24 | Territorio | cultivo por campaña | 30 m | 2023-10-19 a 2024-10-31 | WMS y WCS central | 2018/19 vegetación natural leñosa; 2019 a 2022 no agrícola; invierno 2022 barbecho; verano 2022/23 **maíz**; invierno 2023 barbecho; verano 2023/24 **soja** | Alta (historia real del lote) |
| 121 | Cobertura del suelo 2006-2007 (LCCS-FAO) | Territorio | cobertura | 1:500.000 | 2022-12-13 | WFS y WMS central | Cultivos de herbáceas graminoideas | Baja |
| 113, 111, 112, 133 a 206 | Atlas climático digital (Bianchi y Cravero) | Contexto | lluvia normal anual y mensual, ETP mensual, P-EP, aridez | no publicada | 2022-12 a 2023-03 | WMS y WCS central | lluvia anual 673 mm; balance P-EP -135 mm; Martonne 25 (subhúmedo); ETP enero 138 mm | Media (normales para comparar; el dato diario ya lo dan POWER e IMERG) |
| 667, 665 | Humedales (Pampa Interior, Monte Central) | Contexto | probabilidad de humedal | no publicada | 2024-08-28 | WMS y WCS central | 0,10 y 0 | Baja |
| 737, 736, 735 | Pequeños productores (CNA 2018) | Contexto | proporción por departamento | departamento | 2025-07-29 | WMS `geo-nodo05` | Departamento General Pedernera, 39,96 % de EAP de pequeños productores | Baja |

## 22.3 Sin dato en el lote

| id | Dataset | Qué devolvió |
|---|---|---|
| 723, 724, 725, 726 | Secuencias de cultivos, intensidad de siembra, número de cereales y soja de primera (2018/19 a 2023/24) | Código 255, que no está en la leyenda: el lote quedó fuera del análisis. Coincide con el Mapa Nacional de Cultivos, que lo marca no agrícola hasta 2022. |
| 702 | Perfiles de suelos Sisinta | Ningún perfil en el lote (es una capa de puntos). |
| 680 a 684 | Suelos, aptitud de riego, cartas y ambientes de Córdoba | 0 unidades: el recuadro llega a San Luis, pero el mapa no. |
| 744 a 749 | Las otras hojas de suelos de San Luis (San Luis, Buena Esperanza, Concarán, Arizona, Martín de Loyola, Villa General Roca) | Fuera de su extensión. Sirven para lotes en otras partes de la provincia. |
| 292, 332, 123 | Zonificación agroecológica y zonas agroeconómicas | Solo existen para Salta, Jujuy y el NOA. **No hay zonificación agroecológica que cubra San Luis.** |
| 755, 742 | Laboratorios del INTA, Sistemas Participativos de Garantía | No aportan a la rotación. |

## 22.4 Propuesta para que Hernán apruebe

Nada de esto se implementa hasta que Hernán lo apruebe (TASK-005).

| Prioridad | Dataset | Por qué |
|---|---|---|
| 1 | Cartas de suelos 1:100.000 de San Luis (744 a 750) | Dan la **capacidad de uso** que hoy falta en San Luis (en el lote: VIes) y un IP a mayor detalle que el Atlas. El conector elige la hoja que cubre el lote. |
| 1 | Clases texturales a 4 profundidades (691 a 694) | La textura define agua útil y riesgo de erosión eólica, clave para elegir entre maíz, soja, girasol o pasturas. |
| 2 | Mapa Nacional de Cultivos (11 campañas) | Es la historia real de cultivos del lote, lo que necesita el motor de rotación para no repetir cultivo. |
| 2 | pH 0-30 y 30-100 cm | Útil como alerta de alcalinidad, siempre aclarando que es un modelo de 1 km. |
| 3 | Carbono orgánico 2023 | Contexto de salud del suelo. Falta confirmar la unidad. **Integrado** a pedido de Hernán; la unidad quedó confirmada (t/ha, 0-30 cm, §23.6). |
| No | Atlas climático, humedales, censo, cobertura 2007 | Contexto o dato que ya dan otras fuentes. |

## 22.5 Criterios

- SAT-INTA-001 (catálogo identificado): cumplido para los candidatos de 22.2 y 22.3.
- SAT-INTA-002 (cobertura): cumplido con el lote de San Luis.
- SAT-INTA-003 a 005: corresponden al conector, después de la aprobación.

# 23. Integración aprobada (prioridad 1 y 2)

Hernán eligió "Prioridad 1 y 2": cartas 1:100.000 de San Luis, textura, Mapa Nacional de Cultivos y pH. El mismo día sumó el [anexo de geoservicios](021-anexo-geoservicios.md), que pide WFS para vectores, WCS para rásters y WMS solo para ver.

El 15/10/2026 Hernán pidió "necesito que conectes a los datasets de INTA". La única capa del INTA que faltaba para el lote de San Luis era la de prioridad 3, el carbono orgánico 2023, y se sumó (§23.6).

## 23.1 Cómo se lee cada capa

| Capa | Servicio y nodo | Variable | Valor |
|---|---|---|---|
| Hojas de suelo de San Luis (7 hojas: Villa Mercedes, San Luis, Buena Esperanza, Concarán, Martín de Loyola y Varela, Arizona a 1:100.000; Villa General Roca a 1:200.000) | WFS del nodo 15 (`geo-nodo15.inta.gob.ar/geoserver/wfs`) | `suelo_clase_capacidad_uso` (la misma de Buenos Aires) y `suelo_indice_productividad_detallado` | clase 1 a 8 e IP 0-100 de la unidad dominante, por muestreo de puntos como en la spec 020 |
| Mapa Nacional de Cultivos, 13 campañas (2018/19 a verano 2024/25) | 2018/19 a verano 2023/24: WCS del nodo Nacional (`geo-backend.inta.gob.ar/geoserver/wcs`), GeoTIFF recortado al lote; leyenda por WMS `GetLegendGraphic`. Invierno 2024 y verano 2024/25: GeoTIFF de GeoSEPA leído por rangos (§23.4) | `cultivo_mnc_verano`, `cultivo_mnc_invierno` y `cultivo_mnc_campana` (la 2018/19 es un solo mapa) | código común del cultivo dominante; el reparto completo va en la `nota` |
| Carbono orgánico del suelo 2023 (recurso 487) | WCS del nodo Nacional (`geo-backend.inta.gob.ar/geoserver/wcs`), cobertura `geonode:Mapa_COS_Nacional`, GeoTIFF recortado al lote | `suelo_carbono_organico_0_30cm_t_ha` | media de los píxeles de ~250 m con centro en el lote, en t/ha; cantidad de píxeles y rango en la nota (§23.6) |
| Textura (4 profundidades) y pH (2) | WMS `GetFeatureInfo` del nodo 05 (`geo-nodo05.inta.gob.ar/geoserver/wms`): no están en su WCS ni WFS, y Hernán eligió leerlos por WMS | `suelo_textura_0_15cm`, `_15_30cm`, `_30_60cm`, `_60_100cm`; `suelo_ph_0_30cm`, `suelo_ph_30_100cm` | textura: código común de la clase dominante en una grilla de 3 × 3 puntos; pH: media de los puntos, con mínimo y máximo en la nota |

El conector elige la hoja de San Luis con la extensión publicada de cada una (sin consultar nada). Si el lote no está en San Luis, usa la carta 1:50.000 de Buenos Aires, como antes.

## 23.2 Código común de cultivos

Cada campaña publica su propia leyenda (la soja es 1 en 2018/19 y 11 después), así que el conector traduce por el **nombre de la clase** que trae la leyenda de esa misma capa. Una clase que no está en la tabla queda `descartada` con su nombre en la nota; nunca se adivina.

| Código | Clase | Código | Clase |
|---|---|---|---|
| 1 | Maíz | 20 | Cereales de invierno |
| 2 | Soja | 21 | Cultivo de invierno (sin especificar) |
| 3 | Girasol | 22 | Garbanzo |
| 4 | Sorgo | 23 | Arveja |
| 5 | Maní | 24 | Otros cultivos (de invierno) |
| 6 | Poroto | 30 | Cultivo de invierno - soja (2018/19) |
| 7 | Algodón | 31 | Cultivo de invierno - maíz (2018/19) |
| 8 | Arroz | 32 | Girasol - cultivo de verano |
| 9 | Caña de azúcar | 40 | Barbecho |
| 10 | Papa | 41 | No agrícola |
| 11 | Tabaco | 42 | Ganadería |
| 12 | Verdeo de sorgo | 43 | Vegetación natural leñosa |
| 13 | Verdeo de maíz (desde 2024/25) | | |
| | | 44 | Plantaciones forestales y frutales |
| | | 45 | Vegetación leñosa implantada |

"Zonas enmascaradas", "Limite", "Máscara" y los códigos que no están en la leyenda (como 255) no son una clase: no cuentan para el dominante y se informan como "sin clasificar".

La textura sigue la misma regla. Cada profundidad tiene su leyenda (el 9 es "Limoso" a 0-15 cm y "Franco arenoso" a 30-60 cm), así que se traduce por nombre a un código común de grueso a fino:

| Código | Clase | Código | Clase |
|---|---|---|---|
| 1 | Arenoso | 7 | Franco arcillo arenoso |
| 2 | Areno franco | 8 | Franco arcilloso |
| 3 | Franco arenoso | 9 | Franco arcillo limoso |
| 4 | Franco | 10 | Arcillo arenoso |
| 5 | Franco limoso | 11 | Arcillo limoso |
| 6 | Limoso | 12 | Arcilloso |
| | | 13 | Franco o franco limoso (clase combinada de 30-60 cm) |

"Miscelánea" no es una clase de textura y en el pH (código 101) tampoco cuenta.

## 23.4 Campaña 2024/25 desde GeoSEPA (agregado)

Hernán encontró el Mapa Nacional de Cultivos verano 2024/25 (`MNC_verano_2024-2025.tif`, 193 MB). No está en el WCS de GeoINTA: el INTA lo publica en **GeoSEPA** (`sepa.inta.gob.ar/productos/geosepa/Mapa_Nacional_Cultivo/tif/`), junto con el de invierno 2024 (`listar_archivos_MNC.php` lista 2019/20 a 2024/25, invierno y verano).

- **Cómo se lee:** el servidor de SEPA es muy lento para bajar el archivo entero, pero acepta rangos de bytes. El conector abre el GeoTIFF con `/vsicurl/` y lee solo la ventana del lote (en el archivo local, 0,2 a 0,6 s). Cuentan los píxeles con el centro dentro del lote, como en el WCS.
- **Leyenda:** GeoSEPA no tiene `GetLegendGraphic`; se usan sus archivos `MNC_verano.qml` y `MNC_invierno.qml`. Verano: 10 Maíz, 11 Soja, 12 Girasol, 13 Poroto, 14 Caña de azúcar, 15 Algodón, 16 Maní, 17 Arroz, 18 Sorgo, 19 Girasol-CV, 21 Barbecho, 22 No agrícola, 26 Papa, 27 Verdeo de maíz, 28 Verdeo de sorgo, 30 Tabaco, 31 Máscara. Invierno: 6 Garbanzo, 16 Cereales de invierno, 17 Otros cultivos de invierno, 18 Barbecho, 19 Caña de azúcar, 20 No agrícola, 24 Arveja, 25 Máscara, 26 Papa. Se traducen al código común de §23.2 por el nombre, igual que las demás.
- **Nombre del archivo de invierno:** `MNC_invierno_2024-2025.tif`, igual que el de verano. Se supuso por analogía y la prueba real confirmó que existe.
- **Uso:** al venir de GeoSEPA, rigen los términos de SEPA (uso comercial con autorización escrita del CIRN-INTA, spec 023 §5.3). La `nota` lo dice.
- **Verificado en la prueba real (GitHub, 4/10/2026, leído de GeoSEPA por rangos):** lote de San Luis, verano 2024/25 **maíz 52 %** y no agrícola 48 % (324 píxeles), `buena` por poco; invierno 2024 **barbecho 52 %**. Pergamino: verano 2024/25 **soja 64 %** (no agrícola 20 %, maíz 16 %); invierno 2024 **barbecho 74 %**. Con el archivo que subió Hernán dio lo mismo. Cada lote tarda 17 a 18 s con las 13 campañas.
- **Tope de tiempo (agregado):** en la prueba del piloto con parcelas reales del Catastro, la lectura de GeoSEPA quedó trabada más de una hora en dos parcelas de San Luis (Justo Daract, 456 ha, y Buena Esperanza, 196 ha), y la consulta del suelo no volvía nunca. Ahora todo el Mapa Nacional de Cultivos tiene un tope de 90 s: las campañas que no llegan quedan `descartada` con la `nota` "no respondió en 90 s" y el resto del suelo contesta igual. Además, GDAL corta un rango que baja a menos de 1000 bytes por segundo durante 15 s.

## 23.3 Supuestos

- **Fecha de cada campaña:** la de verano se fecha el 1 de enero del año de cosecha (verano 2023/24 → 1/1/2024), la de invierno el 1 de julio y la 2018/19 el 1/1/2019. Los títulos del INTA solo dicen la campaña.
- **Fecha de las hojas de San Luis:** la de alta de la versión digital en el catálogo (19 y 22/9/2025). El relevamiento original es anterior.
- **Resolución de las hojas:** 0,5 mm del mapa, como en la spec 020 (1:100.000 da 50 m; 1:200.000, 100 m).
- **Píxel del Mapa de Cultivos:** 0,000269° (DescribeCoverage), unos 30 m.
- **Resolución de la textura:** no está publicada; se toma 1 km, la del pH (mismo proyecto y autor). El pH sí publica 1 km.
- **Fecha de textura y pH:** la de alta en el catálogo (10 y 9/12/2024). Son mapas de modelo, no mediciones: la nota lo dice, y el pH lleva su error publicado (RMSE 0,84; R² 0,456).
- **Calidad:** `buena` si la clase o unidad dominante cubre al menos la mitad del lote (en el pH, si al menos la mitad de los puntos tiene dato); si no, `dudosa`.

## 23.4 Prueba real

Workflow `Probar GeoINTA (suelos y cultivos)`, corridas [37210945085](https://github.com/hernanfirmapaz-ops/N4-4-1.2/actions/runs/37210945085) (cartas y cultivos) y [37211263016](https://github.com/hernanfirmapaz-ops/N4-4-1.2/actions/runs/37211263016) (todo, con textura y pH). Cada campaña contó 361 píxeles de 30 m en el lote de 25,7 ha.

| Lote | Suelo | Cultivos (dominante y reparto) |
|---|---|---|
| San Luis | Hoja Villa Mercedes 1:100.000: unidad Cr, clase **VI** (subclase es), IP 50. Atlas: IP 50. Textura **franco arenosa** en las 4 profundidades (9 de 9 puntos). pH **8,53** (0-30 cm, de 8,47 a 8,56) y **8,48** (30-100 cm). | 2018/19 vegetación natural leñosa 51 % (soja 47 %). 2019 a 2023: no agrícola 53-86 %, con barbecho, soja o maíz en el resto. Invierno 2023 barbecho 52 %. Verano 2023/24 **dudoso**: no agrícola 48 %, soja 46 %, maíz 6 %. |
| Pergamino (control) | Carta 1:50.000: Pe4, clase **I**. Atlas: IP 95. Textura franco limosa (0-30 cm) y franco arcillo limosa (30-100 cm), igual que el Atlas. pH **6,19** y **6,87**. | 2018/19 soja 70 %. Veranos: soja (2019/20), maíz (2020/21), soja (2021/22, 2022/23, 2023/24 con 65 %). Inviernos: cereales 2019, barbecho 2020-2022, cereales 45 % en 2023 (dudoso). |

El punto central del lote de San Luis daba soja en 2023/24 (inventario, §22.2); el recorte por WCS muestra que es casi mitad y mitad, y por eso queda `dudosa`.

## 23.5 Criterios

- SAT-INTA-003 (fuente): `fuente = "GeoINTA"` y la nota trae nodo, servicio, capa, escala y versión. Verificado en la prueba real.
- SAT-INTA-004 (ausencia): sin unidad, fuera de la leyenda o sin respuesta → `valor: null`, `descartada` y la razón. Cubierto por los tests.
- SAT-INTA-005 (escala): la escala y la resolución van en `resolucion_m` y en la nota; el Mapa de Cultivos informa el reparto, no un único valor.
- SAT-INTA-006 (datos reales): los valores de 23.4 y, para el carbono, los de 23.6.

## 23.6 Carbono orgánico del suelo 2023 (agregado)

Hernán lo pidió ("necesito que conectes a los datasets de INTA"). Era la prioridad 3 de §22.4, la única capa del INTA con dato en el lote de San Luis que todavía no estaba integrada.

**De dónde sale.** Es el recurso 487 del catálogo GeoINTA, "Almacenamiento de Carbono - 2023". Lo hicieron Gaitán et al. (2023) para el INTA, Aapresid, CREA y la SAGyP, con un modelo Random Forest entrenado con muestras de 2015 a 2022. El ráster se publica como la cobertura `geonode:Mapa_COS_Nacional` en el WCS central (`https://geo-backend.inta.gob.ar/geoserver/wcs`). Su `gml:name` es "Argentina - Stock de Carbono en los Suelos - 2023".

**Unidad y profundidad (verificadas).** El resumen del recurso 487 (`/api/v2/resources/487`, campo `raw_abstract`) dice que el objetivo es "actualizar el mapa de almacenamiento de COS (0 – 30 cm, t/ha)". La variable es entonces el stock de carbono orgánico de 0 a 30 cm, en toneladas por hectárea. Se leyó en la prueba real (corridas [38730176751](https://github.com/hernanfirmapaz-ops/N4-4-1.2/actions/runs/38730176751) y [38731508056](https://github.com/hernanfirmapaz-ops/N4-4-1.2/actions/runs/38731508056), paso "Metadatos del carbono orgánico 2023 del INTA").
- El `DescribeCoverage` dice `uom code="W.m-2.Sr-1"`, que es el valor por defecto de GeoServer y no la unidad del dato. No se usa.
- La leyenda (`GetLegendGraphic`) es una rampa de 15 a 200 sin unidad.
- El documento 752 ("Raster - Almacenamiento de Carbono - 2023") es un ZIP de 165 MB con el GeoTIFF. No trae la unidad en sus metadatos.
- La versión 2018 (recurso 700) usa Mg/ha de 0-30 cm, que es lo mismo que t/ha.

**Cómo se lee.**
- Se pide por WCS 1.0.0 el GeoTIFF recortado a la caja del lote, con un píxel de margen, a la resolución nativa.
- Cuentan los píxeles con el centro dentro del lote. Si el lote es más chico que un píxel, cuentan los que toca. Es la misma función `pixeles_en_el_lote` del Mapa de Cultivos.
- El ráster es `float32` y no declara un valor de "sin dato". Por eso no cuentan los píxeles NaN, los de 0 o menos ni los de ±3,4e38 (el relleno de float32), porque ninguno es un stock posible.

**Regla de agregación.** Se usa la **media** de los píxeles válidos, redondeada a 2 decimales. La nota lleva la cantidad de píxeles, el mínimo y el máximo, y cuántos no tenían dato. Se eligió la media y no la mediana por dos razones:
- El mapa es una superficie continua y suave, sin clases ni valores sueltos.
- En un lote de 25 ha entran muy pocos píxeles (4 en San Luis), y con tan pocos la mediana no protege de nada.

El rango de la nota muestra si hay un píxel raro.

**Resolución, fecha y calidad.**
- `resolucion_m = 250`: el píxel es de 0,002245788° (`offsetVector` del `DescribeCoverage`), unos 250 m de latitud.
- `fecha = 2023-10-27`: la fecha de publicación del recurso 487 en el catálogo. Las muestras son de 2015 a 2022.
- La calidad es siempre `dudosa`. Es un modelo nacional, no una medición del lote. El resumen dice que se estimó la incertidumbre del modelo, pero el catálogo no publica ni el error ni la validación (remite al repositorio del INTA, handle 20.500.12123/14624). Sin una validación publicada no hay base para `buena`.
- Sin píxeles válidos, o si el WCS falla, el valor es `null` y la calidad `descartada`, con el motivo en la nota. Un error del WCS de carbono no frena el resto del suelo: es un paso aparte de `obtener_suelo`.

**Licencia.** El recurso 487 se publica bajo CC BY-NC-SA 2.5, que es de uso no comercial, y la nota lo dice. Hernán tiene que decidir si eso sirve para el uso que piensa darle a Rotaterra.

**Verificado en la prueba real** (corrida [38731508056](https://github.com/hernanfirmapaz-ops/N4-4-1.2/actions/runs/38731508056), 15/10/2026, commit `cf0b79f`):

| Lote | Carbono orgánico 0-30 cm | Píxeles | Rango |
|---|---|---|---|
| San Luis (-33,700 / -65,300) | **37,9 t/ha**, `dudosa` | 4 | 35,86 a 40,12 t/ha |
| Pergamino (control) | **54,66 t/ha**, `dudosa` | 4 | 53,13 a 56,77 t/ha |

En el inventario (§22.2), el punto central del lote de San Luis por WMS había dado 37,13, dentro del rango leído por WCS.

**Criterios de aceptación**
- [x] La unidad y la profundidad salen de una fuente del INTA: el resumen del recurso 487 dice "0 – 30 cm, t/ha" (corridas 38730176751 y 38731508056).
- [x] El conector lee la cobertura por WCS dentro del lote y entrega `suelo_carbono_organico_0_30cm_t_ha`. Los valores son `unidad = "t/ha"`, `fuente = "GeoINTA"`, `resolucion_m = 250` y `fecha = 2023-10-27`. La nota trae la cantidad de píxeles, el rango, la capa, la fuente de la unidad y la licencia. Dio San Luis 37,9 t/ha (4 píxeles, de 35,86 a 40,12) y Pergamino 54,66 t/ha (4 píxeles, de 53,13 a 56,77) en la corrida real.
- [x] Si no hay píxeles válidos, o el WCS falla o devuelve un GeoTIFF ilegible, el valor es `null` y la calidad `descartada` con el motivo, y el resto del suelo sigue saliendo. Lo cubren los tests sin internet de `tests/test_geointa.py`, con GeoTIFF reales en memoria.
- [x] `probar_geointa.py` imprime el carbono de los dos lotes y lo exige (`--exigir`). Con `--metadatos-carbono` imprime la unidad, la fecha, la licencia, el píxel y la leyenda que publica el INTA.
