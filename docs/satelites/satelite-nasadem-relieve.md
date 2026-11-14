# NASADEM - altura, pendiente y ambientes del lote

**Rama:** `satelite-nasadem-relieve` · **Conector:** `rotaterra/fuentes/nasadem.py` · **Specs:** `docs/specs/008-altimetria-nasadem.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector NASADEM: altura, pendiente y ambientes (bajo, media loma, loma) del lote (spec 008).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_nasadem.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-nasadem.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_nasadem.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_nasadem.py "-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300"`

```
Altimetría del lote (NASADEM, 30 m, febrero de 2000) · 4 s

Variable                      Valor  Unidad Calidad    
altura_media_m                488.4  m      buena      
altura_min_m                    485  m      buena      
altura_max_m                    492  m      buena      
pendiente_media_pct            2.76  %      buena      
superficie_bajo_ha             8.28  ha     buena      
superficie_media_loma_ha      10.86  ha     buena      
superficie_loma_ha             6.58  ha     buena      

Detalle: bajo / loma = más de 1 m por debajo / por encima de la media del lote (umbral supuesto, a calibrar) · proporción de píxeles × 25.7 ha del lote · NASADEM (SRTM, febrero de 2000) · 289 de 289 píxeles de 30 m con dato
```
