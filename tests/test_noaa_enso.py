from datetime import date

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rotaterra.fuentes import noaa_enso

HOY = date(2026, 10, 14)

ONI = """    SEAS  YR   TOTAL   ANOM
    DJF 1950   24.72  -1.53
    JFM 1950   25.17  -1.34
    MJJ 2026   28.10   1.12
    JJA 2026   28.51   1.71
    JAS 2026   28.85   2.16
"""

DISCUSION = """<html><head><title>ENSO Diagnostic Discussion</title><script>var x = "Synopsis: no";</script></head>
<body><b>EL NIÑO/SOUTHERN OSCILLATION (ENSO) DIAGNOSTIC DISCUSSION</b><br>
issued by<br>CLIMATE PREDICTION CENTER/NCEP/NWS<br>and the International Research Institute for Climate and Society
<br>9 October 2026<br><br>
<p><b>ENSO Alert System Status:</b> El Ni&ntilde;o Advisory</p>
<p><b>Synopsis:</b> El Niño is expected to continue, with a strong to very strong event
 likely (greater than 83% chance in January-March 2027).</p>
<p>During September, El Niño strengthened, with above-average sea surface temperatures...</p>
</body></html>"""

PSL = """ 1948 2026
 1948   -0.32   -0.47  -0.39  -0.02  -0.08   0.11   0.02  -0.07   0.03  -0.15  -0.18  -0.29
 2026    0.20    0.35   0.61   0.90   1.20   1.50   1.85   2.10   2.30  -99.99  -99.99  -99.99
  -99.99
  Nino 3.4 SST anomaly
  ERSST V6
  Anomaly from 1981-2010
  units=degC
"""


def cliente(oni=ONI, discusion=DISCUSION, psl=PSL, caidos=()):
    """Cliente con NOAA simulado; `caidos` son los servidores que no responden ('oni', 'discusion', 'psl')."""
    pedidos = []

    def responder(pedido: httpx.Request) -> httpx.Response:
        url = str(pedido.url)
        pedidos.append(url)
        clave = {noaa_enso.URL_ONI: "oni", noaa_enso.URL_DISCUSION: "discusion", noaa_enso.URL_PSL: "psl"}[url]
        if clave in caidos:
            raise httpx.ConnectTimeout("sin respuesta", request=pedido)
        return httpx.Response(200, text={"oni": oni, "discusion": discusion, "psl": psl}[clave])

    c = httpx.Client(transport=httpx.MockTransport(responder))
    c.pedidos = pedidos
    return c


# ---------- clasificación con los umbrales de NOAA ----------

@pytest.mark.parametrize("oni, esperado", [
    (0.5, "El Niño débil"), (0.45, "El Niño débil"), (0.44, "neutral"), (0.0, "neutral"), (-0.44, "neutral"),
    (-0.5, "La Niña débil"), (-0.45, "La Niña débil"), (0.9, "El Niño débil"), (1.0, "El Niño moderado"),
    (-1.2, "La Niña moderada"), (1.44, "El Niño moderado"), (1.45, "El Niño fuerte"), (1.5, "El Niño fuerte"), (-1.5, "La Niña fuerte"),
    (1.95, "El Niño muy fuerte"), (2.0, "El Niño muy fuerte"), (2.16, "El Niño muy fuerte"),
    (-2.0, "La Niña muy fuerte"),
])
def test_fase_en_los_bordes(oni, esperado):
    assert noaa_enso.fase(oni) == esperado


def test_trimestres_y_su_ultimo_dia():
    assert noaa_enso.meses_del_trimestre("JAS", 2026) == [(2026, 7), (2026, 8), (2026, 9)]
    assert noaa_enso.meses_del_trimestre("DJF", 2026) == [(2025, 12), (2026, 1), (2026, 2)]
    assert noaa_enso.meses_del_trimestre("NDJ", 2026) == [(2026, 11), (2026, 12), (2027, 1)]
    assert noaa_enso.nombre_periodo(noaa_enso.meses_del_trimestre("DJF", 2026)) == "dic 2025-feb 2026"
    assert noaa_enso.viejo(date(2026, 9, 30), HOY) is False
    assert noaa_enso.viejo(date(2026, 6, 30), HOY) is True


# ---------- lectura de los archivos ----------

def test_lee_el_ultimo_trimestre_del_oni():
    assert noaa_enso.leer_oni(ONI) == ("JAS", 2026, 2.16)
    with pytest.raises(noaa_enso.ErrorENSO):
        noaa_enso.leer_oni("<html>Página de error</html>")


def test_lee_los_meses_de_psl_sin_faltantes_ni_pie():
    meses = noaa_enso.leer_psl(PSL)
    assert len(meses) == 12 + 9
    assert meses[-1] == (2026, 9, 2.30)


def test_lee_la_discusion():
    leida = noaa_enso.leer_discusion(DISCUSION)
    assert leida["alerta"] == "El Niño Advisory"
    assert leida["publicada"] == date(2026, 10, 9)
    assert leida["sinopsis"].startswith("El Niño is expected to continue")
    assert leida["sinopsis"].endswith("January-March 2027).")
    assert noaa_enso.traducir_alerta(leida["alerta"]) == "Aviso de El Niño"
    assert noaa_enso.traducir_alerta("Not Active") == "Sin alerta"
    assert noaa_enso.traducir_alerta("Final La Nina Advisory") == "Aviso final de La Niña"
    assert noaa_enso.probabilidad(leida["sinopsis"]) == ("más de 83 %", "para ene-mar 2027")
    assert noaa_enso.probabilidad("ENSO-neutral is favored (55% chance) through DJF 2026") == \
        ("55 %", "hasta dic 2025-feb 2026")
    assert noaa_enso.probabilidad("a 60% chance during NDJ 2026") == ("60 %", "para nov 2026-ene 2027")
    # la sinopsis real del 8/10/2026: el período va antes del porcentaje
    real = ("El Niño continues to strengthen, with a strong-to-very strong El Niño likely through January-March 2027 "
            "(remaining greater than an 83% chance).")
    assert noaa_enso.probabilidad(real) == ("más de 83 %", "hasta ene-mar 2027")
    assert noaa_enso.probabilidad("El Niño is favored (70% chance).") == ("70 %", None)
    assert noaa_enso.probabilidad("No numbers here") is None


