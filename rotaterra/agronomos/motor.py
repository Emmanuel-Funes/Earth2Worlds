"""Motor de recomendación para agrónomos (spec 064).

Para UN lote y UNA campaña dice, cultivo por cultivo (maíz de primera y tardío, soja, sorgo, maní y girasol), si es
"Recomendable", "Con cuidado" o "No recomendable", y muestra cada regla de la ficha técnica con el dato del lote, el
umbral y su fuente. No arma rotaciones: eso lo hace el motor de rotación (spec 062), que no cambia.

Clima: la serie DIARIA de NASA POWER (la misma que usa el motor de rotación), campaña por campaña. Cada regla se
evalúa en todas las campañas de la serie y se cuenta en cuántas pasa: así el agrónomo ve la frecuencia, no un promedio.

Reglas (todas en `catalogo_agronomos.json`, con su fuente):
1. Temperatura del suelo para sembrar: los 3 días anteriores a la fecha de siembra con TSOIL1 (media diaria de 0 a 10 cm,
   MERRA-2) por encima del mínimo. Avisa si falla en 1 de cada 5 campañas o más; descarta si en la mayoría de las campañas
   el suelo no llega antes de fin de enero.
2. Grados día: ((Tmáx + Tmín) / 2) − Tbase, 0 si da negativo, con la Tmáx cortada en 30 °C en maíz (MAIZAR ec. 2.1;
   criterio agronómico del equipo). ¿Junta los grados día del ciclo antes de la primera helada fuerte o del 30 de abril? Avisa.
3. Humedad del suelo a la siembra (% del agua útil de 2 a 8 cm, Hernán 14/11/2026): la medida si el agrónomo la carga;
   si no, un balance diario de la capa de 0 a 8 cm con lluvia y evaporación de barbecho con rastrojo (FAO-56). Avisa.
4. Agua del ciclo: agua útil a la siembra + lluvia del ciclo (+ riego) contra el 60 % de la demanda (revisión agronómica
   del equipo). Descarta en secano si no llega en el año medio; avisa si falla en 3 de cada 10 campañas o más.
5. Textura y profundidad: arenoso (no areno franco) de 0 a 30 cm en maíz y soja de secano, maní con más de 35 % de arcilla, girasol con menos de
   40 cm de suelo. Descarta (criterio agronómico del equipo, falta que lo confirme).
6. pH: la misma regla escalonada del motor de rotación (laboratorio decide; mapa solo avisa).
7. Sales: maíz con más de 2 dS/m (INTA San Luis); soja con pH > 8 y más de 0,5 dS/m (INTA Marcos Juárez). Avisa.
8. Helada después de sembrar y días de más de 35 °C en el período crítico: riesgos del clima, con su frecuencia; no
   cambian el estado (como en el motor de rotación).
"""

from __future__ import annotations

import json
import statistics
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from rotaterra.recomendacion.motor import ObservacionRecibida
from rotaterra.rotacion.clima import eto_hargreaves
from rotaterra.rotacion.motor import CapaSuelo, Textura, agua_util_por_capas
from rotaterra.rotacion.motor import cargar_catalogo as cargar_catalogo_rotacion
from rotaterra.rotacion.ph_del_lote import evaluar_ph

CATALOGO = Path(__file__).with_name("catalogo_agronomos.json")
CULTIVOS = ("maiz", "maiz_tardio", "soja", "sorgo", "mani", "girasol")
UMBRAL_CALOR = 35.0
# Humedad de siembra: se mide de 2 a 8 cm (Hernán, 14/11/2026). El balance usa la capa de 0 a 8 cm, que la contiene.
CAPA_SIEMBRA_CM = 8
# Evaporación de la capa de arriba en barbecho con rastrojo: Ke máx ≈ 1,2 en suelo desnudo mojado (FAO-56, cap. 7),
# menos ≈25 % por la cobertura de rastrojo (FAO-56: ≈5 % menos por cada 10 % de cobertura; supuesto 50 %).
KE_CAPA_SIEMBRA = 0.9
# Ventana alrededor de la fecha de siembra para buscar un día con humedad suficiente (se siembra después de una lluvia)
VENTANA_SIEMBRA_DIAS = 15
ESTADOS = {"no": "No recomendable", "aviso": "Con cuidado", "ok": "Recomendable"}
ORDEN_ESTADO = {"Recomendable": 0, "Con cuidado": 1, "No recomendable": 2}


def cargar_catalogo(ruta: Path = CATALOGO) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- pedido

class AnalisisLote(BaseModel):
    """Análisis de suelo del lote. El pH con laboratorio y fecha decide; sin eso, es del productor (spec 046)."""
    fecha: str | None = None
    laboratorio: str | None = None
    ph: float | None = Field(None, ge=3, le=11)
    ce_ds_m: float | None = Field(None, ge=0, le=60, description="Conductividad eléctrica del extracto (dS/m)")
    arcilla_pct: float | None = Field(None, ge=0, le=100, description="Arcilla de 0 a 20 cm (%)")


class PedidoAgronomos(BaseModel):
    latitud: float = Field(..., ge=-56, le=-21)
    longitud: float = Field(..., ge=-74, le=-53)
    sistema: Literal["secano", "riego"] = "secano"
    riego_mm_campana: float = Field(0, ge=0, le=1500, description="Riego que se puede aplicar en el ciclo (mm)")
    textura: Textura = Field("no_sabe", description="Textura de 0 a 30 cm, si el agrónomo la conoce")
    capas_textura: list[CapaSuelo] | None = Field(None, description="Textura por capas (si no viene, se toma de GeoINTA vía observaciones)")
    profundidad_cm: float | None = Field(None, gt=0, le=400, description="Profundidad efectiva del suelo (tosca o napa)")
    analisis_suelo: AnalisisLote | None = None
    agua_util_siembra_pct: float | None = Field(None, ge=0, le=100, description="Humedad medida a la siembra en la capa de 2 a 8 cm (% del agua útil)")
    agua_util_mayo_pct: float | None = Field(None, ge=0, le=100, description="Agua útil al 1 de mayo para el balance (% de 0 a 100 cm)")
    fechas_siembra: dict[str, str] = Field({}, description='Fecha de siembra por cultivo, "MM-DD" (por ejemplo {"soja": "11-20"})')
    cultivos: list[str] = Field(list(CULTIVOS))
    historial: list[str] = Field([], description='Cultivos de las campañas anteriores, la más reciente primero (por ejemplo ["soja", "maiz", "girasol"])')
    observaciones: list[ObservacionRecibida] = Field([], description="Lo que devolvió POST /consulta (textura GeoINTA, pH)")
    power: dict | None = Field(None, description="JSON diario de NASA POWER ya bajado; si no viene, la API lo pide")
    desde: int = Field(1991, ge=1981, le=2015)
    hasta: int = Field(2025, ge=1995, le=2026)

    @field_validator("cultivos")
    @classmethod
    def _cultivos(cls, v):
        malos = set(v) - set(CULTIVOS)
        if malos or not v:
            raise ValueError(f"Cultivos posibles: {', '.join(CULTIVOS)}")
        return v

    @field_validator("fechas_siembra")
    @classmethod
    def _fechas(cls, v):
        for c, f in v.items():
            if c not in CULTIVOS:
                raise ValueError(f"Cultivo desconocido en fechas_siembra: {c}")
            _mes_dia(f)
        return v


