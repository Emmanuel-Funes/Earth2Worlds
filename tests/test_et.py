from datetime import date

import httpx
import numpy as np
import pytest

from rotaterra.fuentes import et
from rotaterra.geo import poligono_desde_esquinas

# lote de prueba de ~50 ha alrededor de -33,7025; -65,2975 (el mismo del NDVI de MODIS y VIIRS)
POLIGONO = poligono_desde_esquinas("-33.699, -65.301; -33.699, -65.294; -33.706, -65.294; -33.706, -65.301")

GRUPO = "/MOD_Grid_MOD16A2/Data_Fields"  # rutas reales de MOD16A2 v061 (prueba del 4/10/2026)
RUTAS = {"et": f"{GRUPO}/ET_500m", "pet": f"{GRUPO}/PET_500m", "qc": f"{GRUPO}/ET_QC_500m"}
DMR = """<?xml version="1.0" encoding="UTF-8"?>
<Dataset xmlns="http://xml.opendap.org/ns/DAP/4.0#" name="MOD16A2.hdf">
  <Group name="MOD_Grid_MOD16A2">
    <Group name="Data_Fields">
      <Int16 name="ET_500m">
        <Attribute name="scale_factor" type="Float64"><Value>0.1</Value></Attribute>
        <Attribute name="valid_range" type="Int16"><Value>-32767</Value><Value>32700</Value></Attribute>
      </Int16>
      <Int16 name="LE_500m"/>
      <Int16 name="PET_500m">
        <Attribute name="scale_factor" type="Float64"><Value>0.1</Value></Attribute>
      </Int16>
      <Int16 name="PLE_500m"/>
      <UInt8 name="ET_QC_500m"/>
    </Group>
  </Group>
</Dataset>"""


@pytest.fixture(autouse=True)
def sin_rutas_guardadas():
    et._RUTAS.clear()
    et._ATRIBUTOS.clear()


@pytest.fixture
def credenciales(monkeypatch):
    monkeypatch.setenv("EARTHDATA_USERNAME", "usuario")
    monkeypatch.setenv("EARTHDATA_PASSWORD", "clave")


def test_celda_del_lote_de_prueba():
    # mosaico h12v12 confirmado en la prueba real (MOD16A2.A2026001.h12v12)
    assert et.celda(-33.7025, -65.2975) == (12, 12, 888, 1362)


def test_coordenadas_vuelven_al_mismo_pixel():
    h, v, f0, f1, c0, c1 = et.ventana(POLIGONO)
    lat, lon = et.coordenadas(h, v, f0, f1, c0, c1)
    assert et.celda(lat[0, 0], lon[0, 0]) == (h, v, f0, c0)
    assert et.celda(lat[-1, -1], lon[-1, -1]) == (h, v, f1, c1)


def test_rutas_y_escala_salen_de_los_metadatos():
    rutas, atributos = et.rutas_de_capas(DMR)
    assert rutas == RUTAS  # PET_500m no se confunde con ET_500m, ni ET_QC con ET
    assert atributos["et"] == {"escala": 0.1, "valido_max": 32700}
    assert atributos["qc"] == {"escala": et.ESCALA, "valido_max": et.VALIDO_MAX}


def test_rutas_con_nombres_al_estilo_viirs():
    dmr = DMR.replace('<Group name="MOD_Grid_MOD16A2">', '<Group name="HDFEOS"><Group name="VIIRS_Grid_ET_500m">') \
        .replace("Data_Fields", "Data Fields").replace("  </Group>\n</Dataset>", "  </Group></Group>\n</Dataset>")
    rutas, _ = et.rutas_de_capas(dmr)
    assert rutas["et"] == "/HDFEOS/VIIRS_Grid_ET_500m/Data Fields/ET_500m"


def test_metadatos_sin_pet_avisan():
    with pytest.raises(et.ErrorET, match="pet"):
        et.rutas_de_capas(DMR.replace('"PET_500m"', '"PET_1km"'))


