# GOES-19 - temperatura mínima de la madrugada (heladas del día)

**Rama:** `satelite-goes-heladas-del-dia` · **Conector:** `rotaterra/fuentes/goes_heladas.py` · **Specs:** `docs/specs/023-sepa-inta-historial-goes.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector GOES-19 heladas: temperatura de superficie mínima de la madrugada, respaldo "del día" de VIIRS (spec 043).

VIIRS publica la temperatura nocturna con 1 a 2 días de atraso. GOES-19, el satélite geoestacionario de la NOAA (socia
de la NASA), mira la Argentina todo el tiempo y publica la temperatura de superficie cada hora con menos de 1 hora de
atraso, en píxeles de 10 km. Se toma la mínima entre las 4 y las 7 de la mañana, cerca del mínimo térmico, como en los
visores de heladas de SEPA (spec 023). Solo completa los últimos días que VIIRS todavía no publicó: el núcleo lo pide
con `al_dia=True` (spec 043, parte A).

Satélite independiente (spec 009): no importa a ningún otro satélite. El archivo de la NOAA en AWS es abierto: no usa
cuenta.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_goes_heladas.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-goes-heladas.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_goes_heladas.py <lat> <lon> <desde> <hasta>` en la compu.
- No necesita claves.

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
