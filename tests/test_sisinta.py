"""SISINTA (spec 048). Sin internet: la respuesta del WFS es REAL, guardada el 20/10/2026 (recuadro de ±25 km
alrededor del lote de prueba, 63 horizontes de 16 perfiles); los demás casos son SINTÉTICOS."""

import json
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rotaterra.fuentes import sisinta

MUESTRA = json.loads((Path(__file__).parent / "datos" / "sisinta_lote_de_prueba.geojson").read_text(encoding="utf-8"))


def cuadrado(lat, lon, lado=0.002):
    m = lado / 2
    return {"type": "Polygon", "coordinates": [[[lon - m, lat - m], [lon + m, lat - m], [lon + m, lat + m],
                                                [lon - m, lat + m], [lon - m, lat - m]]]}


LOTE_DE_PRUEBA = cuadrado(-33.700, -65.300)


def cliente_con(respuesta, pedidos=None):
    def manejar(request):
        if pedidos is not None:
            pedidos.append(request)
        return respuesta(request) if callable(respuesta) else httpx.Response(200, json=respuesta)
    return httpx.Client(transport=httpx.MockTransport(manejar))


def horizonte(id_perfil, lat, lon, sup, inf, ph, publico=1, fecha="1980-05-01Z", serie="Prueba"):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"id perfil": id_perfil, "s_publico": publico, "fecha": fecha, "nombre de serie": serie,
                           "profundiad sup.": sup, "profundiad inf.": inf, "ph h2o": ph}}


def por_variable(observaciones):
    return {o.variable: o for o in observaciones}


# ---------- con la respuesta real del INTA ----------

def test_lote_de_prueba_da_lo_mismo_que_el_informe_del_19_10():
    obs = por_variable(sisinta.obtener_ph_perfiles("lote-7", LOTE_DE_PRUEBA, cliente_con(MUESTRA)))
    arriba = obs["suelo_ph_perfiles_0_30cm"]
    assert (arriba.valor, arriba.resolucion_m, arriba.fuente, arriba.calidad, arriba.unidad) == \
        (7.88, 10000, "SISINTA", "dudosa", "pH")
    assert arriba.lote_id == "lote-7"
    assert "Mediana de 5 perfiles" in arriba.nota and "de 7.22 a 8.71" in arriba.nota
    assert "perfil 4902, serie Cramer, a 7.2 km" in arriba.nota
    assert "la última palabra la tiene el análisis de suelo del productor" in arriba.nota
    abajo = obs["suelo_ph_perfiles_30_100cm"]
    assert abajo.valor is not None and abajo.calidad == "dudosa"


def test_agrupa_horizontes_por_perfil_y_salta_perfiles_sin_ph():
    perfiles = sisinta.perfiles_de(MUESTRA)
    assert len(perfiles) == 14  # 16 perfiles en la muestra; 2 (por ejemplo el 4419 y el 4936) no traen ningún pH
    assert all(p.horizontes for p in perfiles)


def test_pide_wfs_1_0_0_con_bbox_lon_lat():
    pedidos = []
    sisinta.obtener_ph_perfiles("x", LOTE_DE_PRUEBA, cliente_con(MUESTRA, pedidos))
    params = pedidos[0].url.params
    assert params["version"] == "1.0.0" and params["typeName"] == "geonode:rehecho"
    oeste, sur, este, norte = map(float, params["bbox"].split(","))
    assert oeste < -65.3 < este and sur < -33.7 < norte  # orden lon,lat
    assert abs((norte - sur) / 2 - 25 / 111.32) < 1e-3


# ---------- casos sintéticos ----------

def test_promedio_pesado_por_espesor_y_mitad_del_tramo():
    perfil = sisinta.Perfil(1, 0, 0, None, "s", [(0, 10, 7.0), (10, 30, 8.0)])
    assert sisinta.ph_del_tramo(perfil, 0, 30) == pytest.approx((7.0 * 10 + 8.0 * 20) / 30)
    corto = sisinta.Perfil(2, 0, 0, None, "s", [(0, 14, 7.0)])
    assert sisinta.ph_del_tramo(corto, 0, 30) is None          # 14 de 30 cm: menos de la mitad
    justo = sisinta.Perfil(3, 0, 0, None, "s", [(0, 15, 7.0), (40, 60, 9.0)])
    assert sisinta.ph_del_tramo(justo, 0, 30) == 7.0             # 15 de 30 cm alcanza; el de 40-60 no entra


def test_sin_perfiles_a_10_km_usa_los_de_25():
    datos = {"features": [horizonte(1, -33.85, -65.30, "0", "30", "6.5")]}  # ~16,7 km al sur
    arriba = por_variable(sisinta.obtener_ph_perfiles("x", LOTE_DE_PRUEBA, cliente_con(datos)))["suelo_ph_perfiles_0_30cm"]
    assert (arriba.valor, arriba.resolucion_m) == (6.5, 25000)
    assert "Un solo perfil medido del INTA a 25 km o menos, 0-30 cm, año 1980" in arriba.nota


def test_sin_perfiles_no_inventa_nada():
    obs = sisinta.obtener_ph_perfiles("x", LOTE_DE_PRUEBA, cliente_con({"features": []}))
    assert len(obs) == 2
    assert all(o.valor is None and o.calidad == "descartada" for o in obs)
    assert "No hay perfiles medidos del INTA" in obs[0].nota