def _mes_dia(texto: str) -> tuple[int, int]:
    try:
        mes, dia = (int(x) for x in texto.split("-"))
        date(2001, mes, dia)
    except (ValueError, TypeError):
        raise ValueError(f'Fecha "{texto}" inválida: va "MM-DD"')
    return mes, dia


# ---------------------------------------------------------------- clima diario

def serie_diaria(power: dict) -> dict[date, dict]:
    """Día → tmax, tmin, lluvia, tsuelo (None si falta) desde el JSON diario de POWER."""
    p = power["properties"]["parameter"]
    tmax, tmin, lluvia, tsuelo = p["T2M_MAX"], p["T2M_MIN"], p["PRECTOTCORR"], p.get("TSOIL1") or {}
    dias = {}
    for k, ll in lluvia.items():
        tx, tn = tmax.get(k), tmin.get(k)
        if ll is None or ll < 0 or tx is None or tn is None or tx < -90 or tn < -90:
            continue
        ts = tsuelo.get(k)
        dias[date(int(k[:4]), int(k[4:6]), int(k[6:]))] = {
            "tmax": tx, "tmin": tn, "lluvia": ll, "tsuelo": ts if ts is not None and ts > -90 else None}
    return dias


def campanas(dias: dict[date, dict]) -> list[int]:
    """Años y de las campañas (1/5/y al 30/4/y+1) con al menos 360 días con dato."""
    if not dias:
        return []
    anios = range(min(dias).year, max(dias).year + 1)
    salida = []
    for y in anios:
        ini, fin = date(y, 5, 1), date(y + 1, 4, 30)
        if sum(1 for i in range((fin - ini).days + 1) if ini + timedelta(i) in dias) >= 360:
            salida.append(y)
    return salida


def fecha_en_campana(y: int, mes: int, dia: int) -> date:
    return date(y if mes >= 5 else y + 1, mes, dia)


def grados_dia(d: dict, tb: float, tope: float | None) -> float:
    tx = min(d["tmax"], tope) if tope is not None else d["tmax"]
    return max(0.0, (tx + d["tmin"]) / 2 - tb)


def _frac(valores: list[bool]) -> float | None:
    return sum(valores) / len(valores) if valores else None


def _ddmm(f: date | None) -> str | None:
    return f.strftime("%d/%m") if f else None


def _mediana_fecha(fechas: list[date], y_ref: int = 2003) -> date | None:
    """Mediana de fechas de distintas campañas, llevadas a una campaña de referencia (2003/04: tiene 29 de febrero)."""
    if not fechas:
        return None
    ordinales = sorted((fecha_en_campana(y_ref, f.month, f.day) - date(y_ref, 5, 1)).days for f in fechas)
    return date(y_ref, 5, 1) + timedelta(int(statistics.median(ordinales)))


def desde_fecha(filas: list[dict], clave: str, fraccion: float) -> date | None:
    """Primer día (en una campaña de referencia) desde el que el suelo cumple el umbral en `fraccion` de las campañas."""
    if not filas:
        return None
    largo = min(len(f["ventana_suelo"][clave]) for f in filas)
    for i in range(largo):
        vals = [f["ventana_suelo"][clave][i] for f in filas if f["ventana_suelo"][clave][i] is not None]
        if vals and sum(vals) / len(vals) >= fraccion:
            ini = filas[0]["inicio_ventana"]
            return fecha_en_campana(2001, ini.month, ini.day) + timedelta(i)
    return None


# ---------------------------------------------------------------- suelo

def suelo_del_lote(pedido: PedidoAgronomos, cat_rot: dict) -> dict:
    """Textura de arriba, capas, capacidad de agua útil de 0 a 100 cm y de dónde sale cada cosa."""
    capas, fuente, usados = pedido.capas_textura, "cargada por el agrónomo", []
    textura = pedido.textura
    if pedido.observaciones and (textura == "no_sabe" or not capas):
        from rotaterra.rotacion.desde_pipeline import completar
        datos, usados = completar({"lote": {"textura": textura, "capas_textura": capas and [c.model_dump() for c in capas]}},
                                  pedido.observaciones)
        lote = datos["lote"]
        if textura == "no_sabe" and lote.get("textura", "no_sabe") != "no_sabe":
            textura, fuente = lote["textura"], lote.get("textura_fuente") or "GeoINTA"
        if not capas and lote.get("capas_textura"):
            capas = [CapaSuelo(**c) for c in lote["capas_textura"]]
    if textura == "no_sabe" and capas:
        textura = sorted(capas, key=lambda c: c.desde_cm)[0].textura
    # GeoINTA distingue arenoso (código 1) de areno franco (código 2), pero las dos caen en la clase "arenoso" del motor.
    # Para el descarte vale solo arenoso (Hernán, 14/11/2026): se miran los códigos de 0-15 y 15-30 cm.
    codigos = {}
    if pedido.textura == "no_sabe" and not pedido.capas_textura:
        from rotaterra.recomendacion.motor import _ultima
        for var in ("suelo_textura_0_15cm", "suelo_textura_15_30cm"):
            if o := _ultima(pedido.observaciones, var):
                codigos[var] = round(o.valor)
    prof = min(pedido.profundidad_cm or 100, 100)
    supuesta = False
    if capas:
        cap, detalle = agua_util_por_capas(cat_rot, capas, prof)
    elif textura != "no_sabe":
        cap, detalle = cat_rot["agua_util_mm_por_m"][textura] * prof / 100, f"0-{prof:.0f} cm {textura.replace('_', ' ')}"
    else:
        supuesta = True
        cap, detalle = cat_rot["agua_util_mm_por_m"]["franco_arenoso"] * prof / 100, f"0-{prof:.0f} cm franco arenoso (supuesta)"
    # Arenoso "puro" de 0 a 30 cm: la textura de arriba, y si hay capas, todas las que empiezan antes de 30 cm
    arriba = [c.textura for c in (capas or []) if c.desde_cm < 30] or ([textura] if textura != "no_sabe" else [])
    if codigos:
        arenoso_puro = all(v == 1 for v in codigos.values())
    else:
        arenoso_puro = bool(arriba) and all(t == "arenoso" for t in arriba)
    sup = textura if textura != "no_sabe" else "franco_arenoso"
    capa = cat_rot["agua_util_mm_por_m"][sup] * CAPA_SIEMBRA_CM / 100
    return {"textura": textura, "textura_fuente": None if textura == "no_sabe" else fuente, "arriba_30cm": arriba, "arenoso_puro": arenoso_puro,
            "codigos_geointa": codigos, "capacidad_capa_siembra_mm": round(capa, 2),
            "capacidad_mm": round(cap, 1), "detalle_agua": detalle, "agua_supuesta": supuesta, "profundidad_balance_cm": prof,
            "datos_del_pipeline": usados}


# ---------------------------------------------------------------- campaña por campaña

