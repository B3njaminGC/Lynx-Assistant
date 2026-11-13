"""
Control remoto por Telegram: desde el celular le preguntás a la PC cómo va una descarga, cuánta batería
queda, o le pedís que haga algo (los mismos comandos de Lynx), y la PC te avisa cuando termina algo.

Funciona con un bot propio de Telegram (se crea gratis con @BotFather). Solo obedece a UNA cuenta:
la tuya (por su ID). Cualquier otra persona que le escriba al bot es ignorada.
Usa solo la librería estándar: no hay que instalar nada.
"""
import ctypes
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import nucleo

SIN_VENTANA = 0x08000000 if sys.platform == "win32" else 0
EXTENSIONES_DESCARGA = (".crdownload", ".part", ".opdownload", ".download", ".partial", ".!qb",
                        ".aria2", ".tmp", ".ytdl")
ACTIVA_SI_TOCADA_HACE = 45      # una descarga "en curso" es un archivo temporal que creció hace menos de esto (s)
TERMINA_SI_QUIETA_POR = 45      # se da por terminada si pasan estos segundos sin actividad (s)
SEGUNDOS_PARA_APAGAR = 60       # cuenta regresiva antes de apagar (se puede cancelar)
MENSAJE_VIEJO = 300             # un mensaje de hace más de 5 minutos se ignora (por si llegó mientras estaba apagada)
VIGILANCIA_MAXIMA = 12 * 3600   # deja de vigilar una descarga a las 12 horas

AYUDA = (
    "Esto puedo hacer:\n"
    "• \"cuánto va la descarga\"\n"
    "• \"cuánta batería tengo\"\n"
    "• \"estado\" (resumen de todo)\n"
    "• \"avisame cuando termine la descarga\"\n"
    "• \"apagá la PC cuando termine la descarga\" (te aviso y la apago con cuenta regresiva)\n"
    "• \"apagá la PC\" (te pido confirmación)\n"
    "• \"cancelar\" (frena un apagado o una vigilancia)\n"
    "• cualquier comando de tu Lynx, tal como lo dirías en voz alta (\"abrí OBS\", \"playlist fortnite\")."
)


# ------------------------------------------------------------------ datos de la PC

class _EstadoEnergia(ctypes.Structure):
    _fields_ = [("ac", ctypes.c_ubyte), ("bandera", ctypes.c_ubyte), ("porcentaje", ctypes.c_ubyte),
                ("sistema", ctypes.c_ubyte), ("segundos", ctypes.c_uint32), ("segundos_total", ctypes.c_uint32)]


