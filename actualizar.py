"""Aviso de versión nueva: mira en GitHub si hay un release más nuevo. Nunca instala nada solo."""
import json
import re
import urllib.request

VERSION = "1.0"
REPO = "B3njaminGC/Lynx-Assistant"
API = f"https://api.github.com/repos/{REPO}/releases/latest"


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
        return etiqueta.lstrip("vV"), enlace
    except Exception:
        return None
