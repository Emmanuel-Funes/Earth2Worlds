"""Conector SEPA INTA y GOES-19 (spec 023), sin internet: lecturas de rasters y respuestas simuladas."""

from datetime import date, datetime, timezone

import httpx
import pytest

from rotaterra.fuentes import sepa_inta as s

LOTE = {"type": "Polygon", "coordinates": [[[-65.31, -33.71], [-65.29, -33.71], [-65.29, -33.69],
                                            [-65.31, -33.69], [-65.31, -33.71]]]}


# ---------- balance hídrico ----------

def test_decadas_terminan_el_10_el_20_y_fin_de_mes():
    assert [d[3] for d in s.decadas(date(2026, 2, 5), date(2026, 3, 10))] == [
        date(2026, 2, 10), date(2026, 2, 20), date(2026, 2, 28), date(2026, 3, 10)]


def test_url_agua_sigue_el_patron_de_geosepa():
    assert s.url_agua("ad", 2026, 9, 3) == (
        "https://sepa.inta.gob.ar/productos/geosepa/agua_en_suelo/ad/tif/ad_202609_3.tif")


def lector(valores_por_producto):
    def leer(url, poligono):
        codigo = url.rsplit("/", 1)[-1].split("_")[0]
        valor = valores_por_producto[codigo]
        if isinstance(valor, Exception):
            raise valor
        return valor, 500.0
    return leer


def test_agua_media_del_lote_con_unidad_fuente_y_cita():
    leer = lector({"ad": [120.0, 140.0], "ch": [80.0, 100.0], "db": [3.0, 3.0], "dr": [0.0], "pj": [60.0, 62.0]})
    obs = s.agua_del_lote("lote-7", LOTE, date(2026, 9, 21), date(2026, 9, 30), leer=leer)
    ad = next(o for o in obs if o.variable == "agua_disponible_2m")
    assert (ad.valor, ad.unidad, ad.fuente, ad.fecha, ad.calidad) == (130.0, "mm", "SEPA_INTA", date(2026, 9, 30),
                                                                      "buena")
    assert "CIRN-INTA" in ad.nota and "autorizado" in ad.nota
    assert next(o for o in obs if o.variable == "confort_hidrico_inta").unidad == "%"


def test_leer_lote_toma_todos_los_pixeles_que_toca(tmp_path):
    """Lote de ~550 m con píxeles de ~500 m, como el balance de SEPA: tiene que tocar 4 píxeles, no 1."""
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    ruta = tmp_path / "ad.tif"
    paso = 0.00449
    datos = np.arange(100, dtype="float32").reshape(10, 10)
    datos[0, 0] = np.nan
    with rasterio.open(ruta, "w", driver="GTiff", width=10, height=10, count=1, dtype="float32", crs="EPSG:4326",
                       transform=from_origin(-65.3125, -33.6925, paso, paso), nodata=np.nan) as ds:
        ds.write(datos, 1)
    valores, pixel_m = s.leer_lote(str(ruta), LOTE)
    assert len(valores) >= 4
    assert 480 < pixel_m < 520


def test_confort_sin_calculo_menos_99_no_entra_en_la_media():
    leer = lector({"ad": [1.0], "ch": [-99.0, 90.0, 100.0], "db": [3.0], "dr": [0.0], "pj": [50.0]})
    obs = s.agua_del_lote("lote-7", LOTE, date(2026, 9, 21), date(2026, 9, 30), leer=leer)
    ch = next(o for o in obs if o.variable == "confort_hidrico_inta")
    assert ch.valor == 95.0
    assert "20%" in ch.nota


def test_confort_todo_menos_99_queda_sin_valor():
    leer = lector({"ad": [1.0], "ch": [-99.0, -99.0], "db": [3.0], "dr": [0.0], "pj": [50.0]})
    obs = s.agua_del_lote("lote-7", LOTE, date(2026, 9, 21), date(2026, 9, 30), leer=leer)
    ch = next(o for o in obs if o.variable == "confort_hidrico_inta")
    assert ch.valor is None and ch.calidad == "descartada" and "cobertura verde" in ch.nota


