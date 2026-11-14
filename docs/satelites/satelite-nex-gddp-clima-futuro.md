# NEX-GDDP-CMIP6 - clima futuro 2041-2060 de la zona del lote

**Rama:** `satelite-nex-gddp-clima-futuro` · **Conector:** `rotaterra/fuentes/nex_gddp.py` · **Specs:** `docs/specs/058-clima-futuro-nex-gddp.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector NEX-GDDP-CMIP6 (NASA): clima futuro de la zona del lote, 2041-2060 contra 1995-2014 (spec 058).

Proyecciones diarias de temperatura máxima, mínima y lluvia de los modelos climáticos CMIP6, corregidas y
bajadas de escala por la NASA (Ames, NEX) a una grilla de 0,25° (~25 km). Se leen por el servicio NCSS del THREDDS
público del NCCS (sin cuenta), un año por pedido, solo en la celda del lote.

Con eso se calculan indicadores para comparar rotaciones frente al clima que viene: días de calor (≥ 35 °C), máxima
de verano, días de helada del aire, lluvia del año y de la campaña, días de lluvia extrema (≥ 50 mm) y la racha
seca más larga de la campaña. Para cada uno: la línea de base de los modelos (1995-2014) y dos escenarios a
2041-2060, SSP2-4.5 (emisiones intermedias) y SSP5-8.5 (emisiones altas).

Es una PROYECCIÓN de modelos, no un pronóstico, y un dato REGIONAL de ~25 km: todo sale `dudosa`. Los datos
no cambian, así que cada celda se calcula una sola vez y queda en memoria. La primera vez tarda unos 15 minutos
(540 pedidos de unos 7 s, de a 4 a la vez).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_nex_gddp.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-nex-gddp.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_nex_gddp.py <lat> <lon> <desde> <hasta>` en la compu.
- No necesita claves.

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.