def bateria():
    """Texto con la batería, o None si no se pudo saber. Es 'PC de escritorio' si no tiene batería."""
    if sys.platform != "win32":
        return None
    try:
        estado = _EstadoEnergia()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(estado)):
            return None
    except Exception:
        return None
    if estado.bandera == 128 or estado.porcentaje == 255:
        return "Esta PC no tiene batería (o no la detecto)."
    enchufada = estado.ac == 1
    texto = f"Batería: {estado.porcentaje}%, " + ("enchufada" if enchufada else "usando batería")
    if not enchufada and estado.segundos != 0xFFFFFFFF:
        horas, minutos = divmod(estado.segundos // 60, 60)
        texto += f" (calculo ~{horas} h {minutos} min)" if horas else f" (calculo ~{minutos} min)"
    return texto + "."


def carpetas_de_descarga(config):
    carpetas = [c for c in (config.get("carpetas_descarga") or []) if c]
    return carpetas or [str(Path.home() / "Downloads")]


def descargas_activas(carpetas, ahora=None, activa_si=ACTIVA_SI_TOCADA_HACE):
    """[(nombre, tamaño, carpeta)] de los archivos temporales de descarga que crecieron hace poco."""
    ahora = ahora or time.time()
    encontradas = []
    for carpeta in carpetas:
        try:
            with os.scandir(carpeta) as it:
                for entrada in it:
                    if entrada.is_file() and entrada.name.lower().endswith(EXTENSIONES_DESCARGA):
                        info = entrada.stat()
                        if ahora - info.st_mtime <= activa_si:
                            encontradas.append((entrada.name, info.st_size, carpeta))
        except OSError:
            continue
    return encontradas


def tamano(bytes_):
    for unidad in ("B", "KB", "MB", "GB"):
        if bytes_ < 1024 or unidad == "GB":
            return f"{bytes_:.0f} {unidad}" if unidad == "B" else f"{bytes_:.1f} {unidad}"
        bytes_ /= 1024


def informe_descargas(carpetas, espera=4.0, dormir=time.sleep):
    """Dos mediciones separadas por unos segundos: tamaño actual y velocidad de cada descarga."""
    antes = {(n, c): t for n, t, c in descargas_activas(carpetas)}
    if not antes:
        return ("No veo ninguna descarga en curso en " + " / ".join(carpetas) + ".\n"
                "(Solo detecto descargas del navegador, yt-dlp y torrents que guardan ahí.)")
    dormir(espera)
    despues = {(n, c): t for n, t, c in descargas_activas(carpetas)}
    lineas = []
    for (nombre, carpeta), t in despues.items():
        velocidad = (t - antes.get((nombre, carpeta), t)) / espera
        nombre_corto = nombre if len(nombre) <= 45 else nombre[:42] + "..."
        lineas.append(f"• {nombre_corto}: {tamano(t)}" + (f" (+{tamano(velocidad)}/s)" if velocidad > 0 else " (parada)"))
    if not lineas:
        return "La descarga que había ya terminó o se detuvo."
    return ("Descargas en curso:\n" + "\n".join(lineas[:8]) +
            "\n\nNo puedo saber el porcentaje (el navegador no lo guarda), pero mirá si el tamaño sigue creciendo.")


def _correr(argumentos):
    subprocess.run(argumentos, capture_output=True, creationflags=SIN_VENTANA)


# ------------------------------------------------------------------ Telegram

def _llamar(token, metodo, datos=None, timeout=20):
    """Llama a la API de Telegram. Devuelve el 'result' o levanta RuntimeError (sin mostrar el token)."""
    url = f"https://api.telegram.org/bot{token}/{metodo}"
    cuerpo = urllib.parse.urlencode(datos or {}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=cuerpo), timeout=timeout) as r:
            respuesta = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            detalle = json.loads(error.read().decode("utf-8")).get("description", "")
        except Exception:
            detalle = ""
        raise RuntimeError(f"Telegram respondió {error.code}" + (f": {detalle}" if detalle else "")) from None
    except Exception as error:
        raise RuntimeError(str(error).replace(token, "***") or error.__class__.__name__) from None
    if not respuesta.get("ok"):
        raise RuntimeError(respuesta.get("description", "error de Telegram"))
    return respuesta.get("result")


def probar(token, usuario):
    """Para el botón 'Probar': verifica el token y, si hay ID, manda un mensaje. Devuelve un texto."""
    token = (token or "").strip()
    if not token:
        return "Falta pegar el token del bot."
    try:
        bot = _llamar(token, "getMe")
    except RuntimeError as error:
        return f"No pude conectar: {error}"
    nombre = bot.get("username", "tu bot")
    if not usuario:
        return f"El token es válido (@{nombre}). Ahora escribile \"hola\" a ese bot desde tu Telegram."
    try:
        _llamar(token, "sendMessage", {"chat_id": usuario, "text": "✅ Lynx conectado. Escribime \"ayuda\"."})
    except RuntimeError as error:
        return f"El token anda, pero no pude escribirte: {error}. ¿Le escribiste \"hola\" al bot antes?"
    return f"Todo bien: te mandé un mensaje desde @{nombre}."


