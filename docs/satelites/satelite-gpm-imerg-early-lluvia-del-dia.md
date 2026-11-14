# IMERG Early - lluvia del día (respaldo del día de IMERG)

**Rama:** `satelite-gpm-imerg-early-lluvia-del-dia` · **Conector:** `rotaterra/fuentes/imerg_early.py` · **Specs:** ver docstring del conector

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector IMERG Early: lluvia del día, respaldo "del día" de IMERG (spec 043).

IMERG Late diario sale con 1 día de atraso. IMERG Early es la misma lluvia de la NASA (GPM) calculada más rápido y con
menos correcciones: el archivo de cada media hora sale unas 4 a 9 horas después. Solo completa los últimos días que
IMERG todavía no publicó: el núcleo lo pide con `al_dia=True` (spec 043, parte A).

Igual que IMERG, el día es el día UTC (de las 21 h del día anterior a las 21 h en Argentina).

Satélite independiente (spec 009): hace su propio pedido a la NASA y no importa a ningún otro satélite.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_imerg_early.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-imerg-early.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_imerg_early.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
