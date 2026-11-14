"""Motor de rotación de cultivos multianual (spec 062, SDD v1.0 de Hernán).

Para un lote arma planes de 3 a 6 campañas: genera las secuencias posibles, descarta las que rompen una
regla dura, simula agua, rinde, nutrientes, rastrojo, cobertura, erosión y sanidad en tres escenarios de
clima, y elige los mejores planes según el perfil del dueño. Todo lo explica con números reales del cálculo.

No le pide nada a la NASA: recibe el clima ya resumido (ver `clima.py`) y los datos del lote.
Los parámetros viven en `catalogo_rotacion.json` y son provisionales hasta que un agrónomo los valide.
"""

from __future__ import annotations

import json
import math

from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Literal

import numpy as np

from pydantic import BaseModel, Field, field_validator, model_validator

from rotaterra.recomendacion.motor import ObservacionRecibida

CATALOGO = Path(__file__).with_name("catalogo_rotacion.json")
ESCENARIOS = ("seco", "medio", "humedo")
VERSION_MOTOR = "0.1.0"
INDICADORES = ("E", "S", "W", "C", "B", "H", "D", "R")
# Sentido de cada indicador: +1 = más es mejor, -1 = menos es mejor
SENTIDO = {"E": 1, "S": 1, "W": 1, "C": 1, "B": 1, "H": -1, "D": 1, "R": -1}
NOMBRE_INDICADOR = {
    "E": "margen bruto medio (por ha y por campaña, año medio)",
    "S": "balance de nitrógeno + fósforo por unidad producida (kg/ha por cada rinde regional cosechado)",
    "W": "agua cubierta en año seco (fracción de la demanda de los cultivos)",
    "C": "carbono que entra al suelo con rastrojo y raíces (t C/ha por campaña)",
    "B": "cobertura media del suelo en el año (% de superficie, cultivo vivo + rastrojo)",
    "H": "riesgo sanitario por hospedantes repetidos, reglas blandas y malezas resistentes",
    "D": "diversidad de cultivos (índice de Shannon)",
    "R": "caída del resultado en año seco respecto del medio",
}
SIN_PRECIOS = "producción relativa: rinde del año medio dividido por el rinde de referencia, sumado por campaña (sin precios)"
SIN_COSTOS = "ingreso bruto medio (US$/ha por campaña, año medio): rinde por precio, sin restar costos"
UsoAnterior = Literal["agricola", "virgen", "pastura", "no_sabe"]
UMBRAL_EROSION = (2.0, 6.0)
BEAM = 400            # secuencias que se conservan por perfil en cada campaña cuando no se pueden probar todas
EXHAUSTIVO_HASTA = 20000


def cargar_catalogo(ruta: Path = CATALOGO) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- pedido

Textura = Literal["arenoso", "franco_arenoso", "franco", "franco_limoso", "franco_arcilloso", "arcilloso", "no_sabe"]
Evidencia = Literal["observado", "inferido", "estimado", "declarado"]
Maleza = Literal["yuyo_colorado", "rama_negra", "sorgo_de_alepo", "pata_de_gallina"]  # las de `malezas.resistentes` del catálogo


class CapaSuelo(BaseModel):
    desde_cm: float = Field(ge=0, le=400)
    hasta_cm: float = Field(gt=0, le=400)
    textura: Textura


class AmbientesLote(BaseModel):
    """Superficie de cada ambiente del lote (NASADEM: más de 1 m por encima o por debajo de la altura media)."""
    loma: float = Field(0, ge=0)
    media_loma: float = Field(0, ge=0)
    bajo: float = Field(0, ge=0)
    fuente: str | None = None


class LoteRotacion(BaseModel):
    nombre: str = "lote"
    textura: Textura = "no_sabe"
    textura_fuente: str | None = None
    capas_textura: list[CapaSuelo] | None = Field(None, description="Textura por capa (GeoINTA 0-15, 15-30, 30-60, 60-100 cm): agua útil capa por capa")
    capas_fuente: str | None = None
    ambientes_ha: AmbientesLote | None = Field(None, description="Hectáreas de loma, media loma y bajo (NASADEM)")
    capacidad_uso: int | None = Field(None, ge=1, le=8, description="Clase de capacidad de uso del INTA (1 a 8)")
    indice_productividad: float | None = Field(None, ge=0, le=100, description="Índice de productividad del INTA (0-100)")
    suelo_fuente: str | None = None
    profundidad_cm: float | None = Field(None, gt=0, le=400)
    pendiente_pct: float | None = Field(None, ge=0, le=60)
    aporte_napa_mm_mes: float | None = Field(None, ge=0, le=100, description="Ascenso capilar desde la napa, si el productor lo conoce")
    riego_mm_mes: list[float] | None = Field(None, description="Riego que se puede aplicar por mes (mayo a abril, 12 valores, mm)")
    riego_costo_usd_mm: float | None = Field(None, ge=0, le=10, description="Costo de cada mm regado por ha (US$), si el productor lo sabe. Si no, el de INTA Manfredi")
    tenencia: Literal["propio", "alquilado"] = Field("propio", description="Alquilado: se resta el arrendamiento de la región por campaña")

    @field_validator("riego_mm_mes")
    @classmethod
    def _riego_doce(cls, v):
        if v is not None and (len(v) != 12 or any(x < 0 for x in v)):
            raise ValueError("riego_mm_mes lleva 12 valores (mayo a abril), sin negativos")
        return v
    uso_anterior: UsoAnterior = Field("no_sabe", description="agricola: ya se cultivó; virgen: monte o pastizal natural que nunca se cultivó; pastura: venía con pastura o campo natural para ganado")


class AnalisisSuelo(BaseModel):
    """Análisis de laboratorio del lote (0-20 cm; nitratos 0-60 cm). Lo del productor manda sobre los mapas."""
    fecha: str | None = None
    ph: float | None = Field(None, ge=3, le=11)
    mo_pct: float | None = Field(None, ge=0, le=20)
    p_bray_ppm: float | None = Field(None, ge=0, le=500)
    zinc_ppm: float | None = Field(None, ge=0, le=100)
    n_no3_kg_ha_0_60: float | None = Field(None, ge=0, le=600)
    laboratorio: str | None = None


class EventoHistorial(BaseModel):
    campana: str = Field(..., pattern=r"^\d{4}/\d{2}$")
    cultivo: str
    uso: Literal["grano", "cobertura", "pastura", "forraje"] = "grano"
    evidencia: Evidencia = "declarado"
    rinde_kg_ha: float | None = Field(None, ge=0)
    fuente: str | None = None


class ClimaRotacion(BaseModel):
    lluvia_mm: dict[str, list[float]]
    eto_mm: dict[str, list[float]] | list[float]
    viento_m_s: list[float | None] | None = None
    dias_viento_erosivo: list[float | None] | None = Field(None, description="Días por mes con ráfaga a 2 m ≥ 5 m/s (promedio de la serie)")
    tsuelo_c: list[float | None] | None = Field(None, description="Temperatura media del suelo de 0 a 10 cm por mes de la campaña (NASA POWER TSOIL1, promedio de la serie)")
    serie: list[dict] | None = Field(None, description="Todas las campañas de la serie: {campana, lluvia_mm[12], eto_mm[12]}")
    fuente: str
    detalle: str | None = None
    escala: str = "regional"
    campanas_serie: list[dict] | None = None
    campanas_escenario: dict[str, str] | None = Field(None, description="Campaña real que es el año malo, normal y bueno de lluvia")
    primera_campana: dict | None = Field(None, description="Años seco, medio y húmedo solo para la primera campaña (por ejemplo, de la misma fase de El Niño o La Niña)")

    @model_validator(mode="after")
    def _doce_meses(self):
        for esc in ESCENARIOS:
            if esc not in self.lluvia_mm or len(self.lluvia_mm[esc]) != 12:
                raise ValueError(f"lluvia_mm necesita 12 meses (mayo a abril) para el escenario '{esc}'")
        etos = self.eto_mm if isinstance(self.eto_mm, dict) else {e: self.eto_mm for e in ESCENARIOS}
        for esc in ESCENARIOS:
            if esc not in etos or len(etos[esc]) != 12:
                raise ValueError(f"eto_mm necesita 12 meses para el escenario '{esc}'")
        if self.viento_m_s is not None and len(self.viento_m_s) != 12:
            raise ValueError("viento_m_s necesita 12 meses")
        if self.dias_viento_erosivo is not None and len(self.dias_viento_erosivo) != 12:
            raise ValueError("dias_viento_erosivo necesita 12 meses")
        if self.tsuelo_c is not None and len(self.tsuelo_c) != 12:
            raise ValueError("tsuelo_c necesita 12 meses")
        for c in self.serie or []:
            if len(c.get("lluvia_mm", [])) != 12 or len(c.get("eto_mm", [])) != 12:
                raise ValueError("cada campaña de la serie necesita lluvia_mm y eto_mm de 12 meses")
        pc = self.primera_campana
        if pc is not None:
            for clave in ("lluvia_mm", "eto_mm"):
                if not isinstance(pc.get(clave), dict) or any(len(pc[clave].get(e) or []) != 12 for e in ESCENARIOS):
                    raise ValueError(f"primera_campana.{clave} necesita 12 meses para seco, medio y húmedo")
        return self

    def eto(self, esc: str) -> list[float]:
        return self.eto_mm[esc] if isinstance(self.eto_mm, dict) else self.eto_mm


class ValorConFuente(BaseModel):
    valor: float = Field(..., ge=0)
    fuente: str
    escala: Literal["lote", "regional"] = "regional"


class Herbicida(BaseModel):
    producto: str
    campana: str = Field(..., pattern=r"^\d{4}/\d{2}$")
    cultivos_sensibles: list[str]
    campanas_de_espera: int = Field(..., ge=1, le=5, description="Lo que dice el marbete")


class Fertilizacion(BaseModel):
    n_kg_ha: float = Field(0, ge=0)
    p_kg_ha: float = Field(0, ge=0)


class PedidoRotacion(BaseModel):
    lote: LoteRotacion
    historial: list[EventoHistorial] = []
    analisis_suelo: AnalisisSuelo | None = None
    clima: ClimaRotacion
    agua_util_inicial: ValorConFuente | None = None
    rindes_referencia: dict[str, ValorConFuente] = {}
    precios: dict[str, ValorConFuente] = Field({}, description="Precio neto en tranquera por tonelada, por cultivo")
    costos: dict[str, ValorConFuente] = Field({}, description="Costo directo por hectárea, por cultivo")
    usar_pizarra_rosario: bool = Field(True, description="Si no vienen precios, POST /rotacion/plan los toma de la pizarra del día de la Bolsa de Rosario")
    usar_enso: bool = Field(True, description="Si el clima trae la serie, POST /rotacion/plan elige los años de la primera campaña según El Niño o La Niña (NOAA)")
    usar_costos_magyp: bool = Field(True, description="Si no vienen costos, POST /rotacion/plan usa los gastos directos de MAGyP para la región San Luis")
    flete_usd_t: ValorConFuente | None = Field(None, description="Flete y gastos hasta Rosario (US$/t), se descuentan del precio pizarra")
    moneda: str = "USD"
    fertilizacion: dict[str, Fertilizacion] = {}
    viabilidad: dict[str, str] = Field({}, description="Resultado de /recomendacion/viabilidad por cultivo")
    incluir_no_recomendables: bool = False
    herbicidas: list[Herbicida] = []
    malezas_presentes: list[Maleza] | None = Field(None, description="Malezas resistentes del lote (yuyo_colorado, rama_negra, sorgo_de_alepo, "
                                                "pata_de_gallina). Sin dato se suponen yuyo colorado y rama negra (REM-Aapresid)")
    campana_inicial: str = Field("2026/27", pattern=r"^\d{4}/\d{2}$")
    horizonte: int = Field(5, ge=1, le=6)
    perfil: str | dict[str, float] = "equilibrado"
    fijadas: dict[str, str] = Field({}, description="Campaña → ocupación que el dueño fija")
    excluidas: list[str] = Field([], description="Cultivos u ocupaciones que el dueño no quiere")
    ocupaciones: list[str] | None = None
    observaciones: list[ObservacionRecibida] = Field([], description="Lo que devolvió POST /consulta: llena los campos vacíos")
    datos_del_pipeline: list[str] = Field([], description="Lo que se tomó de las observaciones (lo completa el motor)")
    contexto_satelital: dict = Field({}, description="Datos de la zona que el plan muestra como contexto (carbono, monte, napa, clima futuro)")

    @model_validator(mode="before")
    @classmethod
    def _completar(cls, datos):
        if isinstance(datos, dict) and datos.get("observaciones"):
            from rotaterra.rotacion.desde_pipeline import completar
            obs = [o if isinstance(o, ObservacionRecibida) else ObservacionRecibida.model_validate(o) for o in datos["observaciones"]]
            datos, usados = completar(dict(datos), obs)
            datos["datos_del_pipeline"] = usados
        return datos

    @field_validator("perfil")
    @classmethod
    def _perfil(cls, v):
        if isinstance(v, dict):
            if set(v) - set(INDICADORES):
                raise ValueError(f"Los pesos solo pueden ser {', '.join(INDICADORES)}")
            if any(x < 0 for x in v.values()) or sum(v.values()) <= 0:
                raise ValueError("Los pesos tienen que ser positivos y sumar más de 0")
        return v


def anio(campana: str) -> int:
    return int(campana[:4])


def etiqueta(anio_inicio: int) -> str:
    return f"{anio_inicio}/{str(anio_inicio + 1)[2:]}"


# ---------------------------------------------------------------- funciones agronómicas

