"""
Cámara de Lynx: una ventanita con tu imagen que se enciende y se apaga con la voz.

Todo pasa en tu PC: no se graba nada, no se guarda ninguna imagen y no sale nada a internet.
Cada cuadro se mira y se descarta. Mientras la cámara está prendida, la luz de la laptop queda encendida.

Partes (cada una se prueba por separado):
  - Inactividad          cuenta el tiempo sin actividad para apagar la cámara sola.
  - hay_movimiento       dice si algo se movió entre dos cuadros.
  - Captura              hilo que lee la cámara y deja listo el último cuadro.
  - VentanaCamara        la ventanita (tkinter) con la imagen y el aviso de apagado.
  - ControlDeCamara      lo que usa la aplicación: encender, apagar, y vigilar el apagado automático.

"Actividad" (lo que evita que se apague sola): si hay gestos instalados, que se vea tu mano; si no, que
haya movimiento frente a la cámara. Los gestos (gestos.py) usan MediaPipe, que instala instalar_gestos.bat.

Necesita OpenCV (lo instala instalar_camara.bat). Sin OpenCV Lynx sigue funcionando igual: solo avisa
que falta para usar la cámara. Sin MediaPipe la cámara anda, pero sin gestos.
"""

import queue
import sys
import threading
import time

import gestos

ANCHO, ALTO = 320, 240       # tamaño de la imagen que se muestra (chico: gasta poco)
CUADROS_POR_SEGUNDO = 8      # alcanza para ver tu imagen y detectar movimiento
CUADROS_CON_GESTOS = 12      # con gestos hace falta un poco más para no perderse un deslizamiento
UMBRAL_CAMBIO = 25           # cuánto tiene que cambiar un punto (0 a 255) para contar como movimiento
FRACCION_MOVIMIENTO = 0.012  # qué parte de la imagen tiene que cambiar para contar como movimiento
MAXIMO_DE_CAMARAS = 5        # hasta qué número de cámara se busca


def _registrar(texto):
    try:
        import nucleo
        nucleo.log(texto)
    except Exception:
        pass


# ---------------------------------------------------------------- apagado por inactividad

class Inactividad:
    """Cuenta cuánto hace que no pasa nada. `reloj` se puede cambiar para probarlo sin esperar."""

    def __init__(self, minutos, reloj=time.monotonic):
        self.limite = max(0.1, float(minutos)) * 60
        self.reloj = reloj
        self.ultima = reloj()

    def hubo_actividad(self):
        self.ultima = self.reloj()

    def segundos_restantes(self):
        return max(0.0, self.limite - (self.reloj() - self.ultima))

    def vencio(self):
        return self.segundos_restantes() <= 0


def texto_de_cuenta_regresiva(segundos):
    """90 -> '1:30'."""
    segundos = max(0, int(segundos + 0.999))
    return f"{segundos // 60}:{segundos % 60:02d}"


# ---------------------------------------------------------------- detectar movimiento

def hay_movimiento(anterior, actual, umbral=UMBRAL_CAMBIO, fraccion=FRACCION_MOVIMIENTO):
    """Compara dos imágenes en gris del mismo tamaño (matrices de números 0-255)."""
    if anterior is None or actual is None or anterior.shape != actual.shape:
        return False
    import numpy as np
    diferencia = np.abs(anterior.astype(np.int16) - actual.astype(np.int16))
    return float((diferencia > umbral).mean()) > fraccion


def a_imagen_ppm(rgb_bytes, ancho, alto):
    """Arma una imagen PPM, que tkinter muestra sin necesitar ninguna librería extra."""
    return b"P6 %d %d 255\n" % (ancho, alto) + rgb_bytes


# ---------------------------------------------------------------- leer la cámara

def _abrir(indice):
    import cv2
    if sys.platform == "win32":
        return cv2.VideoCapture(indice, cv2.CAP_DSHOW)
    return cv2.VideoCapture(indice)


def opencv_disponible():
    try:
        import cv2  # noqa: F401
        import numpy  # noqa: F401
        return True
    except ImportError:
        return False