def test_variacion_es_una_clase_con_su_leyenda():
    leer = lector({"ad": [1.0], "ch": [90.0], "db": [2.0, 3.0, 3.0, 3.0], "dr": [0.0], "pj": [50.0]})
    obs = s.agua_del_lote("lote-7", LOTE, date(2026, 9, 21), date(2026, 9, 30), leer=leer)
    db = next(o for o in obs if o.variable == "variacion_agua_disponible_clase")
    assert (db.valor, db.unidad, db.calidad) == (3.0, "clase", "buena")
    assert "aumento menor a 30 mm" in db.nota and "75%" in db.nota


def test_raster_que_no_responde_no_se_inventa():
    leer = lector({"ad": TimeoutError("lento"), "ch": [90.0], "db": [3.0], "dr": [0.0], "pj": [50.0]})
    obs = s.agua_del_lote("lote-7", LOTE, date(2026, 9, 21), date(2026, 9, 30), leer=leer)
    ad = next(o for o in obs if o.variable == "agua_disponible_2m")
    assert ad.valor is None and ad.calidad == "descartada" and "ad_202609_3" in ad.nota


def test_antes_de_mayo_2024_no_hay_balance():
    obs = s.agua_del_lote("lote-7", LOTE, date(2024, 1, 1), date(2024, 3, 31), leer=lector({}))
    assert len(obs) == 1
    assert obs[0].valor is None and "mayo de 2024" in obs[0].nota


# ---------- anomalías (solo el último período) ----------

def pagina_sepa(periodo="2026241"):
    html = (f'<a href="sc-{periodo}.tif">tif</a><a href="sc_{periodo}.gif">gif</a>'
            f'<a href="persistencia-{periodo}.tif">tif</a>')
    return httpx.Client(transport=httpx.MockTransport(lambda pedido: httpx.Response(200, text=html)))


def test_anomalia_lee_el_ultimo_geotiff_que_publica_la_pagina():
    leidos = []

    def leer(url, poligono):
        leidos.append(url)
        return [-12.0, -8.0], 250.0
    obs = s.anomalias_del_lote("lote-7", LOTE, date(2026, 9, 1), date(2026, 10, 4), pagina_sepa(), leer=leer)
    anomalia = next(o for o in obs if o.variable == "anomalia_historica_ndvi")
    assert anomalia.valor == -10.0 and anomalia.fecha == date(2026, 8, 29)  # el compuesto empieza antes y se cruza
    assert leidos[0].endswith("anomalia_16d_historica/sc-2026241.tif")


def test_anomalia_vieja_queda_sin_valor_y_dice_cual_es_la_ultima():
    obs = s.anomalias_del_lote("lote-7", LOTE, date(2025, 1, 1), date(2025, 2, 1), pagina_sepa(),
                               leer=lambda url, poligono: pytest.fail("no se lee un GeoTIFF fuera del rango"))
    assert all(o.valor is None and o.calidad == "descartada" for o in obs)
    assert "29/08/2026" in obs[0].nota and "sc_AAAADDD.gif" in obs[0].nota


# ---------- imágenes sin número ----------

def test_imagenes_van_con_la_url_en_la_nota_y_sin_valor():
    existentes = {"https://sepa.inta.gob.ar/productos/sepaproductos/et_10d/et_202609_1.gif"}
    cliente = httpx.Client(transport=httpx.MockTransport(
        lambda pedido: httpx.Response(200 if str(pedido.url) in existentes else 404)))
    obs = s.imagenes_del_lote("lote-7", date(2026, 9, 1), date(2026, 9, 10), cliente)
    et = [o for o in obs if o.variable == "etr_10d_inta"]
    assert len(et) == 1
    assert et[0].valor is None and et[0].calidad == "descartada" and "et_202609_1.gif" in et[0].nota
    assert not [o for o in obs if o.variable == "ndvi_10d_inta"]  # 404: no se ofrece una imagen que no existe


# ---------- Q de trigo con POWER ----------

