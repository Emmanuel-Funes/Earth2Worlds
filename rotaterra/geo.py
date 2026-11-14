"""Ayudas geográficas."""


def poligono_desde_esquinas(texto: str) -> dict:
    """'lat, lon; lat, lon; ...' (como lo copia Google Maps) -> GeoJSON Polygon."""
    puntos = []
    for esquina in texto.split(";"):
        if not esquina.strip():  # tolera un ';' de más al final o entre esquinas
            continue
        try:
            lat, lon = (float(x) for x in esquina.split(","))
        except ValueError:
            raise ValueError(f"Esquina mal escrita: '{esquina.strip()}'. Formato: 'lat, lon; lat, lon; ...'") from None
        puntos.append([lon, lat])
    if len(puntos) < 3:
        raise ValueError("Un lote necesita al menos 3 esquinas")
    return {"type": "Polygon", "coordinates": [puntos + [puntos[0]]]}


def validar_poligono(poligono: dict) -> None:
    """El lote tiene que ser un GeoJSON Polygon válido, en grados decimales (EPSG:4326)."""
    from shapely.geometry import shape

    if poligono.get("type") != "Polygon":
        raise ValueError("El lote tiene que ser un GeoJSON de tipo Polygon")
    try:
        geometria = shape(poligono)
    except Exception as error:
        raise ValueError(f"Polígono inválido: {error}") from error
    if not geometria.is_valid or geometria.area == 0:
        raise ValueError("El polígono del lote no es válido (¿esquinas cruzadas o repetidas?)")
    minx, miny, maxx, maxy = geometria.bounds
    if not (-180 <= minx and maxx <= 180 and -90 <= miny and maxy <= 90):
        raise ValueError("Coordenadas fuera de rango: usá grados decimales (EPSG:4326)")
