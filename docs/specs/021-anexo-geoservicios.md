# Anexo — GeoINTA Geoservicios

**Proyecto:** Rotaterra (Earth2Worlds)  
**Repositorio:** `hernanfirmapaz-ops/N4-4-1.2`  
**Relacionado con:** `docs/specs/021-GeoINTA` y `Spec 020 — GeoINTA`  
**Fuente oficial:** https://geo.inta.gob.ar/geoservicios/  
**Fecha de verificación:** 4 de octubre de 2026

---

## 1. Objetivo

Documentar los geoservicios oficiales de INTA que pueden utilizarse como mecanismo técnico de acceso a información geoespacial para Rotaterra.

Este documento complementa la Spec 021.

No reemplaza la especificación ni crea un conector nuevo por sí mismo.

La finalidad es separar claramente:

```text
CATÁLOGO
¿Qué información existe?

GEOSERVICIOS
¿Cómo puede consumirse técnicamente?
```

---

## 2. Qué ofrece INTA Digital Geo

La página oficial de Geoservicios de INTA indica que INTA Digital Geo ofrece servicios en línea para acceder, compartir y manipular datos geoespaciales.

Actualmente documenta:

- **WMS (Web Map Service)**: mapas geoespaciales generados dinámicamente.
- **WFS (Web Feature Service)**: acceso a datos geoespaciales vectoriales.
- **WCS (Web Coverage Service)**: acceso a coberturas/datos raster.

Fuente oficial:

https://geo.inta.gob.ar/geoservicios/

---

## 3. Nodos oficiales identificados

La página de INTA publica un **Nodo Nacional** y distintos nodos regionales.

### Nodo Nacional

```text
WMS
https://geo-backend.inta.gob.ar/geoserver/wms

WFS
https://geo-backend.inta.gob.ar/geoserver/wfs

WCS
https://geo-backend.inta.gob.ar/geoserver/wcs
```

### Región La Pampa – San Luis

Este nodo es especialmente relevante para Rotaterra por el lote de prueba actual y por la zona inicial de trabajo.

```text
WMS
https://geo-nodo15.inta.gob.ar/geoserver/wms

WFS
https://geo-nodo15.inta.gob.ar/geoserver/wfs

WCS
https://geo-nodo15.inta.gob.ar/geoserver/wcs
```

La página oficial de INTA identifica expresamente `geo-nodo15` como:

> Región La Pampa – San Luis

---

## 4. Otros nodos regionales publicados

INTA también publica nodos para:

```text
CNIA – Centro Nacional de Investigaciones Agropecuarias
Región Buenos Aires
Región Catamarca – La Rioja
Región Chaco – Formosa
Región Córdoba
Región Corrientes
Región Entre Ríos
Región Mendoza – San Juan
Región Misiones
Región Patagonia Sur
Región Río Negro – Neuquén
Región Salta – Jujuy
Región Santa Fe
Región Santiago del Estero – Tucumán
```

Cada nodo dispone de servicios WMS, WFS y WCS según la página oficial.

---

## 5. Uso previsto en Rotaterra

### WMS

Uso principal:

- visualización;
- comprobación visual;
- apoyo al desarrollo;
- validación de que una capa cubre el lote;
- generación de mapas para futuras interfaces.

WMS no debe considerarse automáticamente el mecanismo principal para alimentar el modelo de IA.

---

### WFS

Uso principal:

- consultar entidades vectoriales;
- recuperar atributos;
- realizar consultas espaciales;
- intersectar geometrías de lotes con capas territoriales;
- obtener clases, categorías u otros atributos oficiales.

Para Rotaterra, WFS es candidato prioritario cuando la información requerida sea vectorial.

Ejemplo conceptual:

```text
Lote Rotaterra
      ↓
intersección espacial
      ↓
capa GeoINTA
      ↓
unidad cartográfica
      ↓
atributos INTA
      ↓
Observacion
```

---

### WCS

Uso principal:

- consultar datos raster;
- recuperar coberturas;
- trabajar con valores continuos;
- extraer estadísticas dentro del lote;
- obtener información espacial que no tenga sentido representar únicamente como atributos vectoriales.

Para Rotaterra, WCS es candidato prioritario cuando la información requerida sea raster.

Ejemplo conceptual:

```text
Lote Rotaterra
      ↓
consulta espacial
      ↓
raster GeoINTA
      ↓
valores dentro del lote
      ↓
media / mínimo / máximo / distribución
      ↓
Observacion
```

---

## 6. Arquitectura recomendada

Los geoservicios no deben ser llamados directamente desde la aplicación final.

La arquitectura debe ser:

```text
GeoINTA
   │
   ├── WMS
   ├── WFS
   └── WCS
        │
        ↓
   Conector GeoINTA
        │
        ↓
   Normalización
        │
        ↓
   contrato Observacion
        │
        ↓
   núcleo Rotaterra
        │
        ├── API
        └── futuras features / IA
```

El núcleo no debe conocer los endpoints concretos de GeoINTA.

---

## 7. Selección del nodo

El conector debe poder seleccionar el nodo apropiado según la cobertura del dataset.

Regla inicial:

```text
1. Dataset nacional disponible
        ↓
   usar Nodo Nacional

2. Dataset regional
        ↓
   usar nodo regional correspondiente

3. Para San Luis / La Pampa
        ↓
   priorizar nodo 15 cuando el dataset
   y su cobertura lo indiquen
```

Esto no significa que el nodo 15 deba sustituir automáticamente al Nodo Nacional.

La selección dependerá del dataset realmente publicado y de su cobertura.

---

## 8. Descubrimiento técnico

Antes de implementar una capa, el agente debe verificar:

- endpoint;
- tipo de servicio;
- versión OGC soportada;
- capas disponibles;
- nombre técnico de la capa;
- CRS;
- extensión geográfica;
- escala/resolución;
- atributos;
- restricciones de acceso;
- formato de respuesta;
- funcionamiento real.

No se debe asumir que todos los nodos ofrecen exactamente las mismas capas.

---

## 9. GetCapabilities

Para descubrir las capacidades del servicio deben utilizarse las operaciones estándar del servicio correspondiente cuando estén disponibles.

Ejemplos conceptuales:

```text
WMS → GetCapabilities
WFS → GetCapabilities
WCS → GetCapabilities
```

El sistema debe registrar la respuesta necesaria para identificar:

- capas;
- nombres técnicos;
- títulos;
- CRS;
- bounding boxes;
- formatos;
- operaciones soportadas.

Las URLs concretas de consultas deben generarse a partir de los endpoints verificados y no escribirse por suposición.

---

## 10. Regla de automatización

El pipeline debe preferir una consulta espacial sobre el lote antes que descargar innecesariamente una cobertura completa.

Objetivo:

```text
NO:

dataset completo
      ↓
descarga
      ↓
procesamiento
      ↓
buscar lote
```

Preferentemente:

```text
lote
 ↓
consulta espacial
 ↓
dataset
 ↓
respuesta limitada al área necesaria
```

Siempre que el servicio y el dataset lo permitan.

---

## 11. Relación con el contrato `Observacion`

El resultado de una consulta GeoINTA debe integrarse al contrato ya existente:

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

Nunca crear un contrato alternativo solamente para GeoINTA.

---

## 12. Trazabilidad

Cada dato debe permitir conocer:

```text
organismo
→ INTA

plataforma
→ INTA Digital Geo

nodo
→ Nacional / regional

servicio
→ WMS / WFS / WCS

dataset
→ identificado por metadata

capa
→ nombre técnico verificado

fecha de consulta
→ registrada

calidad
→ registrada
```

Cuando un dato se convierta en una feature del modelo de IA, debe conservarse la trazabilidad hacia su origen.

---

## 13. Calidad y escala

La existencia de un geoservicio no garantiza que la información sea apta para decisiones a escala de lote.

Cada dataset debe evaluarse por:

- escala cartográfica;
- resolución espacial;
- fecha;
- cobertura;
- precisión;
- naturaleza del dato;
- aplicabilidad agronómica.

Una capa regional puede ser útil para contexto, pero no debe describirse como si fuese una medición directa del lote.

---

## 14. Prioridad técnica inicial

Para el proyecto:

```text
PRIORIDAD 1
WFS
→ datos vectoriales y atributos

PRIORIDAD 2
WCS
→ datos raster y coberturas

PRIORIDAD 3
WMS
→ visualización y verificación
```

Esta prioridad puede cambiar según el dataset.

---

## 15. Integración con los satélites existentes

GeoINTA no reemplaza las fuentes satelitales actuales.