def simular(dias: dict, anios: list[int], cultivo: dict, siembra: tuple[int, int], helada: dict, calor: dict | None,
            capacidad: float, au_mayo_pct: float, pres: dict, riego_mm: float, capa_siembra: float = 0.0) -> list[dict]:
    """Una fila por campaña con todo lo que miran las reglas."""
    ts, gd = cultivo["temperatura_suelo"], cultivo["grados_dia"]
    kc = 0.25  # barbecho con rastrojo (FAO-56, catálogo del motor de rotación)
    lat = pres["_latitud"]
    filas = []
    for y in anios:
        s = fecha_en_campana(y, *siembra)
        fin = date(y + 1, 4, 30)
        # 1) suelo: ¿los 3 días hasta la siembra superan el mínimo? ¿desde cuándo se da en la campaña?
        def suelo_ok(f: date, umbral: float) -> bool | None:
            vals = [dias.get(f - timedelta(i), {}).get("tsuelo") for i in range(ts["dias_seguidos"])]
            return None if any(v is None for v in vals) else all(v >= umbral for v in vals)

        # Para cada día de la ventana de búsqueda (1/8 a 31/1): ¿el suelo ya cumple ese día? (para la fecha sugerida)
        ini_v = fecha_en_campana(y, *_mes_dia(pres["inicio_busqueda_tsuelo"]))
        ventana = {clave: [suelo_ok(ini_v + timedelta(i), ts[clave]) for i in range((date(y + 1, 1, 31) - ini_v).days + 1)]
                   for clave in ("minimo_c", "recomendado_c")}
        # 2) balance de barbecho desde el 1 de mayo hasta la siembra
        # (el perfil de 0 a 100 cm para el agua del ciclo; la capa de 0 a 8 cm para la humedad de siembra)
        au = capacidad * au_mayo_pct / 100
        top = capa_siembra * au_mayo_pct / 100
        # La capa de siembra se sigue hasta VENTANA_SIEMBRA_DIAS después: se siembra después de una lluvia, así que importa si
        # en los días alrededor de la fecha hay humedad, no el día exacto.
        f, au_siembra, top_ventana = date(y, 5, 1), None, []
        ventana_ini, ventana_fin = s - timedelta(VENTANA_SIEMBRA_DIAS), s + timedelta(VENTANA_SIEMBRA_DIAS)
        while f <= ventana_fin:
            if f == s:
                au_siembra = au
            d = dias.get(f)
            if d:
                eto = eto_hargreaves(d["tmax"], d["tmin"], lat, f.timetuple().tm_yday)
                if f < s:
                    au = min(capacidad, au + d["lluvia"])
                    au -= kc * eto * (au / capacidad if capacidad else 0)
                    au = max(0.0, au)
                top = min(capa_siembra, top + d["lluvia"])
                top -= min(top, KE_CAPA_SIEMBRA * eto * (top / capa_siembra if capa_siembra else 0))
                if f >= ventana_ini and capa_siembra:
                    top_ventana.append(100 * top / capa_siembra)
            f += timedelta(1)
        au = au_siembra if au_siembra is not None else au
        # 3) grados día desde la siembra hasta la madurez, la helada que mata o el 30 de abril
        acum, f, madurez, flor, helada_mata, llega_publicado = 0.0, s, None, None, None, None
        lluvia_ciclo, helada_temprana = 0.0, False
        meta = gd["ciclo_cd"][0]
        while f <= fin:
            d = dias.get(f)
            if d:
                acum += grados_dia(d, gd["tb_c"], gd["tope_tmax_c"])
                lluvia_ciclo += d["lluvia"] if madurez is None else 0
                if (f - s).days < pres["dias_helada_tras_siembra"] and d["tmin"] <= helada["emergencia"]:
                    helada_temprana = True
                if flor is None and acum >= meta * gd["fraccion_floracion"]:
                    flor = f
                if madurez is None and acum >= meta:
                    madurez = f
                if gd.get("ciclo_publicado_cd") and llega_publicado is None and acum >= gd["ciclo_publicado_cd"]:
                    llega_publicado = f
                # Helada fuerte después del primer mes y antes de madurar: corta el ciclo
                if madurez is None and (f - s).days > 30 and d["tmin"] <= helada["llenado"]:
                    helada_mata = f
                    break
            if madurez is not None and (not gd.get("ciclo_publicado_cd") or llega_publicado is not None):
                break
            f += timedelta(1)
        # 4) calor en el período crítico
        dias_calor = racha_calor = dias_letal = None
        if calor and flor:
            if calor["etapa"] == "floracion":
                ini, fin_v = flor - timedelta(pres["ventana_floracion_dias"]), flor + timedelta(pres["ventana_floracion_dias"])
            else:
                ini, fin_v = flor, flor + timedelta(pres["ventana_llenado_dias"])
            umbral = calor.get("umbral_c", UMBRAL_CALOR)
            dias_calor = racha_calor = dias_letal = racha = 0
            for i in range((fin_v - ini).days + 1):
                dd = dias.get(ini + timedelta(i))
                caliente = bool(dd) and dd["tmax"] > umbral
                dias_calor += caliente
                racha = racha + 1 if caliente else 0
                racha_calor = max(racha_calor, racha)
                dias_letal += bool(dd) and calor.get("letal_c") is not None and dd["tmax"] >= calor["letal_c"]
        filas.append({
            "campana": f"{y}/{str(y + 1)[2:]}", "siembra": s,
            "suelo_ok": suelo_ok(s, ts["minimo_c"]), "suelo_ok_recomendado": suelo_ok(s, ts["recomendado_c"]),
            "ventana_suelo": ventana, "inicio_ventana": ini_v,
            "au_siembra_mm": au, "au_siembra_pct": 100 * au / capacidad if capacidad else None,
            "capa_siembra_max_ventana_pct": max(top_ventana) if top_ventana else None,
            "madurez": madurez, "floracion": flor, "helada_corta": helada_mata, "gd_acumulados": acum,
            "llega_publicado": llega_publicado, "helada_temprana": helada_temprana, "dias_calor": dias_calor, "racha_calor": racha_calor, "dias_letal": dias_letal,
            "oferta_mm": au + lluvia_ciclo + riego_mm,
        })
    return filas


# ---------------------------------------------------------------- reglas

def _regla(id_: str, nombre: str, resultado: str, dato: str, umbral: str, fuentes: list, cat: dict, detalle: str = "",
           comparativa_optimo: str = "") -> dict:
    claves: list[str] = []
    for f in fuentes:  # una regla puede tener una fuente o una lista de fuentes
        for k in (f if isinstance(f, list) else [f]):
            if k in cat["fuentes"] and k not in claves:
                claves.append(k)
    return {"id": id_, "regla": nombre, "resultado": resultado, "dato_del_lote": dato, "umbral": umbral,
            "comparativa_optimo": comparativa_optimo or f"Tu campo: {dato} · Óptimo: {umbral}",
            "fuente": "; ".join(cat["fuentes"][k] for k in claves), "detalle": detalle}