def test_cociente_fototermal_formula_del_inta():
    assert s.cociente_fototermal(20.0, 14.5) == (2.0, "")
    valor, motivo = s.cociente_fototermal(20.0, 4.9)
    assert valor is None and "≤ 0.5" in motivo


def test_q_trigo_diario_y_por_decada():
    dias = {f"202609{d:02d}": d for d in range(1, 11)}
    cuerpo = {"properties": {"parameter": {
        "T2M": {k: 14.5 for k in dias} | {"20260905": 4.6},
        "ALLSKY_SFC_SW_DWN": {k: 20.0 for k in dias} | {"20260906": -999}}}}
    cliente = httpx.Client(transport=httpx.MockTransport(lambda pedido: httpx.Response(200, json=cuerpo)))
    obs = s.q_trigo("lote-7", -33.7, -65.3, date(2026, 9, 1), date(2026, 9, 10), cliente)
    diarios = {o.fecha.day: o for o in obs if o.variable == "cociente_fototermal_trigo"}
    assert diarios[1].valor == 2.0 and diarios[1].fuente == "POWER" and diarios[1].unidad == "MJ/m²/día/°C"
    assert diarios[5].valor is None and diarios[5].calidad == "descartada"   # Tmedia − Tb ≤ 0,5
    assert diarios[6].valor is None                                           # -999 de POWER: no se inventa
    decada = next(o for o in obs if o.variable == "cociente_fototermal_trigo_10d")
    assert decada.fecha == date(2026, 9, 10) and "9 días" in decada.nota


# ---------- GOES ----------

LISTA_S3 = """<ListBucketResult>
<Contents><Key>ABI-L2-LSTF/2026/276/08/OR_ABI-L2-LSTF-M6_G19_s20262760800205_e1.nc</Key></Contents>
<Contents><Key>ABI-L2-CMIPF/2026/277/21/OR_ABI-L2-CMIPF-M6C14_G19_s20262772120205_e1.nc</Key></Contents>
</ListBucketResult>"""


def s3_falso():
    pedidos = []

    def responder(pedido):
        pedidos.append(pedido)
        return httpx.Response(200, text=LISTA_S3)
    cliente = httpx.Client(transport=httpx.MockTransport(responder))
    cliente.pedidos = pedidos
    return cliente


def test_goes_19_desde_abril_2025_y_goes_16_antes():
    assert s.satelite_goes(date(2025, 4, 7)) == "GOES-19"
    assert s.satelite_goes(date(2025, 4, 6)) == "GOES-16"


def test_temperatura_nocturna_es_la_minima_y_avisa_helada():
    lecturas = iter([(272.15, 0), (271.15, 1), (275.0, 0), (None, None)])
    obs = s._temp_goes("lote-7", date(2026, 10, 3), "temp_superficie_nocturna", s.HORAS_NOCHE, min, -33.7, -65.3,
                       s3_falso(), lambda *a, **k: next(lecturas))
    assert obs.valor == -2.0 and obs.calidad == "buena" and obs.fuente == "GOES"
    assert "helada" in obs.nota and "no del aire" in obs.nota


def test_dqf_sin_calidad_se_descarta():
    obs = s._temp_goes("lote-7", date(2026, 10, 3), "temp_superficie_diurna", s.HORAS_DIA, max, -33.7, -65.3,
                       s3_falso(), lambda *a, **k: (300.0, 3))
    assert obs.valor is None and obs.calidad == "descartada" and "nubes" in obs.nota


def test_goes_del_lote_dos_valores_por_dia_y_nada_del_futuro():
    ahora = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
    obs = s.goes_del_lote("lote-7", -33.7, -65.3, date(2026, 9, 20), date(2026, 9, 22), s3_falso(),
                          leer=lambda *a, **k: (290.0, 0), ahora=ahora)
    assert len(obs) == 6
    assert {o.variable for o in obs} == {"temp_superficie_nocturna", "temp_superficie_diurna"}
    assert all(o.valor == 16.9 for o in obs)


