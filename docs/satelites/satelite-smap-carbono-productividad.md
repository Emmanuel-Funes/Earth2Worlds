# SMAP L4 Carbono - productividad de la vegetación

**Rama:** `satelite-smap-carbono-productividad` · **Conector:** `rotaterra/fuentes/smap_carbono.py` · **Specs:** `docs/specs/055-productividad-smap-carbono.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector SMAP L4 Carbono: productividad diaria de la vegetación alrededor del lote (spec 055).

SMAP L4C (NASA) combina la humedad del suelo de SMAP con la luz absorbida por las plantas y calcula, todos los
días y en celdas de 9 km, cuánto carbono fija la vegetación (GPP, productividad primaria bruta) y el balance
neto del ecosistema (NEE). Reemplaza la productividad de MODIS (MOD17), que deja de salir con el fin de MODIS.

Es un dato **regional**: una celda de 9 km tiene ~8.100 ha, y el lote de 25 ha cae dentro. Sirve para comparar
campañas y ver cómo viene la zona; no es el rinde del lote.

Cada archivo pesa ~140 MB. No se baja: se pide por OPeNDAP solo el valor de la celda del lote (un pedido por día).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_smap_carbono.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-smap-carbono.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_smap_carbono.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
