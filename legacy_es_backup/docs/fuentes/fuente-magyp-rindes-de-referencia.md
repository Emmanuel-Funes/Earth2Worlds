# MAGyP - rindes de referencia por departamento (Estimaciones Agrícolas)

**Rama:** `fuente-magyp-rindes-de-referencia` · **Conector:** `rotaterra/fuentes/magyp_rindes.py` · **Specs:** `docs/specs/040-rindes-de-referencia-magyp.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector MAGyP: rindes de referencia del departamento (spec 040).

Las Estimaciones Agrícolas del Ministerio de Agricultura, Ganadería y Pesca (MAGyP) dan, por departamento y
por campaña, la superficie sembrada y cosechada, la producción y el rinde de cada cultivo. De ahí sale un rinde
de referencia por cultivo: la mediana de las últimas 10 campañas con rinde. Es un dato DEL DEPARTAMENTO, no del
lote: sirve para comparar cultivos y tener un orden de magnitud, no reemplaza el historial del productor.

El departamento del lote sale de la API Georef del Estado nacional (o viene en el pedido). No es una fuente de la
NASA: entra como excepción aprobada por Hernán el 14/11/2026 (Georef, el 14/11/2026). No hay respaldo.

El servidor del Ministerio no responde desde fuera del país (14/11/2026), y Render está en Estados Unidos. Por eso
la app lee una copia del CSV vigente guardada en el repo (`datos/magyp_rindes.csv.gz`, solo los cultivos del
catálogo desde 2000/01). El Ministerio publica un archivo nuevo una o dos veces por año; la copia se renueva con
el workflow "Actualizar copia de MAGyP (rindes de referencia)".


## Cómo se prueba

- Sin internet: `pytest -q tests/test_magyp_rindes.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow `probar-magyp-rindes.yml` en Actions (corre en el PR y se puede lanzar a mano), o `python probar_magyp_rindes.py` en la compu.
- No necesita claves.

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ninguna otra fuente.
