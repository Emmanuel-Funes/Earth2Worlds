# Spec 020 · Suelo del lote desde las cartas de suelo del INTA (GeoINTA)

**Estado:** aprobada por Hernán ("Sumar lo necesario para cubrir lo que hace falta") · implementada y probada con datos reales · **Etapa:** pipeline fuente → API → app (sin interfaz) · **Requiere:** nada (servicio público, sin usuario ni contraseña)

## Objetivo

Saber qué suelo tiene cada lote y cuánto produce en potencia: el **índice de productividad** (IP) y la **clase de capacidad de uso**, con la serie, la textura y las limitantes en la nota. Es el dato que pone en contexto el NDVI, la humedad y el rinde: un lote de IP 50 no se compara con uno de IP 95.

## Fuente

Es la **excepción prevista a la regla NASA** (AGENTS.md § 2 y Guía técnica): el suelo no lo mide un satélite, lo relevó a campo el **INTA** y lo publica en **GeoINTA**, su infraestructura de datos espaciales.

- **Servicio:** WFS público de GeoINTA, `https://geo-backend.inta.gob.ar/geoserver/ows` (GeoServer de la GeoNode del INTA). Sin credenciales.
- **Capas que se usan** (averiguadas con `probar_geointa.py --explorar` desde GitHub Actions, ver abajo):

| Capa | Qué es | Escala | Atributos que se usan | Fecha que se guarda |
|---|---|---|---|---|
| `geonode:suelos_argentina_1_500` | Atlas de Suelos de la República Argentina, INTA, v9 | 1:500.000 (1:1.000.000 en Neuquén, Mendoza, San Juan, La Rioja, Chubut y Santa Cruz) | `simbc`, `tipo_uc`, `provincia`, `ind_prod`, `porc_sue1..3`, `sgrup_sue1..3`, `posi_sue1..3`, `text_sups1`, `text_bs1`, `drenaje_s1`, `limit_ppal/secu/terc` | 2026-11-14 (versión digital 9.0, según los metadatos de GeoINTA) |
| `geonode:Suelos_BA_50mil_V2` | Cartas de Suelo de la provincia de Buenos Aires, INTA, v2 | 1:50.000 | `SIMBC`, `Nombre_UC`, `SERIE1..6`, `PORC1..6`, `FASE1..6`, `PAISAJE`, `CAP_USO`, `taxo_ppal` | 2026-11-14 (versión 2.0 publicada por el Instituto de Suelos del INTA) |

La fecha de la observación es la de la **versión digital de la carta**, no la del relevamiento de campo (que en las cartas 1:50.000 va de 1964 en adelante y no viene en el servicio). Se aclara en la nota.

### Lo que se encontró en GeoINTA (exploración)

- `geo-backend.inta.gob.ar/geoserver/ows` responde WFS 1.0/1.1 y GeoJSON: 30 capas, 10 de suelo.
- `geointa.inta.gob.ar/geoserver/ows` responde 200 pero no devuelve un GetCapabilities XML legible; `geointa.inta.gov.ar` ya no existe en el DNS.
- Capas de suelo con cobertura parcial que **no** se usan todavía: `suelos_santa_fe_…` (Santa Fe 1:50.000; trae `gat`/`iat`, índices propios de la provincia que hay que confirmar antes de usarlos como IP), cartas de Salta y Jujuy, Valle de Lerma y Santa Rosa (La Pampa). Ninguna cubre el lote de San Luis ni Pergamino.
- **Cobertura:** el Atlas 1:500.000 cubre todo el país. La carta 1:50.000 con capacidad de uso publicada en GeoINTA es la de Buenos Aires. **San Luis no tiene carta 1:50.000 en GeoINTA**: para el lote de prueba solo hay IP del Atlas. **Actualización (spec 021):** el nodo 15 del INTA publica por WFS las hojas 1:100.000 de San Luis con capacidad de uso e IP. En el lote de prueba dan clase VI (`VIes`) e IP 50, y el conector ya las usa (ver spec 021, §23).
- En el lote de prueba de San Luis el Atlas da la unidad `EPtc-1` (Consociación, Ustortentes típico, franco arenosa, drenaje algo excesivo, limitante climática y erosión eólica, IP 50). En Pergamino, `MItc-1` (Argiudoles típico, franco limosa, sin limitaciones, IP 95); la carta 1:50.000 tiene ahí unidades como `Pe3` (CU `IVe`), `AD1` (`IIIe`), `Ro9x` (`I-2`) y `Pe4` (`I-1`). El punto -33,89; -60,57 cae en la ciudad (unidad `M`), por eso el lote de control está en el campo, al suroeste.
- **Velocidad:** pedir las geometrías completas no sirve. Con la caja del lote de Pergamino, el WFS de la carta 1:50.000 no respondió en 300 s, porque hay unidades enormes (la unidad urbana `M` es un solo multipolígono que junta ciudades de toda la provincia, de Pergamino a Bahía Blanca). Además el filtro `bbox` de ese servidor es por rectángulo envolvente: devolvió 18 unidades cuando el lote toca 1. Pedir **sin geometría** con un filtro CQL exacto (`INTERSECTS`) tarda 0,2 s por consulta.

