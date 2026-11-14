"""Base de semillas extensivas (spec 049): sin internet, con un CSV de INASE en miniatura."""

import csv
import json
from datetime import date

import pytest

from semillas.construir_base import (COLUMNAS_INASE, SIN_DATO, construir, es_inta, eventos_de, guardar,
                                     normalizar)

FILAS = [
    dict(numero="1", cultivar="DM 46R18 STS", especie="SOJA", grupo="OL", inscripcion_rnc="2020-01-01",
         inscripcion_rnpc="2020-01-01", validez_rnpc="2040-01-01", caracteristicas="IV - TR",
         evento_transgenico="MON-Ø4Ø32-6", evento_transgenico_caracteristica="Tolerancia a Glifosato",
         solicitante_rnc="DON MARIO"),
    dict(numero="2", cultivar="ASEM 400 INTA", especie="MANI", grupo="OL", inscripcion_rnc="2013-12-12",
         inscripcion_rnpc="2013-12-12", validez_rnpc="2025-01-01",
         solicitante_rnc="INSTITUTO NACIONAL DE TECNOLOGIA AGROPECUARIA"),
    dict(numero="3", cultivar="DULCINEA", especie="MAIZ", grupo="HT", condicion_genetica="CHOCLO DULCE HIBRIDO",
         inscripcion_rnc="2026-10-23"),
    dict(numero="4", cultivar="TOMATITO", especie="TOMATE", grupo="HT", inscripcion_rnc="2001-01-01"),
    dict(numero="5", cultivar="AX 7761", especie="MAIZ", grupo="CE", condicion_genetica="HIBRIDO SIMPLE",
         inscripcion_rnc="2019-05-05", caracteristicas="TR",
         evento_transgenico="MON-89Ø34-3 x DAS-Ø15Ø7-1 x MON-ØØ6Ø3-6",
         evento_transgenico_caracteristica="Resistencia a Lepidópteros", solicitante_rnc="NIDERA"),
]


@pytest.fixture
def catalogo(tmp_path):
    ruta = tmp_path / "catalogo.csv"
    with ruta.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS_INASE)
        w.writeheader()
        for fila in FILAS:
            w.writerow({c: fila.get(c, "") for c in COLUMNAS_INASE})
    return ruta


def test_solo_entran_cultivos_extensivos_y_se_marca_el_destino(catalogo):
    t = construir(catalogo)
    por_nombre = {c["cultivar"]: c for c in t["cultivares"]}
    assert "TOMATITO" not in por_nombre
    assert por_nombre["DULCINEA"]["extensivo"] == "NO"
    assert por_nombre["AX 7761"]["subtipo"] == "Maíz granífero"
    assert por_nombre["AX 7761"]["tipo_material"] == "Híbrido"


def test_nada_se_inventa(catalogo):
    t = construir(catalogo)
    mani = next(c for c in t["cultivares"] if c["especie"] == "MANI")
    assert mani["estado_ogm"] == "Sin evento declarado en este registro"  # no "convencional confirmada"
    assert mani["disponibilidad_comercial"] == SIN_DATO
    assert mani["precio_semilla"] == SIN_DATO
    assert mani["tipo_material"] == SIN_DATO
    assert all(p["con_disponibilidad_comercial_verificada"] == 0 for p in t["perfiles"])


def test_rnpc_vigente_segun_fecha_de_corte(catalogo):
    t = construir(catalogo)
    estados = {c["cultivar"]: c["estado_rnpc"] for c in t["cultivares"]}
    assert t["_meta"][0]["fecha_corte"] == "2026-10-23"  # la inscripción más reciente del archivo
    assert estados["DM 46R18 STS"].startswith("RNPC_PROTEGIDO")
    assert estados["ASEM 400 INTA"] == "Protección RNPC vencida al corte"
    assert estados["DULCINEA"] == "Sin inscripción RNPC en el registro"
    t = construir(catalogo, fecha_corte=date(2050, 1, 1))
    assert {c["cultivar"]: c["estado_rnpc"] for c in t["cultivares"]}["DM 46R18 STS"] == "Protección RNPC vencida al corte"


