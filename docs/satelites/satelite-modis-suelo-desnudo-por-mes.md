# MODIS - meses del año con el lote sin cobertura verde

**Rama:** `satelite-modis-suelo-desnudo-por-mes` · **Conector:** `rotaterra/fuentes/suelo_desnudo.py` · **Specs:** `docs/specs/060-suelo-desnudo-por-mes.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector suelo desnudo: en qué meses del año el lote queda sin cobertura verde, con 5 años de MODIS (spec 060).

El desafío pide mostrar cuándo los lotes quedan típicamente desnudos: es cuando el suelo se vuela (erosión eólica en
los suelos arenosos de San Luis), pierde agua por evaporación y no suma carbono. Es el hueco donde entra un cultivo de
servicio o un verdeo.

Se usa el NDVI de 250 m de MODIS Terra (MOD13Q1, compuestos de 16 días) de los últimos 4 años (48 meses): es el NDVI
de la NASA con historia larga que se lee en pocos minutos. Cada compuesto se pide por OPeNDAP, solo la ventana del lote.
El OPeNDAP de la NASA sirve MOD13Q1 desde mediados de 2022 (los compuestos anteriores dan 404), por eso 4 años y no más.
Un mes cuenta como "desnudo" en un año si la mediana del NDVI del lote ese mes es menor a 0,25, y con "cobertura baja"
si es menor a 0,30.

Satélite independiente (spec 009): repite a propósito la lectura de MODIS del conector de NDVI y no lo importa.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_suelo_desnudo.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-suelo-desnudo.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_suelo_desnudo.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