def kc_del_mes(cultivo: dict, siembra: int, cosecha: int, mes: int) -> float:
    """Curva de Kc de FAO-56 (inicial, desarrollo, media, final) evaluada en el centro del mes."""
    if "kc_mensual" in cultivo:
        return cultivo["kc_mensual"][mes]
    ini, med, fin = cultivo["kc"]
    f_ini, f_des, f_med, _ = cultivo["etapas"]
    x = (mes - siembra + 0.5) / (cosecha - siembra + 1)
    if x <= f_ini:
        return ini
    if x <= f_ini + f_des:
        return ini + (med - ini) * (x - f_ini) / f_des
    if x <= f_ini + f_des + f_med:
        return med
    resto = 1 - (f_ini + f_des + f_med)
    return med + (fin - med) * min(1.0, (x - f_ini - f_des - f_med) / resto) if resto > 0 else med


def rinde_por_agua(rinde_maximo: float, ky: float, eta: float, etc: float) -> float:
    """FAO-33: 1 − Ya/Ym = Ky · (1 − ETa/ETc)."""
    if etc <= 0:
        return rinde_maximo
    return max(0.0, rinde_maximo * (1 - ky * (1 - eta / etc)))


def cobertura_rastrojo(kg_ha: float, coef: float) -> float:
    return 1 - math.exp(-coef * max(kg_ha, 0.0))


def shannon(cultivos: list[str]) -> float:
    if not cultivos:
        return 0.0
    n = len(cultivos)
    return -sum((c / n) * math.log(c / n) for c in (cultivos.count(x) for x in set(cultivos)))


# ---------------------------------------------------------------- simulación de una campaña

@dataclass
class Estado:
    au: dict[str, float]            # agua útil del perfil por escenario (mm)
    rastrojo: dict[str, float]      # kg MS/ha en superficie por escenario
    tipo_rastrojo: str = "alto_cn"
    extra_n: float | None = None    # nitratos medidos en el análisis antes de la primera campaña (se usan una vez)


@dataclass
class ResultadoCampana:
    ocupacion: str
    cultivos: list[dict] = field(default_factory=list)
    au_final: dict[str, float] = field(default_factory=dict)
    meses_cubiertos: dict[str, int] = field(default_factory=dict)
    cobertura_media: dict[str, float] = field(default_factory=dict)
    erosion_eolica: dict[str, float] = field(default_factory=dict)
    carbono_t_ha: dict[str, float] = field(default_factory=dict)
    n_balance: float | None = None
    p_balance: float | None = None
    drenaje_mm: dict[str, float] = field(default_factory=dict)
    riego_mm: dict[str, float] = field(default_factory=dict)


def agua_util_por_capas(cat: dict, capas: list, prof: float) -> tuple[float, str]:
    """Agua útil hasta `prof` cm sumando capa por capa; debajo de la última capa se repite la más profunda."""
    capas = sorted(capas, key=lambda c: c.desde_cm)
    total, partes, hasta = 0.0, [], 0.0
    for i, c in enumerate(capas):
        # Cada capa llena desde donde terminó la anterior hasta donde empieza la siguiente (sin huecos)
        fin = prof if i == len(capas) - 1 else min(max(c.hasta_cm, capas[i + 1].desde_cm), prof)
        ini = hasta
        if fin <= ini:
            continue
        textura = c.textura if c.textura in cat["agua_util_mm_por_m"] else "franco_arenoso"
        total += cat["agua_util_mm_por_m"][textura] * (fin - ini) / 100
        partes.append(f"{ini:.0f}-{fin:.0f} cm {textura.replace('_', ' ')}" + (" (supuesta)" if textura != c.textura else ""))
        hasta = fin
        if hasta >= prof:
            break
    return total, ", ".join(partes)


class Simulador:
    def __init__(self, pedido: PedidoRotacion, cat: dict):
        self.p = pedido
        self.cat = cat
        self.supuestos: list[str] = []
        self.faltantes: list[dict] = []
        lote = pedido.lote
        textura = lote.textura
        if textura == "no_sabe" and lote.capas_textura:
            textura = min(lote.capas_textura, key=lambda c: c.desde_cm).textura
        if textura == "no_sabe":
            textura = "franco_arenoso"
            self.faltantes.append({"dato": "textura", "criticidad": "importante",
                                   "por_que": "define cuánta agua guarda el suelo y cuánto se vuela",
                                   "supuesto": "franco arenoso, la textura más común en el este de San Luis"})
        self.textura = textura
        prof = lote.profundidad_cm
        if prof is None:
            prof = 150
            self.faltantes.append({"dato": "profundidad_cm", "criticidad": "importante",
                                   "por_que": "junto con la textura da el agua útil total del perfil",
                                   "supuesto": "150 cm de suelo explorable por las raíces"})
        self.taw = cat["agua_util_mm_por_m"][textura] * prof / 100
        if lote.capas_textura:
            self.taw, detalle = agua_util_por_capas(cat, lote.capas_textura, prof)
            self.supuestos.append(f"Agua útil total del perfil: {self.taw:.0f} mm, capa por capa hasta {prof:.0f} cm ({detalle}; "
                                  f"FAO-56, tabla 19; texturas: {lote.capas_fuente or 'cargadas'})")
        else:
            self.supuestos.append(f"Agua útil total del perfil: {self.taw:.0f} mm ({textura.replace('_', ' ')}, {prof:.0f} cm; FAO-56, tabla 19)")
        self.riego = lote.riego_mm_mes or [0.0] * 12
        self.napa = lote.aporte_napa_mm_mes or 0.0
        if lote.riego_mm_mes:
            self.supuestos.append(f"Riego disponible: {sum(self.riego):.0f} mm por campaña, solo en los meses con cultivo. "
                                  "El rinde potencial sigue siendo el de referencia: con riego conviene cargar rindes de referencia bajo riego")
        if pedido.agua_util_inicial is not None:
            self.au0 = min(pedido.agua_util_inicial.valor, self.taw)
            self.supuestos.append(f"Agua útil al inicio: {self.au0:.0f} mm ({pedido.agua_util_inicial.fuente})")
        else:
            self.au0 = 0.5 * self.taw
            self.faltantes.append({"dato": "agua_util_inicial", "criticidad": "importante",
                                   "por_que": "el agua guardada al empezar define la primera campaña",
                                   "supuesto": f"perfil a la mitad ({self.au0:.0f} mm); se puede tomar de SEPA o del balance propio"})
        self.ftext = cat["factor_erosion_eolica_textura"][textura]
        self.res = cat["residuos"]
        self.dias_viento = pedido.clima.dias_viento_erosivo
        if self.dias_viento is None:
            self.faltantes.append({"dato": "viento", "criticidad": "opcional",
                                   "por_que": "sin los días de viento fuerte no se estima la erosión eólica",
                                   "supuesto": "erosión eólica sin calcular; se arma con GET /rotacion/clima"})
        self.k_eolica = cat["erosion_eolica"]["k_cobertura"]
        self.escurrimiento_extra = 0.05 if (lote.pendiente_pct or 0) > 3 else 0.0
        self.aporte_ladera = 0.0  # en un bajo: veces el propio escurrimiento que llega de la loma y la media loma
        if not pedido.fertilizacion:
            self.supuestos.append("Sin fertilización cargada: los balances de N y P suponen 0 kg/ha de fertilizante "
                                  "(muestran cuánto se lleva cada cultivo, no cuánto conviene reponer)")
        self.ym: dict[str, float] = {}
        self.ym_fuente: dict[str, str] = {}
        self.yref: dict[str, float] = {}
        self._calibrar_rindes()

    # Rinde máximo (sin estrés hídrico) calibrado para que el año medio dé el rinde de referencia
    def _calibrar_rindes(self) -> None:
        cat = self.cat
        referencias: dict[str, tuple[float, str]] = {}
        por_cultivo: dict[str, list[float]] = {}
        for ev in self.p.historial:
            if ev.rinde_kg_ha and ev.uso == "grano" and ev.evidencia == "observado":
                por_cultivo.setdefault(ev.cultivo, []).append(ev.rinde_kg_ha)
        for c, vals in por_cultivo.items():
            referencias[c] = (median(vals), f"mediana de {len(vals)} cosecha(s) del lote (dato del productor)", True)
        for c, v in self.p.rindes_referencia.items():
            if c not in referencias:
                referencias[c] = (v.valor, f"{v.fuente} ({v.escala})", v.escala == "lote")
        # Maíz tardío (siembra en diciembre): si no tiene referencia propia, se calibra con la del maíz, así la mediana
        # de los dos da el rinde del departamento y lo que cambia es cómo le va en cada año (spec 062, §6 ter)
        if "maiz" in referencias and "maiz_tardio" not in referencias:
            valor, fuente, del_lote = referencias["maiz"]
            referencias["maiz_tardio"] = (valor, fuente + " · calibrado para siembra tardía (diciembre)", del_lote)
        # Un rinde regional (departamento) sale de lotes típicos en secano: se calibra con el suelo típico de la zona
        # (franco arenoso de 2 m, plano, sin riego ni napa) y después se simula con el suelo, el riego y la napa del lote.
        # Así un suelo arenoso o poco profundo rinde menos que la referencia y un lote regado rinde más. Un rinde del propio lote se calibra con el lote.
        propio = (self.taw, self.riego, self.napa, self.escurrimiento_extra)
        tipico = (cat["agua_util_mm_por_m"]["franco_arenoso"] * 2.0, [0.0] * 12, 0.0, 0.0)
        for clave, (valor, fuente, del_lote) in referencias.items():
            self.taw, self.riego, self.napa, self.escurrimiento_extra = propio if del_lote else tipico
            ocupacion = {"soja_2da": "trigo/soja_2da", "sorgo_2da": "trigo/sorgo_2da"}.get(clave, clave)
            cultivo = clave.replace("_2da", "").replace("_tardio", "")
            if ocupacion not in cat["ocupaciones"] or cultivo not in cat["cultivos"] or not cat["cultivos"][cultivo].get("ky"):
                continue
            # El rinde de referencia es una mediana de varias campañas: Ym se ajusta para que la MEDIANA de los rindes
            # simulados con toda la serie de clima dé ese valor (si no hay serie, el año medio)
            serie = self.p.clima.serie if self.p.clima.serie and len(self.p.clima.serie) >= 10 else None
            if serie:
                esc = {f"k{k}": (c["lluvia_mm"], c["eto_mm"]) for k, c in enumerate(serie)}
            else:
                esc = {"medio": (self.p.clima.lluvia_mm["medio"], self.p.clima.eto("medio"))}
            # Se corre dos campañas seguidas del mismo cultivo y se calibra con la segunda: así el cultivo llega a la
            # siembra con el agua que deja su propio barbecho (el trigo, con el del verano), como en los lotes de la estadística
            estado = Estado(au={e: min(self.au0, self.taw) for e in esc}, rastrojo={e: 2000.0 for e in esc})
            _, estado = self.campana(ocupacion, estado, calibrando=True, escenarios=esc)
            res, _ = self.campana(ocupacion, estado, calibrando=True, escenarios=esc)
            fila = [x for x in res.cultivos if x["cultivo"] == cultivo][-1]
            ky = cat["cultivos"][cultivo]["ky"]
            factor = median(max(0.15, 1 - ky * (1 - r)) for r in fila["agua_relativa"].values())
            self.ym[clave] = valor / factor
            self.yref[clave] = valor
            self.ym_fuente[clave] = fuente
        self.taw, self.riego, self.napa, self.escurrimiento_extra = propio
        for c in ("maiz", "soja", "girasol", "sorgo", "mani", "trigo"):
            if c not in self.ym:
                self.faltantes.append({"dato": f"rinde de referencia de {cat['cultivos'][c]['nombre'].lower()}", "criticidad": "importante",
                                       "por_que": "sin él no se estima el rinde ni el margen de ese cultivo",
                                       "supuesto": "rinde sin calcular; el cultivo se evalúa solo por agua, suelo y sanidad"})

    def _ym(self, cultivo: str, segunda: bool, tardio: bool = False) -> tuple[float | None, str | None]:
        if tardio and f"{cultivo}_tardio" in self.ym:
            return self.ym[f"{cultivo}_tardio"], self.ym_fuente[f"{cultivo}_tardio"]
        if segunda and f"{cultivo}_2da" in self.ym:
            return self.ym[f"{cultivo}_2da"], self.ym_fuente[f"{cultivo}_2da"]
        if cultivo in self.ym:
            nota = self.ym_fuente[cultivo] + (" · sin referencia de segunda: usa el potencial de primera (optimista)" if segunda else "")
            return self.ym[cultivo], nota
        return None, None

    def campana(self, ocupacion: str, estado: Estado, calibrando: bool = False,
                escenarios: dict[str, tuple[list[float], list[float]]] | None = None, t: int | None = None) -> tuple[ResultadoCampana, Estado] | ResultadoCampana:
        """Simula una campaña mes a mes en cada escenario. `escenarios` = {nombre: (lluvia, eto)}; por defecto seco, medio y húmedo.
        En la primera campaña (t = 0), si el clima trae `primera_campana` (fase de El Niño o La Niña), se usan esos años."""
        cat = self.cat
        pc = self.p.clima.primera_campana
        if escenarios is None and t == 0 and pc:
            escenarios = {e: (pc["lluvia_mm"][e], pc["eto_mm"][e]) for e in ESCENARIOS}
        if escenarios is None:
            escenarios = {e: (self.p.clima.lluvia_mm[e], self.p.clima.eto(e)) for e in ESCENARIOS}
        ESC = list(escenarios)
        etapas = cat["ocupaciones"][ocupacion]
        res = ResultadoCampana(ocupacion=ocupacion)
        nuevo = Estado(au=dict(estado.au), rastrojo=dict(estado.rastrojo), tipo_rastrojo=estado.tipo_rastrojo, extra_n=estado.extra_n)
        acumulado = [{e: {"eta": 0.0, "etc": 0.0} for e in ESC} for _ in etapas]
        au_siembra = [{} for _ in etapas]
        for esc in ESC:
            lluvia, eto = escenarios[esc]
            au, rastrojo, tipo = nuevo.au[esc], nuevo.rastrojo[esc], nuevo.tipo_rastrojo
            cubiertos, erosion, drenaje, carbono, suma_cob, regado = 0, 0.0, 0.0, 0.0, 0.0, 0.0
            for m in range(12):
                # En el mes en que se cosecha un cultivo y se siembra el de segunda (trigo y soja de 2.ª en diciembre),
                # el mes se reparte por mitades entre los dos.
                activas = [(i, e) for i, e in enumerate(etapas) if e["siembra"] <= m <= e["cosecha"]]
                peso = 1.0 / len(activas) if activas else 0.0
                cob_rastrojo = cobertura_rastrojo(rastrojo, self.res["cobertura_coef_ha_kg"])
                kcs = []
                for i, et in activas:
                    cult = cat["cultivos"][et["cultivo"]]
                    if m == et["siembra"]:
                        au_siembra[i][esc] = au
                    kcs.append(kc_del_mes(cult, et["siembra"], et["cosecha"], m))
                if activas:
                    cob_verde = max(min(0.95, k / max(cat["cultivos"][et["cultivo"]].get("kc_mensual") or cat["cultivos"][et["cultivo"]]["kc"]))
                                    for k, (_, et) in zip(kcs, activas))
                else:
                    cob_verde = 0.0
                kc_barbecho = 0.0 if activas else (cat["barbecho"]["kc_con_rastrojo"] if cob_rastrojo >= 0.5 else cat["barbecho"]["kc_desnudo"])
                cobertura = 1 - (1 - cob_verde) * (1 - cob_rastrojo)
                esc_frac = 0.05 + 0.10 * (1 - cobertura) + self.escurrimiento_extra
                pe = lluvia[m] * (1 - esc_frac) + lluvia[m] * esc_frac * self.aporte_ladera
                if activas:
                    riego = min(self.riego[m], max(0.0, self.taw - au - pe))
                    regado += riego
                    w = au + pe + self.napa + riego
                    demandas = []
                    for k, (i, et) in zip(kcs, activas):
                        cult = cat["cultivos"][et["cultivo"]]
                        etc_i = k * eto[m] * peso
                        ks = min(1.0, w / ((1 - cult["p"]) * self.taw)) if self.taw > 0 else 0
                        demandas.append((i, etc_i, etc_i * ks))
                    total = sum(d[2] for d in demandas)
                    escala = min(1.0, w / total) if total > 0 else 1.0
                    eta = 0.0
                    for i, etc_i, eta_i in demandas:
                        acumulado[i][esc]["eta"] += eta_i * escala
                        acumulado[i][esc]["etc"] += etc_i
                        eta += eta_i * escala
                else:
                    w = au + pe
                    eta = min(kc_barbecho * eto[m], pe + 0.1 * au)
                nuevo_au = w - eta
                if nuevo_au > self.taw:
                    drenaje += nuevo_au - self.taw
                    nuevo_au = self.taw
                au = max(0.0, nuevo_au)
                suma_cob += cobertura
                if cobertura >= 0.3:
                    cubiertos += 1
                if self.dias_viento and self.dias_viento[m] is not None:
                    # RWEQ: la cobertura de rastrojo baja la pérdida en e^(−0,0438 · % de cobertura) (Fryrear et al., 1998)
                    erosion += self.dias_viento[m] * self.ftext * math.exp(-self.k_eolica * cobertura * 100)
                rastrojo *= math.exp(-self.res["descomposicion_mensual"][tipo])
                for i, et in activas:
                    if m != et["cosecha"]:
                        continue
                    cult = cat["cultivos"][et["cultivo"]]
                    r = acumulado[i][esc]["eta"] / acumulado[i][esc]["etc"] if acumulado[i][esc]["etc"] else 1.0
                    if "biomasa_kg_ms_ha" in cult:
                        aereo = cult["biomasa_kg_ms_ha"] * r
                    elif not calibrando and (ym := self._ym(et["cultivo"], et.get("segunda", False), et.get("tardio", False))[0]) is not None:
                        rinde = rinde_por_agua(ym, cult["ky"], acumulado[i][esc]["eta"], acumulado[i][esc]["etc"])
                        ms_grano = rinde * (1 - cult.get("humedad_comercial", 0.13))
                        aereo = ms_grano * (1 - cult["indice_cosecha"]) / cult["indice_cosecha"] if cult.get("indice_cosecha") else 0
                    else:
                        aereo = 2000.0 * r if not "kc_mensual" in cult else 0.0
                    rastrojo += aereo
                    tipo = cult["rastrojo"]
                    carbono += (aereo * (1 + self.res["raices_sobre_aereo"])) * self.res["fraccion_carbono"] / 1000
            nuevo.au[esc], nuevo.rastrojo[esc] = au, rastrojo
            nuevo.tipo_rastrojo = tipo
            res.au_final[esc] = round(au, 1)
            res.meses_cubiertos[esc] = cubiertos
            res.cobertura_media[esc] = round(suma_cob / 12 * 100, 1)
            res.erosion_eolica[esc] = round(erosion, 2) if self.dias_viento else None
            res.drenaje_mm[esc] = round(drenaje, 1)
            res.riego_mm[esc] = round(regado, 1)
            res.carbono_t_ha[esc] = round(carbono, 2)
        n_total, p_total, sin_dato = 0.0, 0.0, False
        ya_extra = False  # los nitratos medidos en el análisis van al primer cultivo de grano de la campaña
        for i, et in enumerate(etapas):
            cult = cat["cultivos"][et["cultivo"]]
            fila = {"cultivo": et["cultivo"], "nombre": cult["nombre"] + (" tardío" if et.get("tardio") else ""), "segunda": et.get("segunda", False),
                    "tardio": et.get("tardio", False), "siembra_mes": et["siembra"], "cosecha_mes": et["cosecha"],
                    "agua_relativa": {e: round(acumulado[i][e]["eta"] / acumulado[i][e]["etc"], 3) if acumulado[i][e]["etc"] else 1.0 for e in ESC},
                    "etc_mm": {e: round(acumulado[i][e]["etc"]) for e in ESC},
                    "eta_mm": {e: round(acumulado[i][e]["eta"]) for e in ESC},
                    "agua_util_siembra_mm": {e: round(au_siembra[i].get(e, 0)) for e in ESC}}
            pastura = "kc_mensual" in cult
            if cult.get("ky") and not calibrando:
                ym, fuente = self._ym(et["cultivo"], et.get("segunda", False), et.get("tardio", False))
                if ym is not None:
                    fila["rinde_kg_ha"] = {e: round(rinde_por_agua(ym, cult["ky"], acumulado[i][e]["eta"], acumulado[i][e]["etc"])) for e in ESC}
                    fila["rinde_fuente"] = f"rinde de referencia: {fuente}; ajustado por agua con FAO-33 (Ky {cult['ky']})"
                    if pastura:
                        # La pastura da forraje (kg de materia seca por ha): no se calcula balance de N y P de grano
                        fila["rinde_unidad"] = "kg de materia seca de forraje por ha"
                        res.cultivos.append(fila)
                        continue
                    t = fila["rinde_kg_ha"].get("medio", median(fila["rinde_kg_ha"].values())) / 1000
                    if cult.get("n_export_kg_t") is None:
                        sin_dato = True
                    else:
                        fert = self.p.fertilizacion.get(et["cultivo"], Fertilizacion())
                        fijacion = (cult.get("ndfa") or 0) * (cult.get("n_absorbido_kg_t") or 0) * t
                        extra = 0.0
                        primero = not ya_extra
                        ya_extra = True
                        if primero and estado.extra_n is not None:
                            extra = estado.extra_n
                            fila["n_por_analisis_kg_ha"] = round(extra, 1)
                        fila["n_balance_kg_ha"] = round(fert.n_kg_ha + fijacion + extra - cult["n_export_kg_t"] * t, 1)
                        fila["p_balance_kg_ha"] = round(fert.p_kg_ha - cult["p_export_kg_t"] * t, 1)
                        n_total += fila["n_balance_kg_ha"]
                        p_total += fila["p_balance_kg_ha"]
                elif not pastura:
                    sin_dato = True
            res.cultivos.append(fila)
        if not sin_dato:
            res.n_balance, res.p_balance = round(n_total, 1), round(p_total, 1)
        if ya_extra:
            nuevo.extra_n = None  # los nitratos medidos ya los usó un cultivo de grano
        return res, nuevo