class Captura(threading.Thread):
    """Lee la cámara en segundo plano. Deja en `imagen` el último cuadro (PPM) y en `movimiento` si algo se movió."""

    def __init__(self, indice, abrir=_abrir, crear_detector=gestos.detector_por_defecto, config=None):
        super().__init__(daemon=True, name="camara")
        self.indice = indice
        self._abrir = abrir
        self._crear_detector = crear_detector
        self.config = config or {}
        self.parar = threading.Event()
        self.imagen = None
        self.movimiento = False
        self.actividad = False           # ¿hay alguien usando la cámara? (mano a la vista, o movimiento si no hay gestos)
        self.con_gestos = False          # ¿hay detector de manos andando?
        self.motivo_sin_gestos = ""      # si no, por qué (texto técnico, para que se pueda arreglar)
        self.atento = False              # los gestos están activados (mostraste la palma)
        self.segundos_atento = 0.0
        self.clase_mano = ""             # lo que ve ahora: palma, puño, otro o "" si no hay mano (para el panel de la ventana)
        self.fps = 0.0                   # cuántos cuadros por segundo está procesando de verdad
        self.eventos = queue.Queue()     # gestos detectados, para que la aplicación los atienda
        self.error = ""
        self.lista = threading.Event()   # ya abrió (o falló): la ventana puede mostrar algo

    def run(self):
        camara = None
        try:
            camara = self._abrir(self.indice)
            if camara is None or not camara.isOpened():
                self.error = "No pude abrir esa cámara. ¿La está usando otro programa?"
                return
            detector = self._crear_detector() if self.config.get("camara_gestos", True) else None
            self.con_gestos = detector is not None
            if detector is None and self.config.get("camara_gestos", True):
                self.motivo_sin_gestos = gestos.MOTIVO_FALLA or "no hay detector de manos"
                _registrar("[gestos] no hay gestos: " + self.motivo_sin_gestos)
            try:
                self._leer_en_bucle(camara, detector)
            finally:
                if detector is not None:
                    detector.cerrar()
        except Exception as error:
            self.error = f"Falló la cámara: {error}"
        finally:
            self.lista.set()
            if camara is not None:
                try:
                    camara.release()
                except Exception:
                    pass

    def _leer_en_bucle(self, camara, detector=None):
        import cv2
        espera = 1.0 / (CUADROS_CON_GESTOS if detector is not None else CUADROS_POR_SEGUNDO)
        reconocedor = gestos.Reconocedor(segundos_atento=float(self.config.get("gestos_segundos_atento", 6) or 6))
        anterior = None
        fallos = 0
        while not self.parar.is_set():
            empezo = time.monotonic()
            ok, cuadro = camara.read()
            if not ok or cuadro is None:
                fallos += 1
                if fallos > 20:
                    self.error = "La cámara dejó de mandar imagen."
                    return
                time.sleep(0.1)
                continue
            fallos = 0
            cuadro = cv2.flip(cv2.resize(cuadro, (ANCHO, ALTO)), 1)   # como un espejo
            gris = cv2.GaussianBlur(cv2.resize(cv2.cvtColor(cuadro, cv2.COLOR_BGR2GRAY), (64, 48)), (5, 5), 0)
            self.movimiento = hay_movimiento(anterior, gris)
            anterior = gris
            rgb = cv2.cvtColor(cuadro, cv2.COLOR_BGR2RGB)
            puntos = None
            if detector is not None:
                puntos = detector.buscar(rgb)
                for gesto in reconocedor.paso(puntos, time.monotonic()):
                    self.eventos.put(gesto)
                self.clase_mano = gestos.clasificar_mano(puntos) or ""
                self.atento = reconocedor.armado
                self.segundos_atento = reconocedor.segundos_atento_restantes(time.monotonic())
            self.actividad = (puntos is not None) if detector is not None else self.movimiento
            self._dibujar(cv2, rgb, puntos)
            self.imagen = a_imagen_ppm(rgb.tobytes(), ANCHO, ALTO)
            self.lista.set()
            duracion = time.monotonic() - empezo
            self.fps = 0.9 * self.fps + 0.1 / max(duracion, espera) if self.fps else 1 / max(duracion, espera)
            resto = espera - duracion
            if resto > 0:
                time.sleep(resto)

    def _dibujar(self, cv2, rgb, puntos):
        """Marco verde = te veo; marco azul = gestos activados. Puntitos sobre la mano si se ve."""
        if self.atento:
            cv2.rectangle(rgb, (2, 2), (ANCHO - 3, ALTO - 3), (70, 140, 255), 4)
        elif self.actividad:
            cv2.rectangle(rgb, (2, 2), (ANCHO - 3, ALTO - 3), (80, 220, 80), 3)
        for punto in puntos or ():
            cv2.circle(rgb, (int(punto[0] * ANCHO), int(punto[1] * ALTO)), 3, (255, 255, 255), -1)


# ---------------------------------------------------------------- la ventanita

