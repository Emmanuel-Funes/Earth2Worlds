"""Prueba real de los rindes de referencia del departamento (Ministerio de Agricultura). Se usa desde GitHub
(Actions → "Probar MAGyP (rindes de referencia)").

Georef se consulta en vivo; los rindes salen de la copia del CSV del Ministerio guardada en el repo. Además se
mira, sin cortar la prueba, si el portal del Ministerio responde y si su CSV vigente sigue siendo el de la copia."""

import sys
import time
from collections import Counter

from rotaterra.fuentes import magyp_rindes as magyp

lat, lon = float(sys.argv[1]), float(sys.argv[2])
departamento_id = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else None
# investigación 033 (14/10/2026): General Pedernera, medianas de 2015/16 a 2024/25
ESPERADAS = {"maiz": 4950, "soja": 2100, "sorgo": 3650, "mani": 3055, "girasol": 1850, "trigo": 1450}

cliente = magyp.nuevo_cliente()

print(f"1) Georef: departamento de ({lat}, {lon})", flush=True)
r = cliente.get(magyp.URL_GEOREF, params={"lat": lat, "lon": lon})
print(f"HTTP {r.status_code}\n{r.text[:800]}\n")
if departamento_id:
    print(f"El pedido trae departamento_id={departamento_id}: no se usa Georef")
    codigo = magyp.codigo_indec(departamento_id)
else:
    codigo, nombre, provincia = magyp.departamento_del_punto(lat, lon, cliente)
    print(f"Departamento: {codigo} = {nombre}, {provincia}")

print("\n2) Copia del CSV del Ministerio en el repo", flush=True)
texto, ficha = magyp.leer_copia()
print(f"{magyp.COPIA.name} · {magyp.COPIA.stat().st_size / 1e6:.2f} MB comprimida · ficha: {ficha}")
filas = list(magyp.lector(texto))
del_departamento = [f for f in filas if magyp.es_del_departamento(codigo, f.get("provincia_id"), f.get("departamento_id"))]
print(f"{len(filas)} filas · del departamento {codigo}: {len(del_departamento)}")
cultivos = Counter((f.get("cultivo") or "") for f in del_departamento)
print("Cultivos del departamento (nombre del Ministerio -> catálogo, filas):")
for nombre, cuantas in sorted(cultivos.items()):
    print(f"  {nombre!r:<28} -> {magyp.cultivo_del_catalogo(nombre)!s:<9} {cuantas}")

print("\n3) ¿El portal del Ministerio responde? (solo diagnóstico, no corta la prueba)", flush=True)
inicio = time.time()
try:
    vigente = magyp.buscar_csv(cliente).rsplit("/", 1)[-1]
    igual = "es el de la copia" if vigente == ficha.get("archivo") else "ES OTRO: correr 'Actualizar copia de MAGyP'"
    print(f"Responde ({time.time() - inicio:.0f} s). CSV vigente: {vigente} · {igual}")
except magyp.ErrorMAGyP as error:
    print(f"No responde ({time.time() - inicio:.0f} s): {error}")

print("\n4) Rindes de referencia", flush=True)
obs = magyp.obtener_rindes("lote-prueba", lat, lon, departamento_id, cliente)
print(f"{'Variable':<34}{'Valor':>7}  {'Calidad':<11}{'Fecha':<12}Esperada (033)")
distintas = []
for o in obs:
    cultivo = o.variable.removeprefix("rinde_referencia_").removesuffix("_kg_ha")
    esperada = ESPERADAS.get(cultivo)
    marca = ""
    if esperada is not None:
        marca = f"{esperada} {'COINCIDE' if o.valor == esperada else 'DIFIERE'}"
        if o.valor != esperada:
            distintas.append(cultivo)
    print(f"{o.variable:<34}{'—' if o.valor is None else int(o.valor):>7}  {o.calidad:<11}{o.fecha!s:<12}{marca}")
print("\nNotas:")
for o in obs:
    print(f"  {o.variable}: {o.nota}")
if not any(o.calidad != "descartada" for o in obs):
    sys.exit("Ningún cultivo con rinde: revisar el diagnóstico")
if codigo == "74035" and distintas:
    sys.exit(f"Las medianas de General Pedernera no dan las de la investigación 033: {distintas}")
