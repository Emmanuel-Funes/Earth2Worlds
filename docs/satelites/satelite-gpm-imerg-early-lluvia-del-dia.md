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

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_imerg_early.py "-33.70" "-65.30" "" ""`

```
GPM_3IMERGDE: colección C2723754850-GES_DISC · 1 archivos con OPeNDAP entre ayer y hoy · último GPM_3IMERGDE.07:3B-DAY-E.MS.MRG.3IMERG.20261113-S000000-E235959.V07C.nc4
GPM_3IMERGHHE: colección C2723758340-GES_DISC · 64 archivos con OPeNDAP entre ayer y hoy · último GPM_3IMERGHHE.07:3B-HHR-E.MS.MRG.3IMERG.20261114-S073000-E075959.0450.V07C.HDF5

IMERG Early en (-33.7, -65.3) del 2026-11-11 al 2026-11-14 (días UTC) · 3 s

2026-11-11     0.0 mm  buena      IMERG Early de la NASA (GPM), sin corregir con pluviómetros · celda de 0,1° · día UTC · archivo diario
2026-11-12     0.0 mm  buena      IMERG Early de la NASA (GPM), sin corregir con pluviómetros · celda de 0,1° · día UTC · archivo diario
2026-11-13     4.0 mm  buena      IMERG Early de la NASA (GPM), sin corregir con pluviómetros · celda de 0,1° · día UTC · archivo diario
2026-11-14     0.3 mm  dudosa     IMERG Early de la NASA (GPM), sin corregir con pluviómetros · celda de 0,1° · día UTC · día en curso: lluvia hasta las 08:00 UTC (16 de 48 medias horas)
```
