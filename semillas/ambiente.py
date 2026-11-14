"""Requerimientos ambientales por especie: la capa del dossier de investigación del 31/10/2026 (spec 061).

Hernán subió un dossier armado con ChatGPT (ampliaciones 06 a 10, libro de 59 pestañas transcripto como CSV) y eligió
el 31/10/2026 "Argentino + FAO marcado global". Se pasan a una tabla larga solo las pestañas con datos (temperatura,
heladas, calor, suelo, sales, sodio, pH, Kc, raíces, nutrientes, ensayos y ambiente de San Luis), sin cambiar los
valores. Cada fila guarda fuente, unidad, etapa, sitio y un nivel de evidencia: "San Luis", "Argentina" o "global"
(FAO, EcoCrop y estudios de otros países). Es una capa aparte de las fichas por variedad y del manejo por cultivo:
el motor no la usa para descartar cultivos.
"""
import csv
import re
from pathlib import Path
from urllib.parse import urlparse

CARPETA = Path(__file__).resolve().parent / "datos" / "raw" / "dossier_2026-10-31"
COLUMNAS = ["capa", "cultivo", "cultivo_banco", "especie", "cultivar", "variable", "valor", "unidad", "etapa", "sitio",
            "campana", "metodo", "nivel", "nivel_original", "fuente", "fuente_url", "advertencia", "pestana",
            "verificacion"]
NIVELES = ("San Luis", "Argentina", "global")
VERIFICACION = "dossier ChatGPT 31/10/2026, sin releer el original"
# pestañas cotejadas número por número con el documento original
LEIDAS = {"A10_Clima_Centro.csv": "texto leído: tesis Riglos (2023), cuadro 2.3, PDF original subido por Hernán el 31/10/2026",
          "A11_Suelos_SanLuis.csv": "texto leído: tesis Riglos (2023), cap. 5, PDF original subido por Hernán el 31/10/2026",
          "A07_Emergencia_Raiz.csv": "texto leído: UNRC, Sistema suelo-planta (2018), tablas 8.2 y 8.4, PDF bajado el 31/10/2026",
          "A25_Stress_hidrico_ORA.csv": "texto leído: ORA 2018, Mapas de áreas aptas, cuadro 2, PDF bajado el 31/10/2026",
          "A30_Lote06_SanLuis.csv": "texto leído: nota INTA San Luis en argentina.gob.ar (Riglos), bajada el 31/10/2026",
          "A90_Tesis_UNSL.csv": "texto leído: trabajos finales UNSL-FICA (Lujan 2024, Tello 2024), PDF bajado el 04/11/2026",
          "A91_pH_argentino.csv": "pH con fuente argentina, búsqueda del 04/11/2026: la advertencia dice si se leyó el texto o solo el resumen",
          "A92_Mejoramiento_soja.csv": "texto leído: Abdala, Otegui y Di Mauro (2026), Field Crops Research 351, tabla 2 (PDF subido por Hernán; no va al repo)",
          "A31_Lote06_salino.csv": "texto leído: revista INTA Fruticultura & Diversificación n.º 98 (2025), PDF bajado el 31/10/2026"}
FAO = ("FAO", "EcoCrop", "OpenCLIM", "Maas", "SAGIT")
ARGENTINA = ("INTA", "INASE", "SISA", "EEAOC", "SAGyP", "ORA", "MAGyP", "UNRC", "UNLP", "UNR", "UNC", "UNLPam",
             "UNNE", "FAUBA", "UBA", "Riglos", "Agricultura")
ECOCROP_URL = "https://ecocrop.apps.fao.org/ecocrop/srv/en/search"

