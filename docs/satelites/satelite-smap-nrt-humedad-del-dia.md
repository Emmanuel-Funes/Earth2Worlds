# SMAP NRT - humedad del día (respaldo del día de SMAP)

**Rama:** `satelite-smap-nrt-humedad-del-dia` · **Conector:** `rotaterra/fuentes/smap_nrt.py` · **Specs:** ver docstring del conector

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector SMAP NRT: humedad superficial del día (SPL2SMP_NRT, 36 km), respaldo "del día" de SMAP (spec 043).

SMAP L4 (la principal) publica con unos 2 días de atraso. El producto de tiempo casi real SPL2SMP_NRT sale unas 2 horas
después de cada pasada (6 a 7 de la mañana o 19 a 20 en Argentina), en celdas EASE-2 de 36 km. Solo completa los últimos
días que SMAP todavía no publicó: el núcleo lo pide con `al_dia=True` (spec 043, parte A).

Satélite independiente (spec 009): busca en CMR y baja los archivos de NSIDC con la cuenta de Earthdata.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_smap_nrt.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-smap-nrt.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_smap_nrt.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_smap_nrt.py "-33.70" "-65.30" "" ""`

```
SMAP NRT (humedad del día) en (-33.7, -65.3) del 2026-11-14 al 2026-11-14 · 6 s

2026-11-14    0.141 m³/m³  dudosa      promedio de 1 de 1 pasadas (22:41 UTC) · centro de la celda a 15 km del lote
2026-11-14    0.133 m³/m³  dudosa      promedio de 1 de 1 pasadas (09:40 UTC) · centro de la celda a 15 km del lote
2026-11-14    0.093 m³/m³  dudosa      promedio de 1 de 1 pasadas (10:16 UTC) · centro de la celda a 15 km del lote
2026-11-14    0.169 m³/m³  dudosa      promedio de 1 de 1 pasadas (22:53 UTC) · centro de la celda a 15 km del lote
2026-11-14    0.131 m³/m³  dudosa      promedio de 1 de 1 pasadas (09:52 UTC) · centro de la celda a 15 km del lote
```