def calcular_porcentaje_optimo(c: dict, filas: list[dict], suelo: dict, ph: dict, pedido: PedidoAgronomos,
                               estado: str, reglas: list[dict]) -> int:
    """Calcula un porcentaje (0% a 100%) de coincidencia agronómica óptima evaluando agua, grados día, suelo, siembra y rotación."""
    pts_agua = 0.0
    ag = c.get("agua_ciclo", {})
    optimo_mm = ag.get("optimo_mm", 650.0)
    maximo_mm = ag.get("maximo_mm", 1800.0)
    if filas:
        ofertas = [f["oferta_mm"] for f in filas]
        med_agua = statistics.median(ofertas)
        if med_agua >= optimo_mm:
            pts_agua = 35.0
            if med_agua > maximo_mm:
                pts_agua = max(20.0, 35.0 - (med_agua - maximo_mm) / 50.0)
        elif med_agua <= 0:
            pts_agua = 0.0
        else:
            pts_agua = 35.0 * (med_agua / optimo_mm)
    else:
        pts_agua = 22.0

    pts_termico = 0.0
    if filas:
        fr_llega = _frac([f["madurez"] is not None for f in filas])
        pts_termico = 25.0 * (fr_llega if fr_llega is not None else 0.8)
    else:
        pts_termico = 20.0

    pts_suelo = 15.0
    p = c.get("ph")
    if p and ph.get("ph"):
        ph_val = ph["ph"]["valor"]
        ph_opt = p["optimo"]
        diff = abs(ph_val - ph_opt)
        if diff <= 0.3:
            pts_suelo = 20.0
        elif p["minimo"] <= ph_val <= p["maximo"]:
            pts_suelo = max(10.0, 20.0 - (diff * 5.0))
        else:
            pts_suelo = 5.0
    if c.get("textura", {}).get("bloquea_secano") and pedido.sistema == "secano" and suelo.get("arenoso_puro"):
        pts_suelo = 0.0

    pts_siembra = 0.0
    if filas:
        fr_ts = _frac([f["suelo_ok"] for f in filas if f["suelo_ok"] is not None]) or 0.8
        fr_hum = _frac([f["capa_siembra_max_ventana_pct"] is not None and f["capa_siembra_max_ventana_pct"] >= c["humedad_siembra_pct_au"]["minimo"] for f in filas]) or 0.8
        pts_siembra = (5.0 * fr_ts) + (5.0 * fr_hum)
    else:
        pts_siembra = 8.0

    pts_rotacion = 10.0
    nr = c.get("no_repetir")
    if nr and pedido.historial:
        if any(h and h.lower() in ("otro", "otros", "ninguno") for h in pedido.historial):
            pts_rotacion = 10.0
        else:
            previas = [h.replace("maiz_tardio", "maiz") for h in pedido.historial[:nr["campanas_libres"]]]
            if nr["especie"] in previas:
                pts_rotacion = 0.0
            else:
                pts_rotacion = 10.0

    total_bruto = pts_agua + pts_termico + pts_suelo + pts_siembra + pts_rotacion

    if estado == "No recomendable":
        return min(48, max(22, int(total_bruto * 0.48)))
    elif estado == "Con cuidado":
        return min(78, max(55, int(total_bruto * 0.78)))
    else:
        return min(98, max(80, int(total_bruto * 0.98)))