def test_eventos_apilados_se_separan():
    assert eventos_de("MON-89Ø34-3 x DAS-Ø15Ø7-1 x MON-ØØ6Ø3-6") == ["MON-89034-3", "DAS-01507-1", "MON-00603-6"]
    assert eventos_de("DAS-Ø15Ø7-1 x DAS4Ø278-9") == ["DAS-01507-1", "DAS-40278-9"]
    assert eventos_de("DAS-Ø15Ø7-1 x MON-ØØ81Ø-6 y MON-ØØ81Ø-6 x DAS-Ø15Ø7-1") == ["DAS-01507-1", "MON-00810-6"]


def test_soja_guarda_grupo_de_madurez_y_eventos(catalogo):
    t = construir(catalogo)
    soja = next(c for c in t["cultivares"] if c["especie"] == "SOJA")
    assert soja["grupo_madurez"] == "IV"
    assert soja["eventos_ogm"] == "MON-04032-6"
    evento = next(e for e in t["eventos_ogm"] if e["evento"] == "MON-04032-6")
    assert evento["rasgo_segun_inase"] == "Tolerancia a Glifosato"
    assert evento["autorizacion_comercial"].startswith("pendiente")


def test_obtentor_inta_en_sus_distintas_formas():
    assert es_inta("INSTITUTO NACIONAL DE TECNOLOGIA AGROPECUARIA")
    assert es_inta("INST. NAC.TEC. AGROPECUARIA")
    assert es_inta("INTA E.E.A.SAN PEDRO")
    assert not es_inta("PINTADO S.A.")


def test_conciliacion_inta_no_fusiona_por_parecido(catalogo):
    t = construir(catalogo)
    asem = {c["nombre_en_documento_ssd"]: c for c in t["candidatos_inta"] if c["perfil_ssd"] == "Maní"}
    assert asem["ASEM 400 INTA"]["estado_conciliacion"] == "EXACTO"
    assert asem["ASEM 400 INTA"]["cultivar_id_inase"] == "INASE-2"
    assert asem["ASEM 505 INTA"]["estado_conciliacion"].startswith("NO_ENCONTRADO")
    assert normalizar("Ñu Poty INTA CL") == "NU POTY INTA CL"


def test_guardar_deja_manifiesto_con_hash(catalogo, tmp_path):
    t = construir(catalogo)
    m = guardar(t, tmp_path / "salida", catalogo)
    assert len(m["sha256"]) == 64
    assert m["tablas"]["cultivares"] == 4
    assert json.loads((tmp_path / "salida" / "manifiesto.json").read_text(encoding="utf-8"))["filas_fuente"] == 5
    assert (tmp_path / "salida" / "fuentes.csv").exists()


def test_oferta_se_cruza_con_inase_sin_unir_por_parecido(catalogo, tmp_path):
    oferta = tmp_path / "oferta.csv"
    oferta.write_text(
        "perfil_ssd,material,tipo_evidencia\n"
        "Soja,DM 46R18 STS,LANZAMIENTO_DECLARADO\n"
        "Maíz,AX 7761 VT3 PRO,CATALOGO_EMPRESA\n"
        "Maní,ASEM 999 INTA,USO_DECLARADO_SISA\n", encoding="utf-8")
    filas = {o["material"]: o for o in construir(catalogo, ruta_oferta=oferta)["oferta_comercial"]}
    assert filas["DM 46R18 STS"]["estado_en_inase"].startswith("INSCRIPTO")
    assert filas["DM 46R18 STS"]["disponibilidad_comercial"].startswith("OFERTA_DECLARADA")
    assert filas["AX 7761 VT3 PRO"]["estado_en_inase"].startswith("PARA_REVISION")  # otra sigla de tecnología
    assert filas["ASEM 999 INTA"]["estado_en_inase"].startswith("NO_ENCONTRADO")
    assert filas["ASEM 999 INTA"]["disponibilidad_comercial"] == SIN_DATO


def test_nucleo_ignora_siglas_de_tecnologia():
    from semillas.construir_base import nucleo
    assert nucleo("LT 722 VT3 PRO") == nucleo("LT722VT3P") == ("LT", "722")
    assert nucleo("DM 46E25") == nucleo("DM46E25 SE") == ("DM", "46E25")
    assert nucleo("STAR 7718") != nucleo("ARG 7718")


