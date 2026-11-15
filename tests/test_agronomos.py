"""Motor de recomendación para agrónomos (spec 064). Todos los datos son SINTÉTICOS, armados para cada caso."""

import math
import os
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from rotaterra.agronomos import motor
from rotaterra.agronomos.motor import PedidoAgronomos, recomendar
from rotaterra.api import app

LAT, LON = -33.7, -65.42


def power_sintetico(anios=12, desplazar_t=0.0, lluvia_verano=3.5, helada_marzo=False):
    """Serie diaria con el clima típico del este de San Luis: verano caluroso y lluvioso, invierno seco y frío."""
    tmax, tmin, ll, ts = {}, {}, {}, {}
    d = date(2000, 1, 1)
    while d <= date(2000 + anios, 4, 30):
        fase = 2 * math.pi * (d.timetuple().tm_yday - 15) / 365  # 15 de enero = lo más caluroso
        media = 16 + 9 * math.cos(fase) + desplazar_t
        k = d.strftime("%Y%m%d")
        tmax[k], tmin[k] = media + 7, media - 7
        if helada_marzo and d.month == 3 and d.day == 1:
            tmin[k] = -5
        verano = d.month in (11, 12, 1, 2, 3)
        # Lluvia en pulsos de una vez por semana (como las tormentas de verano), con el mismo total
        ll[k] = (7 * (lluvia_verano if verano else 0.4)) if d.toordinal() % 7 == 0 else 0.0
        ts[k] = media + 1
        d += timedelta(1)
    return {"properties": {"parameter": {"T2M_MAX": tmax, "T2M_MIN": tmin, "PRECTOTCORR": ll, "TSOIL1": ts}}}


POWER = power_sintetico()


def pedido(**kw):
    base = dict(latitud=LAT, longitud=LON, textura="franco_arenoso", profundidad_cm=120,
                analisis_suelo={"ph": 7.0, "laboratorio": "INTA EEA San Luis", "fecha": "2026-08-01"})
    base.update(kw)
    return PedidoAgronomos(**base)


def por_cultivo(r):
    return {c["cultivo"]: c for c in r["cultivos"]}


def regla(c, id_):
    return next(x for x in c["reglas"] if x["id"] == id_)


def test_respuesta_tiene_los_seis_cultivos_con_reglas_y_fuentes():
    r = recomendar(pedido(), POWER)
    assert {c["cultivo"] for c in r["cultivos"]} == set(motor.CULTIVOS)
    for c in r["cultivos"]:
        assert c["estado"] in ("Recomendable", "Con cuidado", "No recomendable")
        for x in c["reglas"]:
            assert x["resultado"] in ("ok", "aviso", "no", "sin_dato")
            assert x["tipo"] in ("regla", "riesgo_de_clima")
            if x["id"] != "ph" or x["resultado"] != "sin_dato":
                assert x["fuente"] or x["id"] == "ph", x
    assert r["clima"]["campanas"] >= 10
    assert set(r["resumen"]) == {"Recomendable", "Con cuidado", "No recomendable"}


def test_lote_bueno_sale_recomendable():
    r = por_cultivo(recomendar(pedido(), POWER))
    assert r["maiz_tardio"]["estado"] == "Recomendable"
    assert r["sorgo"]["no_pasa"] == []


def test_arenoso_puro_en_secano_descarta_maiz_y_soja_pero_no_con_riego():
    r = por_cultivo(recomendar(pedido(textura="arenoso"), POWER))
    for c in ("maiz", "maiz_tardio", "soja"):
        assert r[c]["estado"] == "No recomendable"
        assert "Textura" in r[c]["no_pasa"]
    assert "Textura" not in r["sorgo"]["no_pasa"]
    r = por_cultivo(recomendar(pedido(textura="arenoso", sistema="riego", riego_mm_campana=300), POWER))
    assert regla(r["maiz"], "textura")["resultado"] == "ok"


def test_arenoso_solo_abajo_no_descarta():
    capas = [{"desde_cm": 0, "hasta_cm": 30, "textura": "franco_arenoso"}, {"desde_cm": 30, "hasta_cm": 100, "textura": "arenoso"}]
    r = por_cultivo(recomendar(pedido(textura="no_sabe", capas_textura=capas), POWER))
    assert regla(r["maiz"], "textura")["resultado"] == "ok"


def test_mani_con_mas_de_35_por_ciento_de_arcilla_no():
    r = por_cultivo(recomendar(pedido(analisis_suelo={"ph": 7.0, "laboratorio": "X", "fecha": "2026-08-01", "arcilla_pct": 40}), POWER))
    assert r["mani"]["estado"] == "No recomendable"
    r = por_cultivo(recomendar(pedido(textura="franco_arcilloso"), POWER))
    assert regla(r["mani"], "textura")["resultado"] == "aviso"