def test_calendario_de_compuestos():
    assert et.dias_del_compuesto(date(2026, 1, 9)) == 8
    assert et.dias_del_compuesto(date(2026, 12, 27)) == 5   # día 361 de un año común
    assert et.dias_del_compuesto(date(2024, 12, 26)) == 6   # día 361 de un bisiesto
    assert et.compuestos(date(2026, 1, 1), date(2026, 1, 31)) == [date(2026, 1, d) for d in (1, 9, 17, 25)]
    assert et.compuestos(date(2026, 1, 5), date(2026, 1, 10)) == [date(2026, 1, 1), date(2026, 1, 9)]
    assert et.compuestos(date(2025, 12, 30), date(2026, 1, 2)) == [date(2025, 12, 27), date(2026, 1, 1)]


def test_inicio_compuesto():
    assert et.inicio_compuesto("MOD16A2.A2026009.h12v12.061.2026020212752") == date(2026, 1, 9)


def ventana_sintetica(et_crudo=256, pet_crudo=480, qc=0, poligono=POLIGONO):
    h, v, f0, f1, c0, c1 = et.ventana(poligono)
    lat, lon = et.coordenadas(h, v, f0, f1, c0, c1)
    forma = lat.shape
    return {"et": np.full(forma, et_crudo, dtype=float), "pet": np.full(forma, pet_crudo, dtype=float),
            "qc": np.full(forma, qc, dtype=float), "lat": lat, "lon": lon}


def test_compuesto_limpio_da_promedio_diario():
    obs = et.resumir("lote-7", POLIGONO, ventana_sintetica(), date(2026, 1, 1))
    ev, pet = obs
    assert (ev.variable, ev.valor, ev.unidad, ev.calidad, ev.fecha, ev.fuente, ev.resolucion_m) == \
        ("et_mm_dia", 3.2, "mm/día", "buena", date(2026, 1, 1), "MODIS", 500)  # 25,6 mm / 8 días
    assert (pet.variable, pet.valor) == ("pet_mm_dia", 6.0)
    assert "inicio del compuesto de 8 días (2026-01-01 al 2026-01-08)" in ev.nota and "Terra" in ev.nota


def test_ultimo_compuesto_del_anio_divide_por_5():
    ev, _ = et.resumir("lote-7", POLIGONO, ventana_sintetica(et_crudo=200), date(2025, 12, 27))
    assert ev.valor == 4.0 and "5 días" in ev.nota


def test_relleno_se_descarta_y_dice_por_que():
    ev, pet = et.resumir("lote-7", POLIGONO, ventana_sintetica(et_crudo=32762, pet_crudo=32762), date(2026, 1, 1))
    assert ev.valor is None and ev.calidad == "descartada" and "urbano" in ev.nota
    assert pet.valor is None and pet.calidad == "descartada"


def test_sin_dato_se_descarta():
    ev, _ = et.resumir("lote-7", POLIGONO, ventana_sintetica(et_crudo=np.nan), date(2026, 1, 1))
    assert ev.valor is None and ev.calidad == "descartada" and "sin dato" in ev.nota


def test_algoritmo_de_respaldo_es_dudoso():
    ev, _ = et.resumir("lote-7", POLIGONO, ventana_sintetica(qc=3 << 5), date(2026, 1, 1))
    assert ev.valor == 3.2 and ev.calidad == "dudosa" and "algoritmo principal 0%" in ev.nota


