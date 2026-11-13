"""
Actualizaciones de Lynx desde GitHub. Nunca instala nada sin que toques el botón.

Hay dos tipos de release:
- Parche de código ("codigo-base1.zip", pesa unos cientos de KB): se baja, se verifica y se aplica en
  segundos, sin reinstalar. Es lo normal para mejoras y arreglos.
- Instalador completo ("Instalar-Lynx.exe"): hace falta solo cuando cambia algo de base del programa
  (una librería nueva, por ejemplo). Los parches avisan de qué "base" necesitan.
"""
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from collections import namedtuple
from pathlib import Path

VERSION = "1.4"
REPO = "B3njaminGC/Lynx-Assistant"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
NOMBRE_INSTALADOR = "Instalar-Lynx.exe"
PATRON_CODIGO = re.compile(r"^codigo-base(\d+)\.zip$")
MAXIMO_CODIGO = 20 * 1024 * 1024  # un parche de código jamás pesa tanto: si pasa, algo está mal
SIN_VENTANA = 0x08000000 if sys.platform == "win32" else 0

# version, enlace (página del release), descarga + sha256 (instalador completo o None),
# codigo + codigo_sha + base (parche de código o None)
Nueva = namedtuple("Nueva", "version enlace descarga sha256 codigo codigo_sha base")


def base_actual():
    """Nivel de la parte fija del programa (el .exe); lo define el lanzador. Un parche pide una base mínima."""
    try:
        return int(os.environ.get("LYNX_BASE", "1"))
    except ValueError:
        return 1


def _numeros(texto):
    """'v1.2.3' -> (1, 2, 3); None si no parece una versión."""
    m = re.search(r"\d+(?:\.\d+)*", str(texto))
    return tuple(int(x) for x in m.group(0).split(".")) if m else None


def es_mas_nueva(remota, actual=None):
    actual = VERSION if actual is None else actual
    a, b = _numeros(remota), _numeros(actual)
    if not a or not b:
        return False
    largo = max(len(a), len(b))
    return a + (0,) * (largo - len(a)) > b + (0,) * (largo - len(b))


def _asset_confiable(archivo):
    url = archivo.get("browser_download_url") or ""
    digest = str(archivo.get("digest") or "")
    if url.startswith("https://github.com/") and digest.startswith("sha256:"):
        return url, digest[7:].lower()
    return None, None


def consultar(abrir=urllib.request.urlopen, timeout=8):
    """Devuelve una Nueva si hay un release más nuevo; None si no (o si no hay internet)."""
    try:
        pedido = urllib.request.Request(API, headers={"User-Agent": "Lynx-Asistente",
                                                      "Accept": "application/vnd.github+json"})
        with abrir(pedido, timeout=timeout) as r:
            datos = json.loads(r.read().decode("utf-8"))
        etiqueta = datos.get("tag_name") or datos.get("name") or ""
        if datos.get("draft") or datos.get("prerelease") or not es_mas_nueva(etiqueta):
            return None
        enlace = datos.get("html_url") or f"https://github.com/{REPO}/releases/latest"
        if not enlace.startswith("https://github.com/"):
            enlace = f"https://github.com/{REPO}/releases/latest"
        descarga = sha = codigo = codigo_sha = None
        base = 0
        for archivo in datos.get("assets") or []:
            nombre = archivo.get("name") or ""
            url, huella = _asset_confiable(archivo)
            if not url:
                continue
            if nombre == NOMBRE_INSTALADOR:
                descarga, sha = url, huella
            else:
                m = PATRON_CODIGO.match(nombre)
                if m:
                    codigo, codigo_sha, base = url, huella, int(m.group(1))
        return Nueva(etiqueta.lstrip("vV"), enlace, descarga, sha, codigo, codigo_sha, base)
    except Exception:
        return None


def esta_instalado():
    """True si este programa corre desde el instalador (junto al .exe está el desinstalador de Inno Setup)."""
    if not getattr(sys, "frozen", False):
        return False
    return os.path.exists(os.path.join(os.path.dirname(sys.executable), "unins000.exe"))


def puede_aplicar_parche(info):
    return bool(esta_instalado() and info.codigo and info.codigo_sha and info.base <= base_actual())


