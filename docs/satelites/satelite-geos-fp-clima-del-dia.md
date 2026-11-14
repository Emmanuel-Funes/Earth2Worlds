# GEOS-FP - clima y ET del día (respaldo del día de POWER)

**Rama:** `satelite-geos-fp-clima-del-dia` · **Conector:** `rotaterra/fuentes/geos_fp.py` · **Specs:** ver docstring del conector

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector GEOS-FP: clima y evapotranspiración del día del modelo de la NASA, respaldo "del día" de POWER y de ET
(spec 043).

POWER publica con 4 días de atraso (la radiación con 7) y la evapotranspiración de MODIS con 8 días o más. GEOS-FP es el
modelo con el que trabaja la NASA (GMAO) y publica cada hora con unas 9 horas de atraso, en celdas de 0,25° × 0,3125°
(unos 28 km). Solo completa los últimos días que la principal todavía no publicó: el núcleo lo pide con `al_dia=True`
(spec 043, parte A).

Satélite independiente (spec 009): hace su propio pedido a la NASA y no importa a ningún otro satélite. El servidor
OPeNDAP de GEOS-FP es público: no usa la cuenta de Earthdata.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_geos_fp.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-geos-fp.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_geos_fp.py <lat> <lon> <desde> <hasta>` en la compu.
- No necesita claves.

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_geos_fp.py "-33.70" "-65.30" "" ""`

```
Última hora publicada: 14/11/2026 02:30 UTC · 78483 horas en la serie
t2m, [3][1][1]
[0][0], 302.33105

[1][0], 301.31873

[2][0], 299.74908


time, [3]
739935.0208333334, 739935.0625, 739935.1041666666
lat, [1]
-33.75
lon, [1]
-65.3125


GEOS-FP (clima del día) en (-33.7, -65.3) del 2026-11-10 al 2026-11-14 · 31 s

Fecha         Máx °C  Mín °C   MJ/m²  Lluvia mm  Calidad de la máxima
2026-11-10      22.6    16.5     8.3        2.0  buena
2026-11-11      31.8    15.0    30.8        0.0  buena
2026-11-12      36.6    17.2    30.4        1.7  buena
2026-11-13      36.3    20.3    26.4        2.3  buena
2026-11-14         —       —       —          —  descartada

Nota temp_max 2026-11-14: Dato del día de NASA GEOS-FP (modelo del GMAO, no una medición), celda de 0,25° × 0,3125° (~28 km, regional): completa los días que POWER todavía no publicó · GEOS-FP todavía no publicó este día
Nota radiacion 2026-11-14: Dato del día de NASA GEOS-FP (modelo del GMAO, no una medición), celda de 0,25° × 0,3125° (~28 km, regional): completa los días que POWER todavía no publicó · GEOS-FP todavía no publicó este día

Evapotranspiración · última hora publicada: 14/11/2026 02:30 UTC
evland, [3][1][1]
[0][0], 1.6782229E-5

[1][0], 1.7108368E-5

[2][0], 1.5343358E-5


time, [3]
739935.0208333334, 739935.0625, 739935.1041666666
lat, [1]
-33.75
lon, [1]
-65.3125

GEOS-FP (evapotranspiración del día) · 15 s
2026-11-10       1.1 mm/día  dudosa  
2026-11-11       3.7 mm/día  dudosa  
2026-11-12       4.3 mm/día  dudosa  
2026-11-13       3.9 mm/día  dudosa  
2026-11-14         — mm/día  descartada  GEOS-FP todavía no publicó este día
```
