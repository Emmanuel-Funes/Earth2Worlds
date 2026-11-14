"""Banco de semillas en la API: archivo SQLite de solo lectura con cultivares y ensayos (spec 057)."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from rotaterra import api, semillas


@pytest.fixture
def cliente():
    return TestClient(api.app)


@pytest.fixture
def banco_chico(tmp_path, monkeypatch):
    ruta = tmp_path / "semillas.sqlite"
    with sqlite3.connect(ruta) as db:
        db.executescript("""
            CREATE TABLE _manifiesto (clave TEXT, valor TEXT);
            INSERT INTO _manifiesto VALUES ('fecha_corte', '2026-10-28');
            CREATE TABLE cultivares (cultivar_id TEXT, cultivar TEXT, nombre_busqueda TEXT, perfil_ssd TEXT, obtentor_inta TEXT);
            INSERT INTO cultivares VALUES ('INASE-1', 'FEBO 817 CL INTA', 'FEBO 817 CL INTA', 'Girasol', 'SI'),
                                          ('INASE-2', 'NS 1115 CL', 'NS 1115 CL', 'Girasol', 'NO'),
                                          ('INASE-3', 'ACA 471 VT3P', 'ACA 471 VT3P', 'Maíz', 'NO');
            CREATE TABLE banco_inta (cultivar_id TEXT, cultivar TEXT, nombre_busqueda TEXT, cultivo TEXT, grupo TEXT, ensayos TEXT);
            INSERT INTO banco_inta VALUES ('INASE-1', 'FEBO 817 CL INTA', 'FEBO 817 CL INTA', 'Girasol', 'Oleaginosas', 'Red girasol'),
                                          ('INASE-9', 'LCP 85-384', 'LCP 85-384', 'Caña de azucar', 'Industriales', '');
            CREATE TABLE girasol_resumen_cultivar (cultivar TEXT, cultivar_id_inase TEXT);
            INSERT INTO girasol_resumen_cultivar VALUES ('NS 1115 CL', 'INASE-2; INASE-20'), ('FEBO 817 CL INTA', 'INASE-1');
            CREATE TABLE girasol_rindes (cultivar TEXT, rinde_kg_ha INTEGER, referencia_san_luis TEXT);
            INSERT INTO girasol_rindes VALUES ('NS 1115 CL', 3100, 'SEMIARIDA_VECINA (La Pampa)'), ('NS 1115 CL', 4200, 'OTRA_REGION');
            CREATE TABLE fichas_inta (cultivar_id TEXT, cultivar TEXT, cultivo TEXT, atributo TEXT, valor TEXT, fuente TEXT, fuente_url TEXT);
            INSERT INTO fichas_inta VALUES ('INASE-1', 'FEBO 817 CL INTA', 'Girasol', 'ciclo', 'intermedio', 'INTA, noticia', 'https://x'),
                                           ('INASE-1', 'FEBO 817 CL INTA', 'Girasol', 'tolerancia: herbicidas', 'IMI', 'INTA, noticia', 'https://x');
            CREATE TABLE manejo_cultivos (cultivo TEXT, tema TEXT, valor TEXT, fuente TEXT, fuente_url TEXT, verificacion TEXT);
            INSERT INTO manejo_cultivos VALUES ('Maní', 'epoca_siembra', 'octubre-noviembre', 'INTA, noticia', 'https://x', 'texto leído'),
                                               ('Maní', 'ph', 'sin dato verificado', '', '', 'falta fuente');
            CREATE TABLE fuentes (fuente_id TEXT, estado TEXT);
            INSERT INTO fuentes VALUES ('INASE_CNC', 'INGERIDA');
        """)
    monkeypatch.setenv("ROTATERRA_SEMILLAS_DB", str(ruta))


def test_resumen_es_solo_del_inta_y_avisa_que_no_hay_stock(cliente, banco_chico):
    r = cliente.get("/semillas").json()
    assert r["fecha_corte_inase"] == "2026-10-28" and r["cultivares"] == 2 and r["solo_inta"]
    assert {c["grupo"] for c in r["por_grupo"]} == {"Oleaginosas", "Industriales"}  # todo el país, no solo San Luis
    assert "stock" in r["aviso"]


def test_manejo_filtra_por_cultivo_y_tema_y_oculta_lo_sin_dato(cliente, banco_chico):
    assert len(cliente.get("/semillas/manejo", params={"cultivo": "Maní"}).json()["filas"]) == 2
    filas = cliente.get("/semillas/manejo", params={"cultivo": "Maní", "solo_con_dato": True}).json()["filas"]
    assert [f["tema"] for f in filas] == ["epoca_siembra"]
    assert cliente.get("/semillas/manejo", params={"tema": "ph"}).json()["filas"][0]["valor"] == "sin dato verificado"
    assert cliente.get("/semillas/manejo", params={"cultivo": "Rosa"}).status_code == 404


def test_cultivares_del_inta_por_defecto_y_privados_solo_si_se_piden(cliente, banco_chico):
    r = cliente.get("/semillas/cultivares", params={"cultivo": "Girasol"}).json()
    assert [c["cultivar"] for c in r["cultivares"]] == ["FEBO 817 CL INTA"]
    assert cliente.get("/semillas/cultivares", params={"grupo": "Industriales"}).json()["total"] == 1
    assert cliente.get("/semillas/cultivares", params={"cultivo": "Girasol", "incluir_privadas": True}).json()["total"] == 2
    assert cliente.get("/semillas/cultivares", params={"texto": "aca 471"}).json()["total"] == 0
    assert cliente.get("/semillas/cultivares", params={"texto": "aca 471", "incluir_privadas": True}).json()["total"] == 1


def test_un_cultivar_trae_sus_ensayos_sin_confundir_ids(cliente, banco_chico):
    r = cliente.get("/semillas/cultivares/INASE-2").json()
    assert r["ensayos"]["girasol"]["resultados"][0]["cultivar"] == "NS 1115 CL"
    assert cliente.get("/semillas/cultivares/INASE-3").json()["ensayos"] == {}  # INASE-3 no es "INASE-30"
    assert cliente.get("/semillas/cultivares/NO-EXISTE").status_code == 404


def test_ficha_de_cultivo_por_variedad_con_su_fuente(cliente, banco_chico):
    ficha = cliente.get("/semillas/cultivares/INASE-1").json()["ficha"]
    assert {f["atributo"]: f["valor"] for f in ficha} == {"ciclo": "intermedio", "tolerancia: herbicidas": "IMI"}
    assert all(f["fuente"] for f in ficha)
    assert "sin dato verificado" in cliente.get("/semillas/cultivares/INASE-9").json()["ficha"]
    r = cliente.get("/semillas/fichas", params={"atributo": "tolerancia"}).json()
    assert [f["valor"] for f in r["filas"]] == ["IMI"]
    assert {c["cultivo"]: c["con_ficha"] for c in r["cobertura"]} == {"Girasol": 1, "Caña de azucar": 0}


def test_rindes_por_defecto_solo_inta_y_cerca_de_san_luis(cliente, banco_chico):
    assert cliente.get("/semillas/ensayos/girasol/rindes").json()["rindes"] == []  # NS 1115 CL es privado
    privados = {"incluir_privadas": True}
    cerca = cliente.get("/semillas/ensayos/girasol/rindes", params=privados).json()["rindes"]
    assert [x["rinde_kg_ha"] for x in cerca] == [3100]
    todos = cliente.get("/semillas/ensayos/girasol/rindes", params={**privados, "cerca_de_san_luis": False}).json()["rindes"]
    assert len(todos) == 2
    resumen = cliente.get("/semillas/ensayos/girasol").json()["resultados"]
    assert [x["cultivar"] for x in resumen] == ["FEBO 817 CL INTA"]
    assert cliente.get("/semillas/ensayos/papa").status_code == 404


def test_sin_archivo_responde_503(cliente, tmp_path, monkeypatch):
    monkeypatch.setenv("ROTATERRA_SEMILLAS_DB", str(tmp_path / "no-esta.sqlite"))
    assert cliente.get("/semillas").status_code == 503


def test_el_archivo_real_viaja_con_la_api(cliente):
    assert semillas.ARCHIVO.exists()
    r = cliente.get("/semillas").json()
    assert r["cultivares"] > 400 and r["fecha_corte_inase"] == "2026-10-28"
    cultivos = {c["cultivo"] for c in r["por_cultivo"]}
    assert {"Trigo", "Caña de azúcar", "Lenteja", "Arveja"} <= cultivos and "Rosa" not in cultivos  # extensivos de todo el país
    for cultivo in semillas.ENSAYOS:
        assert cliente.get(f"/semillas/ensayos/{cultivo}", params={"incluir_privadas": True}).json()["resultados"], cultivo
    sorgo = cliente.get("/semillas/ensayos/sorgo/rindes", params={"cultivar": "EXP-G66"}).json()["rindes"]
    assert sorgo[0]["obtentor_inta"] == "SI"
    trigo = cliente.get("/semillas/ensayos/trigo").json()["resultados"]
    # el banco suma entes públicos (EEAOC, universidades, CONICET) además del INTA (Hernán, 03/11/2026)
    ids = semillas._ids_inta()
    assert trigo and all("INTA" in t["cultivar"].upper() or t.get("obtentor_inta") == "SI"
                         or any(i.strip() in ids for i in str(t.get("cultivar_id_inase") or "").split(";")) for t in trigo)
    algodon = cliente.get("/semillas/ensayos/san_luis/rindes").json()["rindes"]
    assert {a["cultivar"] for a in algodon} == {"GUARANI INTA BGRR"}
    cobertura = {c["cultivo"]: c["con_ficha"] for c in cliente.get("/semillas/fichas").json()["cobertura"]}
    assert cobertura["Soja"] >= 15 and cobertura["Trigo"] > 25 and cobertura["Avena"] > 10  # planillas INASE + fichas INTA
    mani = cliente.get("/semillas/manejo", params={"cultivo": "Maní", "solo_con_dato": True}).json()["filas"]
    assert {"epoca_siembra", "densidad", "cosecha"} <= {m["tema"] for m in mani}
    assert all(m["fuente_url"].startswith("http") for m in mani)
    assert {m["cultivo"] for m in cliente.get("/semillas/manejo").json()["filas"]} >= cultivos  # todos los cultivos del banco
    au = cliente.get("/semillas/ambiente", params={"nivel": "San Luis", "variable": "agua útil máxima"}).json()["filas"]
    assert sorted(int(f["valor"]) for f in au) == [150, 216, 237]  # series de Villa Mercedes, tesis Riglos 2023
    lenteja = cliente.get("/semillas/ambiente", params={"cultivo": "Lenteja"}).json()
    assert lenteja["filas"] and lenteja["por_nivel"]["global"] and lenteja["por_nivel"]["Argentina"]
    assert all(f["nivel"] == "global" for f in lenteja["filas"] if "fao.org" in f["fuente_url"])
    assert cliente.get("/semillas/ambiente", params={"nivel": "Marte"}).status_code == 400
    assert cliente.get("/semillas/ambiente", params={"cultivo": "Rosa"}).status_code == 404


@pytest.mark.con_clave
def test_semillas_pide_clave(monkeypatch):
    monkeypatch.setenv("ROTATERRA_API_KEYS", "clave-de-prueba")
    assert TestClient(api.app).get("/semillas").status_code == 401
