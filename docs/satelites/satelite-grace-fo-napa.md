# GRACE-FO - napa y agua profunda de la región

**Rama:** `satelite-grace-fo-napa` · **Conector:** `rotaterra/fuentes/grace.py` · **Specs:** `docs/specs/026-napa-grace-fo.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector GRACE-FO: napa y agua profunda de la región (spec 026).

Principal: indicadores de sequía GRACE-DA de la NASA (GRACEDADM_CLSM025GL_7D, Goddard), un percentil
semanal de agua subterránea, de humedad en la zona de raíces y de humedad superficial, en una grilla
de 0,25°. Respaldo: anomalía mensual del agua total de los mascons de JPL (TELLUS_GRAC-GRFO_MASCON_CRI).
Las dos se leen por OPeNDAP de la NASA, solo en el píxel del centro del lote. Es un dato REGIONAL:
GRACE-FO mide la gravedad con una resolución real de unos 300 km.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_grace.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-grace.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_grace.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (en GitHub Actions, corrida https://github.com/Emmanuel-Funes/Earth2Worlds/actions/runs/43600983119). Lote de prueba de San Luis.

Comando: `python probar_grace.py "-33.70" "-65.30" "2026-11-14" "2026-11-14"`

```
1) Principal: GRACE-DA (GRACEDADM_CLSM025GL_7D) para (-33.7025, -65.2975) del 2026-11-14 al 2026-11-14
24 semanas publicadas en el período · última semana publicada: 2026-11-14 · 10 s
Esquema leído: {'C2283200566-GES_DISC': {'tamanos': {'lat': 600, 'lon': 1440, 'time': 1}, 'variables': {'lat': ['lat'], 'lon': ['lon'], 'time': ['time'], 'gws_inst': ['time', 'lat', 'lon'], 'rtzsm_inst': ['time', 'lat', 'lon'], 's

Semana         Napa  Raíces  Superf.  Categoría de la napa
2026-11-14      1.8    19.0     31.0  sequía excepcional
2026-11-14      0.2     7.3     16.9  sequía excepcional
2026-11-14      1.5    14.5     50.4  sequía excepcional
2026-11-14      1.5    12.2     15.5  sequía excepcional
2026-11-14      1.3    32.0     92.1  sequía excepcional
2026-11-14      0.9    21.0     24.6  sequía excepcional
2026-11-14      1.1     9.6     10.8  sequía excepcional
2026-11-14      1.5     5.3      3.2  sequía excepcional
2026-11-14      1.5     9.5      9.0  sequía excepcional
2026-11-14      2.2    10.9      1.2  sequía extrema
2026-11-14      2.6     6.3      0.2  sequía extrema
2026-11-14      2.2    30.7     45.6  sequía extrema
2026-11-14      1.5    12.8     23.0  sequía excepcional
2026-11-14      1.1     7.7     24.9  sequía excepcional
2026-11-14      1.1     4.6      8.7  sequía excepcional
2026-11-14      1.1     4.7      4.8  sequía excepcional
2026-11-14      1.3     1.1      1.1  sequía excepcional
2026-11-14      1.3     7.7     69.1  sequía excepcional
2026-11-14      1.3     8.9     13.4  sequía excepcional
2026-11-14      1.3     2.9      4.7  sequía excepcional
2026-11-14      1.3     0.7      4.8  sequía excepcional
2026-11-14      1.3     1.3      1.3  sequía excepcional
2026-11-14      1.3     1.3      0.2  sequía excepcional
2026-11-14      1.3     1.4     35.9  sequía excepcional
2026-11-14      —       —        —    
2026-11-14      —       —        —    

78 observaciones: 72 buenas, 0 dudosas, 6 descartadas.
Ejemplo de nota: Percentil de agua subterránea (napa): 1.8 = sequía excepcional · GRACE-DA de la NASA (GRACEDADM_CLSM025GL_7D), píxel de 0,25° · percentil frente a la misma semana de 1948 a 2014 (50 = normal) · dato REGIONAL, no d

2) Respaldo: mascons de JPL (TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4)
5 meses · 3 s
2026-11-14     -21.5 cm  buena
2026-11-14     -21.3 cm  buena
2026-11-14     -22.1 cm  buena
2026-11-14     -21.6 cm  buena
2026-11-14     -18.3 cm  buena
Ejemplo de nota: 21.51 cm de menos agua que el promedio · Respaldo de GRACE-DA · mascons de JPL (TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4), píxel de 0,5° · anomalía del agua total (napa + suelo + lagunas) frente al promedio 2004
```
