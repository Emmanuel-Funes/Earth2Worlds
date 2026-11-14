# Spec 009 · Satélites independientes, en ramas separadas

**Estado:** aprobada por Hernán el 3 de octubre de 2026 (tarjeta: "Ramas separadas") · **Pedido por:** Hernán, con el documento "SDD - Aislamiento e Independencia de Satélites"

## Objetivo

Que cada satélite y cada respaldo funcionen **por su cuenta**, sin depender de otro, y que **no estén unidos a `main`** hasta que Hernán dé la orden. `main` queda solo con el **núcleo**. Cada satélite espera en su propia rama, completo y probado, listo para unirse con un PR.

## Cómo se traduce el documento de Hernán a Rotaterra

El documento habla de firmware, sockets y MQTT. En Rotaterra, un "satélite" es un **conector** que lee datos de la NASA (`rotaterra/fuentes/`), y "Main" es la **rama `main`**, desde donde corre la actualización nocturna.

| Documento | En Rotaterra |
|---|---|
| Aislamiento total entre satélites | Ningún satélite importa código de otro. Solo usa el núcleo compartido: el contrato, `geo.py`, `earthdata.py` y `registro.py`. Un test lo verifica en cada PR |
| Fallas contenidas | Si un satélite falla, o directamente no carga por un error de código, los demás se actualizan igual |
| Desconexión temporal de Main | Los satélites salen de `main`. Sin satélites unidos, la actualización nocturna no pide nada y lo dice |
| `READY_TO_CONNECT` | Cada satélite está en su rama con su código, sus tests, su prueba real de un clic y su spec. Las pruebas pasan contra el núcleo solo |
| `ON_DEMAND_CONNECT` | La orden es aprobar el PR de esa rama (**Merge**). El satélite se suma solo: no hay que tocar el núcleo |
| Backups en *warm standby* | Cada respaldo tiene **su propia rama**. Unido sin su principal, queda en espera y no se consulta. Con su principal, entra solo si el principal falla |

## Núcleo (lo único que queda en `main`)

| Archivo | Qué hace |
|---|---|
| `rotaterra/contrato.py` | Contrato JSON común |
| `rotaterra/base.py` | Base de datos, lotes, combinación de fuentes |
| `rotaterra/geo.py` | Esquinas del lote y validación del polígono |
| `rotaterra/actualizar.py` | Actualización nocturna con los satélites que encuentre |
| `rotaterra/api.py` | API de la app (lotes, observaciones, estado) más las rutas de prueba de cada satélite unido |
| `rotaterra/fuentes/registro.py` | Cómo se anuncia un satélite y cómo el núcleo lo encuentra |
| `rotaterra/fuentes/earthdata.py` | Acceso común a NASA Earthdata (token, CMR, OPeNDAP) |

Las specs 001 a 008 quedan en `main` como documentación: describen qué hace cada satélite aunque todavía no esté unido.

## Cómo se anuncia un satélite

Cada archivo de `rotaterra/fuentes/` que no es del núcleo es un satélite y declara:

```python
SATELITES = [Satelite("POWER", pedir)]                                   # principal
SATELITES = [Satelite("POWER:MERRA2", pedir, respaldo_de="POWER")]       # respaldo
SATELITES = [Satelite("HLS:VIIRS", pedir, respaldo_de="HLS", orden=1)]  # primer respaldo de varios (spec 005)
SATELITES = [Satelite("NASADEM", pedir, estatico=True)]                  # dato fijo
router = APIRouter()  # opcional: sus endpoints de prueba (/clima, /ndvi, ...)
```

El núcleo los encuentra solo (`registro.descubrir()`). Unir un satélite no modifica ningún archivo del núcleo ni de otro satélite, así que los PR no chocan entre sí y se pueden aprobar en cualquier orden.

## Ramas

| Rama | Satélite | Es respaldo de |
|---|---|---|
| `NUCLEO-contrato_base_y_api` | Núcleo (este PR va primero) | — |
| `POWER-clima` | NASA POWER | — |
| `MERRA2-clima_respaldo` | MERRA-2 | POWER |
| `HLS-NDVI_NDMI` | HLS | — |
| `MODIS-NDVI_respaldo` | MODIS | HLS |
| `SMAP-humedad_suelo` | SMAP (camino directo, con AppEEARS adentro como respaldo del mismo producto) | — |
| `IMERG-lluvia` | GPM IMERG | — |
| `NASADEM-altimetria` | NASADEM | — |

SMAP directo y SMAP vía AppEEARS son **el mismo producto** por dos caminos (spec 005), así que viajan juntos.

## Reglas

1. Un satélite no importa nada de otro satélite. El núcleo no nombra a ningún satélite.
2. Un satélite que no carga queda en `error` con el motivo, y los demás siguen.
3. Un respaldo sin su principal unido no se consulta.
4. "Pendiente" es un estado del núcleo (`registro.Pendiente`), no algo propio de SMAP.

## Criterios de aceptación

- [x] `main` con solo el núcleo: los tests pasan y la actualización dice que no hay satélites unidos. *(PR #14 en GitHub: `tests` y `tests-postgres` en verde, 40 pasan + 1 omitido en local; `python -m rotaterra.actualizar` responde "No hay satélites unidos a esta rama…".)*
- [x] Cada rama de satélite pasa sus tests contra el núcleo solo, sin ninguna otra rama. *(PR #15 a #21 en GitHub: `tests` y `tests-postgres` en verde en los 7. En local: POWER 53, MERRA-2 45, HLS 69, MODIS 48, SMAP 71, IMERG 47, NASADEM 53.)*
- [x] Todas las ramas unidas a la vez pasan los mismos tests que hoy, sin conflictos entre sí. *(Unión de las 7 ramas en local, sin conflictos: 146 pasan. El registro encuentra los 8 satélites y respaldos, ninguno roto.)*
- [x] Un test verifica que ningún satélite importa a otro y que el núcleo no nombra a ninguno. *(`tests/test_nucleo.py`.)*
- [x] Un satélite roto no frena a los demás (test). *(`test_un_satelite_roto_queda_aislado` y `test_un_satelite_caido_no_frena_a_los_demas`.)*
- [x] Un respaldo sin su principal queda en espera (test). *(`test_respaldo_sin_su_principal_no_corre`.)*

## Fuera de alcance

Prender o apagar satélites sin tocar `main`, con un interruptor en GitHub (fue la opción descartada de la tarjeta). La base de datos sigue pendiente por decisión de Hernán.
