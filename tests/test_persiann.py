"""Tercer respaldo de la lluvia de IMERG con NOAA PERSIANN-CDR (spec 038). Sin internet: índice y NetCDF simulados."""

import os
from datetime import date

import httpx
import pytest

from rotaterra import actualizar, base
from rotaterra.contrato import Observacion
from rotaterra.fuentes import persiann
from rotaterra.fuentes.registro import Satelite
from rotaterra.geo import poligono_desde_esquinas

POLIGONO = poligono_desde_esquinas("-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300")
DESDE, HASTA = date(2026, 1, 12), date(2026, 1, 15)

# nombre del archivo de cada día (como lo publica NCEI) y lo que leería el píxel del lote:
# el 14/1 es relleno (píxel sin dato) y el 15/1 no está en el índice (día que PERSIANN todavía no publicó).
NOMBRES = {date(2026, 1, 12): "PERSIANN-CDR_v01r01_20260112_c20260115.nc",
           date(2026, 1, 13): "PERSIANN-CDR_v01r01_20260113_c20260116.nc",
           date(2026, 1, 14): "PERSIANN-CDR_v01r01_20260114_c20260117.nc"}
LECTURA = {"PERSIANN-CDR_v01r01_20260112_c20260115.nc": 0.0,
           "PERSIANN-CDR_v01r01_20260113_c20260116.nc": 25.3,
           "PERSIANN-CDR_v01r01_20260114_c20260117.nc": None}


def pedir(monkeypatch, nombres=NOMBRES, lectura=LECTURA, desde=DESDE, hasta=HASTA):
    """obtener_lluvia con el índice anual y la lectura del píxel reemplazados por datos fijos."""
    monkeypatch.setattr(persiann, "listado_anual", lambda cliente, anio: {d: n for d, n in nombres.items() if d.year == anio})
    monkeypatch.setattr(persiann, "bajar_dia", lambda cliente, anio, nombre: nombre)  # devuelve el nombre como "ruta"
    monkeypatch.setattr(persiann, "lluvia_del_punto", lambda ruta, lat, lon: lectura[ruta])
    return persiann.obtener_lluvia("lote-7", -33.7025, -65.2975, desde, hasta,
                                   httpx.Client(transport=httpx.MockTransport(lambda p: httpx.Response(200))))


def por_fecha(obs):
    return {o.fecha: o for o in obs}


# ---------- a_observacion y obtener_lluvia ----------

def test_un_valor_por_dia_pedido_con_la_variable_de_imerg(monkeypatch):
    obs = pedir(monkeypatch)
    assert [o.fecha for o in obs] == [date(2026, 1, d) for d in (12, 13, 14, 15)]
    assert all(o.variable == "lluvia_mm" and o.unidad == "mm/día" for o in obs)
    assert all(o.fuente == "PERSIANN" and o.resolucion_m == 27000 for o in obs)


def test_valor_normal_es_buena_y_la_nota_dice_que_es_respaldo(monkeypatch):
    dia = por_fecha(pedir(monkeypatch))[date(2026, 1, 13)]
    assert (dia.valor, dia.calidad) == (25.3, "buena")
    assert dia.nota == persiann.NOTA and "satélite" in dia.nota


def test_cero_es_un_dato_real_no_un_faltante(monkeypatch):
    dia = por_fecha(pedir(monkeypatch))[date(2026, 1, 12)]
    assert (dia.valor, dia.calidad) == (0.0, "buena")


def test_pixel_sin_dato_no_se_inventa(monkeypatch):
    dia = por_fecha(pedir(monkeypatch))[date(2026, 1, 14)]
    assert dia.valor is None and dia.calidad == "descartada"
    assert "sin dato" in dia.nota and "Respaldo de IMERG" in dia.nota


def test_dia_que_persiann_todavia_no_publico_queda_descartado(monkeypatch):
    dia = por_fecha(pedir(monkeypatch))[date(2026, 1, 15)]
    assert dia.valor is None and dia.calidad == "descartada"
    assert "todavía no tiene" in dia.nota


def test_fuera_de_rango_es_dudosa_sin_corregir(monkeypatch):
    nombre = "PERSIANN-CDR_v01r01_20260112_c20260115.nc"
    (dia,) = pedir(monkeypatch, nombres={DESDE: nombre}, lectura={nombre: 612.5}, hasta=DESDE)
    assert (dia.valor, dia.calidad) == (612.5, "dudosa")


