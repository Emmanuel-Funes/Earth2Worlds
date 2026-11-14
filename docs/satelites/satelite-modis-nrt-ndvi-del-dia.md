# MODIS NRT - NDVI del día (respaldo del día de HLS)

**Rama:** `satelite-modis-nrt-ndvi-del-dia` · **Conector:** `rotaterra/fuentes/modis_nrt.py` · **Specs:** ver docstring del conector

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector MODIS NRT: NDVI del día de 250 m (LANCE, MOD13Q4N), respaldo del día de HLS (spec 043).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_modis_nrt.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-modis-nrt.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_modis_nrt.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (en GitHub Actions, corrida https://github.com/Emmanuel-Funes/Earth2Worlds/actions/runs/43600978037). Lote de prueba de San Luis.

Comando: `python probar_modis_nrt.py "-33.70" "-65.30" "" ""`

```
MODIS NRT (NDVI del día) en (-33.7, -65.3), lado 0.01°, del 2026-11-14 al 2026-11-14 · 4 s

2026-11-14    0.282  dudosa      MOD13Q4N.A2026317.h12v12.061.2026317205006, compuesto del 2026-11-14 al 2026-11-14 · 16 píxeles de 250 m · píxeles vistos este día 100%
```
