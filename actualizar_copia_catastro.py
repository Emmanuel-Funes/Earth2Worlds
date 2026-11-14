"""Renueva la copia del mapa de parcelas rurales que usa el conector del Catastro de San Luis cuando el Catastro no
contesta (spec 045). Se usa desde GitHub (Actions → "Actualizar copia del Catastro").

Sin argumentos baja el mapa completo del Catastro. Con --desde ARCHIVO usa un mapa ya bajado de
/catastro-sl/parcelas-rurales (así se armó la primera copia, con el mapa del 5/10/2026)."""

import argparse
import asyncio
import gzip
import json
import sys
from pathlib import Path

from rotaterra.fuentes import catastro_sl as catastro

MINIMO = 0.9  # un mapa con menos del 90 % de las parcelas de la copia anterior no la reemplaza


def guardar_copia(datos: dict, carpeta: Path = catastro.DATOS) -> dict:
    cantidad = len(datos.get("features", []))
    anterior = carpeta / catastro.COPIA_INFO.name
    if anterior.exists():
        antes = json.loads(anterior.read_text(encoding="utf-8"))["cantidad"]
        if cantidad < MINIMO * antes:
            raise SystemExit(f"El mapa nuevo trae {cantidad} parcelas y la copia tiene {antes}: parece incompleto, "
                             "no se reemplaza la copia.")
    fecha = datos["fecha_consulta"]
    datos = {**datos, "cantidad": cantidad,
             "nota": f"Copia del mapa de parcelas rurales guardada en el repo el {fecha}: se entrega cuando el "
                     f"Catastro no contesta (spec 045). {datos.get('nota', '')}".strip()}
    texto = json.dumps(datos, ensure_ascii=False, separators=(",", ":")).encode()
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / catastro.COPIA.name).write_bytes(gzip.compress(texto, 9, mtime=0))
    info = {"fecha": fecha, "cantidad": cantidad, "fuente": catastro.FUENTE, "capa": catastro.CAPAS["RURAL"]}
    anterior.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return info


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--desde", type=Path, help="mapa ya bajado (GeoJSON de /catastro-sl/parcelas-rurales)")
    desde = argumentos.parse_args().desde
    if desde:
        datos = json.loads(desde.read_text(encoding="utf-8"))
    else:
        print("Bajando el mapa completo de parcelas rurales del Catastro de San Luis…", flush=True)
        datos = asyncio.run(catastro.parcelas_rurales())
    if datos.get("truncado"):
        sys.exit("El mapa vino truncado: no se reemplaza la copia.")
    info = guardar_copia(datos)
    tamano = catastro.COPIA.stat().st_size / 1e6
    print(f"Copia guardada: {info['cantidad']} parcelas del {info['fecha']}, {tamano:.1f} MB comprimida.")


if __name__ == "__main__":
    main()