class VentanaCamara:
    """Ventana chica, siempre encima, con la imagen de la cámara. Cerrarla apaga la cámara."""

    def __init__(self, raiz, al_cerrar, al_cambiar_camara, indice):
        import tkinter as tk
        self.tk = tk
        self.raiz = raiz
        self.ventana = tk.Toplevel(raiz)
        self.ventana.title("Lynx · Cámara")
        self.ventana.attributes("-topmost", True)
        self.ventana.resizable(False, False)
        self.ventana.protocol("WM_DELETE_WINDOW", al_cerrar)
        self.cuadro = tk.Label(self.ventana, bg="black", width=ANCHO, height=ALTO,
                               text="Abriendo la cámara…", fg="white", compound="center")
        self.cuadro.pack()
        self.linea_detalle = tk.Label(self.ventana, text="", anchor="w", font=("Consolas", 8), fg="#666666")
        self.linea_detalle.pack(fill="x", padx=6)
        pie = tk.Frame(self.ventana)
        pie.pack(fill="x")
        self.aviso = tk.Label(pie, text="", anchor="w", font=("Segoe UI", 9))
        self.aviso.pack(side="left", padx=6, pady=3)
        self.boton = tk.Button(pie, text=f"Otra cámara ({indice})", command=al_cambiar_camara)
        self.boton.pack(side="right", padx=6, pady=3)
        self._foto = None
        self._ubicar()

    def _ubicar(self):
        """Abajo a la derecha, para que no tape lo que estás haciendo."""
        self.ventana.update_idletasks()
        x = self.ventana.winfo_screenwidth() - ANCHO - 40
        y = self.ventana.winfo_screenheight() - ALTO - 120
        self.ventana.geometry(f"+{max(0, x)}+{max(0, y)}")

    def mostrar(self, imagen_ppm):
        if imagen_ppm is None:
            return
        self._foto = self.tk.PhotoImage(data=imagen_ppm)   # hay que guardarla o tkinter la borra
        self.cuadro.configure(image=self._foto, text="", width=ANCHO, height=ALTO)

    def texto(self, texto):
        self.aviso.configure(text=texto)

    def detalle(self, texto):
        self.linea_detalle.configure(text=texto)

    def mantener_visible(self):
        """"Mostrar el escritorio" minimiza todo, la cámara incluida: la vuelve a mostrar enseguida, así
        siempre podés ver si te detecta."""
        try:
            if self.ventana.state() == "iconic":
                self.ventana.deiconify()
                self.ventana.attributes("-topmost", True)
                self.ventana.lift()
        except Exception:
            pass

    def poner_numero(self, indice):
        self.boton.configure(text=f"Otra cámara ({indice})")

    def mensaje(self, texto):
        self.cuadro.configure(image="", text=texto, wraplength=ANCHO - 20, width=40, height=15)

    def cerrar(self):
        try:
            self.ventana.destroy()
        except Exception:
            pass


# ---------------------------------------------------------------- lo que usa la aplicación

