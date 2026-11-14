"""Consulta en el momento con respaldos, sin base de datos (spec 012)."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from rotaterra import api, consulta
from rotaterra.fuentes.registro import Conectados, Satelite
from tests.test_base_y_actualizar import POLIGONO, falso, obs

DESDE, HASTA = date(2026, 1, 1), date(2026, 1, 3)
LOTE = consulta.lote_para_consulta("lote-7", POLIGONO)


def ndvi(pedidos, hls_falla=True, viirs_falla=False, viirs_vacio=False):
    """HLS con dos respaldos: VIIRS primero y MODIS segundo (declarados al revés a propósito)."""
    return [falso("HLS", pedidos, falla=hls_falla, fuente="HLS"),
            falso("HLS:MODIS", pedidos, respaldo_de="HLS", fuente="MODIS", orden=2),
            falso("HLS:VIIRS", pedidos, respaldo_de="HLS", fuente="VIIRS", orden=1,
                  falla=viirs_falla, vacio=viirs_vacio)]


def test_el_lote_lleva_su_centro():
    assert LOTE["lat"] == pytest.approx(-33.7025) and LOTE["lon"] == pytest.approx(-65.2975)


def test_si_el_principal_responde_no_se_pide_ningun_respaldo():
    pedidos = []
    r = consulta.consultar(LOTE, "HLS", DESDE, HASTA, ndvi(pedidos, hls_falla=False))
    assert r.fuente_usada == "HLS" and len(r.observaciones) == 3
    assert [p[0] for p in pedidos] == ["HLS"]


def test_si_el_principal_falla_entra_el_primer_respaldo():
    pedidos = []
    r = consulta.consultar(LOTE, "HLS", DESDE, HASTA, ndvi(pedidos))
    assert r.fuente_usada == "HLS:VIIRS" and {o.fuente for o in r.observaciones} == {"VIIRS"}
    assert [(i.satelite, i.resultado) for i in r.intentos] == [("HLS", "error"), ("HLS:VIIRS", "ok")]
    assert [p[0] for p in pedidos] == ["HLS", "HLS:VIIRS"]  # MODIS ni se consulta


@pytest.mark.parametrize("como", ["falla", "vacio"])
def test_si_el_primer_respaldo_tampoco_trae_datos_entra_el_segundo(como):
    pedidos = []
    satelites = ndvi(pedidos, viirs_falla=como == "falla", viirs_vacio=como == "vacio")
    r = consulta.consultar(LOTE, "HLS", DESDE, HASTA, satelites)
    assert r.fuente_usada == "HLS:MODIS" and {o.fuente for o in r.observaciones} == {"MODIS"}
    assert [i.resultado for i in r.intentos] == ["error", "error" if como == "falla" else "sin_datos", "ok"]


def test_pendiente_deja_pasar_al_respaldo():
    pedidos = []
    satelites = [falso("SMAP", pedidos, pendiente=True),
                 falso("SMAP:AppEEARS", pedidos, respaldo_de="SMAP", fuente="SMAP")]
    r = consulta.consultar(LOTE, "SMAP", DESDE, HASTA, satelites)
    assert r.fuente_usada == "SMAP:AppEEARS" and r.intentos[0].resultado == "pendiente"


def test_si_nadie_trae_datos_no_se_inventa_nada():
    pedidos = []
    satelites = [falso("POWER", pedidos, falla=True),
                 falso("POWER:MERRA2", pedidos, respaldo_de="POWER", fuente="MERRA2", falla=True)]
    r = consulta.consultar(LOTE, "POWER", DESDE, HASTA, satelites)
    assert r.fuente_usada is None and r.observaciones == [] and len(r.intentos) == 2


# ---------- spec 041, parte B: un principal todo descartado deja pasar al respaldo ----------

def test_principal_todo_descartado_deja_pasar_al_respaldo():
    """Ej. HLS con todas las imágenes nubladas: antes la app recibía todo null; ahora contesta el respaldo."""
    pedidos = []
    satelites = [falso("HLS", pedidos, fuente="HLS", valor=None),
                 falso("HLS:VIIRS", pedidos, respaldo_de="HLS", fuente="VIIRS")]
    r = consulta.consultar(LOTE, "HLS", DESDE, HASTA, satelites)
    assert r.fuente_usada == "HLS:VIIRS" and {o.fuente for o in r.observaciones} == {"VIIRS"}
    assert [(i.satelite, i.resultado) for i in r.intentos] == [("HLS", "sin_datos"), ("HLS:VIIRS", "ok")]
    assert "descartadas" in r.intentos[0].mensaje and r.intentos[0].filas == 3


def test_con_algun_dato_util_el_principal_alcanza():
    pedidos = []

    def medio_nublado(lote, desde, hasta):
        pedidos.append(("HLS", desde, hasta))
        return [obs(desde, valor=None, fuente="HLS"), obs(hasta, valor=0.4, fuente="HLS")]

    satelites = [Satelite("HLS", medio_nublado), falso("HLS:VIIRS", pedidos, respaldo_de="HLS", fuente="VIIRS")]
    r = consulta.consultar(LOTE, "HLS", DESDE, HASTA, satelites)
    assert r.fuente_usada == "HLS" and [p[0] for p in pedidos] == ["HLS"]


def test_si_todos_vienen_descartados_vuelve_el_primero_con_sus_notas():
    """Nunca se inventa un valor ni se tira un 502 por esto: vuelven las descartadas del principal."""
    pedidos = []
    satelites = [falso("HLS", pedidos, fuente="HLS", valor=None),
                 falso("HLS:VIIRS", pedidos, respaldo_de="HLS", fuente="VIIRS", valor=None),
                 falso("HLS:MODIS", pedidos, respaldo_de="HLS", fuente="MODIS", orden=2, falla=True)]
    r = consulta.consultar(LOTE, "HLS", DESDE, HASTA, satelites)
    assert r.fuente_usada == "HLS" and {o.fuente for o in r.observaciones} == {"HLS"}
    assert all(o.valor is None and o.calidad == "descartada" for o in r.observaciones)
    assert [i.resultado for i in r.intentos] == ["sin_datos", "sin_datos", "error"]


def test_si_el_principal_falla_y_el_respaldo_viene_descartado_vuelve_el_respaldo():
    pedidos = []
    satelites = [falso("HLS", pedidos, falla=True),
                 falso("HLS:VIIRS", pedidos, respaldo_de="HLS", fuente="VIIRS", valor=None)]
    r = consulta.consultar(LOTE, "HLS", DESDE, HASTA, satelites)
    assert r.fuente_usada == "HLS:VIIRS" and all(o.valor is None for o in r.observaciones)


def test_api_principal_descartado_responde_200_con_el_respaldo(unidos):
    unidos += [falso("HLS", [], fuente="HLS", valor=None), falso("HLS:VIIRS", [], respaldo_de="HLS", fuente="VIIRS")]
    r = TestClient(api.app).post("/consulta", json=pedido())
    assert r.status_code == 200 and r.json()["fuente_usada"] == "HLS:VIIRS"


def test_un_respaldo_no_se_pide_como_principal():
    with pytest.raises(consulta.SateliteDesconocido):
        consulta.consultar(LOTE, "HLS:VIIRS", DESDE, HASTA, ndvi([]))


def test_rango_invalido():
    with pytest.raises(ValueError):
        consulta.consultar(LOTE, "HLS", HASTA, DESDE, ndvi([]))
    with pytest.raises(ValueError):
        consulta.consultar(LOTE, "HLS", date(2025, 1, 1), date(2026, 1, 3), ndvi([]))


# ---------- API: funciona sin base de datos ----------

@pytest.fixture
def unidos():
    satelites: list[Satelite] = []
    api.app.dependency_overrides[api.conectados] = lambda: Conectados(satelites=satelites)
    yield satelites
    api.app.dependency_overrides.clear()


def pedido(satelite="HLS"):
    return {"satelite": satelite, "lote_id": "lote-7", "poligono": POLIGONO,
            "desde": DESDE.isoformat(), "hasta": HASTA.isoformat()}


def test_api_lista_satelites_y_respaldos_en_orden(unidos):
    unidos += ndvi([]) + [falso("POWER", [])]
    assert TestClient(api.app).get("/satelites").json() == [
        {"satelite": "HLS", "respaldos": ["HLS:VIIRS", "HLS:MODIS"], "del_dia": []},
        {"satelite": "POWER", "respaldos": [], "del_dia": []}]


def test_api_responde_con_el_respaldo_y_lo_dice(unidos):
    unidos += ndvi([])
    r = TestClient(api.app).post("/consulta", json=pedido())
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["fuente_usada"] == "HLS:VIIRS" and {o["fuente"] for o in cuerpo["observaciones"]} == {"VIIRS"}
    assert cuerpo["intentos"][0]["resultado"] == "error" and "HLS caído" in cuerpo["intentos"][0]["mensaje"]


def test_api_no_exige_lote_id(unidos):
    """El lote es el polígono; lote_id es una etiqueta opcional (pedido del frontend, 5/10/2026)."""
    recibidos = []

    def pedir(lote, desde, hasta):
        recibidos.append(lote["id"])
        return []

    unidos += [Satelite("POWER", pedir)]
    sin_id = {k: v for k, v in pedido("POWER").items() if k != "lote_id"}
    TestClient(api.app).post("/consulta", json=sin_id)
    TestClient(api.app).post("/consulta", json=pedido("POWER"))
    assert recibidos == [api.LOTE_SIN_ID, "lote-7"]


def test_api_502_si_nadie_trae_datos(unidos):
    unidos += [falso("POWER", [], falla=True)]
    r = TestClient(api.app).post("/consulta", json=pedido("POWER"))
    assert r.status_code == 502 and r.json()["detail"]["intentos"][0]["resultado"] == "error"


def test_api_503_si_faltan_credenciales(unidos):
    class FaltanCredenciales(Exception):
        pass

    def sin_clave(lote, desde, hasta):
        raise FaltanCredenciales("Faltan EARTHDATA_USERNAME y EARTHDATA_PASSWORD")

    unidos += [Satelite("HLS", sin_clave)]
    assert TestClient(api.app).post("/consulta", json=pedido()).status_code == 503


def test_api_404_y_422(unidos):
    unidos += ndvi([])
    cliente = TestClient(api.app)
    assert cliente.post("/consulta", json=pedido("ECOSTRESS")).status_code == 404
    malo = pedido() | {"poligono": {"type": "Point", "coordinates": [0, 0]}}
    assert cliente.post("/consulta", json=malo).status_code == 422


# ---------- respaldos del día: completan la cola de días que la fuente todavía no publicó (spec 043) ----------

HOY = date(2026, 10, 15)
DESDE_COLA = date(2026, 10, 10)


def con_atraso(nombre, pedidos, ultimo, variables=("temp_max",), fuente="POWER", relleno=True, huecos=()):
    """Fuente que publica hasta `ultimo`; después manda -999 descartado (como POWER) o nada."""
    def pedir(lote, desde, hasta):
        pedidos.append((nombre, desde, hasta))
        filas = []
        for i in range((hasta - desde).days + 1):
            dia = desde + timedelta(days=i)
            for v in variables:
                ultimo_v = ultimo[v] if isinstance(ultimo, dict) else ultimo
                if dia <= ultimo_v and dia not in huecos:
                    filas.append(obs(dia, variable=v, valor=20.0, fuente=fuente))
                elif relleno:
                    filas.append(obs(dia, variable=v, valor=None, fuente=fuente))
        return filas
    return Satelite(nombre, pedir)


def del_dia(nombre, pedidos, respaldo_de="POWER", fuente="MERRA2", variables=("temp_max",), falla=False, orden=1,
            hasta_dia=None):
    def pedir(lote, desde, hasta):
        pedidos.append((nombre, desde, hasta))
        if falla:
            raise RuntimeError(f"{nombre} caído")
        ultimo = hasta_dia or hasta
        return [obs(desde + timedelta(days=i), variable=v, valor=30.0, fuente=fuente)
                for i in range((min(hasta, ultimo) - desde).days + 1) for v in variables]
    return Satelite(nombre, pedir, respaldo_de=respaldo_de, al_dia=True, orden=orden)


def test_el_respaldo_del_dia_completa_solo_los_dias_que_faltan():
    pedidos = []
    satelites = [con_atraso("POWER", pedidos, date(2026, 10, 12)), del_dia("POWER:GEOS_FP", pedidos)]
    r = consulta.consultar(LOTE, "POWER", DESDE_COLA, HOY, satelites)
    assert r.fuente_usada == "POWER" and r.completada_con == ["POWER:GEOS_FP"]
    assert [(o.fecha.day, o.fuente, o.valor) for o in r.observaciones] == [
        (10, "POWER", 20.0), (11, "POWER", 20.0), (12, "POWER", 20.0),
        (13, "MERRA2", 30.0), (14, "MERRA2", 30.0), (15, "MERRA2", 30.0)]  # los -999 de POWER se reemplazan
    assert pedidos[-1] == ("POWER:GEOS_FP", date(2026, 10, 13), HOY)  # solo se le pide la cola
    assert [(i.satelite, i.resultado, i.filas) for i in r.intentos] == [("POWER", "ok", 6),
                                                                        ("POWER:GEOS_FP", "completo", 3)]


def test_si_el_principal_tiene_todos_los_dias_no_se_llama_al_del_dia():
    pedidos = []
    satelites = [con_atraso("POWER", pedidos, HOY), del_dia("POWER:GEOS_FP", pedidos)]
    r = consulta.consultar(LOTE, "POWER", DESDE_COLA, HOY, satelites)
    assert [p[0] for p in pedidos] == ["POWER"] and r.completada_con == []


def test_un_hueco_en_el_medio_no_se_rellena():
    pedidos = []
    satelites = [con_atraso("HLS", pedidos, date(2026, 10, 14), variables=("ndvi",), fuente="HLS", relleno=False,
                            huecos=(date(2026, 10, 11), date(2026, 10, 12))),
                 del_dia("HLS:MODIS_NRT", pedidos, respaldo_de="HLS", fuente="MODIS", variables=("ndvi",))]
    r = consulta.consultar(LOTE, "HLS", DESDE_COLA, HOY, satelites)
    assert [(o.fecha.day, o.fuente) for o in r.observaciones] == [
        (10, "HLS"), (13, "HLS"), (14, "HLS"), (15, "MODIS")]


def test_cada_variable_tiene_su_propia_cola():
    """POWER publica la temperatura hasta el 12 y la radiación hasta el 9: cada una se completa desde su día."""
    pedidos = []
    ultimo = {"temp_max": date(2026, 10, 12), "radiacion": date(2026, 10, 9)}
    satelites = [con_atraso("POWER", pedidos, ultimo, variables=("temp_max", "radiacion")),
                 del_dia("POWER:GEOS_FP", pedidos, fuente="MERRA2", variables=("temp_max", "radiacion", "viento"))]
    r = consulta.consultar(LOTE, "POWER", date(2026, 10, 8), HOY, satelites)
    desde_goes = {v: min(o.fecha for o in r.observaciones if o.variable == v and o.fuente == "MERRA2")
                  for v in ("temp_max", "radiacion")}
    assert desde_goes == {"temp_max": date(2026, 10, 13), "radiacion": date(2026, 10, 10)}
    assert "viento" not in {o.variable for o in r.observaciones}  # solo las variables que trae el principal
    assert all(o.valor is not None for o in r.observaciones)
    assert pedidos[-1][1] == date(2026, 10, 10)


def test_si_el_del_dia_falla_queda_la_respuesta_de_siempre():
    pedidos = []
    satelites = [con_atraso("POWER", pedidos, date(2026, 10, 12)), del_dia("POWER:GEOS_FP", pedidos, falla=True)]
    r = consulta.consultar(LOTE, "POWER", DESDE_COLA, HOY, satelites)
    assert r.fuente_usada == "POWER" and r.completada_con == [] and len(r.observaciones) == 6
    assert r.intentos[-1].satelite == "POWER:GEOS_FP" and r.intentos[-1].resultado == "error"


def test_dos_respaldos_del_dia_en_orden():
    """El primero llega hasta ayer; el segundo pone solo lo que falta (hoy)."""
    pedidos = []
    satelites = [con_atraso("IMERG", pedidos, date(2026, 10, 12), variables=("lluvia_mm",), fuente="IMERG"),
                 del_dia("IMERG:GOES", pedidos, respaldo_de="IMERG", fuente="MERRA2", variables=("lluvia_mm",),
                         orden=2),
                 del_dia("IMERG:IMERG_EARLY", pedidos, respaldo_de="IMERG", fuente="IMERG", orden=1,
                         variables=("lluvia_mm",), hasta_dia=date(2026, 10, 14))]
    r = consulta.consultar(LOTE, "IMERG", DESDE_COLA, HOY, satelites)
    assert r.completada_con == ["IMERG:IMERG_EARLY", "IMERG:GOES"]
    assert pedidos[-1] == ("IMERG:GOES", HOY, HOY)
    assert [(o.fecha.day, o.fuente) for o in r.observaciones][-3:] == [(13, "IMERG"), (14, "IMERG"), (15, "MERRA2")]


def test_el_pedido_de_solo_hoy_lo_contesta_el_del_dia():
    """POWER no tiene hoy (todo -999) y su respaldo común tampoco: el del día trae el dato de hoy."""
    pedidos = []
    satelites = [con_atraso("POWER", pedidos, date(2026, 10, 12)),
                 Satelite("POWER:MERRA2", lambda lote, d, h: [], respaldo_de="POWER"),
                 del_dia("POWER:GEOS_FP", pedidos)]
    r = consulta.consultar(LOTE, "POWER", HOY, HOY, satelites)
    assert r.fuente_usada == "POWER" and r.completada_con == ["POWER:GEOS_FP"]
    assert [(o.fecha, o.fuente, o.valor) for o in r.observaciones] == [(HOY, "MERRA2", 30.0)]


def test_si_todos_fallan_el_del_dia_contesta_solo():
    pedidos = []
    satelites = [falso("POWER", pedidos, falla=True), del_dia("POWER:GEOS_FP", pedidos)]
    r = consulta.consultar(LOTE, "POWER", DESDE_COLA, HOY, satelites)
    assert r.fuente_usada == "POWER:GEOS_FP" and len(r.observaciones) == 6


def test_el_del_dia_no_entra_como_respaldo_comun():
    pedidos = []
    satelites = [falso("POWER", pedidos, falla=True), del_dia("POWER:GEOS_FP", pedidos),
                 falso("POWER:MERRA2", pedidos, respaldo_de="POWER", fuente="MERRA2")]
    r = consulta.consultar(LOTE, "POWER", DESDE_COLA, HOY, satelites)
    assert r.fuente_usada == "POWER:MERRA2" and r.completada_con == []
    assert [p[0] for p in pedidos] == ["POWER", "POWER:MERRA2"]


def test_api_dice_quien_completo_y_lista_los_del_dia(unidos):
    unidos += [con_atraso("POWER", [], date(2026, 10, 12)), del_dia("POWER:GEOS_FP", [])]
    cliente = TestClient(api.app)
    assert cliente.get("/satelites").json() == [{"satelite": "POWER", "respaldos": [], "del_dia": ["POWER:GEOS_FP"]}]
    cuerpo = pedido("POWER") | {"desde": DESDE_COLA.isoformat(), "hasta": HOY.isoformat()}
    r = cliente.post("/consulta", json=cuerpo).json()
    assert r["fuente_usada"] == "POWER" and r["completada_con"] == ["POWER:GEOS_FP"]
    assert r["intentos"][-1]["resultado"] == "completo"


# ---------- huecos largos: los rellena el respaldo siguiente, de más detalle a menos (spec 052) ----------

ENERO, FIN_ENERO = date(2026, 1, 1), date(2026, 1, 31)


def cada(nombre, pedidos, dias, fuente, respaldo_de=None, orden=1, variable="ndvi", valor=0.5, falla=False):
    """Satélite que solo tiene dato útil los días de `dias` (el resto, nada)."""
    def pedir(lote, desde, hasta):
        pedidos.append((nombre, desde, hasta))
        if falla:
            raise RuntimeError(f"{nombre} caído")
        return [obs(d, variable=variable, valor=valor, fuente=fuente) for d in sorted(dias) if desde <= d <= hasta]
    return Satelite(nombre, pedir, respaldo_de=respaldo_de, orden=orden)


def dias_de(*numeros):
    return {date(2026, 1, n) for n in numeros}


def test_huecos_cuenta_principio_medio_y_final():
    assert consulta.huecos(dias_de(8, 9, 20), ENERO, FIN_ENERO, 5) == [
        (date(2026, 1, 1), date(2026, 1, 7)), (date(2026, 1, 10), date(2026, 1, 19)),
        (date(2026, 1, 21), date(2026, 1, 31))]
    assert consulta.huecos(dias_de(*range(1, 32, 5)), ENERO, FIN_ENERO, 5) == []  # cada 5 días alcanza
    assert consulta.huecos(dias_de(*range(1, 32, 3)), ENERO, FIN_ENERO, consulta.HUECO_MAXIMO_DIAS["ndvi"]) == []


def test_hueco_largo_lo_rellena_el_de_mas_detalle_y_solo_ahi():
    pedidos = []
    hls = dias_de(1, 4, 7, 26, 29)              # nublado del 8 al 25
    s2 = dias_de(10, 15, 27)                    # el 27 HLS ya tiene cerca: no hace falta
    diario = set(dias_de(*range(1, 32)))        # pasa todos los días
    satelites = [cada("HLS", pedidos, hls, "HLS"),
                 cada("HLS:DIARIO", pedidos, diario, "MODIS", "HLS", orden=2),
                 cada("HLS:SENTINEL2", pedidos, s2, "SENTINEL2", "HLS", orden=1)]
    r = consulta.consultar(LOTE, "HLS", ENERO, FIN_ENERO, satelites)
    assert r.fuente_usada == "HLS" and r.rellenada_con == ["HLS:SENTINEL2", "HLS:DIARIO"]
    por_dia = {o.fecha.day: o.fuente for o in r.observaciones}
    assert [d for d, f in por_dia.items() if f == "SENTINEL2"] == [10, 15]
    # después de Sentinel-2 quedan el 11-14 y el 16-25 (más de 2 días): el diario los rellena; el 8-9 queda (2 días)
    assert sorted(d for d, f in por_dia.items() if f == "MODIS") == list(range(11, 15)) + list(range(16, 26))
    assert [d for d, f in por_dia.items() if f == "HLS"] == [1, 4, 7, 26, 29]
    # a cada respaldo se le pide todo el período, para compararlo con HLS (spec 056)
    assert pedidos[1] == ("HLS:SENTINEL2", ENERO, FIN_ENERO) and pedidos[2] == ("HLS:DIARIO", ENERO, FIN_ENERO)
    assert [(i.satelite, i.resultado) for i in r.intentos] == [("HLS", "ok"), ("HLS:SENTINEL2", "relleno"),
                                                              ("HLS:DIARIO", "relleno")]


def test_sin_huecos_largos_no_se_pide_ningun_respaldo():
    pedidos = []
    satelites = [cada("HLS", pedidos, dias_de(*range(1, 32, 3)), "HLS"),
                 cada("HLS:SENTINEL2", pedidos, dias_de(2), "SENTINEL2", "HLS")]
    r = consulta.consultar(LOTE, "HLS", ENERO, FIN_ENERO, satelites)
    assert [p[0] for p in pedidos] == ["HLS"] and r.rellenada_con == []


def test_variable_sin_regla_de_huecos_no_se_rellena():
    pedidos = []
    satelites = [cada("POWER", pedidos, dias_de(1), "POWER", variable="temp_max"),
                 cada("POWER:MERRA2", pedidos, dias_de(*range(1, 32)), "MERRA2", "POWER", variable="temp_max")]
    r = consulta.consultar(LOTE, "POWER", ENERO, FIN_ENERO, satelites)
    assert [p[0] for p in pedidos] == ["POWER"] and len(r.observaciones) == 1


def test_respaldo_caido_deja_el_hueco_para_el_siguiente():
    pedidos = []
    satelites = [cada("HLS", pedidos, dias_de(1, 31), "HLS"),
                 cada("HLS:SENTINEL2", pedidos, set(), "SENTINEL2", "HLS", orden=1, falla=True),
                 cada("HLS:VIIRS", pedidos, dias_de(9, 17, 25), "VIIRS", "HLS", orden=2)]
    r = consulta.consultar(LOTE, "HLS", ENERO, FIN_ENERO, satelites)
    assert r.rellenada_con == ["HLS:VIIRS"]
    assert [(o.fecha.day, o.fuente) for o in r.observaciones] == [(1, "HLS"), (9, "VIIRS"), (17, "VIIRS"),
                                                                 (25, "VIIRS"), (31, "HLS")]
    assert ("HLS:SENTINEL2", "error") in [(i.satelite, i.resultado) for i in r.intentos]


def test_si_contesto_un_respaldo_rellenan_solo_los_que_vienen_despues():
    pedidos = []
    satelites = [cada("HLS", pedidos, set(), "HLS"),
                 cada("HLS:SENTINEL2", pedidos, dias_de(1, 31), "SENTINEL2", "HLS", orden=1),
                 cada("HLS:DIARIO", pedidos, dias_de(*range(1, 32)), "MODIS", "HLS", orden=2)]
    r = consulta.consultar(LOTE, "HLS", ENERO, FIN_ENERO, satelites)
    assert r.fuente_usada == "HLS:SENTINEL2" and r.rellenada_con == ["HLS:DIARIO"]
    assert [p[0] for p in pedidos] == ["HLS", "HLS:SENTINEL2", "HLS:DIARIO"]


def test_api_dice_quien_relleno(unidos):
    pedidos = []
    unidos += [cada("HLS", pedidos, dias_de(1, 31), "HLS"),
               cada("HLS:DIARIO", pedidos, dias_de(*range(1, 32)), "MODIS", "HLS")]
    respuesta = TestClient(api.app).post("/consulta", json={
        "lote_id": "lote-7", "poligono": POLIGONO, "satelite": "HLS", "desde": "2026-01-01", "hasta": "2026-01-31"})
    assert respuesta.status_code == 200
    assert respuesta.json()["rellenada_con"] == ["HLS:DIARIO"] and len(respuesta.json()["observaciones"]) == 31


# ---------- ajuste por lote del satélite que rellena (spec 056) ----------

def test_pares_toma_el_hls_mas_cercano_a_un_dia():
    hls = [obs(date(2026, 1, d), variable="ndvi", valor=v, fuente="HLS") for d, v in [(1, 0.30), (4, 0.36)]]
    otras = [obs(date(2026, 1, d), variable="ndvi", valor=v, fuente="VIIRS") for d, v in [(2, 0.40), (5, 0.50), (9, 0.9)]]
    assert [(f.day, round(x, 3)) for f, x in consulta.pares(hls, otras, "ndvi")] == [(2, 0.10), (5, 0.14)]


def test_corrimiento_usa_la_ventana_y_la_mediana():
    # +0,10 a principio de mes, 0 a fin de mes (como Sentinel-3 en enero de 2026); un par raro de +0,30
    todos = [(date(2026, 1, d), x) for d, x in [(1, 0.10), (2, 0.10), (3, 0.30), (4, 0.10), (5, 0.10),
                                                  (25, 0.0), (26, 0.0), (27, 0.0), (28, 0.0), (29, 0.0)]]
    assert consulta.corrimiento(todos, date(2026, 1, 3))[:2] == (pytest.approx(0.10), 5)
    assert consulta.corrimiento(todos, date(2026, 1, 27))[:2] == (0.0, 5)
    # el 15 no tiene 5 pares a ±10 días: se usa todo el período
    assert consulta.corrimiento(todos, date(2026, 1, 15)) == (pytest.approx(0.05), 10, "del período")


def test_con_pocos_pares_no_hay_corrimiento():
    assert consulta.corrimiento([(date(2026, 1, 2), 0.1)], date(2026, 1, 2)) == (None, 1, "")


def test_ajustar_descuenta_y_deja_el_original_en_la_nota():
    todos = [(date(2026, 1, d), 0.1) for d in range(5, 12)]
    o = consulta.ajustar(obs(date(2026, 1, 10), variable="ndvi", valor=0.572, fuente="VIIRS"), todos, "HLS")
    assert o.valor == 0.472 and o.calidad == "buena" and "ajustado al lote: -0.100" in o.nota
    assert "valor original 0.572" in o.nota and "7 pares a ±10 días con HLS" in o.nota
    sin = consulta.ajustar(obs(date(2026, 1, 10), variable="ndvi", valor=0.572, fuente="VIIRS"), todos[:2], "HLS")
    assert sin.valor == 0.572 and sin.calidad == "dudosa" and "sin ajuste al lote" in sin.nota


def test_el_relleno_viene_ajustado_al_lote():
    pedidos = []
    hls = dias_de(1, 2, 3, 4, 5, 6, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31)  # nublado del 7 al 19
    satelites = [cada("HLS", pedidos, hls, "HLS", valor=0.40),
                 cada("HLS:DIARIO", pedidos, dias_de(*range(1, 32)), "MODIS", "HLS", valor=0.55)]
    r = consulta.consultar(LOTE, "HLS", ENERO, FIN_ENERO, satelites)
    rellenos = [o for o in r.observaciones if o.fuente == "MODIS"]
    assert [o.fecha.day for o in rellenos] == list(range(7, 20))
    assert all(o.valor == 0.40 and o.calidad == "buena" and "valor original 0.55" in o.nota for o in rellenos)