def test_catalogo_inta_suma_licencia_y_no_duplica_por_registro(catalogo, tmp_path):
    inta = tmp_path / "catalogo_inta.csv"
    inta.write_text(
        "grupo,especie,variedad,unidad,situacion_registral,fecha_inscripcion,tipo_licencia,licenciatario\n"
        "Industriales,Maní,ASEM 400 INTA,EEA Manfredi,Registro Nacional de Cultivares (RNC),2013-12-12,Licencia exclusiva,Semillero X\n"
        "Industriales,Maní,ASEM 400 INTA,EEA Manfredi,Registro Nacional de la Propiedad de Cultivares (RNPC),2013-12-12,Licencia exclusiva,Semillero X\n"
        "Industriales,Maní,ASEM 999 INTA,EEA Manfredi,Registro Nacional de Cultivares (RNC),2010-01-01,Sin licencia,\n",
        encoding="utf-8")
    t = construir(catalogo, ruta_catalogo_inta=inta)
    asem = next(c for c in t["cultivares_inta"] if c["cultivar"] == "ASEM 400 INTA")
    assert asem["en_catalogo_inta"] == "EXACTO"  # una fila RNC y otra RNPC no son un conflicto
    assert asem["licenciatario"] == "Semillero X"
    assert asem["disponibilidad_comercial"].startswith("licenciada a Semillero X")
    assert [v["variedad"] for v in t["catalogo_inta_sin_inase"]] == ["ASEM 999 INTA"]


def test_registro_solo_rnpc_no_se_toma_como_semilla_vendible(tmp_path):
    ruta = tmp_path / "catalogo.csv"
    with ruta.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS_INASE)
        w.writeheader()
        w.writerow({c: dict(numero="20", cultivar="L 123", especie="GIRASOL", grupo="OL", condicion_genetica="LINEA",
                            inscripcion_rnpc="2020-01-01", validez_rnpc="2040-01-01").get(c, "") for c in COLUMNAS_INASE})
    t = construir(ruta, fecha_corte=date(2026, 10, 28), ruta_oferta=None, ruta_catalogo_inta=None)
    linea = t["cultivares"][0]
    assert linea["estado_registral"].startswith("SOLO_RNPC")
    assert linea["extensivo"] == "REVISAR"
    assert linea["tipo_material"] == "Línea (parental de híbridos)"


def _recso_mini(tmp_path):
    prefijo = tmp_path / "recso"
    (tmp_path / "recso_ensayos.csv").write_text("ensayo_id,provincia\nE1,San Luis\nE2,Buenos Aires\n", encoding="utf-8")
    (tmp_path / "recso_cultivares.csv").write_text(
        "cultivar,empresa,grupo_madurez_recso,fuente_url\nDM 46R18 STS,DON MARIO,IV largo,u\nCZ 1846 STS,BASF,IV largo,u\n",
        encoding="utf-8")
    cab = "ensayo_id,cultivar,rinde_kg_ha,rinde_relativo_pct,grupo_estadistico,en_analisis_conjunto,referencia_san_luis\n"
    (tmp_path / "recso_rindes.csv").write_text(cab +
        "E1,DM 46R18 STS,3800,110.0,+,SI,SAN_LUIS (ensayo en la provincia)\n"
        "E2,DM 46R18 STS,5000,90.0,,SI,OTRA_REGION\n"
        "E3,DM 46R18 STS,1000,50.0,,NO,OTRA_REGION\n"
        "E1,CZ 1846 STS,3000,90.0,,SI,SAN_LUIS (ensayo en la provincia)\n", encoding="utf-8")
    return prefijo