# ---------------------------------------------------------------- reglas y planificación

def clave_termica(et: dict) -> str:
    return "maiz_tardio" if et["cultivo"] == "maiz" and et.get("tardio") else et["cultivo"]


def ajustar_por_temperatura_suelo(cat: dict, tsuelo: list[float | None] | None) -> tuple[dict, list[dict], set[str]]:
    """Filtro térmico de siembra (revisión agronómica del equipo, spec 062 §6 octies).

    Para cada cultivo de cada ocupación compara la temperatura media del suelo (0 a 10 cm, NASA POWER TSOIL1) del mes de
    siembra con el mínimo del catálogo. Estados: «factible» (el mes alcanza), «esperar» (un mes siguiente alcanza: la
    siembra y la cosecha se corren, y si la cosecha se pasa de abril el ciclo se acorta como mucho
    `acortar_ciclo_max_meses`) y «no_factible» (ningún mes alcanza o el ciclo no entra). Devuelve el catálogo con el
    calendario corrido (copia; el original no cambia), el detalle por cultivo y las ocupaciones no factibles.
    """
    ts = cat.get("temperatura_suelo_siembra")
    if not ts or not tsuelo:
        return cat, [], set()
    minimos, maximo_acortar = ts["minimo_c"], ts.get("acortar_ciclo_max_meses", 0)
    ocupaciones, detalle, no_factibles = {}, [], set()
    for o, etapas in cat["ocupaciones"].items():
        nuevas, fin_anterior = [], None
        for et in etapas:
            minimo = minimos.get(clave_termica(et))
            if minimo is None or tsuelo[et["siembra"]] is None:
                nuevas.append(et)
                fin_anterior = et["cosecha"]
                continue
            # La siembra no puede ir antes de que termine el cultivo anterior de la ocupación (en diciembre comparten el mes)
            desde = max(et["siembra"], fin_anterior if fin_anterior is not None else 0)
            mes = next((m for m in range(desde, 12) if tsuelo[m] is not None and tsuelo[m] >= minimo), None)
            fila = {"ocupacion": o, "cultivo": et["cultivo"], "clave": clave_termica(et), "minimo_c": minimo,
                    "rango": ts.get("rango", {}).get(clave_termica(et)), "siembra_mes": et["siembra"],
                    "tsuelo_siembra_c": tsuelo[et["siembra"]]}
            if mes is None:
                fila["estado"] = "no_factible"
                no_factibles.add(o)
                detalle.append(fila)
                nuevas.append(et)
                continue
            cosecha = et["cosecha"] + (mes - et["siembra"])
            acorta = max(0, cosecha - 11)
            if acorta > maximo_acortar or min(cosecha, 11) < mes:
                fila.update(estado="no_factible", siembra_posible_mes=mes, meses_que_faltan=acorta)
                no_factibles.add(o)
                detalle.append(fila)
                nuevas.append(et)
                continue
            if mes == et["siembra"]:
                fila["estado"] = "factible"
                nuevas.append(et)
            else:
                fila.update(estado="esperar", siembra_nueva_mes=mes, tsuelo_siembra_nueva_c=tsuelo[mes], ciclo_acortado_meses=acorta)
                nuevas.append({**et, "siembra": mes, "cosecha": min(cosecha, 11)})
            fin_anterior = nuevas[-1]["cosecha"]
            detalle.append(fila)
        ocupaciones[o] = nuevas
    return {**cat, "ocupaciones": ocupaciones}, detalle, no_factibles


def cultivos_de(cat: dict, ocupacion: str) -> list[str]:
    return [e["cultivo"] for e in cat["ocupaciones"][ocupacion]]


def variantes_de(cat: dict, ocupacion: str) -> set[str]:
    """Los nombres con que el dueño puede excluir algo de la ocupación: cultivo, cultivo de segunda (soja_2da) o tardío (maiz_tardio)."""
    nombres = set()
    for e in cat["ocupaciones"][ocupacion]:
        nombres.add(e["cultivo"])
        if e.get("segunda"):
            nombres.add(f"{e['cultivo']}_2da")
        if e.get("tardio"):
            nombres.add(f"{e['cultivo']}_tardio")
    return nombres


@dataclass
class Nodo:
    secuencia: list[str]
    estado: Estado
    resultados: list[ResultadoCampana]
    blandas: list[str]


