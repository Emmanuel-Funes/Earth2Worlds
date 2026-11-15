# Sentinel-3 SLSTR - heladas como segundo respaldo de VIIRS

**Rama:** `satelite-sentinel3-heladas-respaldo` · **Conector:** `rotaterra/fuentes/sentinel3_heladas.py` · **Specs:** `docs/specs/051-heladas-respaldo-sentinel3.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector Sentinel-3 SLSTR LST nocturna: segundo respaldo de heladas, después de MODIS (spec 051).

Respaldo de VIIRS_LST (variable temp_sup_min_c). La fuente es el producto oficial de temperatura de la
**superficie** de la ESA, SL_2_LST (SLSTR de Sentinel-3A y 3B, 1 km), que solo publica el portal
Copernicus Data Space Ecosystem (la NASA no lo redistribuye). Pide una cuenta gratis de Copernicus:
COPERNICUS_USERNAME / COPERNICUS_PASSWORD como variables de entorno o secrets, nunca en el código.

Satélite independiente (spec 009): no importa a ningún otro satélite. Da la temperatura de la superficie
(suelo/canopeo), no la del aire: la helada agronómica se decide con esto más el criterio del productor.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_sentinel3_heladas.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-sentinel3-heladas.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_sentinel3_heladas.py <lat> <lon> <desde> <hasta>` en la compu.
- No necesita claves.

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_sentinel3_heladas.py "-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300" "2026-11-14" "2026-11-14"`

```
Temperatura de superficie nocturna del lote (Sentinel-3A/3B SLSTR SL_2_LST, 1 km, RESPALDO de VIIRS después de MODIS) del 2026-11-14 al 2026-11-14 · 27 s

Fecha        T sup °C  Calidad     Detalle
2026-11-14        8.8  buena       Respaldo · Sentinel-3 SLSTR LST nocturna (temperatura de superficie, no del aire) · lote menor a un píxel de 1 km: se usa el píxel del centro · SL_2_LST (Sentinel-3A, ESA Copernicus) · noche del 
2026-11-14        8.1  buena       Respaldo · Sentinel-3 SLSTR LST nocturna (temperatura de superficie, no del aire) · lote menor a un píxel de 1 km: se usa el píxel del centro · SL_2_LST (Sentinel-3B, ESA Copernicus) · noche del 
2026-11-14       —     descartada  Nubes o sin dato · Respaldo · Sentinel-3 SLSTR LST nocturna (temperatura de superficie, no del aire) · lote menor a un píxel de 1 km: se usa el píxel del centro · SL_2_LST (Sentinel-3B, ESA Coper
2026-11-14       13.7  buena       Respaldo · Sentinel-3 SLSTR LST nocturna (temperatura de superficie, no del aire) · lote menor a un píxel de 1 km: se usa el píxel del centro · SL_2_LST (Sentinel-3A, ESA Copernicus) · noche del 
2026-11-14       —     descartada  Nubes o sin dato · Respaldo · Sentinel-3 SLSTR LST nocturna (temperatura de superficie, no del aire) · lote menor a un píxel de 1 km: se usa el píxel del centro · SL_2_LST (Sentinel-3A, ESA Coper
2026-11-14       10.2  buena       Respaldo · Sentinel-3 SLSTR LST nocturna (temperatura de superficie, no del aire) · SL_2_LST (Sentinel-3B, ESA Copernicus) · noche del 2026-11-14, paso de las 22:42 hora solar (temprano: la madru
2026-11-14       —     descartada  Nubes o sin dato · Respaldo · Sentinel-3 SLSTR LST nocturna (temperatura de superficie, no del aire) · lote menor a un píxel de 1 km: se usa el píxel del centro · SL_2_LST (Sentinel-3B, ESA Coper
2026-11-14       —     descartada  Nubes o sin dato · Respaldo · Sentinel-3 SLSTR LST nocturna (temperatura de superficie, no del aire) · lote menor a un píxel de 1 km: se usa el píxel del centro · SL_2_LST (Sentinel-3A, ESA Coper
2026-11-14       10.4  buena       Respaldo · Sentinel-3 SLSTR LST nocturna (temperatura de superficie, no del aire) · lote menor a un píxel de 1 km: se usa el píxel del centro · SL_2_LST (Sentinel-3A, ESA Copernicus) · noche del 
2026-11-14       —     descartada  Nubes o sin dato · Respaldo · Sentinel-3 SLSTR LST nocturna (temperatura de superficie, no del aire) · lote menor a un píxel de 1 km: se usa el píxel del centro · SL_2_LST (Sentinel-3B, ESA Coper
2026-11-14       —     descartada  Nubes o sin dato · Respaldo · Sentinel-3 SLSTR LST nocturna (temperatura de superficie, no del aire) · lote menor a un píxel de 1 km: se usa el píxel del centro · SL_2_LST (Sentinel-3B, ESA Coper
2026-11-14        6.7  buena       Respaldo · Sentinel-3 SLSTR LST nocturna (temperatura de superficie, no del aire) · SL_2_LST (Sentinel-3A, ESA Copernicus) · noche del 2026-11-14, paso de las 22:24 hora solar (temprano: la madru
2026-11-14       11.5  buena       Respaldo · Sentinel-3 SLSTR LST nocturna (temperatura de superficie, no del aire) · lote menor a un píxel de 1 km: se usa el píxel del centro · SL_2_LST (Sentinel-3B, ESA Copernicus) · noche del 
2026-11-14       —     descartada  Nubes o sin dato · Respaldo · Sentinel-3 SLSTR LST nocturna (temperatura de superficie, no del aire) · lote menor a un píxel de 1 km: se usa el píxel del centro · SL_2_LST (Sentinel-3B, ESA Coper
2026-11-14       13.6  buena       Respaldo · Sentinel-3 SLSTR LST nocturna (temperatura de superficie, no del aire) · SL_2_LST (Sentinel-3B, ESA Copernicus) · noche del 2026-11-14, paso de las 22:08 hora solar (temprano: la madru
2026-11-14       18.8  buena       Respaldo · Sentinel-3 SLSTR LST nocturna (temperatura de superficie, no del aire) · lote menor a un píxel de 1 km: se usa el píxel del centro · SL_2_LST (Sentinel-3A, ESA Copernicus) · noche del 

16 noches · calidad {'buena': 9, 'descartada': 7} · 9 con dato · 0 con riesgo de helada (≤ 0 °C)
Noche más fría: 2026-11-14 con 6.7 °C de superficie
```