# ---------- principal ----------

def test_principal_da_el_oni_con_la_sinopsis():
    [o] = noaa_enso.obtener_oni("lote-7", cliente(), HOY)
    assert (o.lote_id, o.fecha, o.variable, o.valor) == ("lote-7", date(2026, 9, 30), "enso_oni", 2.16)
    assert (o.unidad, o.fuente, o.resolucion_m, o.calidad) == ("°C (anomalía)", "CPC", 0, "buena")
    assert o.nota.startswith("El Niño muy fuerte (ONI jul-sep 2026: +2,16 °C")
    assert "discusión del 9 de octubre de 2026: Aviso de El Niño; probabilidad de más de 83 % para ene-mar 2027" \
        in o.nota
    assert '"El Niño is expected to continue' in o.nota
    assert o.nota.endswith("Índice del Pacífico, no del lote.")


def test_discusion_sin_sinopsis_deja_el_indice_sin_pronostico():
    [o] = noaa_enso.obtener_oni("lote-7", cliente(discusion="<html><p>Mantenimiento</p></html>"), HOY)
    assert o.valor == 2.16 and o.calidad == "buena"
    assert "Sin pronóstico de NOAA" in o.nota and "Synopsis" not in o.nota


def test_discusion_caida_no_frena_el_indice():
    [o] = noaa_enso.obtener_oni("lote-7", cliente(caidos=("discusion",)), HOY)
    assert o.valor == 2.16
    assert "Sin pronóstico de NOAA" in o.nota and "ConnectTimeout" in o.nota


def test_un_trimestre_viejo_queda_dudoso():
    [o] = noaa_enso.obtener_oni("lote-7", cliente(), date(2027, 2, 15))
    assert o.calidad == "dudosa" and "más de 3 meses" in o.nota


def test_cpc_caido_lanza_error_para_que_entre_el_respaldo():
    with pytest.raises(noaa_enso.ErrorENSO, match="ONI de CPC no respondió"):
        noaa_enso.obtener_oni("lote-7", cliente(caidos=("oni",)), HOY)


# ---------- respaldo ----------

def test_respaldo_promedia_los_tres_ultimos_meses():
    [o] = noaa_enso.obtener_psl("lote-7", cliente(), HOY)
    assert o.valor == round((1.85 + 2.10 + 2.30) / 3, 2) == 2.08
    assert o.fecha == date(2026, 9, 30) and o.calidad == "dudosa" and o.fuente == "CPC"
    assert o.nota.startswith("El Niño muy fuerte (Niño 3.4 promedio jul-sep 2026: +2,08 °C")
    assert "NOAA PSL (ERSST V6, anomalía frente a 1981-2010;" in o.nota
    assert "Respaldo del ONI de CPC" in o.nota and o.nota.endswith("Índice del Pacífico, no del lote.")


def test_respaldo_con_meses_salteados_queda_descartado():
    psl = " 1948 2026\n 2026  1.0  -99.99  1.2  1.3  -99.99  -99.99  -99.99  -99.99  -99.99  -99.99  -99.99  -99.99\n"
    [o] = noaa_enso.obtener_psl("lote-7", cliente(psl=psl), HOY)
    assert o.valor is None and o.calidad == "descartada" and "no son seguidos" in o.nota


def test_cpc_caido_pasa_al_respaldo_y_queda_dudoso():
    [o] = noaa_enso.obtener_enso("lote-7", cliente(caidos=("oni",)), HOY)
    assert o.valor == 2.08 and o.calidad == "dudosa" and "Respaldo" in o.nota


def test_sin_indice_ni_respaldo_no_se_inventa_la_fase():
    [o] = noaa_enso.obtener_enso("lote-7", cliente(caidos=("oni", "psl", "discusion")), HOY)
    assert o.valor is None and o.calidad == "descartada"
    assert o.nota.startswith("Sin índice") and "débil" not in o.nota and "fuerte" not in o.nota


# ---------- núcleo y endpoints ----------

def test_se_anuncia_con_su_respaldo():
    nombres = {s.nombre: s.respaldo_de for s in noaa_enso.SATELITES}
    assert nombres == {"NOAA_ENSO": None, "NOAA_ENSO:PSL": "NOAA_ENSO"}


def test_endpoints(monkeypatch):
    original = noaa_enso._cliente
    monkeypatch.setattr(noaa_enso, "_cliente", lambda c: original(c or cliente(caidos=("oni",))))
    app = FastAPI()
    app.include_router(noaa_enso.router)
    http = TestClient(app)
    [o] = http.get("/enso").json()
    assert o["lote_id"] == "consulta" and o["valor"] == 2.08 and o["calidad"] == "dudosa"
    [o] = http.get("/enso/psl", params={"lote_id": "lote-7"}).json()
    assert o["lote_id"] == "lote-7" and o["valor"] == 2.08
    monkeypatch.setattr(noaa_enso, "_cliente", lambda c: original(c or cliente(caidos=("psl",))))
    assert http.get("/enso/psl").status_code == 502


def test_el_cliente_real_se_arma_sin_red():
    real = noaa_enso._cliente(None)
    assert real.headers["User-Agent"].isascii()
    real.close()
