"""Prueba real contra NOAA (El Niño / La Niña). Se usa desde GitHub
(Actions → "Probar NOAA (El Niño / La Niña)"). No necesita cuenta ni lugar: el índice es global."""

import sys
import time

import httpx

from rotaterra.fuentes import noaa_enso

cliente = noaa_enso._cliente(None)


def mirar(nombre: str, url: str, primeras: int = 5, ultimas: int = 8) -> str | None:
    """Qué devuelve el servidor: código HTTP, tamaño y las primeras y últimas líneas."""
    print(f"\n--- {nombre}: {url}", flush=True)
    inicio = time.time()
    try:
        r = cliente.get(url)
    except httpx.HTTPError as error:
        print(f"Sin respuesta: {type(error).__name__}: {error}")
        return None
    lineas = r.text.splitlines()
    print(f"HTTP {r.status_code} · {len(r.content)} bytes · {len(lineas)} líneas · {time.time() - inicio:.1f} s")
    for linea in lineas[:primeras]:
        print(f"  | {linea[:150]}")
    if len(lineas) > primeras + ultimas:
        print("  | ...")
    for linea in lineas[max(primeras, len(lineas) - ultimas):]:
        print(f"  | {linea[:150]}")
    return r.text if r.status_code == 200 else None


print("1) Lo que devuelve cada servidor de NOAA")
oni_txt = mirar("ONI de CPC", noaa_enso.URL_ONI)
pagina = mirar("Discusión de ENSO de CPC", noaa_enso.URL_DISCUSION, primeras=3, ultimas=3)
psl_txt = mirar("Niño 3.4 de PSL", noaa_enso.URL_PSL)
if psl_txt:
    print(f"Serie de PSL según el pie del archivo: {noaa_enso.describir_psl(psl_txt)}")

if pagina:
    leida = noaa_enso.leer_discusion(pagina)
    print(f"\nDiscusión leída:\n  alerta: {leida['alerta']!r} -> {noaa_enso.traducir_alerta(leida['alerta'])!r}"
          f"\n  publicada: {leida['publicada']}\n  sinopsis: {leida['sinopsis']!r}"
          f"\n  probabilidad: {noaa_enso.probabilidad(leida['sinopsis'])}")
    if not leida["sinopsis"]:
        texto = noaa_enso._texto_plano(pagina)
        i = texto.find("Synopsis")
        print(f"  (no se encontró la sinopsis; texto alrededor: {texto[max(0, i - 300):i + 500]!r})")

print("\n2) Principal: ONI de CPC + discusión", flush=True)
oni = None
try:
    [o] = noaa_enso.obtener_oni("lote-prueba", cliente)
    oni = o.valor
    print(f"{o.fecha} · {o.variable} = {o.valor} {o.unidad} · {o.fuente} · {o.calidad} · "
          f"fase: {noaa_enso.fase(o.valor)}")
    print(f"Nota: {o.nota}")
except noaa_enso.ErrorENSO as error:
    print(f"Error: {error}")

print("\n3) Respaldo: Niño 3.4 de PSL (promedio de los 3 últimos meses)", flush=True)
psl = None
try:
    [r] = noaa_enso.obtener_psl("lote-prueba", cliente)
    psl = r.valor
    print(f"{r.fecha} · {r.variable} = {r.valor} {r.unidad} · {r.fuente} · {r.calidad}")
    print(f"Nota: {r.nota}")
except noaa_enso.ErrorENSO as error:
    print(f"Error: {error}")

if oni is not None and psl is not None:
    print(f"\nComparación: ONI {oni:+.2f} · PSL {psl:+.2f} · diferencia {abs(oni - psl):.2f} °C "
          f"({'menor' if abs(oni - psl) < 0.3 else 'NO menor'} a 0,3 °C)")

print("\n4) Cadena completa (lo que responde GET /enso)")
[c] = noaa_enso.obtener_enso("consulta", cliente)
print(f"{c.fecha} · {c.valor} · {c.calidad} · {c.nota[:200]}")

if oni is None or psl is None:
    sys.exit("Falló el principal o el respaldo: revisar lo que devolvió cada servidor")