def test_lote_parcialmente_sin_dato_es_dudoso():
    from shapely.geometry import Point, shape

    grande = poligono_desde_esquinas("-33.69, -65.31; -33.69, -65.29; -33.71, -65.29; -33.71, -65.31")  # ~400 ha
    datos = ventana_sintetica(poligono=grande)
    lote = shape(grande)
    adentro = [(i, j) for i in range(datos["lat"].shape[0]) for j in range(datos["lat"].shape[1])
               if lote.contains(Point(datos["lon"][i, j], datos["lat"][i, j]))]
    for i, j in adentro[: len(adentro) // 2]:
        datos["et"][i, j] = 32767
    ev, pet = et.resumir("lote-7", grande, datos, date(2026, 1, 1))
    assert ev.calidad == "dudosa" and ev.valor == 3.2 and pet.calidad == "buena"


def test_lote_menor_a_un_pixel_usa_el_del_centro():
    chico = poligono_desde_esquinas("-33.7024, -65.2976; -33.7024, -65.2974; -33.7026, -65.2974; -33.7026, -65.2976")
    ev, _ = et.resumir("lote-7", chico, ventana_sintetica(), date(2026, 1, 1))
    assert ev.valor == 3.2 and "menor a un píxel" in ev.nota


def test_viirs_se_anota_como_viirs():
    ev, _ = et.resumir("lote-7", POLIGONO, ventana_sintetica(), date(2026, 1, 1), "VJ116A2")
    assert ev.fuente == "VIIRS" and "NOAA-20" in ev.nota


class NASAFalsa:
    """CMR y OPeNDAP simulados: por_producto = {producto: {día del año de inicio: ventana}}."""

    def __init__(self, por_producto):
        self.por_producto = por_producto
        self.leidos = []

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        url = str(pedido.url)
        if "find_or_create_token" in url:
            return httpx.Response(200, json={"access_token": "tk"})
        if "/collections.umm_json" in url:
            nombre = pedido.url.params["short_name"]
            if nombre not in self.por_producto:
                return httpx.Response(200, json={"items": []})
            return httpx.Response(200, json={"items": [{"meta": {"concept-id": f"C-{nombre}"},
                                                        "umm": {"Version": "002"}}]})
        if "/granules.umm_json" in url:
            producto = pedido.url.params["collection_concept_id"][2:]
            nombres = [f"{producto}.A2026{d:03d}.{t}.061.1" for d in self.por_producto[producto]
                       for t in ("h12v12", "h12v13")]
            return httpx.Response(200, json={"items": [{"umm": {"GranuleUR": n, "RelatedUrls": [
                {"URL": f"https://opendap.earthdata.nasa.gov/collections/C-{producto}/granules/{n}.h5"}]}}
                for n in nombres]})
        if url.endswith(".dmr"):
            return httpx.Response(200, text=DMR)
        if ".dap.csv" in url:
            assert "h12v12" in url
            granulo = url.split("/granules/")[1]
            producto, dia = granulo.split(".")[0], int(granulo.split(".")[1][5:])
            self.leidos.append((producto, dia))
            datos = self.por_producto[producto][dia]
            lineas = ["Dataset: x"]
            for capa, ruta in RUTAS.items():
                for i, fila in enumerate(datos[capa]):
                    lineas.append(f"{ruta}[{i}], " + ", ".join("" if np.isnan(v) else repr(float(v)) for v in fila))
            return httpx.Response(200, text="\n".join(lineas) + "\n")
        return httpx.Response(404)


def pedir(nasa, desde=date(2026, 1, 1), hasta=date(2026, 1, 31)):
    return et.obtener_et("lote-7", POLIGONO, desde, hasta, cliente=httpx.Client(transport=httpx.MockTransport(nasa)))


def test_obtener_et_de_terra(credenciales):
    nasa = NASAFalsa({"MOD16A2": {1: ventana_sintetica(256), 9: ventana_sintetica(320), 17: ventana_sintetica(240),
                                  25: ventana_sintetica(200)}})
    obs = pedir(nasa)
    assert [(o.fecha, o.variable, o.valor) for o in obs if o.variable == "et_mm_dia"] == [
        (date(2026, 1, 1), "et_mm_dia", 3.2), (date(2026, 1, 9), "et_mm_dia", 4.0),
        (date(2026, 1, 17), "et_mm_dia", 3.0), (date(2026, 1, 25), "et_mm_dia", 2.5)]
    assert len(obs) == 8 and {o.fuente for o in obs} == {"MODIS"}


def test_lo_que_falta_se_completa_con_el_siguiente_producto(credenciales):
    nasa = NASAFalsa({"MOD16A2": {1: ventana_sintetica(256), 9: ventana_sintetica(32767)},
                      "MYD16A2": {1: ventana_sintetica(999), 9: ventana_sintetica(320), 17: ventana_sintetica(240)},
                      "VJ116A2": {25: ventana_sintetica(200)}})
    obs = [o for o in pedir(nasa) if o.variable == "et_mm_dia"]
    assert [(o.fecha.day, o.valor, o.fuente) for o in obs] == [(1, 3.2, "MODIS"), (9, 4.0, "MODIS"),
                                                              (17, 3.0, "MODIS"), (25, 2.5, "VIIRS")]
    assert "Terra" in obs[0].nota and "Aqua" in obs[1].nota and "NOAA-20" in obs[3].nota
    assert ("MYD16A2", 1) not in nasa.leidos  # el 1/1 ya estaba cubierto por Terra: no se vuelve a leer


def test_compuesto_sin_dato_en_ningun_producto_queda_descartado(credenciales):
    nasa = NASAFalsa({"MOD16A2": {1: ventana_sintetica(256), 9: ventana_sintetica(32766)}})
    obs = [o for o in pedir(nasa, hasta=date(2026, 1, 16)) if o.variable == "et_mm_dia"]
    assert [(o.fecha.day, o.valor, o.calidad) for o in obs] == [(1, 3.2, "buena"), (9, None, "descartada")]
    assert "agua" in obs[1].nota


def test_sin_archivos_es_error_para_que_entren_los_respaldos(credenciales):
    with pytest.raises(et.ErrorET, match="CMR no tiene"):
        pedir(NASAFalsa({}))


def test_todo_relleno_es_error_para_que_entren_los_respaldos(credenciales):
    nasa = NASAFalsa({"MOD16A2": {1: ventana_sintetica(32762)}})
    with pytest.raises(et.ErrorET, match="urbano"):
        pedir(nasa, hasta=date(2026, 1, 8))


def test_sin_credenciales(monkeypatch):
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    monkeypatch.delenv("EARTHDATA_PASSWORD", raising=False)
    with pytest.raises(et.FaltanCredenciales):
        et.obtener_et("lote-7", POLIGONO, date(2026, 1, 1), date(2026, 1, 8),
                      cliente=httpx.Client(transport=httpx.MockTransport(NASAFalsa({}))))


def test_pedido_invalido():
    with pytest.raises(ValueError):
        et.obtener_et("lote-7", POLIGONO, date(2026, 2, 1), date(2026, 1, 1))


def test_se_registra_como_principal_de_et():
    (satelite,) = et.SATELITES
    assert (satelite.nombre, satelite.respaldo_de) == ("ET", None)


def test_endpoint_de_prueba(credenciales, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    nasa = NASAFalsa({"MOD16A2": {1: ventana_sintetica(256)}})
    original = et.obtener_et
    monkeypatch.setattr(et, "obtener_et", lambda *a: original(
        *a, cliente=httpx.Client(transport=httpx.MockTransport(nasa))))
    app = FastAPI()
    app.include_router(et.router)
    respuesta = TestClient(app).post("/evapotranspiracion", json={
        "lote_id": "lote-7", "poligono": POLIGONO, "desde": "2026-01-01", "hasta": "2026-01-08"})
    assert respuesta.status_code == 200
    assert [o["valor"] for o in respuesta.json()] == [3.2, 6.0]
    mal = TestClient(app).post("/evapotranspiracion", json={
        "lote_id": "lote-7", "poligono": POLIGONO, "desde": "2026-02-01", "hasta": "2026-01-08"})
    assert mal.status_code == 422