class Planificador:
    def __init__(self, pedido: PedidoRotacion, cat: dict | None = None):
        self.p = pedido
        self.cat, self.termico, self.no_factibles_termico = ajustar_por_temperatura_suelo(cat or cargar_catalogo(), pedido.clima.tsuelo_c)
        self.sim = Simulador(pedido, self.cat)
        self.descartes: dict[str, int] = {}
        self.ejemplos_descarte: dict[str, str] = {}
        self.inicio = anio(pedido.campana_inicial)
        self.historia = {}  # índice relativo de campaña → cultivos (grano, pastura o cobertura)
        for ev in pedido.historial:
            self.historia.setdefault(anio(ev.campana) - self.inicio, []).append(ev.cultivo.replace("_2da", ""))
        from rotaterra.rotacion.ph_del_lote import evaluar_ph
        self.ph = evaluar_ph(pedido.analisis_suelo, pedido.observaciones, self.cat)
        self._cache_temp: dict = {}
        mz = self.cat.get("malezas") or {"resistentes": [], "presentes_por_defecto": []}
        ids = {m["id"] for m in mz["resistentes"]}
        presentes = pedido.malezas_presentes if pedido.malezas_presentes is not None else mz["presentes_por_defecto"]
        if ids and set(presentes) - ids:
            raise ValueError(f"Maleza desconocida: {', '.join(sorted(set(presentes) - ids))}. Las malezas son: {', '.join(sorted(ids))}")
        self.malezas = [m for m in mz["resistentes"] if m["id"] in presentes]
        self.malezas_supuestas = pedido.malezas_presentes is None
        self._cache_malezas: dict = {}
        cr = self.cat["costo_riego"]
        self.costo_riego = pedido.lote.riego_costo_usd_mm if pedido.lote.riego_costo_usd_mm is not None else cr["usd_por_mm_ha"]
        if pedido.lote.riego_mm_mes and any(pedido.lote.riego_mm_mes):
            if pedido.lote.riego_costo_usd_mm is not None:
                self.sim.supuestos.append(f"Riego: se restan {self.costo_riego:g} US$ por cada mm regado por ha (dato del productor)")
            else:
                self.sim.supuestos.append(f"Riego: se restan {self.costo_riego:g} US$ por cada mm regado por ha. {cr['nota']}")
        self.ocupaciones = self._ocupaciones_permitidas()
        self.pesos = self._pesos()

    # Qué ocupaciones se pueden usar en este lote
    def _ocupaciones_permitidas(self) -> list[str]:
        cat, p = self.cat, self.p
        base = p.ocupaciones or list(cat["ocupaciones"])
        fuera = set(p.excluidas)
        from rotaterra.rotacion.ph_del_lote import combinar
        por_ph = self.ph["viabilidad"]
        for c, estado in combinar(p.viabilidad, por_ph).items():
            if estado == "no_viable" or (estado == "no_recomendable" and not p.incluir_no_recomendables):
                fuera.add(c)
                if c in por_ph and por_ph[c] == estado:
                    ph = self.ph["ph"]
                    self._descartar(f"ph_{estado}", f"{c}: {estado.replace('_', ' ')} por pH {ph['valor']:g} ({ph['fuente']})")
                else:
                    self._descartar(f"viabilidad_{estado}", f"{c}: {estado.replace('_', ' ')} según el filtro de viabilidad del lote")
        permitidas = []
        for o in base:
            if o not in cat["ocupaciones"]:
                raise ValueError(f"Ocupación desconocida: {o}")
            if o in fuera or any(c in fuera for c in variantes_de(cat, o)):
                continue
            if o in self.no_factibles_termico:
                f = next(x for x in self.termico if x["ocupacion"] == o and x["estado"] == "no_factible")
                self._descartar("temperatura_suelo", f"{o}: el suelo no llega a {f['minimo_c']:g} °C para sembrar {self.cat['cultivos'][f['cultivo']]['nombre'].lower()} a tiempo")
                continue
            permitidas.append(o)
        if not permitidas:
            raise ValueError("No queda ninguna ocupación posible para el lote")
        return permitidas

    def _pesos(self) -> dict[str, float]:
        perfil = self.p.perfil
        if isinstance(perfil, str) and perfil not in self.cat["perfiles"]:
            raise ValueError(f"Perfil desconocido: {perfil}. Los perfiles son: {', '.join(self.cat['perfiles'])}")
        return dict(self.cat["perfiles"][perfil]) if isinstance(perfil, str) else {k: perfil.get(k, 0.0) for k in INDICADORES}

    def _descartar(self, motivo: str, ejemplo: str) -> None:
        self.descartes[motivo] = self.descartes.get(motivo, 0) + 1
        self.ejemplos_descarte.setdefault(motivo, ejemplo)

    def _cultivos_en(self, secuencia: list[str], t: int) -> list[str]:
        if t < 0:
            return self.historia.get(t, [])
        return cultivos_de(self.cat, secuencia[t]) if t < len(secuencia) else []

    # Reglas duras de secuencia: True si la ocupación se puede poner en la campaña t
    def admite(self, secuencia: list[str], ocupacion: str, registrar: bool = True) -> bool:
        t = len(secuencia)
        etiqueta_t = etiqueta(self.inicio + t)
        fijada = self.p.fijadas.get(etiqueta_t)
        if fijada and fijada != ocupacion:
            return False
        nuevos = [c for c in cultivos_de(self.cat, ocupacion) if c != "centeno_cobertura"]
        # La alfalfa que sigue su propio bloque de años no se repite: es la misma pastura
        sigue_bloque = ocupacion == "alfalfa" and bool(secuencia) and secuencia[-1] == "alfalfa"
        for regla in self.cat["reglas_secuencia"]:
            if regla["tipo"] != "dura" or "campanas_sin_repetir" not in regla or regla["cultivo"] not in nuevos or sigue_bloque:
                continue
            for k in range(1, regla["campanas_sin_repetir"] + 1):
                if regla["cultivo"] in self._cultivos_en(secuencia, t - k):
                    if registrar:
                        self._descartar(regla["id"], f"{etiqueta_t}: {regla['texto']}")
                    return False
        for h in self.p.herbicidas:
            a = anio(h.campana) - self.inicio
            if a < t <= a + h.campanas_de_espera and any(c in h.cultivos_sensibles for c in nuevos):
                if registrar:
                    self._descartar("residualidad_herbicida", f"{etiqueta_t}: {h.producto} aplicado en {h.campana} deja sensible a {', '.join(h.cultivos_sensibles)} por {h.campanas_de_espera} campaña(s)")
                return False
        return True

    def oferta_agua(self, c: dict, t: int) -> dict[str, float]:
        """Oferta de agua del filtro hídrico de la revisión agronómica, en mm por escenario: agua útil del suelo a la siembra
        más la lluvia y el riego de los meses del ciclo."""
        pc = self.p.clima.primera_campana
        riego = self.p.lote.riego_mm_mes or [0.0] * 12
        out = {}
        for e, au in c["agua_util_siembra_mm"].items():
            lluvia = pc["lluvia_mm"][e] if t == 0 and pc else self.p.clima.lluvia_mm[e]
            out[e] = round(au + sum(lluvia[m] + riego[m] for m in range(c["siembra_mes"], c["cosecha_mes"] + 1)))
        return out

    def umbral_agua(self, c: dict) -> float | None:
        regla = next((r for r in self.cat["reglas_secuencia"] if r["id"] == "cultivo_con_agua"), None)
        return regla["umbral_mm"].get(clave_termica(c)) if regla else None

    def estados_cultivo(self, ocupacion: str, c: dict, t: int) -> dict:
        """Estados de factibilidad de la revisión agronómica para mostrar: térmico (suelo a la siembra y heladas) e hídrico."""
        out = {}
        fila = next((x for x in self.termico if x["ocupacion"] == ocupacion and x["cultivo"] == c["cultivo"]), None)
        et = next((e for e in self.cat["ocupaciones"][ocupacion] if e["cultivo"] == c["cultivo"]), None)
        heladas = et is not None and (r := self.riesgo_temperatura(et)) and any(a.startswith("helada") for a in r["avisos"])
        if fila or heladas:
            estado = "riesgoso" if heladas and (not fila or fila["estado"] != "no_factible") else fila["estado"]
            texto = {"factible": "el suelo ya está a temperatura para sembrar",
                     "riesgoso": "hay heladas en una etapa sensible en 1 de cada 5 campañas o más",
                     "no_factible": "el suelo no llega a la temperatura de siembra a tiempo"}.get(estado, "")
            if fila and fila["estado"] == "esperar":
                texto = (f"suelo frío en {MESES[fila['siembra_mes']]} ({fila['tsuelo_siembra_c']:g} °C, mínimo {fila['minimo_c']:g} °C): "
                         f"la siembra se corre a {MESES[fila['siembra_nueva_mes']]}") + (f"; además {texto}" if estado == "riesgoso" else "")
            out["estado_termico"] = {"estado": estado, "texto": texto}
        umbral = self.umbral_agua(c)
        if umbral is not None:
            oferta = self.oferta_agua(c, t)
            estado = "no_factible" if oferta["medio"] < umbral else "riesgoso" if oferta.get("seco", umbral) < umbral else "factible"
            out["estado_hidrico"] = {"estado": estado, "oferta_mm": oferta, "umbral_mm": umbral,
                                     "texto": {"factible": f"agua del suelo más lluvia llega a {umbral:g} mm (60 % de su demanda) aun en año seco",
                                               "riesgoso": f"en año normal llega a {umbral:g} mm; en año seco tiene {oferta.get('seco')} mm",
                                               "no_factible": f"en año normal tiene {oferta['medio']} mm y necesita {umbral:g} mm"}[estado]}
        return out

    def _conocida(self, t: int) -> bool:
        """True si se sabe qué hubo en la campaña t: las del plan siempre; las anteriores, solo si están en el historial."""
        return t >= 0 or t in self.historia

    def blandas(self, secuencia: list[str]) -> list[str]:
        """Reglas blandas que rompe la última campaña de la secuencia: campañas seguidas con el mismo cultivo, antecesores no
        recomendados (matriz de la revisión agronómica) y una sola familia de cultivos en la ventana de campañas."""
        avisos = []
        t = len(secuencia) - 1
        for regla in self.cat["reglas_secuencia"]:
            if regla["tipo"] != "blanda":
                continue
            if "antes" in regla:
                if regla["antes"] in self._cultivos_en(secuencia, t - 1) and regla["despues"] in self._cultivos_en(secuencia, t):
                    avisos.append(f"{etiqueta(self.inicio + t)}: {regla['texto']}")
                continue
            if "minimo_familias" in regla:
                ventana = range(t - regla["ventana"] + 1, t + 1)
                if all(self._conocida(k) for k in ventana):
                    por_campana = [{self.cat["cultivos"][c]["familia"] for c in self._cultivos_en(secuencia, k) if c in self.cat["cultivos"]}
                                   for k in ventana]
                    familias = set().union(*por_campana)
                    # Un barbecho corta la secuencia: hace falta que al menos 2 campañas de la ventana tengan cultivo
                    if sum(1 for f in por_campana if f) >= 2 and len(familias) < regla["minimo_familias"]:
                        avisos.append(f"{etiqueta(self.inicio + t)}: {regla['texto']}")
                continue
            seguidas = 0
            k = t
            while regla["cultivo"] in self._cultivos_en(secuencia, k):
                seguidas += 1
                k -= 1
            if seguidas > regla["max_seguidas"]:
                avisos.append(f"{etiqueta(self.inicio + t)}: {regla['texto']}")
        return avisos

    def riesgo_sanitario(self, secuencia: list[str]) -> float:
        riesgo = 0.0
        for t in range(len(secuencia)):
            for org in self.cat["organismos"]:
                presentes = sum(1 for k in range(0, org["persistencia_campanas"])
                                if any(c in org["hospedantes"] for c in self._cultivos_en(secuencia, t - k)))
                riesgo += max(0, presentes - 1)
        return riesgo

    def _herramientas(self, cultivos: list[str], estacion: str) -> tuple[list[str], bool]:
        """Grupos de herbicidas de la estación (invierno o verano) y si hay centeno; sin cultivo en esa estación, los del barbecho."""
        mz = self.cat["malezas"]
        en_estacion = [c for c in cultivos if mz["estacion_del_cultivo"].get(c, "verano") == estacion or c == "alfalfa"]
        centeno = "centeno_cobertura" in en_estacion
        granos = [c for c in en_estacion if c != "centeno_cobertura"]
        if not granos:
            return list(mz["barbecho"]["grupos"]), centeno
        return sorted({g for c in granos for g in mz["por_cultivo"].get(c, {}).get("grupos", [])}), centeno

    def malezas_campana(self, secuencia: list[str], t: int) -> tuple[list[str], list[str]]:
        """Lo bueno y lo que hay que vigilar con las malezas resistentes en la campaña t (REM-Aapresid, spec 062 §6 septies).

        Para cada maleza del lote se cuentan los grupos de herbicidas que la controlan en esa estación y que no resiste
        (más el centeno, que la suprime). Con menos de 2 herramientas, o si el cultivo no tiene herbicida selectivo contra
        ella, hay que vigilar. También se marca si el grupo base se repite respecto de la campaña anterior (la REM pide no
        repetir el mismo sitio de acción).
        """
        if not self.cat.get("malezas"):
            return [], []
        ahora = cultivos_de(self.cat, secuencia[t]) if t < len(secuencia) else []
        antes = self._cultivos_en(secuencia, t - 1)
        clave = (tuple(ahora), tuple(antes))
        if clave in self._cache_malezas:
            return self._cache_malezas[clave]
        mz = self.cat["malezas"]
        a_favor, cuidado = [], []
        minimo = mz["herramientas_minimas"]
        for m in self.malezas:
            corto = m["nombre"].split(" (")[0]
            grupos, centeno = self._herramientas(ahora, m["estacion"])
            sirven = [g for g in grupos if g not in m["resistente_a"] and mz["grupos_hrac"][g]["controla"] in (m["tipo"], "ambas")]
            sin_selectivo = [c for c in ahora if c in m.get("sin_control_selectivo_en", [])]
            if sin_selectivo:
                cuidado.append(f"{corto}: no hay herbicida que la controle dentro del {self.cat['cultivos'][sin_selectivo[0]]['nombre'].lower()} sin dañarlo")
            elif len(sirven) + (1 if centeno and m["id"] in mz["centeno_suprime"] else 0) < minimo:
                resiste = [mz["grupos_hrac"][g]["nombre"].split(" (")[0] for g in m["resistente_a"]]
                cuidado.append(f"{corto}: pocas herramientas en {m['estacion']} (resiste {' y '.join(resiste)}; queda"
                               + (" solo " + ", ".join(f"el grupo {g}: {mz['grupos_hrac'][g]['nombre']}" for g in sirven) + ")"
                                  if sirven else " ningún grupo)"))
            if centeno and m["id"] in mz["centeno_suprime"]:
                a_favor.append(f"el centeno compite con la {corto.lower()}")
        base = lambda cs: next((mz["por_cultivo"][c]["base"] for c in cs if mz["por_cultivo"].get(c, {}).get("base")), None)
        # Se compara el primer cultivo de esta campaña con el último de la anterior (en trigo/soja de 2ª, la soja)
        b_ahora, b_antes = base(ahora), base([c for c in reversed(antes) if c in self.cat["cultivos"]])
        if b_ahora and b_antes:
            if b_ahora == b_antes:
                cuidado.append(f"repite el herbicida base de la campaña anterior (grupo {b_ahora}: {mz['grupos_hrac'][b_ahora]['nombre']})")
            else:
                a_favor.append(f"cambia el herbicida base (grupo {b_antes} a grupo {b_ahora})")
        self._cache_malezas[clave] = (a_favor, cuidado)
        return a_favor, cuidado

    def riesgo_malezas(self, secuencia: list[str]) -> int:
        return sum(len(self.malezas_campana(secuencia, t)[1]) for t in range(len(secuencia)))

    def expandir(self, nodo: Nodo) -> list[Nodo]:
        hijos = []
        if nodo.secuencia and nodo.secuencia[-1] == "alfalfa":
            bloque = 0
            for o in reversed(nodo.secuencia):
                if o != "alfalfa":
                    break
                bloque += 1
            if bloque % self.cat["cultivos"]["alfalfa"]["anios"] != 0:
                opciones = ["alfalfa"]
            else:
                opciones = self.ocupaciones
        else:
            opciones = self.ocupaciones
        regla_segunda = next(r for r in self.cat["reglas_secuencia"] if r["id"] == "segunda_con_agua")
        for o in opciones:
            if not self.admite(nodo.secuencia, o):
                continue
            res, estado = self.sim.campana(o, nodo.estado, t=len(nodo.secuencia))
            segunda = [c for c in res.cultivos if c["segunda"]]
            if segunda and segunda[0]["agua_relativa"]["medio"] < regla_segunda["agua_relativa_minima"]:
                self._descartar("segunda_sin_agua", f"{etiqueta(self.inicio + len(nodo.secuencia))} {o}: la segunda cubre el "
                                f"{segunda[0]['agua_relativa']['medio'] * 100:.0f} % de su demanda de agua en el año medio")
                continue
            t = len(nodo.secuencia)
            falta = next((c for c in res.cultivos if not c["segunda"] and self.umbral_agua(c) is not None
                          and self.oferta_agua(c, t)["medio"] < self.umbral_agua(c)), None)
            if falta:
                self._descartar("cultivo_sin_agua", f"{etiqueta(self.inicio + t)} {o}: el {falta['nombre'].lower()} tiene "
                                f"{self.oferta_agua(falta, t)['medio']} mm (agua del suelo a la siembra más lluvia del ciclo) en el año medio "
                                f"y necesita {self.umbral_agua(falta):g} mm")
                continue
            seq = nodo.secuencia + [o]
            hijos.append(Nodo(seq, estado, nodo.resultados + [res], nodo.blandas + self.blandas(seq)))
        return hijos

    # Indicadores de un plan (ver NOMBRE_INDICADOR)
    def indicadores(self, nodo: Nodo) -> dict[str, float | None]:
        rs = nodo.resultados
        n = len(rs)
        margen_esc, faltan_precios = self.margenes(nodo)
        if margen_esc is not None:
            e = margen_esc["medio"] / n
            r = (margen_esc["medio"] - margen_esc["seco"]) / n
        elif self.p.precios:
            # Con precios, un plan con un cultivo sin precio (por ejemplo, maní) no se mezcla con otra unidad: queda neutro
            e, r = None, None
        else:
            # Sin precios: producción relativa = suma de (rinde del año medio / rinde de referencia) por campaña
            prod = [c["rinde_kg_ha"]["medio"] / self._ref(c) for x in rs for c in x.cultivos if "rinde_kg_ha" in c and self._ref(c)]
            e = sum(prod) / n if prod else None
            rel = [(c["rinde_kg_ha"]["seco"], c["rinde_kg_ha"]["medio"]) for x in rs for c in x.cultivos if "rinde_kg_ha" in c]
            r = 1 - sum(a for a, _ in rel) / sum(b for _, b in rel) if rel and sum(b for _, b in rel) > 0 else None
        cultivos_agua = [c["agua_relativa"]["seco"] for x in rs for c in x.cultivos if c["cultivo"] != "centeno_cobertura"]
        # Balance de N + P por unidad producida (kg/ha por cada "rinde regional" cosechado), en las campañas con dato.
        # Se divide por la producción para que un barbecho, que no se lleva nutrientes porque no produce, no salga premiado.
        # Una campaña con un cultivo sin dato de extracción no entra
        bal, prod = 0.0, 0.0
        for x in rs:
            if x.cultivos and x.n_balance is None:
                continue
            bal += x.n_balance or 0.0
            bal += x.p_balance or 0.0
            prod += sum(c["rinde_kg_ha"]["medio"] / self._ref(c) for c in x.cultivos if "rinde_kg_ha" in c and self._ref(c))
        s = bal / prod if prod > 0.1 else None
        especies = [c["cultivo"] for x in rs for c in x.cultivos]
        return {
            "E": round(e, 1) if e is not None else None,
            "S": round(s, 1) if s is not None else None,
            "W": round(sum(cultivos_agua) / len(cultivos_agua), 3) if cultivos_agua else 0.0,
            "C": round(sum(x.carbono_t_ha["medio"] for x in rs) / n, 2),
            "B": round(sum(x.cobertura_media["medio"] for x in rs) / n, 1),
            "H": round(self.riesgo_sanitario(nodo.secuencia) + 2 * len(nodo.blandas) + self.riesgo_malezas(nodo.secuencia), 1),
            "D": round(shannon(especies), 3),
            "R": round(r, 3) if r is not None else None,
        }

    def mes_floracion(self, et: dict) -> int:
        """Mes de la campaña (0 = mayo) en que florece el cultivo."""
        tc = self.cat.get("temperaturas_criticas") or {}
        fr = self.cat["cultivos"][et["cultivo"]].get("etapas", [0.25, 0.25, 0.3, 0.2])
        s, c = et["siembra"], et["cosecha"]
        antes = tc.get("floracion_meses_antes_de_cosecha", {}).get(et["cultivo"])
        return c - antes if isinstance(antes, int) else min(c, s + int((c - s + 1) * (fr[0] + fr[1])))

    def cociente_fototermal(self, et: dict) -> dict | None:
        """Q del trigo en el período crítico (20 días antes a 10 después de la floración), campaña por campaña de la serie
        de NASA POWER, con la fórmula del INTA (spec 062, §6 decies). Es información: no cambia el rinde ni descarta."""
        cq = self.cat.get("cociente_fototermal")
        if not cq or et["cultivo"] not in cq["cultivos"]:
            return None
        mes = self.mes_floracion(et)
        valores = [(x["campana"], x["q_trigo"][mes]) for x in (self.p.clima.serie or [])
                   if x.get("q_trigo") and x["q_trigo"][mes] is not None]
        if len(valores) < 10:
            return None
        qs = sorted(v for _, v in valores)
        pct = lambda f: qs[min(len(qs) - 1, int(round(f * (len(qs) - 1))))]  # noqa: E731
        por_escenario = {}
        for esc, campana in (self.p.clima.campanas_escenario or {}).items():
            q = dict(valores).get(campana)
            if q is not None:
                por_escenario[esc] = {"campana": campana, "q": q}
        largos = ["mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre", "enero", "febrero",
                  "marzo", "abril"]
        return {"floracion": f"mediados de {largos[mes]}", "campanas": len(qs),
                "q_bajo": pct(0.2), "q_mediano": round(median(qs), 2), "q_alto": pct(0.8),
                "minimo": qs[0], "maximo": qs[-1], "por_campana": dict(valores),
                "escenarios_de_lluvia": por_escenario}

    def riesgo_temperatura(self, et: dict) -> dict | None:
        """Heladas y calor en las etapas clave de un cultivo, contados en las campañas reales de la serie (spec 062, §6 ter)."""
        serie = [c for c in (self.p.clima.serie or []) if c.get("tmin_c") and c.get("dias_mas_35")]
        tc = self.cat.get("temperaturas_criticas")
        if len(serie) < 10 or not tc:
            return None
        clave = (et["cultivo"], et["siembra"], et["cosecha"])
        if clave in self._cache_temp:
            return self._cache_temp[clave]
        s, c = et["siembra"], et["cosecha"]
        flor = self.mes_floracion(et)
        meses = {"emergencia": s, "floracion": flor, "llenado": min(c, flor + 1)}
        nombres = {"emergencia": "la emergencia", "floracion": "la floración", "llenado": "el llenado de granos"}
        n, avisos, detalle = len(serie), [], {}
        fuentes = self.cat["fuentes"]
        hel = tc["helada_c"].get(et["cultivo"])
        if hel:
            for etapa, mes in meses.items():
                if etapa not in hel:
                    continue
                k = sum(1 for x in serie if x["tmin_c"][mes] <= hel[etapa])
                detalle[f"helada_{etapa}"] = {"mes": MESES[mes], "critica_c": hel[etapa], "campanas": k, "de": n}
                if k / n >= tc["aviso_desde_fraccion"]:
                    avisos.append(f"helada de {hel[etapa]:g} °C o menos en {nombres[etapa]} ({MESES[mes]}) en {k} de {n} campañas "
                                  f"({fuentes[hel['fuente']].split(':')[0]})")
        cal = tc["calor_periodo_critico"].get(et["cultivo"])
        if cal:
            mes = meses[cal["etapa"]]
            k = sum(1 for x in serie if x["dias_mas_35"][mes] >= 1)
            dias = median(x["dias_mas_35"][mes] for x in serie)
            detalle["calor"] = {"mes": MESES[mes], "campanas_con_dias_mas_35": k, "de": n, "mediana_dias": dias}
            if k / n >= tc["aviso_desde_fraccion"]:
                avisos.append(f"calor de más de 35 °C en {cal['texto']} ({MESES[mes]}) en {k} de {n} campañas, "
                              f"mediana {dias:g} días ({fuentes[tc['calor_periodo_critico']['fuente']].split(':')[0]})")
        self._cache_temp[clave] = {"avisos": avisos, "detalle": detalle}
        return self._cache_temp[clave]

    def _ref(self, c: dict) -> float | None:
        clave = f"{c['cultivo']}_2da" if c["segunda"] and f"{c['cultivo']}_2da" in self.sim.yref else c["cultivo"]
        return self.sim.yref.get(clave)

    def margen_campana(self, res: "ResultadoCampana", escenarios) -> tuple[dict[str, float], set[str]]:
        """Margen de una campaña por escenario (o ingreso bruto si no se cargaron costos) y los cultivos sin precio,
        sin costo o sin rinde. Una sola regla para el plan y para la distribución con toda la serie."""
        usar_costos = bool(self.p.costos)
        faltan: set[str] = set()
        alquiler = self.cat["arrendamiento_san_luis"]["usd_ha_campana"] if self.p.lote.tenencia == "alquilado" else 0.0
        total = {e: -alquiler - res.riego_mm.get(e, 0.0) * self.costo_riego for e in escenarios}
        if not res.cultivos and (costo_b := self.p.costos.get("barbecho")):
            for e in escenarios:
                total[e] -= costo_b.valor
        for c in res.cultivos:
            nombre = f"{c['cultivo']}_2da" if c.get("segunda") and f"{c['cultivo']}_2da" in self.p.costos else c["cultivo"]
            costo = self.p.costos.get(nombre)
            if usar_costos and costo is None:
                faltan.add(nombre)
                continue
            gasto = costo.valor if costo else 0.0
            if c["cultivo"] == "centeno_cobertura":
                for e in escenarios:
                    total[e] -= gasto
                continue
            precio = self.p.precios.get(nombre) or self.p.precios.get(c["cultivo"])
            if precio is None or "rinde_kg_ha" not in c:
                # La alfalfa da forraje: sin ganadería en el motor no tiene ingreso; queda como faltante
                faltan.add(nombre)
                continue
            for e in escenarios:
                total[e] += c["rinde_kg_ha"][e] / 1000 * precio.valor - gasto
        return total, faltan

    def margenes(self, nodo: Nodo) -> tuple[dict[str, float] | None, list[str]]:
        """Margen por escenario (o ingreso bruto si no se cargaron costos). None si falta el precio de algún cultivo."""
        faltan = set()
        total = {e: 0.0 for e in ESCENARIOS}
        for x in nodo.resultados:
            m, f = self.margen_campana(x, ESCENARIOS)
            faltan |= f
            for e in ESCENARIOS:
                total[e] += m[e]
        return (None, sorted(faltan)) if faltan else (total, [])

    # Búsqueda: todas las secuencias si son pocas; si no, haz de búsqueda por perfil
    def buscar(self) -> list[Nodo]:
        raiz = Nodo([], self.estado_inicial(ESCENARIOS), [], [])
        capa = [raiz]
        total_posible = len(self.ocupaciones) ** self.p.horizonte
        self.modo = "exhaustivo" if total_posible <= EXHAUSTIVO_HASTA else f"haz de búsqueda ({BEAM} por perfil y campaña)"
        for _ in range(self.p.horizonte):
            siguiente = [h for nodo in capa for h in self.expandir(nodo)]
            if not siguiente:
                return []
            if self.modo != "exhaustivo" and len(siguiente) > BEAM:
                siguiente = self._podar(siguiente)
            capa = siguiente
        return capa

    def estado_inicial(self, escenarios, registrar: bool = True) -> Estado:
        """Agua, rastrojo y lo que dice el análisis de suelo al empezar la primera campaña."""
        rastrojo = self._rastrojo_inicial(registrar)["medio"]
        a = self.p.analisis_suelo
        extra_n = a.n_no3_kg_ha_0_60 if a and a.n_no3_kg_ha_0_60 is not None else None
        return Estado(au={e: self.sim.au0 for e in escenarios}, rastrojo={e: rastrojo for e in escenarios}, extra_n=extra_n)

    def _rastrojo_inicial(self, registrar: bool = True) -> dict[str, float]:
        ultimos = self.historia.get(-1, [])
        kg = 3000.0 if any(c in ("maiz", "sorgo", "trigo") for c in ultimos) else 1500.0 if ultimos else 500.0
        if not ultimos and registrar and self.p.lote.uso_anterior not in ("virgen", "pastura") and not any("poco rastrojo" in s for s in self.sim.supuestos):
            self.sim.supuestos.append("Sin campaña anterior en el historial: se arranca con poco rastrojo (500 kg/ha)")
        return {e: kg for e in ESCENARIOS}

    def _podar(self, nodos: list[Nodo]) -> list[Nodo]:
        inds = [self.indicadores(n) for n in nodos]
        elegidos: set[int] = set()
        for pesos in list(self.cat["perfiles"].values()) + [self.pesos]:
            puntajes = puntaje(inds, pesos)
            orden = sorted(range(len(nodos)), key=lambda i: (-puntajes[i], nodos[i].secuencia))
            elegidos.update(orden[:BEAM])
        return [nodos[i] for i in sorted(elegidos, key=lambda i: nodos[i].secuencia)]