def test_girasol_en_suelo_de_menos_de_40_cm_no():
    r = por_cultivo(recomendar(pedido(profundidad_cm=35), POWER))
    assert "Profundidad del suelo" in r["girasol"]["no_pasa"]


def test_ph_de_laboratorio_alto_descarta_con_la_regla_escalonada():
    r = por_cultivo(recomendar(pedido(analisis_suelo={"ph": 9.5, "laboratorio": "X", "fecha": "2026-08-01"}), POWER))
    assert all(c["estado"] == "No recomendable" for c in r.values())
    r = por_cultivo(recomendar(pedido(analisis_suelo=None), POWER))
    assert regla(r["soja"], "ph")["resultado"] == "sin_dato"


def test_suelo_frio_avisa_y_sugiere_fecha():
    frio = power_sintetico(desplazar_t=-4)
    r = por_cultivo(recomendar(pedido(fechas_siembra={"mani": "10-01"}), frio))
    t = regla(r["mani"], "temperatura_suelo")
    assert t["resultado"] in ("aviso", "no")
    assert r["mani"]["siembra_sugerida_desde"] is not None


def test_suelo_que_nunca_llega_descarta():
    muy_frio = power_sintetico(desplazar_t=-12)
    r = por_cultivo(recomendar(pedido(), muy_frio))
    assert regla(r["mani"], "temperatura_suelo")["resultado"] == "no"


def test_humedad_medida_manda_sobre_la_estimada():
    r = por_cultivo(recomendar(pedido(agua_util_siembra_pct=10), POWER))
    h = regla(r["maiz"], "humedad_siembra")
    assert h["resultado"] == "aviso" and "Medida" in h["dato_del_lote"]
    r2 = recomendar(pedido(), POWER)
    assert any("estimada" in a for a in r2["avisos"])


def test_sin_lluvia_el_agua_del_ciclo_descarta_en_secano_y_no_con_riego():
    seco = power_sintetico(lluvia_verano=0.3)
    r = por_cultivo(recomendar(pedido(), seco))
    assert regla(r["maiz"], "agua_ciclo")["resultado"] == "no"
    r = por_cultivo(recomendar(pedido(sistema="riego", riego_mm_campana=600), seco))
    assert regla(r["maiz"], "agua_ciclo")["resultado"] == "ok"


def test_grados_dia_con_tope_de_30_en_maiz():
    d = {"tmax": 40, "tmin": 20}
    assert motor.grados_dia(d, 8, 30) == pytest.approx((30 + 20) / 2 - 8)
    assert motor.grados_dia(d, 10, None) == pytest.approx(20)
    assert motor.grados_dia({"tmax": 5, "tmin": -5}, 8, 30) == 0


def test_helada_que_corta_el_ciclo_avisa_en_grados_dia():
    r = por_cultivo(recomendar(pedido(fechas_siembra={"soja": "01-20"}), power_sintetico(helada_marzo=True)))
    g = regla(r["soja"], "grados_dia")
    assert g["resultado"] == "aviso" and "helada" in g["dato_del_lote"]


def test_riesgos_de_clima_no_cambian_el_estado():
    r = recomendar(pedido(), POWER)
    for c in r["cultivos"]:
        decide = [x for x in c["reglas"] if x["tipo"] == "regla"]
        if all(x["resultado"] in ("ok", "sin_dato") for x in decide):
            assert c["estado"] == "Recomendable"


def test_sales_maiz_y_soja():
    r = por_cultivo(recomendar(pedido(analisis_suelo={"ph": 8.1, "laboratorio": "X", "fecha": "2026-08-01", "ce_ds_m": 2.5}), POWER))
    assert regla(r["maiz"], "sales")["resultado"] == "aviso"
    assert regla(r["soja"], "sales")["resultado"] == "aviso"
    r = por_cultivo(recomendar(pedido(analisis_suelo={"ph": 7.0, "laboratorio": "X", "fecha": "2026-08-01", "ce_ds_m": 1.0}), POWER))
    assert regla(r["soja"], "sales")["resultado"] == "ok"  # con pH 7 la regla del INTA Marcos Juárez no aplica


def test_validaciones_del_pedido():
    with pytest.raises(ValidationError):
        pedido(fechas_siembra={"soja": "13-40"})
    with pytest.raises(ValidationError):
        pedido(cultivos=["papa"])


def test_serie_corta_da_error():
    with pytest.raises(ValueError):
        recomendar(pedido(), power_sintetico(anios=5))


