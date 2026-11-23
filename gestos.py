"""
Gestos de mano para Lynx (se usan con la cámara encendida, ver camara.py).

Cómo se usa:
  1. Mostrás la palma abierta, quieta, durante 1 segundo: Lynx queda "atento" unos segundos.
  2. Mientras está atento: deslizás la mano abierta a la izquierda o a la derecha, o cerrás el puño.
  3. Lo que hace cada gesto depende de la aplicación que tengas adelante (navegador, reproductor, PowerPoint...).
     Si esa app no tiene el gesto, se usa el del escritorio.

Todo lo importante de acá es lógica pura (se prueba sin cámara ni Windows). Lo único que toca el exterior es
DetectorDeManos (MediaPipe, que encuentra los 21 puntos de la mano) y ventana_activa_exe (Windows).

Qué hace cada gesto se puede cambiar en config.json, clave "gestos":
    {"general": {"puño": "mostrar_escritorio"},
     "apps": {"chrome.exe": {"deslizar_der": "pestana_siguiente"}}}
Cada valor es una acción del catálogo (acciones_pc.py), "teclas:ctrl+tab" o "media:siguiente".
"""

import math
import os
import sys
import time
from collections import deque

# ------------------------------------------------------------------ qué hace cada gesto por defecto

GESTOS = ("deslizar_der", "deslizar_izq", "puño")

PERFIL_GENERAL = {
    "deslizar_der": "cambiar_ventana",
    "deslizar_izq": "teclas:alt+shift+tab",
    "puño": "mostrar_escritorio",
}

_NAVEGADOR = {"deslizar_der": "pestana_siguiente", "deslizar_izq": "pestana_anterior", "puño": "media:pausa"}
_REPRODUCTOR = {"deslizar_der": "media:siguiente", "deslizar_izq": "media:anterior", "puño": "media:pausa"}
_DIAPOSITIVAS = {"deslizar_der": "teclas:derecha", "deslizar_izq": "teclas:izquierda", "puño": "teclas:esc"}

PERFILES_POR_APP = {
    **{exe: _NAVEGADOR for exe in ("chrome.exe", "msedge.exe", "brave.exe", "firefox.exe", "opera.exe",
                                   "vivaldi.exe")},
    **{exe: _REPRODUCTOR for exe in ("spotify.exe", "vlc.exe", "wmplayer.exe", "musicbee.exe", "itunes.exe",
                                     "foobar2000.exe", "resonar.exe")},
    "powerpnt.exe": _DIAPOSITIVAS,
    "acrord32.exe": _DIAPOSITIVAS,
}


def valor_de_gesto(gesto, exe, config=None):
    """Qué hay que hacer con ese gesto estando `exe` adelante: tus cambios de config.json, el perfil de la app,
    o el del escritorio (en ese orden). Devuelve '' si no hay nada."""
    exe = (exe or "").lower()
    propios = (config or {}).get("gestos")
    if not isinstance(propios, dict):   # un config.json mal escrito no tiene que romper los gestos
        propios = {}
    apps = propios.get("apps") if isinstance(propios.get("apps"), dict) else {}
    por_app = {k.lower(): v for k, v in apps.items() if isinstance(v, dict)}
    for perfil in (por_app.get(exe), PERFILES_POR_APP.get(exe), propios.get("general"), PERFIL_GENERAL):
        if isinstance(perfil, dict) and perfil.get(gesto):
            return perfil[gesto]
    return ""


def ejecutar_valor(valor, acciones_pc_ejecutar, claves_de_acciones, pulsar, multimedia):
    """Hace lo que dice `valor`. Todo viene de afuera (para poder probarlo):
       acciones_pc_ejecutar(clave), claves_de_acciones (las claves válidas), pulsar(texto), multimedia(nombre).
    Devuelve True si hizo algo."""
    if not valor:
        return False
    if valor in claves_de_acciones:
        acciones_pc_ejecutar(valor)
    elif valor.startswith("teclas:"):
        pulsar(valor[len("teclas:"):])
    elif valor.startswith("media:"):
        multimedia(valor[len("media:"):])
    else:
        return False
    return True


# ------------------------------------------------------------------ entender la mano (21 puntos)

# Los 21 puntos de MediaPipe: 0 muñeca; por dedo: base, articulaciones y punta.
MUNECA = 0
DEDOS = ((6, 8), (10, 12), (14, 16), (18, 20))   # (segunda articulación, punta) de índice, medio, anular y meñique
CENTRO = 9                                       # base del dedo medio: queda más o menos en el centro de la palma