def test_goes_corta_en_31_dias_y_lo_dice():
    ahora = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
    obs = s.goes_del_lote("lote-7", -33.7, -65.3, date(2026, 6, 1), date(2026, 9, 30), s3_falso(),
                          leer=lambda *a, **k: (290.0, 0), ahora=ahora)
    assert "31 días" in obs[0].nota
    assert min(o.fecha for o in obs[1:]) == date(2026, 8, 31)


def test_rayos_cuenta_solo_los_cercanos():
    destellos = ([-33.70, -33.75, -34.5], [-65.30, -65.32, -65.3])
    assert s.contar_rayos(["u", "v"], -33.7, -65.3, leer_vector=lambda url: destellos) == 4


def test_goes_ahora_trae_la_animacion_en_la_nota():
    ahora = datetime(2026, 10, 4, 21, 30, tzinfo=timezone.utc)
    obs = s.goes_ahora("lote-7", -33.7, -65.3, s3_falso(), lambda *a, **k: (250.0, 0), ahora,
                       leer_vector=lambda url: ([], []))
    animacion = next(o for o in obs if o.variable == "animacion_ir_goes")
    assert animacion.valor is None and "get-abi" in animacion.nota and "lat=-33.70" in animacion.nota
    ir = next(o for o in obs if o.variable == "infrarrojo_termico_goes")
    assert ir.valor == -23.1


# ---------- pedido y registro ----------

def test_rango_al_reves_o_muy_largo_se_rechaza():
    with pytest.raises(ValueError):
        s.validar_pedido(date(2026, 2, 1), date(2026, 1, 1))
    with pytest.raises(ValueError):
        s.validar_pedido(date(2024, 1, 1), date(2026, 1, 1))


def test_se_anuncia_como_dos_satelites():
    assert [x.nombre for x in s.SATELITES] == ["SEPA_INTA", "GOES"]
    assert all(x.respaldo_de is None for x in s.SATELITES)


def test_sepa_caido_avisa_rapido_y_el_q_sigue_con_power():
    def responder(pedido):
        if pedido.url.host == "sepa.inta.gob.ar":
            raise httpx.ConnectError("sin conexión")
        cuerpo = {"properties": {"parameter": {"T2M": {"20260913": 15.0}, "ALLSKY_SFC_SW_DWN": {"20260913": 21.0}}}}
        return httpx.Response(200, json=cuerpo)

    cliente = httpx.Client(transport=httpx.MockTransport(responder))
    poligono = {"type": "Polygon", "coordinates": [[[-65.3, -33.7], [-65.295, -33.7], [-65.295, -33.705],
                                                    [-65.3, -33.705], [-65.3, -33.7]]]}
    obs = s.obtener_sepa("lote-1", poligono, date(2026, 9, 13), date(2026, 9, 13), cliente)
    agua = [o for o in obs if o.fuente == "SEPA_INTA"]
    assert {o.variable for o in agua} == {p.variable for p in s.AGUA}
    assert all(o.valor is None and o.calidad == "descartada" and "ConnectError" in o.nota for o in agua)
    q = [o for o in obs if o.variable == "cociente_fototermal_trigo"]
    assert q and q[0].valor == pytest.approx(21.0 / (15.0 - 4.5), abs=0.001)


def test_en_la_consulta_sepa_caido_deja_pasar_al_respaldo(monkeypatch):
    # 16/10/2026: con SEPA caído la consulta devolvía solo el Q y el agua del suelo quedaba vacía
    monkeypatch.setattr(s, "sepa_caido", lambda cliente: "ConnectTimeout")
    monkeypatch.setattr(s, "q_trigo", lambda *a: [])
    lote = {"id": "lote-1", "poligono": {"type": "Polygon", "coordinates": [[[-65.3, -33.7], [-65.295, -33.7],
                                         [-65.295, -33.705], [-65.3, -33.705], [-65.3, -33.7]]]}}
    with pytest.raises(s.SEPACaido, match="ConnectTimeout"):
        s.SATELITES[0].pedir(lote, date(2026, 10, 1), date(2026, 10, 10))