def test_ignora_na_ph_fuera_de_rango_sin_profundidad_y_perfiles_privados():
    datos = {"features": [
        horizonte(1, -33.70, -65.30, "0", "30", "NA"),
        horizonte(2, -33.70, -65.30, "0", "30", "0"),          # fuera de 3-11
        horizonte(3, -33.70, -65.30, "NA", "30", "7.0"),       # sin profundidad
        horizonte(4, -33.70, -65.30, "0", "30", "5.0", publico=0),
        horizonte(5, -33.70, -65.30, "0", "30", "7.4"),
    ]}
    arriba = por_variable(sisinta.obtener_ph_perfiles("x", LOTE_DE_PRUEBA, cliente_con(datos)))["suelo_ph_perfiles_0_30cm"]
    assert arriba.valor == 7.4 and "Un solo perfil" in arriba.nota


def test_fecha_es_la_del_perfil_mas_nuevo_usado():
    datos = {"features": [horizonte(1, -33.70, -65.30, "0", "30", "7.0", fecha="1979-01-02Z"),
                          horizonte(2, -33.71, -65.30, "0", "30", "8.0", fecha="2012-11-29Z")]}
    arriba = por_variable(sisinta.obtener_ph_perfiles("x", LOTE_DE_PRUEBA, cliente_con(datos)))["suelo_ph_perfiles_0_30cm"]
    assert str(arriba.fecha) == "2012-11-29" and arriba.valor == 7.5 and "años 1979-2012" in arriba.nota


@pytest.mark.parametrize("respuesta", [lambda r: httpx.Response(503, text="caído"),
                                       lambda r: httpx.Response(200, text="<html>no</html>"),
                                       lambda r: httpx.Response(200, json={"error": "x"})])
def test_wfs_caido_o_ilegible_es_error(respuesta):
    with pytest.raises(sisinta.ErrorSISINTA):
        sisinta.obtener_ph_perfiles("x", LOTE_DE_PRUEBA, cliente_con(respuesta))


# ---------- memoria (los perfiles no cambian) ----------

@pytest.fixture
def inta_simulado(monkeypatch):
    sisinta._memoria.clear()
    pedidos = []
    estado = {"respuesta": MUESTRA}

    def manejar(request):
        pedidos.append(request)
        r = estado["respuesta"]
        return r(request) if callable(r) else httpx.Response(200, json=r)

    original = httpx.Client

    def cliente(*args, **kwargs):
        return original(*args, transport=httpx.MockTransport(manejar), **kwargs)

    monkeypatch.setattr(sisinta.httpx, "Client", cliente)
    yield pedidos, estado
    sisinta._memoria.clear()


def test_el_segundo_pedido_del_mismo_lote_sale_de_la_memoria(inta_simulado):
    pedidos, _ = inta_simulado
    primero = sisinta.obtener_ph_perfiles("a", LOTE_DE_PRUEBA)
    segundo = sisinta.obtener_ph_perfiles("b", LOTE_DE_PRUEBA)
    assert len(pedidos) == 1
    assert [o.valor for o in primero] == [o.valor for o in segundo] and {o.lote_id for o in segundo} == {"b"}


def test_un_error_no_queda_en_memoria(inta_simulado):
    pedidos, estado = inta_simulado
    estado["respuesta"] = lambda r: httpx.Response(503)
    with pytest.raises(sisinta.ErrorSISINTA):
        sisinta.obtener_ph_perfiles("a", LOTE_DE_PRUEBA)
    estado["respuesta"] = MUESTRA
    assert sisinta.obtener_ph_perfiles("a", LOTE_DE_PRUEBA)[0].valor == 7.88
    assert len(pedidos) == 2


def test_la_memoria_vence_a_los_30_dias():
    sisinta._memoria.clear()
    llave = sisinta._llave(-33.7, -65.3)
    obs = sisinta.obtener_ph_perfiles("a", LOTE_DE_PRUEBA, cliente_con(MUESTRA))
    sisinta._a_la_memoria(llave, obs, ahora=0)
    assert sisinta._de_la_memoria(llave, "z", ahora=sisinta.DURACION_MEMORIA - 1) is not None
    assert sisinta._de_la_memoria(llave, "z", ahora=sisinta.DURACION_MEMORIA + 1) is None
    sisinta._memoria.clear()


# ---------- endpoint y registro ----------

def test_endpoint_de_prueba(inta_simulado):
    app = FastAPI()
    app.include_router(sisinta.router)
    with TestClient(app) as cliente:
        ok = cliente.post("/suelo/ph-perfiles", json={"poligono": LOTE_DE_PRUEBA})
        assert ok.status_code == 200 and ok.json()[0]["valor"] == 7.88
        assert cliente.post("/suelo/ph-perfiles", json={"poligono": {"type": "Point"}}).status_code == 422
        sisinta._memoria.clear()
        inta_simulado[1]["respuesta"] = lambda r: httpx.Response(500)
        assert cliente.post("/suelo/ph-perfiles", json={"poligono": LOTE_DE_PRUEBA}).status_code == 502


def test_se_anuncia_como_satelite_estatico_y_no_es_respaldo():
    (satelite,) = sisinta.SATELITES
    assert satelite.nombre == "SISINTA" and satelite.estatico and satelite.respaldo_de is None
