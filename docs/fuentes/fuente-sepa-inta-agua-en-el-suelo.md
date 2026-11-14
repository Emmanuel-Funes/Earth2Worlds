# SEPA INTA - agua en el suelo y anomalía de vegetación

**Rama:** `fuente-sepa-inta-agua-en-el-suelo` · **Conector:** `rotaterra/fuentes/sepa_inta.py` · **Specs:** `docs/specs/023-sepa-inta-historial-goes.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector SEPA INTA y GOES-19: agua en el suelo, anomalías, heladas, temperatura de superficie y Q de trigo (spec 023).

De dónde sale cada número (ver la spec 023, §5):
- **SEPA INTA (GeoSEPA):** balance hídrico por década desde mayo de 2024 (agua disponible hasta 2 m, confort hídrico,
  variación, drenaje y porcentaje de agua), y la última anomalía histórica de NDVI de 16 días y su persistencia.
  Son GeoTIFF; se lee solo el pedazo del lote con pedidos por rangos de bytes (nunca el mapa entero).
- **GOES-19 (NOAA):** los visores de heladas y de temperatura diurna de SEPA se calculan con GOES-19. Acá se lee el
  producto oficial de la NOAA (temperatura de superficie, topes nubosos, infrarrojo y rayos) del archivo abierto en AWS.
- **Q de trigo:** el INTA lo estima con el pronóstico GFS. Acá se calcula igual (Tb 4,5 °C) con datos de NASA POWER.
- Los productos de SEPA que solo existen como imagen de colores van con `valor: null` y la dirección de la imagen en
  la `nota`, para que el frontend la muestre. Nunca se lee un número de un color.

## Permiso de uso

SEPA es del Instituto de Clima y Agua (CIRN-INTA). El CIRN-INTA autorizó su uso **solo para la hackatón de la NASA**. Cualquier otro uso, y sobre todo un uso comercial, necesita acordar antes las condiciones con el INTA. Cada dato lleva la cita al INTA en su nota.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_sepa_inta.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow `probar_sepa_inta_completo.yml` en Actions (corre en el PR y se puede lanzar a mano), o `python probar_sepa_inta.py` en la compu.
- No necesita claves.

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ninguna otra fuente.
