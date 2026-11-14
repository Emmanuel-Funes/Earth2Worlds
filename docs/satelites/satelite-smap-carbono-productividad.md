# SMAP L4 Carbono - productividad de la vegetación

**Rama:** `satelite-smap-carbono-productividad` · **Conector:** `rotaterra/fuentes/smap_carbono.py` · **Specs:** `docs/specs/055-productividad-smap-carbono.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector SMAP L4 Carbono: productividad diaria de la vegetación alrededor del lote (spec 055).

SMAP L4C (NASA) combina la humedad del suelo de SMAP con la luz absorbida por las plantas y calcula, todos los
días y en celdas de 9 km, cuánto carbono fija la vegetación (GPP, productividad primaria bruta) y el balance
neto del ecosistema (NEE). Reemplaza la productividad de MODIS (MOD17), que deja de salir con el fin de MODIS.

Es un dato **regional**: una celda de 9 km tiene ~8.100 ha, y el lote de 25 ha cae dentro. Sirve para comparar
campañas y ver cómo viene la zona; no es el rinde del lote.

Cada archivo pesa ~140 MB. No se baja: se pide por OPeNDAP solo el valor de la celda del lote (un pedido por día).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_smap_carbono.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-smap-carbono.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_smap_carbono.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_smap_carbono.py "-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300" "2026-11-14" "2026-11-14"`

```
Productividad SMAP L4 Carbono (celda de 9 km del lote) del 2026-11-14 al 2026-11-14 · 9 s

Fecha           GPP    NEE  Calidad     Detalle
2026-11-14     1.33   1.39  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 1.35 · latifoliadas 1.08 · cel
2026-11-14     3.14   0.48  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 3.19 · latifoliadas 2.54 · cel
2026-11-14     2.27   0.87  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 2.30 · latifoliadas 1.98 · cel
2026-11-14     3.21   0.67  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 3.25 · latifoliadas 2.85 · cel
2026-11-14     2.27   0.89  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 2.29 · latifoliadas 2.10 · cel
2026-11-14     3.25   0.62  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 3.30 · latifoliadas 2.61 · cel
2026-11-14     1.59   1.36  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 1.61 · latifoliadas 1.32 · cel
2026-11-14     1.38   1.56  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 1.41 · latifoliadas 1.04 · cel
2026-11-14     1.04   1.09  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 1.05 · latifoliadas 0.88 · cel
2026-11-14     0.78   1.13  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 0.79 · latifoliadas 0.66 · cel
2026-11-14     2.30   0.50  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 2.32 · latifoliadas 2.04 · cel
2026-11-14     1.37   1.03  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 1.38 · latifoliadas 1.22 · cel
2026-11-14     1.25   1.12  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 1.27 · latifoliadas 1.09 · cel
2026-11-14     1.05   1.11  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 1.06 · latifoliadas 0.88 · cel
2026-11-14     1.41   0.94  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 1.43 · latifoliadas 1.19 · cel
2026-11-14     2.04   0.72  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 2.05 · latifoliadas 1.88 · cel
2026-11-14     2.30   0.67  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 2.30 · latifoliadas 2.21 · cel
2026-11-14     2.93   0.34  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 2.93 · latifoliadas 2.96 · cel
2026-11-14     2.41   0.51  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 2.40 · latifoliadas 2.56 · cel
2026-11-14     1.75   0.79  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 1.74 · latifoliadas 1.78 · cel
2026-11-14     1.73   0.83  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 1.72 · latifoliadas 1.77 · cel
2026-11-14     2.19   1.06  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 2.18 · latifoliadas 2.36 · cel
2026-11-14     1.42   1.50  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 1.43 · latifoliadas 1.22 · cel
2026-11-14     1.55   1.21  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 1.56 · latifoliadas 1.37 · cel
2026-11-14     1.54   1.05  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 1.56 · latifoliadas 1.22 · cel
2026-11-14     3.27   0.16  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 3.30 · latifoliadas 2.84 · cel
2026-11-14     1.86   0.85  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 1.87 · latifoliadas 1.72 · cel
2026-11-14     1.61   1.19  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 1.63 · latifoliadas 1.28 · cel
2026-11-14     3.37   0.54  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 3.38 · latifoliadas 3.24 · cel
2026-11-14     3.38   0.66  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 3.36 · latifoliadas 3.60 · cel
2026-11-14     3.25   0.81  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 3.24 · latifoliadas 3.42 · cel
2026-11-14     2.77   0.87  buena       SMAP L4 Carbono · productividad primaria bruta (carbono que fija la vegetación) · dato regional de la celda de 9 km, no del lote · GPP del modelo para cereales 2.74 · latifoliadas 3.09 · cel

32 días · 32 con dato · GPP media 2.09 (mín 0.78, máx 3.38) g C/m²/día · suma 67 g C/m²
```
