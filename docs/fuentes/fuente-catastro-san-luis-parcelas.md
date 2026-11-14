# Catastro de San Luis - parcelas rurales para elegir el lote

**Rama:** `fuente-catastro-san-luis-parcelas` · **Conector:** `rotaterra/fuentes/catastro_sl.py` · **Specs:** `docs/specs/025-catastro-san-luis.md`, `docs/specs/045-copia-del-mapa-del-catastro.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector CATASTRO_SL: límites oficiales y datos de una parcela del Catastro de San Luis (spec 025).

Excepción a la regla de fuentes (decisión de Hernán, spec 025): la Dirección Provincial de Catastro y Tierras
Fiscales de San Luis es la fuente oficial de los límites de los lotes en la provincia.

Cómo funciona el visor público (relevado con ingeniería inversa, ver la spec):
1. `f?p=VISPUB:1` (Oracle APEX) redirige a una sesión nueva (`p_instance`) y trae, en el campo oculto
   `P1_CATGIS_VISUALIZADOR_URL`, la dirección del mapa con un TOKEN de un solo uso.
2. El mapa (Angular + OpenLayers) dibuja y consulta las capas de un GeoServer público en el mismo servidor,
   con WMS/WFS. Las parcelas están en las capas `SanLuis:GIS_PARCELAS_RUR_VV`, `_SUB_VV` y `_URB_VV`
   (EPSG:22183, Gauss-Krüger faja 3), y el GeoServer las reproyecta a EPSG:4326 si se le pide.
Este conector abre la sesión del visor para saber en qué servidor está el mapa (nunca usa un Session ID fijo)
y después consulta el WFS directamente.

## Qué datos trae la copia

La copia del mapa trae solo datos públicos de la parcela: nomenclatura catastral, partida, número de parcela, plano de mensura, superficie y el dibujo. **No trae nombres de titulares ni datos personales.**

## Cómo se prueba

- Sin internet: `pytest -q tests/test_catastro_sl.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow `probar-catastro-sl.yml` en Actions (corre en el PR y se puede lanzar a mano), o `python probar_catastro_sl.py` en la compu.
- No necesita claves.

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ninguna otra fuente.
