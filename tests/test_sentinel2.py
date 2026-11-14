"""Sentinel-2 L2A (spec 014): tests sin internet, con escenas sintéticas en GeoTIFF locales."""

from datetime import date, datetime

import numpy as np
import pytest
from fastapi.testclient import TestClient

from rotaterra import api
from rotaterra.fuentes import registro, sentinel2

LOTE = {"type": "Polygon", "coordinates": [[
    [-65.30, -33.70], [-65.295, -33.70], [-65.295, -33.705], [-65.30, -33.705], [-65.30, -33.70]]]}


# ---------- cálculo puro ----------

def test_ndvi_de_cultivo_verde():
    rojo = np.array([[0.04]])
    nir = np.array([[0.36]])
    assert sentinel2.diferencia_normalizada(nir, rojo)[0, 0] == pytest.approx(0.8)


def test_division_por_cero_y_sin_dato_no_dan_numero():
    a = sentinel2.reflectancia(np.array([[0, 500]]), 0.0001, 0.0)
    b = sentinel2.reflectancia(np.array([[300, 0]]), 0.0001, 0.0)
    assert np.isnan(sentinel2.diferencia_normalizada(a, b)).all()
    cero = np.array([[0.0]])
    assert np.isnan(sentinel2.diferencia_normalizada(cero, cero)).all()


@pytest.mark.parametrize("clase, limpio", [
    (0, False), (1, False), (2, False), (3, False), (4, True), (5, True),
    (6, False), (7, False), (8, False), (9, False), (10, False), (11, False),
])
def test_mascara_scl(clase, limpio):
    assert sentinel2.mascara_valida(np.array([[clase]], dtype="uint8"))[0, 0] == limpio


@pytest.mark.parametrize("propiedades, bandas, esperado", [
    # Earth Search ya restó el offset en los píxeles: no se aplica el -0.1 de raster:bands (verificado con datos reales)
    ({"earthsearch:boa_offset_applied": True, "s2:processing_baseline": "05.11"},
     [{"scale": 0.0001, "offset": -0.1}], (0.0001, 0.0)),
    # sin aplicar: se usa el offset declarado
    ({"earthsearch:boa_offset_applied": False, "s2:processing_baseline": "05.11"},
     [{"scale": 0.0001, "offset": -0.1}], (0.0001, -0.1)),
    # sin raster:bands: lo decide la línea de base
    ({"s2:processing_baseline": "04.00"}, None, (0.0001, -0.1)),
    ({"s2:processing_baseline": "02.09"}, None, (0.0001, 0.0)),
    ({}, None, (0.0001, 0.0)),
])
def test_escala_y_offset(propiedades, bandas, esperado):
    assert sentinel2.escala_y_offset(propiedades, bandas) == pytest.approx(esperado)


def test_reflectancia_con_offset():
    r = sentinel2.reflectancia(np.array([[1300, 0]], dtype="uint16"), 0.0001, -0.1)
    assert r[0, 0] == pytest.approx(0.03)
    assert np.isnan(r[0, 1])


def test_resumen_solo_cuenta_pixeles_del_lote():
    indice = np.array([[0.2, 0.4, 0.6, 0.8]])
    dentro = np.array([[True, True, True, False]])
    validos = np.array([[True, True, False, True]])
    r = sentinel2.resumir(indice, dentro, validos)
    assert r.validos_pct == pytest.approx(200 / 3)
    assert r.mediana == pytest.approx(0.3)


@pytest.mark.parametrize("pct, calidad", [(100, "buena"), (60, "buena"), (45, "dudosa"), (19, "descartada")])
def test_calidad_segun_pixeles_validos(pct, calidad):
    r = sentinel2.Resumen(0.61, 0.6, 0.5, 0.7, pct)
    obs = sentinel2.a_observacion("lote-7", date(2026, 1, 16), "ndvi", r, "S2C 20HKH")
    assert obs.calidad == calidad
    assert obs.fuente == "SENTINEL2" and obs.resolucion_m == 10 and obs.unidad == "índice (-1 a 1)"
    assert obs.nota.startswith("Respaldo de HLS · Sentinel-2 L2A (ESA) · S2C 20HKH")
    if calidad == "descartada":
        assert obs.valor is None
    else:
        assert obs.valor == 0.61


