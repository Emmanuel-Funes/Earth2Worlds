# Earth2Worlds · Rotaterra — datos satelitales para planificar rotaciones

Proyecto del equipo **Earth2Worlds** para el NASA Space Apps Challenge 2026 (14 y 15 de noviembre de 2026).
Rotaterra trae datos de satélites de la **NASA** y de agencias socias (ESA, NOAA, ISRO) para cada lote,
los pasa a un **contrato JSON común** y los entrega a la app por una API.

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD, en `docs/specs/`).

## Cómo está organizado

`main` (después de unir esta rama) tiene solo el **núcleo**: contrato común, geometría del lote, base opcional,
consulta con respaldos y la API con clave. **Cada satélite vive en su propia rama** y se une a `main` cuando se
aprueba su PR. Ningún satélite depende de otro (lo verifica `tests/test_nucleo.py`).

| Rama | Qué aporta | Archivo |
|---|---|---|
| `nucleo-api-y-contrato-comun` | Núcleo: contrato, API con clave, consulta con respaldos | `rotaterra/` |
| `satelite-nasa-power-clima-diario` | NASA POWER - clima diario del lote (temperatura, lluvia, radiación) | `rotaterra/fuentes/power.py` |
| `satelite-nasa-power-lluvia-respaldo` | NASA POWER - lluvia diaria como respaldo de IMERG | `rotaterra/fuentes/power_lluvia.py` |
| `satelite-merra2-clima-respaldo` | MERRA-2 - temperatura y radiación como respaldo de POWER | `rotaterra/fuentes/merra2.py` |
| `satelite-geos-fp-clima-del-dia` | GEOS-FP - clima y ET del día (respaldo del día de POWER) | `rotaterra/fuentes/geos_fp.py` |
| `satelite-nex-gddp-clima-futuro` | NEX-GDDP-CMIP6 - clima futuro 2041-2060 de la zona del lote | `rotaterra/fuentes/nex_gddp.py` |
| `satelite-gpm-imerg-lluvia` | GPM IMERG - lluvia diaria del lote | `rotaterra/fuentes/imerg.py` |
| `satelite-gpm-imerg-early-lluvia-del-dia` | IMERG Early - lluvia del día (respaldo del día de IMERG) | `rotaterra/fuentes/imerg_early.py` |
| `satelite-persiann-cdr-lluvia-respaldo` | PERSIANN-CDR - lluvia como respaldo de IMERG | `rotaterra/fuentes/persiann.py` |
| `satelite-hls-ndvi-ndmi-30m` | HLS (Landsat + Sentinel-2) - NDVI y NDMI del lote a 30 m | `rotaterra/fuentes/hls.py` |
| `satelite-sentinel2-ndvi-ndmi-respaldo` | Sentinel-2 - NDVI 10 m y NDMI 20 m como respaldo de HLS | `rotaterra/fuentes/sentinel2.py` |
| `satelite-sentinel3-ndvi-respaldo` | Sentinel-3 - NDVI diario de 300 m como respaldo de HLS | `rotaterra/fuentes/sentinel3.py` |
| `satelite-viirs-ndvi-respaldo` | VIIRS - NDVI de 500 m como respaldo de HLS | `rotaterra/fuentes/viirs.py` |
| `satelite-modis-ndvi-respaldo` | MODIS - NDVI de 250 m como respaldo de HLS | `rotaterra/fuentes/modis.py` |
| `satelite-modis-nrt-ndvi-del-dia` | MODIS NRT - NDVI del día (respaldo del día de HLS) | `rotaterra/fuentes/modis_nrt.py` |
| `satelite-modis-suelo-desnudo-por-mes` | MODIS - meses del año con el lote sin cobertura verde | `rotaterra/fuentes/suelo_desnudo.py` |
| `satelite-smap-humedad-suelo` | SMAP L4 - humedad del suelo diaria | `rotaterra/fuentes/smap.py` |
| `satelite-smap-l3-humedad-respaldo` | SMAP L3 - humedad de superficie como respaldo de SMAP L4 | `rotaterra/fuentes/smap_l3.py` |
| `satelite-smap-nrt-humedad-del-dia` | SMAP NRT - humedad del día (respaldo del día de SMAP) | `rotaterra/fuentes/smap_nrt.py` |
| `satelite-gldas-humedad-y-et-respaldo` | GLDAS - humedad del suelo y ET como respaldo | `rotaterra/fuentes/gldas.py` |
| `satelite-fldas-humedad-respaldo` | FLDAS - humedad del suelo como respaldo final de SMAP | `rotaterra/fuentes/fldas.py` |
| `satelite-modis-evapotranspiracion` | MODIS MOD16 - evapotranspiración real y potencial | `rotaterra/fuentes/et.py` |
| `satelite-ecostress-evapotranspiracion-estres` | ECOSTRESS - evapotranspiración y estrés hídrico a 70 m | `rotaterra/fuentes/ecostress.py` |
| `satelite-viirs-heladas` | VIIRS LST nocturna - aviso de heladas del lote | `rotaterra/fuentes/viirs_heladas.py` |
| `satelite-modis-heladas-respaldo` | MODIS LST nocturna - heladas como respaldo de VIIRS | `rotaterra/fuentes/modis_heladas.py` |
| `satelite-sentinel3-heladas-respaldo` | Sentinel-3 SLSTR - heladas como segundo respaldo de VIIRS | `rotaterra/fuentes/sentinel3_heladas.py` |
| `satelite-goes-heladas-del-dia` | GOES-19 - temperatura mínima de la madrugada (heladas del día) | `rotaterra/fuentes/goes_heladas.py` |
| `satelite-ecostress-heladas-por-zona` | ECOSTRESS LST - heladas por zona del lote a 70 m | `rotaterra/fuentes/ecostress_heladas.py` |
| `satelite-nasadem-relieve` | NASADEM - altura, pendiente y ambientes del lote | `rotaterra/fuentes/nasadem.py` |
| `satelite-copernicus-dem-relieve-respaldo` | Copernicus DEM - relieve como respaldo de NASADEM | `rotaterra/fuentes/copdem.py` |
| `satelite-aster-relieve-respaldo` | ASTER GDEM - relieve como segundo respaldo de NASADEM | `rotaterra/fuentes/aster.py` |
| `satelite-grace-fo-napa` | GRACE-FO - napa y agua profunda de la región | `rotaterra/fuentes/grace.py` |
| `satelite-gedi-vegetacion` | GEDI - cobertura y estructura de la vegetación (láser) | `rotaterra/fuentes/gedi.py` |
| `satelite-nisar-radar` | NISAR - radar banda L a 20 m, con o sin nubes | `rotaterra/fuentes/nisar.py` |
| `satelite-smap-carbono-productividad` | SMAP L4 Carbono - productividad de la vegetación | `rotaterra/fuentes/smap_carbono.py` |

Orden sugerido para unir: primero el núcleo, después cualquier satélite (son independientes).

## Probar

```bash
python3.11 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q            # sin internet: las respuestas de la NASA están simuladas
```

Las pruebas reales contra la NASA usan los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD`, que viven
**solo** en GitHub (Settings → Secrets and variables → Actions). Ninguna clave va en el código.

Reglas de trabajo: [`AGENTS.md`](AGENTS.md).