# nombre del dossier -> cultivo del banco (None = no está en el banco o mezcla varios cultivos)
BANCO = [("Arveja fresca", None), ("Colza/rapeseed", None), ("Lupino", None), ("Haba", None),
         ("Alfalfa", "Alfalfa"), ("Algodón", "Algodón"), ("Arroz", "Arroz"), ("Arveja", "Arveja"), ("Avena", "Avena"), ("Caupí", "Caupí"),
         ("Caña", "Caña de azúcar"), ("Cebada", "Cebada"), ("Centeno", "Centeno"), ("Colza", "Colza/Canola"),
         ("Cártamo", "Cártamo"), ("Garbanzo", "Garbanzo"), ("Girasol", "Girasol"), ("Lenteja", "Lenteja"),
         ("Lino", "Lino"), ("Maní", "Maní"), ("Maíz", "Maíz"), ("Mostaza", "Mostazas (carinata, juncea)"),
         ("Papa", "Papa"), ("Poroto", "Porotos (negro, alubia, colorado)"), ("Quinoa", "Quinoa"), ("Soja", "Soja"),
         ("Sorgo", "Sorgo"), ("Trigo", "Trigo"), ("Triticale", "Triticale")]


def cultivo_banco(nombre: str) -> str:
    if "," in nombre or " y " in nombre:
        return ""
    for prefijo, banco in BANCO:
        if nombre.startswith(prefijo):
            return banco or ""
    return ""


def nivel(sitio: str, fuente: str, url: str) -> str:
    """San Luis si el dato es de un sitio de San Luis; global si la fuente es FAO, EcoCrop o de otro país."""
    if re.search(r"San Luis|Villa Mercedes", sitio):
        return "San Luis"
    hosts = [urlparse(u.strip()).hostname or "" for u in url.split("|") if u.strip()]
    if hosts and all(h.endswith(".ar") for h in hosts):
        return "Argentina"
    if hosts or any(p in fuente for p in FAO):
        return "global"
    return "Argentina" if any(p in fuente for p in ARGENTINA) else "global"


def _leer(nombre: str) -> list[dict]:
    with (CARPETA / nombre).open(encoding="utf-8") as f:
        lector = csv.reader(f)
        cab = next(lector)
        return [dict(zip(cab, r)) for r in lector if len(r) == len(cab)]  # una fila rota de triticale no trae valores


def _fila(pestana, capa, cultivo="", valor="", fuente="", url="", sitio="", **otros) -> dict | None:
    valor = (valor or "").strip()
    if not valor or re.match(r"(?i)sin dato|no asignar", valor):  # los huecos que el dossier anotó no son datos
        return None
    f = {c: "" for c in COLUMNAS}
    f.update({k: (v or "").strip() for k, v in otros.items()})
    url = (url or "").strip()
    f.update(capa=capa, cultivo=cultivo.strip(), cultivo_banco=cultivo_banco(cultivo.strip()), valor=valor,
             fuente=(fuente or url).strip(), fuente_url=url, sitio=(sitio or "").strip(), pestana=pestana,
             verificacion=LEIDAS.get(pestana, VERIFICACION))
    f["nivel"] = nivel(f["sitio"], f["fuente"], url)
    return f


def _larga(pestana, capa="especie"):
    """Pestañas que ya vienen una fila por dato (lotes 06, 09 y 10)."""
    for r in _leer(pestana):
        yield _fila(pestana, capa, r["cultivo"], r["valor"], r["fuente"], r["url_fuente"], r["alcance_geografico"],
                    especie=r["especie"], variable=r["parametro"], unidad=r["unidad"], etapa=r["etapa_o_contexto"],
                    metodo=r["tipo_evidencia"], nivel_original=r["nivel_evidencia"], advertencia=r["limitaciones"],
                    campana=r.get("fecha_fuente", ""))


