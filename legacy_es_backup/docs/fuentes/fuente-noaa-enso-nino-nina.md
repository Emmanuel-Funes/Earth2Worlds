# NOAA - estado de El Niño / La Niña (ENSO)

**Rama:** `fuente-noaa-enso-nino-nina` · **Conector:** `rotaterra/fuentes/noaa_enso.py` · **Specs:** `docs/specs/039-el-nino-la-nina-noaa.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

El Niño / La Niña de NOAA CPC como aviso de la campaña (spec 039).

Satélite independiente (spec 009): baja sus propios archivos de NOAA y no usa otros satélites.
NOAA es una de las agencias socias de la NASA permitidas (spec 008).

- Principal: el ONI (Oceanic Niño Index) de CPC, la anomalía de temperatura del mar en la región
  Niño 3.4 en trimestres móviles, más la sinopsis y el estado de alerta de la discusión mensual de ENSO.
- Respaldo: el índice Niño 3.4 mensual de NOAA PSL (ERSST, hoy V6), promediando los tres últimos meses
  publicados. Es otro servidor de NOAA.

El índice es uno solo para todo el planeta: no depende del lote. Por eso se ignoran el lugar y el
período pedidos y siempre sale el último dato publicado.


## Cómo se prueba

- Sin internet: `pytest -q tests/test_noaa_enso.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow `probar-noaa-enso.yml` en Actions (corre en el PR y se puede lanzar a mano), o `python probar_noaa_enso.py` en la compu.
- No necesita claves.

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ninguna otra fuente.
