"""Carga o actualiza un lote en la base. Se usa desde GitHub (Actions → "Cargar lote")."""

import os
import sys

from rotaterra import base
from rotaterra.geo import poligono_desde_esquinas, validar_poligono

if not os.environ.get("DATABASE_URL"):
    print("Falta el secreto DATABASE_URL: todavía no hay base de datos configurada.")
    sys.exit(1)

lote_id, nombre, esquinas = sys.argv[1], sys.argv[2], sys.argv[3]
poligono = poligono_desde_esquinas(esquinas)
validar_poligono(poligono)
lote = base.guardar_lote(base.conectar(), lote_id, nombre, poligono)
print(f"Lote '{lote['id']}' ({lote['nombre']}) guardado. Centro: {lote['lat']}, {lote['lon']}.")
print("Sus datos se bajan en la próxima actualización nocturna, o ya mismo con 'Actualizar datos (nocturno)'.")
