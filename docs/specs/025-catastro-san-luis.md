# Spec 025 · Límites oficiales y datos de la parcela del Catastro de San Luis

**Estado:** implementada, espera la aprobación de Hernán · **Origen:** SDD "Integración Catastro San Luis" de Hernán, que llegó como `spec_024_catastro_sl.md` · **Etapa:** pipeline fuente → API → app (sin interfaz) · **Requiere:** nada (el servicio es público, sin usuario ni clave)

> **Número:** la spec de Hernán venía como 024, pero ese número ya era del balance hídrico propio. Esta queda como **025**.

## Objetivo

Que la app no tenga que dibujar el lote a mano: con un punto (lat, lon), una nomenclatura catastral o una partida, se pide al Catastro de San Luis el **polígono oficial de la parcela** y sus datos legales, y ese polígono se usa para recortar los datos de la NASA y del INTA.

## Excepción a la regla de fuentes

Las fuentes permitidas son la NASA, sus agencias socias y el INTA. Con esta spec, Hernán suma como excepción explícita a la **Dirección Provincial de Catastro y Tierras Fiscales de San Luis**, como fuente oficial de límites territoriales (decisión de Hernán, 14/11/2026, en su SDD).

## Fuente (relevada con ingeniería inversa)

El visor público `http://www.sistemacatastro.sanluis.gov.ar/pls/apex/f?p=VISPUB:1` funciona así:

1. **Sesión Oracle APEX.** La dirección base redirige (dos 302) a una sesión nueva, por ejemplo `f?p=VISPUB:1:9564563888057:::::`. El número de sesión (`p_instance`) cambia en cada visita y se lee del formulario (`<input name="p_instance">`). La página trae en el campo oculto `P1_CATGIS_VISUALIZADOR_URL` la dirección del mapa con un TOKEN de un solo uso: `http://visualcatsl.dyndns.info/mapsPortlet/?TOKEN=…`.
2. **Mapa.** Es una app Angular con OpenLayers. Dibuja y consulta las capas de un **GeoServer 2.3 público** en el mismo servidor (`/geoserver/wfs` y `/geoserver/SanLuis/wms`), espacio de trabajo `SanLuis`, 42 capas en EPSG:22183 (Gauss-Krüger faja 3). Al hacer clic pide un `GetFeatureInfo` en JSON; la búsqueda por nomenclatura es un `GetFeature` con `cql_filter=CATNMC_CAT='…'`.
3. **Capas de parcelas** que usa el conector: `GIS_PARCELAS_RUR_VV` (rurales), `GIS_PARCELAS_SUB_VV` (suburbanas) y `GIS_PARCELAS_URB_VV` (urbanas). Atributos: `CATNMC_CAT` (nomenclatura catastral), `CATNMC_TRI` (nomenclatura tributaria = partida), `ETIQUETA` (número de parcela), `CATMEN_CODIGO` (plano de mensura) y `NOMBRE`, que es la ficha del visor: `Parcela: 3565 \n Nom.Catastral: … \n Nom.Tributaria: … \n Sup. Terreno: 5278958.35 m2 \n Tipo Parcela: RURAL \n Plano Mensura: …`.
4. El GeoServer **reproyecta a EPSG:4326** si se le pide `srsName=EPSG:4326`, y acepta la caja de búsqueda en grados (`bbox=oeste,sur,este,norte,EPSG:4326`). No hace falta reproyectar nada de nuestro lado.
5. La ficha detallada (`LINK`, `f?p=2023:150` con `P150_TOKEN`) **no es pública**: pide un token cifrado del visor y responde "Usted no se encuentra habilitado". No se usa.

El servicio del mapa no pide la sesión APEX. Igual el conector abre una sesión nueva del visor para leer de ahí en qué servidor está el mapa, así que si la provincia lo muda, el conector lo sigue sin cambiar código. **Nunca usa un Session ID fijo.**

## Entrada

Una de tres: `lat` y `lon` (grados decimales, EPSG:4326), `nomenclatura` catastral (`E5-03-01-00-000000-003565`) o `partida` (`01-1064404`).

## Proceso