def test_recso_separa_san_luis_del_pais_y_descarta_ensayos_fuera_del_analisis(catalogo, tmp_path):
    t = construir(catalogo, prefijo_recso=_recso_mini(tmp_path))
    r = {x["cultivar"]: x for x in t["recso_resumen_cultivar"]}
    dm = r["DM 46R18 STS"]
    assert dm["ensayos_pais"] == 2  # el ensayo que el INTA dejó fuera no cuenta
    assert dm["rinde_relativo_pais_pct"] == 100.0
    assert dm["ensayos_san_luis_y_vecinos"] == 1 and dm["rinde_relativo_san_luis_y_vecinos_pct"] == 110.0
    assert dm["en_grupo_superior_san_luis_y_vecinos"] == 1 and dm["rinde_kg_ha_en_san_luis"] == "3800"
    assert dm["estado_en_inase"].startswith("INSCRIPTO") and dm["cultivar_id_inase"] == "INASE-1"
    assert r["CZ 1846 STS"]["estado_en_inase"].startswith("NO_ENCONTRADO")
    assert len(t["recso_rindes"]) == 4 and len(t["recso_ensayos"]) == 2


def test_recso_datos_reales_cierran_con_el_informe():
    """Cada ensayo cargado tiene que coincidir con la MEDIA impresa y no repetir cultivar."""
    from collections import Counter
    from semillas.construir_base import RECSO
    with RECSO.with_name(RECSO.name + "_ensayos.csv").open(encoding="utf-8") as f:
        ensayos = list(csv.DictReader(f))
    with RECSO.with_name(RECSO.name + "_rindes.csv").open(encoding="utf-8") as f:
        rindes = list(csv.DictReader(f))
    assert len(ensayos) == 351
    por_ensayo = {}
    for r in rindes:
        por_ensayo.setdefault(r["ensayo_id"], []).append(r)
    for e in ensayos:
        filas = por_ensayo[e["ensayo_id"]]
        media = sum(int(r["rinde_kg_ha"]) for r in filas) / len(filas)
        assert abs(media - int(e["rinde_medio_kg_ha"])) / int(e["rinde_medio_kg_ha"]) < 0.02, e["ensayo_id"]
        assert max(Counter(r["cultivar"] for r in filas).values()) == 1, e["ensayo_id"]
        assert all(r["cultivar"] for r in filas)
    assert {e["localidad"] for e in ensayos if e["provincia"] == "San Luis"} == {"Cte. Granville"}


def test_recso_suma_varias_campanas_de_la_subregion(catalogo, tmp_path):
    prefijo = _recso_mini(tmp_path)
    (tmp_path / "recso_multianual.csv").write_text(
        "cultivar,subregion,periodo,rinde_relativo_al_testigo_pct,ensayos_en_el_periodo\n"
        "DM 46R18 STS,II-3,2023/24 a 2025/26 (3 campañas),104,12\n"
        "DM 46R18 STS,II-4,2023/24 a 2025/26 (3 campañas),90,60\n", encoding="utf-8")
    t = construir(catalogo, prefijo_recso=prefijo)
    dm = next(x for x in t["recso_resumen_cultivar"] if x["cultivar"] == "DM 46R18 STS")
    assert dm["II-3_3_campanas_pct_testigo"] == "104 (12 ensayos)"
    assert dm["II-5_3_campanas_pct_testigo"] == "" and dm["II-3_2_campanas_pct_testigo"] == ""
    assert len(t["recso_multianual"]) == 2


def test_ret_trigo_separa_la_subregion_de_san_luis(catalogo, tmp_path):
    (tmp_path / "ret_ensayos.csv").write_text("ensayo_id\nT1\nT2\n", encoding="utf-8")
    cab = "ensayo_id,campana,cultivar,clave_nombre,nombre_en_planilla,rinde_relativo_pct,referencia_san_luis\n"
    (tmp_path / "ret_rindes.csv").write_text(cab +
        "T1,2024/25,KLEIN X,X,K. X,110.0,SAN_LUIS_MISMA_SUBREGION (PSC)\n"
        "T2,2024/25,KLEIN X,X,KLEIN X,94.0,OTRA_REGION\n", encoding="utf-8")
    t = construir(catalogo, prefijo_ret=tmp_path / "ret")
    x = t["ret_resumen_cultivar"][0]
    assert x["ensayos_pais"] == 2 and x["rinde_relativo_pais_pct"] == 102.0
    assert x["ensayos_pampa_semiarida_central"] == 1 and x["rinde_relativo_pampa_semiarida_central_pct"] == 110.0
    assert x["nombres_en_planillas"] == "K. X; KLEIN X"
    assert x["estado_en_inase"].startswith("NO_ENCONTRADO")


