"""GOES-19 heladas, respaldo "del día" de VIIRS (spec 043): tests sin internet con el archivo de la NOAA simulado."""

from datetime import date, datetime, timezone

import httpx

from rotaterra.fuentes import goes_heladas

AHORA = datetime(2026, 10, 15, 23, 45, tzinfo=timezone.utc)


def cubo(horas_con_archivo=None, caido=False):
    """Lista un archivo por hora (o solo en las horas pedidas); el nombre lleva la hora para la lectura falsa."""
    def responder(pedido: httpx.Request) -> httpx.Response:
        if caido:
            return httpx.Response(503)
        prefijo = pedido.url.params["prefix"]
        hora = int(prefijo.rstrip("/").rsplit("/", 1)[1])
        if horas_con_archivo is not None and hora not in horas_con_archivo:
            return httpx.Response(200, text="<ListBucketResult></ListBucketResult>")
        return httpx.Response(200, text=f"<ListBucketResult><Contents><Key>{prefijo}OR_LST_h{hora:02d}.nc</Key>"
                                        "</Contents></ListBucketResult>")
    return httpx.Client(transport=httpx.MockTransport(responder))


def lectura(temperaturas: dict, dqf: dict | None = None):
    """temperaturas: hora UTC -> °C."""
    def leer(url, lat, lon):
        hora = int(url.rsplit("_h", 1)[1][:2])
        return temperaturas[hora] + 273.15, (dqf or {}).get(hora, 0)
    return leer


def test_minima_de_la_madrugada_y_aviso_de_helada():
    obs, = goes_heladas.obtener_heladas("lote-7", -33.7, -65.3, date(2026, 10, 15), date(2026, 10, 15), cubo(),
                                        lectura({7: 1.5, 8: 0.2, 9: -1.4, 10: 0.8}), AHORA)
    assert (obs.valor, obs.calidad, obs.fuente, obs.variable) == (-1.4, "buena", "GOES", "temp_sup_min_c")
    assert "a las 6 h" in obs.nota and "riesgo de helada" in obs.nota


def test_nubes_no_inventan_un_valor():
    obs, = goes_heladas.obtener_heladas("lote-7", -33.7, -65.3, date(2026, 10, 15), date(2026, 10, 15), cubo(),
                                        lectura({7: 5, 8: 5, 9: 5, 10: 5}, dqf={7: 3, 8: 3, 9: 3, 10: 3}), AHORA)
    assert (obs.valor, obs.calidad) == (None, "descartada") and "nubes" in obs.nota


def test_madrugada_en_curso_es_dudosa_y_dia_futuro_descartado():
    a_las_9 = datetime(2026, 10, 15, 9, 10, tzinfo=timezone.utc)
    hoy, manana = goes_heladas.obtener_heladas("lote-7", -33.7, -65.3, date(2026, 10, 15), date(2026, 10, 16),
                                               cubo(), lectura({7: 3.0, 8: 2.0}), a_las_9)
    assert (hoy.valor, hoy.calidad) == (2.0, "dudosa") and "2 de 4 horas" in hoy.nota
    assert manana.valor is None and "todavía no pasó" in manana.nota


def test_noaa_caida():
    obs, = goes_heladas.obtener_heladas("lote-7", -33.7, -65.3, date(2026, 10, 15), date(2026, 10, 15),
                                        cubo(caido=True), lectura({}), AHORA)
    assert obs.valor is None and "no respondió" in obs.nota


def test_solo_los_ultimos_diez_dias():
    obs = goes_heladas.obtener_heladas("lote-7", -33.7, -65.3, date(2026, 10, 1), date(2026, 10, 15), cubo(),
                                       lectura({7: 4, 8: 3, 9: 2, 10: 3}), AHORA)
    assert len(obs) == 15 and sum(o.valor is not None for o in obs) == 10


def test_se_anuncia_como_respaldo_del_dia_de_viirs():
    s, = goes_heladas.SATELITES
    assert (s.nombre, s.respaldo_de, s.al_dia) == ("VIIRS_LST:GOES", "VIIRS_LST", True)


def test_una_lectura_dudosa_no_gana_si_hay_buenas():
    """Borde de nube: la lectura dudosa da −5,7 °C, las buenas 8 °C (prueba real del 16/10/2026)."""
    obs, = goes_heladas.obtener_heladas("lote-7", -33.7, -65.3, date(2026, 10, 13), date(2026, 10, 13), cubo(),
                                        lectura({7: 9.0, 8: -5.7, 9: 8.0, 10: 8.5}, dqf={8: 2}), AHORA)
    assert (obs.valor, obs.calidad) == (8.0, "buena") and "riesgo" not in obs.nota


def test_si_solo_hay_dudosas_se_usan_marcadas():
    obs, = goes_heladas.obtener_heladas("lote-7", -33.7, -65.3, date(2026, 10, 13), date(2026, 10, 13), cubo(),
                                        lectura({7: 1.0, 8: -2.0, 9: 5, 10: 5}, dqf={7: 2, 8: 2, 9: 3, 10: 3}), AHORA)
    assert (obs.valor, obs.calidad) == (-2.0, "dudosa") and "posible nube" in obs.nota