1. Abrir sesión en el visor (`GET f?p=VISPUB:1`), leer `p_instance` y la dirección del mapa. Se reutiliza una hora. Si el visor no responde o cambió, se usa el servidor conocido (`visualcatsl.dyndns.info`) y la `nota` lo dice.
2. Pedir al WFS, en las tres capas de parcelas a la vez:
   - por punto: las parcelas que tocan una caja de ±0,0005° (~50 m) alrededor del punto, y quedarse con la que **contiene** el punto (shapely);
   - por nomenclatura o partida: `CQL_FILTER=CATNMC_CAT='…'` o `CATNMC_TRI='…'`.
3. Leer los atributos y la ficha, medir la superficie del polígono y armar el resultado.

## Salida

No es una serie en el tiempo, así que **no usa el contrato `Observacion`**: devuelve los datos fijos del lote (`ParcelaCatastral`), con la misma idea de calidad y nota.

| Campo | Qué es |
|---|---|
| `geometria_lote` | GeoJSON **Polygon** EPSG:4326, listo para recortar satélites (pasa `validar_poligono`) |
| `geometria_parcela` | La geometría completa tal como la da el Catastro (puede ser MultiPolygon) |
| `nomenclatura_catastral` | ID provincial: cuadrante-departamento-circunscripción-sección-manzana-parcela |
| `partida_inmobiliaria` | "Nom. Tributaria" del visor (padrón de Rentas) |
| `superficie_registrada_m2` | Superficie del terreno según el Catastro (mensura) |
| `superficie_calculada_m2` | Medida sobre el polígono devuelto, para validar |
| `tipo_parcela` | RURAL, SUBURBANA o URBANA |
| `numero_parcela`, `plano_mensura`, `capa` | Datos de referencia |
| `fuente`, `fecha_consulta`, `calidad`, `nota` | "Catastro San Luis", día de la consulta, `buena` / `dudosa` / `descartada`, y por qué |

## Reglas de calidad

1. **Nunca inventar.** Si el punto no cae en ninguna parcela publicada (camino, ruta, curso de agua, parcela sin datos públicos o fuera de la provincia), o la nomenclatura o partida no existe, todo queda en `null`, `calidad: "descartada"` y la `nota` explica por qué.
2. Superficie medida y registrada con más de **5 %** de diferencia → `dudosa` (**supuesto**: el polígono digitalizado no coincide con la mensura).
3. Parcela en varias partes → `geometria_lote` es la parte mayor y queda `dudosa`.
4. El punto cae en dos parcelas superpuestas → se elige la más chica y queda `dudosa`, con las otras nombradas en la `nota`.
5. Polígono del Catastro con el borde cruzado sobre sí mismo (inválido) → se repara con `make_valid`, quedan solo las partes con superficie y queda `dudosa`, con la `nota` que lo dice. Así `geometria_lote` siempre pasa `validar_poligono` y `POST /consulta` lo acepta. En el mapa completo esas parcelas traen `geometria_reparada: true`.
6. Nomenclaturas y partidas solo aceptan letras, números y guiones (evita inyectar filtros en el WFS).
7. Sin base de datos: todo se pide en el momento, con `httpx` asincrónico.

## API

`GET /catastro-sl/parcela?lat=-33.700&lon=-65.300` (o `?nomenclatura=…` o `?partida=…`) → `ParcelaCatastral`. `422` si faltan o están mal los parámetros, `502` si el Catastro no responde. Una parcela que no existe no es error: vuelve `200` con `descartada`.

## Mapa completo de parcelas rurales (pedido de Hernán)

Hernán pidió que se tenga en cuenta "el mapa completo con todas las parcelas rurales", para que Daniel pueda cargarlas en el frontend.

- `GET /catastro-sl/parcelas-rurales` devuelve **todas** las parcelas de `GIS_PARCELAS_RUR_VV` como GeoJSON `FeatureCollection` en EPSG:4326. Cada parcela trae `id` (la nomenclatura) y `properties` con `nomenclatura_catastral`, `partida_inmobiliaria`, `numero_parcela`, `tipo_parcela`, `plano_mensura`, `superficie_registrada_m2` y `geometria_reparada`, más `fuente`, `fecha_consulta`, `cantidad`, `truncado` y `nota` en la colección.
- Para no pedirle 11 MB al Catastro en cada consulta, sin base de datos, el mapa completo se guarda **en memoria un día**, ya comprimido con gzip. La respuesta va comprimida si el cliente la acepta (todos los navegadores) y con `Cache-Control` de un día.
- Con `oeste`, `sur`, `este` y `norte` devuelve solo las parcelas de esa zona del mapa, pedidas en el momento, hasta **5000**. Si hay más, devuelve 5000 con `truncado: true` y la `nota` pide acercar el mapa.
- Las coordenadas se redondean a 6 decimales (~0,1 m), que alcanza para dibujar y achica el archivo.
- Sin parcelas en la zona → colección vacía y la `nota` lo dice. Caja al revés o incompleta → `422`. Catastro caído → `502`.
- La prueba real exporta el mapa completo como archivo descargable de GitHub Actions (`parcelas-rurales-san-luis`, se guarda 30 días).