def _filas():
    for p in ("A29_Lote06_datos.csv", "A45_L09_datos.csv", "A47_L09_nutricion.csv", "A52_L10_agro.csv",
              "A54_L10_nutricion.csv"):
        yield from _larga(p)
    p = "A07_Emergencia_Raiz.csv"
    for r in _leer(p):
        yield _fila(p, "especie", r["cultivo"], r["valor"], r["fuente"], r["url_fuente"], r["contexto"],
                    especie=r["nombre_cientifico"], variable=f"{r['proceso']}: {r['parametro']}", unidad=r["unidad"],
                    metodo=r["metodo"], nivel_original=r["nivel_evidencia"], advertencia=r["advertencia"])
    p = "A08_Heladas_Etapas.csv"
    for r in _leer(p):
        yield _fila(p, "especie", r["cultivo"], r["temperatura_critica_c"], r["fuente"], r["url_fuente"],
                    r["region_contexto"], variable="temperatura crítica de helada", unidad=r["unidad"],
                    etapa=r["etapa"], metodo=r["metodo_contexto"], nivel_original=r["nivel_evidencia"],
                    advertencia=r["advertencia"])
    p = "A09_Calor_Reproductivo.csv"
    for r in _leer(p):
        yield _fila(p, "especie", r["cultivo"], r["umbral_c"], r["fuente"], r["url_fuente"], r["alcance"],
                    variable=r["indicador"], unidad=r["unidad"], etapa=r["etapa_critica"], metodo=r["calculo"],
                    nivel_original=r["nivel_evidencia"], advertencia=r["advertencia"])
    p = "A02_Temperatura.csv"  # solo temperatura de suelo para sembrar: EcoCrop y Tb ya vienen en A34 y A07
    for r in _leer(p):
        for col, var in (("temperatura_suelo_siembra_min_c", "temperatura de suelo para sembrar: mínima"),
                         ("temperatura_suelo_siembra_opt_min_c", "temperatura de suelo para sembrar: óptima mínima"),
                         ("temperatura_suelo_siembra_opt_max_c", "temperatura de suelo para sembrar: óptima máxima")):
            yield _fila(p, "especie", r["cultivo"], r[col], r["fuente_y_metodo_temperatura"], r["fuentes_url"],
                        especie=r["nombre_cientifico"], variable=var, unidad="°C", etapa="siembra",
                        metodo=r["tipo_umbral_suelo"], advertencia=r["advertencia_uso"])
    p = "A03_Suelo_cultivos.csv"
    for r in _leer(p):
        for col in ("textura_preferida", "otras_texturas_admisibles_en_fuente", "clase_profundidad_preferida",
                    "clase_profundidad_absoluta_o_admisible", "drenaje_preferido_o_requerido"):
            yield _fila(p, "especie", r["cultivo"], r[col], r["fuentes_codigos"], r["fuentes_url"],
                        especie=r["nombre_cientifico"], variable=col.replace("_", " "),
                        nivel_original=r["estado_evidencia"], advertencia=r["advertencia_suelo"])
    p = "A14_Aptitud_suelo_cultivo_3.csv"
    for r in _leer(p):
        yield _fila(p, "especie", r["cultivo"], r["valor"], r["fuente"], r["url"], r["region_y_alcance"],
                    variable=r["indicador"], unidad=r["unidad"], etapa=r["fase_o_contexto"],
                    nivel_original=r["evidencia"], advertencia=r["limitacion"])
    p = "A19_Salinidad_ECe.csv"
    for r in _leer(p):
        for col, var, uni in (("ECe umbral (dS/m) o rango", "salinidad: ECe umbral", "dS/m"),
                              ("Pendiente (% por dS/m)", "salinidad: pérdida por encima del umbral", "% por dS/m"),
                              ("Rating FAO", "salinidad: tolerancia relativa FAO", "")):
            yield _fila(p, "especie", r["Cultivo o material"], r[col], "FAO / Maas & Grattan, Annex 1, Table A1.1",
                        "https://www.fao.org/4/y4263e/y4263e0e.htm", especie=r["Taxón"], variable=var, unidad=uni,
                        etapa=r["Variable de respuesta"], metodo=r["Contexto y método"],
                        advertencia=r["Limitación para Rotaterra"])
    p = "A20_pH_optimo.csv"
    for r in _leer(p):
        for col, var in (("pH mínimo óptimo", "pH óptimo: mínimo"), ("pH máximo óptimo", "pH óptimo: máximo")):
            yield _fila(p, "especie", r["Cultivo"], r[col], r["Fuente"], r["URL"], variable=var,
                        metodo=r["Variable y método"], nivel_original=r["Estado de evidencia"],
                        advertencia=r["Interpretación"])
    p = "A21_Sodicidad_ESP.csv"
    for r in _leer(p):
        yield _fila(p, "especie", r["Cultivo"], r["Rango ESP asociado a rendimiento ~50%"], r["Fuente"], r["URL"],
                    variable="sodio: PSI/ESP con rinde cerca del 50 %", unidad="%",
                    nivel_original=r["Estado de evidencia"], advertencia=r["Limitación"])
    p = "A22_Kc_FAO56.csv"
    for r in _leer(p):
        for col, var, uni in (("Kc inicial", "Kc inicial", ""), ("Kc medio", "Kc medio", ""),
                              ("Kc final", "Kc final", ""), ("Altura media máxima (m)", "altura máxima", "m")):
            yield _fila(p, "especie", r["Cultivo / sistema"], r[col], r["Fuente"], r["URL"], variable=var,
                        unidad=uni, metodo=r["Grupo y fila fuente"], advertencia=f"{r['Nota de transcripción']} {r['Advertencia']}")
    p = "A23_Raiz_RAW_FAO56.csv"
    for r in _leer(p):
        for col, var, uni in (("Zr efectiva (m)", "profundidad de raíces efectiva (Zr)", "m"),
                              ("p antes de estrés", "fracción de agua que se puede gastar sin estrés (p)", "")):
            yield _fila(p, "especie", r["Cultivo"], r[col], r["Fuente"], r["URL"], especie=r["Taxón / grupo"],
                        variable=var, unidad=uni, metodo=r["Condición de p"], advertencia=r["Limitación"])
    p = "A25_Stress_hidrico_ORA.csv"
    for r in _leer(p):
        for col in ("Ventana fenológica crítica", "Otro período crítico"):
            yield _fila(p, "especie", r["Cultivo"], r[col], "Oficina de Riesgo Agropecuario (ORA), mapas de áreas aptas",
                        r["Fuente"], variable=f"{r['Tipo de estrés']}: {col.lower()}", metodo=r["Interpretación"],
                        advertencia=r["Limitación"])
    p = "A34_EcoCrop_especies.csv"
    for r in _leer(p):
        for col in ("TOPMN_temp_opt_min_C", "TOPMX_temp_opt_max_C", "TMIN_temp_abs_min_C", "TMAX_temp_abs_max_C",
                    "ROPMN_lluvia_opt_min_mm_anual", "ROPMX_lluvia_opt_max_mm_anual", "RMIN_lluvia_abs_min_mm_anual",
                    "RMAX_lluvia_abs_max_mm_anual", "GMIN_ciclo_min_dias", "GMAX_ciclo_max_dias",
                    "KTMPR_temp_mortal_reposo_C", "KTMP_temp_mortal_crecimiento_temprano_C", "PHOTO_fotoperiodo",
                    "FAO_pH_optimo_ficha_actual", "FAO_pH_absoluto_ficha_actual", "FAO_sal_optimo_categoria",
                    "FAO_profundidad_optima", "FAO_drenaje_optimo", "TEXT_textura_optima"):
            codigo, _, nombre = col.partition("_")
            unidad = "°C" if col.endswith("_C") else "mm/año" if col.endswith("_anual") else "días" if col.endswith("_dias") else ""
            yield _fila(p, "especie", r["Nombre_comun_ES"], r[col], "FAO EcoCrop (OpenCLIM v1.0 y ficha FAO)",
                        r["Fuente_ficha_FAO"] or ECOCROP_URL, especie=r["Nombre_cientifico"],
                        variable=f"EcoCrop {codigo}: {nombre.replace('_', ' ')}", unidad=unidad,
                        nivel_original=r["Alertas_calidad"], advertencia=r["Advertencia_uso"])
    p = "A39_Nutricion_Lote08.csv"
    for r in _leer(p):
        yield _fila(p, "especie", r["Cultivo_o_grupo"], r["Valor"], r["Fuente"], r["URL"], r["Region_ambiente"],
                    variable=r["Nutriente_o_indicador"], unidad=r["Unidad"], metodo=r["Profundidad_etapa_metodo"],
                    nivel_original=r["Nivel_evidencia"], advertencia=r["Interpretacion"], campana=r["Anio_fuente"])
    p = "A40_Lupino_Lote08.csv"
    for r in _leer(p):
        yield _fila(p, "ensayo", "Lupino (especie no precisada)", r["Valor"], r["Fuente"], r["URL"],
                    r["Lugar_y_fecha"], cultivar=r["Ensayo_material"], variable=r["Variable"], unidad=r["Unidad"],
                    metodo=r["Metodo_contexto"], advertencia=r["Limitacion_para_Rotaterra"])
    for p in ("A46_L09_varietales.csv", "A53_L10_varietales.csv"):
        for r in _leer(p):
            yield _fila(p, "ensayo", r["cultivo"], r["resultado"], r["fuente"], r["url_fuente"], r["sitio"],
                        especie=r["especie"], cultivar=r["cultivar_o_material"], variable=r["destino_o_ensayo"],
                        unidad=r["unidad"], etapa=r["fenologia_observada"], campana=r["campaña"],
                        metodo=f"siembra {r['fecha_siembra']}; {r['metodo_o_diseno']}".strip("; "),
                        nivel_original=r["nivel_evidencia"], advertencia=r["limitaciones"])
    p = "A30_Lote06_SanLuis.csv"
    for r in _leer(p):
        yield _fila(p, "ensayo", r["cultivo"], r["resultado"], r["fuente"], r["url"], r["ambientes"],
                    especie=r["cultivo_especie"], variable=r["variable"], unidad=r["unidad"], campana=r["campañas"],
                    metodo=r["tipo_de_estudio"], advertencia=r["limitaciones"])
    p = "A90_Tesis_UNSL.csv"  # tesis y trabajos finales de la UNSL (04/11/2026), PDF leído
    for r in _leer(p):
        yield _fila(p, r["capa"], r["cultivo"], r["valor"], r["fuente"], r["url"], r["sitio"], variable=r["variable"],
                    unidad=r["unidad"], etapa=r["etapa"], campana=r["campana"], metodo=r["metodo"],
                    advertencia=r["advertencia"])
    p = "A91_pH_argentino.csv"  # pH por especie con fuente argentina (04/11/2026); referencia, nunca descarte
    for r in _leer(p):
        f = _fila(p, r["capa"], r["cultivo"], r["valor"], r["fuente"], r["url"], r["sitio"], variable=r["variable"],
                  unidad=r["unidad"], etapa=r["etapa"], campana=r["campana"], metodo=r["metodo"],
                  advertencia=r["advertencia"])
        if f:
            f["advertencia"] = "; ".join(x for x in (r["advertencia"], f"verificación: {r['verif']}") if x)
            f["nivel"] = "Argentina"  # todas son de entes argentinos (la de soja es texto del INTA en un sitio no oficial)
        yield f
    p = "A92_Mejoramiento_soja.csv"  # ganancia genética de soja en Argentina (paper que subió Hernán, 08/11/2026)
    for r in _leer(p):
        f = _fila(p, r["capa"], r["cultivo"], r["valor"], r["fuente"], r["url"], r["sitio"], variable=r["variable"],
                  unidad=r["unidad"], campana=r["campana"], metodo=r["metodo"], advertencia=r["advertencia"])
        if f:
            f["nivel"] = "Argentina"  # datos argentinos dentro de una revisión mundial (doi.org no es .ar)
        yield f
    p = "A48_L09_regional.csv"
    for r in _leer(p):
        if r["cultivo"] == "Centeno":  # repite el centeno de San Luis que ya trae L09_datos con su fuente
            continue
        yield _fila(p, "ensayo", r["cultivo"], r["dato"], "", r["url_fuente"], r["sitio_region"],
                    especie=r["especie"], variable=r["variable_contextual"], campana=r["campaña_o_contexto"],
                    advertencia=r["limitacion"])
    p = "A10_Clima_Centro.csv"
    for r in _leer(p):
        for col, var, uni in (("radiacion_fotosinteticamente_activa_incidente_media_MJ_m2_dia", "radiación PAR media", "MJ/m²/día"),
                              ("temperatura_media_aire_C", "temperatura media del aire", "°C"),
                              ("precipitacion_mensual_mm", "lluvia del mes", "mm"),
                              ("deficit_presion_vapor_medio_kPa", "déficit de presión de vapor medio", "kPa"),
                              ("evapotranspiracion_referencia_mensual_mm", "evapotranspiración de referencia del mes", "mm"),
                              ("riego_complementario_mensual_mm", "riego complementario del mes", "mm")):
            yield _fila(p, "zona", "", r[col], r["fuente"], r["url_fuente"], r["region"], variable=var, unidad=uni,
                        etapa=r["mes"], campana=r["campania"], metodo=r["periodo_y_metodo"], advertencia=r["advertencia"])
    p = "A11_Suelos_SanLuis.csv"  # solo lo medido: el agua útil "inicial" por escenario es una cuenta del dossier
    vistos = set()
    for r in _leer(p):
        if r["serie_suelo"] in vistos:
            continue
        vistos.add(r["serie_suelo"])
        for col, var, uni in (("arena_media_en_perfil_pct", "arena media en el perfil", "%"),
                              ("agua_util_maxima_mm_hasta_210cm", "agua útil máxima hasta 210 cm", "mm")):
            yield _fila(p, "zona", "", r[col], r["fuente"], r["url_fuente"], f"Serie {r['serie_suelo']}, {r['ambiente']}",
                        variable=var, unidad=uni, metodo=r["tipo_valor"], advertencia=r["advertencia"])
    p = "A15_Agua_util_regional_3.csv"
    for r in _leer(p):
        yield _fila(p, "zona", "", r["agua_util_mm"], r["fuente"], r["url"], f"{r['perfil_suelo']} ({r['region']})",
                    variable=f"agua útil ({r['profundidad_o_espesor']})", unidad=r["unidad"],
                    metodo=r["metodo_o_detalle"], advertencia=r["limitacion"])
    p = "A04_Diagnostico_suelo.csv"
    for r in _leer(p):
        yield _fila(p, "criterio", "", r["referencia_o_umbral"], r["fuente_codigo"], r["url_fuente"],
                    variable=r["variable"], unidad=r["unidad"], metodo=r["metodo_o_dato"],
                    advertencia=r["alcance_y_limitacion"])
    p = "A31_Lote06_salino.csv"
    for r in _leer(p):
        yield _fila(p, "criterio", "", r["valor"], r["fuente"], r["url"], variable=f"{r['variable']}: {r['criterio']}",
                    unidad=r["unidad"], metodo=r["contexto"], advertencia=r["limitaciones"])