def test_endpoint_con_power_en_el_pedido():
    claves = os.environ.get("ROTATERRA_API_KEYS")
    cuerpo = pedido(power=POWER).model_dump(mode="json")
    r = TestClient(app).post("/agronomos/recomendacion", json=cuerpo,
                             headers={"X-API-Key": claves.split(",")[0]} if claves else {})
    assert r.status_code == 200, r.text
    assert len(r.json()["cultivos"]) == 6


def test_mediana_de_fechas_con_29_de_febrero():
    assert motor._mediana_fecha([date(2004, 2, 29), date(2005, 3, 1), date(2006, 2, 28)]).strftime("%d/%m") == "29/02"


def _obs_textura(c015, c1530):
    return [{"fecha": "2026-11-14", "variable": v, "valor": c, "unidad": "código", "fuente": "GeoINTA", "resolucion_m": 250, "calidad": "buena"}
            for v, c in (("suelo_textura_0_15cm", c015), ("suelo_textura_15_30cm", c1530))]


def test_solo_arenoso_descarta_areno_franco_no():
    r = por_cultivo(recomendar(pedido(textura="no_sabe", observaciones=_obs_textura(1, 1)), POWER))
    assert "Textura" in r["maiz"]["no_pasa"]
    r = por_cultivo(recomendar(pedido(textura="no_sabe", observaciones=_obs_textura(2, 2)), POWER))
    t = regla(r["maiz"], "textura")
    assert t["resultado"] == "ok" and "Areno franco" in t["dato_del_lote"]


def test_humedad_de_siembra_en_la_capa_de_2_a_8_cm():
    h = regla(por_cultivo(recomendar(pedido(), POWER))["soja"], "humedad_siembra")
    assert "2 a 8 cm" in h["umbral"] and "2 a 8 cm" in h["dato_del_lote"]
    # Sin lluvia la capa de arriba se seca: avisa
    h = regla(por_cultivo(recomendar(pedido(), power_sintetico(lluvia_verano=0.0)))["soja"], "humedad_siembra")
    assert h["resultado"] == "aviso"


def test_regla_1_en_3_no_repetir_la_especie():
    r = por_cultivo(recomendar(pedido(historial=["soja", "mani", "maiz"]), POWER))
    assert "No repetir la especie" in r["mani"]["no_pasa"]        # maní: 3 campañas libres
    assert "No repetir la especie" in r["soja"]["no_pasa"]
    assert regla(r["maiz"], "no_repetir")["resultado"] == "ok"     # maíz hace 3 campañas: 2 libres alcanza
    assert regla(r["girasol"], "no_repetir")["resultado"] == "ok"
    r = por_cultivo(recomendar(pedido(), POWER))
    assert regla(r["sorgo"], "no_repetir")["resultado"] == "sin_dato"


def test_ph_de_la_tabla_de_leandro():
    lab = {"laboratorio": "X", "fecha": "2026-08-01"}
    r = por_cultivo(recomendar(pedido(analisis_suelo={"ph": 8.8, **lab}), POWER))
    assert "pH" not in r["sorgo"]["no_pasa"]       # sorgo hasta 8,8
    assert "pH" not in r["girasol"]["no_pasa"]     # girasol hasta 8,7 (+0,3 tolerable)
    assert "pH" in r["soja"]["no_pasa"]            # soja hasta 8,4: 8,8 se pasa 0,4 (más que la tolerancia de 0,3)


def test_plan_rotacion_trienal():
    r = recomendar(pedido(historial=["maiz"]), POWER)
    assert "plan_rotacion" in r
    assert len(r["plan_rotacion"]) == 3
    assert "rotaciones" in r
    assert all(k in r["rotaciones"] for k in ("1", "2", "3"))
    # Los 3 años deben tener cultivo recomendado asignado y no repetir especie consecutiva
    cultivos = [paso["cultivo"] for paso in r["plan_rotacion"]]
    assert len(set(cultivos)) == 3, f"El plan trienal no debe repetir el mismo cultivo: {cultivos}"
    for paso in r["plan_rotacion"]:
        assert paso["anio"] in (1, 2, 3)
        assert paso["cultivo"] in motor.CULTIVOS
        assert paso["porcentaje_coincidencia"] > 0

    # Si el usuario eligió 'otro', el plan trienal tampoco debe repetir 3 veces el mismo cultivo
    r_otro = recomendar(pedido(historial=["otro"]), POWER)
    cultivos_otro = [paso["cultivo"] for paso in r_otro["plan_rotacion"]]
    assert len(set(cultivos_otro)) == 3, f"Con historial 'otro', el plan no debe repetir el cultivo: {cultivos_otro}"

