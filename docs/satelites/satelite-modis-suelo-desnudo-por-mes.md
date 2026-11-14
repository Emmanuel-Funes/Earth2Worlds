# MODIS - meses del año con el lote sin cobertura verde

**Rama:** `satelite-modis-suelo-desnudo-por-mes` · **Conector:** `rotaterra/fuentes/suelo_desnudo.py` · **Specs:** `docs/specs/060-suelo-desnudo-por-mes.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector suelo desnudo: en qué meses del año el lote queda sin cobertura verde, con 5 años de MODIS (spec 060).

El desafío pide mostrar cuándo los lotes quedan típicamente desnudos: es cuando el suelo se vuela (erosión eólica en
los suelos arenosos de San Luis), pierde agua por evaporación y no suma carbono. Es el hueco donde entra un cultivo de
servicio o un verdeo.

Se usa el NDVI de 250 m de MODIS Terra (MOD13Q1, compuestos de 16 días) de los últimos 4 años (48 meses): es el NDVI
de la NASA con historia larga que se lee en pocos minutos. Cada compuesto se pide por OPeNDAP, solo la ventana del lote.
El OPeNDAP de la NASA sirve MOD13Q1 desde mediados de 2022 (los compuestos anteriores dan 404), por eso 4 años y no más.
Un mes cuenta como "desnudo" en un año si la mediana del NDVI del lote ese mes es menor a 0,25, y con "cobertura baja"
si es menor a 0,30.

Satélite independiente (spec 009): repite a propósito la lectura de MODIS del conector de NDVI y no lo importa.

## Cómo se prueba

- Sin internet: `pytest -q tests/test_suelo_desnudo.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-suelo-desnudo.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_suelo_desnudo.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_suelo_desnudo.py "-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300"`

```
Suelo desnudo del lote con MODIS, últimos 48 meses · 82 s

· meses_suelo_desnudo: 0 meses · buena · Meses en que el lote suele quedar desnudo (la mitad de los años o más): ninguno · MODIS Terra MOD13Q1 (NASA), NDVI de 250 m, 11/2022 a 10/2026 · 91 compuestos de 16 días con el lote visible
· meses_cobertura_baja: 2 meses · buena · Meses en que el lote suele quedar con cobertura baja (la mitad de los años o más): agosto, diciembre · MODIS Terra MOD13Q1 (NASA), NDVI de 250 m, 11/2022 a 10/2026 · 91 compuestos de 16 dí
· suelo_desnudo_mes_01_pct: 0 % de los años · buena · Enero: desnudo en 0 % de los años y con cobertura baja en 0 % (4 años); NDVI mediano 0.56 (por año: 2023 0.55, 2024 0.57, 2025 0.75, 2026 0.55) · MODIS Terra MOD13Q1 (NASA), ND
· suelo_desnudo_mes_02_pct: 0 % de los años · buena · Febrero: desnudo en 0 % de los años y con cobertura baja en 0 % (4 años); NDVI mediano 0.85 (por año: 2023 0.81, 2024 0.86, 2025 0.85, 2026 0.84) · MODIS Terra MOD13Q1 (NASA), 
· suelo_desnudo_mes_03_pct: 0 % de los años · buena · Marzo: desnudo en 0 % de los años y con cobertura baja en 0 % (4 años); NDVI mediano 0.81 (por año: 2023 0.79, 2024 0.81, 2025 0.82, 2026 0.80) · MODIS Terra MOD13Q1 (NASA), ND
· suelo_desnudo_mes_04_pct: 0 % de los años · buena · Abril: desnudo en 0 % de los años y con cobertura baja en 0 % (4 años); NDVI mediano 0.64 (por año: 2023 0.71, 2024 0.53, 2025 0.67, 2026 0.62) · MODIS Terra MOD13Q1 (NASA), ND
· suelo_desnudo_mes_05_pct: 0 % de los años · buena · Mayo: desnudo en 0 % de los años y con cobertura baja en 0 % (4 años); NDVI mediano 0.42 (por año: 2023 0.49, 2024 0.39, 2025 0.44, 2026 0.39) · MODIS Terra MOD13Q1 (NASA), NDV
· suelo_desnudo_mes_06_pct: 0 % de los años · buena · Junio: desnudo en 0 % de los años y con cobertura baja en 25 % (4 años); NDVI mediano 0.36 (por año: 2023 0.40, 2024 0.32, 2025 0.28, 2026 0.39) · MODIS Terra MOD13Q1 (NASA), N
· suelo_desnudo_mes_07_pct: 0 % de los años · buena · Julio: desnudo en 0 % de los años y con cobertura baja en 0 % (4 años); NDVI mediano 0.31 (por año: 2023 0.31, 2024 0.30, 2025 0.30, 2026 0.35) · MODIS Terra MOD13Q1 (NASA), ND
· suelo_desnudo_mes_08_pct: 0 % de los años · buena · Agosto: desnudo en 0 % de los años y con cobertura baja en 50 % (4 años); NDVI mediano 0.29 (por año: 2023 0.27, 2024 0.31, 2025 0.27, 2026 0.31) · MODIS Terra MOD13Q1 (NASA), 
· suelo_desnudo_mes_09_pct: 0 % de los años · buena · Septiembre: desnudo en 0 % de los años y con cobertura baja en 25 % (4 años); NDVI mediano 0.31 (por año: 2023 0.29, 2024 0.31, 2025 0.32, 2026 0.32) · MODIS Terra MOD13Q1 (NAS
· suelo_desnudo_mes_10_pct: 0 % de los años · buena · Octubre: desnudo en 0 % de los años y con cobertura baja en 25 % (4 años); NDVI mediano 0.36 (por año: 2023 0.28, 2024 0.35, 2025 0.38, 2026 0.37) · MODIS Terra MOD13Q1 (NASA),
· suelo_desnudo_mes_11_pct: 0 % de los años · buena · Noviembre: desnudo en 0 % de los años y con cobertura baja en 25 % (4 años); NDVI mediano 0.33 (por año: 2022 0.38, 2023 0.35, 2024 0.30, 2025 0.31) · MODIS Terra MOD13Q1 (NASA
· suelo_desnudo_mes_12_pct: 0 % de los años · buena · Diciembre: desnudo en 0 % de los años y con cobertura baja en 50 % (4 años); NDVI mediano 0.34 (por año: 2022 0.30, 2023 0.38, 2024 0.53, 2025 0.27) · MODIS Terra MOD13Q1 (NASA
```