def normalizar(inds: list[dict], clave: str) -> list[float] | None:
    """0 = la peor alternativa evaluada, 1 = la mejor. Un valor sin dato queda en 0,5 (neutro): ni premia ni castiga."""
    vals = [x[clave] for x in inds]
    conocidos = [v for v in vals if v is not None]
    if not conocidos:
        return None
    lo, hi = min(conocidos), max(conocidos)
    if hi == lo:
        return [0.5] * len(vals)
    return [0.5 if v is None else ((v - lo) / (hi - lo)) if SENTIDO[clave] > 0 else ((hi - v) / (hi - lo)) for v in vals]


def puntaje(inds: list[dict], pesos: dict[str, float]) -> list[float]:
    norm = {k: normalizar(inds, k) for k in INDICADORES}
    usados = {k: w for k, w in pesos.items() if w > 0 and norm.get(k) is not None}
    suma = sum(usados.values()) or 1.0
    return [sum(w / suma * norm[k][i] for k, w in usados.items()) for i in range(len(inds))]


def frente_pareto(inds: list[dict]) -> list[int]:
    """Planes que ningún otro supera en todos los indicadores a la vez (comparación vectorizada, por bloques)."""
    # Un indicador sin dato en algunos planes (por ejemplo, el margen de un plan con un cultivo sin precio) se
    # compara con la mediana de los demás, igual que en el puntaje (neutro), en vez de sacar ese indicador para todos.
    claves = [k for k in INDICADORES if any(x[k] is not None for x in inds)]
    if not inds or not claves:
        return list(range(len(inds)))
    neutro = {k: median([x[k] for x in inds if x[k] is not None]) for k in claves}
    v = np.array([[SENTIDO[k] * (x[k] if x[k] is not None else neutro[k]) for k in claves] for x in inds], dtype=float)
    frente = []
    for ini in range(0, len(v), 256):
        bloque = v[ini:ini + 256]
        mejor_o_igual = (v[None, :, :] >= bloque[:, None, :]).all(axis=2)
        estricto = (v[None, :, :] > bloque[:, None, :]).any(axis=2)
        dominado = (mejor_o_igual & estricto).any(axis=1)
        frente += [ini + i for i in np.flatnonzero(~dominado)]
    return [int(i) for i in frente]