def _distancia(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def dedos_estirados(puntos):
    """Cuántos de los 4 dedos largos están estirados (la punta más lejos de la muñeca que la articulación)."""
    muneca = puntos[MUNECA]
    return sum(1 for articulacion, punta in DEDOS
               if _distancia(puntos[punta], muneca) > _distancia(puntos[articulacion], muneca) * 1.08)


def clasificar_mano(puntos):
    """'palma' (4 dedos estirados), 'puño' (ninguno) u 'otro'. `puntos` = 21 pares (x, y) entre 0 y 1."""
    if not puntos or len(puntos) < 21:
        return None
    estirados = dedos_estirados(puntos)
    if estirados == 4:
        return "palma"
    if estirados == 0:
        return "puño"
    return "otro"


def centro_de_mano(puntos):
    return puntos[CENTRO]


# ------------------------------------------------------------------ cuándo es un gesto

class Reconocedor:
    """
    Mira la mano cuadro a cuadro (`paso`) y avisa los gestos. Devuelve una lista de textos:
      'activado'       mostraste la palma quieta y Lynx quedó atento
      'desactivado'    pasó el tiempo atento sin hacer nada
      'deslizar_der' / 'deslizar_izq' / 'puño'
    Los gestos solo valen mientras está atento, así no se dispara nada por mover la mano de casualidad.
    "Derecha" es la derecha tuya (la imagen de la cámara va en espejo).
    """

    def __init__(self, segundos_para_activar=1.0, segundos_atento=6.0, distancia_deslizar=0.25,
                 ventana_deslizar=0.6, quieta=0.10, segundos_puño=0.3, enfriamiento=0.8):
        self.segundos_para_activar = segundos_para_activar
        self.segundos_atento = segundos_atento
        self.distancia_deslizar = distancia_deslizar
        self.ventana_deslizar = ventana_deslizar
        self.quieta = quieta
        self.segundos_puño = segundos_puño
        self.enfriamiento = enfriamiento
        self.armado = False
        self._reiniciar_todo()

    def _reiniciar_todo(self):
        self._palma_desde = None
        self._ancla = None
        self._historial = deque()
        self._puño_desde = None
        self._puño_dado = False
        self._atento_hasta = 0.0
        self._ultimo_gesto = -1e9

    def segundos_atento_restantes(self, ahora):
        return max(0.0, self._atento_hasta - ahora) if self.armado else 0.0

    def paso(self, puntos, ahora):
        eventos = []
        if self.armado and ahora >= self._atento_hasta:
            self.armado = False
            self._reiniciar_todo()
            eventos.append("desactivado")
        clase = clasificar_mano(puntos)
        if clase is None:   # no se ve la mano
            self._palma_desde = None
            self._historial.clear()
            self._puño_desde, self._puño_dado = None, False
            return eventos
        if not self.armado:
            self._esperar_activacion(clase, centro_de_mano(puntos), ahora, eventos)
        else:
            self._buscar_gesto(clase, centro_de_mano(puntos), ahora, eventos)
        return eventos

    def _esperar_activacion(self, clase, centro, ahora, eventos):
        if clase != "palma":
            self._palma_desde = None
            return
        if self._palma_desde is None or _distancia(centro, self._ancla) > self.quieta:
            self._palma_desde, self._ancla = ahora, centro   # recién llegó o se movió: vuelve a contar
        elif ahora - self._palma_desde >= self.segundos_para_activar:
            self._reiniciar_todo()
            self.armado = True
            self._atento_hasta = ahora + self.segundos_atento
            eventos.append("activado")

    def _buscar_gesto(self, clase, centro, ahora, eventos):
        libre = ahora - self._ultimo_gesto >= self.enfriamiento
        if clase == "palma":
            self._historial.append((ahora, centro[0], centro[1]))
            while self._historial and ahora - self._historial[0][0] > self.ventana_deslizar:
                self._historial.popleft()
            gesto = self._deslizo(centro) if libre else None
            if gesto:
                self._historial.clear()
                self._dar(gesto, ahora, eventos)
        else:
            self._historial.clear()
        if clase == "puño":
            if self._puño_desde is None:
                self._puño_desde = ahora
            elif not self._puño_dado and libre and ahora - self._puño_desde >= self.segundos_puño:
                self._puño_dado = True
                self._dar("puño", ahora, eventos)
        else:
            self._puño_desde, self._puño_dado = None, False

    def _deslizo(self, centro):
        if len(self._historial) < 3:
            return None
        _, x0, y0 = self._historial[0]
        dx, dy = centro[0] - x0, centro[1] - y0
        if abs(dx) >= self.distancia_deslizar and abs(dy) <= 0.6 * abs(dx):
            return "deslizar_der" if dx > 0 else "deslizar_izq"
        return None

    def _dar(self, gesto, ahora, eventos):
        self._ultimo_gesto = ahora
        self._atento_hasta = ahora + self.segundos_atento   # cada gesto lo mantiene atento un rato más
        eventos.append(gesto)


# ------------------------------------------------------------------ lo que toca el exterior

MOTIVO_FALLA = ""   # por qué no hay gestos (para mostrarlo en la ventanita y anotarlo en el registro)

# El modelo que reconoce manos (7 MB, oficial de Google). Se baja una sola vez y queda junto al programa.
NOMBRE_MODELO = "hand_landmarker.task"
URL_MODELO = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/"
              "float16/1/hand_landmarker.task")


