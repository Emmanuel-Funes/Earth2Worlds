from datetime import date

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rotaterra.fuentes import magyp_rindes as magyp

LAT, LON = -33.7025, -65.2975
ENCABEZADO = ("cultivo,anio,campania,provincia,provincia_id,departamento,departamento_id,superficie_sembrada_ha,"
              "superficie_cosechada_ha,produccion_tm,rendimiento_kgxha")
# rindes de maíz de 2013/14 a 2024/25: las dos primeras quedan afuera de las últimas 10
MAIZ = [6000, 6100, 4950, 3300, 7200, 5000, 4900, 4000, 6000, 5500, 4500, 3900]


def fila(cultivo, inicio, rinde, sembrada="1000", cosechada="900", provincia_id="74", departamento_id="74035",
         departamento="General Pedernera", provincia="San Luis"):
    return (f'"{cultivo}",{inicio + 1},{inicio}/{(inicio + 1) % 100:02d},{provincia},{provincia_id},"{departamento}",'
            f'{departamento_id},{sembrada},{cosechada},,{rinde}')


def csv_simulado(filas: list[str]) -> str:
    return "\n".join([ENCABEZADO] + filas) + "\n"


def csv_pedernera() -> str:
    filas = [fila("Maíz", 2013 + i, r) for i, r in enumerate(MAIZ)]
    # soja de primera: 2 campañas sin rinde (vacía y pérdida total) que no cuentan
    filas += [fila("Soja 1ra", 2019, "2100"), fila("Soja 1ra", 2020, "", cosechada=""),
              fila("Soja 1ra", 2021, "0", cosechada="0"), fila("Soja 1ra", 2022, "1200"),
              fila("Soja 1ra", 2023, "3200"), fila("Soja 1ra", 2024, "2462,5")]
    filas += [fila("soja 2da", 2023, "1500"), fila("Soja total", 2024, "9999")]
    filas += [fila("Girasol", 2015 + i, r) for i, r in enumerate([1700, 1850, 2462, 1800, 1900])]
    # otro departamento (General Pueyrredón, San Luis) y otra provincia con el mismo número de departamento
    filas += [fila("Maíz", 2024, "9000", departamento_id="74049", departamento="Juan Martín de Pueyrredón"),
              fila("Maíz", 2024, "8000", provincia_id="14", departamento_id="14035", departamento="Otro",
                   provincia="Córdoba"),
              fila("Trigo total", 2025, "", sembrada="500", cosechada="")]
    return csv_simulado(filas)


def departamento(texto: str | None = None, codigo: str = "74035") -> magyp.Departamento:
    return magyp.leer_departamento(texto or csv_pedernera(), codigo)


def por_variable(obs):
    return {o.variable: o for o in obs}


# ---------- reglas sin internet ----------

def test_nombres_del_ministerio_al_catalogo():
    assert magyp.cultivo_del_catalogo("Maíz") == "maiz"
    assert magyp.cultivo_del_catalogo("SOJA 1RA") == "soja"
    assert magyp.cultivo_del_catalogo("Soja 2da.") == "soja_2da"
    assert magyp.cultivo_del_catalogo("Maní") == "mani"
    assert magyp.cultivo_del_catalogo("Trigo total") == "trigo"
    assert magyp.cultivo_del_catalogo("Algodón") == "algodon"
    assert magyp.cultivo_del_catalogo("Soja total") is None  # mezcla primera y segunda
    assert magyp.cultivo_del_catalogo("Cebada cervecera") is None


def test_numeros_del_csv():
    assert magyp.numero("2462") == 2462 and magyp.numero("2462,5") == 2462.5 and magyp.numero("1.234,5") == 1234.5
    assert magyp.numero("") is None and magyp.numero(None) is None and magyp.numero("SD") is None


def test_campanias_y_codigos():
    assert magyp.inicio_campania("2024/25", "2025") == 2024
    assert magyp.inicio_campania("2024/2025", None) == 2024
    assert magyp.campania_texto(2015) == "2015/16" and magyp.campania_texto(1999) == "1999/00"
    assert magyp.codigo_indec("74035") == "74035" and magyp.codigo_indec(6007) == "06007"
    with pytest.raises(ValueError):
        magyp.codigo_indec("35")


def test_departamento_como_texto_o_como_numero():
    assert magyp.es_del_departamento("74035", "74", "74035")
    assert magyp.es_del_departamento("74035", "74", "35")
    assert magyp.es_del_departamento("74035", "74", "035")
    assert magyp.es_del_departamento("74035", "74.0", "35.0")
    assert not magyp.es_del_departamento("74035", "14", "35")
    assert not magyp.es_del_departamento("74035", "74", "49")
    assert not magyp.es_del_departamento("74035", "74", "")