def test_periodo_que_cruza_el_anio_pide_los_dos_indices(monkeypatch):
    anios = []
    monkeypatch.setattr(persiann, "listado_anual", lambda cliente, anio: anios.append(anio) or {})
    persiann.obtener_lluvia("lote-7", -33.7, -65.3, date(2025, 12, 30), date(2026, 1, 2))
    assert anios == [2025, 2026]


@pytest.mark.parametrize("lat, lon, desde, hasta", [
    (-95, -65, DESDE, HASTA),       # latitud imposible
    (-33, -190, DESDE, HASTA),      # longitud imposible
    (-72, -65, DESDE, HASTA),       # fuera de 60°S-60°N (PERSIANN no cubre)
    (-33, -65, HASTA, DESDE),       # desde > hasta
    (-33, -65, date(2025, 1, 1), date(2026, 1, 1)),  # supera MAX_DIAS
])
def test_pedido_invalido_no_pide_nada(lat, lon, desde, hasta, monkeypatch):
    llamado = []
    monkeypatch.setattr(persiann, "listado_anual", lambda *a: llamado.append(a) or {})
    with pytest.raises(ValueError):
        persiann.obtener_lluvia("lote-7", lat, lon, desde, hasta)
    assert llamado == []


def test_persiann_caido_o_ilegible_da_error_claro(monkeypatch):
    def romper(cliente, anio):
        raise httpx.ConnectError("NOAA no responde")
    monkeypatch.setattr(persiann, "listado_anual", romper)
    with pytest.raises(persiann.ErrorPERSIANN):
        persiann.obtener_lluvia("lote-7", -33.7, -65.3, DESDE, HASTA)


# ---------- índice anual (parseo del HTML de NCEI) ----------

INDICE_HTML = """<html><body>
<a href="PERSIANN-CDR_v01r01_20260112_c20260115.nc">PERSIANN-CDR_v01r01_20260112_c20260115.nc</a>
<a href="PERSIANN-CDR_v01r01_20260113_c20260116.nc">...</a>
<a href="PERSIANN-CDR_v01r01_20260113_c20260116.nc.md5">no es un NetCDF</a>
</body></html>"""


def test_listado_anual_arma_el_mapa_de_fechas_desde_el_indice(monkeypatch, tmp_path):
    monkeypatch.setattr(persiann, "_LISTADO", {})
    cliente = httpx.Client(transport=httpx.MockTransport(lambda p: httpx.Response(200, text=INDICE_HTML)))
    listado = persiann.listado_anual(cliente, 2026)
    assert listado == {date(2026, 1, 12): "PERSIANN-CDR_v01r01_20260112_c20260115.nc",
                       date(2026, 1, 13): "PERSIANN-CDR_v01r01_20260113_c20260116.nc"}


def test_listado_anual_se_pide_una_sola_vez(monkeypatch):
    monkeypatch.setattr(persiann, "_LISTADO", {})
    pedidos = []

    def responder(pedido):
        pedidos.append(str(pedido.url))
        return httpx.Response(200, text=INDICE_HTML)

    cliente = httpx.Client(transport=httpx.MockTransport(responder))
    persiann.listado_anual(cliente, 2026)
    persiann.listado_anual(cliente, 2026)
    assert pedidos == ["https://www.ncei.noaa.gov/data/precipitation-persiann/access/2026/"]


# ---------- detección de la variable de lluvia en el NetCDF ----------

def sub(nombre):  # simula un subdataset de GDAL
    return f"netcdf:/tmp/x.nc:{nombre}"


def test_elige_la_variable_precip_entre_varias():
    subs = [sub("lat"), sub("lon"), sub("time"), sub("precip"), sub("numgauges")]
    assert persiann._elegir_precip(subs) == sub("precip")


def test_elige_precipitation_aunque_no_se_llame_exacto():
    subs = [sub("latitude"), sub("longitude"), sub("precipitation")]
    assert persiann._elegir_precip(subs) == sub("precipitation")


def test_si_queda_una_sola_variable_de_datos_la_usa():
    subs = [sub("lat"), sub("lon"), sub("rain")]
    assert persiann._elegir_precip(subs) == sub("rain")


def test_sin_variable_de_datos_clara_devuelve_none():
    # dos variables de datos y ninguna con 'precip': no adivina
    assert persiann._elegir_precip([sub("lat"), sub("lon"), sub("tmax"), sub("tmin")]) is None


# ---------- descarga y caché ----------