def test_ret_datos_reales():
    from semillas.construir_base import RET
    with RET.with_name(RET.name + "_ensayos.csv").open(encoding="utf-8") as f:
        ensayos = list(csv.DictReader(f))
    with RET.with_name(RET.name + "_rindes.csv").open(encoding="utf-8") as f:
        rindes = list(csv.DictReader(f))
    assert {e["campana"] for e in ensayos} == {f"{a}/{(a + 1) % 100:02d}" for a in range(2018, 2026)}
    assert {e["sitio"] for e in ensayos if e["subregion_2021"].startswith("9 ")} == {"Anguil"}
    ids = {e["ensayo_id"] for e in ensayos}
    assert len(ids) == len(ensayos) and all(r["ensayo_id"] in ids for r in rindes)
    assert all(100 < int(r["rinde_kg_ha"]) < 15000 for r in rindes)  # Anguil 2019 y 2024 tuvieron sequía: hay rindes de 300 kg/ha
    assert not any(r["cultivar"].upper().startswith(("CV", "DMS", "PROMEDIO")) for r in rindes)


def test_girasol_deja_fuera_los_testigos_anonimos(catalogo, tmp_path):
    (tmp_path / "gir_ensayos.csv").write_text("ensayo_id\nG1\n", encoding="utf-8")
    cab = "ensayo_id,campana,cultivar,empresa,es_testigo_anonimo,rinde_relativo_pct,aceite_pct,referencia_san_luis\n"
    (tmp_path / "gir_rindes.csv").write_text(cab +
        "G1,2025/26,NS 1113 CL,Nidera,NO,105.0,50.0,SEMIARIDA_VECINA (La Pampa)\n"
        "G1,2025/26,Testigo 1,TESTIGO,SI,95.0,48.0,SEMIARIDA_VECINA (La Pampa)\n", encoding="utf-8")
    t = construir(catalogo, prefijo_girasol=tmp_path / "gir")
    assert [x["cultivar"] for x in t["girasol_resumen_cultivar"]] == ["NS 1113 CL"]
    assert t["girasol_resumen_cultivar"][0]["aceite_vecinas_pct"] == 50.0
    assert len(t["girasol_rindes"]) == 2


def test_maiz_resume_por_hibrido_y_vecinas(catalogo, tmp_path):
    (tmp_path / "mz_ensayos.csv").write_text("ensayo_id\nM1\nM2\n", encoding="utf-8")
    cab = "ensayo_id,campana,sitio,hibrido,empresa,nombre_en_planilla,rinde_kg_ha,rinde_relativo_pct,referencia_san_luis\n"
    (tmp_path / "mz_rindes.csv").write_text(cab +
        "M1,2025/26,Mattaldi,NK 835 VIP3,SYNGENTA,NK 835 VIP3,,,SEMIARIDA_VECINA (sur de Córdoba)\n"
        "M2,2025/26,Bell Ville,NK 835 VIP3,SYNGENTA,NK 835 VIP3,12000,110.0,OTRA_REGION\n", encoding="utf-8")
    t = construir(catalogo, prefijo_maiz=tmp_path / "mz")
    r = t["maiz_resumen_hibrido"][0]
    assert (r["ensayos_total"], r["ensayos_vecinas_san_luis"], r["rinde_relativo_total_pct"]) == (1, 0, 110.0)  # sin dato no cuenta