def test_mediana_de_las_ultimas_10_campanias():
    obs = por_variable(magyp.observaciones("lote-7", departamento()))
    maiz = obs["rinde_referencia_maiz_kg_ha"]
    # últimas 10: 2015/16 a 2024/25 -> mediana de 4950 y 4900... ordenados: 3300 3900 4000 4500 4900 4950 5000 5500
    # 6000 7200 -> (4900 + 4950) / 2 = 4925
    assert (maiz.valor, maiz.unidad, maiz.fuente, maiz.resolucion_m, maiz.calidad, maiz.fecha) == \
        (4925, "kg/ha", "MAGyP", 100000, "buena", date(2025, 6, 30))
    assert maiz.nota == ("Mediana de 10 campañas (2015/16 a 2024/25) en General Pedernera, San Luis: de 3300 a 7200 "
                         "kg/ha. Promedio del departamento, no del lote (Estimaciones Agrícolas, Ministerio de "
                         "Agricultura).")


def test_campanias_sin_rinde_no_cuentan_y_la_perdida_total_se_informa():
    soja = por_variable(magyp.observaciones("lote-7", departamento()))["rinde_referencia_soja_kg_ha"]
    # cuentan 2019, 2022, 2023 y 2024: 2100, 1200, 3200, 2462,5 -> mediana 2281,25; con 4 campañas es dudosa
    assert soja.valor == 2281 and soja.calidad == "dudosa" and soja.fecha == date(2025, 6, 30)
    assert "Mediana de 4 campañas (2019/20 a 2024/25)" in soja.nota and "de 1200 a 3200 kg/ha" in soja.nota
    assert soja.nota.endswith(" · 1 campañas con pérdida total")


def test_soja_de_segunda_aparte_y_soja_total_afuera():
    obs = por_variable(magyp.observaciones("lote-7", departamento()))
    assert obs["rinde_referencia_soja_2da_kg_ha"].valor == 1500
    assert 9999 not in [o.valor for o in obs.values()]


def test_cultivo_sin_filas_sale_descartado_con_la_fecha_del_archivo():
    obs = por_variable(magyp.observaciones("lote-7", departamento()))
    for cultivo in ("alfalfa", "algodon", "mani", "sorgo"):
        o = obs[f"rinde_referencia_{cultivo}_kg_ha"]
        assert o.valor is None and o.calidad == "descartada" and "sin datos en el departamento" in o.nota.lower()
        assert o.fecha == date(2026, 6, 30)  # el archivo llega hasta 2025/26
    trigo = obs["rinde_referencia_trigo_kg_ha"]  # sembrado, todavía sin cosechar: no es pérdida total
    assert trigo.valor is None and "sin campañas con rinde" in trigo.nota.lower() and "pérdida" not in trigo.nota


def test_siempre_una_observacion_por_cultivo_del_catalogo():
    obs = magyp.observaciones("lote-7", departamento())
    assert [o.variable for o in obs] == [f"rinde_referencia_{c}_kg_ha" for c in
                                         ("maiz", "soja", "soja_2da", "sorgo", "mani", "girasol", "trigo", "alfalfa",
                                          "algodon")]


def test_departamento_con_codigo_corto_y_provincia_aparte():
    texto = csv_simulado([fila("Maíz", 2020 + i, 5000 + i, departamento_id="35") for i in range(5)] +
                         [fila("Maíz", 2024, "1", provincia_id="14", departamento_id="35")])
    maiz = por_variable(magyp.observaciones("lote-7", departamento(texto)))["rinde_referencia_maiz_kg_ha"]
    assert maiz.valor == 5002 and maiz.calidad == "buena"


def test_csv_en_latin1_con_punto_y_coma(tmp_path):
    texto = csv_simulado([fila("Maní", 2024, "3055")]).replace(",", ";")
    ruta = tmp_path / "x.csv"
    ruta.write_bytes(texto.encode("latin-1"))
    mani = por_variable(magyp.observaciones("lote-7", departamento(magyp.texto_del_archivo(ruta))))
    assert mani["rinde_referencia_mani_kg_ha"].valor == 3055


def test_csv_con_otras_columnas_avisa():
    with pytest.raises(magyp.ErrorMAGyP, match="columnas"):
        magyp.leer_departamento("a,b,c\n1,2,3\n", "74035")


