import os
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from rotaterra import actualizar, api, base
from rotaterra.contrato import Observacion
from rotaterra.fuentes import registro
from rotaterra.fuentes.registro import Conectados, Satelite
from rotaterra.geo import poligono_desde_esquinas

POLIGONO = poligono_desde_esquinas("-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300")
HOY = date(2026, 3, 1)


@pytest.fixture
def motor(tmp_path):
    """SQLite por defecto; PostgreSQL si TEST_DATABASE_URL está definida (lo hace CI)."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        return base.conectar(f"sqlite:///{tmp_path}/prueba.db")
    motor = base.conectar(url)
    base.metadata.drop_all(motor)
    base.metadata.create_all(motor)
    return motor


@pytest.fixture
def lote(motor):
    return base.guardar_lote(motor, "lote-7", "Lote 7", POLIGONO)


def obs(fecha, variable="temp_max", valor=25.0, fuente="POWER"):
    return Observacion(lote_id="lote-7", fecha=fecha, variable=variable, valor=valor, unidad="°C",
                       fuente=fuente, resolucion_m=55000, calidad="buena" if valor is not None else "descartada")


def falso(nombre, pedidos, falla=False, pendiente=False, respaldo_de=None, fuente=None, variable="temp_max",
          valor=25.0, estatico=False, orden=1, vacio=False):
    """Satélite de mentira: un dato por día pedido, guardado con su fuente; anota cada pedido."""
    def pedir(lote, desde, hasta):
        pedidos.append((nombre, desde, hasta))
        if falla:
            raise RuntimeError(f"{nombre} caído")
        if pendiente:
            raise registro.Pendiente("sigue en la fila")
        if vacio:
            return []
        return [obs(desde + timedelta(days=i), variable=variable, valor=valor, fuente=fuente or nombre)
                for i in range((hasta - desde).days + 1)]
    return Satelite(nombre, pedir, respaldo_de=respaldo_de, estatico=estatico, orden=orden)


# ---------- base ----------

def test_lote_calcula_su_centro(lote):
    assert lote["lat"] == pytest.approx(-33.7025) and lote["lon"] == pytest.approx(-65.2975)


def test_guardar_dos_veces_no_duplica_y_reemplaza(motor, lote):
    base.guardar_observaciones(motor, [obs(date(2026, 1, 1), valor=20.0)])
    base.guardar_observaciones(motor, [obs(date(2026, 1, 1), valor=21.5)])
    guardadas = base.leer_observaciones(motor, "lote-7")
    assert len(guardadas) == 1 and guardadas[0].valor == 21.5


def test_misma_fecha_y_variable_de_otra_fuente_convive(motor, lote):
    base.guardar_observaciones(motor, [obs(date(2026, 1, 1)), obs(date(2026, 1, 1), fuente="productor")])
    assert len(base.leer_observaciones(motor, "lote-7")) == 2


def test_filtros_de_lectura(motor, lote):
    base.guardar_observaciones(motor, [obs(date(2026, 1, d)) for d in range(1, 11)] +
                               [obs(date(2026, 1, 5), variable="lluvia_mm", valor=3.0)])
    assert len(base.leer_observaciones(motor, "lote-7", variable="lluvia_mm")) == 1
    assert len(base.leer_observaciones(motor, "lote-7", desde=date(2026, 1, 8))) == 3


def test_ultima_fecha_ignora_valores_descartados(motor, lote):
    base.guardar_observaciones(motor, [obs(date(2026, 1, 1)), obs(date(2026, 1, 9), valor=None)])
    assert base.ultima_fecha(motor, "lote-7", "POWER") == date(2026, 1, 1)


# ---------- actualización ----------

def test_primera_vez_pide_historial_completo(motor, lote):
    pedidos = []
    actualizar.actualizar_lote(motor, lote, HOY, satelites=[falso("POWER", pedidos)])
    assert pedidos == [("POWER", HOY - timedelta(days=365), HOY - timedelta(days=1))]


def test_segunda_vez_pide_solo_lo_nuevo_con_solape(motor, lote):
    pedidos = []
    power = [falso("POWER", pedidos)]
    actualizar.actualizar_lote(motor, lote, HOY, satelites=power)
    actualizar.actualizar_lote(motor, lote, HOY + timedelta(days=3), satelites=power)
    _, desde, hasta = pedidos[-1]
    assert desde == HOY - timedelta(days=5)  # última guardada (ayer) menos 4: 5 días de solape
    assert hasta == HOY + timedelta(days=2)
    assert len(base.leer_observaciones(motor, "lote-7")) == 365 + 3  # sin duplicados


def test_misma_noche_repite_solo_el_solape(motor, lote):
    pedidos = []
    power = [falso("POWER", pedidos)]
    actualizar.actualizar_lote(motor, lote, HOY, satelites=power)
    r = actualizar.actualizar_lote(motor, lote, HOY, satelites=power)
    assert r[0].resultado == "ok"  # repite el solape: toma correcciones de los últimos días
    assert pedidos[-1][1] == HOY - timedelta(days=5)


def test_un_satelite_caido_no_frena_a_los_demas(motor, lote):
    pedidos = []
    satelites = [falso("POWER", pedidos), falso("HLS", pedidos, falla=True),
                 falso("HLS:MODIS", pedidos, respaldo_de="HLS", fuente="MODIS"), falso("SMAP", pedidos)]
    resultados = actualizar.actualizar_lote(motor, lote, HOY, satelites=satelites)
    assert {r.fuente: r.resultado for r in resultados} == {"POWER": "ok", "HLS": "error", "HLS:MODIS": "ok", "SMAP": "ok"}
    assert {o.fuente for o in base.leer_observaciones(motor, "lote-7")} == {"POWER", "MODIS", "SMAP"}
    estado = {e["fuente"]: e for e in base.estado(motor, "lote-7")}
    assert estado["HLS"]["resultado"] == "error" and "HLS caído" in estado["HLS"]["mensaje"]


def test_pendiente_no_es_error(motor, lote):
    pedidos = []
    resultados = actualizar.actualizar_lote(motor, lote, HOY, satelites=[
        falso("SMAP", pedidos, falla=True),
        falso("SMAP:AppEEARS", pedidos, respaldo_de="SMAP", fuente="SMAP", pendiente=True)])
    assert [(r.fuente, r.resultado) for r in resultados] == [("SMAP", "error"), ("SMAP:AppEEARS", "pendiente")]


def test_satelite_fijo_se_pide_una_sola_vez(motor, lote):
    pedidos = []
    nasadem = [falso("NASADEM", pedidos, estatico=True)]
    actualizar.actualizar_lote(motor, lote, HOY, satelites=nasadem)
    (r,) = actualizar.actualizar_lote(motor, lote, HOY + timedelta(days=1), satelites=nasadem)
    assert r.resultado == "al_dia" and len(pedidos) == 1


def test_main_sin_satelites_no_hace_nada(monkeypatch, capsys):
    monkeypatch.setattr(registro, "descubrir", lambda: Conectados())
    assert actualizar.main() == 0
    assert "No hay satélites" in capsys.readouterr().out


def test_main_sin_base_configurada_no_hace_nada(monkeypatch, capsys):
    monkeypatch.setattr(registro, "descubrir", lambda: Conectados(satelites=[falso("POWER", [])]))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert actualizar.main() == 0
    salida = capsys.readouterr().out
    assert "Satélites conectados: POWER" in salida and "DATABASE_URL" in salida


# ---------- API: lee lo guardado, sin llamar a la NASA ----------

@pytest.fixture
def cliente(motor, monkeypatch):
    api.app.dependency_overrides[api.motor] = lambda: motor
    yield TestClient(api.app)
    api.app.dependency_overrides.clear()


def test_api_alta_y_lectura_de_lote(cliente, motor):
    r = cliente.post("/lotes", json={"id": "lote-7", "nombre": "Lote 7", "poligono": POLIGONO})
    assert r.status_code == 201 and r.json()["lat"] == pytest.approx(-33.7025)
    base.guardar_observaciones(motor, [obs(date(2026, 1, d)) for d in range(1, 4)])
    r = cliente.get("/lotes/lote-7/observaciones", params={"desde": "2026-01-02"})
    assert r.status_code == 200 and [o["fecha"] for o in r.json()] == ["2026-01-02", "2026-01-03"]
    assert [l["id"] for l in cliente.get("/lotes").json()] == ["lote-7"]


def test_api_estado_del_lote(cliente, motor, lote):
    actualizar.actualizar_lote(motor, lote, HOY, satelites=[falso("POWER", [])])
    (estado,) = cliente.get("/lotes/lote-7/estado").json()
    assert estado["resultado"] == "ok" and estado["ultima_fecha_con_dato"] == str(HOY - timedelta(days=1))


def test_api_lote_inexistente_404(cliente):
    assert cliente.get("/lotes/no-existe/observaciones").status_code == 404


def test_api_poligono_invalido_422(cliente):
    r = cliente.post("/lotes", json={"id": "x", "nombre": "x", "poligono": {"type": "Point", "coordinates": [0, 0]}})
    assert r.status_code == 422



# ---------- respaldos NASA (spec 005) ----------

def principal_caido_y_respaldo(nombre, respaldo, fuente_respaldo, **kwargs):
    pedidos = []
    return pedidos, [falso(nombre, pedidos, falla=True),
                     falso(respaldo, pedidos, respaldo_de=nombre, fuente=fuente_respaldo, **kwargs)]


def test_principal_caido_entra_su_respaldo_por_el_mismo_periodo(motor, lote):
    pedidos, satelites = principal_caido_y_respaldo("SMAP", "SMAP:AppEEARS", "SMAP")
    resultados = actualizar.actualizar_lote(motor, lote, HOY, satelites=satelites)
    assert [(r.fuente, r.resultado) for r in resultados] == [("SMAP", "error"), ("SMAP:AppEEARS", "ok")]
    assert pedidos[1] == ("SMAP:AppEEARS", HOY - timedelta(days=365), HOY - timedelta(days=1))
    assert {o.fuente for o in base.leer_observaciones(motor, "lote-7")} == {"SMAP"}


def test_estado_del_respaldo_muestra_su_ultima_fecha(motor, lote):
    _, satelites = principal_caido_y_respaldo("SMAP", "SMAP:AppEEARS", "SMAP")
    actualizar.actualizar_lote(motor, lote, HOY, satelites=satelites)
    estado = {e["fuente"]: e for e in base.estado(motor, "lote-7")}
    assert estado["SMAP:AppEEARS"]["ultima_fecha_con_dato"] == HOY - timedelta(days=1)


def test_principal_ok_no_usa_respaldo(motor, lote):
    pedidos = []
    actualizar.actualizar_lote(motor, lote, HOY, satelites=[
        falso("POWER", pedidos), falso("POWER:MERRA2", pedidos, respaldo_de="POWER", fuente="MERRA2")])
    assert [p[0] for p in pedidos] == ["POWER"]


def test_respaldo_sin_su_principal_no_corre(motor, lote):
    pedidos = []
    resultados = actualizar.actualizar_lote(motor, lote, HOY, satelites=[
        falso("POWER:MERRA2", pedidos, respaldo_de="POWER", fuente="MERRA2")])
    assert resultados == [] and pedidos == []  # queda en espera hasta que se una POWER


def test_satelite_sin_respaldo_no_lo_pide(motor, lote):
    pedidos = []
    actualizar.actualizar_lote(motor, lote, HOY, satelites=[
        falso("IMERG", pedidos, falla=True), falso("HLS:MODIS", pedidos, respaldo_de="HLS", fuente="MODIS")])
    assert [p[0] for p in pedidos] == ["IMERG"]


def test_varios_respaldos_entran_en_orden_hasta_que_uno_cubre(motor, lote):
    pedidos = []
    actualizar.actualizar_lote(motor, lote, HOY, satelites=[
        falso("HLS:MODIS", pedidos, respaldo_de="HLS", fuente="MODIS", orden=2),
        falso("HLS", pedidos, falla=True),
        falso("HLS:VIIRS", pedidos, respaldo_de="HLS", fuente="VIIRS", orden=1)])
    assert [p[0] for p in pedidos] == ["HLS", "HLS:VIIRS"]  # VIIRS cubrió: MODIS no se pide


def test_si_el_primer_respaldo_falla_o_no_trae_datos_entra_el_siguiente(motor, lote):
    for primero in (dict(falla=True), dict(vacio=True)):
        pedidos = []
        resultados = actualizar.actualizar_lote(motor, lote, HOY, satelites=[
            falso("HLS", pedidos, falla=True),
            falso("HLS:VIIRS", pedidos, respaldo_de="HLS", fuente="VIIRS", orden=1, **primero),
            falso("HLS:MODIS", pedidos, respaldo_de="HLS", fuente="MODIS", orden=2)])
        assert [p[0] for p in pedidos] == ["HLS", "HLS:VIIRS", "HLS:MODIS"]
        assert resultados[-1].fuente == "HLS:MODIS" and resultados[-1].resultado == "ok"


def test_combinar_prefiere_viirs_sobre_modis(motor, lote):
    base.guardar_observaciones(motor, [obs(date(2026, 1, 1), variable="ndvi", valor=0.5, fuente="MODIS"),
                                       obs(date(2026, 1, 1), variable="ndvi", valor=0.6, fuente="VIIRS")])
    assert [o.fuente for o in base.combinar_fuentes(base.leer_observaciones(motor, "lote-7"))] == ["VIIRS"]


def test_combinar_prefiere_modis_sobre_ecostress_para_la_et(motor, lote):
    base.guardar_observaciones(motor, [
        obs(date(2026, 1, 1), variable="et_mm_dia", valor=1.3, fuente="MODIS"),
        obs(date(2026, 1, 1), variable="et_mm_dia", valor=2.9, fuente="ECOSTRESS"),
        obs(date(2026, 1, 1), variable="et_mm_dia", valor=3.0, fuente="productor"),
        obs(date(2026, 1, 2), variable="et_mm_dia", valor=1.4, fuente="MODIS"),
        obs(date(2026, 1, 2), variable="et_mm_dia", valor=2.0, fuente="ECOSTRESS"),
        obs(date(2026, 1, 3), variable="et_mm_dia", valor=2.5, fuente="ECOSTRESS"),  # MODIS sin dato: va ECOSTRESS
    ])
    combinadas = base.combinar_fuentes(base.leer_observaciones(motor, "lote-7"))
    assert [(o.fecha.day, o.fuente) for o in combinadas] == [(1, "productor"), (2, "MODIS"), (3, "ECOSTRESS")]


def test_respaldo_caido_queda_registrado(motor, lote):
    _, satelites = principal_caido_y_respaldo("SMAP", "SMAP:AppEEARS", "SMAP", falla=True)
    resultados = actualizar.actualizar_lote(motor, lote, HOY, satelites=satelites)
    assert resultados[-1].resultado == "error" and "SMAP:AppEEARS caído" in resultados[-1].mensaje


def test_main_no_marca_error_si_el_respaldo_cubrio(monkeypatch, motor, lote):
    _, satelites = principal_caido_y_respaldo("POWER", "POWER:MERRA2", "MERRA2")
    monkeypatch.setattr(registro, "descubrir", lambda: Conectados(satelites=satelites))
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setattr(actualizar.base, "conectar", lambda: motor)
    assert actualizar.main() == 0


def test_main_marca_error_si_nadie_cubrio(monkeypatch, motor, lote):
    pedidos = []
    monkeypatch.setattr(registro, "descubrir", lambda: Conectados(satelites=[falso("IMERG", pedidos, falla=True)]))
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setattr(actualizar.base, "conectar", lambda: motor)
    assert actualizar.main() == 1


def test_combinar_prefiere_principal_y_rellena_con_respaldo(motor, lote):
    base.guardar_observaciones(motor, [
        obs(date(2026, 1, 1), valor=25.0, fuente="POWER"),
        obs(date(2026, 1, 1), valor=24.0, fuente="MERRA2"),
        obs(date(2026, 1, 2), valor=None, fuente="POWER"),   # POWER sin dato ese día
        obs(date(2026, 1, 2), valor=23.0, fuente="MERRA2"),
        obs(date(2026, 1, 3), valor=22.0, fuente="MERRA2"),
    ])
    combinadas = base.combinar_fuentes(base.leer_observaciones(motor, "lote-7"))
    assert [(o.fecha.day, o.fuente, o.valor) for o in combinadas] == [
        (1, "POWER", 25.0), (2, "MERRA2", 23.0), (3, "MERRA2", 22.0)]


def test_combinar_prefiere_imerg_para_la_lluvia(motor, lote):
    base.guardar_observaciones(motor, [
        obs(date(2026, 1, 1), variable="lluvia_mm", valor=5.0, fuente="POWER"),
        obs(date(2026, 1, 1), variable="lluvia_mm", valor=8.7, fuente="IMERG"),
        obs(date(2026, 1, 2), variable="lluvia_mm", valor=3.0, fuente="POWER"),
        obs(date(2026, 1, 2), variable="lluvia_mm", valor=None, fuente="IMERG"),  # IMERG sin dato: va POWER
        obs(date(2026, 1, 1), variable="temp_max", valor=30.0, fuente="POWER"),
    ])
    combinadas = base.combinar_fuentes(base.leer_observaciones(motor, "lote-7"))
    assert [(o.fecha.day, o.variable, o.fuente) for o in combinadas] == [
        (1, "lluvia_mm", "IMERG"), (1, "temp_max", "POWER"), (2, "lluvia_mm", "POWER")]


def test_api_combinar(cliente, motor):
    base.guardar_lote(motor, "lote-7", "Lote 7", POLIGONO)
    base.guardar_observaciones(motor, [obs(date(2026, 1, 1), fuente="POWER"),
                                       obs(date(2026, 1, 1), valor=1.0, fuente="MERRA2")])
    assert len(cliente.get("/lotes/lote-7/observaciones").json()) == 2
    (unica,) = cliente.get("/lotes/lote-7/observaciones", params={"combinar": "true"}).json()
    assert unica["fuente"] == "POWER"