def test_maiz_datos_reales_cuadran():
    from semillas.construir_base import MAIZ
    with MAIZ.with_name(MAIZ.name + "_ensayos.csv").open(encoding="utf-8-sig") as f:
        ensayos = list(csv.DictReader(f))
    with MAIZ.with_name(MAIZ.name + "_rindes.csv").open(encoding="utf-8-sig") as f:
        rindes = list(csv.DictReader(f))
    assert len(ensayos) == 25 and all(r["hibrido"] for r in rindes)
    assert {e["sitio"] for e in ensayos if e["referencia_san_luis"].startswith("SAN_LUIS")} == {"Villa Mercedes", "Tilisarao"}
    medias = {(e["campana"], e["sitio"], e["epoca_siembra"]): int(e["rinde_medio_kg_ha"]) for e in ensayos}
    assert medias[("2025/26", "Mattaldi", "temprana")] == 8878  # promedio impreso en el informe
    assert medias[("2024/25", "General Villegas", "tardía")] == 13078
    assert all(2000 < int(r["rinde_kg_ha"]) < 20000 for r in rindes if r["rinde_kg_ha"])


def test_sorgo_manfredi_cuadra_con_el_informe(catalogo):
    t = construir(catalogo)
    rindes = t["sorgo_rindes"]
    assert len(rindes) == 40 and round(sum(int(r["rinde_kg_ha"]) for r in rindes) / 40) == 6798  # media impresa
    inta = [r for r in rindes if r["obtentor_inta"] == "SI"]
    assert [r["hibrido"] for r in inta] == ["EXP-G66"] and inta[0]["sin_diferencia_con_el_mejor"] == "SI"


def test_ensayos_en_san_luis_cuadran_y_se_cruzan_con_inase(catalogo):
    t = construir(catalogo)
    rindes = t["san_luis_rindes"]
    assert {e["ensayo_id"] for e in t["san_luis_ensayos"]} == {r["ensayo_id"] for r in rindes} and len(rindes) == 59
    tilisarao = [int(r["rinde_kg_ha"]) for r in rindes if r["ensayo_id"] == "MAIZ-HIBRIDOS-TILISARAO"]
    assert len(tilisarao) == 23 and abs(sum(tilisarao) / 23 - 8522) <= 2  # media impresa de los híbridos
    sorgo = [r for r in rindes if r["cultivo"] == "Sorgo"]
    assert all(r["estado_en_inase"] == "SIN_NOMBRE en el informe" for r in sorgo)  # el informe no los nombra


def test_banco_inta_trae_solo_extensivos_del_inta_y_ninguno_privado(tmp_path):
    ruta = tmp_path / "c.csv"
    filas = FILAS + [dict(numero="6", cultivar="PLATENSE INTA", especie="TOMATE", grupo="HT", inscripcion_rnc="2001-01-01",
                          solicitante_rnc="INST. NAC.TEC. AGROPECUARIA"),
                     dict(numero="7", cultivar="TUC 95-10", especie="CAÑA DE AZUCAR", grupo="CI", inscripcion_rnc="2010-01-01",
                          solicitante_rnc="INTA E.E.A. FAMAILLA"),
                     dict(numero="8", cultivar="ROSA INTA", especie="ROSA", grupo="OR", inscripcion_rnc="2010-01-01",
                          solicitante_rnc="INTA")]
    with ruta.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS_INASE); w.writeheader()
        w.writerows({c: fila.get(c, "") for c in COLUMNAS_INASE} for fila in filas)
    tablas = construir(ruta, fecha_corte=date(2026, 10, 28), ruta_oferta=None, ruta_catalogo_inta=None)
    banco = tablas["banco_inta"]
    assert {b["cultivar"]: b["cultivo"] for b in banco} == {"ASEM 400 INTA": "Maní", "TUC 95-10": "Caña de azúcar"}  # sin tomate ni rosa
    assert all(b["obtentor_inta"] == "SI" for b in banco)
    # la ficha del maní viene de lo transcripto, cada dato con su fuente; solo variedades del banco
    asem = {b["cultivar_id"] for b in banco if b["cultivar"] == "ASEM 400 INTA"}
    assert tablas["fichas_inta"] and {f["cultivar_id"] for f in tablas["fichas_inta"]} <= {b["cultivar_id"] for b in banco}
    assert {f["cultivar_id"] for f in tablas["fichas_inta"]} & asem
    assert all(f["fuente"] and f["fuente_url"].startswith("http") for f in tablas["fichas_inta"])
    # manejo: cada cultivo del banco tiene los temas de la guía, con dato y fuente o "sin dato verificado"
    from semillas.manejo import SIN_DATO, TEMAS
    mani = [m for m in tablas["manejo_cultivos"] if m["cultivo"] == "Maní"]
    assert {t for t, _ in TEMAS} <= {m["tema"] for m in mani}
    assert any(m["valor"] != SIN_DATO for m in mani)
    assert all(m["valor"] == SIN_DATO or m["fuente_url"].startswith("http") for m in tablas["manejo_cultivos"])