def test_recurso_vigente_es_el_csv_mas_nuevo():
    paquetes = [{"resources": [
        {"name": "Estimaciones agrícolas", "format": "CSV",
         "url": "https://datos.magyp.gob.ar/dataset/x/estimaciones-agricolas-2025-09.csv"},
        {"name": "Estimaciones agrícolas", "format": "CSV",
         "url": "https://datos.magyp.gob.ar/dataset/x/estimaciones-agricolas-2026-03.csv"},
        {"name": "Diccionario", "format": "PDF", "url": "https://datos.magyp.gob.ar/x/estimaciones-agricolas.pdf"},
        {"name": "Otro", "format": "CSV", "url": "https://datos.magyp.gob.ar/x/precios-2027-01.csv"}]}]
    assert magyp.recurso_vigente(paquetes)["url"].endswith("2026-03.csv")
    with pytest.raises(magyp.ErrorMAGyP):
        magyp.recurso_vigente([{"resources": []}])


# ---------- portal del Ministerio y Georef simulados ----------

URL_CSV = "https://datos.magyp.gob.ar/dataset/estimaciones/estimaciones-agricolas-2026-03.csv"


def servidores(pedidos: list[str], georef: dict | None = None):
    def responder(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        pedidos.append(url)
        if request.url.host == "apis.datos.gob.ar":
            return httpx.Response(200, json=georef if georef is not None else {"ubicacion": {
                "departamento": {"id": "74035", "nombre": "General Pedernera"},
                "provincia": {"id": "74", "nombre": "San Luis"}, "lat": LAT, "lon": LON}})
        if "package_search" in url:
            return httpx.Response(200, json={"success": True, "result": {"results": [
                {"name": "estimaciones-agricolas", "resources": [{"name": "Estimaciones agrícolas", "format": "CSV",
                                                                  "url": URL_CSV}]}]}})
        if url == URL_CSV:
            return httpx.Response(200, content=csv_pedernera().encode("utf-8"))
        return httpx.Response(404)

    return responder


@pytest.fixture
def carpeta(tmp_path, monkeypatch):
    monkeypatch.setattr(magyp, "CARPETA", tmp_path)
    return tmp_path


@pytest.fixture
def copia(tmp_path, monkeypatch):
    """La copia del repo, armada con el CSV simulado."""
    ruta = tmp_path / "datos" / "magyp_rindes.csv.gz"
    magyp.guardar_copia(csv_pedernera(), {"archivo": "estimaciones-agricolas-2026-03.csv"}, ruta)
    monkeypatch.setattr(magyp, "COPIA", ruta)
    return ruta


# ---------- la copia del repo ----------

def test_la_copia_guarda_solo_los_cultivos_del_catalogo_desde_2000():
    texto = csv_pedernera() + fila("Ajo", 2024, "9000") + "\n" + fila("Maíz", 1999, "2000") + "\n"
    recorte, guardadas = magyp.armar_copia(texto)
    lineas = recorte.splitlines()
    assert lineas[0] == ENCABEZADO and guardadas == len(lineas) - 1
    assert not [l for l in lineas if "Ajo" in l or "Soja total" in l or "1999/00" in l]
    # la copia da los mismos rindes que el archivo completo
    assert magyp.observaciones("x", departamento(recorte)) == magyp.observaciones("x", departamento())


def test_guardar_y_leer_la_copia(tmp_path):
    ruta = tmp_path / "datos" / "magyp_rindes.csv.gz"
    guardadas = magyp.guardar_copia(csv_pedernera(), {"archivo": "estimaciones-agricolas-2026-03.csv"}, ruta)
    primera = ruta.read_bytes()
    magyp.guardar_copia(csv_pedernera(), {"archivo": "estimaciones-agricolas-2026-03.csv"}, ruta)
    assert ruta.read_bytes() == primera  # misma entrada, mismo archivo: git no ve cambios falsos
    texto, ficha = magyp.leer_copia(ruta)
    assert ficha == {"archivo": "estimaciones-agricolas-2026-03.csv", "filas": guardadas}
    assert texto.splitlines()[0] == ENCABEZADO
    with pytest.raises(magyp.ErrorMAGyP, match="copia"):
        magyp.leer_copia(tmp_path / "no-esta.csv.gz")


def test_la_copia_del_repo_existe_y_se_lee():
    texto, ficha = magyp.leer_copia()
    assert ficha["archivo"].startswith("estimaciones-agricolas-") and ficha["filas"] > 1000
    assert magyp.lector(texto).fieldnames[0] == "cultivo"


def test_de_punta_a_punta_con_georef_simulado(copia):
    pedidos = []
    cliente = httpx.Client(transport=httpx.MockTransport(servidores(pedidos)))
    obs = magyp.obtener_rindes("lote-7", LAT, LON, cliente=cliente)
    assert len(obs) == 9
    maiz = por_variable(obs)["rinde_referencia_maiz_kg_ha"]
    assert maiz.valor == 4925 and "archivo estimaciones-agricolas-2026-03.csv" in maiz.nota
    # solo se le pregunta el departamento a Georef: los rindes salen de la copia, sin llamar al portal
    assert len(pedidos) == 1 and "lat=-33.7025" in pedidos[0] and "lon=-65.2975" in pedidos[0]


def test_con_departamento_en_el_pedido_no_se_llama_a_georef(copia):
    pedidos = []
    cliente = httpx.Client(transport=httpx.MockTransport(servidores(pedidos)))
    dep = magyp.leer_rindes(LAT, LON, "74035", cliente=cliente)
    assert (dep.nombre, dep.provincia) == ("General Pedernera", "San Luis")
    assert not pedidos


def test_el_csv_se_baja_una_sola_vez_por_dia(carpeta):
    pedidos = []
    cliente = httpx.Client(transport=httpx.MockTransport(servidores(pedidos)))
    (carpeta / "estimaciones-agricolas-20260101.csv").write_text("viejo")
    primera = magyp.archivo_del_dia(cliente, date(2026, 10, 15))
    segunda = magyp.archivo_del_dia(cliente, date(2026, 10, 15))
    assert primera == segunda == carpeta / "estimaciones-agricolas-20261015.csv"
    assert sum(1 for p in pedidos if p == URL_CSV) == 1 and sum(1 for p in pedidos if "package_search" in p) == 1
    assert [p.name for p in carpeta.iterdir()] == ["estimaciones-agricolas-20261015.csv"]


def test_georef_sin_departamento_avisa(copia):
    cliente = httpx.Client(transport=httpx.MockTransport(servidores([], georef={"ubicacion": {
        "departamento": {"id": None, "nombre": None}, "provincia": {"id": None, "nombre": None}}})))
    with pytest.raises(magyp.ErrorMAGyP, match="no encontró un departamento"):
        magyp.obtener_rindes("lote-7", -40.0, -30.0, cliente=cliente)


def test_portal_caido_es_error_del_conector(copia, monkeypatch):
    cliente = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(503)))
    with pytest.raises(magyp.ErrorMAGyP):
        magyp.buscar_csv(cliente)
    # el portal caído no afecta a la app: los rindes salen de la copia
    assert len(magyp.obtener_rindes("lote-7", LAT, LON, "74035", cliente=cliente)) == 9
    monkeypatch.setattr(magyp, "COPIA", copia.with_name("no-esta.csv.gz"))
    with pytest.raises(magyp.ErrorMAGyP, match="copia"):
        magyp.obtener_rindes("lote-7", LAT, LON, "74035", cliente=cliente)
    monkeypatch.setattr(magyp, "COPIA", copia)

    def sin_red(request):
        raise httpx.ConnectError("sin red")

    with pytest.raises(magyp.ErrorMAGyP, match="Georef"):
        magyp.obtener_rindes("lote-7", LAT, LON, cliente=httpx.Client(transport=httpx.MockTransport(sin_red)))


