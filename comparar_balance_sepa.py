"""Comparación en mm del balance propio contra todo el historial de SEPA (spec 024, calibración).

Se usa desde GitHub (Actions → "Comparar balance hídrico propio con SEPA"). Necesita los secretos de Earthdata.
No imprime ningún secreto.

1. SEPA: lee agua disponible (ad, mm) y % de agua (pj) de cada década desde mayo de 2024, en los píxeles del lote.
   Con ad ÷ pj sale la capacidad de agua útil que usa SEPA en el lote.
2. Lluvia: la de POWER (PRECTOTCORR, 0,5°) y la de IMERG (0,1°; Final y, donde todavía no salió, Late),
   leída por OPeNDAP con el núcleo `earthdata`. Se comparan los totales por mes.
3. Corre el balance día por día con muchas combinaciones (lluvia, Kc de verano y de invierno, capacidad, agotamiento, escurrimiento,
   arranque) y ordena por la diferencia media en mm contra SEPA. Para no sobreajustar, también muestra el error
   en el segundo año (oct-2025 a sep-2026) de la combinación elegida con el primero.
Las lecturas de SEPA e IMERG se guardan en `datos_comparacion/` (cache de Actions) para no repetirlas.
"""

import calendar
import itertools
import json
import math
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import httpx

from rotaterra.fuentes import balance_hidrico as b
from rotaterra.fuentes import earthdata as ed

LAT, LON = -33.7025, -65.2975  # centro del lote de San Luis
LOTE = {"type": "Polygon", "coordinates": [[[-65.300, -33.700], [-65.295, -33.700], [-65.295, -33.705],
                                             [-65.300, -33.705], [-65.300, -33.700]]]}
DESDE, HASTA = date(2024, 5, 1), date(2026, 9, 30)
ARRANQUE = DESDE - timedelta(days=730)  # dos años antes: para probar cuánto arranque necesita el balance
CORTE = date(2025, 9, 30)  # primer año para elegir, segundo año para comprobar
CACHE = Path("datos_comparacion")
SEPA_URL = "https://sepa.inta.gob.ar/productos/geosepa/agua_en_suelo/{p}/tif/{p}_{a}{m:02d}_{d}.tif"
ENTORNO_GDAL = dict(GDAL_HTTP_TIMEOUT=60, GDAL_HTTP_MAX_RETRY=3, GDAL_HTTP_RETRY_DELAY=3,
                    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_USE_HEAD="NO",
                    GDAL_HTTP_USERAGENT="Rotaterra/0.1 (+https://github.com/hernanfirmapaz-ops/N4-4-1.2)")

# combinaciones a probar
# ronda 1 (5/10/2026): el arranque no cambia nada, y POWER marca lluvias de invierno que IMERG y SEPA no ven
# ronda 2: Kc distinto en invierno (cultivo/pasto parado: consume poco) y lluvia combinada de POWER e IMERG.
#          Bajó a 17-18 mm; el escurrimiento casi no cambia nada.
# ronda 3: ajuste fino, mezclas de lluvia y meses de invierno. 16 mm con la menor de las dos lluvias y Kc 0,5
#          (borde de la grilla); IMERG o el promedio solos, 18,5 mm; POWER sola no baja de 21 mm.
# ronda 4: Kc más bajos, y se simula el balance como lo corre la app (arranque al 50 %, 1 o 2 años antes del mes
#          pedido) para ver si el error se sostiene con el arranque real
#          Resultado: 15,8 mm es el piso; Kc más bajos no mejoran y con un año de arranque alcanza.
# ronda 5: Kc que sigue al verde del lote (NDVI de MODIS de 250 m), como hace SEPA con la cobertura verde:
#          Kc = Kc mínimo + (Kc máximo - Kc mínimo) × cobertura, con cobertura = NDVI llevado a 0-1 entre su
#          percentil 5 y 95 del período. Se compara contra el Kc de dos temporadas de la ronda 4.
LLUVIAS = ["POWER", "IMERG", "MEDIA", "MENOR"]          # MEDIA y MENOR: promedio y la menor de las dos, día por día
KCS = [0.45, 0.5, 0.55, 0.6]                             # Kc de la temporada de crecimiento
KCS_INVIERNO = [None, 0.2, 0.25, 0.3, 0.35]              # None = el mismo Kc todo el año
INVIERNOS = {"may-sep": {5, 6, 7, 8, 9}, "jun-sep": {6, 7, 8, 9}}
KC_NDVI_MIN = [0.1, 0.2, 0.3]                            # Kc con el lote sin verde
KC_NDVI_MAX = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2]        # Kc con el lote en su máximo verde
CAPACIDADES = [160, 180, 200]                            # mm de agua útil en 2 m (se suma la de SEPA)
AGOTAMIENTOS = [0.6, 0.7, 0.8]                           # p de FAO-56 (tabla 22)
CURVAS = [None]                                          # número de curva SCS para el escurrimiento (None = sin)
ARRANQUES = [0.5]                                        # fracción de la capacidad el 2/5/2022 (no influye)