def test_manejo_transcripto_tiene_fuente_oficial_y_temas_conocidos():
    from urllib.parse import urlparse
    from semillas.manejo import TEMAS, leer
    temas = {t for t, _ in TEMAS} | {"zona", "manejo", "aptitud_san_luis"}
    # organismos oficiales, revistas científicas y libros de universidades nacionales (el del garbanzo de la UNC solo
    # se pudo bajar de la copia que publicó Bichos de Campo)
    OFICIALES = {"www.argentina.gob.ar", "repositorio.inta.gob.ar", "magyp.gob.ar", "sedici.unlp.edu.ar",
                 "libros.unlp.edu.ar", "www.scielo.org.ar", "bichosdecampo.com",
                 "www.produccion-animal.com.ar"}
    NO_GOB_CON_AUTOR_INTA = {"fecic.org.ar"}  # manual de FECIC con capítulo escrito por INTA Corrientes
    for f in leer():
        assert f["valor"] and f["fuente"] and f["verificacion"], f
        # desde el 31/10/2026 Hernán acepta cualquier sitio sobre cultivos, marcado "No oficial"
        assert urlparse(f["fuente_url"]).hostname in OFICIALES or f["fuente"].startswith("No oficial") \
            or urlparse(f["fuente_url"]).hostname in NO_GOB_CON_AUTOR_INTA, f
        assert f["tema"].split(" (")[0] in temas, f


def test_ambiente_por_especie_guarda_fuente_y_nivel_y_separa_fao():
    from semillas import ambiente
    filas = ambiente.armar()
    cotejo = ambiente.cotejo()
    assert len(filas) > 1500
    for f in filas:
        assert list(f) == ambiente.COLUMNAS, f
        assert f["valor"] and f["fuente"] and f["pestana"], f
        c = cotejo.get(tuple(f[k] for k in ambiente.CLAVE)) or \
            next((r for k, r in cotejo.items() if r["variable_corregida"] == f["variable"] and k[-1] == f["valor"]), None) or \
            next((r for k, r in cotejo.items() if r["valor_corregido"] == f["valor"] and k[3] == f["variable"]), None)
        assert f["verificacion"] == (c["verificacion"] if c else ambiente.LEIDAS.get(f["pestana"], ambiente.VERIFICACION)), f
        assert f["nivel"] in ambiente.NIVELES, f
        if "fao.org" in f["fuente_url"]:
            assert f["nivel"] == "global", f  # FAO entra solo como referencia global (Hernán, 31/10/2026)
    # agua útil de las series de suelo de Villa Mercedes (tesis Riglos 2023), sin las cuentas de escenario del dossier
    au = {f["sitio"].split(",")[0]: f["valor"] for f in filas if f["variable"] == "agua útil máxima hasta 210 cm"}
    assert au == {"Serie Buena Esperanza": "150", "Serie Cramer": "216", "Serie Granville": "237"}
    assert all(f["nivel"] == "San Luis" for f in filas if f["pestana"].startswith("A11_"))
    # los huecos anotados ("sin dato verificado") no son datos, y lupino no está en el banco
    assert not any(f["valor"].lower().startswith("sin dato") for f in filas)
    assert all(f["cultivo_banco"] == "" for f in filas if f["cultivo"].startswith("Lupino"))
    assert {f["cultivo_banco"] for f in filas if f["cultivo"] == "Sorgo granífero"} == {"Sorgo"}
    # cotejo fila por fila con los PDFs que subió Hernán (31/10/2026)
    assert not any("<function" in f["variable"] for f in filas)
    lluvia = [f for f in filas if f["pestana"].startswith("A40") and f["variable"] == "Lluvia acumulada en ciclo"]
    assert [f["valor"] for f in lluvia] == ["535"] and "decía 524" in lluvia[0]["advertencia"]
    heladas = {(f["cultivo"], f["etapa"]): f for f in filas if f["pestana"].startswith("A08") and "13881" in f["fuente_url"]}
    assert heladas[("Trigo", "Floración")]["valor"] == "-1" and heladas[("Trigo", "Floración")]["verificacion"].startswith("cotejado")
    assert all(f["verificacion"].startswith("no se pudo") for f in filas if f["variable"] == "agua útil (Cada 20 cm)")


