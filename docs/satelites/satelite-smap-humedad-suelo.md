# SMAP L4 - humedad del suelo diaria

**Rama:** `satelite-smap-humedad-suelo` · **Conector:** `rotaterra/fuentes/smap.py` · **Specs:** `docs/specs/003-conector-smap-humedad.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector SMAP L4: humedad del suelo diaria (spec 003).

Dos caminos al mismo producto de la NASA (SPL4SMGP):
- directo: CMR + OPeNDAP de la NASA, un píxel por archivo de 3 h. Rápido, sin fila de espera (principal).
- AppEEARS: la NASA arma el pedido y avisa cuando está; puede tardar de 5 a 40 minutos (respaldo, spec 005).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_smap.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-smap.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_smap.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
