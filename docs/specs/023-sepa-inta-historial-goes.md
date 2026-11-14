# Spec 023 · SEPA INTA: historial completo, balance hídrico y GOES

**Estado:** aprobada por Hernán el 5/10/2026 ("Te doy el okey SPEC023"). Fase 1 (inventario) terminada; fase 2 (conector) programada y probada. No se une a `main` hasta que Hernán lo ordene.
**Autor:** Hernán (vía IA) · **Rama:** `SEPA_INTA-historial_goes_y_variables` · **Conector:** `rotaterra/fuentes/sepa_inta.py`
**Pedido:** "Es vital que investigues cómo extraer datos puntuales de todos esos mapas y visores del INTA (Series Temporales, GOES-19, Balance Hídrico, Anomalías)".

## 1. Objetivo

Desarrollar la fuente `sepa_inta` para consultar el sistema SEPA del INTA (sepa.inta.gob.ar) y sus visores satelitales, incluido GOES-19. La meta es hacer **ingeniería inversa** de los pedidos que hace la web y extraer la **serie temporal histórica completa** y en tiempo real de las variables de §2, en el lote.

**Fuentes permitidas:** SEPA es del INTA, que es una excepción prevista (AGENTS §2). GOES-19 es de la NOAA, agencia socia de la NASA (spec 005, regla de socios del PR #23). Los productos de SEPA que usan MODIS o VIIRS son de la NASA y la NOAA.

## 2. Variables a extraer e investigar (mapeo al contrato `Observacion`)

### A. Índices de vegetación y anomalías

| Producto INTA / frecuencia | `variable` | Unidad |
|---|---|---|
| Compuesto 10 días | `ndvi_10d_inta` | adimensional |
| Compuesto 16 días, NDVI | `ndvi_16d_inta` | adimensional |
| Compuesto 16 días, EVI | `evi_16d_inta` | adimensional |
| Índice mensual | `ndvi_mensual_inta` | adimensional |
| Índice de condición de la vegetación (VCI) cada 8 días | `vci_8d_inta` | % |
| Anomalía cada 10 días / mensual | `anomalia_ndvi_inta` | % |
| Duración de anomalías negativas de NDVI (2000-2025) | `duracion_anomalia_negativa` | días / ciclos |
| Anomalía histórica (8 d, 16 d, mensual) | `anomalia_historica_ndvi` | % |

### B. Balance y confort hídrico

| Producto INTA | `variable` | Unidad |
|---|---|---|
| Confort hídrico | `confort_hidrico_inta` | % (transpiración lograda ÷ demanda) |
| Variación de agua disponible | `variacion_agua_disponible_clase` | clase de 1 a 5 (el INTA publica clases, no mm) |
| Agua disponible hasta 2 metros | `agua_disponible_2m` | mm |
| Porcentaje de agua en el suelo | `agua_suelo_porcentaje` | % |
| Agua excedente | `agua_excedente_inta` | mm |

La metodología del balance va como texto en la `nota`, si el INTA la publica.

### C. Evapotranspiración y meteorología

| Producto INTA | `variable` | Unidad |
|---|---|---|
| Evapotranspiración real cada 10 días | `etr_10d_inta` | mm/día |
| Anomalía de ETR cada 10 días | `anomalia_etr_10d` | % |
| Radiación solar media mensual | `radiacion_solar_mensual` | W/m² o MJ/m² |
| Cociente fototermal (Q) para trigo, diario y por década | `cociente_fototermal_trigo`, `cociente_fototermal_trigo_10d` | MJ/m²/día/°C |
| Albedo | `albedo_inta` | % |

### D. GOES y sensores en tiempo real

| Producto INTA / GOES | `variable` | Unidad |
|---|---|---|
| Temperatura de superficie nocturna (heladas) | `temp_superficie_nocturna` | °C |
| Temperatura de superficie diurna | `temp_superficie_diurna` | °C |
| Temperatura de superficie cada 10 días | `temp_superficie_10d` | °C |
| Infrarrojo térmico / infrarrojo térmico color | `infrarrojo_termico_goes` | K o °C |
| Temperatura de topes nubosos | `temp_topes_nubosos` | °C |
| Monitoreo de rayos en tiempo real | `rayos_tiempo_real` | destellos/km² |
| Animación infrarrojo térmico Sudamérica | `animacion_ir_goes` | URL de video o GIF |

## 3. Reglas de extracción (de Hernán)

1. **Ingeniería inversa:** usar `httpx` para repetir los pedidos que hace el navegador al hacer clic en un lote en los visores del INTA, y leer los JSON o los WMS/FeatureInfo.
2. **Historial por lote:** `pedir(lote, desde, hasta)` trae la serie de cada variable. Se usa el centroide si el INTA pide un punto, o el polígono si acepta consultas espaciales.
3. **No inventar valores:** si un producto no tiene un número para esa fecha y ese lugar, va `valor: null`, `calidad: "descartada"` y el motivo en la `nota`.
4. **Multimedia:** si un producto es solo una imagen o una animación, la URL va en la `nota` para que el frontend la muestre.
5. **Sin base de datos:** todo se consulta en el momento.
6. **Aislamiento:** la fuente es un satélite más, independiente del resto.

### 3.1 Cómo se adaptan estas reglas al repositorio

| Regla de Hernán | Cómo se cumple | Por qué |
|---|---|---|
| "Registrar la clase en `fuentes/registro.py`" | El conector declara `SATELITES = [Satelite(...)]` al final, y `registro.py` lo descubre solo | AGENTS §8 y §9: el núcleo nunca nombra a un satélite. El resultado es el mismo: la fuente aparece en `GET /satelites` y en `POST /consulta` |
| URL "en `nota` o `valor`" | Va en la `nota`, con `valor: null` | En el contrato `valor` es un número; un texto ahí rompería la API |
| Fuente `SEPA_INTA` y `GOES` | Se suman al tipo `Fuente` de `contrato.py` y a `PRIORIDAD` en `base.py` | Igual que se sumaron GeoINTA, Sentinel-2 y Copernicus DEM |
| Pedidos a un sitio público | Pausa entre pedidos, se respeta `robots.txt` y se pide lo justo para el lote | Para no cargar el servidor del INTA |

## 4. Fase 1: inventario (terminada)

SEPA no publica un manual de API. El workflow **Probar SEPA INTA (inventario de mapas y visores)** (`inventariar_sepa_inta.py` e `inventariar_sepa_inta_detalle.py`) recorrió las páginas públicas, los scripts de los visores, los servidores de mapas, los PDF de metodología y el código de las apps de Earth Engine, y leyó valores en el lote de San Luis (-33,700; -65,300). Lo que encontró:

- **GeoSEPA** (`/productos/geosepa/`) es el único lugar con números. Lista sus archivos con `componentes/listar_archivos.php?seccion=…&producto=…&tipo=decada|juliano` y guarda cada período como `{seccion}/{producto}/tif/{producto}_{AAAAMM}_{década}.tif`. Los productos por día juliano (`tipo=juliano`) tienen solo imagen, sin GeoTIFF.
- El servidor de SEPA es lento para bajar archivos enteros (~35 KB/s, cortes por tiempo), pero acepta pedidos por rangos de bytes. Por eso el conector lee solo el pedazo del lote (2 a 6 s por mapa) y nunca el mapa entero.
- No hay WMS, WFS ni GetFeatureInfo en SEPA. No hay JSON con valores por punto.
- Los visores de heladas, temperatura diurna y Q de trigo son apps de Google Earth Engine. Su código es público y muestra de dónde salen: heladas y temperatura usan **NOAA GOES-19** (`NOAA/GOES/19/MCMIPF`), y el Q usa el pronóstico **NOAA GFS** (`NOAA/GFS0P25`). No exponen una API, así que el conector va a la fuente original.
- El resto de los productos (índices de 10 días, mensuales, VCI, ETR, radiación, anomalías de ETR) son **imágenes de colores** (GIF/JPG) con la fecha en el nombre. Tienen historial navegable, pero no tienen el número.

## 5. Qué se puede extraer (verificado)

| Variable | Dónde está | Número en el lote | Historial | Cómo lo entrega el conector |
|---|---|---|---|---|
| `agua_disponible_2m` (mm) | GeoSEPA `agua_en_suelo/ad` | **Sí** (GeoTIFF 500 m) | Por década desde mayo de 2024 | Media de los píxeles del lote, con mín, máx y cantidad en la `nota` |
| `agua_suelo_porcentaje` (%) | GeoSEPA `agua_en_suelo/pj` | **Sí** | Desde mayo de 2024 | Media del lote |
| `confort_hidrico_inta` (%) | GeoSEPA `agua_en_suelo/ch` | **Sí** | Desde mayo de 2024 | Media del lote; el código -99 (cobertura verde menor al 20%, el INTA no lo calcula) queda afuera y se avisa |
| `variacion_agua_disponible_clase` | GeoSEPA `agua_en_suelo/db` | **Sí, como clase** | Desde mayo de 2024 | La clase que más ocupa el lote, y el reparto en la `nota`. Clases del INTA: 1 baja más de 30 mm, 2 baja menos de 30 mm, 3 sube menos de 30 mm, 4 sube 30 a 90 mm, 5 sube más de 90 mm |
| `agua_excedente_inta` (mm) | GeoSEPA `agua_en_suelo/dr` | **Sí** | Desde mayo de 2024 | Media del lote |
| `anomalia_historica_ndvi` (%) | `indices_de_vegetacion/anomalia_16d_historica/sc-AAAADDD.tif` | **Sí** (250 m) | **Solo el último compuesto** (el 4/10/2026 era el que empieza el 29/08/2026) | El conector busca el enlace al GeoTIFF en la página del producto. Si ese compuesto cruza el rango pedido, va el número; si no, `null` con la fecha del último y la imagen de colores (`sc_AAAADDD.gif`, que sí tiene historial) |
| `duracion_anomalia_negativa` (días) | `indices_de_vegetacion/persistencia_16d/persistencia-AAAADDD.tif` | **Sí** | **Solo el último compuesto** | Igual que la anomalía |
| `temp_superficie_nocturna` y `temp_superficie_diurna` (°C) | NOAA GOES-19 `ABI-L2-LSTF` (archivo abierto en AWS), la misma fuente que el visor de heladas | **Sí** (10 km, cada hora) | GOES-19 desde el 7/4/2025; antes, GOES-16 (sin probar todavía) | Mínima entre las 4 y las 7 h y máxima entre las 13 y las 16 h (hora argentina), con la calidad DQF de la NOAA. Si es ≤ 0 °C la `nota` avisa riesgo de helada. Hasta 31 días por pedido |
| `infrarrojo_termico_goes` (°C) | GOES-19 `ABI-L2-CMIPF` banda 14 | **Sí** (2 km) | Tiempo real (última imagen) | Temperatura de brillo en el lote |
| `temp_topes_nubosos` (°C) | GOES-19 `ABI-L2-ACHTF` | **Sí** (10 km) | Tiempo real | Si no hay nube, `null` con el motivo |
| `rayos_tiempo_real` (destellos/km²) | GOES-19 `GLM-L2-LCFA` | **Sí** | Últimos 15 minutos | Destellos a menos de 10 km del lote ÷ área |
| `animacion_ir_goes` | Animación de la NASA (`weather.ndc.nasa.gov`, la que muestra SEPA) | No (es un video) | Tiempo real | URL centrada en el lote en la `nota` |
| `cociente_fototermal_trigo` y `_10d` | Calculado con **NASA POWER** (el INTA usa NOAA GFS) | **Sí** (55 km) | Desde 1981 | Fórmula del INTA, ver §5.2 |
| `ndvi_10d_inta`, `ndvi_16d_inta`, `evi_16d_inta`, `ndvi_mensual_inta`, `vci_8d_inta` | Imágenes de SEPA y GeoSEPA | **No** (solo colores) | 10 d desde 2018; 16 d por día juliano | `null` + `descartada` + la URL de la imagen en la `nota` (se comprueba que exista) |
| `etr_10d_inta`, `anomalia_etr_10d`, `radiacion_solar_mensual` | Imágenes de SEPA | **No** | ETR desde 2015; radiación desde 2025 | Igual: URL en la `nota` |
| `anomalia_ndvi_inta`, `temp_superficie_10d` | `DF_DECADA.gif`, `TS.gif` | **No** | Solo la última | URL en la `nota` cuando el rango llega a hoy |
| `albedo_inta` | No se encontró en SEPA | No | — | No se entrega |

**Nunca se lee un número de un color.** Los valores de NDVI, EVI y ETR con número ya los dan otros satélites de la app (HLS, MODIS, VIIRS, MOD16, ECOSTRESS). Las series de 16 días del INTA son MODIS MOD13Q1 de la NASA: el mismo dato que trae el respaldo MODIS (spec 011).

### 5.1 Unidades y metodología del balance hídrico (de los PDF del INTA)

El balance diario del INTA usa lluvia IMERG corregida con estaciones del INTA y del SMN, ETo FAO-56 de estaciones, NDVI y DFI de VIIRS, y cartas de suelo del INTA, con raíces hasta 2 m. Se publica por década (hasta el día 10, el 20 y fin de mes) a ~500 m. Archivos nuevos: `nodata` = NaN; viejos: −3,4·10³⁸; el conector descarta los dos.

### 5.2 Q de trigo

SEPA lo estima con el pronóstico NOAA GFS (dato modelado, no observado). El conector usa la misma fórmula con NASA POWER, que es dato de reanálisis y sí está en la regla de fuentes:

- `Q = radiación global (MJ/m²/día) ÷ (temperatura media − 4,5 °C)`.
- Si `temperatura media − 4,5 ≤ 0,5 °C`, no hay valor (`null`, con el motivo), igual que en SEPA.
- Por década: radiación media ÷ (temperatura media − 4,5), solo con al menos 8 días con dato.
- Es por día calendario o década, no en la ventana de antesis de un lote (eso necesita fecha de siembra y cultivar; queda para después).

### 5.3 Uso de los datos de SEPA (términos del INTA)

Los términos de SEPA permiten el uso personal y no comercial. El uso comercial necesita **autorización escrita del Instituto de Clima y Agua (CIRN-INTA)**. Los términos también dicen que no se pueden crear enlaces que muestren una página o imagen del sitio sin autorización, y eso alcanza a las URL de imágenes que el conector pone en la `nota`. Además piden citar al INTA y al equipo SEPA, y poner un link a https://sepa.inta.gob.ar/productos/. Por eso cada observación de SEPA lleva en la `nota` la cita y la autorización. GOES (NOAA) y POWER (NASA) no tienen esa restricción.

**Decisión de Hernán (4/10/2026):** pedir la autorización al INTA, aclarando que Rotaterra es para la hackatón de la NASA. El borrador del mail va a Lucas Gusmerotti (contacto del balance hídrico en GeoSEPA), con copia a Patricio Oricchio (consultas de los visores). Mientras no haya respuesta, el uso se mantiene sin fines comerciales, y se arma un balance hídrico propio con datos de la NASA como respaldo (spec 024).

**Respuesta del INTA (5/10/2026):** Patricio Oricchio (CIRN-INTA) contestó: "Adelante con el uso de los productos que mencionas en tu correo. […] Si debo aclararte que si uso es comercial, tendríamos que averiguar con el INTA las condiciones de uso." O sea:

| Uso | Estado |
|---|---|
| Rotaterra en la hackatón de la NASA, con los productos del mail | Autorizado |
| Uso comercial | Hay que averiguar las condiciones con el INTA antes |

La `nota` de cada dato de SEPA dice "uso autorizado por el CIRN-INTA el 5/10/2026 para Rotaterra en la hackatón NASA; el uso comercial necesita acordar condiciones con el INTA", y sigue llevando la cita al INTA. El balance propio (spec 024) queda como respaldo para cuando SEPA no conteste, y como camino sin SEPA si el uso comercial no se acuerda.

**Enlaces a imágenes (Hernán, 4/10/2026: "Lo de la imagen da igual, usarlo igualmente"):** el conector sigue poniendo la URL de la imagen de SEPA en la `nota`.

**Si SEPA está caído (Hernán, 4/10/2026: "no considerarlo, ver la forma de costearlos nosotros mismos"):** el conector pregunta primero si el sitio de SEPA contesta (20 s como máximo). Si no contesta, devuelve el agua del suelo como `descartada` con el motivo, sin esperar minutos por cada archivo, y sigue con el Q de trigo (POWER). La prueba real no lo cuenta como falla: avisa y exige solo lo que no depende de SEPA. El dato de agua lo cubre el balance propio (spec 024). **En `POST /consulta` (agregado el 16/10/2026):** si SEPA está caído, el conector da error en vez de devolver solo el Q, para que conteste el respaldo `SEPA_INTA:BALANCE` con el agua del suelo. Lo encontró la prueba del piloto: con SEPA caído, la consulta de dos parcelas reales devolvía el Q y el agua vacía, y el balance nunca entraba. Ese día el Q de trigo no viene (sale de POWER y el motor no lo usa). `POST /sepa` sigue igual que antes.

**Un pedido por vez (prueba de lotes grandes, 6/10/2026, spec 022 §10):** un mes de SEPA tarda unos 3,5 minutos con cualquier lote (213 s con 25 ha y 210 s con 944 ha). Después de un pedido completo, el servidor del INTA rechaza la conexión (`ConnectError`) por un rato, sea cual sea el tamaño del lote siguiente. El conector lo maneja con el aviso de arriba. Si muchos usuarios piden SEPA a la vez, la mayoría va a recibir ese aviso y el agua del balance propio.

### 5.4 Cambios en el núcleo

Se suman `SEPA_INTA` y `GOES` al tipo `Fuente` (`contrato.py`) y a `PRIORIDAD` (`base.py`), como se hizo con GeoINTA. Ningún otro archivo del núcleo cambia.

## 6. Criterios de aceptación

Verificado el 4/10/2026 en GitHub (workflow **Probar SEPA INTA y GOES (agua, heladas, Q de trigo)**, lote de San Luis -33,700; -65,300).

- [x] Existe `rotaterra/fuentes/sepa_inta.py` y los tests del núcleo y de todos los satélites siguen pasando (68 tests sin internet, workflow **Tests** en verde).
- [x] Extrae el historial del balance hídrico hasta 2 m, con número, promediando todos los píxeles que toca el lote (6 píxeles de 500 m en el lote de San Luis). Últimos 35 días (355 s, 4/10/2026): agua disponible 92,1 → 86,0 → 83,9 → **84,0 mm** al 30/9/2026 (mín 31,3 y máx 135,5 entre píxeles); agua útil 41,8 → 39,1 → **38,2 %**; confort hídrico 100 → 100 → 98,2 → **91,3 %** (3 píxeles con −99 quedan afuera); variación clase **2** (reparto 50 % clase 2 y 50 % clase 3); excedente 0 mm. Una corrida anterior que leía un solo píxel dio 61,8 mm; por eso se corrigió la ventana. Enero de 2025 (corrida de un píxel, 54 s): agua 58,1 → 39,2 → **25,9 mm**, agua útil 26 → 12 %, confort 87 → 59,9 → **29,9 %** (estrés de enero).
- [x] Historial de índices y de evapotranspiración del INTA: **solo como imágenes** (URL en la `nota`, comprobada), porque SEPA no publica el número (§5). El número de NDVI, EVI y ET lo dan otros satélites de la app.
- [x] Se conecta a GOES-19 y extrae la temperatura de superficie y el riesgo de heladas. Del 28/9 al 4/10/2026 (6 s): mínimas de 11,9; 9,0; **−8,6**; **−5,3**; 7,1 y 10,3 °C (las bajo cero con calidad `dudosa` de la NOAA), máximas de 31,5 a 35,5 °C, con dos días nublados `descartada`. Además infrarrojo −2,4 °C, topes nubosos −32,9 °C, 0 rayos en 15 minutos y la animación.
- [x] Q de trigo con NASA POWER: diario y por década (1,813; 1,687 y 1,402 en septiembre de 2026), sin valor los días con Tmedia − 4,5 ≤ 0,5 °C o sin dato de POWER.
- [x] Existe `.github/workflows/probar_sepa_inta_completo.yml`, con el lote de prueba (-33,700; -65,300). Corre en cada PR que toque el conector; el botón para lanzarlo con un clic aparece en GitHub cuando el workflow esté en `main`.
- [x] Lo que no se puede leer como número queda descartado con el motivo, o con su URL en la `nota`.
- [x] Hernán aprobó esta spec (5/10/2026).
