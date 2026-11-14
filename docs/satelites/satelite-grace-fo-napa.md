# GRACE-FO - napa y agua profunda de la región

**Rama:** `satelite-grace-fo-napa` · **Conector:** `rotaterra/fuentes/grace.py` · **Specs:** `docs/specs/026-napa-grace-fo.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector GRACE-FO: napa y agua profunda de la región (spec 026).

Principal: indicadores de sequía GRACE-DA de la NASA (GRACEDADM_CLSM025GL_7D, Goddard), un percentil
semanal de agua subterránea, de humedad en la zona de raíces y de humedad superficial, en una grilla
de 0,25°. Respaldo: anomalía mensual del agua total de los mascons de JPL (TELLUS_GRAC-GRFO_MASCON_CRI).
Las dos se leen por OPeNDAP de la NASA, solo en el píxel del centro del lote. Es un dato REGIONAL:
GRACE-FO mide la gravedad con una resolución real de unos 300 km.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_grace.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-grace.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_grace.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