def test_ndmi_va_a_20_m():
    obs = sentinel2.a_observacion("lote-7", date(2026, 1, 16), "ndmi", sentinel2.Resumen(0.1, 0.1, 0, 0.2, 100), "x")
    assert obs.resolucion_m == 20


def test_sin_pixeles_validos_no_inventa_y_dice_por_que():
    scl = np.array([[10, 10, 10, 3]])
    lote = np.ones_like(scl, dtype=bool)
    r = sentinel2.resumir(np.array([[0.5, 0.5, 0.5, 0.5]]), lote, sentinel2.mascara_valida(scl))
    obs = sentinel2.a_observacion("lote-7", date(2026, 1, 26), "ndvi", r, "S2C 20HKH",
                                  sentinel2.motivo_descarte(scl, lote))
    assert obs.valor is None and obs.calidad == "descartada"
    assert "cirros 75%" in obs.nota and "sombra de nube 25%" in obs.nota


@pytest.mark.parametrize("poligono, desde, hasta", [
    ({"type": "Point", "coordinates": [-65.3, -33.7]}, date(2026, 1, 1), date(2026, 2, 1)),
    (LOTE, date(2026, 2, 1), date(2026, 1, 1)),
    (LOTE, date(2024, 1, 1), date(2026, 1, 1)),
])
def test_pedido_invalido(poligono, desde, hasta):
    with pytest.raises(ValueError):
        sentinel2.validar_pedido(poligono, desde, hasta)


# ---------- búsqueda en Earth Search (simulada) ----------

class Item:
    def __init__(self, nubes):
        self.properties = {"eo:cloud_cover": nubes}


def cliente_falso(monkeypatch, respuestas):
    """respuestas: colección -> lista de items, o una excepción para fallar una vez."""
    import pystac_client

    llamadas = []

    class Busqueda:
        def __init__(self, items):
            self._items = items

        def items(self):
            return iter(self._items)

    class Cliente:
        def search(self, **kwargs):
            llamadas.append(kwargs)
            r = respuestas[kwargs["collections"][0]]
            if isinstance(r, list) and r and isinstance(r[0], Exception):
                raise r.pop(0)
            return Busqueda(r)

    monkeypatch.setattr(pystac_client.Client, "open", staticmethod(lambda url: Cliente()))
    monkeypatch.setattr(sentinel2.time, "sleep", lambda s: None)
    return llamadas


def test_busqueda_por_bbox_con_reintento_y_filtro_de_nubes(monkeypatch):
    llamadas = cliente_falso(monkeypatch, {"sentinel-2-l2a": [RuntimeError("caído"), Item(5), Item(95)]})
    escenas = sentinel2.buscar_escenas(LOTE, date(2026, 1, 1), date(2026, 1, 31), nubosidad_max=70)
    assert len(escenas) == 1
    assert llamadas[0]["bbox"] == pytest.approx([-65.30, -33.705, -65.295, -33.70])
    assert llamadas[0]["datetime"] == "2026-01-01T00:00:00Z/2026-01-31T23:59:59Z"
    assert len(llamadas) == 2  # falló una vez y reintentó; no hizo falta la colección 1


def test_si_la_coleccion_no_trae_nada_prueba_la_coleccion_1(monkeypatch):
    llamadas = cliente_falso(monkeypatch, {"sentinel-2-l2a": [], "sentinel-2-c1-l2a": [Item(10)]})
    assert len(sentinel2.buscar_escenas(LOTE, date(2026, 1, 1), date(2026, 1, 31), 70)) == 1
    assert [c["collections"][0] for c in llamadas] == ["sentinel-2-l2a", "sentinel-2-c1-l2a"]


