# FLDAS - humedad del suelo como respaldo final de SMAP

**Rama:** `satelite-fldas-humedad-respaldo` · **Conector:** `rotaterra/fuentes/fldas.py` · **Specs:** `docs/specs/036-humedad-respaldo-fldas.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Conector FLDAS: respaldo de humedad del suelo de la NASA (spec 036).

Respaldo final de SMAP (después de AppEEARS, SMAP L3 y GLDAS). La fuente es FLDAS Noah 0.1°
(`FLDAS_NOAH01_C_GL_M`), un modelo de superficie de la NASA (GES DISC), hermano de GLDAS pero con una
grilla más fina (~11 km) y paso **mensual**. Da la humedad del suelo por capas en m³/m³.

Es un dato REGIONAL de modelo y MENSUAL: el píxel cubre miles de hectáreas y el valor es el promedio del
mes. Por eso entra último (orden 4) y su calidad nunca pasa de `dudosa`. Se lee por OPeNDAP (`.dmr` para
los metadatos, `.dap.csv` para el recorte), solo el píxel del lote. No importa a ningún otro satélite
(spec 009): las ayudas de OPeNDAP están repetidas acá a propósito (vienen del patrón de GLDAS).

## Cómo se prueba

- Sin internet: `pytest -q tests/test_fldas.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow **probar-fldas.yml** en Actions (corre en el PR y se puede lanzar a mano), o
  `python probar_fldas.py <lat> <lon> <desde> <hasta>` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ningún otro satélite.

## Prueba real del 14/11/2026

Corrida el 14/11/2026 contra la fuente real, con datos de los últimos días (desde esta máquina de trabajo). Lote de prueba de San Luis.

Comando: `python probar_fldas.py "-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300" "2026-11-14" "2026-11-14"`

```
Humedad del suelo del lote (FLDAS Noah 0,1°, RESPALDO de SMAP) del 2026-11-14 al 2026-11-14 · centro (-33.7025, -65.2975) · 11 s

Mes         Variable                 m³/m³  Calidad     Detalle
2026-11-14  humedad_superficial      0.270  dudosa      Respaldo · humedad del suelo de 0 a 10 cm del modelo FLDAS Noah de la NASA (GES DISC) · promedio del mes · píxel de 0,1° (~11 km), dato REGIONAL y MENSUAL de modelo, no una m
2026-11-14  humedad_zona_raiz        0.226  dudosa      Respaldo · humedad de la zona de raíces (0 a 100 cm) del modelo FLDAS Noah de la NASA (GES DISC) · promedio del mes · píxel de 0,1° (~11 km), dato REGIONAL y MENSUAL de model
2026-11-14  humedad_superficial      0.253  dudosa      Respaldo · humedad del suelo de 0 a 10 cm del modelo FLDAS Noah de la NASA (GES DISC) · promedio del mes · píxel de 0,1° (~11 km), dato REGIONAL y MENSUAL de modelo, no una m
2026-11-14  humedad_zona_raiz        0.224  dudosa      Respaldo · humedad de la zona de raíces (0 a 100 cm) del modelo FLDAS Noah de la NASA (GES DISC) · promedio del mes · píxel de 0,1° (~11 km), dato REGIONAL y MENSUAL de model
2026-11-14  humedad_superficial      0.259  dudosa      Respaldo · humedad del suelo de 0 a 10 cm del modelo FLDAS Noah de la NASA (GES DISC) · promedio del mes · píxel de 0,1° (~11 km), dato REGIONAL y MENSUAL de modelo, no una m
2026-11-14  humedad_zona_raiz        0.223  dudosa      Respaldo · humedad de la zona de raíces (0 a 100 cm) del modelo FLDAS Noah de la NASA (GES DISC) · promedio del mes · píxel de 0,1° (~11 km), dato REGIONAL y MENSUAL de model
2026-11-14  humedad_superficial      0.254  dudosa      Respaldo · humedad del suelo de 0 a 10 cm del modelo FLDAS Noah de la NASA (GES DISC) · promedio del mes · píxel de 0,1° (~11 km), dato REGIONAL y MENSUAL de modelo, no una m
2026-11-14  humedad_zona_raiz        0.221  dudosa      Respaldo · humedad de la zona de raíces (0 a 100 cm) del modelo FLDAS Noah de la NASA (GES DISC) · promedio del mes · píxel de 0,1° (~11 km), dato REGIONAL y MENSUAL de model

8 observaciones · calidad {'dudosa': 8} · 8 con dato
Fuente FLDAS, resolución 11000 m. GLDAS dio ~0,267 y SMAP anda en ese orden: FLDAS tiene que quedar parecido.
```
