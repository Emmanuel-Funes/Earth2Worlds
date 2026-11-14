"""Segundo respaldo de la lluvia de IMERG con NOAA CPC (spec 029). Sin internet: NetCDF y descarga simulados."""

import os
from datetime import date

import httpx
import pytest

from rotaterra import actualizar, base
from rotaterra.contrato import Observacion
from rotaterra.fuentes import cpc_lluvia
from rotaterra.fuentes.registro import Satelite
from rotaterra.geo import poligono_desde_esquinas

POLIGONO = poligono_desde_esquinas("-33.700, -65.300; -33.700, -65.295; -33.705, -65.295; -33.705, -65.300")
DESDE, HASTA = date(2026, 1, 12), date(2026, 1, 15)

# lo que daría el lector del NetCDF para el píxel del lote: el 14/1 es relleno (píxel sin dato),
# el 15/1 no está en el archivo (día que CPC todavía no publicó)
LECTURA = {date(2026, 1, 12): 0.0, date(2026, 1, 13): 18.37, date(2026, 1, 14): None}


def lector_falso(lectura=LECTURA):
    """Reemplaza dias_del_punto: devuelve una serie fija sin abrir ningún NetCDF."""
    def leer(ruta, lat, lon):
        leer.pedidos.append((ruta, lat, lon))
        return dict(lectura)
    leer.pedidos = []
    return leer


def pedir(monkeypatch, lectura=LECTURA, desde=DESDE, hasta=HASTA):
    monkeypatch.setattr(cpc_lluvia, "archivo_anual", lambda cliente, anio: f"precip.{anio}.nc")
    monkeypatch.setattr(cpc_lluvia, "dias_del_punto", lector_falso(lectura))
    return cpc_lluvia.obtener_lluvia("lote-7", -33.7025, -65.2975, desde, hasta,
                                     httpx.Client(transport=httpx.MockTransport(lambda p: httpx.Response(200))))


def por_fecha(obs):
    return {o.fecha: o for o in obs}


# ---------- a_observacion y obtener_lluvia ----------

def test_un_valor_por_dia_pedido_con_la_variable_de_imerg(monkeypatch):
    obs = pedir(monkeypatch)
    assert [o.fecha for o in obs] == [date(2026, 1, d) for d in (12, 13, 14, 15)]
    assert all(o.variable == "lluvia_mm" and o.unidad == "mm/día" for o in obs)
    assert all(o.fuente == "CPC" and o.resolucion_m == 55000 for o in obs)


def test_valor_normal_es_buena_y_la_nota_dice_que_es_respaldo(monkeypatch):
    dia = por_fecha(pedir(monkeypatch))[date(2026, 1, 13)]
    assert (dia.valor, dia.calidad) == (18.37, "buena")
    assert dia.nota == "Respaldo de IMERG · NOAA CPC Global Unified (pluviómetros) · celda de 0,5°"


def test_cero_es_un_dato_real_no_un_faltante(monkeypatch):
    dia = por_fecha(pedir(monkeypatch))[date(2026, 1, 12)]
    assert (dia.valor, dia.calidad) == (0.0, "buena")


def test_pixel_sin_dato_no_se_inventa(monkeypatch):
    dia = por_fecha(pedir(monkeypatch))[date(2026, 1, 14)]
    assert dia.valor is None and dia.calidad == "descartada"
    assert "sin dato" in dia.nota and "Respaldo de IMERG" in dia.nota


def test_dia_que_cpc_todavia_no_publico_queda_descartado(monkeypatch):
    dia = por_fecha(pedir(monkeypatch))[date(2026, 1, 15)]
    assert dia.valor is None and dia.calidad == "descartada"
    assert "todavía no tiene" in dia.nota


def test_fuera_de_rango_es_dudosa_sin_corregir(monkeypatch):
    (dia,) = pedir(monkeypatch, lectura={DESDE: 612.5}, hasta=DESDE)
    assert (dia.valor, dia.calidad) == (612.5, "dudosa")


def test_se_pide_el_punto_del_lote(monkeypatch):
    monkeypatch.setattr(cpc_lluvia, "archivo_anual", lambda cliente, anio: f"precip.{anio}.nc")
    lector = lector_falso()
    monkeypatch.setattr(cpc_lluvia, "dias_del_punto", lector)
    cpc_lluvia.obtener_lluvia("lote-7", -33.7025, -65.2975, DESDE, HASTA)
    assert lector.pedidos == [("precip.2026.nc", -33.7025, -65.2975)]


def test_periodo_que_cruza_el_anio_baja_los_dos_archivos(monkeypatch):
    anios = []
    monkeypatch.setattr(cpc_lluvia, "archivo_anual", lambda cliente, anio: anios.append(anio) or f"precip.{anio}.nc")
    monkeypatch.setattr(cpc_lluvia, "dias_del_punto", lambda ruta, lat, lon: {})
    cpc_lluvia.obtener_lluvia("lote-7", -33.7, -65.3, date(2025, 12, 30), date(2026, 1, 2))
    assert anios == [2025, 2026]


@pytest.mark.parametrize("lat, lon, desde, hasta", [
    (-95, -65, DESDE, HASTA),
    (-33, -190, DESDE, HASTA),
    (-33, -65, HASTA, DESDE),
    (-33, -65, date(2024, 1, 1), date(2026, 1, 1)),
])
def test_pedido_invalido_no_baja_nada(lat, lon, desde, hasta, monkeypatch):
    llamado = []
    monkeypatch.setattr(cpc_lluvia, "archivo_anual", lambda *a: llamado.append(a))
    with pytest.raises(ValueError):
        cpc_lluvia.obtener_lluvia("lote-7", lat, lon, desde, hasta)
    assert llamado == []