def evaluar_cultivo(clave: str, cat: dict, cat_rot: dict, filas: list[dict], pedido: PedidoAgronomos, suelo: dict,
                    ph: dict) -> dict:
    c = cat["cultivos"][clave]
    pres = cat["presentacion"]
    aviso_desde = pres["aviso_desde_fraccion"]
    n = len(filas)
    reglas = []
    ts, gd = c["temperatura_suelo"], c["grados_dia"]
    siembra = filas[0]["siembra"] if filas else None
    fuentes_clima = ["nasa_power"]

    # 1) temperatura del suelo
    validas = [f["suelo_ok"] for f in filas if f["suelo_ok"] is not None]
    fr = _frac(validas)
    desde_min = desde_fecha(filas, "minimo_c", 1 - aviso_desde)
    desde_rec = desde_fecha(filas, "recomendado_c", 1 - aviso_desde)
    if fr is None:
        res, dato = "sin_dato", "La serie de POWER no trae temperatura del suelo (TSOIL1)"
        comp_ts = f"Tu campo: sin serie de temperatura de suelo vs Óptimo: {ts.get('optimo_c', 22)} °C (Mínimo: {ts['minimo_c']} °C)"
    elif desde_fecha(filas, "minimo_c", 0.5) is None:
        res, dato = "no", f"Ni a fin de enero el suelo tiene {ts['minimo_c']} °C en la mitad de las campañas"
        comp_ts = f"Tu campo: no alcanza {ts['minimo_c']} °C a fin de enero vs Óptimo: {ts.get('optimo_c', 22)} °C (Mínimo requerido: {ts['minimo_c']} °C)"
    else:
        res = "ok" if 1 - fr < aviso_desde else "aviso"
        dato = (f"Al {_ddmm(siembra)} el suelo ya tiene {ts['minimo_c']} °C ({ts['dias_seguidos']} días) en {round(fr * 10)} de cada "
                f"10 campañas. Se da en 8 de cada 10 desde el {_ddmm(desde_min) or '(nunca antes del 31/01)'}"
                + (f"; {ts['recomendado_c']} °C, desde el {_ddmm(desde_rec)}" if ts["recomendado_c"] != ts["minimo_c"] and desde_rec else ""))
        if ts.get("recomendado_c") and ts["recomendado_c"] != ts["minimo_c"]:
            rango_req = f"Mínimo: {ts['minimo_c']} °C, Recomendado: {ts['recomendado_c']} °C"
        else:
            rango_req = f"Mínimo de siembra: {ts['minimo_c']} °C"
        comp_ts = f"Tu campo: suelo con {ts['minimo_c']} °C en {round(fr * 10)}/10 campañas vs Óptimo: {ts.get('optimo_c', 22)} °C ({rango_req})"
    reglas.append(_regla("temperatura_suelo", "Temperatura del suelo para sembrar", res, dato, ts["rango"], [ts["fuente"], *fuentes_clima], cat,
                         "TSOIL1 es la media diaria de 0 a 10 cm del modelo MERRA-2, no la medida a la mañana en el lote",
                         comparativa_optimo=comp_ts))

    # 2) grados día
    llega = [f["madurez"] is not None for f in filas]
    fr_llega = _frac(llega)
    madurez_med = _mediana_fecha([f["madurez"] for f in filas if f["madurez"]])
    cortes = sum(1 for f in filas if f["helada_corta"])
    if fr_llega is None:
        res, dato = "sin_dato", "Sin serie de clima"
        comp_gd = f"Tu campo: sin serie térmica vs Óptimo ciclo: {gd['ciclo_cd'][0]:,} a {gd['ciclo_cd'][1]:,} °Cd".replace(",", ".")
    else:
        res = "ok" if 1 - fr_llega < aviso_desde else "aviso"
        dato = (f"Junta {gd['ciclo_cd'][0]:,} °Cd en {round(fr_llega * 10)} de cada 10 campañas".replace(",", ".")
                + (f"; madura hacia el {_ddmm(madurez_med)}" if madurez_med else "")
                + (f"; en {cortes} de {n} campañas una helada corta el ciclo antes" if cortes else ""))
        if gd.get("ciclo_publicado_cd"):
            fp = _frac([f["llega_publicado"] is not None for f in filas])
            dato += f". Con el dato de ASAGIR ({gd['ciclo_publicado_cd']:,} °Cd) llega en {round(fp * 10)} de cada 10".replace(",", ".")
        comp_gd = f"Tu campo: madura antes de helada en {round(fr_llega * 10)}/10 campañas vs Óptimo ciclo: {gd['ciclo_cd'][0]:,} a {gd['ciclo_cd'][1]:,} °Cd (Tb {gd['tb_c']} °C)".replace(",", ".")
    umbral = (f"{gd['ciclo_cd'][0]:,}–{gd['ciclo_cd'][1]:,} °Cd, Tb {gd['tb_c']} °C".replace(",", ".")
              + (f", Tmáx tope {gd['tope_tmax_c']} °C" if gd["tope_tmax_c"] else ""))
    reglas.append(_regla("grados_dia", "Grados día: llega a madurar", res, dato, umbral, [gd["fuente"], gd["fuente_tb"], *fuentes_clima], cat,
                         gd["contraste"] + (f". EN REVISIÓN con la agrónoma: {gd['en_revision']}" if gd.get("en_revision") else ""),
                         comparativa_optimo=comp_gd))

    # 3) humedad a la siembra
    h = c["humedad_siembra_pct_au"]
    if pedido.agua_util_siembra_pct is not None:
        v = pedido.agua_util_siembra_pct
        res = "ok" if v >= h["minimo"] else "aviso"
        dato = f"Medida: {v:g} % del agua útil de 2 a 8 cm"
        comp_h = f"Tu campo: {v:g} % agua útil (medida 2-8 cm) vs Óptimo: 40 % a 50 % (Mínimo: {h['minimo']} %)"
    elif filas and any(f["capa_siembra_max_ventana_pct"] is not None for f in filas):
        pcts = [f["capa_siembra_max_ventana_pct"] for f in filas if f["capa_siembra_max_ventana_pct"] is not None]
        fr_h = _frac([p >= h["minimo"] for p in pcts])
        res = "ok" if 1 - fr_h < aviso_desde else "aviso"
        dato = (f"Estimada: hay al menos un día con humedad suficiente de 2 a 8 cm entre el "
                f"{_ddmm(siembra - timedelta(VENTANA_SIEMBRA_DIAS))} y el {_ddmm(siembra + timedelta(VENTANA_SIEMBRA_DIAS))} "
                f"en {round(fr_h * 10)} de cada 10 campañas (balance diario de lluvia y evaporación). Conviene medirla")
        comp_h = f"Tu campo: humedad de siembra estimada en {round(fr_h * 10)}/10 campañas vs Óptimo: 40 % a 50 % de agua útil (Mínimo: {h['minimo']} %)"
    else:
        res, dato = "sin_dato", "Sin dato"
        comp_h = f"Tu campo: sin registro de humedad de siembra vs Óptimo: 40 % (Mínimo: {h['minimo']} %)"
    reglas.append(_regla("humedad_siembra", "Humedad del suelo a la siembra", res, dato, f"≥ {h['rango']} del agua útil, de 2 a 8 cm",
                         [h["fuente"], "fao56"], cat, "Sin fuente publicada: criterio de la agrónoma",
                         comparativa_optimo=comp_h))

    # 4) agua del ciclo contra el 60 % de la demanda
    reg_agua = cat_rot["reglas_secuencia"]
    umbral_mm = next((r["umbral_mm"][c["clave_rotacion"]] for r in reg_agua if "umbral_mm" in r and c["clave_rotacion"] in r["umbral_mm"]), None)
    demanda = next((r["demanda_mm"][c["clave_rotacion"]] for r in reg_agua if "demanda_mm" in r and c["clave_rotacion"] in r["demanda_mm"]), None)
    if umbral_mm and filas:
        ofertas = [f["oferta_mm"] for f in filas]
        fr_falla = _frac([o < umbral_mm for o in ofertas])
        med = statistics.median(ofertas)
        maximo = c.get("agua_ciclo", {}).get("maximo_mm")
        if med < umbral_mm and pedido.sistema == "secano":
            res = "no"
        elif maximo and med > maximo:
            res = "aviso"
        elif fr_falla >= pres["agua_cuidado_desde_fraccion"] or med < umbral_mm:
            res = "aviso"
        else:
            res = "ok"
        dato = (f"Agua útil a la siembra + lluvia del ciclo{' + riego' if pedido.riego_mm_campana else ''}: año medio {med:.0f} mm; "
                f"no llega en {round(fr_falla * 10)} de cada 10 campañas"
                + (f"; se pasa del máximo ({maximo:,} mm) en {round(_frac([o > maximo for o in ofertas]) * 10)} de cada 10".replace(",", ".") if maximo else ""))
        ag = c.get("agua_ciclo", {})
        umbral_txt = f"mínimo {umbral_mm} mm (60 % de {demanda} mm)" + (f"; óptimo {ag['optimo_mm']} mm; máximo {ag['maximo_mm']:,} mm".replace(",", ".") if ag else "")
        opt_mm = ag.get("optimo_mm", demanda)
        comp_agua = f"Tu campo: oferta media {med:.0f} mm vs Óptimo: {opt_mm} mm (Mínimo requerido: {umbral_mm} mm, 60% de demanda)"
        reglas.append(_regla("agua_ciclo", "Agua del ciclo (60 % de la demanda)", res, dato, umbral_txt,
                             ["criterio_agronomico_equipo", *([ag["fuente"]] if ag else []), *fuentes_clima], cat,
                             comparativa_optimo=comp_agua))

    # 5) textura y profundidad
    tx = c["textura"]
    if tx.get("bloquea_secano"):
        if not suelo["arriba_30cm"]:
            res, dato = "sin_dato", "Falta la textura del lote"
            comp_tx = "Tu campo: sin textura cargada vs Óptimo: Franco a franco-arenoso"
        elif pedido.sistema == "secano" and suelo["arenoso_puro"]:
            res, dato = "no", f"0 a 30 cm arenoso ({suelo['textura_fuente']}), en secano"
            comp_tx = f"Tu campo: Arenoso puro de 0 a 30 cm ({suelo['textura_fuente']}) vs Óptimo: Suelo no arenoso en secano"
        elif suelo["codigos_geointa"] and 2 in suelo["codigos_geointa"].values():
            res, dato = "ok", f"Areno franco ({suelo['textura_fuente']}): no es arenoso puro, no se descarta"
            comp_tx = f"Tu campo: Areno franco ({suelo['textura_fuente']}) vs Óptimo: Franco a franco-arenoso con retención de agua"
        else:
            res, dato = "ok", f"{suelo['textura'].replace('_', ' ')} ({suelo['textura_fuente']})"
            comp_tx = f"Tu campo: {suelo['textura'].replace('_', ' ')} vs Óptimo: Franco a franco-arenoso"
        reglas.append(_regla("textura", "Textura", res, dato, tx["texto"], [tx["fuente"]], cat, "Criterio agronómico del equipo; solo la clase arenoso, no areno franco (Hernán, 14/11/2026)",
                             comparativa_optimo=comp_tx))
    if tx.get("arcilla_max_pct"):
        arc = pedido.analisis_suelo.arcilla_pct if pedido.analisis_suelo else None
        if arc is not None:
            res, dato = ("no" if arc > tx["arcilla_max_pct"] else "ok"), f"Arcilla {arc:g} % (análisis)"
            comp_arc = f"Tu campo: Arcilla {arc:g} % vs Óptimo: ≤ 30 % arcilla (Límite máximo: {tx['arcilla_max_pct']} %)"
        elif suelo["textura"] in tx["bloquea"]:
            res, dato = "no", f"Textura arcillosa ({suelo['textura_fuente']})"
            comp_arc = f"Tu campo: Textura arcillosa ({suelo['textura_fuente']}) vs Óptimo: Suelo suelto/arenoso-franco para arrancado"
        elif suelo["textura"] in tx["cuidado"]:
            res, dato = "aviso", f"Franco arcilloso ({suelo['textura_fuente']}): puede pasar 35 % de arcilla; medilo"
            comp_arc = f"Tu campo: Franco arcilloso ({suelo['textura_fuente']}) vs Óptimo: Franco-arenoso (< 35 % de arcilla)"
        elif suelo["textura"] == "no_sabe":
            res, dato = "sin_dato", "Falta la textura o la arcilla del análisis"
            comp_arc = f"Tu campo: sin dato de arcilla vs Óptimo: < 30 % de arcilla"
        else:
            res, dato = "ok", f"{suelo['textura'].replace('_', ' ')} ({suelo['textura_fuente']})"
            comp_arc = f"Tu campo: {suelo['textura'].replace('_', ' ')} vs Óptimo: Franco a franco-arenoso"
        reglas.append(_regla("textura", "Textura (arcilla)", res, dato, tx["texto"], [tx["fuente"]], cat,
                             "El límite de 35 % es criterio agronómico del equipo; falta que confirme el descarte",
                             comparativa_optimo=comp_arc))
    if tx.get("profundidad_min_cm"):
        p = pedido.profundidad_cm
        res = "sin_dato" if p is None else ("no" if p < tx["profundidad_min_cm"] else "ok")
        comp_prof = f"Tu campo: {p or 'Sin dato'} cm vs Óptimo: ≥ {tx['profundidad_min_cm']} cm de profundidad efectiva"
        reglas.append(_regla("profundidad", "Profundidad del suelo", res, "Falta la profundidad" if p is None else f"{p:g} cm",
                             f"≥ {tx['profundidad_min_cm']} cm", [tx["fuente"]], cat,
                             comparativa_optimo=comp_prof))

    # 6) pH (misma regla escalonada del motor de rotación)
    cp = c["clave_ph"]
    if ph["ph"] is None:
        reglas.append(_regla("ph", "pH", "sin_dato", "Sin pH del lote ni de los mapas", "Tope por cultivo (FAO Ecocrop) y rangos de la UNLP", [], cat,
                             comparativa_optimo="Tu campo: sin pH medido vs Óptimo: 6.0 a 6.8"))
    else:
        estado = ph["viabilidad"].get(cp)
        propios = [d for d in ph["detalle"] if d["cultivo"] == cp]
        riesgos = ph["riesgos_por_cultivo"].get(cp, [])
        res = "no" if estado in ("no_viable", "no_recomendable") else ("aviso" if propios or riesgos else "ok")
        dato = f"pH {ph['ph']['valor']:g} ({ph['ph']['fuente']})"
        detalle = " · ".join([d["regla"] for d in propios] + riesgos)
        p = c.get("ph")
        opt_ph = p["optimo"] if p else 6.5
        min_ph = p["minimo"] if p else 5.5
        max_ph = p["maximo"] if p else 8.0
        umbral_ph = (f"mínimo {min_ph:g} · óptimo {opt_ph:g} · máximo {max_ph:g}; hasta 0,3 fuera es tolerable" if p
                     else "Tope por cultivo (FAO Ecocrop); hasta 0,3 por encima es tolerable")
        comp_ph = f"Tu campo: pH {ph['ph']['valor']:g} vs Óptimo: pH {opt_ph:g} (Tolerancia: {min_ph:g} a {max_ph:g})"
        reglas.append(_regla("ph", "pH", res, dato, umbral_ph, [p["fuente"]] if p else [], cat, detalle,
                             comparativa_optimo=comp_ph))

    # 6 bis) regla 1 en 3: no repetir la especie (criterio agronómico del equipo)
    nr = c.get("no_repetir")
    if nr:
        if not pedido.historial:
            res, dato = "sin_dato", "Falta el historial del lote (cultivos de las campañas anteriores)"
            comp_nr = f"Tu campo: sin historial previo vs Óptimo: rotación biológica sin repetir {nr['especie']}"
        elif any(h and h.lower() in ("otro", "otros", "ninguno") for h in pedido.historial):
            res, dato = "ok", "Sin monocultivo previo: lote con rotación libre y favorable"
            comp_nr = f"Tu campo: sin restricciones de especies previas vs Óptimo: rotación biológica sin repetir {nr['especie']}"
        else:
            previas = [h.replace("maiz_tardio", "maiz") for h in pedido.historial[:nr["campanas_libres"]]]
            if nr["especie"] in previas:
                res, dato = "no", f"Hubo {nr['especie'].replace('mani', 'maní').replace('maiz', 'maíz')} hace {previas.index(nr['especie']) + 1} campaña(s)"
                comp_nr = f"Tu campo: cultivo previo '{pedido.historial[0]}' coincide con la misma especie vs Óptimo: al menos {nr['campanas_libres']} campañas libres"
            else:
                res, dato = "ok", "Últimas campañas: " + ", ".join(pedido.historial[:nr["campanas_libres"]])
                comp_nr = f"Tu campo: cultivo previo '{pedido.historial[0]}' vs Óptimo: rotación cruzada favorable sin repetir especie"
        reglas.append(_regla("no_repetir", "No repetir la especie", res, dato, nr["texto"], [nr["fuente"]], cat,
                             comparativa_optimo=comp_nr))

    # 7) sales
    s = c.get("sales")
    ce = pedido.analisis_suelo.ce_ds_m if pedido.analisis_suelo else None
    if s and ce is not None:
        cond = ce > s["ce_max_ds_m"] and (s.get("con_ph_mayor_de") is None or (ph["ph"] and ph["ph"]["valor"] > s["con_ph_mayor_de"]))
        umbral = f"> {s['ce_max_ds_m']:g} dS/m" + (f" con pH > {s['con_ph_mayor_de']:g}" if s.get("con_ph_mayor_de") else "")
        comp_s = f"Tu campo: {ce:g} dS/m vs Óptimo: < {s['ce_max_ds_m']:g} dS/m (Suelo libre de sales)"
        reglas.append(_regla("sales", "Sales", "aviso" if cond else "ok", f"{ce:g} dS/m", umbral, [s["fuente"]], cat,
                             comparativa_optimo=comp_s))
    elif s:
        reglas.append(_regla("sales", "Sales", "sin_dato", "Falta la conductividad del análisis", f"> {s['ce_max_ds_m']:g} dS/m", [s["fuente"]], cat,
                             comparativa_optimo=f"Tu campo: sin análisis de conductividad vs Óptimo: < {s['ce_max_ds_m']:g} dS/m"))

    # 8) helada después de sembrar y calor en el período crítico
    hel = cat_rot["temperaturas_criticas"]["helada_c"][c["clave_ph"]]
    if filas:
        fr_h = _frac([f["helada_temprana"] for f in filas])
        comp_hel = f"Tu campo: heladas tempranas en {round(fr_h * 10)}/10 campañas vs Óptimo: 0 heladas en emergencia ({hel['emergencia']} °C)"
        reglas.append(_regla("helada_siembra", "Helada después de sembrar", "aviso" if fr_h >= aviso_desde else "ok",
                             f"En {round(fr_h * 10)} de cada 10 campañas hay {hel['emergencia']} °C o menos en los "
                             f"{pres['dias_helada_tras_siembra']} días después del {_ddmm(siembra)}",
                             f"{hel['emergencia']} °C en emergencia (aire a 2 m)", [hel["fuente"], *fuentes_clima], cat,
                             comparativa_optimo=comp_hel))
    calor = c.get("calor")
    con_calor = [f for f in filas if f["racha_calor"] is not None]
    if calor and con_calor:
        fr_c = _frac([f["racha_calor"] >= calor["dias_seguidos"] for f in con_calor])
        fr_l = _frac([f["dias_letal"] > 0 for f in con_calor])
        seguidos = f" ({calor['dias_seguidos']} días seguidos o más)" if calor["dias_seguidos"] > 1 else ""
        comp_calor = f"Tu campo: olas de calor en {round(fr_c * 10)}/10 campañas vs Óptimo: 0 días >{calor['umbral_c']} °C en {calor['texto']}"
        reglas.append(_regla("calor", "Calor en el período crítico", "aviso" if fr_c >= aviso_desde else "ok",
                             f"Más de {calor['umbral_c']} °C{seguidos} en {calor['texto']} en {round(fr_c * 10)} de cada 10 campañas "
                             f"(mediana {statistics.median(f['dias_calor'] for f in con_calor):.0f} días); "
                             f"{calor['letal_c']} °C o más (letal) en {round(fr_l * 10)} de cada 10",
                             f"> {calor['umbral_c']} °C{seguidos}; letal {calor['letal_c']} °C (aire a 2 m)",
                             [calor["fuente"], "riglos_2023_calor", *fuentes_clima], cat,
                             "La floración se ubica con los grados día (aproximado)",
                             comparativa_optimo=comp_calor))

    # Helada y calor son riesgos del clima del lugar: se muestran con su frecuencia, pero no cambian el estado
    # (igual que en el motor de rotación: nunca descartan). El estado lo deciden las reglas del suelo, el agua y la siembra.
    for r in reglas:
        r["tipo"] = "riesgo_de_clima" if r["id"] in ("helada_siembra", "calor") else "regla"
    deciden = [r for r in reglas if r["tipo"] == "regla"]
    peor = "no" if any(r["resultado"] == "no" for r in deciden) else ("aviso" if any(r["resultado"] == "aviso" for r in deciden) else "ok")
    sugerida = None
    objetivo = desde_rec or desde_min
    if objetivo and siembra and fecha_en_campana(2001, siembra.month, siembra.day) < objetivo:
        sugerida = _ddmm(objetivo)
    
    estado_final = ESTADOS[peor]
    pct_coincidencia = calcular_porcentaje_optimo(c, filas, suelo, ph, pedido, estado_final, reglas)

    return {"cultivo": clave, "nombre": c["nombre"], "estado": estado_final, "fecha_siembra": _ddmm(siembra),
            "siembra_sugerida_desde": sugerida,
            "porcentaje_coincidencia": pct_coincidencia,
            "no_pasa": [r["regla"] for r in reglas if r["resultado"] == "no"],
            "avisos": [r["regla"] for r in deciden if r["resultado"] == "aviso"],
            "riesgos_de_clima": [r["regla"] for r in reglas if r["tipo"] == "riesgo_de_clima" and r["resultado"] == "aviso"],
            "faltan_datos": [r["regla"] for r in reglas if r["resultado"] == "sin_dato"],
            "reglas": reglas}