CLAVE = ("pestana", "cultivo", "cultivar", "variable", "etapa", "sitio", "valor")


def cotejo() -> dict:
    """Cotejo fila por fila con los PDFs originales que Hernán subió el 31/10/2026 (cotejo_originales.csv)."""
    archivo = CARPETA / "cotejo_originales.csv"
    if not archivo.exists():
        return {}
    with archivo.open(encoding="utf-8") as f:
        return {tuple(r[c] for c in CLAVE): r for r in csv.DictReader(f)}


def _aplicar_cotejo(f: dict, c: dict) -> None:
    f["verificacion"] = c["verificacion"]
    if c["variable_corregida"]:
        f["variable"] = c["variable_corregida"]
    if c["valor_corregido"]:
        f["advertencia"] = (f["advertencia"] + " " if f["advertencia"] else "") + \
            f"Corregido con el original: el dossier decía {f['valor']}."
        f["valor"] = c["valor_corregido"]
    if c["metodo_corregido"]:
        f["metodo"] = c["metodo_corregido"]


def armar() -> list[dict]:
    filas = [f for f in _filas() if f]
    cot = cotejo()
    for f in filas:
        c = cot.get(tuple(f[k] for k in CLAVE))
        if c:
            _aplicar_cotejo(f, c)
    orden = {n: i for i, n in enumerate(NIVELES)}
    return sorted(filas, key=lambda f: (f["capa"], f["cultivo_banco"] or "~", f["cultivo"], orden[f["nivel"]]))