def test_cpc_caido_o_ilegible_da_error_claro(monkeypatch):
    def romper(cliente, anio):
        raise httpx.ConnectError("NOAA no responde")
    monkeypatch.setattr(cpc_lluvia, "archivo_anual", romper)
    with pytest.raises(cpc_lluvia.ErrorCPC):
        cpc_lluvia.obtener_lluvia("lote-7", -33.7, -65.3, DESDE, HASTA)


# ---------- eje de tiempo ----------

def test_fechas_del_tiempo_lee_horas_desde_1900():
    # así lo expone GDAL para el archivo real de CPC: horas desde 1900-01-01
    fechas = cpc_lluvia.fechas_del_tiempo([1104504.0, 1104528.0], "hours since 1900-01-01 00:00:00")
    assert fechas == [date(2026, 1, 1), date(2026, 1, 2)]


def test_fechas_del_tiempo_tambien_lee_days_since():
    fechas = cpc_lluvia.fechas_del_tiempo([46021.0, 46022.0], "days since 1900-01-01 00:00:0.0")
    assert fechas == [date(2026, 1, 1), date(2026, 1, 2)]


def test_fechas_del_tiempo_rechaza_unidades_raras():
    with pytest.raises(cpc_lluvia.ErrorCPC):
        cpc_lluvia.fechas_del_tiempo([0.0], "something odd")


# ---------- descarga y caché ----------

def test_baja_el_archivo_anual_una_vez_por_dia(monkeypatch, tmp_path):
    monkeypatch.setattr(cpc_lluvia, "CARPETA", tmp_path)
    pedidos = []

    def responder(pedido):
        pedidos.append(str(pedido.url))
        return httpx.Response(200, content=b"NetCDF-falso")

    cliente = httpx.Client(transport=httpx.MockTransport(responder))
    ruta = cpc_lluvia.archivo_anual(cliente, 2026)
    assert ruta.read_bytes() == b"NetCDF-falso"
    assert pedidos == ["https://downloads.psl.noaa.gov/Datasets/cpc_global_precip/precip.2026.nc"]
    # segunda llamada el mismo día: no vuelve a bajar
    cpc_lluvia.archivo_anual(cliente, 2026)
    assert len(pedidos) == 1


# ---------- conexión con el núcleo (specs 005 y 009) ----------

def test_se_anuncia_como_segundo_respaldo_de_imerg():
    (satelite,) = cpc_lluvia.SATELITES
    assert (satelite.nombre, satelite.respaldo_de, satelite.orden, satelite.estatico) == (
        "IMERG:CPC", "IMERG", 2, False)


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
        pedidos.append(("IMERG:CPC", desde, hasta))
        serie = {desde: 17.5, hasta: 3.1}
        dias = [(desde, serie.get(desde)), (hasta, serie.get(hasta))]
        return [cpc_lluvia.a_observacion(lote_id, dia, valor, True) for dia, valor in dias]

    monkeypatch.setattr(cpc_lluvia, "obtener_lluvia", espiar)
    return cpc_lluvia.SATELITES


def test_imerg_caido_entra_cpc_por_el_mismo_periodo(motor, monkeypatch):
    lote = base.guardar_lote(motor, "lote-7", "Lote 7", POLIGONO)
    pedidos = []
    satelites = [imerg_falso(pedidos, falla=True)] + respaldo_espiado(monkeypatch, pedidos)
    resultados = actualizar.actualizar_lote(motor, lote, hoy=date(2026, 1, 16), satelites=satelites)
    assert [(r.fuente, r.resultado) for r in resultados] == [("IMERG", "error"), ("IMERG:CPC", "ok")]
    assert pedidos[0][1:] == pedidos[1][1:]  # mismo período
    guardadas = base.leer_observaciones(motor, "lote-7", variable="lluvia_mm", fuente="CPC")
    assert guardadas and all(o.nota.startswith("Respaldo de IMERG") or o.valor is None for o in guardadas)


def test_imerg_ok_no_consulta_el_respaldo(motor, monkeypatch):
    lote = base.guardar_lote(motor, "lote-7", "Lote 7", POLIGONO)
    pedidos = []
    satelites = [imerg_falso(pedidos)] + respaldo_espiado(monkeypatch, pedidos)
    resultados = actualizar.actualizar_lote(motor, lote, hoy=date(2026, 1, 16), satelites=satelites)
    assert [r.fuente for r in resultados] == ["IMERG"]
    assert [p[0] for p in pedidos] == ["IMERG"]


def test_sin_imerg_unido_queda_en_espera(motor, monkeypatch):
    lote = base.guardar_lote(motor, "lote-7", "Lote 7", POLIGONO)
    pedidos = []
    resultados = actualizar.actualizar_lote(motor, lote, hoy=date(2026, 1, 16),
                                            satelites=respaldo_espiado(monkeypatch, pedidos))
    assert resultados == [] and pedidos == []


def test_combinar_prefiere_imerg_y_cpc_rellena_lo_que_falta():
    def lluvia(dia, fuente, valor):
        return Observacion(lote_id="lote-7", fecha=date(2026, 1, dia), variable="lluvia_mm", valor=valor,
                           unidad="mm/día", fuente=fuente, resolucion_m=55000 if fuente == "CPC" else 10000,
                           calidad="buena" if valor is not None else "descartada")
    serie = base.combinar_fuentes([lluvia(13, "IMERG", 22.5), lluvia(13, "CPC", 17.5),
                                   lluvia(14, "IMERG", None), lluvia(14, "CPC", 3.1)])
    assert [(o.fecha.day, o.fuente, o.valor) for o in serie] == [(13, "IMERG", 22.5), (14, "CPC", 3.1)]