## Entrada

`lote_id`, `poligono` (GeoJSON Polygon, EPSG:4326).

## Proceso

1. Para cada capa, pedir al WFS (`GetFeature` 1.0.0, GeoJSON) **sin geometría** (`propertyName` con los atributos de la tabla) las unidades que tocan el polígono del lote: `CQL_FILTER=INTERSECTS(the_geom, POLYGON((lon lat, …)))`, hasta 50. Si no hay ninguna, la carta no cubre el lote.
2. Calcular qué parte del lote cubre cada unidad **por muestreo**: una grilla de 5 × 5 puntos sobre la caja del lote, de la que se usan los que caen dentro del polígono (hasta 25); para cada punto, `INTERSECTS(the_geom, POINT(lon lat))` dice en qué unidad cae (5 consultas a la vez). Fracción = puntos de la unidad / puntos totales. Una unidad que toca el lote sin que le caiga ningún punto figura como "(borde)"; los puntos sin unidad se informan como "lote sin unidad en la carta".
3. La **unidad dominante** es la que tiene más puntos.
4. Atlas → `suelo_indice_productividad` = `ind_prod` de la unidad dominante. Carta 1:50.000 → `suelo_clase_capacidad_uso` = número de clase del texto `CAP_USO` (`IVe` → 4, `I-2` → 1); la subclase (e = erosión, w = exceso de agua, s = suelo, c = clima) va en la nota.

## Salida (contrato común)

Una observación por variable, `fuente: "GeoINTA"`.

| Variable | Unidad | Carta | `resolucion_m` |
|---|---|---|---|
| `suelo_indice_productividad` | `IP 0-100` | Atlas 1:500.000 | 250 |
| `suelo_clase_capacidad_uso` | `clase 1-8` | Buenos Aires 1:50.000, o las hojas 1:100.000 de San Luis (spec 021) | 25 (50 en San Luis) |

- `resolucion_m` es un **supuesto**: 0,5 mm del mapa a esa escala (lo más fino que se puede leer en la carta).
- La **nota** lleva: símbolo y tipo de la unidad, series o subgrupos con su porcentaje y posición (o fase), textura superficial y del subsuelo, drenaje, limitantes, el texto original de capacidad de uso con su subclase, qué porcentaje del lote cubre la unidad dominante y cuáles son las otras (por muestreo de puntos, con saltos de 4 % en un lote con 25 puntos), y la carta con su escala y fecha.

Ejemplo (Pergamino):

```json
{"lote_id": "lote-prueba", "fecha": "2026-11-14", "variable": "suelo_clase_capacidad_uso", "valor": 1,
 "unidad": "clase 1-8", "fuente": "GeoINTA", "resolucion_m": 25, "calidad": "buena",
 "nota": "Unidad Pe4 (Consociacion Pergamino 4) · series: Pergamino 100 % (llana) · Argiudol tipico · capacidad de uso 'I-1' = clase 1 · cubre 100% del lote (muestreo de puntos) · Cartas de Suelo de Buenos Aires (INTA) v2, escala 1:50.000 (versión digital del 14/11/2026)"}
```

## Reglas de calidad

