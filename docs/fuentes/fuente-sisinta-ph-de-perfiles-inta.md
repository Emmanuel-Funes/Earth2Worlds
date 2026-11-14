# SISINTA - pH medido en perfiles de suelo del INTA cerca del lote

**Rama:** `fuente-sisinta-ph-de-perfiles-inta` · **Conector:** `rotaterra/fuentes/sisinta.py` · **Specs:** `docs/specs/048-ph-de-perfiles-medidos-sisinta.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector SISINTA: pH medido en los perfiles de suelo del INTA cerca del lote (spec 048).

SISINTA es la base nacional de perfiles de suelo del INTA. GeoINTA la publica como capa de puntos (id 702,
dominio público) y se lee por WFS del nodo 05 sin clave. Cada feature es un HORIZONTE de un perfil, con su
profundidad y su pH en agua. Casi todos los campos llegan como texto y el faltante es el texto "NA".

Para cada perfil se calcula el pH en agua de 0-30 y de 30-100 cm, pesado por el espesor de cada horizonte, y se
entrega la mediana de los perfiles a 10 km del lote (o a 25 km si no hay ninguno). Es una referencia regional:
mediciones puntuales, casi todas de 1975-1988, de lotes vecinos. Nunca reemplaza al análisis del productor.
No importa a ningún otro satélite (spec 009).


## Cómo se prueba

- Sin internet: `pytest -q tests/test_sisinta.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow `probar-sisinta.yml` en Actions (corre en el PR y se puede lanzar a mano), o `python probar_sisinta.py` en la compu.
- No necesita claves.

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ninguna otra fuente.
