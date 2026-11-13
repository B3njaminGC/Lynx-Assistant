"""
Punto de entrada del .exe de Lynx.

El programa instalado trae su propio código adentro, pero si junto al .exe hay una carpeta "codigo" con un
parche más nuevo (lo baja el botón "Actualizar ahora"), se usa ese código en lugar del que viene adentro.
Si el parche falla al arrancar, se descarta solo y Lynx vuelve a abrirse con el código original.

BASE_NIVEL es la "base" de este .exe (Python + librerías). Se sube solo cuando hace falta un instalador
completo, por ejemplo al agregar una librería nueva; los parches de código declaran qué base necesitan.
"""
import importlib.abc
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

BASE_NIVEL = "1"
os.environ["LYNX_BASE"] = BASE_NIVEL
SIN_VENTANA = 0x08000000 if sys.platform == "win32" else 0


def carpeta_del_programa():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


class BuscadorDeParche(importlib.abc.MetaPathFinder):
    """Entrega los módulos de la carpeta del parche antes que los que vienen dentro del .exe."""

    def __init__(self, carpeta):
        self.carpeta = Path(carpeta)
        self.nombres = {p.stem for p in self.carpeta.glob("*.py")}

    def find_spec(self, nombre, path=None, target=None):
        if nombre in self.nombres:
            return importlib.util.spec_from_file_location(nombre, self.carpeta / f"{nombre}.py")
        return None


def _numeros(texto):
    import re
    m = re.search(r"\d+(?:\.\d+)*", str(texto))
    return tuple(int(x) for x in m.group(0).split(".")) if m else ()


def parche_utilizable(base):
    """Ruta de la carpeta 'codigo' si trae una versión más nueva que la del .exe y una base compatible."""
    carpeta = Path(base) / "codigo"
    try:
        manifiesto = json.loads((carpeta / "manifiesto.json").read_text(encoding="utf-8"))
        if int(manifiesto.get("base", 1)) > int(BASE_NIVEL):
            return None
        import actualizar as incluido  # el que viene dentro del .exe
        version_del_exe = incluido.VERSION
        sys.modules.pop("actualizar", None)
        largo = max(len(_numeros(manifiesto["version"])), len(_numeros(version_del_exe)))
        relleno = lambda v: _numeros(v) + (0,) * (largo - len(_numeros(v)))
        if relleno(manifiesto["version"]) > relleno(version_del_exe) and (carpeta / "app.py").exists():
            return carpeta
    except Exception:
        pass
    return None


def activar_parche(base):
    """Si hay un parche utilizable lo pone primero en la búsqueda de módulos. Devuelve su carpeta o None."""
    carpeta = parche_utilizable(base)
    if carpeta is None:
        return None
    sys.meta_path.insert(0, BuscadorDeParche(carpeta))
    return carpeta


def descartar_parche(base):
    """Aparta el parche que falló (queda en codigo.fallido para poder mirarlo)."""
    base = Path(base)
    shutil.rmtree(base / "codigo.fallido", ignore_errors=True)
    try:
        (base / "codigo").rename(base / "codigo.fallido")
    except OSError:
        shutil.rmtree(base / "codigo", ignore_errors=True)


def _anotar(base, texto):
    try:
        with open(Path(base) / "asistente.log", "a", encoding="utf-8") as f:
            f.write(texto + "\n")
    except OSError:
        pass


def main():
    base = carpeta_del_programa()
    carpeta = activar_parche(base)
    try:
        import app
        if carpeta is not None:
            _anotar(base, f"[lanzador] usando el parche de código de {carpeta}")
        app.main()
    except SystemExit:
        raise
    except BaseException:
        if carpeta is None:
            raise
        # El parche no arrancó: se aparta y Lynx se vuelve a abrir con el código original.
        _anotar(base, "[lanzador] el parche falló y se descartó:\n" + traceback.format_exc())
        descartar_parche(base)
        subprocess.Popen([sys.executable] + sys.argv[1:], close_fds=True, creationflags=SIN_VENTANA)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        _anotar(carpeta_del_programa(), "ERROR FATAL:\n" + traceback.format_exc())
        try:
            import tkinter as tk
            from tkinter import messagebox
            raiz = tk.Tk()
            raiz.withdraw()
            messagebox.showerror("Asistente de voz",
                                 "El asistente no pudo iniciar. Mirá asistente.log junto al programa.")
        except Exception:
            pass
        sys.exit(1)