1. **Nunca inventar.** Si la carta no tiene ninguna unidad en el lote (p. ej. la carta 1:50.000 fuera de Buenos Aires) → `valor: null`, `descartada`, y la nota dice que no hay carta publicada para ese lote.
2. IP ausente, ≤ 0 o > 100 (agua, urbano, misceláneas) → `descartada`.
3. Capacidad de uso ilegible (no empieza con un número romano del I al VIII) → `descartada`.
4. La unidad dominante cubre **menos del 50 %** del lote → `dudosa` ("lote mixto"), y la nota lista las demás unidades.
5. Si una de las dos capas no responde, esa variable sale `descartada` con el motivo y se reintenta en la próxima consulta; si no responde ninguna, es un error (`ErrorGeoINTA`, 502 en la API).

## Prioridad y respaldo

- Es un **dato fijo** (`estatico=True`): una vez guardado con valor, la actualización no lo vuelve a pedir.
- Si el productor carga un **análisis de suelo**, ese dato manda (fuente `productor`, prioridad 0 en el núcleo).
- **Sin respaldo automático.** La alternativa global (SoilGrids, de ISRIC) no es una agencia: queda **pendiente de decisión de Hernán**. Mientras tanto, sin dato del INTA la variable queda descartada.

## API

`POST /suelo` con `{"lote_id": …, "poligono": …}` → las 2 observaciones. `422` polígono inválido, `502` GeoINTA no responde. Uso interno y pruebas; la app la consulta en el momento como las demás fuentes (spec 010).

## Pruebas

- `tests/test_geointa.py`: sin internet, con el WFS simulado (`httpx.MockTransport`).
- `probar_geointa.py` + workflow **Probar GeoINTA (suelos)**: explora los servidores (paso informativo) y pide el suelo del lote de San Luis (exige IP) y de un lote de control en el campo al suroeste de Pergamino (`-33.960, -60.650; -33.960, -60.645; -33.965, -60.645; -33.965, -60.650`, ~26 ha; exige IP y capacidad de uso). Corre en cada PR que toque el conector y con un clic; a mano se puede pedir además la exploración de capas (`--explorar`).

## Criterios de aceptación

- [x] Con el lote de prueba de San Luis se obtiene el IP del Atlas, y la capacidad de uso sale descartada con el motivo (sin carta 1:50.000). *Desde la spec 021 sale de la hoja 1:100.000 Villa Mercedes: clase 6.* Prueba real: IP **50** (`EPtc-1`, Ustortentes típico, franco arenosa, limitantes climática y erosión eólica, cubre el 100 % del lote), en 3 s.
- [x] Con el lote de Pergamino se obtienen el IP y la clase de capacidad de uso, con la serie en la nota. Prueba real: IP **95** (`MItc-1`, Argiudoles típico, franco limosa) y capacidad de uso **clase 1** (`Pe4`, serie Pergamino 100 %, fase llana, `I-1`), las dos `buena` y cubriendo el 100 % del lote, en 4 s.
- [x] Tests sin internet (`tests/test_geointa.py`, 23 casos, WFS simulado que resuelve el filtro CQL): unidad dominante, lote mixto, unidad que solo roza el borde, lote en parte fuera de la carta, IP inválido, capacidad ilegible, respuesta que no es JSON, una capa caída y las dos caídas.
- [x] Prueba real con un clic y automática en cada PR que toque el conector (workflow "Probar GeoINTA (suelos)", en verde en el PR).

## Riesgos conocidos

- El Atlas es **1:500.000**: para un lote de 25 ha da el suelo de la región, no el del lote. Sirve para ubicar el lote; no reemplaza una carta 1:50.000 ni un análisis.
- Cada lote hace hasta 52 consultas cortas al INTA (2 cartas × (1 + 25 puntos)). Es un dato fijo y se pide una sola vez, pero si el INTA limita consultas habría que bajar la grilla.
- Un lote con un polígono de muchos vértices viaja en la URL; se simplifica a ~1 m antes de mandarlo.
- Los nombres de capa de GeoNode cambian si el INTA vuelve a publicar la carta (la de Santa Fe ya tiene un sufijo de hash). Si una capa desaparece, la variable sale descartada con el error y la prueba real lo muestra.
- El servidor devuelve algunos acentos mal codificados ("V?a de escurrimiento"); se guardan como vienen.
- Las fechas de las cartas salen de los metadatos publicados por el INTA, no del servicio WFS.

## Fuera de alcance

Cartas 1:50.000 de otras provincias (se suman cuando GeoINTA las publique con IP o capacidad de uso), perfiles de SiSINTA, cartas provinciales que no son del INTA (p. ej. IDECOR Córdoba) y propiedades por horizonte (materia orgánica, agua útil).