def test_busqueda_que_siempre_falla_da_error_claro(monkeypatch):
    cliente_falso(monkeypatch, {"sentinel-2-l2a": [RuntimeError("caído")] * 3})
    with pytest.raises(sentinel2.ErrorSentinel2, match="Earth Search"):
        sentinel2.buscar_escenas(LOTE, date(2026, 1, 1), date(2026, 1, 31), 70)


# ---------- escena sintética de punta a punta ----------

class EscenaFalsa:
    """Imita un item de Earth Search con bandas en GeoTIFF locales (UTM 20S, grilla de 10 m y de 20 m)."""

    def __init__(self, carpeta, dia, dn, scl, offset_aplicado=True, ident=None):
        import rasterio
        from rasterio.transform import from_origin
        from rasterio.warp import transform

        self.id = ident or f"S2C_20HKH_202601{dia:02d}_0_L2A"
        self.datetime = datetime(2026, 1, dia, 14, 22)
        self.properties = {"earthsearch:boa_offset_applied": offset_aplicado, "s2:processing_baseline": "05.11",
                           "eo:cloud_cover": 1.0}
        self.assets = {}
        xs, ys = transform("EPSG:4326", "EPSG:32720", [-65.302], [-33.698])
        x0, y0 = round(xs[0] / 20) * 20, round(ys[0] / 20) * 20  # grillas de 10 y 20 m alineadas, como en la ESA
        for asset, valor in {**dn, "scl": scl}.items():
            res = 10 if asset in ("red", "nir") else 20
            n = 800 // res
            ruta = f"{carpeta}/{self.id}_{asset}.tif"
            dtype = "uint8" if asset == "scl" else "uint16"
            with rasterio.open(ruta, "w", driver="GTiff", width=n, height=n, count=1, crs="EPSG:32720",
                               transform=from_origin(x0, y0, res, res), dtype=dtype, nodata=0) as destino:
                destino.write(np.full((n, n), valor, dtype=dtype), 1)
            extra = {} if asset == "scl" else {"raster:bands": [{"scale": 0.0001, "offset": -0.1}]}
            self.assets[asset] = type("Asset", (), {"href": ruta, "extra_fields": extra})()


DN = {"red": 400, "nir": 3600, "nir08": 3400, "swir16": 1700}


def test_procesar_escena_de_punta_a_punta(tmp_path):
    escena = EscenaFalsa(tmp_path, 16, DN, scl=4)
    resultado = sentinel2.procesar_escena("lote-7", escena, LOTE)
    ndvi = next(o for o, _ in resultado if o.variable == "ndvi")
    ndmi = next(o for o, _ in resultado if o.variable == "ndmi")
    assert ndvi.valor == pytest.approx(0.8) and ndvi.calidad == "buena" and ndvi.resolucion_m == 10
    assert ndmi.valor == pytest.approx(1 / 3, abs=1e-3) and ndmi.resolucion_m == 20
    assert ndvi.fecha == date(2026, 1, 16) and ndvi.fuente == "SENTINEL2"
    assert "S2C 20HKH" in ndvi.nota and "válidos 100%" in ndvi.nota


def test_escena_sin_offset_aplicado_resta_1000(tmp_path):
    escena = EscenaFalsa(tmp_path, 16, {"red": 1400, "nir": 4600, "nir08": 4400, "swir16": 2700}, scl=4,
                         offset_aplicado=False)
    ndvi = next(o for o, _ in sentinel2.procesar_escena("lote-7", escena, LOTE) if o.variable == "ndvi")
    assert ndvi.valor == pytest.approx(0.8)  # (0.36 - 0.04) / (0.36 + 0.04)


