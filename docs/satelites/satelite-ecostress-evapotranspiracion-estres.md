# ECOSTRESS - evapotranspiración y estrés hídrico a 70 m

**Rama:** `satelite-ecostress-evapotranspiracion-estres` · **Conector:** `rotaterra/fuentes/ecostress.py` · **Specs:** `docs/specs/018-ecostress-et-y-estres.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector ECOSTRESS: evapotranspiración diaria y estrés hídrico (ESI) del lote a 70 m (spec 018).

Primer respaldo de la ET principal: si la principal falla, entra ECOSTRESS; si tampoco trae datos, entra FAO-56.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_ecostress.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-ecostress.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_ecostress.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
