"""Acceso común a la NASA: token de Earthdata, búsqueda de archivos en CMR y lectura de un punto por OPeNDAP."""

import os
import re
from datetime import date

import httpx

URL_CMR = "https://cmr.earthdata.nasa.gov/search"
URL_TOKEN = "https://urs.earthdata.nasa.gov/api/users/find_or_create_token"


class FaltanCredenciales(Exception):
    """No están EARTHDATA_USERNAME / EARTHDATA_PASSWORD."""


class ErrorNASA(Exception):
    """Earthdata, CMR u OPeNDAP no respondieron o respondieron algo ilegible."""


def cliente_autorizado(cliente: httpx.Client | None = None) -> httpx.Client:
    """Cliente HTTP con el token de Earthdata ya puesto."""
    usuario = os.environ.get("EARTHDATA_USERNAME")
    clave = os.environ.get("EARTHDATA_PASSWORD")
    if not usuario or not clave:
        raise FaltanCredenciales("Faltan EARTHDATA_USERNAME y EARTHDATA_PASSWORD")
    cliente = cliente or httpx.Client(timeout=120, follow_redirects=True)
    respuesta = cliente.post(URL_TOKEN, auth=(usuario, clave))
    if respuesta.status_code in (401, 403):
        raise ErrorNASA("Earthdata rechazó el usuario o la contraseña")
    respuesta.raise_for_status()
    cliente.headers["Authorization"] = f"Bearer {respuesta.json()['access_token']}"
    return cliente


def coleccion_vigente(cliente: httpx.Client, nombre: str) -> str | None:
    """Id de CMR de la versión más nueva de un producto (None si CMR no lo tiene)."""
    items = cliente.get(f"{URL_CMR}/collections.umm_json",
                        params={"short_name": nombre, "page_size": 20}).json()["items"]
    if not items:
        return None
    return max(items, key=lambda i: i["umm"].get("Version", ""))["meta"]["concept-id"]


_FECHA = re.compile(r"(\d{8})")


def archivos(cliente: httpx.Client, coleccion: str, desde: date, hasta: date,
             caja: tuple[float, float, float, float] | None = None) -> list[tuple[str, str]]:
    """(nombre, URL OPeNDAP) de cada archivo del período; 'caja' = (oeste, sur, este, norte) opcional."""
    params = {"collection_concept_id": coleccion, "page_size": 2000, "sort_key": "start_date",
              "temporal": f"{desde.isoformat()}T00:00:00Z,{hasta.isoformat()}T23:59:59Z"}
    if caja:
        params["bounding_box"] = ",".join(str(c) for c in caja)
    hallados = []
    encabezados = {}
    while True:
        respuesta = cliente.get(f"{URL_CMR}/granules.umm_json", params=params, headers=encabezados)
        respuesta.raise_for_status()
        items = respuesta.json()["items"]
        for item in items:
            urls = [u["URL"] for u in item["umm"].get("RelatedUrls", []) if "opendap" in u["URL"].lower()]
            if urls:
                hallados.append((item["umm"]["GranuleUR"], urls[0]))
        siguiente = respuesta.headers.get("CMR-Search-After")
        if not siguiente or len(items) < params["page_size"]:
            return hallados
        encabezados = {"CMR-Search-After": siguiente}


def archivos_por_dia(cliente: httpx.Client, coleccion: str, desde: date, hasta: date) -> dict[date, list[str]]:
    """URL OPeNDAP de cada archivo del período, agrupadas por la fecha AAAAMMDD que figura en su nombre."""
    por_dia: dict[date, list[str]] = {}
    for nombre, url in archivos(cliente, coleccion, desde, hasta):
        hallado = _FECHA.search(nombre)
        if hallado:
            texto = hallado[1]
            dia = date(int(texto[:4]), int(texto[4:6]), int(texto[6:8]))
            if desde <= dia <= hasta:
                por_dia.setdefault(dia, []).append(url)
    return por_dia


def leer_csv(cliente: httpx.Client, url: str, expresion: str) -> dict[str, list[list[float | None]]]:
    """Pide a OPeNDAP un recorte en CSV. Devuelve variable -> filas de valores (vacío = None).

    Ojo: el servidor de la NASA devuelve vacío cuando el recorte es de un solo valor;
    por eso los conectores piden 2 celdas en la última dimensión y usan la primera.
    """
    respuesta = cliente.get(f"{url}.dap.csv", params={"dap4.ce": expresion})
    if respuesta.status_code in (401, 403):
        raise ErrorNASA("La NASA negó el acceso: ¿está autorizada la aplicación del archivo en Earthdata?")
    respuesta.raise_for_status()
    variables: dict[str, list[list[float | None]]] = {}
    for linea in respuesta.text.splitlines()[1:]:
        if "," not in linea:
            continue
        nombre, *valores = [v.strip() for v in linea.split(",")]
        nombre = nombre.split("[")[0].lstrip("/")
        variables.setdefault(nombre, []).append([float(v) if v else None for v in valores])
    return variables