@pytest.mark.parametrize("scl", [3, 6, 8, 9, 10, 11])
def test_escena_tapada_se_descarta(tmp_path, scl):
    escena = EscenaFalsa(tmp_path, 26, DN, scl=scl)
    resultado = sentinel2.procesar_escena("lote-7", escena, LOTE)
    assert all(o.valor is None and o.calidad == "descartada" for o, _ in resultado)
    assert all(sentinel2.SCL_NOMBRES[scl] in o.nota for o, _ in resultado)


def test_suelo_desnudo_cuenta_como_valido(tmp_path):
    escena = EscenaFalsa(tmp_path, 3, {"red": 2000, "nir": 2600, "nir08": 2600, "swir16": 3200}, scl=5)
    ndvi = next(o for o, _ in sentinel2.procesar_escena("lote-7", escena, LOTE) if o.variable == "ndvi")
    assert ndvi.calidad == "buena" and ndvi.valor == pytest.approx(0.13, abs=1e-3)


def test_obtener_ndvi_mismo_dia_gana_la_mas_limpia(tmp_path, monkeypatch):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    nublada = EscenaFalsa(tmp_path / "a", 16, DN, scl=9, ident="S2C_20HKH_20260116_0_L2A")
    limpia = EscenaFalsa(tmp_path / "b", 16, DN, scl=4, ident="S2C_20HKH_20260116_1_L2A")
    otra = EscenaFalsa(tmp_path / "b", 11, DN, scl=4)
    monkeypatch.setattr(sentinel2, "buscar_escenas", lambda *a, **k: [nublada, limpia, otra])
    obs = sentinel2.obtener_ndvi("lote-7", LOTE, date(2026, 1, 1), date(2026, 1, 31))
    assert [(o.fecha.day, o.variable) for o in obs] == [(11, "ndmi"), (11, "ndvi"), (16, "ndmi"), (16, "ndvi")]
    assert all(o.calidad == "buena" for o in obs)


def test_escena_ilegible_es_error_de_sentinel2(monkeypatch):
    escena = type("Item", (), {"id": "rota", "assets": {}, "properties": {}})()
    monkeypatch.setattr(sentinel2, "buscar_escenas", lambda *a, **k: [escena])
    with pytest.raises(sentinel2.ErrorSentinel2, match="rota"):
        sentinel2.obtener_ndvi("lote-7", LOTE, date(2026, 1, 1), date(2026, 1, 31))


# ---------- conexión con el núcleo ----------

def test_se_anuncia_como_primer_respaldo_de_hls():
    s = next(s for s in registro.descubrir().satelites if s.nombre == "HLS:SENTINEL2")
    assert s.respaldo_de == "HLS" and s.orden == 1 and not s.estatico


def test_pedir_del_registro_usa_el_lote(monkeypatch):
    vistos = []
    monkeypatch.setattr(sentinel2, "obtener_ndvi", lambda *a: vistos.append(a) or [])
    sentinel2.SATELITES[0].pedir({"id": "lote-7", "poligono": LOTE}, date(2026, 1, 1), date(2026, 1, 31))
    assert vistos == [("lote-7", LOTE, date(2026, 1, 1), date(2026, 1, 31))]


def test_api_poligono_invalido_responde_422():
    r = TestClient(api.app).post("/ndvi/sentinel2", json=dict(
        lote_id="lote-7", poligono={"type": "Point", "coordinates": [0, 0]}, desde="2026-01-01", hasta="2026-01-31"))
    assert r.status_code == 422


def test_api_earth_search_caido_responde_502(monkeypatch):
    def caido(*a, **k):
        raise sentinel2.ErrorSentinel2("Earth Search no responde")
    monkeypatch.setattr(sentinel2, "buscar_escenas", caido)
    r = TestClient(api.app).post("/ndvi/sentinel2", json=dict(
        lote_id="lote-7", poligono=LOTE, desde="2026-01-01", hasta="2026-01-31"))
    assert r.status_code == 502 and "Earth Search" in r.json()["detail"]