# ---------------------------------------------------------------- salida

MESES = ["may", "jun", "jul", "ago", "sep", "oct", "nov", "dic", "ene", "feb", "mar", "abr"]


def _clase_erosion(valor: float | None) -> str | None:
    """Días-equivalentes de suelo desnudo con viento erosivo en la campaña (umbrales provisionales)."""
    if valor is None:
        return None
    return "bajo" if valor < UMBRAL_EROSION[0] else "medio" if valor < UMBRAL_EROSION[1] else "alto"


AGUA_POCA = 0.5  # menos de la mitad del agua que necesita el cultivo: riesgo (lo usan los riesgos del plan y el semáforo)
FAMILIA_SIMPLE = {"poaceae": "gramínea", "fabaceae": "leguminosa", "asteraceae": "compuesta (girasol)", "malvaceae": "malvácea (algodón)"}


def semaforo_de_pases(pl: Planificador, nodo: Nodo, campanas: list[dict]) -> list[dict]:
    """Verde, amarillo o rojo para cada cambio de cultivo del plan, con el por qué (spec 062, §6 quinquies).

    Idea tomada de la revisión del documento de Leandro: el color es solo para mostrar y sale de lo que el motor ya
    calculó (sanidad, familia, nitrógeno, agua, suelo y reglas blandas); no cambia el puntaje ni el orden de los planes.
    Rojo: incumple una regla blanda, en el año medio un cultivo cubre menos de la mitad de su agua o la erosión es alta.
    Amarillo: hay algo para vigilar. Verde: nada para vigilar.
    """
    cat = pl.cat
    pases = []
    principales = lambda cs: [c for c in cs if c != "centeno_cobertura" and c in cat["cultivos"]]
    for t, o in enumerate(nodo.secuencia):
        antes = principales(pl._cultivos_en(nodo.secuencia, t - 1))
        ahora = principales(cultivos_de(cat, o))
        a_favor, cuidado, grave = [], [], []
        # Sanidad: hospedantes que se repiten dentro de lo que dura el inóculo, o que se cortan
        repite, corta, frena, repite_ids = [], [], [], []
        for org in cat["organismos"]:
            corto = org["nombre"].split(" (")[0]
            hosp_ahora = any(c in org["hospedantes"] for c in ahora)
            hosp_antes = any(c in org["hospedantes"] for k in range(1, org["persistencia_campanas"])
                             for c in pl._cultivos_en(nodo.secuencia, t - k))
            if hosp_ahora and hosp_antes:
                repite.append(corto)
                repite_ids.append(org["id"])
            elif not hosp_ahora and any(c in org["hospedantes"] for c in antes):
                (corta if org["persistencia_campanas"] <= 2 else frena).append(corto)
        if repite:
            cuidado.append("vuelve a sembrar un hospedante de: " + ", ".join(repite))
        if corta:
            a_favor.append("corta el ciclo de: " + ", ".join(corta))
        if frena:
            a_favor.append("frena (sin cortarlo del todo, el inóculo dura varias campañas): " + ", ".join(frena))
        prefijo = etiqueta(pl.inicio + t) + ": "
        grave.extend(b[len(prefijo):] for b in dict.fromkeys(nodo.blandas) if b.startswith(prefijo))
        # Familia y nitrógeno
        fam_antes = {cat["cultivos"][c]["familia"] for c in antes}
        fam_ahora = {cat["cultivos"][c]["familia"] for c in ahora}
        if fam_antes and fam_ahora:
            mismas = fam_antes & fam_ahora
            if mismas:
                cuidado.append("misma familia que la campaña anterior (" + ", ".join(FAMILIA_SIMPLE.get(f, f) for f in sorted(mismas)) + ")")
            else:
                a_favor.append("cambia de familia de cultivo")
            if "fabaceae" in fam_antes and fam_ahora - {"fabaceae"}:
                a_favor.append("aprovecha el nitrógeno que deja la leguminosa")
        if not ahora:
            a_favor.append("descanso: sin hospedantes de enfermedades y guarda agua" if antes else "descanso")
        mf, mc = pl.malezas_campana(nodo.secuencia, t)
        a_favor.extend(mf)
        cuidado.extend(mc)
        # Agua y suelo, de la simulación de esta campaña
        for cu in campanas[t]["cultivos"]:
            if cu["cultivo"] == "centeno_cobertura":
                continue
            medio, seco = cu["agua_relativa"]["medio"], cu["agua_relativa"]["seco"]
            if medio < AGUA_POCA:
                grave.append(f"{cu['nombre']}: en el año medio cubre solo el {medio * 100:.0f} % del agua que necesita")
            elif seco < AGUA_POCA:
                cuidado.append(f"{cu['nombre']}: en año seco cubre solo el {seco * 100:.0f} % del agua")
        if campanas[t]["erosion_eolica"].get("medio") == "alto":
            grave.append("erosión por viento alta en el año medio")
        elif campanas[t]["cobertura_media_pct"].get("medio", 0) >= 70:
            a_favor.append(f"suelo cubierto el {campanas[t]['cobertura_media_pct']['medio']:.0f} % del año")
        color = "rojo" if grave else "amarillo" if cuidado else "verde"
        pases.append({
            "campana": campanas[t]["campana"],
            "de": (" + ".join(cat["cultivos"][c]["nombre"] if c in cat["cultivos"] else c.replace("_", " ")
                              for c in pl._cultivos_en(nodo.secuencia, t - 1))
                   or ("barbecho" if t > 0 else "sin historial del lote")),
            "a": " + ".join(cu["nombre"] for cu in campanas[t]["cultivos"]) or "barbecho",
            "color": color,
            "a_favor": a_favor,
            "cuidado": grave + cuidado,
            "enfermedades_repetidas": repite_ids,
        })
    return pases


def pedido_ocupaciones(pl: "Planificador") -> set[str]:
    return set(pl.p.ocupaciones or pl.cat["ocupaciones"])


def describir_plan(pl: Planificador, nodo: Nodo, ind: dict, mediana: dict, etiqueta_plan: str, nombres: dict) -> dict:
    campanas = []
    for t, (o, res) in enumerate(zip(nodo.secuencia, nodo.resultados)):
        campanas.append({
            "campana": etiqueta(pl.inicio + t),
            "ocupacion": o,
            "cultivos": [{**{k: v for k, v in c.items() if k not in ("siembra_mes", "cosecha_mes")},
                          "siembra": MESES[c["siembra_mes"]], "cosecha": MESES[c["cosecha_mes"]],
                          **pl.estados_cultivo(o, c, t)} for c in res.cultivos],
            "agua_util_final_mm": res.au_final,
            "drenaje_mm": res.drenaje_mm,
            **({"riego_aplicado_mm": res.riego_mm, "costo_riego_usd_ha": {e: round(v * pl.costo_riego, 1) for e, v in res.riego_mm.items()}}
               if any(res.riego_mm.values()) else {}),
            "meses_cubiertos_30": res.meses_cubiertos,
            "cobertura_media_pct": res.cobertura_media,
            "erosion_eolica": {e: _clase_erosion(v) for e, v in res.erosion_eolica.items()},
            "carbono_entra_t_ha": res.carbono_t_ha,
            "balance_n_kg_ha": res.n_balance,
            "balance_p_kg_ha": res.p_balance,
        })
    motivos, riesgos = [], []
    for k in INDICADORES:
        if ind[k] is None or mediana.get(k) is None:
            continue
        mejor = SENTIDO[k] * (ind[k] - mediana[k]) > 0
        if mejor and pl.pesos.get(k, 0) > 0 or (etiqueta_plan != "elegido" and mejor):
            motivos.append(f"{nombres[k][0].upper()}{nombres[k][1:]}: {ind[k]} (mediana de las alternativas: {mediana[k]})")
    riesgos.extend(sorted(set(nodo.blandas)))
    for c in campanas:
        for cu in c["cultivos"]:
            if cu["cultivo"] != "centeno_cobertura" and cu["agua_relativa"]["seco"] < AGUA_POCA:
                riesgos.append(f"{c['campana']} {cu['nombre']}: en año seco cubre solo el {cu['agua_relativa']['seco'] * 100:.0f} % del agua que necesita")
        if c["erosion_eolica"].get("medio") == "alto":
            riesgos.append(f"{c['campana']}: riesgo de erosión eólica alto en el año medio (suelo poco cubierto con viento)")
    for org in pl.cat["organismos"]:
        n = sum(1 for o in nodo.secuencia for c in cultivos_de(pl.cat, o) if c in org["hospedantes"])
        if n >= max(3, len(nodo.secuencia) - 1):
            riesgos.append(f"{org['nombre']}: {n} de {len(nodo.secuencia)} campañas con hospedantes")
    if pl.p.lote.uso_anterior in ("virgen", "pastura"):
        vistas = set()
        for c in campanas:
            for cu in c["cultivos"]:
                if pl.cat["cultivos"][cu["cultivo"]]["familia"] == "fabaceae" and cu["cultivo"] not in vistas:
                    vistas.add(cu["cultivo"])
                    riesgos.append(f"{c['campana']} {cu['nombre']}: primera leguminosa de ese tipo en un suelo que nunca la tuvo, "
                                   "no hay rizobios propios: inocular la semilla sí o sí")
    vistos_temp = set()
    for t, o in enumerate(nodo.secuencia):
        for et in pl.cat["ocupaciones"][o]:
            clave = (et["cultivo"], et["siembra"])
            r = pl.riesgo_temperatura(et) if clave not in vistos_temp else None
            vistos_temp.add(clave)
            if r and r["avisos"]:
                nombre = pl.cat["cultivos"][et["cultivo"]]["nombre"] + (" tardío" if et.get("tardio") else "") + (" de segunda" if et.get("segunda") else "")
                riesgos.append(f"{nombre}: " + "; ".join(r["avisos"]))
    for c in campanas:
        for cu in c["cultivos"]:
            et = cu.get("estado_termico")
            if et and "se corre" in et["texto"]:
                riesgos.append(f"{c['campana']} {cu['nombre']}: {et['texto']}")
    vistos_ph = set()
    for c in campanas:
        for cu in c["cultivos"]:
            for texto in pl.ph["riesgos_por_cultivo"].get(cu["cultivo"], []):
                if cu["cultivo"] not in vistos_ph:
                    riesgos.append(f"{cu['nombre']}: {texto}" if texto.startswith("Precaución")
                                   else f"{cu['nombre']} con pH {pl.ph['ph']['valor']:g}: {texto}")
            vistos_ph.add(cu["cultivo"])
    margen, faltan = pl.margenes(nodo)
    return {
        "secuencia": nodo.secuencia,
        "indicadores": ind,
        "margen_total": {e: round(v) for e, v in margen.items()} if margen else None,
        "margen_faltan": faltan,
        "campanas": campanas,
        "motivos": motivos,
        "riesgos": riesgos,
        "reglas_blandas_incumplidas": len(nodo.blandas),
        "semaforo": semaforo_de_pases(pl, nodo, campanas),
    }


