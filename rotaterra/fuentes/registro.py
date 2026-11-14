"""Registro de satélites (spec 009).

Cada satélite vive en su propio archivo de `rotaterra/fuentes/` y se anuncia solo con una lista
`SATELITES`. El núcleo (actualización y API) no importa ningún satélite por su nombre: usa los que
encuentra. Así cada satélite se une a `main` desde su rama sin tocar el núcleo ni a los demás.
"""

import importlib
import pkgutil
from dataclasses import dataclass, field
from typing import Callable

# módulos de rotaterra/fuentes/ que son del núcleo y no satélites
NUCLEO = {"registro", "earthdata"}


class Pendiente(Exception):
    """La NASA sigue procesando el pedido: se retoma en la próxima corrida (no es un error)."""


@dataclass(frozen=True)
class Satelite:
    nombre: str                     # como queda en `actualizaciones`: "POWER", o "POWER:MERRA2" si es respaldo
    pedir: Callable                 # pedir(lote, desde, hasta) -> list[Observacion]
    respaldo_de: str | None = None  # nombre del satélite principal al que respalda
    estatico: bool = False          # dato fijo: una vez guardado no se vuelve a pedir (ej. NASADEM)
    orden: int = 1                  # si un satélite tiene varios respaldos, entra primero el de menor orden
    al_dia: bool = False            # respaldo "del día": solo completa los últimos días que el principal no publicó


@dataclass
class Conectados:
    satelites: list[Satelite] = field(default_factory=list)
    rutas: list = field(default_factory=list)         # APIRouter de prueba de cada satélite
    rotos: dict[str, str] = field(default_factory=dict)  # módulo -> error al cargarlo


def respaldos_en_orden(satelites: list[Satelite], al_dia: bool = False) -> dict[str, list[Satelite]]:
    """Principal -> sus respaldos en el orden en que entran (ej. HLS -> [VIIRS, MODIS]). Lo usan la
    actualización nocturna y la consulta en el momento (specs 005 y 012).

    Con `al_dia=True` devuelve solo los respaldos del día, que completan la cola de días (spec 043); si no, solo los
    respaldos comunes."""
    respaldos: dict[str, list[Satelite]] = {}
    elegidos = (s for s in satelites if s.respaldo_de and s.al_dia == al_dia)
    for s in sorted(elegidos, key=lambda s: (s.orden, s.nombre)):
        respaldos.setdefault(s.respaldo_de, []).append(s)
    return respaldos


def _roto(modulo: str, error: Exception) -> Satelite:
    def pedir(lote, desde, hasta):
        raise RuntimeError(f"El satélite '{modulo}' no carga: {type(error).__name__}: {error}")
    return Satelite(nombre=modulo.upper(), pedir=pedir)


def descubrir(paquete: str = "rotaterra.fuentes") -> Conectados:
    """Busca los satélites unidos a esta rama. Uno que no carga queda aislado y no frena a los demás."""
    conectados = Conectados()
    raiz = importlib.import_module(paquete)
    for info in sorted(pkgutil.iter_modules(raiz.__path__), key=lambda m: m.name):
        if info.name in NUCLEO or info.name.startswith("_"):
            continue
        try:
            modulo = importlib.import_module(f"{paquete}.{info.name}")
        except Exception as error:  # un satélite roto no rompe al resto
            conectados.rotos[info.name] = f"{type(error).__name__}: {error}"
            conectados.satelites.append(_roto(info.name, error))
            continue
        conectados.satelites += list(getattr(modulo, "SATELITES", []))
        if getattr(modulo, "router", None) is not None:
            conectados.rutas.append(modulo.router)
    return conectados
