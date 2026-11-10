"""
Núcleo del asistente: rutas, registro (log), configuración, comandos y motor de voz.
No tiene ventanas: el motor corre en un hilo y la interfaz le pregunta su estado.
"""
import base64
import json
import math
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import traceback
from array import array
from pathlib import Path

from personajes import Personajes, escribir_lista, guion_voz_base


def carpeta_base():
    """Carpeta donde viven comandos.json, config.json, el modelo y el log (junto al .exe)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE = carpeta_base()
ARCHIVO_COMANDOS = BASE / "comandos.json"
ARCHIVO_COMANDOS_EJEMPLO = BASE / "comandos.ejemplo.json"
ARCHIVO_CONFIG = BASE / "config.json"
CARPETA_MODELO = BASE / "modelo-es"  # modelo de Vosk en español
ARCHIVO_LOG = BASE / "asistente.log"
RUTA_VOCES = BASE / "voces"  # voces naturales de Piper (.onnx + .onnx.json)
PREFIJO_NATURAL = "Natural: "

RATE = 16000
SIN_VENTANA = 0x08000000 if sys.platform == "win32" else 0  # evita que parpadee una consola

PALABRAS_DORMIR = ["gracias", "chau", "chao", "adios"]
PALABRAS_SI = ["si", "dale", "confirmo"]
PALABRAS_NO = ["no", "cancela", "cancelar"]

TILDES = str.maketrans("áéíóúü", "aeiouu")
CON_TILDE = {"a": "á", "e": "é", "i": "í", "o": "ó", "u": "ú"}


# ---------------------------------------------------------------- registro

_cerrojo_log = threading.Lock()


def log(*partes):
    linea = time.strftime("%H:%M:%S ") + " ".join(str(p) for p in partes)
    try:
        with _cerrojo_log, open(ARCHIVO_LOG, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except OSError:
        pass


def iniciar_log():
    try:
        if ARCHIVO_LOG.exists() and ARCHIVO_LOG.stat().st_size > 500_000:
            ARCHIVO_LOG.write_text("", encoding="utf-8")
    except OSError:
        pass
    log("---------------- inicio ----------------")


# ---------------------------------------------------------------- configuración

CONFIG_BASE = {
    "microfono": None,              # None = predeterminado de Windows; o el nombre del dispositivo
    "activacion": ["lynx", "links", "linx", "lince"],
    "mostrar_circulo": True,
    "tamano_circulo": 64,
    "responder_con_voz": True,
    "voz": None,                    # None = voz predeterminada de Windows; o el nombre de la voz
    "voz_velocidad": 170,
    "iniciar_con_windows": False,
    "salida_audio": None,           # None = salida predeterminada de Windows; o parte del nombre del dispositivo
    "voces_naturales": False,       # voces neuronales de Piper (suenan robóticas): apagadas
    "personaje": None,              # None = sin voz de personaje; o el nombre de la carpeta en "personajes"
    "personaje_tono": 0,            # semitonos: negativo = más grave (útil si la voz base es de mujer)
    "applio_dir": r"C:\Applio",    # dónde está instalado Applio (lo hace instalar_voz_personaje.bat)
}

# Lo que dice el asistente al ejecutar un comando que no tiene respuesta propia.
RESPUESTAS_POR_DEFECTO = {
    "abrir_programa": "Abriendo.",
    "abrir_web": "Abriendo.",
    "cerrar_programa": "Listo, lo cerré.",
    "cerrar_varios": "Listo, cerré los programas.",
    "apagar": "Apagando la PC.",
    "cambiar_salida": "Listo, ahora hablo por acá.",
}


# Frases fijas que dice el asistente (las de cada comando se suman aparte): se preparan con la voz de personaje.
FRASE_DE_PRUEBA = "Hola, así suena mi voz."
FRASES_FIJAS = [  # la de prueba va primera: se convierte antes y se puede escuchar enseguida
    FRASE_DE_PRUEBA, "Te escucho.", "Hasta luego.", "¿Confirmás?", "Cancelado.", "No entendí ese comando.",
    "No pude hacerlo. Revisá la ruta del comando.", "Todavía no sé hacer esa acción.",
    "No encuentro esa salida de audio.",
]

GESTOR = Personajes(BASE, log, SIN_VENTANA)  # voces de personaje: se comparte entre reinicios del motor


def cargar_config():
    cfg = dict(CONFIG_BASE)
    try:
        with open(ARCHIVO_CONFIG, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, json.JSONDecodeError):
        pass
    return cfg


def guardar_config(cfg):
    with open(ARCHIVO_CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def _clave_inicio():
    import winreg
    return winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                          r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                          winreg.KEY_SET_VALUE)


def comando_de_inicio():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --silencioso'
    pyw = Path(sys.executable).with_name("pythonw.exe")
    ejecutable = pyw if pyw.exists() else Path(sys.executable)
    return f'"{ejecutable}" "{Path(__file__).resolve().parent / "app.py"}" --silencioso'


def configurar_inicio_con_windows(activar):
    """Agrega o quita el asistente de los programas que arrancan con Windows (solo este usuario)."""
    import winreg
    clave = _clave_inicio()
    try:
        if activar:
            winreg.SetValueEx(clave, "AsistenteLynx", 0, winreg.REG_SZ, comando_de_inicio())
        else:
            try:
                winreg.DeleteValue(clave, "AsistenteLynx")
            except FileNotFoundError:
                pass
    finally:
        winreg.CloseKey(clave)


# ---------------------------------------------------------------- comandos

def leer_comandos():
    """Los comandos tal como están en el archivo (para editarlos en la ventana)."""
    try:
        with open(ARCHIVO_COMANDOS, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # Primera vez (por ejemplo, recién bajado de GitHub): se parte de los comandos de ejemplo.
        try:
            with open(ARCHIVO_COMANDOS_EJEMPLO, encoding="utf-8") as f:
                ejemplo = json.load(f)
            guardar_comandos(ejemplo)
            return ejemplo
        except (OSError, ValueError):
            return []


def guardar_comandos(comandos):
    with open(ARCHIVO_COMANDOS, "w", encoding="utf-8") as f:
        json.dump(comandos, f, ensure_ascii=False, indent=2)


def sin_tildes(texto):
    return texto.lower().translate(TILDES)


def limpiar(texto):
    """Minúsculas, sin tildes y sin las marcas [unk] ("no reconocido") del reconocedor."""
    return " ".join(p for p in sin_tildes(texto).split() if p != "[unk]")


def cargar_comandos():
    """Comandos listos para el motor: frases normalizadas y las más largas primero."""
    listos = []
    for c in leer_comandos():
        c = dict(c)
        c["frase"] = " ".join(sin_tildes(c["frase"]).split())
        listos.append(c)
    return sorted(listos, key=lambda c: len(c["frase"]), reverse=True)


def buscar_comando(texto, comandos):
    for cmd in comandos:
        if cmd["frase"] in texto:
            return cmd
    return None


# ---------------------------------------------------------------- micrófonos

def listar_microfonos():
    """[(índice, nombre)] de los micrófonos de la API de audio predeterminada de Windows."""
    import sounddevice as sd
    api = sd.query_hostapis(sd.default.hostapi)
    resultado = []
    for i in api["devices"]:
        d = sd.query_devices(i)
        if d["max_input_channels"] > 0:
            resultado.append((i, d["name"]))
    return resultado


def resolver_microfono(nombre):
    """Índice del micrófono con ese nombre, o None (= predeterminado de Windows)."""
    if not nombre:
        return None
    try:
        for indice, n in listar_microfonos():
            if n == nombre:
                return indice
    except Exception as error:
        log("No pude listar los micrófonos:", error)
    log(f"No encuentro el micrófono '{nombre}'; uso el predeterminado.")
    return None


# ---------------------------------------------------------------- salida de audio

def listar_salidas():
    """[(índice, nombre)] de los dispositivos de sonido (parlantes, auriculares) de Windows."""
    import sounddevice as sd
    api = sd.query_hostapis(sd.default.hostapi)
    resultado = []
    for i in api["devices"]:
        d = sd.query_devices(i)
        if d["max_output_channels"] > 0:
            resultado.append((i, d["name"]))
    return resultado


def _coincide(nombre, buscado):
    a, b = nombre.lower(), buscado.lower()
    return a in b or b in a


def resolver_salida(nombre):
    """Índice del dispositivo cuyo nombre contiene `nombre` (o al revés), o None."""
    if not nombre:
        return None
    try:
        for indice, n in listar_salidas():
            if _coincide(n, nombre):
                return indice
    except Exception as error:
        log("No pude listar las salidas de audio:", error)
    return None


def reproducir_wav(datos, salida=None):
    """Reproduce un WAV (bytes) y espera a que termine, por la salida elegida o la predeterminada."""
    if salida:
        try:
            import io
            import wave
            dispositivo = resolver_salida(salida)
            if dispositivo is not None:
                with wave.open(io.BytesIO(datos)) as w:
                    canales, ancho, tasa = w.getnchannels(), w.getsampwidth(), w.getframerate()
                    marcos = w.readframes(w.getnframes())
                if ancho == 2:
                    import sounddevice as sd
                    with sd.RawOutputStream(samplerate=tasa, channels=canales, dtype="int16",
                                            device=dispositivo) as flujo:
                        flujo.write(marcos)
                    return
            else:
                log(f"No encuentro la salida '{salida}'; uso la predeterminada.")
        except Exception as error:
            log("No pude usar la salida elegida; uso la predeterminada:", error)
    import winsound
    winsound.PlaySound(datos, winsound.SND_MEMORY)  # espera a que termine


# ---------------------------------------------------------------- vocabulario del modelo

def forma_en_modelo(modelo, palabra):
    """Cómo está escrita la palabra en el vocabulario del modelo (con o sin tilde), o None."""
    if not hasattr(modelo, "vosk_model_find_word"):
        return palabra  # no se puede comprobar: se usa tal cual
    candidatos = [palabra]
    for i, letra in enumerate(palabra):
        if letra in CON_TILDE:
            candidatos.append(palabra[:i] + CON_TILDE[letra] + palabra[i + 1:])
    for candidato in candidatos:
        if modelo.vosk_model_find_word(candidato) > 0:
            return candidato
    return None


def frase_en_modelo(modelo, frase):
    """(frase escrita como la conoce el modelo, lista de palabras que el modelo no conoce)"""
    formas, faltan = [], []
    for palabra in frase.split():
        forma = forma_en_modelo(modelo, palabra)
        (formas if forma else faltan).append(forma or palabra)
    return " ".join(formas), faltan


def crear_reconocedor(modelo, frases, silenciosas=(), avisos=None):
    """Reconocedor que solo puede devolver una de las frases dadas (o [unk])."""
    from vosk import KaldiRecognizer
    usables = []
    for frase, avisar in [(f, True) for f in frases] + [(f, False) for f in silenciosas]:
        escrita, faltan = frase_en_modelo(modelo, frase)
        if faltan:
            if avisar:
                mensaje = (f"No puedo escuchar '{frase}': el modelo no conoce "
                           f"{', '.join(faltan)}. Probá con otra palabra.")
                log("[aviso]", mensaje)
                if avisos is not None:
                    avisos.append(mensaje)
        else:
            usables.append(escrita)
    gramatica = json.dumps(usables + ["[unk]"], ensure_ascii=False)
    return KaldiRecognizer(modelo, RATE, gramatica), usables


_modelo = None


def obtener_modelo():
    """Carga el modelo una sola vez (tarda unos segundos)."""
    global _modelo
    if _modelo is None:
        from vosk import Model
        if not CARPETA_MODELO.exists():
            raise FileNotFoundError(f"Falta el modelo de voz en: {CARPETA_MODELO}")
        _modelo = Model(str(CARPETA_MODELO))
    return _modelo


# ---------------------------------------------------------------- voz de Windows

def _velocidad_sapi(palabras_por_minuto):
    """Palabras por minuto -> escala de la voz de Windows (-10 a 10, 0 = normal)."""
    return max(-10, min(10, round(math.log(max(50, palabras_por_minuto) / 200.0, 1.1))))


class VozWindows:
    """
    La voz de Windows (SAPI) usada directamente y de forma sincrónica: habla y recién devuelve
    el control cuando terminó. Más fiable que pyttsx3 dentro de un hilo, donde puede quedar muda.
    """
    nombre_motor = "SAPI"

    def __init__(self):
        try:
            import pythoncom
            import win32com.client
            pythoncom.CoInitialize()  # cada hilo necesita su propio COM
            self.tts = win32com.client.Dispatch("SAPI.SpVoice")
            self.nombre_motor = "SAPI (pywin32)"
        except Exception as error:
            log("pywin32 no disponible para la voz:", error)
            import comtypes
            import comtypes.client
            try:
                comtypes.CoInitialize()
            except OSError:
                pass  # ya estaba inicializado en este hilo
            self.tts = comtypes.client.CreateObject("SAPI.SpVoice")
            self.nombre_motor = "SAPI (comtypes)"
        self.tts.Volume = 100
        self._voces = self.tts.GetVoices()
        self._inicial = self.tts.Voice
        try:
            self._salida_inicial = self.tts.AudioOutput
        except Exception:
            self._salida_inicial = None

    def listar(self):
        return [self._voces.Item(i).GetDescription() for i in range(self._voces.Count)]

    def elegir(self, nombre):
        for i in range(self._voces.Count):
            voz = self._voces.Item(i)
            if voz.GetDescription() == nombre:
                self.tts.Voice = voz
                return True
        return False

    def predeterminada(self):
        self.tts.Voice = self._inicial

    def elegir_salida(self, nombre):
        """Dirige la voz a un dispositivo de sonido (None = el predeterminado). True si lo logró."""
        try:
            if not nombre:
                if self._salida_inicial is not None:
                    self.tts.AudioOutput = self._salida_inicial
                return True
            salidas = self.tts.GetAudioOutputs()
            for i in range(salidas.Count):
                if _coincide(salidas.Item(i).GetDescription(), nombre):
                    self.tts.AudioOutput = salidas.Item(i)
                    return True
        except Exception as error:
            log("No pude cambiar la salida de la voz de Windows:", error)
        return False

    def velocidad(self, palabras_por_minuto):
        self.tts.Rate = _velocidad_sapi(palabras_por_minuto)

    def decir(self, texto):
        self.tts.Speak(texto, 16)  # 16 = tratar como texto plano; sin "async": espera a terminar


class VozPowerShell:
    """Respaldo: habla con System.Speech a través de PowerShell (más lento, pero muy fiable)."""
    nombre_motor = "PowerShell"

    def __init__(self):
        if shutil.which("powershell") is None:
            raise FileNotFoundError("No encuentro PowerShell")
        self.nombre = None
        self.rate = 0

    def listar(self):
        return []

    def elegir(self, nombre):
        self.nombre = nombre
        return True

    def predeterminada(self):
        self.nombre = None

    def elegir_salida(self, nombre):
        return not nombre  # este respaldo solo sabe hablar por la salida predeterminada

    def velocidad(self, palabras_por_minuto):
        self.rate = _velocidad_sapi(palabras_por_minuto)

    def decir(self, texto):
        b64 = base64.b64encode(texto.encode("utf-8")).decode("ascii")
        seleccion = f"$s.SelectVoice('{self.nombre}');" if self.nombre else ""
        guion = ("Add-Type -AssemblyName System.Speech;"
                 "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                 f"{seleccion}$s.Rate={self.rate};"
                 f"$s.Speak([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{b64}')))")
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", guion],
                       capture_output=True, creationflags=SIN_VENTANA)


def voces_naturales():
    """Nombres ("Natural: es_MX-claude-high") de las voces de Piper que hay en la carpeta voces."""
    try:
        return [PREFIJO_NATURAL + p.stem for p in sorted(RUTA_VOCES.glob("*.onnx"))
                if (RUTA_VOCES / (p.name + ".json")).exists()]
    except OSError:
        return []


class VozPiper:
    """Voz neuronal local de Piper: suena mucho más natural que las voces de escritorio de Windows."""
    nombre_motor = "Piper"

    def __init__(self, ruta_onnx):
        from piper import PiperVoice  # solo existe si se instaló piper-tts
        self.voz = PiperVoice.load(str(ruta_onnx))
        self.escala = 1.0
        self.salida = None

    def velocidad(self, palabras_por_minuto):
        # Piper mide la duración, no la velocidad: más palabras por minuto = escala más chica.
        self.escala = max(0.6, min(1.6, 170.0 / max(80, palabras_por_minuto)))

    def _escribir(self, archivo, texto):
        if hasattr(self.voz, "synthesize_wav"):  # piper-tts 1.3 o más nuevo
            try:
                from piper.voice import SynthesisConfig
                config = SynthesisConfig(length_scale=self.escala)
            except Exception:
                config = None
            self.voz.synthesize_wav(texto, archivo, syn_config=config)
        else:  # versiones anteriores
            self.voz.synthesize(texto, archivo, length_scale=self.escala)

    def a_wav(self, texto, ruta):
        """Guarda la frase en un archivo WAV (la voz base para la voz de personaje)."""
        import wave
        with wave.open(str(ruta), "wb") as archivo:
            self._escribir(archivo, texto)

    def decir(self, texto):
        import io
        import wave
        memoria = io.BytesIO()
        with wave.open(memoria, "wb") as archivo:
            self._escribir(archivo, texto)
        reproducir_wav(memoria.getvalue(), self.salida)  # espera a que termine


# ---------------------------------------------------------------- motor de voz

class Motor(threading.Thread):
    """
    Escucha el micrófono y ejecuta comandos. Estados que expone en `estado`:
      dormido (esperando "Lynx"), escuchando (despierto), ejecutando, hablando, error.
    """

    def __init__(self, config):
        super().__init__(daemon=True, name="motor-de-voz")
        self.config = dict(config)
        self.parar = threading.Event()
        self.pausado = threading.Event()
        self.recargar = threading.Event()
        self.estado = "dormido"
        self.despierto = False
        self.nivel = 0.0
        self.avisos = []
        self.listo = False
        self.error = None
        self.voz = None              # voz de Windows (también es el respaldo)
        self.voz_activa = None       # la que realmente habla (Windows o Piper)
        self.naturales = {}          # voces de Piper ya cargadas
        self.aviso_voz = ""
        self.voces = []              # nombres de las voces instaladas en Windows
        self.prueba_voz = None       # (nombre, velocidad) pedida desde la ventana
        self.prueba_personaje = False
        self.callback_config = None  # la aplicación se entera si un comando cambia la configuración
        self.comandos = []
        self.reco_comandos = None
        self.cola_audio = queue.Queue()

    # --- utilidades

    def _estado_de_reposo(self):
        return "escuchando" if self.despierto else "dormido"

    def _medir(self, datos):
        muestras = array("h")
        muestras.frombytes(datos[: len(datos) - (len(datos) % 2)])
        if muestras:
            pico = max(max(muestras), -min(muestras))
            self.nivel = min(1.0, pico / 12000)

    def _callback(self, datos, frames, tiempo, estado):
        self.cola_audio.put(bytes(datos))

    def _vaciar_audio(self):
        while not self.cola_audio.empty():
            try:
                self.cola_audio.get_nowait()
            except queue.Empty:
                break

    def _decir(self, texto, personaje=True):
        self.estado = "hablando"
        antes = time.time()
        try:
            if personaje and self._decir_con_personaje(texto):
                pass
            else:
                self.voz_activa.decir(texto)
        except Exception as error:
            log("[error de voz]", error)
            if self.voz is not None and self.voz_activa is not self.voz:
                try:
                    self.voz.decir(texto)  # respaldo: la voz de Windows
                except Exception as error2:
                    log("[error de voz de respaldo]", error2)
        log(f"(habló durante {time.time() - antes:.1f} s)")
        # Descarta lo que el micrófono captó mientras hablaba, para no escucharse a sí mismo.
        self._vaciar_audio()
        self.estado = self._estado_de_reposo()

    def _voz_elegida(self):
        """La voz guardada en la configuración; las de Piper solo valen si están activadas."""
        voz = self.config.get("voz")
        if voz and voz.startswith(PREFIJO_NATURAL) and not self.config.get("voces_naturales"):
            return None
        return voz

    # --- voz de personaje

    def _voz_base_id(self):
        """Identifica la voz base: si cambia (otra voz o velocidad), hay que volver a generar."""
        return f"{self._voz_elegida() or 'predeterminada'}|{int(self.config.get('voz_velocidad', 170))}"

    def _reproducir_bytes(self, datos):
        reproducir_wav(datos, self.config.get("salida_audio"))

    def _aplicar_salida(self):
        """Dirige todas las voces (Windows, Piper y las de personaje) a la salida elegida."""
        salida = self.config.get("salida_audio") or None
        if self.voz is not None and hasattr(self.voz, "elegir_salida"):
            self.voz.elegir_salida(salida)
        for natural in self.naturales.values():
            natural.salida = salida

    def _decir_con_personaje(self, texto):
        """True si la frase estaba preparada y sonó con la voz del personaje."""
        personaje = self.config.get("personaje")
        if not personaje:
            return False
        try:
            return GESTOR.reproducir(personaje, texto, self._voz_base_id(),
                                     int(self.config.get("personaje_tono", 0)),
                                     reproductor=self._reproducir_bytes)
        except Exception as error:
            log("[error al reproducir la voz de personaje]", error)
            return False

    def frases_del_asistente(self):
        """Todo lo que el asistente puede llegar a decir (fijas + la respuesta de cada comando)."""
        frases = list(FRASES_FIJAS)
        for cmd in self.comandos:
            frase = (cmd.get("respuesta") or "").strip() or RESPUESTAS_POR_DEFECTO.get(cmd.get("tipo"), "Listo.")
            frases.append(frase)
        vistas, resultado = set(), []
        for f in frases:
            if f not in vistas:
                vistas.add(f)
                resultado.append(f)
        return resultado

    def _sintetizar_bases(self, pares):
        """Hace la voz base (la elegida en Windows o Piper) de cada frase, en archivos WAV."""
        voz = self._voz_elegida()
        if voz and voz.startswith(PREFIJO_NATURAL):
            natural = self._cargar_natural(voz)
            if natural is not None:
                natural.velocidad(int(self.config.get("voz_velocidad", 170)))
                for texto, ruta in pares:
                    natural.a_wav(texto, ruta)
                return
            voz = None
        lista = escribir_lista(pares)
        try:
            guion = guion_voz_base(lista, voz, _velocidad_sapi(int(self.config.get("voz_velocidad", 170))))
            resultado = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", guion],
                                       capture_output=True, creationflags=SIN_VENTANA, timeout=600)
            if resultado.returncode != 0:
                log("[voz base] PowerShell devolvió", resultado.returncode,
                    resultado.stderr.decode("utf-8", "replace")[-400:])
        finally:
            try:
                lista.unlink()
            except OSError:
                pass

    def preparar_personaje(self):
        """Si hay un personaje elegido, genera en segundo plano las frases que falten."""
        personaje = self.config.get("personaje")
        if not personaje or not self.config.get("responder_con_voz", True):
            return
        GESTOR.preparar(personaje, self.frases_del_asistente(), self._voz_base_id(),
                        int(self.config.get("personaje_tono", 0)),
                        self.config.get("applio_dir") or r"C:\Applio", self._sintetizar_bases)

    def probar_personaje(self):
        """Pedido desde la ventana: dice la frase de prueba con el personaje guardado."""
        self.prueba_personaje = True

    def hablar(self, texto):
        log("[asistente]", texto)
        if self.config.get("responder_con_voz", True) and self.voz_activa is not None:
            self._decir(texto)
        else:
            self.estado = self._estado_de_reposo()

    def _iniciar_voz(self):
        self.voz = None
        for motor_de_voz in (VozWindows, VozPowerShell):
            try:
                self.voz = motor_de_voz()
                break
            except Exception as error:
                log(f"No pude iniciar la voz con {motor_de_voz.__name__}:", error)
        nombres = []
        if self.voz is not None:
            try:
                nombres = self.voz.listar()
            except Exception as error:
                log("No pude listar las voces:", error)
        else:
            log("La voz de Windows no está disponible.")
        self.voces = nombres + (voces_naturales() if self.config.get("voces_naturales") else [])
        self.voz_activa = self.voz
        self._aplicar_voz(self._voz_elegida(), self.config.get("voz_velocidad", 170))
        self._aplicar_salida()
        log("Voz:", getattr(self.voz_activa, "nombre_motor", "ninguna"), "| voces disponibles:", self.voces)

    def _cargar_natural(self, nombre):
        if nombre in self.naturales:
            return self.naturales[nombre]
        ruta = RUTA_VOCES / (nombre[len(PREFIJO_NATURAL):] + ".onnx")
        try:
            voz = VozPiper(ruta)
        except Exception as error:
            log(f"No pude cargar la voz natural '{nombre}':", error)
            return None
        voz.salida = self.config.get("salida_audio") or None
        self.naturales[nombre] = voz
        log("Voz natural cargada:", nombre)
        return voz

    def _aplicar_voz(self, nombre, velocidad):
        """Elige la voz por su nombre (None = la predeterminada de Windows) y la velocidad."""
        self.aviso_voz = ""
        try:
            if nombre and nombre.startswith(PREFIJO_NATURAL):
                voz = self._cargar_natural(nombre)
                if voz is not None:
                    voz.velocidad(int(velocidad))
                    self.voz_activa = voz
                    return
                self.aviso_voz = f"No pude cargar la voz '{nombre}'; uso la de Windows."
            self.voz_activa = self.voz
            if self.voz is None:
                return
            self.voz.velocidad(int(velocidad))
            if nombre and not nombre.startswith(PREFIJO_NATURAL):
                if self.voz.elegir(nombre):
                    return
                log(f"No encuentro la voz '{nombre}'; uso la predeterminada.")
            self.voz.predeterminada()
        except Exception as error:
            log("[error de voz]", error)

    def probar_voz(self, nombre, velocidad):
        """Pedido desde la ventana: el motor lo atiende en su propio hilo, sin guardar nada."""
        self.prueba_voz = (nombre, velocidad)

    def _hacer_prueba_de_voz(self):
        nombre, velocidad = self.prueba_voz
        self.prueba_voz = None
        if self.voz_activa is None:
            return
        self._aplicar_voz(nombre, velocidad)
        self._decir(FRASE_DE_PRUEBA, personaje=False)
        self._aplicar_voz(self._voz_elegida(), self.config.get("voz_velocidad", 170))

    def _escuchar(self, reconocedor, segundos=8):
        """Espera una frase del reconocedor dado. Devuelve "" si pasa el tiempo."""
        reconocedor.Reset()
        limite = time.time() + segundos
        while time.time() < limite and not self.parar.is_set():
            try:
                datos = self.cola_audio.get(timeout=0.2)
            except queue.Empty:
                continue
            self._medir(datos)
            if reconocedor.AcceptWaveform(datos):
                return limpiar(json.loads(reconocedor.Result()).get("text", ""))
        return ""

    def _correr(self, argumentos):
        subprocess.run(argumentos, capture_output=True, creationflags=SIN_VENTANA)

    # --- acciones

    def _cerrar_procesos(self, procesos):
        for proceso in procesos:
            # Sin /F: le pide a cada programa que se cierre, así puede avisar si hay cambios sin guardar.
            self._correr(["taskkill", "/IM", proceso])

    def _ejecutar(self, cmd):
        tipo = cmd["tipo"]
        valor = cmd.get("valor", "")
        # Lo que dice al hacerlo: la respuesta propia del comando o la que corresponde al tipo.
        respuesta = (cmd.get("respuesta") or "").strip() or RESPUESTAS_POR_DEFECTO.get(tipo, "Listo.")
        self.estado = "ejecutando"
        if tipo in ("abrir_programa", "abrir_web"):
            os.startfile(os.path.expandvars(valor))
            time.sleep(0.4)
            self.hablar(respuesta)
        elif tipo == "cerrar_programa":
            self._cerrar_procesos([valor])
            self.hablar(respuesta)
        elif tipo == "cerrar_varios":
            self._cerrar_procesos(valor)
            self.hablar(respuesta)
        elif tipo == "cambiar_salida":
            try:
                existe = any(_coincide(nombre, valor) for _, nombre in listar_salidas())
            except Exception as error:
                log("No pude listar las salidas de audio:", error)
                existe = True
            if not existe:
                self.hablar("No encuentro esa salida de audio.")
                return
            self.config["salida_audio"] = valor or None
            self._aplicar_salida()
            if self.callback_config is not None:
                self.callback_config("salida_audio", valor or None)
            self.hablar(respuesta)  # ya sale por el dispositivo nuevo
        elif tipo == "apagar":
            self.hablar(respuesta)
            self._correr(["shutdown", "/s", "/t", "0"])
        else:
            self.hablar("Todavía no sé hacer esa acción.")

    def _procesar(self, texto, reco_confirmar):
        cmd = buscar_comando(texto, self.comandos)
        if cmd is None:
            self.hablar("No entendí ese comando.")
            return
        if cmd.get("confirmar"):
            self.hablar("¿Confirmás?")
            respuesta = self._escuchar(reco_confirmar)
            log("[confirmación]", repr(respuesta))
            if not (set(PALABRAS_SI) & set(respuesta.split())):
                self.hablar("Cancelado.")
                return
        try:
            self._ejecutar(cmd)
        except Exception as error:  # ruta mal puesta, programa inexistente, etc.
            log("[error al ejecutar]", error)
            self.hablar("No pude hacerlo. Revisá la ruta del comando.")
        self.estado = self._estado_de_reposo()

    def _preparar_comandos(self, modelo):
        try:
            comandos = cargar_comandos()
        except (json.JSONDecodeError, OSError) as error:
            log("[error] no pude leer comandos.json:", error)
            if self.reco_comandos is None:  # primera carga fallida: al menos que entienda "gracias"
                self.reco_comandos, _ = crear_reconocedor(modelo, [], silenciosas=PALABRAS_DORMIR)
            return
        avisos = []
        reconocedor, usables = crear_reconocedor(
            modelo, [c["frase"] for c in comandos], silenciosas=PALABRAS_DORMIR, avisos=avisos)
        self.comandos, self.reco_comandos, self.avisos = comandos, reconocedor, avisos
        log("Frases que entiendo:", usables)

    # --- hilo principal del motor

    def run(self):
        try:
            self._bucle_principal()
        except Exception:
            self.error = traceback.format_exc()
            self.estado = "error"
            log("ERROR en el motor:\n" + self.error)

    def _bucle_principal(self):
        import sounddevice as sd

        modelo = obtener_modelo()
        self._iniciar_voz()

        activacion = [sin_tildes(p.strip()) for p in self.config["activacion"] if p.strip()]
        reco_dormido, activables = crear_reconocedor(modelo, [], silenciosas=activacion)
        reco_confirmar, _ = crear_reconocedor(modelo, PALABRAS_SI + PALABRAS_NO)
        self._preparar_comandos(modelo)
        GESTOR.reintentar_fallidas()  # si algo falló antes, se vuelve a intentar al reiniciar
        self.preparar_personaje()
        if not activables:
            self.avisos.append("El modelo no conoce ninguna de las palabras de activación.")
            log("[aviso] ninguna palabra de activación es válida:", activacion)

        dispositivo = resolver_microfono(self.config.get("microfono"))
        log("Micrófono:", dispositivo if dispositivo is not None else "predeterminado")

        self.listo = True
        self.estado = "dormido"
        with sd.RawInputStream(samplerate=RATE, blocksize=2000, dtype="int16", channels=1,
                               device=dispositivo, callback=self._callback):
            log("Escuchando.")
            while not self.parar.is_set():
                try:
                    self._una_vuelta(modelo, reco_dormido, reco_confirmar, set(activacion))
                except Exception:
                    log("[error en la vuelta]\n" + traceback.format_exc())
        log("Motor detenido.")

    def _una_vuelta(self, modelo, reco_dormido, reco_confirmar, activacion):
        if self.recargar.is_set():
            self.recargar.clear()
            self._preparar_comandos(modelo)
            self.preparar_personaje()  # agregaste o cambiaste un comando: prepara solo lo nuevo
        if self.prueba_voz is not None:
            self._hacer_prueba_de_voz()
        if self.prueba_personaje:
            self.prueba_personaje = False
            if self.voz_activa is not None:
                self._decir(FRASE_DE_PRUEBA)

        try:
            datos = self.cola_audio.get(timeout=0.2)
        except queue.Empty:
            return
        self._medir(datos)

        if self.pausado.is_set():
            self.despierto = False
            self.estado = "dormido"
            return

        reconocedor = self.reco_comandos if self.despierto else reco_dormido
        if not reconocedor.AcceptWaveform(datos):
            return
        crudo = json.loads(reconocedor.Result()).get("text", "").strip()
        if not crudo:
            return
        texto = limpiar(crudo)
        if not texto:
            log("[oído] (no reconocido)")
            return
        log("[oído]", texto)
        palabras = set(texto.split())

        if not self.despierto:
            if palabras & activacion:
                self.despierto = True
                self.estado = "escuchando"
                self.reco_comandos.Reset()
                self.hablar("Te escucho.")
            return

        if palabras & set(PALABRAS_DORMIR):
            self.hablar("Hasta luego.")
            self.despierto = False
            reco_dormido.Reset()
            self.estado = "dormido"
            return

        self._procesar(texto, reco_confirmar)