Conteo del Catastro: **17.976** parcelas rurales, 2.418 suburbanas, 257.825 urbanas y 9 departamentos. Las urbanas no se exportan completas (son 14 veces más); se consultan una por una con `/catastro-sl/parcela`.

## Aislamiento

Vive en `rotaterra/fuentes/catastro_sl.py` y solo usa `httpx`, `shapely` y FastAPI; no importa ningún satélite ni toca el núcleo. Declara `SATELITES = []` (la actualización nocturna no lo pide, porque no es una serie) y trae su `router`.

## Criterios de aceptación

- [x] Maneja solo el Session ID de Oracle APEX, sin copiar ni pegar nada: abre una sesión nueva en cada corrida y lee de ahí el servidor del mapa (prueba real: "servidor leído del visor público (sesión APEX nueva)"; test `test_la_sesion_apex_se_lee_del_visor_y_nunca_es_fija`).
- [x] Con un punto devuelve la nomenclatura y el polígono. Punto de prueba (-33,700; -65,300), en **1,9 s**: parcela rural **3565**, nomenclatura **E5-03-01-00-000000-003565**, partida **01-1064404**, plano **03-234-2020**, **527,90 ha** registradas y 523,90 ha medidas sobre el polígono (0,8 % de diferencia, `buena`), polígono de 8 vértices.
- [x] La misma parcela se encuentra por nomenclatura (0,5 s) y por partida (0,5 s).
- [x] Un punto sin parcela no inventa nada (Pergamino, fuera de San Luis → `descartada`).
- [x] Prueba automática en GitHub Actions: `Probar CATASTRO_SL (límites y parcelas)`, corre en cada PR que toque el conector y a mano con un clic (con otro punto o una nomenclatura).
- [x] Mapa completo de parcelas rurales: **17.976** parcelas en **7 s**, todas con polígono y superficie; 11,4 MB, o **2,3 MB comprimido**. 6.258 no tienen nomenclatura publicada y quedan en `null`. La zona del lote de prueba (0,04° × 0,04°) da 13 parcelas (prueba real, archivo descargable en Actions).
- [x] Todos los polígonos rurales sirven como lote: de las 17.976 parcelas del archivo, 1 venía inválida (parcela 2160, B5-06-43-00-000000-002160, borde cruzado en -64,959321 / -32,412886); reparada, las **17.976** pasan `validar_poligono` (control, hallado por el hilo de satélites).
- [x] Aislado en su propia rama, sin tocar el núcleo ni los satélites; 25 tests sin internet con el visor y el GeoServer simulados.

## Riesgos conocidos

- **La parcela no es el lote.** El lote de prueba de 25,7 ha está **dentro** de una parcela de 527,9 ha. Una parcela catastral puede tener varios lotes de manejo, y un lote puede cruzar dos parcelas. El polígono oficial sirve de punto de partida y de control legal; el lote agronómico lo confirma el productor.
- El servidor del mapa es un **dyndns** (`visualcatsl.dyndns.info`) con GeoServer 2.3 (de 2013) y sin HTTPS. Puede cambiar de dirección o caerse; el conector sigue la dirección del visor y, si no responde, avisa con `502`.
- Es un servicio público pero no documentado: si la provincia cambia los nombres de las capas o de los campos, el conector falla y la prueba real lo muestra.
- Las parcelas sin registro, de posesión, judiciales y de derecho de superficie están en otras capas y no se consultan.

## Fuera de alcance

El mapa completo de parcelas suburbanas y urbanas, el avalúo fiscal y el valor por hectárea (están en `GIS_PARCELAS_RUR_RANGO_VV`, no se pidieron), titulares y la ficha privada del visor, y otras provincias.