def _bajar(url, sha, destino, progreso, abrir, maximo=None):
    """Descarga a 'destino' y comprueba el sha256 publicado. Si no coincide, no deja nada."""
    parcial = str(destino) + ".part"
    pedido = urllib.request.Request(url, headers={"User-Agent": "Lynx-Asistente"})
    suma = hashlib.sha256()
    with abrir(pedido, timeout=30) as r, open(parcial, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        hecho = 0
        while True:
            bloque = r.read(1024 * 256)
            if not bloque:
                break
            hecho += len(bloque)
            if maximo and hecho > maximo:
                f.close()
                os.remove(parcial)
                raise RuntimeError("El archivo es más grande de lo esperado. No lo instalé.")
            f.write(bloque)
            suma.update(bloque)
            if total:
                progreso(hecho / total)
    if suma.hexdigest() != sha:
        os.remove(parcial)
        raise RuntimeError("El archivo descargado no coincide con el publicado. No lo instalé.")
    os.replace(parcial, destino)
    return destino


def descargar_instalador(info, progreso=lambda fraccion: None, abrir=urllib.request.urlopen):
    """Baja el instalador completo a la carpeta temporal y lo verifica. Devuelve la ruta."""
    if not (info.descarga and info.sha256):
        raise RuntimeError("Esta versión no trae un instalador verificable.")
    destino = os.path.join(os.environ.get("TEMP", "."), f"Instalar-Lynx-{info.version}.exe")
    return _bajar(info.descarga, info.sha256, destino, progreso, abrir)


def lanzar_instalador(ruta):
    """Corre el instalador en silencio; reemplaza la versión actual y vuelve a abrir Lynx."""
    subprocess.Popen([ruta, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"],
                     close_fds=True)


# ------------------------------------------------------------------ parche de código

def preparar_parche(info, base_dir, progreso=lambda fraccion: None, abrir=urllib.request.urlopen):
    """
    Baja el parche, lo verifica y lo deja en base_dir/codigo.nuevo sin activarlo todavía.
    Solo acepta archivos .py y manifiesto.json en la raíz del zip, y que todos compilen.
    """
    base_dir = Path(base_dir)
    zip_ruta = Path(os.environ.get("TEMP", ".")) / f"lynx-codigo-{info.version}.zip"
    _bajar(info.codigo, info.codigo_sha, zip_ruta, progreso, abrir, maximo=MAXIMO_CODIGO)
    nuevo = base_dir / "codigo.nuevo"
    shutil.rmtree(nuevo, ignore_errors=True)
    nuevo.mkdir(parents=True)
    try:
        with zipfile.ZipFile(zip_ruta) as z:
            miembros = z.infolist()
            if sum(m.file_size for m in miembros) > MAXIMO_CODIGO:
                raise RuntimeError("El parche es sospechosamente grande. No lo instalé.")
            for m in miembros:
                nombre = m.filename
                if "/" in nombre or "\\" in nombre or nombre.startswith(".") or \
                        not (nombre.endswith(".py") or nombre == "manifiesto.json"):
                    raise RuntimeError(f"El parche trae un archivo inesperado ({nombre}). No lo instalé.")
                (nuevo / nombre).write_bytes(z.read(m))
        if not (nuevo / "manifiesto.json").exists():
            raise RuntimeError("El parche no trae manifiesto. No lo instalé.")
        manifiesto = json.loads((nuevo / "manifiesto.json").read_text(encoding="utf-8"))
        if str(manifiesto.get("version")) != str(info.version):
            raise RuntimeError("La versión del parche no coincide con la del release. No lo instalé.")
        if int(manifiesto.get("base", 1)) > base_actual():
            raise RuntimeError("Este parche necesita una base más nueva: hay que instalar el instalador completo.")
        for archivo in nuevo.glob("*.py"):
            ast.parse(archivo.read_text(encoding="utf-8"), filename=archivo.name)
    except Exception:
        shutil.rmtree(nuevo, ignore_errors=True)
        raise
    finally:
        try:
            os.remove(zip_ruta)
        except OSError:
            pass
    return nuevo


def activar_parche(base_dir):
    """Cambia codigo.nuevo por codigo (la versión anterior queda en codigo.anterior por si hay que volver)."""
    base_dir = Path(base_dir)
    nuevo, actual, anterior = base_dir / "codigo.nuevo", base_dir / "codigo", base_dir / "codigo.anterior"
    if not nuevo.is_dir():
        raise RuntimeError("No hay un parche preparado.")
    shutil.rmtree(anterior, ignore_errors=True)
    if actual.exists():
        actual.rename(anterior)
    nuevo.rename(actual)


def reiniciar_programa():
    """Abre Lynx de nuevo unos segundos después de que esta copia se cierre."""
    ejecutable = sys.executable
    subprocess.Popen(f'cmd /c ping -n 4 127.0.0.1 >nul & start "" "{ejecutable}"',
                     creationflags=SIN_VENTANA | 0x00000008, close_fds=True)
