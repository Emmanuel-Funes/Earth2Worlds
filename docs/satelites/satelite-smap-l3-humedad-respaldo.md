# SMAP L3 - humedad de superficie como respaldo de SMAP L4

**Rama:** `satelite-smap-l3-humedad-respaldo` · **Conector:** `rotaterra/fuentes/smap_l3.py` · **Specs:** `docs/specs/015-humedad-smap-l3-respaldo.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector SMAP L3: humedad de superficie observada por satélite, segundo respaldo de SMAP L4 (spec 015).

El L4 (SPL4SMGP) es un modelo que asimila SMAP; el L3 mejorado (SPL3SMP_E) es la observación del
radiómetro, sin modelo: una pasada AM y una PM por día cuando la órbita cruza la celda de 9 km.
Se lee solo la celda del lote por OPeNDAP de la NASA (CMR + Earthdata), como el camino directo del L4.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_smap_l3.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-smap-l3.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_smap_l3.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_smap_l3.py "-33.70" "-65.30" "2026-11-14" "2026-11-14"`

```
Leyendo SMAP L3 (SPL3SMP_E) de la NASA para (-33.7, -65.3), celda EASE-Grid 2.0 de 9 km fila 1262, columna 1228...

Humedad de superficie SMAP L3 del 2026-11-14 al 2026-11-14 · 14 archivos diarios · 11 s
Capas leídas: {'C2938664763-NSIDC_CPRD': {'AM': {'lon': '/Soil_Moisture_Retrieval_Data_AM/longitude', 'lat': '/Soil_Moisture_Retrieval_Data_AM/latitude', 'bandera': '/Soil_Moisture_Retrieval_Data_AM/retrieval_qual_flag', 'humedad'
Unidad m³/m³ (0,10 = 10 % en volumen). Bandera = retrieval_qual_flag (bit 0 en 0 = calidad recomendada)

Centro de la celda según el archivo: (-33.6715, -65.306) · a 3.2 km del punto · OK: el punto está en la celda

Fecha            AM band.      PM band.     Día  Calidad     L4 0-5 cm
2026-11-14      —       7   0.172     8   0.172  buena                
2026-11-14    0.136     8     —       7   0.136  buena                
2026-11-14      —       7   0.143     8   0.143  buena                
2026-11-14      —       7     —       7     —    descartada           
2026-11-14    0.210     8     —       7   0.209  buena                
2026-11-14      —       7   0.174     8   0.174  buena                
2026-11-14    0.258     9     —       7   0.258  dudosa               
2026-11-14      —       7     —       7     —    descartada           
2026-11-14      —       7   0.154     8   0.154  buena                
2026-11-14    0.150     8     —       7   0.150  buena                
2026-11-14      —       7   0.139     8   0.139  buena                
2026-11-14      —       7   0.119     8   0.119  buena                
2026-11-14    0.130     8     —       7   0.130  buena                
2026-11-14      —       7   0.105     8   0.105  buena                

14 días: 11 buenos, 1 dudosos, 2 descartados (sin pasada o sin archivo).
Ejemplo de nota: Una pasada · Respaldo de SMAP L4 · observación satelital SMAP L3 (SPL3SMP_E), celda de 9 km: contexto regional, no dato del lote · solo superficie 0-5 cm (el L3 no trae zona de raíces) · AM sin pasada · PM 0.172 (
```