def fines_de_decada(desde: date, hasta: date) -> list[tuple[int, int, int, date]]:
    salida, anio, mes = [], desde.year, desde.month
    while date(anio, mes, 1) <= hasta:
        for d, fin in ((1, 10), (2, 20), (3, calendar.monthrange(anio, mes)[1])):
            if desde <= date(anio, mes, fin) <= hasta:
                salida.append((anio, mes, d, date(anio, mes, fin)))
        anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    return salida


def _cargar(nombre: str) -> dict:
    archivo = CACHE / nombre
    return json.loads(archivo.read_text()) if archivo.exists() else {}


def _guardar(nombre: str, datos: dict) -> None:
    CACHE.mkdir(exist_ok=True)
    (CACHE / nombre).write_text(json.dumps(datos, sort_keys=True))


def autorizar():
    """Token de Earthdata, con tres intentos (el 5/10/2026 el servidor de Earthdata no respondió por un rato)."""
    for intento in range(3):
        try:
            return ed.cliente_autorizado()
        except httpx.HTTPError:
            if intento == 2:
                raise
            time.sleep(20)


# ---------- 1. SEPA ----------

def leer_sepa(url: str) -> float | None:
    """Media de los píxeles del lote (misma lectura por rangos que el conector de la spec 023)."""
    import numpy as np
    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.windows import Window, from_bounds
    from shapely.geometry import shape

    geometria = shape(LOTE)
    with rasterio.Env(**ENTORNO_GDAL), rasterio.open("/vsicurl/" + url) as ds:
        v = from_bounds(*geometria.bounds, ds.transform)
        col, fila = math.floor(v.col_off), math.floor(v.row_off)
        ventana = Window(col, fila, math.ceil(v.col_off + v.width) - col + 1, math.ceil(v.row_off + v.height) - fila + 1)
        datos = ds.read(1, window=ventana, masked=True, boundless=True)
        dentro = ~geometry_mask([LOTE], out_shape=datos.shape, transform=ds.window_transform(ventana), all_touched=True)
        if not dentro.any():
            dentro = np.zeros(datos.shape, bool)
            dentro[datos.shape[0] // 2, datos.shape[1] // 2] = True
        validos = [float(x) for x in datos[dentro].compressed() if math.isfinite(float(x)) and float(x) >= 0]
        return sum(validos) / len(validos) if validos else None


def historial_sepa() -> dict[str, dict[str, float]]:
    """{'ad': {AAAA-MM-DD: mm}, 'pj': {AAAA-MM-DD: %}} de todas las décadas, con lo ya guardado."""
    guardado = _cargar("sepa.json")
    pedidos = [(p, a, m, d, fin) for a, m, d, fin in fines_de_decada(DESDE, HASTA) for p in ("ad", "pj")
               if fin.isoformat() not in guardado.get(p, {})]
    print(f"SEPA: {sum(len(v) for v in guardado.values())} lecturas guardadas, faltan {len(pedidos)}")
    try:
        httpx.get("https://sepa.inta.gob.ar/productos/", timeout=20)
    except httpx.HTTPError as error:
        print(f"::warning::SEPA no responde ({type(error).__name__}): se usa solo lo guardado")
        pedidos = []

    def uno(pedido):
        p, a, m, d, fin = pedido
        try:
            return p, fin, leer_sepa(SEPA_URL.format(p=p, a=a, m=m, d=d))
        except Exception as error:
            print(f"   SEPA {p} {fin}: {type(error).__name__}")
            return p, fin, None
    inicio = time.time()
    with ThreadPoolExecutor(4) as hilos:
        for p, fin, valor in hilos.map(uno, pedidos):
            if valor is not None:
                guardado.setdefault(p, {})[fin.isoformat()] = round(valor, 2)
    if pedidos:
        print(f"SEPA: {len(pedidos)} pedidos en {time.time() - inicio:.0f} s")
    _guardar("sepa.json", guardado)
    return guardado


# ---------- 2. lluvia ----------

def clima_power() -> tuple[dict, float]:
    respuesta = httpx.get(b.URL_POWER, timeout=300, params={
        "parameters": ",".join(b.PARAMETROS), "community": "AG", "latitude": LAT, "longitude": LON,
        "start": ARRANQUE.strftime("%Y%m%d"), "end": HASTA.strftime("%Y%m%d"), "format": "JSON"})
    respuesta.raise_for_status()
    datos = respuesta.json()
    return datos["properties"]["parameter"], datos["geometry"]["coordinates"][2]


def lluvia_imerg() -> dict[str, float]:
    """{AAAAMMDD: mm} de IMERG en la celda de 0,1° del lote (Final y, si no salió, Late)."""
    guardado = _cargar("imerg.json")
    i_lon, i_lat = min(int(math.floor((LON + 180) / 0.1)), 3598), min(int(math.floor((LAT + 90) / 0.1)), 1798)
    dias = [ARRANQUE + timedelta(days=i) for i in range((HASTA - ARRANQUE).days + 1)]
    faltan = [d for d in dias if d.strftime("%Y%m%d") not in guardado]
    print(f"IMERG: {len(guardado)} días guardados, faltan {len(faltan)}")
    if not faltan:
        return guardado
    cliente = autorizar()
    elegido: dict[date, str] = {}
    for producto in ("GPM_3IMERGDF", "GPM_3IMERGDL"):
        coleccion = ed.coleccion_vigente(cliente, producto)
        if coleccion:
            por_dia = ed.archivos_por_dia(cliente, coleccion, min(faltan), max(faltan))
            print(f"   {producto}: {len(por_dia)} días disponibles")
            for dia, urls in por_dia.items():
                elegido.setdefault(dia, urls[0])

    def uno(dia):
        if dia not in elegido:
            return dia, None
        for intento in range(3):
            try:
                valor = ed.leer_csv(cliente, elegido[dia], f"/precipitation[0][{i_lon}][{i_lat}:1:{i_lat + 1}]")
                valor = valor["precipitation"][0][0]
                return dia, None if valor is None or valor < 0 else valor
            except Exception as error:
                if intento == 2:
                    print(f"   IMERG {dia}: {type(error).__name__}")
                time.sleep(2 * (intento + 1))
        return dia, None
    inicio = time.time()
    with ThreadPoolExecutor(12) as hilos:
        for dia, valor in hilos.map(uno, faltan):
            if valor is not None:
                guardado[dia.strftime("%Y%m%d")] = round(valor, 2)
    print(f"IMERG: {len(faltan)} días pedidos en {time.time() - inicio:.0f} s")
    _guardar("imerg.json", guardado)
    return guardado


# ---------- 2b. NDVI de MODIS (MOD13Q1, 250 m, cada 16 días) ----------

_R_MODIS, _MOSAICO, _X0_MODIS, _Y0_MODIS = 6371007.181, 1111950.5197665, -20015109.354, 10007554.677
CAPA_NDVI = "/MODIS_Grid_16DAY_250m_500m_VI/Data_Fields/_250m_16_days_NDVI"
CAPA_CONFIABLE = "/MODIS_Grid_16DAY_250m_500m_VI/Data_Fields/_250m_16_days_pixel_reliability"


def ndvi_modis() -> dict[str, float]:
    """{AAAA-MM-DD (mitad del compuesto): NDVI mediano de los 3 × 3 píxeles del lote} con lo ya guardado."""
    guardado = _cargar("ndvi.json")
    x = _R_MODIS * math.radians(LON) * math.cos(math.radians(LAT))
    y = _R_MODIS * math.radians(LAT)
    h, v = math.floor((x - _X0_MODIS) / _MOSAICO), math.floor((_Y0_MODIS - y) / _MOSAICO)
    pixel = _MOSAICO / 4800
    columna = math.floor((x - _X0_MODIS - h * _MOSAICO) / pixel)
    fila = math.floor((_Y0_MODIS - y - v * _MOSAICO) / pixel)
    try:
        cliente = autorizar()
        coleccion = ed.coleccion_vigente(cliente, "MOD13Q1")
    except (httpx.HTTPError, ed.ErrorNASA) as error:
        print(f"::warning::MODIS no respondió ({type(error).__name__}): se usa solo lo guardado")
        return guardado
    mosaico = f".h{h:02d}v{v:02d}."
    urls = [(nombre, url) for nombre, url in ed.archivos(cliente, coleccion, ARRANQUE, HASTA,
                                                         caja=(LON - 0.01, LAT - 0.01, LON + 0.01, LAT + 0.01))
            if mosaico in nombre]

    def mitad(nombre: str) -> str:
        a, d = int(nombre.split(".A")[1][:4]), int(nombre.split(".A")[1][4:7])
        return (date(a, 1, 1) + timedelta(days=d - 1 + 8)).isoformat()
    faltan = [(nombre, url) for nombre, url in urls if mitad(nombre) not in guardado]
    print(f"MODIS: {len(urls)} compuestos, faltan {len(faltan)} (mosaico h{h:02d}v{v:02d}, píxel {fila}, {columna})")

    def uno(par):
        nombre, url = par
        ventana = f"[{fila - 1}:1:{fila + 1}][{columna - 1}:1:{columna + 1}]"
        try:
            datos = ed.leer_csv(cliente, url, f"{CAPA_NDVI}{ventana};{CAPA_CONFIABLE}{ventana}")
            ndvi = [v for f in datos[CAPA_NDVI.lstrip("/")] for v in f]
            conf = [v for f in datos[CAPA_CONFIABLE.lstrip("/")] for v in f]
            validos = sorted(n * 0.0001 for n, c in zip(ndvi, conf) if n is not None and n > -3000 and c in (0, 1))
            return mitad(nombre), validos[len(validos) // 2] if validos else None
        except Exception as error:
            print(f"   MODIS {nombre[:24]}: {type(error).__name__}")
            return mitad(nombre), None
    with ThreadPoolExecutor(6) as hilos:
        for fecha, valor in hilos.map(uno, faltan):
            if valor is not None:
                guardado[fecha] = round(valor, 4)
    _guardar("ndvi.json", guardado)
    return guardado


def cobertura_diaria(ndvi: dict[str, float], dias: list[date]) -> list[float]:
    """NDVI interpolado día por día y llevado a 0-1 entre su percentil 5 y 95."""
    puntos = sorted((date.fromisoformat(f), v) for f, v in ndvi.items())
    valores = sorted(v for _, v in puntos)
    bajo, alto = valores[int(0.05 * len(valores))], valores[int(0.95 * len(valores)) - 1]
    salida, j = [], 0
    for dia in dias:
        while j + 1 < len(puntos) and puntos[j + 1][0] <= dia:
            j += 1
        if dia <= puntos[0][0]:
            valor = puntos[0][1]
        elif j + 1 >= len(puntos):
            valor = puntos[-1][1]
        else:
            (d0, v0), (d1, v1) = puntos[j], puntos[j + 1]
            valor = v0 + (v1 - v0) * (dia - d0).days / (d1 - d0).days
        salida.append(min(1.0, max(0.0, (valor - bajo) / (alto - bajo))))
    return salida


# ---------- 3. balance rápido (mismas ecuaciones que balance_hidrico.py) ----------

def escurrimiento(lluvia: float, curva: int | None) -> float:
    """Lluvia que se escurre (SCS, condición media); None = toda la lluvia entra al suelo."""
    if curva is None:
        return 0.0
    s = 25400 / curva - 254
    return (lluvia - 0.2 * s) ** 2 / (lluvia + 0.8 * s) if lluvia > 0.2 * s else 0.0


def correr(lluvias: list[float], et0s: list[float], kcs: list[float], capacidad: float, p: float,
           curva: int | None, arranque: float) -> list[float]:
    agua, salida = arranque * capacidad, []
    umbral = (1 - p) * capacidad
    for lluvia, et0, kc in zip(lluvias, et0s, kcs):
        entra = lluvia - escurrimiento(lluvia, curva)
        ks = 1.0 if agua >= umbral else agua / umbral
        agua = min(capacidad, agua + entra - min(ks * kc * et0, agua + entra))
        salida.append(agua)
    return salida


def medir(simulado: dict[date, float], sepa: dict[date, float], desde: date, hasta: date):
    comunes = [f for f in sepa if desde <= f <= hasta and f in simulado]
    if len(comunes) < 5:
        return None
    dif = [simulado[f] - sepa[f] for f in comunes]
    x, y = [simulado[f] for f in comunes], [sepa[f] for f in comunes]
    mx, my = sum(x) / len(x), sum(y) / len(y)
    sx, sy = math.sqrt(sum((v - mx) ** 2 for v in x)), math.sqrt(sum((v - my) ** 2 for v in y))
    r = sum((a - mx) * (c - my) for a, c in zip(x, y)) / (sx * sy) if sx and sy else 0.0
    return {"mae": sum(abs(d) for d in dif) / len(dif), "sesgo": sum(dif) / len(dif), "r": r, "n": len(comunes)}


if __name__ == "__main__":
    sepa = historial_sepa()
    agua_sepa = {date.fromisoformat(f): v for f, v in sepa.get("ad", {}).items()}
    pj_sepa = {date.fromisoformat(f): v for f, v in sepa.get("pj", {}).items()}
    print(f"\nSEPA: agua disponible en {len(agua_sepa)} décadas, % de agua en {len(pj_sepa)}")
    capacidades_sepa = sorted(agua_sepa[f] / pj_sepa[f] * 100 for f in agua_sepa if pj_sepa.get(f, 0) > 5)
    if capacidades_sepa:
        mediana = capacidades_sepa[len(capacidades_sepa) // 2]
        print(f"Capacidad que usa SEPA en el lote (ad ÷ pj): mediana {mediana:.0f} mm "
              f"(de {capacidades_sepa[0]:.0f} a {capacidades_sepa[-1]:.0f})")
        CAPACIDADES = sorted(set(CAPACIDADES) | {round(mediana)})
    if len(agua_sepa) < 10:
        print("FALLA: SEPA entregó menos de 10 décadas; sin historial no hay comparación en mm")
        sys.exit(1)

    series, altura = clima_power()
    imerg = lluvia_imerg()
    dias = [ARRANQUE + timedelta(days=i) for i in range((HASTA - ARRANQUE).days + 1)]
    et0s, lluvia = [], {f: [] for f in LLUVIAS}
    huecos_imerg = 0
    for dia in dias:
        clave = dia.strftime("%Y%m%d")
        insumos = {p: series.get(p, {}).get(clave) for p in b.PARAMETROS}
        et0, faltan, _ = b.et0_del_dia(insumos, LAT, dia, altura)
        if faltan:
            print(f"FALLA: POWER sin {faltan} el {dia}")
            sys.exit(1)
        et0s.append(et0)
        lp = insumos["PRECTOTCORR"]
        lp = 0.0 if b._falta(lp) or lp < 0 else lp
        lluvia["POWER"].append(lp)
        li = imerg.get(clave)
        if li is None:
            huecos_imerg += 1
            li = lp  # día sin IMERG: se usa POWER (se informa cuántos)
        lluvia["IMERG"].append(li)
        lluvia["MEDIA"].append((lp + li) / 2)
        lluvia["MENOR"].append(min(lp, li))
        for nombre, peso in (("IMERG25", 0.25), ("IMERG75", 0.75)):
            if nombre in lluvia:
                lluvia[nombre].append(peso * li + (1 - peso) * lp)
    print(f"IMERG: {huecos_imerg} días sin dato (se completaron con POWER)")

    print("\nLluvia por mes (mm)        POWER    IMERG    SEPA ad fin de mes")
    meses: dict[tuple[int, int], list[float]] = {}
    for dia, lp, li in zip(dias, lluvia["POWER"], lluvia["IMERG"]):
        if dia >= DESDE:
            meses.setdefault((dia.year, dia.month), [0.0, 0.0])
            meses[(dia.year, dia.month)][0] += lp
            meses[(dia.year, dia.month)][1] += li
    for (a, m), (lp, li) in meses.items():
        fin = agua_sepa.get(date(a, m, calendar.monthrange(a, m)[1]))
        print(f"{a}-{m:02d}                  {lp:8.1f} {li:8.1f}    {'—' if fin is None else f'{fin:.1f}'}")
    print(f"Total {DESDE} a {HASTA}: POWER {sum(v[0] for v in meses.values()):.0f} mm · "
          f"IMERG {sum(v[1] for v in meses.values()):.0f} mm")

    indice = {d: i for i, d in enumerate(dias)}
    resultados = []
    inicio = time.time()
    temporadas = []
    for kc, kci, (nombre_inv, meses_inv) in itertools.product(KCS, KCS_INVIERNO, INVIERNOS.items()):
        if kci is None and nombre_inv != "may-sep":
            continue
        if kci is not None and kci >= kc:
            continue
        temporadas.append((kc, kci, nombre_inv if kci is not None else "-",
                           [kci if kci is not None and d.month in meses_inv else kc for d in dias]))
    ndvi = ndvi_modis()
    if len(ndvi) >= 20:
        print(f"MODIS: NDVI en {len(ndvi)} compuestos, de {min(ndvi.values()):.2f} a {max(ndvi.values()):.2f}")
        cobertura = cobertura_diaria(ndvi, dias)
        for kmin, kmax in itertools.product(KC_NDVI_MIN, KC_NDVI_MAX):
            temporadas.append((kmax, kmin, "NDVI", [kmin + (kmax - kmin) * c for c in cobertura]))
    else:
        print(f"::warning::MODIS dio solo {len(ndvi)} compuestos: no se prueba el Kc con NDVI")
    for (kc, kci, inv, kcs), fuente, cap, p, curva, arr in itertools.product(temporadas, LLUVIAS, CAPACIDADES,
                                                                            AGOTAMIENTOS, CURVAS, ARRANQUES):
        agua = correr(lluvia[fuente], et0s, kcs, cap, p, curva, arr)
        simulado = {f: agua[indice[f]] for f in agua_sepa}
        total, primero, segundo = (medir(simulado, agua_sepa, DESDE, HASTA), medir(simulado, agua_sepa, DESDE, CORTE),
                                   medir(simulado, agua_sepa, CORTE + timedelta(days=1), HASTA))
        resultados.append(dict(lluvia=fuente, kc=kc, kci=kci, inv=inv, cap=cap, p=p, curva=curva, arranque=arr,
                               total=total, primero=primero, segundo=segundo, simulado=simulado))
    print(f"\n{len(resultados)} combinaciones en {time.time() - inicio:.0f} s")

    def fila(r, titulo=""):
        t, a1, a2 = r["total"], r["primero"], r["segundo"]
        return (f"{titulo}{r['lluvia']:<6}Kc {r['kc']:<4} inv {str(r['kci']):<4} {r['inv']:<8}cap {r['cap']:<4} "
                f"p {r['p']:<4} CN {str(r['curva']):<5}| total: dif {t['mae']:5.1f} mm, sesgo {t['sesgo']:+6.1f}, "
                f"r {t['r']:.2f} | año 1: {a1['mae']:5.1f} | año 2: {a2['mae']:5.1f}" if t and a1 and a2 else "sin datos")

    # el balance actual (POWER, Kc 1,0, 260 mm, p 0,5) se corre aparte porque 260 ya no está en la grilla
    agua = correr(lluvia["POWER"], et0s, [1.0] * len(dias), 260, 0.5, None, 0.5)
    simulado = {f: agua[indice[f]] for f in agua_sepa}
    actual = dict(lluvia="POWER", kc=1.0, kci=None, inv="-", cap=260, p=0.5, curva=None, arranque=0.5,
                  total=medir(simulado, agua_sepa, DESDE, HASTA), primero=medir(simulado, agua_sepa, DESDE, CORTE),
                  segundo=medir(simulado, agua_sepa, CORTE + timedelta(days=1), HASTA), simulado=simulado)
    print("\nBalance actual (spec 024):")
    print(fila(actual))
    validos = [r for r in resultados if r["total"] and r["primero"] and r["segundo"]]
    print("\nLas 15 combinaciones con menor diferencia media en mm contra SEPA (todo el período):")
    for r in sorted(validos, key=lambda r: r["total"]["mae"])[:15]:
        print(fila(r))
    print("\nLas 10 más parejas (menor diferencia en el peor de los dos años):")
    for r in sorted(validos, key=lambda r: max(r["primero"]["mae"], r["segundo"]["mae"]))[:10]:
        print(fila(r))
    elegida = min(validos, key=lambda r: r["primero"]["mae"])
    print("\nElegida solo con el año 1 y comprobada en el año 2 (para ver si se sobreajusta):")
    print(fila(elegida))
    for fuente in LLUVIAS:
        mejor = min((r for r in validos if r["lluvia"] == fuente), key=lambda r: r["total"]["mae"])
        print(f"\nMejor con lluvia de {fuente}:")
        print(fila(mejor))
    for nombre, filtro in (("Kc de dos temporadas", lambda r: r["inv"] != "NDVI"),
                           ("Kc con NDVI (inv = Kc sin verde, Kc = con el máximo verde)", lambda r: r["inv"] == "NDVI")):
        candidatos = [r for r in validos if filtro(r)]
        if candidatos:
            print(f"\nLas 5 mejores con {nombre}:")
            for r in sorted(candidatos, key=lambda r: r["total"]["mae"])[:5]:
                print(fila(r))
    for nombre, filtro in (("sin escurrimiento", lambda r: r["curva"] is None),
                           ("el mismo Kc todo el año", lambda r: r["kci"] is None),
                           ("capacidad 200 mm (cerca de la de SEPA)", lambda r: r["cap"] == 200),
                           ("la capacidad de SEPA (220 mm)", lambda r: r["cap"] == 220),
                           ("p 0,7 (el más usado)", lambda r: r["p"] == 0.7)):
        mejor = min((r for r in validos if filtro(r)), key=lambda r: r["total"]["mae"])
        print(f"\nMejor con {nombre}:")
        print(fila(mejor))

    mejor = min(validos, key=lambda r: r["total"]["mae"])
    pareja = min(validos, key=lambda r: max(r["primero"]["mae"], r["segundo"]["mae"]))
    mejor_power = min((r for r in validos if r["lluvia"] == "POWER"), key=lambda r: r["total"]["mae"])
    print(f"\n{'Década':<11}{'SEPA':>8}{'Actual':>9}{'Mejor':>8}{'Pareja':>8}{'Mejor POWER':>13}")
    for f in sorted(agua_sepa):
        print(f"{f!s:<11}{agua_sepa[f]:8.1f}{actual['simulado'][f]:9.1f}{mejor['simulado'][f]:8.1f}"
              f"{pareja['simulado'][f]:8.1f}{mejor_power['simulado'][f]:13.1f}")
    # Como lo corre la app: cada mes se pide por separado, arrancando al 50 % de la capacidad 1 o 2 años antes
    def como_la_app(r, espera: int):
        kcs_r = next(t[3] for t in temporadas if t[0] == r["kc"] and t[1] == r["kci"] and t[2] == r["inv"])
        simulado = {}
        for f in agua_sepa:
            inicio = indice[f.replace(day=1)] - espera
            if inicio < 0:
                continue
            agua = correr(lluvia[r["lluvia"]][inicio:], et0s[inicio:], kcs_r[inicio:], r["cap"], r["p"], None, 0.5)
            simulado[f] = agua[indice[f] - inicio]
        return medir(simulado, agua_sepa, DESDE, HASTA)
    print("\nCorrido como la app (cada mes por separado, arranque al 50 %), diferencia media en mm contra SEPA:")
    for fuente in LLUVIAS:
        for r in sorted((r for r in validos if r["lluvia"] == fuente), key=lambda r: r["total"]["mae"])[:2]:
            uno, dos = como_la_app(r, 365), como_la_app(r, 730)
            print(fila(r) + f" || app, arranque 1 año: {uno['mae']:5.1f} · 2 años: {dos['mae']:5.1f}")
    con_ndvi = [r for r in validos if r["inv"] == "NDVI"]
    if con_ndvi:
        r = min(con_ndvi, key=lambda r: r["total"]["mae"])
        uno, dos = como_la_app(r, 365), como_la_app(r, 730)
        print("Mejor con NDVI:")
        print(fila(r) + f" || app, arranque 1 año: {uno['mae']:5.1f} · 2 años: {dos['mae']:5.1f}")

    # ¿cuántos días de arranque hacen falta? Se arranca seco (0) y lleno (capacidad) el 1° de cada mes
    # y se cuenta cuántos días tardan las dos corridas en diferir menos de 1 mm.
    kcs_pareja = next(t[3] for t in temporadas if t[0] == pareja["kc"] and t[1] == pareja["kci"]
                      and t[2] == pareja["inv"])
    esperas = []
    for i, dia in enumerate(dias):
        if dia.day != 1 or i + 400 > len(dias):
            continue
        seco = correr(lluvia[pareja["lluvia"]][i:], et0s[i:], kcs_pareja[i:], pareja["cap"], pareja["p"], None, 0.0)
        lleno = correr(lluvia[pareja["lluvia"]][i:], et0s[i:], kcs_pareja[i:], pareja["cap"], pareja["p"], None, 1.0)
        esperas.append((next((j for j, (a, c) in enumerate(zip(seco, lleno)) if abs(a - c) < 1), None), dia))
    sin_converger = [d for j, d in esperas if j is None]
    dias_espera = sorted(j for j, _ in esperas if j is not None)
    if dias_espera:
        print(f"\nArranque con la combinación pareja: seco y lleno se juntan (<1 mm) en {dias_espera[len(dias_espera) // 2]} "
              f"días la mediana, {dias_espera[-1]} el peor caso ({len(esperas)} arranques; "
              f"{len(sin_converger)} no se juntaron en el período)")

    print("\nSEPA (para fijar en el código si el servidor se cae):")
    print(json.dumps({f.isoformat(): v for f, v in sorted(agua_sepa.items())}))
