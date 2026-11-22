"""
Lista de las apps instaladas en Windows (las mismas que ves en el menú Inicio), para elegir una al armar un comando
en vez de buscar su .exe a mano. Incluye programas de escritorio y apps de la Microsoft Store.

Usa Get-StartApps de PowerShell, que ya trae Windows: no instala nada y no usa internet.
Cada app se abre con "shell:AppsFolder\\<id>", que funciona para todas.
"""
import json
import subprocess
import sys
import unicodedata

SIN_VENTANA = 0x08000000 if sys.platform == "win32" else 0
PREFIJO = "shell:AppsFolder\\"
SCRIPT = ("[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
          "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress")


def _correr_real(argumentos):
    return subprocess.run(argumentos, capture_output=True, creationflags=SIN_VENTANA, timeout=60)


def leer(correr=_correr_real):
    """[(nombre, destino)] ordenado por nombre y sin repetidos. Lanza OSError si PowerShell no responde."""
    resultado = correr(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                        "-Command", SCRIPT])
    if getattr(resultado, "returncode", 0) not in (0, None):
        raise OSError("PowerShell no pudo listar las apps.")
    texto = resultado.stdout.decode("utf-8", errors="replace").strip().lstrip("﻿")
    return interpretar(texto)


def interpretar(texto):
    """Pasa el JSON de PowerShell a [(nombre, destino)]."""
    if not texto:
        return []
    try:
        datos = json.loads(texto)
    except ValueError as error:
        raise OSError("No entendí la lista de apps.") from error
    if isinstance(datos, dict):      # con una sola app, PowerShell devuelve un objeto y no una lista
        datos = [datos]
    apps, vistas = [], set()
    for d in datos:
        nombre, id_ = str(d.get("Name") or "").strip(), str(d.get("AppID") or "").strip()
        if not nombre or not id_ or (nombre.lower(), id_) in vistas:
            continue
        vistas.add((nombre.lower(), id_))
        apps.append((nombre, PREFIJO + id_))
    return sorted(apps, key=lambda a: a[0].lower())


def _sin_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def filtrar(apps, busqueda):
    """Las que contienen todas las palabras escritas (sin importar mayúsculas ni tildes)."""
    palabras = _sin_tildes(busqueda).split()
    return [a for a in apps if all(p in _sin_tildes(a[0]) for p in palabras)]