def ruta_del_modelo():
    try:
        import nucleo
        carpeta = nucleo.BASE
    except Exception:
        carpeta = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(carpeta, NOMBRE_MODELO)


def _descargar(url, destino):
    import urllib.request
    with urllib.request.urlopen(url, timeout=60) as respuesta, open(destino, "wb") as archivo:
        archivo.write(respuesta.read())


def asegurar_modelo(ruta, descargar=_descargar):
    """Si el modelo de manos no está, lo baja (se hace una sola vez). Devuelve la ruta."""
    if os.path.exists(ruta) and os.path.getsize(ruta) > 1_000_000:
        return ruta
    temporal = ruta + ".descarga"
    try:
        descargar(URL_MODELO, temporal)
        if os.path.getsize(temporal) < 1_000_000:
            raise OSError("la descarga llegó incompleta")
        os.replace(temporal, ruta)
    except Exception as error:
        try:
            os.remove(temporal)
        except OSError:
            pass
        raise OSError(f"no pude bajar el modelo de manos ({error}); descargalo de {URL_MODELO} "
                      f"y ponelo en {os.path.dirname(ruta)}") from error
    return ruta


def mediapipe_disponible():
    global MOTIVO_FALLA
    try:
        import mediapipe as mp
        if not (hasattr(mp, "tasks") or hasattr(mp, "solutions")):
            raise ImportError("esta versión de mediapipe no trae el reconocedor de manos")
        return True
    except Exception as error:
        MOTIVO_FALLA = f"{type(error).__name__}: {error}"
        return False


class DetectorDeManos:
    """Encuentra los 21 puntos de una mano en una imagen RGB (MediaPipe, todo en tu PC, sin internet).
    Usa la interfaz nueva de MediaPipe (con el modelo hand_landmarker.task) y, si la versión es vieja, la anterior."""

    def __init__(self, ruta_modelo=None):
        import mediapipe as mp
        self._mp = mp
        self._tareas = self._manos = None
        self._t0 = time.monotonic()
        self._ultimo_ms = -1
        if hasattr(mp, "tasks"):
            ruta = asegurar_modelo(ruta_modelo or ruta_del_modelo())
            vision = mp.tasks.vision
            opciones = vision.HandLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=ruta),
                running_mode=vision.RunningMode.VIDEO, num_hands=1,
                min_hand_detection_confidence=0.6, min_hand_presence_confidence=0.5,
                min_tracking_confidence=0.5)
            self._tareas = vision.HandLandmarker.create_from_options(opciones)
        else:
            self._manos = mp.solutions.hands.Hands(
                static_image_mode=False, max_num_hands=1, model_complexity=0,
                min_detection_confidence=0.6, min_tracking_confidence=0.5)

    def buscar(self, rgb):
        if self._tareas is not None:
            import numpy as np
            imagen = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
            ms = max(int((time.monotonic() - self._t0) * 1000), self._ultimo_ms + 1)   # tiene que ir creciendo
            self._ultimo_ms = ms
            resultado = self._tareas.detect_for_video(imagen, ms)
            manos = resultado.hand_landmarks
            return [(p.x, p.y) for p in manos[0]] if manos else None
        resultado = self._manos.process(rgb)
        if not resultado.multi_hand_landmarks:
            return None
        return [(p.x, p.y) for p in resultado.multi_hand_landmarks[0].landmark]

    def cerrar(self):
        try:
            (self._tareas or self._manos).close()
        except Exception:
            pass


def detector_por_defecto():
    """Un detector de manos, o None si no se puede (la cámara sigue andando sin gestos; el motivo queda en MOTIVO_FALLA)."""
    global MOTIVO_FALLA
    if not mediapipe_disponible():
        return None
    try:
        return DetectorDeManos()
    except Exception as error:
        MOTIVO_FALLA = f"{type(error).__name__}: {error}"
        return None


def ventana_activa_exe():
    """Nombre del programa que tenés adelante (por ejemplo 'chrome.exe'), o '' si no se puede saber."""
    if sys.platform != "win32":
        return ""
    try:
        import ctypes
        from ctypes import wintypes
        usuario, kernel = ctypes.windll.user32, ctypes.windll.kernel32
        ventana = usuario.GetForegroundWindow()
        pid = wintypes.DWORD()
        usuario.GetWindowThreadProcessId(ventana, ctypes.byref(pid))
        proceso = kernel.OpenProcess(0x1000, False, pid.value)   # solo consultar
        if not proceso:
            return ""
        try:
            largo = wintypes.DWORD(520)
            texto = ctypes.create_unicode_buffer(520)
            if kernel.QueryFullProcessImageNameW(proceso, 0, texto, ctypes.byref(largo)):
                return os.path.basename(texto.value).lower()
            return ""
        finally:
            kernel.CloseHandle(proceso)
    except Exception:
        return ""