def _pct(valores: list[float], q: float) -> float:
    orden = sorted(valores)
    return orden[max(0, min(len(orden) - 1, math.ceil(q * len(orden)) - 1))]


def distribucion(pl: "Planificador", secuencia: list[str]) -> dict | None:
    """Corre el plan con cada campaña real de la serie como punto de partida (años seguidos, como pasaron)
    y devuelve P10, P50 y P90 de cada rinde, del agua cubierta y del resultado del plan (SDD §8.3)."""
    serie = pl.p.clima.serie
    if not serie or len(serie) < 10:
        return None
    n = len(serie)
    nombres = [f"k{k}" for k in range(n)]
    estado = pl.estado_inicial(nombres, registrar=False)
    campanas, total_prod, total_margen = [], {e: 0.0 for e in nombres}, {e: 0.0 for e in nombres}
    con_margen, usar_costos = bool(pl.p.precios), bool(pl.p.costos)
    for t, o in enumerate(secuencia):
        esc = {f"k{k}": (serie[(k + t) % n]["lluvia_mm"], serie[(k + t) % n]["eto_mm"]) for k in range(n)}
        res, estado = pl.sim.campana(o, estado, escenarios=esc)
        m, faltan = pl.margen_campana(res, nombres)
        if faltan:
            con_margen = False
        for e in nombres:
            total_margen[e] += m[e]
        filas = []
        for c in res.cultivos:
            fila = {"cultivo": c["cultivo"], "segunda": c["segunda"],
                    "agua_cubierta_p10": round(_pct(list(c["agua_relativa"].values()), 0.1), 2)}
            if "rinde_kg_ha" in c:
                vals = list(c["rinde_kg_ha"].values())
                fila["rinde_kg_ha"] = {"p10": round(_pct(vals, 0.1)), "p50": round(_pct(vals, 0.5)), "p90": round(_pct(vals, 0.9))}
                if ref := pl._ref(c):
                    for e in nombres:
                        total_prod[e] += c["rinde_kg_ha"][e] / ref
            filas.append(fila)
        ero = [v for v in res.erosion_eolica.values() if v is not None]
        campanas.append({"campana": etiqueta(pl.inicio + t), "cultivos": filas,
                         "erosion_eolica_p90": _clase_erosion(_pct(ero, 0.9)) if ero else None})
    total = total_margen if con_margen else total_prod
    vals = [v / len(secuencia) for v in total.values()]
    return {"campanas_de_la_serie": n, "metodo": f"el plan corrido {n} veces, cada vez arrancando en una campaña distinta de "
            f"{serie[0]['campana']} a {serie[-1]['campana']} y siguiendo con los años que vinieron después (al final vuelve al principio)",
            "resultado": ("margen_por_campana" if usar_costos else "ingreso_bruto_por_campana") if con_margen else "produccion_relativa_por_campana",
            "p10": round(_pct(vals, 0.1), 2), "p50": round(_pct(vals, 0.5), 2), "p90": round(_pct(vals, 0.9), 2),
            "campanas": campanas}


def por_ambiente(pl: "Planificador", secuencia: list[str]) -> dict | None:
    """El plan en el bajo del lote, que recibe el agua que escurre de la loma y la media loma (NASADEM).

    La loma y la media loma se simulan como el lote (el relieve no dice cuánta agua guarda cada una). El bajo recibe,
    además de su lluvia, el escurrimiento de la superficie de arriba, repartido en su superficie y con un tope."""
    amb = pl.p.lote.ambientes_ha
    if not amb or amb.bajo <= 0 or amb.loma + amb.media_loma <= 0 or not pl.p.clima.serie:
        return None
    reg = pl.cat["ambientes"]
    veces = min(reg["aporte_maximo"], (amb.loma + amb.media_loma) / amb.bajo)
    antes = pl.sim.aporte_ladera
    pl.sim.aporte_ladera = veces
    try:
        bajo = distribucion(pl, secuencia)
    finally:
        pl.sim.aporte_ladera = antes
    total = amb.loma + amb.media_loma + amb.bajo
    salida = {"superficie_ha": {"loma": amb.loma, "media_loma": amb.media_loma, "bajo": amb.bajo}, "fuente": amb.fuente,
              "bajo_recibe": f"{veces:.1f} veces su propio escurrimiento", "nota": reg["nota"],
              "bajo": {"p10": bajo["p10"], "p50": bajo["p50"], "p90": bajo["p90"], "resultado": bajo["resultado"],
                       "rinde_p50": [{"campana": c["campana"], "cultivos": {f["cultivo"]: f["rinde_kg_ha"]["p50"] for f in c["cultivos"] if "rinde_kg_ha" in f}}
                                     for c in bajo["campanas"]]} if bajo else None}
    if amb.bajo / total >= reg["aviso_bajo_desde_fraccion"]:
        salida["aviso"] = (f"El {amb.bajo / total * 100:.0f} % del lote es bajo: conviene manejarlo como ambiente aparte "
                           "(densidad, fertilización y cultivo), y mirar anegamiento y sales si la napa sube")
    return salida


def aptitud_del_suelo(pl: "Planificador") -> dict | None:
    """Clase de capacidad de uso e índice de productividad del INTA (cartas de suelo), con lo que significa para el plan."""
    lote = pl.p.lote
    if lote.capacidad_uso is None and lote.indice_productividad is None:
        return None
    reg = pl.cat["capacidad_uso"]
    salida = {"capacidad_uso": lote.capacidad_uso, "indice_productividad": lote.indice_productividad, "fuente": lote.suelo_fuente,
              "regla": reg["nota"]}
    if lote.capacidad_uso is not None:
        salida["significado"] = reg["clases"][str(lote.capacidad_uso)]
        if lote.capacidad_uso >= reg["no_arable_desde"]:
            salida["aviso"] = ("Según la carta de suelos del INTA, este lote no es apto para agricultura: los planes con cultivos "
                               "de grano son solo orientativos; lo indicado es pastura permanente o monte")
        elif lote.capacidad_uso == reg["no_arable_desde"] - 1:
            salida["aviso"] = "Clase 4: agricultura muy limitada; conviene rotar con pasturas varios años y cuidar la cobertura"
    return salida


def contexto(pl: "Planificador", planes: dict) -> dict | None:
    """Datos de la zona traídos de los satélites y mapas, puestos al lado del plan elegido."""
    ctx = pl.p.contexto_satelital
    if not ctx:
        return None
    try:
        return _contexto(pl, planes, ctx)
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        return {"datos": ctx, "avisos": [], "error": f"contexto_satelital con formato inesperado ({error!r}): no se usó"}


def _contexto(pl: "Planificador", planes: dict, ctx: dict) -> dict:
    salida, avisos = {"datos": ctx}, []
    cos = ctx.get("carbono_organico_0_30cm_t_ha")
    if cos and (elegido := planes.get("elegido")):
        entra = sum(c["carbono_entra_t_ha"].get("medio", 0) for c in elegido["campanas"])
        avisos.append(f"El suelo guarda unas {cos['valor']:.0f} t de carbono por ha en 0-30 cm ({cos['fuente']}). El plan elegido devuelve "
                      f"{entra:.1f} t de carbono por ha en {len(elegido['campanas'])} campañas con rastrojo y raíces; solo una parte "
                      "queda en el suelo")
    napa = ctx.get("napa_percentil")
    if napa:
        if napa["valor"] <= 10:
            avisos.append(f"Agua subterránea en el {napa['valor']:.0f} % más bajo de su historia ({napa['fuente']}): no contar con aporte de napa")
        elif napa["valor"] >= 90:
            avisos.append(f"Agua subterránea en el {napa['valor']:.0f} % más alto de su historia ({napa['fuente']}): riesgo de anegamiento en los bajos")
    fut = ctx.get("clima_futuro")
    if fut:
        ind = fut["indicadores"]
        partes = []
        if "dias_calor_35" in ind:
            d = ind["dias_calor_35"]
            partes.append(f"días de más de 35 °C por año: {d['historico']:.0f} hoy, {d['ssp245']:.0f} a {d['ssp585']:.0f} hacia 2041-2060")
        if "lluvia_campana_mm" in ind:
            d = ind["lluvia_campana_mm"]
            partes.append(f"lluvia de la campaña: {d['historico']:.0f} mm, {d['ssp245']:.0f} a {d['ssp585']:.0f} mm")
        if partes:
            avisos.append("Clima que viene según los modelos de la NASA (NEX-GDDP-CMIP6, proyección, no pronóstico): " + "; ".join(partes)
                          + ". Va más allá del horizonte del plan: sirve para elegir cultivos que toleren calor")
    salida["avisos"] = avisos
    return salida