La combinación esperada es:

```text
          OBSERVACIÓN
               │
     ┌─────────┴─────────┐
     ↓                   ↓
Satélites             GeoINTA
     │                   │
NDVI / NDMI          Suelo
humedad             Aptitud
ET                  Ambiente
estrés              Cartografía
     │                   │
     └─────────┬─────────┘
               ↓
          PERFIL DEL LOTE
               ↓
       MOTOR DE ROTACIÓN
```

La arquitectura actual ya contempla GeoINTA como fuente de suelo, por lo que estos geoservicios constituyen una ampliación del mecanismo de acceso, no un reemplazo de la arquitectura existente.

---

## 16. Reglas para los agentes

### ALWAYS

```text
ALWAYS use the official INTA geoservices documented by INTA.

ALWAYS verify the dataset before implementing it.

ALWAYS preserve node, service and layer provenance.

ALWAYS preserve CRS and scale/resolution metadata.

ALWAYS distinguish WMS, WFS and WCS.

ALWAYS reuse the Observacion contract.

ALWAYS test with the real San Luis test field when applicable.
```

### ASK FIRST

```text
ASK FIRST before changing the GeoINTA connector architecture.

ASK FIRST before adding a new regional node as an application dependency.

ASK FIRST before changing the normalization rules.

ASK FIRST before treating a regional layer as a lot-level measurement.

ASK FIRST before adding a new variable to the ML feature set.
```

### NEVER

```text
NEVER invent layer names.

NEVER assume that all regional nodes contain the same datasets.

NEVER silently change source attribution.

NEVER discard scale/resolution metadata.

NEVER replace raw/source metadata with a derived value.

NEVER make an agronomic recommendation directly from a GeoINTA layer.
```

---

## 17. Prueba inicial recomendada

La primera prueba técnica debe enfocarse en:

```text
Nodo:
geo-nodo15.inta.gob.ar

Región:
La Pampa – San Luis

Área:
lote de prueba de Rotaterra

Servicios:
WFS
WCS
WMS

Objetivo:
descubrir capas disponibles y seleccionar
las que puedan aportar información al modelo
de rotación.
```

---

## 18. Tareas propuestas

### TASK-GEO-001

Consultar GetCapabilities del nodo nacional y del nodo 15.

### TASK-GEO-002

Construir un inventario de capas.

### TASK-GEO-003

Clasificar las capas:

```text
SUelo
Agroecología
Territorio
Agua
Clima
Vegetación
Otros
```

### TASK-GEO-004

Identificar qué capas intersectan el lote de prueba.

### TASK-GEO-005

Seleccionar las capas prioritarias para Rotaterra.

### TASK-GEO-006

Documentar el dataset, escala, CRS y mecanismo de consulta.

### TASK-GEO-007

Realizar una prueba real.

### TASK-GEO-008

Integrar solamente los datasets aprobados al conector existente.

---

## 19. Criterio de terminado

Esta ampliación se considera terminada cuando:

- [ ] los endpoints oficiales están documentados;
- [ ] el nodo 15 para La Pampa–San Luis está documentado;
- [ ] WMS, WFS y WCS fueron diferenciados;
- [ ] se realizó el descubrimiento de capacidades;
- [ ] las capas candidatas están inventariadas;
- [ ] las capas prioritarias fueron seleccionadas;
- [ ] se verificó cobertura sobre el lote de prueba;
- [ ] se documentó escala/resolución;
- [ ] se registraron los resultados reales;
- [ ] se respetó `Observacion`;
- [ ] existen tests;
- [ ] se actualizó `Proyect-context.md`;
- [ ] Hernán autorizó el PR.

---

## 20. Nota de verificación

La página oficial de INTA consultada identifica explícitamente:

```text
Nodo Nacional
https://geo-backend.inta.gob.ar/geoserver/wms
https://geo-backend.inta.gob.ar/geoserver/wfs
https://geo-backend.inta.gob.ar/geoserver/wcs

Región La Pampa – San Luis
https://geo-nodo15.inta.gob.ar/geoserver/wms
https://geo-nodo15.inta.gob.ar/geoserver/wfs
https://geo-nodo15.inta.gob.ar/geoserver/wcs
```

La página muestra además el acceso a otros nodos regionales.

Fuente:

https://geo.inta.gob.ar/geoservicios/
