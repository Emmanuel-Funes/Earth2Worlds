# Balance hídrico propio con NASA POWER (respaldo de SEPA)

**Rama:** `fuente-balance-hidrico-propio` · **Conector:** `rotaterra/fuentes/balance_hidrico.py` · **Specs:** `docs/specs/024-balance-hidrico-propio-power.md`

## Origen

Código escrito y subido durante el evento (14/11/2026), a partir del diseño previo del equipo (SDD).

## Qué hace

Balance hídrico propio con NASA POWER e IMERG: respaldo del balance de SEPA (spec 024).

Un balde de 2 m por lote: entra la lluvia, sale la ET del cultivo (Kc × ET0 FAO-56, reducida por Ks cuando el
suelo se seca) y lo que sobra de la capacidad es excedente. Se resume por década, como SEPA.
La lluvia de cada día es la menor entre POWER e IMERG: POWER marca lluvias de invierno que IMERG y SEPA no ven.
Calibrado contra 87 décadas de SEPA en San Luis (spec 024): diferencia media de 16 mm.


## Cómo se prueba

- Sin internet: `pytest -q tests/test_balance_hidrico.py` (respuestas de la fuente simuladas).
- Contra la fuente real: workflow `probar-balance-hidrico.yml` en Actions (corre en el PR y se puede lanzar a mano), o `python probar_balance_hidrico.py` en la compu.
- Necesita los secretos `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD` (solo en GitHub → Settings → Secrets → Actions; nunca en el código).

## Depende de

Solo del núcleo (rama `nucleo-api-y-contrato-comun`): no importa ninguna otra fuente.