def planificar(pedido: PedidoRotacion, cat: dict | None = None) -> dict:
    pl = Planificador(pedido, cat)
    hojas = pl.buscar()
    if not hojas:
        return {"estado": "sin_solucion", "descartes": pl.descartes, "ejemplos_descarte": pl.ejemplos_descarte,
                "faltantes": pl.sim.faltantes, "aviso": "Ninguna secuencia cumple las reglas duras. Revisá las fijadas y las exclusiones."}
    inds = [pl.indicadores(n) for n in hojas]
    mediana = {k: (round(median([x[k] for x in inds if x[k] is not None]), 3) if any(x[k] is not None for x in inds) else None) for k in INDICADORES}
    pareto = frente_pareto(inds)
    nombres = {**NOMBRE_INDICADOR, **({} if pedido.precios and pedido.costos else {"E": SIN_COSTOS} if pedido.precios else {"E": SIN_PRECIOS})}
    planes = {}
    _dist: dict[tuple, dict | None] = {}

    def dist(secuencia: list[str]) -> dict | None:
        # Varios perfiles suelen elegir la misma secuencia: la serie completa se corre una sola vez por secuencia
        clave = tuple(secuencia)
        if clave not in _dist:
            _dist[clave] = distribucion(pl, secuencia)
        return _dist[clave]

    pedidos = {"elegido": pl.pesos, "rentabilidad": pl.cat["perfiles"]["rentabilidad"],
               "conservacion": pl.cat["perfiles"]["conservacion"], "equilibrado": pl.cat["perfiles"]["equilibrado"]}
    pts_elegido = puntaje(inds, pl.pesos)
    for nombre, pesos in pedidos.items():
        pts = puntaje(inds, pesos)
        i = max(range(len(hojas)), key=lambda j: (pts[j], [-ord(ch) for ch in "|".join(hojas[j].secuencia)]))
        # Porcentaje 0-100 para mostrar (revisión del equipo, Leandro, 10/11/2026): el puntaje de este plan con los
        # pesos del productor, contra las demás alternativas evaluadas. 100 = la mejor alternativa para su perfil.
        planes[nombre] = {"puntaje": round(pts[i], 3), "porcentaje_para_tu_perfil": round(100 * pts_elegido[i]),
                          "en_frente_pareto": i in pareto, **describir_plan(pl, hojas[i], inds[i], mediana, nombre, nombres),
                          "distribucion": dist(hojas[i].secuencia)}
    if not pedido.precios:
        planes["rentabilidad"]["aviso"] = ("Sin precios el margen no se calcula: este plan maximiza la producción relativa "
                                           "al rinde regional, no la plata")
    elif not pedido.costos:
        planes["rentabilidad"]["aviso"] = ("Sin costos cargados este plan maximiza el ingreso bruto (rinde por precio), "
                                           "no el margen: un cultivo caro de hacer puede quedar mejor de lo que es")
    base = _plan_actual(pl)
    if base:
        base["distribucion"] = dist(base["secuencia"])
    faltantes = list(pl.sim.faltantes)
    if not pedido.precios:
        faltantes.append({"dato": "precios y costos", "criticidad": "importante",
                          "por_que": "sin ellos no hay margen bruto ni plan de rentabilidad",
                          "supuesto": "el motor compara por agua, suelo, sanidad y riesgo"})
    else:
        sin_precio = sorted({c for o in pl.ocupaciones for c in cultivos_de(pl.cat, o)
                             if c not in pedido.precios and c not in ("centeno_cobertura", "alfalfa")})
        if sin_precio:
            faltantes.append({"dato": "precio de " + ", ".join(pl.cat["cultivos"][c]["nombre"].lower() for c in sin_precio),
                              "criticidad": "importante", "por_que": "la pizarra de Rosario no los cotiza",
                              "supuesto": "los planes con esos cultivos quedan neutros en el resultado económico"})
        sin_rinde = sorted({c for o in pl.ocupaciones for c in cultivos_de(pl.cat, o)
                            if c in pedido.precios and c not in pl.sim.yref and c not in ("centeno_cobertura", "alfalfa")})
        if sin_rinde:
            faltantes.append({"dato": "rinde de " + ", ".join(pl.cat["cultivos"][c]["nombre"].lower() for c in sin_rinde)
                                      + " en el lote o la zona", "criticidad": "importante",
                              "por_que": "no hay rinde de referencia de San Luis (el de MAGyP para el algodón es del Chaco y "
                                         "Santiago del Estero)",
                              "supuesto": "los planes con esos cultivos quedan neutros en el resultado económico"})
        if any("alfalfa" in cultivos_de(pl.cat, o) for o in pl.ocupaciones) and (
                "alfalfa" not in pedido.precios or "alfalfa" not in pedido.rindes_referencia):
            falta_alf = ([] if "alfalfa" in pedido.rindes_referencia else ["producción (kg de materia seca por ha, en rindes_referencia)"]) \
                + ([] if "alfalfa" in pedido.precios else ["valor (US$ por t de materia seca, en precios)"])
            faltantes.append({"dato": "forraje de la alfalfa: " + " y ".join(falta_alf), "criticidad": "opcional",
                              "por_que": "la alfalfa produce pasto para la hacienda; con esos dos datos el motor calcula su margen",
                              "supuesto": "los planes con alfalfa quedan neutros en el resultado económico"})
        if not pedido.costos:
            faltantes.append({"dato": "costos por cultivo", "criticidad": "importante",
                              "por_que": "sin ellos el resultado es ingreso bruto, no margen",
                              "supuesto": "costo cero para todos los cultivos"})
    uso = pedido.lote.uso_anterior
    if uso in ("virgen", "pastura"):
        if not any("Lote sin agricultura" in s for s in pl.sim.supuestos):
            pl.sim.supuestos.append(f"Lote sin agricultura anterior ({'monte o pastizal natural' if uso == 'virgen' else 'pastura o campo natural'}): "
                                    "no hay rastrojo de cosecha, ni inóculo de enfermedades de los cultivos, ni residuos de herbicidas")
    elif not pedido.historial:
        faltantes.append({"dato": "historial del lote", "criticidad": "critica",
                          "por_que": "las reglas de retorno (girasol, maní) miran las campañas anteriores",
                          "supuesto": "se asume que en las últimas campañas no hubo girasol ni maní; si nunca se cultivó, marcalo como terreno virgen"})
    avisos_lote = list(pl.cat["uso_anterior"].get(uso, {}).get("avisos", []))
    lectura = leer_analisis(pedido.analisis_suelo, pl.cat) if pedido.analisis_suelo else None
    ph = pl.ph["ph"]
    if ph is None:
        faltantes.append({"dato": "pH del lote", "criticidad": "importante",
                          "por_que": "el pH decide qué cultivos entran en los planes (topes de la base de cultivos)",
                          "supuesto": "no se descartó ningún cultivo por pH: cargá el análisis o consultá el lote para tener el pH de referencia"})
    elif not ph["medido"]:
        faltantes.append({"dato": "pH medido del lote", "criticidad": "importante",
                          "por_que": "el pH de referencia no descarta cultivos, solo avisa precaución; el del análisis decide",
                          "supuesto": f"pH no medido: se usó {ph['valor']:g} de {ph['fuente']}"})
    if not pedido.analisis_suelo:
        faltantes.append({"dato": "análisis de suelo del lote", "criticidad": "importante",
                          "por_que": "el pH, el fósforo y los nitratos medidos mandan sobre los mapas regionales",
                          "supuesto": "sin nitratos medidos a la siembra; pH de referencia o sin pH"})
    if pedido.lote.tenencia == "alquilado":
        pl.sim.supuestos.append(f"Campo alquilado: se restan {pl.cat['arrendamiento_san_luis']['usd_ha_campana']:g} US$/ha por campaña "
                                "(7 qq de soja, MAGyP región San Luis, junio 2026)")
    inferidas = sorted({ev.campana for ev in pedido.historial if ev.evidencia == "inferido"})
    avisos_datos = [f"Historial {', '.join(inferidas)} inferido por satélite (Mapa Nacional de Cultivos): confirmalo"] if inferidas else []
    return {
        "estado": "completado_con_avisos" if faltantes or avisos_datos else "completado",
        "estado_evaluacion": "preliminar",
        "lote": pedido.lote.nombre,
        "campanas": [etiqueta(pl.inicio + t) for t in range(pedido.horizonte)],
        "perfil": pedido.perfil,
        "pesos": pl.pesos,
        "planes": planes,
        "como_leer_porcentaje": ("porcentaje_para_tu_perfil compara cada plan con todas las alternativas evaluadas, con los "
                                 "pesos del perfil del productor: 100 es la mejor para ese perfil (revisión del equipo, 10/11/2026)"),
        "plan_actual": base,
        "alternativas_evaluadas": len(hojas),
        "frente_pareto": len(pareto),
        "busqueda": pl.modo,
        "mediana_alternativas": mediana,
        "descartes": pl.descartes,
        "ejemplos_descarte": pl.ejemplos_descarte,
        "faltantes": faltantes,
        "avisos_datos": avisos_datos,
        "uso_anterior": uso,
        "avisos_por_uso_anterior": avisos_lote,
        "analisis_suelo": lectura,
        "ph_del_lote": {**pl.ph, "regla": ("con laboratorio y fecha manda y descarta; escrito por el productor reemplaza al mapa "
                                            "y deja el cultivo no recomendable; en los dos casos, hasta 0,3 fuera del rango el "
                                            "cultivo queda tolerable con aviso (revisión agronómica del equipo); sin pH medido "
                                            "se usa el de referencia (perfiles del INTA o mapa) y no descarta: el plan avisa "
                                            "precaución por esa fuente")} if ph else None,
        "heladas_y_calor": {(pl.cat["cultivos"][et["cultivo"]]["nombre"] + (" tardío" if et.get("tardio") else "") + (" de segunda" if et.get("segunda") else "")):
                            pl.riesgo_temperatura(et) for o in pl.ocupaciones for et in pl.cat["ocupaciones"][o]
                            if et["cultivo"] in pl.cat["temperaturas_criticas"]["helada_c"] and pl.riesgo_temperatura(et)},
        "cociente_fototermal_trigo": _q_trigo(pl),
        "filtro_termico": None if not pl.termico else {
            "fuente": pl.cat["fuentes"][pl.cat["temperatura_suelo_siembra"]["fuente"]],
            "dato": pl.cat["fuentes"][pl.cat["temperatura_suelo_siembra"]["fuente_dato"]],
            "como_se_mide": pl.cat["temperatura_suelo_siembra"]["nota"],
            "tsuelo_c": dict(zip(MESES, pedido.clima.tsuelo_c)),
            "cultivos": [{**x, "siembra_mes": MESES[x["siembra_mes"]],
                          **({"siembra_nueva_mes": MESES[x["siembra_nueva_mes"]]} if "siembra_nueva_mes" in x else {}),
                          **({"siembra_posible_mes": MESES[x["siembra_posible_mes"]]} if "siembra_posible_mes" in x else {})}
                         for x in pl.termico if x["ocupacion"] in pedido_ocupaciones(pl)]},
        "variedades_inta": _variedades(pl, planes),
        "semillas_recomendadas": _semillas(pl, planes["elegido"]),
        "malezas": None if not pl.cat.get("malezas") else {"presentes": [m["nombre"] for m in pl.malezas],
                    "origen": ("supuestas: " + pl.cat["malezas"]["por_defecto_nota"]) if pl.malezas_supuestas else "dato del productor",
                    "como_se_mide": "por campaña, cuántos grupos de herbicidas (HRAC) que el cultivo permite controlan cada maleza sin que ella "
                                    f"los resista (más el centeno contra la rama negra); con menos de {pl.cat['malezas']['herramientas_minimas']} "
                                    "o con el mismo herbicida base que la campaña anterior, suma al riesgo sanitario (H) y sale en el semáforo",
                    "fuente": pl.cat["fuentes"][pl.cat["malezas"]["fuente"]], "nota": pl.cat["malezas"]["nota"]},
        "ambientes": por_ambiente(pl, planes["elegido"]["secuencia"]),
        "aptitud_del_suelo": aptitud_del_suelo(pl),
        "contexto_satelital": contexto(pl, planes),
        "precios_usados": {k: v.model_dump() for k, v in pedido.precios.items()},
        "datos_del_pipeline": pedido.datos_del_pipeline,
        "supuestos": pl.sim.supuestos + [pl.cat["aviso"], "Los indicadores se comparan entre 0 y 1 contra el rango de las alternativas evaluadas"],
        "clima": {"fuente": pedido.clima.fuente, "detalle": pedido.clima.detalle, "escala": pedido.clima.escala,
                  "primera_campana": ({k: pedido.clima.primera_campana[k] for k in ("fase", "oni_ultimo", "fuente", "detalle")}
                                      if pedido.clima.primera_campana else None)},
        "indicadores_significado": nombres,
        "versiones": {"motor": VERSION_MOTOR, "catalogo": pl.cat["version"], "catalogo_estado": pl.cat["estado"]},
        "aviso": "Es una ayuda para decidir. No reemplaza el asesoramiento de un ingeniero agrónomo.",
    }


def _variedades(pl: "Planificador", planes: dict) -> dict | None:
    """Variedades del INTA del banco de semillas para los cultivos que aparecen en los planes (si el banco está)."""
    from rotaterra.rotacion.variedades import variedades_inta
    cultivos = sorted({c for p in planes.values() for o in p["secuencia"] for c in cultivos_de(pl.cat, o)})
    return variedades_inta(cultivos)


def _q_trigo(pl: "Planificador") -> dict | None:
    """Cociente fototermal (Q) del trigo para cada forma de sembrarlo que se pidió (spec 062, §6 decies)."""
    cq = pl.cat.get("cociente_fototermal")
    if not cq:
        return None
    pedidas = pedido_ocupaciones(pl)
    vistos, salida = set(), []
    for o in pl.ocupaciones:
        if o not in pedidas:
            continue
        for et in pl.cat["ocupaciones"][o]:
            clave = (et["cultivo"], et["siembra"], et["cosecha"])
            if clave in vistos:
                continue
            vistos.add(clave)
            q = pl.cociente_fototermal(et)
            if q:
                salida.append({"cultivo": pl.cat["cultivos"][et["cultivo"]]["nombre"], "ocupacion": o, **q})
    if not salida:
        return None
    return {"que_es": cq["que_es"], "formula": cq["formula"], "periodo": cq["periodo"], "dato": cq["dato"],
            "como_leerlo": cq["como_leerlo"], "fuentes": [pl.cat["fuentes"][f] for f in cq["fuentes"]],
            "cambia_el_rinde": False, "trigo": salida}


def _semillas(pl: "Planificador", plan: dict) -> dict | None:
    """Semillas recomendadas para cada cultivo del plan elegido (spec 062, §6 sexies), si el banco de semillas está."""
    from rotaterra.rotacion.variedades import recomendar_semillas
    ph = (pl.ph or {}).get("ph") or {}
    return recomendar_semillas(pl.cat, plan, [c["campana"] for c in plan["campanas"]], ph.get("valor"))


def leer_analisis(a: "AnalisisSuelo", cat: dict) -> dict:
    """Muestra el análisis del lote y arma los avisos que tienen fuente (INTA)."""
    avisos = []
    if a.ph is not None:
        if a.ph >= 8.0:
            avisos.append(f"pH {a.ph:g}: suelo alcalino. Riesgo de falta de hierro y zinc (clorosis en soja) y, arriba de 8,5, "
                          "de sodio que baja el rinde del maíz (INTA). Revisá micronutrientes")
        if a.ph > 6.5:
            avisos.append(f"Maní: el INTA Manfredi recomienda pH 5,8 a 6,5; con {a.ph:g} puede faltar manganeso")
    if a.n_no3_kg_ha_0_60 is not None:
        avisos.append(f"Nitratos medidos: {a.n_no3_kg_ha_0_60:g} kg N/ha (0-60 cm). Entran al balance de nitrógeno del primer cultivo de grano")
    return {"valores": a.model_dump(exclude_none=True), "avisos": avisos}


def _plan_actual(pl: Planificador) -> dict | None:
    """Repetir lo último que se sembró (por ejemplo, soja continua), para comparar contra la situación actual."""
    ultimos = pl.historia.get(-1)
    if not ultimos:
        return None
    candidatas = [o for o, et in pl.cat["ocupaciones"].items() if sorted(cultivos_de(pl.cat, o)) == sorted(ultimos)]
    if not candidatas:
        return None
    o = candidatas[0]
    nodo = Nodo([], pl.estado_inicial(ESCENARIOS, registrar=False), [], [])
    duras = []
    for t in range(pl.p.horizonte):
        if not pl.admite(nodo.secuencia, o, registrar=False):
            duras.append(f"{etiqueta(pl.inicio + t)}: rompe una regla dura de retorno")
        res, est = pl.sim.campana(o, nodo.estado, t=t)
        seq = nodo.secuencia + [o]
        nodo = Nodo(seq, est, nodo.resultados + [res], nodo.blandas + pl.blandas(seq))
    ind = pl.indicadores(nodo)
    return {"secuencia": nodo.secuencia, "indicadores": ind, "reglas_duras_rotas": duras,
            "reglas_blandas_incumplidas": len(nodo.blandas), "riesgos": sorted(set(nodo.blandas))}