class ControlDeCamara:
    """
    Enciende y apaga la cámara. La aplicación lo llama así:
        control.encender() / control.apagar() / control.alternar()
        control.vigilar()          cada décima de segundo (dibuja y apaga si pasó el tiempo)
    `al_apagar(motivo)` avisa a la aplicación ("voz", "ventana", "inactividad", "error").
    """

    def __init__(self, raiz, config, guardar_config, al_apagar=None, crear_ventana=VentanaCamara,
                 crear_captura=Captura, reloj=time.monotonic, al_gesto=None):
        self.raiz = raiz
        self.config = config
        self.guardar_config = guardar_config
        self.al_apagar = al_apagar or (lambda motivo: None)
        self.al_gesto = al_gesto or (lambda gesto: None)   # se llama con cada gesto detectado
        self.crear_ventana = crear_ventana
        self.crear_captura = crear_captura
        self.reloj = reloj
        self.captura = None
        self.ventana = None
        self.inactividad = None
        self.ultimo_cuadro = None
        self.ultimo_gesto = ""

    @property
    def encendida(self):
        return self.captura is not None

    def indice(self):
        try:
            return max(0, int(self.config.get("camara_indice", 0)))
        except (TypeError, ValueError):
            return 0

    def encender(self):
        """Devuelve '' si salió bien, o un texto con lo que falta."""
        if self.encendida:
            return ""
        if not opencv_disponible():
            return "Falta instalar OpenCV. Ejecutá instalar_camara.bat y probá de nuevo."
        self.inactividad = Inactividad(self.config.get("camara_apagar_min", 2), self.reloj)
        self.captura = self._nueva_captura(self.indice())
        self.captura.start()
        self.ventana = self.crear_ventana(self.raiz, self.apagar_por_ventana, self.cambiar_de_camara, self.indice())
        return ""

    def _nueva_captura(self, indice):
        try:
            return self.crear_captura(indice, config=self.config)
        except TypeError:   # una captura de prueba que no recibe la configuración
            return self.crear_captura(indice)

    def apagar(self, motivo="voz"):
        if not self.encendida:
            return
        self.captura.parar.set()
        self.captura = None
        if self.ventana is not None:
            self.ventana.cerrar()
            self.ventana = None
        self.ultimo_cuadro = None
        self.al_apagar(motivo)

    def apagar_por_ventana(self):
        self.apagar("ventana")

    def alternar(self):
        if self.encendida:
            self.apagar("voz")
            return ""
        return self.encender()

    def cambiar_de_camara(self):
        """Pasa a la cámara siguiente (0, 1, 2…) y vuelve a 0 después de la última."""
        siguiente = (self.indice() + 1) % MAXIMO_DE_CAMARAS
        self.config["camara_indice"] = siguiente
        try:
            self.guardar_config(self.config)
        except OSError:
            pass
        if self.encendida:
            self.captura.parar.set()
            self.captura = self._nueva_captura(siguiente)
            self.captura.start()
            self.ultimo_cuadro = None
            self.inactividad.hubo_actividad()
            if self.ventana is not None:
                self.ventana.poner_numero(siguiente)

    def vigilar(self):
        """Se llama seguido: muestra el último cuadro y apaga la cámara si pasó el tiempo sin actividad."""
        if not self.encendida:
            return
        captura = self.captura
        if captura.error:
            if self.ventana is not None:
                self.ventana.mensaje(captura.error)
            if not self.inactividad.vencio():   # deja el error a la vista un rato y después apaga
                if self.ventana is not None:
                    self.ventana.texto("Probá con «Otra cámara»")
                return
            self.apagar("error")
            return
        if captura.actividad:
            self.inactividad.hubo_actividad()
        self._atender_gestos(captura)
        if self.inactividad.vencio():
            self.apagar("inactividad")
            return
        if captura.imagen is not None and captura.imagen is not self.ultimo_cuadro:
            self.ultimo_cuadro = captura.imagen
            if self.ventana is not None:
                self.ventana.mostrar(captura.imagen)
        if self.ventana is not None:
            self.ventana.texto(self._texto_de_estado(captura))
            detalle = getattr(self.ventana, "detalle", None)
            if detalle is not None and getattr(captura, "con_gestos", False):
                mano = captura.clase_mano or "no veo la mano"
                detalle(f"mano: {mano} · {captura.fps:.0f} cuadros/s")
            mantener = getattr(self.ventana, "mantener_visible", None)
            if mantener is not None:
                mantener()

    def _atender_gestos(self, captura):
        eventos = getattr(captura, "eventos", None)
        if eventos is None:
            return
        try:
            while True:
                gesto = eventos.get_nowait()
                self.inactividad.hubo_actividad()
                self.ultimo_gesto = gesto
                self.al_gesto(gesto)
        except queue.Empty:
            pass

    def _texto_de_estado(self, captura):
        cuenta = texto_de_cuenta_regresiva(self.inactividad.segundos_restantes())
        if not getattr(captura, "con_gestos", False):
            quiere_gestos = self.config.get("camara_gestos", True)
            if quiere_gestos and captura.lista.is_set():   # ya abrió y no hay detector de manos
                motivo = (getattr(captura, "motivo_sin_gestos", "") or "")[:70]
                return f"Sin gestos: {motivo} · se apaga en {cuenta}" if motivo else f"Sin gestos · se apaga en {cuenta}"
            return f"Se apaga sola en {cuenta}"
        if getattr(captura, "atento", False):
            return f"ATENTO: deslizá o cerrá el puño ({int(captura.segundos_atento + 0.99)} s)" + self._ultimo()
        return f"Palma quieta 1 s para activar · se apaga en {cuenta}" + self._ultimo()

    def _ultimo(self):
        """El último gesto que entendió, para que veas qué está detectando."""
        nombres = {"deslizar_der": "→", "deslizar_izq": "←", "puño": "puño", "activado": "activado"}
        return f" · último: {nombres.get(self.ultimo_gesto, self.ultimo_gesto)}" if self.ultimo_gesto else ""
