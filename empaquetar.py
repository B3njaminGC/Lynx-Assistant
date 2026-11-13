"""
Arma el parche de código de Lynx: codigo-base<N>.zip (unos cientos de KB).

    python empaquetar.py

Se sube a un release de GitHub (con la etiqueta "v" + la versión de actualizar.py, por ejemplo v1.5);
las copias instaladas lo detectan y se actualizan con el botón "Actualizar ahora", sin reinstalar.

BASE_MINIMA es la base del .exe que el parche necesita. Solo se sube cuando el código empieza a usar
algo que el .exe no trae (una librería nueva): ahí hace falta publicar también un Instalar-Lynx.exe.
"""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

import actualizar

BASE_MINIMA = 1
EXCLUIR = {"lanzador.py", "empaquetar.py", "asistente.py"}


def empaquetar(destino_dir="."):
    aqui = Path(__file__).resolve().parent
    nombre = f"codigo-base{BASE_MINIMA}.zip"
    destino = Path(destino_dir) / nombre
    modulos = sorted(p for p in aqui.glob("*.py") if p.name not in EXCLUIR and not p.name.startswith("prueba"))
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifiesto.json", json.dumps({"version": actualizar.VERSION, "base": BASE_MINIMA}))
        for modulo in modulos:
            z.write(modulo, modulo.name)
    huella = hashlib.sha256(destino.read_bytes()).hexdigest()
    return destino, huella, [m.name for m in modulos]


if __name__ == "__main__":
    ruta, huella, modulos = empaquetar(sys.argv[1] if len(sys.argv) > 1 else ".")
    print(f"{ruta}  ({ruta.stat().st_size // 1024} KB, versión {actualizar.VERSION})")
    print("sha256:", huella)
    print("módulos:", ", ".join(modulos))