def test_el_cliente_se_presenta_y_reintenta():
    with magyp.nuevo_cliente() as cliente:
        assert cliente.headers["User-Agent"].startswith("Rotaterra")


def test_satelite_y_endpoint_de_prueba(copia, monkeypatch):
    assert [(s.nombre, s.respaldo_de) for s in magyp.SATELITES] == [("MAGYP", None)]
    pedidos = []
    monkeypatch.setattr(magyp, "nuevo_cliente", lambda: httpx.Client(transport=httpx.MockTransport(servidores(pedidos))))
    app = FastAPI()
    app.include_router(magyp.router)
    r = TestClient(app).get("/rindes-referencia", params={"lote_id": "x", "lat": LAT, "lon": LON,
                                                          "departamento_id": "74035"})
    assert r.status_code == 200 and len(r.json()) == 9
    assert r.json()[0]["variable"] == "rinde_referencia_maiz_kg_ha" and r.json()[0]["valor"] == 4925
    assert not [p for p in pedidos if "georef" in p]
    obs = magyp.SATELITES[0].pedir({"id": "lote-7", "lat": LAT, "lon": LON}, None, None)
    assert obs[0].lote_id == "lote-7" and [p for p in pedidos if "georef" in p]
    assert TestClient(app).get("/rindes-referencia", params={"lote_id": "x", "lat": -95, "lon": LON}).status_code == 422
    assert TestClient(app).get("/rindes-referencia", params={"lote_id": "x", "lat": LAT, "lon": LON,
                                                             "departamento_id": "35"}).status_code == 422
