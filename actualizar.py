"""Aviso de versión nueva: mira en GitHub si hay un release más nuevo. Nunca instala nada solo."""
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from collections import namedtuple

VERSION = "1.3"
REPO = "B3njaminGC/Lynx-Assistant"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
NOMBRE_INSTALADOR = "Instalar-Lynx.exe"
# version, enlace (página del release), descarga (URL del instalador o None), sha256 (o None)
Nueva = namedtuple("Nueva", "version enlace descarga sha256")


def _numeros(texto):
    """'v1.2.3' -> (1, 2, 3); None si no parece una versión."""
    m = re.search(r"\d+(?:\.\d+)*", str(texto))
    return tuple(int(x) for x in m.group(0).split(".")) if m else None


def es_mas_nueva(remota, actual=VERSION):
    a, b = _numeros(remota), _numeros(actual)
    if not a or not b:
        return False
    largo = max(len(a), len(b))
    return a + (0,) * (largo - len(a)) > b + (0,) * (largo - len(b))


def consultar(abrir=urllib.request.urlopen, timeout=8):
    """Devuelve (version, enlace_de_descarga) si hay una versión más nueva; None si no (o sin internet)."""
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
        descarga = sha = None
        for archivo in datos.get("assets") or []:
            if archivo.get("name") == NOMBRE_INSTALADOR:
                url = archivo.get("browser_download_url") or ""
                digest = str(archivo.get("digest") or "")
                if url.startswith("https://github.com/") and digest.startswith("sha256:"):
                    descarga, sha = url, digest[7:].lower()
        return Nueva(etiqueta.lstrip("vV"), enlace, descarga, sha)
    except Exception:
        return None


def esta_instalado():
    """True si este programa corre desde el instalador (junto al .exe está el desinstalador de Inno Setup)."""
    if not getattr(sys, "frozen", False):
        return False
    return os.path.exists(os.path.join(os.path.dirname(sys.executable), "unins000.exe"))


def descargar_instalador(info, progreso=lambda fraccion: None, abrir=urllib.request.urlopen):
    """Baja el instalador a la carpeta temporal y comprueba que sea el publicado (sha256). Devuelve la ruta."""
    if not (info.descarga and info.sha256):
        raise RuntimeError("Esta versión no trae un instalador verificable.")
    destino = os.path.join(os.environ.get("TEMP", "."), f"Instalar-Lynx-{info.version}.exe")
    parcial = destino + ".part"
    pedido = urllib.request.Request(info.descarga, headers={"User-Agent": "Lynx-Asistente"})
    suma = hashlib.sha256()
    with abrir(pedido, timeout=30) as r, open(parcial, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        hecho = 0
        while True:
            bloque = r.read(1024 * 256)
            if not bloque:
                break
            f.write(bloque)
            suma.update(bloque)
            hecho += len(bloque)
            if total:
                progreso(hecho / total)
    if suma.hexdigest() != info.sha256:
        os.remove(parcial)
        raise RuntimeError("El archivo descargado no coincide con el publicado. No lo instalé.")
    os.replace(parcial, destino)
    return destino


def lanzar_instalador(ruta):
    """Corre el instalador en silencio; reemplaza la versión actual y vuelve a abrir Lynx."""
    subprocess.Popen([ruta, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"],
                     close_fds=True)