def test_baja_el_dia_una_sola_vez(monkeypatch, tmp_path):
    monkeypatch.setattr(persiann, "CARPETA", tmp_path)
    pedidos = []

    def responder(pedido):
        pedidos.append(str(pedido.url))
        return httpx.Response(200, content=b"NetCDF-falso")

    cliente = httpx.Client(transport=httpx.MockTransport(responder))
    nombre = "PERSIANN-CDR_v01r01_20260112_c20260115.nc"
    ruta = persiann.bajar_dia(cliente, 2026, nombre)
    assert ruta.read_bytes() == b"NetCDF-falso"
    assert pedidos == [f"https://www.ncei.noaa.gov/data/precipitation-persiann/access/2026/{nombre}"]
    persiann.bajar_dia(cliente, 2026, nombre)  # ya está en disco: no vuelve a bajar
    assert len(pedidos) == 1


# ---------- conexión con el núcleo (specs 005 y 009) ----------

def test_se_anuncia_como_tercer_respaldo_de_imerg():
    (satelite,) = persiann.SATELITES
    assert (satelite.nombre, satelite.respaldo_de, satelite.orden, satelite.estatico) == (
        "IMERG:PERSIANN", "IMERG", 3, False)


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


def imerg_falso(pedidos, falla=False):
    def pedir_imerg(lote, desde, hasta):
        pedidos.append(("IMERG", desde, hasta))
        if falla:
            raise RuntimeError("GES DISC no responde")
        return [Observacion(lote_id=lote["id"], fecha=desde, variable="lluvia_mm", valor=22.5, unidad="mm/día",
                            fuente="IMERG", resolucion_m=10000, calidad="buena")]
    return Satelite("IMERG", pedir_imerg)


def respaldo_espiado(monkeypatch, pedidos):
    def espiar(lote_id, lat, lon, desde, hasta):
        pedidos.append(("IMERG:PERSIANN", desde, hasta))
        serie = {desde: 25.3, hasta: 2.0}
        return [persiann.a_observacion(lote_id, dia, serie.get(dia), True) for dia in (desde, hasta)]

    monkeypatch.setattr(persiann, "obtener_lluvia", espiar)
    return persiann.SATELITES


def test_imerg_caido_entra_persiann_por_el_mismo_periodo(motor, monkeypatch):
    lote = base.guardar_lote(motor, "lote-7", "Lote 7", POLIGONO)
    pedidos = []
    satelites = [imerg_falso(pedidos, falla=True)] + respaldo_espiado(monkeypatch, pedidos)
    resultados = actualizar.actualizar_lote(motor, lote, hoy=date(2026, 1, 16), satelites=satelites)
    assert [(r.fuente, r.resultado) for r in resultados] == [("IMERG", "error"), ("IMERG:PERSIANN", "ok")]
    assert pedidos[0][1:] == pedidos[1][1:]  # mismo período
    guardadas = base.leer_observaciones(motor, "lote-7", variable="lluvia_mm", fuente="PERSIANN")
    assert guardadas and all(o.nota.startswith("Respaldo de IMERG") or o.valor is None for o in guardadas)


def test_imerg_ok_no_consulta_el_respaldo(motor, monkeypatch):
    lote = base.guardar_lote(motor, "lote-7", "Lote 7", POLIGONO)
    pedidos = []
    satelites = [imerg_falso(pedidos)] + respaldo_espiado(monkeypatch, pedidos)
    resultados = actualizar.actualizar_lote(motor, lote, hoy=date(2026, 1, 16), satelites=satelites)
    assert [r.fuente for r in resultados] == ["IMERG"]
    assert [p[0] for p in pedidos] == ["IMERG"]


def test_combinar_prefiere_imerg_y_persiann_rellena_lo_que_falta():
    def lluvia(dia, fuente, valor):
        return Observacion(lote_id="lote-7", fecha=date(2026, 1, dia), variable="lluvia_mm", valor=valor,
                           unidad="mm/día", fuente=fuente, resolucion_m=27000 if fuente == "PERSIANN" else 10000,
                           calidad="buena" if valor is not None else "descartada")
    serie = base.combinar_fuentes([lluvia(13, "IMERG", 22.5), lluvia(13, "PERSIANN", 25.3),
                                   lluvia(14, "IMERG", None), lluvia(14, "PERSIANN", 2.0)])
    assert [(o.fecha.day, o.fuente, o.valor) for o in serie] == [(13, "IMERG", 22.5), (14, "PERSIANN", 2.0)]