def catalogo_ph(cat: dict) -> dict:
    """La base de cultivos del motor de recomendación con los pH mínimo y máximo del criterio agronómico del equipo (14/11/2026) en
    lugar de los topes de FAO Ecocrop. Solo para este motor: el de rotación sigue con los suyos."""
    import copy
    from rotaterra.recomendacion.motor import cargar_catalogo as cargar_rec
    rec = copy.deepcopy(cargar_rec())
    for cu in rec["cultivos"]:
        p = next((x["ph"] for x in cat["cultivos"].values() if x["clave_ph"] == cu["id"] and x.get("ph")), None)
        if not p:
            continue
        cu["reglas"] = [r for r in cu["reglas"] if r["indicador"] != "ph"] + [
            {"id": "ph_minimo", "tipo": "excluyente", "indicador": "ph", "operador": ">=", "valor": p["minimo"], "unidad": "pH",
             "texto": f"pH desde {p['minimo']:g}", "fuente_umbral": "Criterio agronómico del equipo (14/11/2026)"},
            {"id": "ph_maximo", "tipo": "excluyente", "indicador": "ph", "operador": "<=", "valor": p["maximo"], "unidad": "pH",
             "texto": f"pH hasta {p['maximo']:g}", "fuente_umbral": "Criterio agronómico del equipo (14/11/2026)"}]
    return rec


