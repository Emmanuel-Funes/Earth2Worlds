"""Prueba real contra GRACE-FO (napa y agua profunda). Se usa desde GitHub
(Actions → "Probar GRACE (napa y agua profunda)")."""

import sys
import time
from datetime import date

from rotaterra.fuentes import earthdata, grace

lat, lon = float(sys.argv[1]), float(sys.argv[2])
desde, hasta = date.fromisoformat(sys.argv[3]), date.fromisoformat(sys.argv[4])


def diagnostico(producto: str) -> None:
    """Qué ve la NASA del producto, sin credenciales a la vista: colección, archivos, metadatos y una coordenada."""
    try:
        cliente = earthdata.cliente_autorizado()
        coleccion = earthdata.coleccion_vigente(cliente, producto)
        print(f"Colección {producto}: {coleccion}")
        archivos = earthdata.archivos(cliente, coleccion, desde, hasta)
        print(f"Archivos en el período: {len(archivos)}")
        for nombre, url in archivos[:2]:
            print(f"  {nombre}\n    {url}")
        if archivos:
            url = archivos[-1][1]
            dmr = cliente.get(f"{url}.dmr")
            print(f"\nMetadatos: HTTP {dmr.status_code}")
            print("\n".join(l for l in dmr.text.splitlines() if "<Dim" in l or "name=" in l)[:3000])
            muestra = cliente.get(f"{url}.dap.csv", params={"dap4.ce": "lat"})
            print(f"\nCSV de 'lat': HTTP {muestra.status_code}\n{muestra.text[:400]}")
    except Exception as otro:
        print(f"(el diagnóstico también falló: {type(otro).__name__}: {otro})")


print(f"1) Principal: GRACE-DA ({grace.PRODUCTO}) para ({lat}, {lon}) del {desde} al {hasta}", flush=True)
inicio = time.time()
try:
    leidos, ultima = grace.leer_periodo(lat, lon, desde, hasta)
except grace.ErrorGRACE as error:
    print(f"Error: {error}\n")
    diagnostico(grace.PRODUCTO)
    raise
obs = grace.observaciones("lote-prueba", desde, hasta, leidos, ultima)
print(f"{len(leidos)} semanas publicadas en el período · última semana publicada: {ultima} · "
      f"{time.time() - inicio:.0f} s")
print(f"Esquema leído: {grace._ESQUEMA}\n" if len(str(grace._ESQUEMA)) < 600 else "")
print(f"{'Semana':<12}{'Napa':>7}{'Raíces':>8}{'Superf.':>9}  Categoría de la napa")
por_fecha: dict[date, dict[str, float | None]] = {}
for o in obs:
    por_fecha.setdefault(o.fecha, {})[o.variable] = o.valor
fmt = lambda v: "   —  " if v is None else f"{v:6.1f}"
for dia, v in sorted(por_fecha.items()):
    napa = v.get("napa_percentil")
    print(f"{dia!s:<12}{fmt(napa):>7}{fmt(v.get('humedad_raices_percentil')):>8}"
          f"{fmt(v.get('humedad_superficial_percentil')):>9}  {'' if napa is None else grace.categoria(napa)}")
buenas = sum(1 for o in obs if o.calidad == "buena")
print(f"\n{len(obs)} observaciones: {buenas} buenas, {sum(1 for o in obs if o.calidad == 'dudosa')} dudosas, "
      f"{sum(1 for o in obs if o.calidad == 'descartada')} descartadas.")
print(f"Ejemplo de nota: {next((o.nota for o in obs if o.valor is not None), obs[0].nota if obs else '')}")
if not buenas:
    sys.exit("Ninguna semana con dato: revisar el diagnóstico")

print(f"\n2) Respaldo: mascons de JPL ({grace.PRODUCTO_MASCON})", flush=True)
inicio = time.time()
try:
    meses = grace.obtener_mascon("lote-prueba", lat, lon, desde, hasta)
except grace.ErrorGRACE as error:
    print(f"Error: {error}\n")
    diagnostico(grace.PRODUCTO_MASCON)
    raise
print(f"{len(meses)} meses · {time.time() - inicio:.0f} s")
for o in meses:
    print(f"{o.fecha!s:<12}{fmt(o.valor):>8} cm  {o.calidad}")
print(f"Ejemplo de nota: {next((o.nota for o in meses if o.valor is not None), '')}")
