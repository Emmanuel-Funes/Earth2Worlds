# NASA POWER - clima de la campaña (heladas, lluvia esperada, grados-día)

**Rama:** `fuente-nasa-power-clima-de-campana` · **Conector:** `rotaterra/fuentes/power_campana.py` · **Specs:** `docs/specs/034-clima-de-campana-power.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector clima de la campaña con NASA POWER (spec 034).

Una climatología del lote para el motor de recomendación: días libres de heladas, fechas de helada con riesgo,
lluvia esperada de octubre a marzo, grados-día y la fecha en que el suelo pasa los 14 °C. Sale de 35 años de
POWER (API diaria por punto, sin cuenta) en el centro del lote. Es un dato REGIONAL: la celda de POWER es de ~0,5°.

Respaldo: la temperatura horaria a 2 m de MERRA-2 (M2T1NXSLV) por el servicio de series de tiempo de Giovanni
(GES DISC, NASA), con el token de Earthdata.
Solo da heladas y grados-día; la lluvia y el suelo quedan sin respaldo (spec 034 §2).


## Cómo se prueba

- Sin internet: `pytest -q tests/test_power_campana.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow `probar-power-campana.yml` en Actions (corre en el PR y se puede lanzar a mano), o `python probar_power_campana.py` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ninguna otra fuente.
