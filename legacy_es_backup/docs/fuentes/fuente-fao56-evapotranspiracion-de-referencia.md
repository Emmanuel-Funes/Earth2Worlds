# FAO-56 - evapotranspiración de referencia calculada con NASA POWER

**Rama:** `fuente-fao56-evapotranspiracion-de-referencia` · **Conector:** `rotaterra/fuentes/et0_fao56.py` · **Specs:** `docs/specs/019-et0-fao56-respaldo.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

ET de referencia FAO-56 (Penman-Monteith) con el clima diario de NASA POWER: último respaldo de la ET (spec 019).

Es la ET de un pasto de referencia, NO la ET real del cultivo: ET cultivo = Kc × ET0 (FAO-56, capítulo 6).


## Cómo se prueba

- Sin internet: `pytest -q tests/test_et0_fao56.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow `probar-et0.yml` en Actions (corre en el PR y se puede lanzar a mano), o `python probar_et0.py` en la compu.
- No necesita claves.

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ninguna otra fuente.