class Remoto(threading.Thread):
    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self.parar = threading.Event()
        self.estado = "apagado"        # lo que muestra la pestaña del celular
        self.candidato = None          # (id, nombre) de quien le escribió al bot sin estar autorizado todavía
        self.pendiente = None          # algo que espera tu "sí"
        self.vigilancia = None         # {"apagar": bool, "desde": t, "ultimo_activo": t}
        self.apagado_programado = False
        self._offset = 0
        self._token = None
        self._avisado_intruso = False

    # --- configuración (siempre lee la configuración viva)

    @property
    def config(self):
        return self.app.config

    def _usuario(self):
        try:
            return int(self.config.get("telegram_usuario") or 0)
        except (TypeError, ValueError):
            return 0

    def _carpetas(self):
        return carpetas_de_descarga(self.config)

    # --- comunicación

    def enviar(self, texto):
        usuario, token = self._usuario(), (self.config.get("telegram_token") or "").strip()
        if not usuario or not token:
            return False
        try:
            for i in range(0, len(texto), 3800):
                _llamar(token, "sendMessage", {"chat_id": usuario, "text": texto[i:i + 3800]})
            return True
        except RuntimeError as error:
            nucleo.log("[telegram] no pude enviar:", error)
            return False

    def run(self):
        espera_error = 5
        while not self.parar.is_set():
            token = (self.config.get("telegram_token") or "").strip()
            if not self.config.get("telegram_activo") or not token:
                self.estado = "apagado"
                self._token = None
                self.parar.wait(1.0)
                continue
            if token != self._token:
                self._token, self._offset = token, 0
                self.estado = "conectando..."
            try:
                novedades = _llamar(token, "getUpdates",
                                    {"offset": self._offset, "timeout": 8, "allowed_updates": '["message"]'},
                                    timeout=20)
                self.estado = "conectado"
                espera_error = 5
                for novedad in novedades:
                    self._offset = max(self._offset, novedad["update_id"] + 1)
                    try:
                        self.procesar(novedad)
                    except Exception:
                        import traceback
                        nucleo.log("[telegram] error al procesar un mensaje:\n" + traceback.format_exc())
                self.vigilar()
            except RuntimeError as error:
                self.estado = f"sin conexión ({error})"
                self.parar.wait(espera_error)
                espera_error = min(espera_error * 2, 60)
            except Exception as error:
                nucleo.log("[telegram] error inesperado:", error)
                self.parar.wait(5)

    # --- mensajes entrantes

    def procesar(self, novedad):
        mensaje = novedad.get("message") or {}
        texto = (mensaje.get("text") or "").strip()
        quien = (mensaje.get("from") or {}).get("id")
        if not texto or quien is None:
            return
        if time.time() - mensaje.get("date", time.time()) > MENSAJE_VIEJO:
            nucleo.log("[telegram] ignoré un mensaje viejo")
            return
        autorizado = self._usuario()
        token = (self.config.get("telegram_token") or "").strip()
        if not autorizado:
            # Todavía no hay dueño: no se ejecuta nada; solo se anota quién escribió para que lo confirmes en Lynx.
            nombre = (mensaje.get("from") or {}).get("first_name", "")
            self.candidato = (quien, nombre)
            try:
                _llamar(token, "sendMessage", {"chat_id": quien,
                        "text": f"Hola {nombre}. Para que te obedezca, abrí Lynx > Celular y tocá \"Usar este ID\" "
                                f"(tu ID es {quien})."})
            except RuntimeError:
                pass
            return
        if quien != autorizado:
            if not self._avisado_intruso:
                nucleo.log("[telegram] alguien que no es el dueño le escribió al bot; lo ignoro")
                self._avisado_intruso = True
            return
        respuesta = self.responder(texto)
        if respuesta:
            self.enviar(respuesta)

    # --- qué hacer con lo que escribís

    def _motor(self):
        motor = self.app.motor
        return motor if motor is not None and motor.listo else None

    def estado_general(self):
        partes = [bateria() or "No pude leer la batería.", informe_descargas(self._carpetas(), espera=3.0)]
        if self.apagado_programado:
            partes.append("⚠️ Hay un apagado programado. Escribí \"cancelar\" para frenarlo.")
        if self.vigilancia:
            partes.append("👀 Estoy vigilando la descarga" +
                          (" y después apago la PC." if self.vigilancia["apagar"] else " para avisarte."))
        return "\n\n".join(partes)

    def responder(self, texto):
        t = nucleo.limpiar(texto.lower()).lstrip("/")
        palabras = t.split()
        if not palabras:
            return None

        # Algo esperaba tu respuesta
        if self.pendiente is not None:
            pendiente, self.pendiente = self.pendiente, None
            if palabras[0] in ("si", "dale", "ok", "okey", "confirmo", "obvio", "sip", "yes"):
                return self._confirmado(pendiente)
            if palabras[0] in ("no", "nop", "cancela", "cancelar"):
                return "Listo, no hice nada."

        if "cancel" in t or (len(palabras) <= 2 and palabras[0] in ("frena", "detene", "deten", "para", "no")):
            return self._cancelar()
        if t in ("start", "ayuda", "help", "hola", "menu") or t.startswith("que podes"):
            return AYUDA
        if "bateria" in t:
            return bateria() or "No pude leer la batería."

        habla_de_descarga = any(p in t for p in ("descarga", "bajando", "download"))
        cuando_termine = "cuando termin" in t or "cuando acab" in t or "cuando est" in t or "avisa" in t
        if cuando_termine and (habla_de_descarga or "apag" in t):
            return self._empezar_vigilancia(apagar="apag" in t)
        if "apag" in t:
            self.pendiente = ("apagar",)
            return f"¿Apago la PC? Respondé \"sí\" (se apaga en {SEGUNDOS_PARA_APAGAR} s y podés cancelar) o \"no\"."
        # Tus propios comandos van antes que las preguntas generales ("descarga musica" es un comando tuyo).
        motor = self._motor()
        if motor is not None:
            comando = nucleo.buscar_comando(t, motor.comandos)
            if comando is not None:
                if comando.get("confirmar"):
                    self.pendiente = ("comando", comando)
                    return f"\"{comando['frase']}\" pide confirmación. ¿La hago? (sí / no)"
                return self._hacer(comando)
        if habla_de_descarga or "cuanto va" in t or "progreso" in t:
            return informe_descargas(self._carpetas())
        if t in ("estado", "resumen", "como va todo", "todo bien") or t.startswith("como va"):
            return self.estado_general()
        if motor is None:
            return "Lynx todavía está arrancando. Probá de nuevo en un momento."
        return "No entendí eso. Escribí \"ayuda\" para ver qué puedo hacer."

    def _hacer(self, comando):
        motor = self._motor()
        if motor is None:
            return "Lynx todavía está arrancando. Probá de nuevo en un momento."
        respuesta = motor.ejecutar_remoto(comando)
        if respuesta is None:
            return "No pude confirmar que se hizo (tardó demasiado)."
        return "Hecho. " + respuesta if respuesta else "Hecho."

    def _confirmado(self, pendiente):
        if pendiente[0] == "apagar":
            return self._apagar("Apago la PC")
        return self._hacer(pendiente[1])

    def _apagar(self, prefijo):
        _correr(["shutdown", "/s", "/t", str(SEGUNDOS_PARA_APAGAR)])
        self.apagado_programado = True
        threading.Timer(SEGUNDOS_PARA_APAGAR + 10, lambda: setattr(self, "apagado_programado", False)).start()
        return f"{prefijo} en {SEGUNDOS_PARA_APAGAR} segundos. Escribí \"cancelar\" para frenarlo."

    def _cancelar(self):
        hecho = []
        if self.apagado_programado:
            _correr(["shutdown", "/a"])
            self.apagado_programado = False
            hecho.append("Cancelé el apagado.")
        if self.vigilancia:
            self.vigilancia = None
            hecho.append("Dejé de vigilar la descarga.")
        if self.pendiente:
            self.pendiente = None
        return " ".join(hecho) or "No hay nada para cancelar."

    # --- vigilar una descarga

    def _empezar_vigilancia(self, apagar):
        activas = descargas_activas(self._carpetas())
        if apagar and not activas:
            return ("No veo ninguna descarga en curso, así que no programo el apagado (para no apagarte la PC "
                    "por error). Cuando arranque la descarga, pedímelo de nuevo.")
        ahora = time.time()
        self.vigilancia = {"apagar": apagar, "desde": ahora, "ultimo_activo": ahora, "vio": bool(activas)}
        if activas:
            nombres = ", ".join(n for n, _, _ in activas[:3])
            texto = f"Dale, vigilo: {nombres}."
        else:
            texto = "Ahora no veo descargas en curso. Apenas arranque una y termine, te aviso."
        texto += (f" Cuando termine te aviso y apago la PC ({SEGUNDOS_PARA_APAGAR} s para cancelar)."
                  if apagar else " Cuando termine te aviso.")
        return texto

    def vigilar(self, ahora=None):
        v = self.vigilancia
        if not v:
            return
        ahora = ahora or time.time()
        if ahora - v["desde"] > VIGILANCIA_MAXIMA:
            self.vigilancia = None
            self.enviar("Dejé de vigilar la descarga (pasaron 12 horas).")
            return
        if descargas_activas(self._carpetas(), ahora, ACTIVA_SI_TOCADA_HACE):
            v["vio"], v["ultimo_activo"] = True, ahora
            return
        if v["vio"] and ahora - v["ultimo_activo"] >= TERMINA_SI_QUIETA_POR:
            self.vigilancia = None
            if v["apagar"]:
                self.enviar("✅ Terminó la descarga. " + self._apagar("Apago la PC"))
            else:
                self.enviar("✅ Terminó la descarga.")