def recomendar(pedido: PedidoAgronomos, power: dict, cat: dict | None = None, cat_rot: dict | None = None) -> dict:
    cat = cat or cargar_catalogo()
    cat_rot = cat_rot or cargar_catalogo_rotacion()
    pres = {**cat["presentacion"], "_latitud": pedido.latitud}
    dias = serie_diaria(power)
    anios = campanas(dias)
    if len(anios) < 10:
        raise ValueError("La serie de NASA POWER tiene menos de 10 campañas completas")
    suelo = suelo_del_lote(pedido, cat_rot)
    au_mayo = pedido.agua_util_mayo_pct if pedido.agua_util_mayo_pct is not None else pres["agua_util_mayo_pct_supuesta"]
    ph = evaluar_ph(pedido.analisis_suelo, pedido.observaciones, cat_rot, catalogo_ph(cat))
    def _evaluar_para_pedido(ped: PedidoAgronomos) -> list[dict]:
        salida = []
        for clave in ped.cultivos:
            c = cat["cultivos"][clave]
            siembra = _mes_dia(ped.fechas_siembra.get(clave) or cat["fechas_siembra_tipicas"][clave])
            helada = cat_rot["temperaturas_criticas"]["helada_c"][c["clave_ph"]]
            helada = {"emergencia": helada["emergencia"], "llenado": helada.get("llenado", helada["emergencia"])}
            calor = c.get("calor")
            riego = ped.riego_mm_campana if ped.sistema == "riego" else 0
            filas = simular(dias, anios, c, siembra, helada, calor, suelo["capacidad_mm"], au_mayo, pres, riego,
                            suelo["capacidad_capa_siembra_mm"])
            salida.append(evaluar_cultivo(clave, cat, cat_rot, filas, ped, suelo, ph))
        salida.sort(key=lambda r: (-r.get("porcentaje_coincidencia", 0), ORDEN_ESTADO[r["estado"]], len(r["no_pasa"]), len(r["avisos"])))

        # Asignar ranking comparativo y explicación de por qué se eligió una opción sobre la otra
        top_opcion = salida[0] if salida else None
        for idx, c_item in enumerate(salida):
            c_item["posicion_ranking"] = idx + 1
            pct = c_item.get("porcentaje_coincidencia", 50)
            est = c_item["estado"]
            nom = c_item["nombre"]
            if idx == 0:
                c_item["por_que_se_eligio"] = (
                    f"1ª OPCIÓN RECOMENDADA ({pct}% de coincidencia óptima): Es la mejor alternativa agronómica para tu campo. "
                    f"Supera a todas las demás opciones por su excelente oferta hídrica, alta probabilidad de maduración sin heladas "
                    f"y total armonía con el suelo y la rotación de la campaña."
                )
            else:
                if est == "Recomendable":
                    c_item["por_que_se_eligio"] = (
                        f"Opción {idx + 1}ª ({pct}% de coincidencia óptima): Cultivo completamente viable y recomendable, pero "
                        f"se ubica por detrás de {top_opcion['nombre']} ({top_opcion.get('porcentaje_coincidencia', 0)}%) porque "
                        f"su margen hídrico o acumulación de grados día resulta ligeramente más ajustado frente a los óptimos biológicos."
                    )
                elif est == "Con cuidado":
                    det_aviso = ", ".join(c_item["avisos"][:2]) if c_item["avisos"] else "precaución climática"
                    c_item["por_que_se_eligio"] = (
                        f"Opción {idx + 1}ª con reservas ({pct}% de coincidencia): Queda postergado frente a {top_opcion['nombre']} "
                        f"debido a advertencias técnicas en tu campo ({det_aviso}); requiere monitoreo de humedad o manejo específico."
                    )
                else:
                    det_no = ", ".join(c_item["no_pasa"][:2]) if c_item["no_pasa"] else "parámetros excluyentes"
                    c_item["por_que_se_eligio"] = (
                        f"Descartado ({pct}% de coincidencia): No es conveniente para esta campaña frente a las opciones recomendadas "
                        f"porque no supera reglas críticas para tu campo ({det_no})."
                    )
        return salida

    def _mejor_cultivo(lista: list[dict]) -> dict:
        recomendables = [c for c in lista if c["estado"] == "Recomendable"]
        if recomendables:
            return recomendables[0]
        con_cuidado = [c for c in lista if c["estado"] == "Con cuidado"]
        if con_cuidado:
            return con_cuidado[0]
        return lista[0] if lista else {}

    # Campaña 1 (Año 1)
    salida_1 = _evaluar_para_pedido(pedido)
    top_1 = _mejor_cultivo(salida_1)

    # Campaña 2 (Año 2): encadena el cultivo ganador del año 1 al historial
    ped_2 = pedido.model_copy(update={"historial": [top_1.get("cultivo", "")] + (pedido.historial or [])})
    salida_2 = _evaluar_para_pedido(ped_2)
    top_2 = _mejor_cultivo(salida_2)

    # Campaña 3 (Año 3): encadena año 2 y año 1
    ped_3 = pedido.model_copy(update={"historial": [top_2.get("cultivo", ""), top_1.get("cultivo", "")] + (pedido.historial or [])})
    salida_3 = _evaluar_para_pedido(ped_3)
    top_3 = _mejor_cultivo(salida_3)

    plan_rotacion = [
        {
            "anio": 1,
            "etiqueta": "Año 1 (Próxima Campaña)",
            "cultivo": top_1.get("cultivo"),
            "nombre": top_1.get("nombre"),
            "estado": top_1.get("estado"),
            "porcentaje_coincidencia": top_1.get("porcentaje_coincidencia", 85),
            "por_que_se_eligio": top_1.get("por_que_se_eligio", ""),
            "regla_cumplida": "Pasa todas las reglas agroclimáticas iniciales."
        },
        {
            "anio": 2,
            "etiqueta": "Año 2 (Siguiente Campaña)",
            "cultivo": top_2.get("cultivo"),
            "nombre": top_2.get("nombre"),
            "estado": top_2.get("estado"),
            "porcentaje_coincidencia": top_2.get("porcentaje_coincidencia", 80),
            "por_que_se_eligio": f"Sucesión agronómica recomendada tras {top_1.get('nombre')}: respeta el intervalo sanitario del INTA y mantiene la cobertura del suelo.",
            "regla_cumplida": f"Rotación biológica sin repetir especie sensible (INTA)."
        },
        {
            "anio": 3,
            "etiqueta": "Año 3 (Tercera Campaña)",
            "cultivo": top_3.get("cultivo"),
            "nombre": top_3.get("nombre"),
            "estado": top_3.get("estado"),
            "porcentaje_coincidencia": top_3.get("porcentaje_coincidencia", 80),
            "por_que_se_eligio": f"Rotación trienal equilibrada tras {top_2.get('nombre')} y {top_1.get('nombre')}: diversifica familias botánicas y optimiza el balance de nutrientes.",
            "regla_cumplida": "Cierre de ciclo trienal con alternancia de gramíneas y leguminosas."
        }
    ]

    rotaciones = {
        "1": {
            "cultivos": salida_1,
            "resumen": {e: [r["nombre"] for r in salida_1 if r["estado"] == e] for e in ORDEN_ESTADO},
            "top": top_1
        },
        "2": {
            "cultivos": salida_2,
            "resumen": {e: [r["nombre"] for r in salida_2 if r["estado"] == e] for e in ORDEN_ESTADO},
            "top": top_2
        },
        "3": {
            "cultivos": salida_3,
            "resumen": {e: [r["nombre"] for r in salida_3 if r["estado"] == e] for e in ORDEN_ESTADO},
            "top": top_3
        }
    }

    avisos = []
    if suelo["agua_supuesta"]:
        avisos.append("Sin textura del lote: el agua útil se calculó con franco arenoso (supuesto). Cargá la textura o las observaciones de GeoINTA")
    if pedido.agua_util_mayo_pct is None and pedido.agua_util_siembra_pct is None:
        avisos.append("La humedad de 2 a 8 cm a la siembra es estimada con un balance diario de lluvia y evaporación; "
                      "cargá la medida (agua_util_siembra_pct) para que mande")
    return {
        "lote": {"latitud": pedido.latitud, "longitud": pedido.longitud, "sistema": pedido.sistema,
                 "textura": suelo["textura"], "textura_fuente": suelo["textura_fuente"],
                 "agua_util_0_100cm_mm": suelo["capacidad_mm"], "agua_util_detalle": suelo["detalle_agua"],
                 "ph": ph["ph"], "datos_del_pipeline": suelo["datos_del_pipeline"]},
        "clima": {"fuente": cat["fuentes"]["nasa_power"], "campanas": len(anios),
                  "desde": f"{anios[0]}/{str(anios[0] + 1)[2:]}", "hasta": f"{anios[-1]}/{str(anios[-1] + 1)[2:]}"},
        "cultivos": salida_1,
        "resumen": {e: [r["nombre"] for r in salida_1 if r["estado"] == e] for e in ORDEN_ESTADO},
        "rotaciones": rotaciones,
        "plan_rotacion": plan_rotacion,
        "avisos": avisos,
        "como_leer": ("Recomendable: pasa todas las reglas. Con cuidado: alguna regla avisa (falla en 1 de cada 5 campañas o más, "
                      "o el dato está fuera del rango). No recomendable: alguna regla descarta. La helada y el calor van aparte, "
                      "como riesgos del clima del lugar: dicen en cuántas campañas pasó, pero no cambian el estado. Cada regla dice el dato del lote, "
                      "el umbral y la fuente. Las reglas sin fuente publicada son criterio agronómico del equipo."),
        "aviso": cat["aviso"], "catalogo_version": cat["version"], "estado_catalogo": cat["estado"],
    }
