# SMAP L4 - humedad del suelo diaria

**Rama:** `satelite-smap-humedad-suelo` · **Conector:** `rotaterra/fuentes/smap.py` · **Specs:** `docs/specs/003-conector-smap-humedad.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector SMAP L4: humedad del suelo diaria (spec 003).

Dos caminos al mismo producto de la NASA (SPL4SMGP):
- directo: CMR + OPeNDAP de la NASA, un píxel por archivo de 3 h. Rápido, sin fila de espera (principal).
- AppEEARS: la NASA arma el pedido y avisa cuando está; puede tardar de 5 a 40 minutos (respaldo, spec 005).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_smap.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-smap.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_smap.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (en GitHub Actions, corrida https://github.com/Emmanuel-Funes/Earth2Worlds/actions/runs/43600980590). Lote de prueba de San Luis.

Comando: `python probar_smap.py "-33.70" "-65.30" "2026-10-28" "2026-11-10" "directo"`

```
Leyendo SMAP directo de los archivos de la NASA...

Humedad del suelo SMAP L4 en (-33.7, -65.3) del 2026-10-28 al 2026-11-10 · camino directo · 20 s
Celda de 9 km: contexto regional, no dato del lote. Unidad m³/m³ (0,25 = 25 % en volumen)

Fecha          0-5 cm  0-100 cm  Calidad     Zona de raíces
2026-10-28      0.131     0.085  buena       ███████
2026-10-29      0.098     0.081  buena       ██████
2026-10-30      0.100     0.079  buena       ██████
2026-10-31      0.093     0.077  buena       ██████
2026-11-01      0.122     0.078  buena       ██████
2026-11-02      0.114     0.078  buena       ██████
2026-11-03      0.203     0.096  buena       ████████
2026-11-04      0.157     0.108  buena       █████████
2026-11-05      0.112     0.098  buena       ████████
2026-11-06      0.109     0.092  buena       ███████
2026-11-07      0.147     0.095  buena       ████████
2026-11-08      0.103     0.089  buena       ███████
2026-11-09      0.080     0.084  buena       ███████
2026-11-10      0.092     0.083  buena       ███████

14 días, 28 de 28 valores con calidad buena.
```
