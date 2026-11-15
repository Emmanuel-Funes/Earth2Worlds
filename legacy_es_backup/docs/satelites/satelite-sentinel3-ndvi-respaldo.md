# Sentinel-3 - NDVI diario de 300 m como respaldo de HLS

**Rama:** `satelite-sentinel3-ndvi-respaldo` · **Conector:** `rotaterra/fuentes/sentinel3.py` · **Specs:** `docs/specs/050-ndvi-respaldo-sentinel3.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector Sentinel-3 (ESA): NDVI diario de 300 m del lote, respaldo de HLS entre Sentinel-2 y VIIRS (spec 050).

Producto SYN L2 (Synergy OLCI + SLSTR: reflectancia de superficie sobre tierra) de Sentinel-3A y 3B, que la
NASA redistribuye en LAADS DAAC con la misma cuenta de Earthdata. Cada pasada es un .zip de 350-900 MB con
NetCDF guardados sin comprimir adentro: se leen por HTTP solo los pedazos que tocan al lote (~5 MB por pasada).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_sentinel3.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-sentinel3.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_sentinel3.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_sentinel3.py "-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300" "2026-11-14" "2026-11-14"`

```
NDVI del lote (Sentinel-3A/3B SYN L2, 300 m, una pasada por día) del 2026-11-14 al 2026-11-14 · 198 s

Fecha          NDVI  Calidad     Detalle
2026-11-14     0.38  buena       Respaldo de HLS · Sentinel-3A SYN L2 (OLCI+SLSTR, ESA, vía NASA LAADS) · 6 píxeles de 300 m · media 0.39 · p10 0.25 · p90 0.55 · válidos 100%
2026-11-14     0.31  buena       Respaldo de HLS · Sentinel-3A SYN L2 (OLCI+SLSTR, ESA, vía NASA LAADS) · 4 píxeles de 300 m · media 0.31 · p10 0.26 · p90 0.37 · válidos 100%
2026-11-14     0.37  buena       Respaldo de HLS · Sentinel-3B SYN L2 (OLCI+SLSTR, ESA, vía NASA LAADS) · 4 píxeles de 300 m · media 0.38 · p10 0.24 · p90 0.52 · válidos 100%
2026-11-14     0.42  buena       Respaldo de HLS · Sentinel-3A SYN L2 (OLCI+SLSTR, ESA, vía NASA LAADS) · 2 píxeles de 300 m · media 0.42 · p10 0.29 · p90 0.54 · válidos 100%
2026-11-14     0.52  buena       Respaldo de HLS · Sentinel-3A SYN L2 (OLCI+SLSTR, ESA, vía NASA LAADS) · 5 píxeles de 300 m · media 0.44 · p10 0.27 · p90 0.56 · válidos 100%
2026-11-14      —    descartada  Nubes, nieve o sin dato · Respaldo de HLS · Sentinel-3A SYN L2 (OLCI+SLSTR, ESA, vía NASA LAADS) · 2 píxeles de 300 m · válidos 0%
2026-11-14      —    descartada  Nubes, nieve o sin dato · Respaldo de HLS · Sentinel-3B SYN L2 (OLCI+SLSTR, ESA, vía NASA LAADS) · 2 píxeles de 300 m · válidos 0%
2026-11-14     0.23  buena       Respaldo de HLS · Sentinel-3A SYN L2 (OLCI+SLSTR, ESA, vía NASA LAADS) · 4 píxeles de 300 m · media 0.29 · p10 0.23 · p90 0.40 · válidos 100%
2026-11-14     0.42  buena       Respaldo de HLS · Sentinel-3A SYN L2 (OLCI+SLSTR, ESA, vía NASA LAADS) · 4 píxeles de 300 m · media 0.42 · p10 0.27 · p90 0.57 · válidos 100%
2026-11-14      —    descartada  Nubes, nieve o sin dato · Respaldo de HLS · Sentinel-3B SYN L2 (OLCI+SLSTR, ESA, vía NASA LAADS) · 3 píxeles de 300 m · válidos 0%
2026-11-14     0.46  buena       Respaldo de HLS · Sentinel-3A SYN L2 (OLCI+SLSTR, ESA, vía NASA LAADS) · 3 píxeles de 300 m · media 0.44 · p10 0.30 · p90 0.58 · válidos 100%
2026-11-14     0.31  buena       Respaldo de HLS · Sentinel-3A SYN L2 (OLCI+SLSTR, ESA, vía NASA LAADS) · 4 píxeles de 300 m · media 0.39 · p10 0.30 · p90 0.53 · válidos 100%
2026-11-14      —    descartada  Nubes, nieve o sin dato · Respaldo de HLS · Sentinel-3B SYN L2 (OLCI+SLSTR, ESA, vía NASA LAADS) · 2 píxeles de 300 m · válidos 0%
2026-11-14     0.46  buena       Respaldo de HLS · Sentinel-3A SYN L2 (OLCI+SLSTR, ESA, vía NASA LAADS) · 4 píxeles de 300 m · media 0.47 · p10 0.28 · p90 0.66 · válidos 100%

14 días con pasada · calidad {'buena': 10, 'descartada': 4} · 10 con dato
NDVI de 0.23 a 0.52 · fuente SENTINEL3, resolución 300 m
```
