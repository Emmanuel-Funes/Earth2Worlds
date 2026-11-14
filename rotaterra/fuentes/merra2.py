"""Conector MERRA-2: temperatura y radiación diarias, respaldo de NASA POWER (spec 006)."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date

import httpx

from rotaterra.contrato import Observacion
from rotaterra.fuentes import earthdata
from rotaterra.fuentes.registro import Satelite

TEMPERATURA = "M2SDNXSLV"   # estadísticas diarias: T2MMAX, T2MMIN (K)
RADIACION = "M2T1NXRAD"     # horario: SWGDN (W/m²)
RESOLUCION_M = 55000
RELLENO = 1e14
RANGOS = {"temp_max": (-40.0, 60.0), "temp_min": (-40.0, 60.0), "radiacion": (0.0, 50.0)}
UNIDADES = {"temp_max": "°C", "temp_min": "°C", "radiacion": "MJ/m²/día"}
NOTA = "Respaldo de POWER: reanálisis MERRA-2 de la NASA · celda de 0,5° × 0,625°"
HILOS = 8
NO_ENTREGADO = "La NASA lista el archivo de este día pero OPeNDAP no lo entrega (404)"


class ErrorMERRA2(Exception):
    """La NASA no respondió o respondió algo ilegible."""


def celda(lat: float, lon: float) -> tuple[int, int]:
    """Índices (lat, lon) de la celda más cercana. Grilla: 361 latitudes × 576 longitudes."""
    i_lat = round((lat + 90) / 0.5)
    i_lon = round((lon + 180) / 0.625) % 576
    return i_lat, min(i_lon, 574)  # se piden 2 longitudes, ver earthdata.leer_csv


def _primero(datos: dict, nombre: str) -> list[float | None]:
    """Primera columna de cada fila (la celda pedida); None si es relleno."""
    try:
        return [None if f[0] is None or abs(f[0]) >= RELLENO else f[0] for f in datos[nombre]]
    except (KeyError, IndexError):
        raise ErrorMERRA2(f"OPeNDAP no devolvió '{nombre}'")


def _leer_o_nada(cliente: httpx.Client, url: str, expresion: str) -> dict | None:
    """None si OPeNDAP no entrega un archivo que la NASA ya lista (pasó el 15/10/2026 con el 11/8/2026, spec 042):
    ese día queda sin dato y los demás siguen, en lugar de caerse todo el pedido."""
    try:
        return earthdata.leer_csv(cliente, url, expresion)
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 404:
            return None
        raise


def leer_dia(cliente: httpx.Client, url_temp: str | None, url_rad: str | None,
             i_lat: int, i_lon: int) -> tuple[dict[str, float | None], set[str]]:
    """Valores del día y las variables cuyo archivo la NASA no entregó."""
    valores: dict[str, float | None] = {}
    no_entregadas: set[str] = set()
    lon = f"[{i_lon}:1:{i_lon + 1}]"
    if url_temp:
        datos = _leer_o_nada(cliente, url_temp, f"/T2MMAX[0][{i_lat}]{lon};/T2MMIN[0][{i_lat}]{lon}")
        for variable, nombre in (("temp_max", "T2MMAX"), ("temp_min", "T2MMIN")):
            kelvin = None if datos is None else _primero(datos, nombre)[0]
            valores[variable] = None if kelvin is None else round(kelvin - 273.15, 2)
            if datos is None:
                no_entregadas.add(variable)
    if url_rad:
        datos = _leer_o_nada(cliente, url_rad, f"/SWGDN[0:1:23][{i_lat}]{lon}")
        horas = [] if datos is None else [h for h in _primero(datos, "SWGDN") if h is not None]
        # promedio de W/m² en el día × 86400 s / 1e6 = MJ/m²/día; con menos de 24 horas no se calcula
        valores["radiacion"] = round(sum(horas) / 24 * 0.0864, 2) if len(horas) == 24 else None
        if datos is None:
            no_entregadas.add("radiacion")
    return valores, no_entregadas


def a_observacion(lote_id: str, dia: date, variable: str, valor: float | None,
                  motivo: str = "Sin dato") -> Observacion:
    base = dict(lote_id=lote_id, fecha=dia, variable=variable, unidad=UNIDADES[variable],
                fuente="MERRA2", resolucion_m=RESOLUCION_M)
    if valor is None:
        return Observacion(**base, valor=None, calidad="descartada", nota=f"{motivo} · {NOTA}")
    minimo, maximo = RANGOS[variable]
    if not minimo <= valor <= maximo:
        return Observacion(**base, valor=valor, calidad="dudosa", nota=f"Fuera del rango físico · {NOTA}")
    return Observacion(**base, valor=valor, calidad="buena", nota=NOTA)


def obtener_clima(lote_id: str, lat: float, lon: float, desde: date, hasta: date,
                  cliente: httpx.Client | None = None, hilos: int = HILOS) -> list[Observacion]:
    """Temperatura máxima, mínima y radiación de MERRA-2. Solo los días que la NASA ya publicó."""
    i_lat, i_lon = celda(lat, lon)
    try:
        cliente = earthdata.cliente_autorizado(cliente)
        archivos = {}
        for producto in (TEMPERATURA, RADIACION):
            coleccion = earthdata.coleccion_vigente(cliente, producto)
            archivos[producto] = earthdata.archivos_por_dia(cliente, coleccion, desde, hasta) if coleccion else {}
        dias = sorted(set(archivos[TEMPERATURA]) | set(archivos[RADIACION]))

        def leer(dia):
            return leer_dia(cliente, (archivos[TEMPERATURA].get(dia) or [None])[0],
                            (archivos[RADIACION].get(dia) or [None])[0], i_lat, i_lon)

        with ThreadPoolExecutor(max_workers=hilos) as grupo:
            leidos = dict(zip(dias, grupo.map(leer, dias)))
    except earthdata.FaltanCredenciales:
        raise
    except (httpx.HTTPError, KeyError, ValueError, earthdata.ErrorNASA) as error:
        raise ErrorMERRA2(f"No se pudo obtener el clima de MERRA-2: {error}") from error
    return [a_observacion(lote_id, dia, variable, valor, NO_ENTREGADO if variable in no_entregadas else "Sin dato")
            for dia, (valores, no_entregadas) in sorted(leidos.items()) for variable, valor in sorted(valores.items())]


# ---------- conexión con el núcleo (spec 009) ----------

# respaldo de POWER: entra solo si POWER falla (spec 005 y 006)
SATELITES = [Satelite("POWER:MERRA2", lambda lote, desde, hasta: obtener_clima(lote["id"], lote["lat"], lote["lon"],
                                                                                desde, hasta),
                      respaldo_de="POWER")]
