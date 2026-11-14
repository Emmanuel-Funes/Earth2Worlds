# NISAR - radar banda L a 20 m, con o sin nubes

**Rama:** `satelite-nisar-radar` · **Conector:** `rotaterra/fuentes/nisar.py` · **Specs:** `docs/specs/008-altimetria-nasadem.md`, `docs/specs/054-radar-nisar.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector NISAR: radar en banda L a 20 m sobre el lote, con nubes o sin nubes (spec 054).

NISAR es la misión de radar de la NASA y la ISRO (agencia socia permitida, spec 008). El producto GCOV da cuánto
"rebota" el radar en el suelo y la planta (retrodispersión gamma0, ya corregida por el relieve), en dos
polarizaciones: HH (sube con el suelo mojado y la rugosidad) y HV (sube con la biomasa del cultivo).

Cada archivo pesa ~1,8 GB. No se baja: se leen por HTTP solo los pedazos (de ~1 MB) que caen sobre el lote.
El producto es **provisional** (NASA todavía no lo dio por validado): todo dato sale como mucho "dudoso".

## Cómo se prueba

- Sin internet: `pytest -q tests/test_nisar.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-nisar.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_nisar.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
