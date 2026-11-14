# GeoINTA - suelo del lote (cartas de suelo del INTA)

**Rama:** `fuente-geointa-suelo-del-lote` · **Conector:** `rotaterra/fuentes/geointa.py` · **Specs:** `docs/specs/020-suelo-geointa.md`, `docs/specs/021-anexo-geoservicios.md`, `docs/specs/021-geointa-capas-ampliadas.md`, `docs/specs/044-memoria-del-suelo-geointa.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector GeoINTA: suelo e historia de cultivos del lote desde los geoservicios del INTA (specs 020 y 021).

Excepción prevista a la regla NASA (Guía técnica): el suelo lo releva el INTA, no un satélite.
Las cartas de suelo se consultan por WFS sin bajar geometrías (algunas unidades, como las áreas urbanas de
Buenos Aires, son enormes): primero qué unidades tocan el lote y después en qué unidad cae cada punto de una
grilla dentro del lote. La unidad dominante es la que tiene más puntos.
El Mapa Nacional de Cultivos se recorta por WCS al lote y se cuentan sus píxeles de 30 m (spec 021).
La textura y el pH se leen por WMS en una grilla de puntos, porque el INTA no los publica por WCS ni WFS
(spec 021, decisión de Hernán del 4/10/2026).
El carbono orgánico del suelo 2023 se recorta por WCS al lote y se promedian sus píxeles de 250 m (spec 021, §23.6).


## Cómo se prueba

- Sin internet: `pytest -q tests/test_geointa.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow `probar-geointa.yml` en Actions (corre en el PR y se puede lanzar a mano), o `python probar_geointa.py` en la compu.
- No necesita claves.

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ninguna otra fuente.
