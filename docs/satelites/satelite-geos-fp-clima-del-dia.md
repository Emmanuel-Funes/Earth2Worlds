# GEOS-FP - clima y ET del día (respaldo del día de POWER)

**Rama:** `satelite-geos-fp-clima-del-dia` · **Conector:** `rotaterra/fuentes/geos_fp.py` · **Specs:** ver docstring del conector

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector GEOS-FP: clima y evapotranspiración del día del modelo de la NASA, respaldo "del día" de POWER y de ET
(spec 043).

POWER publica con 4 días de atraso (la radiación con 7) y la evapotranspiración de MODIS con 8 días o más. GEOS-FP es el
modelo con el que trabaja la NASA (GMAO) y publica cada hora con unas 9 horas de atraso, en celdas de 0,25° × 0,3125°
(unos 28 km). Solo completa los últimos días que la principal todavía no publicó: el núcleo lo pide con `al_dia=True`
(spec 043, parte A).

Satélite independiente (spec 009): hace su propio pedido a la NASA y no importa a ningún otro satélite. El servidor
OPeNDAP de GEOS-FP es público: no usa la cuenta de Earthdata.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_geos_fp.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-geos-fp.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_geos_fp.py <lat> <lon> <desde> <hasta>` en la compu.
- No necesita claves.

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
