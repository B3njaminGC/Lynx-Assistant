"""
Copias de seguridad de tus comandos y tu configuración.

- Exportar: un .zip que podés guardar donde quieras (sin el token de Telegram, para poder compartirlo).
- Importar: lo restaura; antes guarda una copia automática de lo que había, así nunca se pierde nada.
- Automática: una vez por día al abrir el asistente, y antes de actualizar o de importar.
  Quedan las últimas 10 en la carpeta "respaldos" junto al programa.
"""
import json
import time
import zipfile
from datetime import datetime

import nucleo

CARPETA_RESPALDOS = nucleo.BASE / "respaldos"
GUARDAR_ULTIMOS = 10
NOMBRES = ("comandos.json", "config.json")
SECRETOS = ("telegram_token",)  # no van en el zip que exportás


class ErrorRespaldo(Exception):
    pass


def _leer_json(ruta):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _hay_algo_que_guardar():
    return any((nucleo.BASE / nombre).exists() for nombre in NOMBRES)


def copia_automatica(motivo="auto", carpeta=None):
    """Guarda una copia (con todo, token incluido: queda en tu PC). Devuelve la ruta o None."""
    if not _hay_algo_que_guardar():
        return None
    carpeta = carpeta or CARPETA_RESPALDOS
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"respaldo-{datetime.now():%Y%m%d-%H%M%S}-{motivo}.zip"
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre in NOMBRES:
            if (nucleo.BASE / nombre).exists():
                z.write(nucleo.BASE / nombre, nombre)
    viejos = sorted(carpeta.glob("respaldo-*.zip"))[:-GUARDAR_ULTIMOS]
    for v in viejos:
        try:
            v.unlink()
        except OSError:
            pass
    return destino


def copia_diaria():
    """Al abrir el asistente: si la última copia tiene más de un día, hace otra."""
    try:
        ultimas = sorted(CARPETA_RESPALDOS.glob("respaldo-*.zip"))
        if ultimas and time.time() - ultimas[-1].stat().st_mtime < 24 * 3600:
            return None
        return copia_automatica("diaria")
    except Exception as error:
        nucleo.log("[respaldo] no pude hacer la copia diaria:", error)
        return None


def exportar(destino):
    """Escribe el .zip de respaldo en 'destino' (sin secretos). Devuelve cuántos comandos incluye."""
    comandos = _leer_json(nucleo.ARCHIVO_COMANDOS)
    config = _leer_json(nucleo.ARCHIVO_CONFIG) or {}
    if comandos is None:
        comandos = []
    for clave in SECRETOS:
        config.pop(clave, None)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("comandos.json", json.dumps(comandos, ensure_ascii=False, indent=2))
        z.writestr("config.json", json.dumps(config, ensure_ascii=False, indent=2))
        z.writestr("LEEME.txt", "Respaldo de Lynx. Para recuperarlo: Lynx > General > Restaurar copia.\n"
                                "No incluye el token de Telegram ni las voces de personaje.\n")
    return len(comandos)


def leer_respaldo(ruta):
    """Valida un .zip de respaldo y devuelve (comandos, config). Levanta ErrorRespaldo si algo no cuadra."""
    try:
        with zipfile.ZipFile(ruta) as z:
            nombres = set(z.namelist())
            if "comandos.json" not in nombres:
                raise ErrorRespaldo("Ese archivo no es un respaldo de Lynx (falta comandos.json).")
            comandos = json.loads(z.read("comandos.json").decode("utf-8"))
            config = json.loads(z.read("config.json").decode("utf-8")) if "config.json" in nombres else {}
    except ErrorRespaldo:
        raise
    except (OSError, ValueError, KeyError, zipfile.BadZipFile):
        raise ErrorRespaldo("No pude leer ese archivo: no es un respaldo válido.") from None
    if not isinstance(comandos, list) or not all(isinstance(c, dict) and c.get("frase") and c.get("tipo")
                                                  for c in comandos):
        raise ErrorRespaldo("Los comandos del respaldo están dañados.")
    if not isinstance(config, dict):
        raise ErrorRespaldo("La configuración del respaldo está dañada.")
    return comandos, config


def restaurar(ruta, configuracion_actual):
    """
    Restaura comandos y configuración desde 'ruta'. Antes guarda una copia automática de lo actual.
    Devuelve (cantidad_de_comandos, config_nueva). La configuración nueva se completa con los valores por
    defecto y conserva tus secretos actuales (por ejemplo el token de Telegram) si el respaldo no los trae.
    """
    comandos, config = leer_respaldo(ruta)
    copia_automatica("antes-de-restaurar")
    nueva = dict(nucleo.CONFIG_BASE)
    nueva.update({k: v for k, v in config.items() if k in nucleo.CONFIG_BASE})
    for clave in SECRETOS:
        if not nueva.get(clave) and configuracion_actual.get(clave):
            nueva[clave] = configuracion_actual[clave]
    nucleo.guardar_comandos(comandos)
    return len(comandos), nueva