def test_fichas_un_valor_por_atributo_y_gana_la_primera_fuente():
    from semillas.fichas import unir
    filas = [dict(cultivar_id="A", atributo="ciclo", valor="largo", fuente="INASE"),
             dict(cultivar_id="A", atributo="ciclo", valor="intermedio", fuente="noticia"),
             dict(cultivar_id="A", atributo="zona", valor="pampeana", fuente="noticia")]
    assert [(f["atributo"], f["valor"]) for f in unir(filas)] == [("ciclo", "largo"), ("zona", "pampeana")]


def test_exportar_sqlite_tipa_columnas_y_guarda_el_manifiesto(tmp_path):
    import sqlite3
    from semillas.exportar_sqlite import exportar
    (tmp_path / "cultivares.csv").write_text("cultivar_id,cultivar,rinde,nota\nA-1,0357 CL,10,\nA-2,ACA 220,12.5,x\n", encoding="utf-8-sig")
    (tmp_path / "vacia.csv").write_text("sin_filas\n", encoding="utf-8")
    (tmp_path / "manifiesto.json").write_text('{"fecha_corte": "2026-10-28", "tablas": {"cultivares": 2}}', encoding="utf-8")
    assert exportar(tmp_path, tmp_path / "s.sqlite") == {"cultivares": 2}
    db = sqlite3.connect(tmp_path / "s.sqlite")
    tipos = {r[1]: r[2] for r in db.execute('PRAGMA table_info("cultivares")')}
    assert tipos == {"cultivar_id": "TEXT", "cultivar": "TEXT", "rinde": "REAL", "nota": "TEXT"}
    assert db.execute("SELECT cultivar FROM cultivares WHERE cultivar_id='A-1'").fetchone() == ("0357 CL",)
    assert dict(db.execute("SELECT * FROM _manifiesto"))["fecha_corte"] == "2026-10-28"


def test_ficha_basica_del_registro_solo_para_las_que_no_tienen_datos():
    from semillas.fichas import registro_basico, PREFIJO_REGISTRO
    import csv
    from pathlib import Path
    crudo = Path(__file__).resolve().parent.parent / "semillas" / "datos" / "raw" / "inase" / "catalogo_inase_2026-10-28.csv"
    r = next(x for x in csv.DictReader(open(crudo, encoding="utf-8-sig")) if x["cultivar"] == "TONELERO INTA")
    banco = [dict(cultivar_id=f"INASE-{r['numero']}", cultivar="TONELERO INTA", cultivo="Sorgo", licenciatario="")]
    filas = registro_basico(banco, set())
    assert filas and all(f["atributo"].startswith(PREFIJO_REGISTRO) and "INASE" in f["fuente"] for f in filas)
    assert {f["atributo"] for f in filas} >= {PREFIJO_REGISTRO + "especie", PREFIJO_REGISTRO + "inscripto en el registro (RNC)"}
    assert registro_basico(banco, {banco[0]["cultivar_id"]}) == []  # si ya tiene ficha, no se agrega la básica


def test_ficha_tecnica_ordena_por_seccion():
    from semillas.ficha_tecnica import seccion
    assert seccion("ciclo") == "Ciclo y fenología"
    assert seccion("USDA GRIN: aceite en grano (%)") == "Calidad del grano"
    assert seccion("sanidad: roya de la hoja") == "Sanidad y plagas"
    assert seccion("cosecha") == "Zona, siembra y manejo"


def test_ficha_tecnica_indice_de_cosecha_es_rendimiento():
    from semillas.ficha_tecnica import seccion
    assert seccion("índice de cosecha") == "Rendimiento"
