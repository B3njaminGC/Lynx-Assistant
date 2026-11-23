"""
Gestos de mano para Lynx (se usan con la cámara encendida, ver camara.py).

Cómo se usa:
  1. Mostrás la palma abierta, quieta, durante 1 segundo: Lynx queda "atento" unos segundos.
  2. Mientras está atento: deslizás la mano abierta (izquierda, derecha, arriba o abajo), o cerrás el puño.
  3. Lo que hace cada gesto depende de la aplicación que tengas adelante (navegador, reproductor, PowerPoint...).
     Si esa app no tiene el gesto, se usa el del escritorio.
  4. Deslizar hacia arriba abre el selector de aplicaciones (Vista de tareas de Windows, como las apps recientes
     del celular) en cualquier app: ahí deslizás para elegir y cerrás el puño para abrir la que marcaste.

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

GESTOS = ("deslizar_der", "deslizar_izq", "deslizar_arriba", "deslizar_abajo", "puño")

# "selector:abrir" abre el selector de aplicaciones (como las apps recientes del celular): ver Traductor.
PERFIL_GENERAL = {
    "deslizar_der": "cambiar_ventana",
    "deslizar_izq": "teclas:alt+shift+tab",
    "deslizar_arriba": "selector:abrir",
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


def tamaño_de_mano(puntos):
    """Largo de la palma (de la muñeca a la base del dedo medio): sirve de regla para medir cuánto se movió."""
    return _distancia(puntos[MUNECA], puntos[CENTRO])


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

    def __init__(self, segundos_para_activar=1.0, segundos_atento=6.0, factor_deslizar=1.0,
                 minimo_deslizar=0.08, ventana_deslizar=0.8, quieta=0.10, segundos_puño=0.3, enfriamiento=0.8,
                 segundos_rebote=1.2, espera_a_la_vista=0.5, margen_borde=0.25):
        self.segundos_para_activar = segundos_para_activar
        self.segundos_atento = segundos_atento
        # Cuánto hay que mover la mano: tantas veces su propio tamaño (así sirve un giro de muñeca de cerca
        # o un movimiento de todo el brazo de lejos), pero nunca menos que el mínimo.
        self.factor_deslizar = factor_deslizar
        self.minimo_deslizar = minimo_deslizar
        self.segundos_rebote = segundos_rebote      # al deslizar, el gesto contrario enseguida es la mano volviendo
        self.espera_a_la_vista = espera_a_la_vista  # una mano que recién entra a la imagen no cuenta todavía
        self.margen_borde = margen_borde            # una mano que se va por un borde mientras se mueve, ya deslizó
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
        self._a_la_vista_desde = None
        self._rebote_de = ("", 0.0)   # (gesto que no vale por ahora, hasta cuándo)

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
            if self.armado:
                gesto = self._salio_por_un_borde(ahora)
                if gesto:
                    self._dar(gesto, ahora, eventos)
            self._palma_desde = None
            self._a_la_vista_desde = None
            self._historial.clear()
            self._puño_desde, self._puño_dado = None, False
            return eventos
        if self._a_la_vista_desde is None:
            self._a_la_vista_desde = ahora
        if not self.armado:
            self._esperar_activacion(clase, centro_de_mano(puntos), ahora, eventos)
        else:
            self._buscar_gesto(clase, centro_de_mano(puntos), ahora, eventos, tamaño_de_mano(puntos))
        return eventos

    def _esperar_activacion(self, clase, centro, ahora, eventos):
        if clase != "palma":
            self._palma_desde = None
            return
        if self._palma_desde is None or _distancia(centro, self._ancla) > self.quieta:
            self._palma_desde, self._ancla = ahora, centro   # recién llegó o se movió: vuelve a contar
        elif ahora - self._palma_desde >= self.segundos_para_activar:
            a_la_vista = self._a_la_vista_desde   # la mano ya estaba ahí: no hay que esperar de nuevo
            self._reiniciar_todo()
            self._a_la_vista_desde = a_la_vista
            self.armado = True
            self._atento_hasta = ahora + self.segundos_atento
            eventos.append("activado")

    def _buscar_gesto(self, clase, centro, ahora, eventos, tamaño):
        libre = ahora - self._ultimo_gesto >= self.enfriamiento
        if clase != "puño":
            # Al deslizar rápido la mano se ve borrosa y a veces no se reconoce como palma perfecta: cuenta igual
            self._historial.append((ahora, centro[0], centro[1], tamaño))
            while self._historial and ahora - self._historial[0][0] > self.ventana_deslizar:
                self._historial.popleft()
            gesto = self._deslizo(ahora) if libre and self._ya_se_ve_un_rato(ahora) else None
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

    def _ya_se_ve_un_rato(self, ahora):
        return self._a_la_vista_desde is not None and ahora - self._a_la_vista_desde >= self.espera_a_la_vista

    def _medidas(self):
        xs = [x for _, x, _, _ in self._historial]
        ys = [y for _, _, y, _ in self._historial]
        tamaños = [t for _, _, _, t in self._historial]
        umbral = max(self.minimo_deslizar, self.factor_deslizar * sum(tamaños) / len(tamaños))
        x, y = xs[-1], ys[-1]
        derecha, izquierda = x - min(xs), max(xs) - x
        abajo, arriba = y - min(ys), max(ys) - y   # en la imagen "abajo" es y más grande
        return xs, ys, umbral, (derecha, izquierda, abajo, arriba)

    def _direccion(self, xs, ys, minimo, movimientos):
        """El gesto de un recorrido si es bastante largo (`minimo`) y casi derecho, o None."""
        derecha, izquierda, abajo, arriba = movimientos
        horizontal, vertical = max(derecha, izquierda), max(abajo, arriba)
        if horizontal >= minimo and horizontal >= vertical and (max(ys) - min(ys)) <= 0.8 * horizontal:
            return "deslizar_der" if derecha >= izquierda else "deslizar_izq"
        if vertical >= minimo and vertical > horizontal and (max(xs) - min(xs)) <= 0.8 * vertical:
            return "deslizar_abajo" if abajo >= arriba else "deslizar_arriba"
        return None

    def _deslizo(self, ahora):
        """Se movió de costado (o de arriba a abajo) lo suficiente en poco tiempo, y casi derecho."""
        if len(self._historial) < 3:
            return None
        xs, ys, umbral, movimientos = self._medidas()
        return self._sin_rebote(self._direccion(xs, ys, umbral, movimientos), ahora)

    def _salio_por_un_borde(self, ahora):
        """La mano se fue de la imagen por un borde yendo para ese lado (por ejemplo, subiste el brazo y salió por
        arriba): el gesto ya estaba hecho, aunque la cámara no llegue a ver el final."""
        if len(self._historial) < 3 or ahora - self._historial[-1][0] > 0.5:
            return None
        if ahora - self._ultimo_gesto < self.enfriamiento or not self._ya_se_ve_un_rato(self._historial[-1][0]):
            return None
        xs, ys, umbral, movimientos = self._medidas()
        gesto = self._direccion(xs, ys, umbral * 0.6, movimientos)
        x, y = xs[-1], ys[-1]
        cerca_del_borde = {"deslizar_arriba": y < self.margen_borde, "deslizar_abajo": y > 1 - self.margen_borde,
                           "deslizar_izq": x < self.margen_borde, "deslizar_der": x > 1 - self.margen_borde}
        return self._sin_rebote(gesto, ahora) if gesto and cerca_del_borde[gesto] else None

    def _sin_rebote(self, gesto, ahora):
        """Después de deslizar, la mano vuelve: ese movimiento contrario enseguida no es un gesto nuevo."""
        if gesto and gesto == self._rebote_de[0] and ahora < self._rebote_de[1]:
            return None
        return gesto

    def _dar(self, gesto, ahora, eventos):
        contrario = {"deslizar_der": "deslizar_izq", "deslizar_izq": "deslizar_der",
                     "deslizar_arriba": "deslizar_abajo", "deslizar_abajo": "deslizar_arriba"}.get(gesto)
        if contrario:
            self._rebote_de = (contrario, ahora + self.segundos_rebote)
        self._ultimo_gesto = ahora
        self._atento_hasta = ahora + self.segundos_atento   # cada gesto lo mantiene atento un rato más
        eventos.append(gesto)


# ------------------------------------------------------------------ el selector de aplicaciones

class Traductor:
    """
    Decide qué hacer con cada gesto. Casi siempre es lo que dice el perfil de la app (valor_de_gesto), salvo
    cuando está abierto el selector de aplicaciones, que funciona como las apps recientes del celular:
      deslizar hacia arriba   abre la Vista de tareas de Windows (todas las ventanas abiertas)
      deslizar en cualquier sentido    mueve la marca de una ventana a otra
      puño                    abre la ventana marcada
      pasar el tiempo sin tocar nada   cierra el selector (Esc)
    """

    def __init__(self):
        self.selector_abierto = False

    def valor(self, gesto, exe, config=None):
        """Lo que hay que hacer (como texto de valor_de_gesto), o '' si nada."""
        if self.selector_abierto:
            return self._en_el_selector(gesto)
        valor = valor_de_gesto(gesto, exe, config)
        if valor == "selector:abrir":
            self.selector_abierto = True
            return "teclas:win+tab"
        return valor

    def _en_el_selector(self, gesto):
        movimientos = {"deslizar_der": "derecha", "deslizar_izq": "izquierda",
                       "deslizar_arriba": "arriba", "deslizar_abajo": "abajo"}
        if gesto in movimientos:
            return "teclas:" + movimientos[gesto]
        if gesto == "puño":
            self.selector_abierto = False
            return "teclas:enter"
        if gesto == "desactivado":    # se cansó de esperar: lo cierra para no dejarte la pantalla tapada
            self.selector_abierto = False
            return "teclas:esc"
        return ""

    def reiniciar(self):
        self.selector_abierto = False


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
