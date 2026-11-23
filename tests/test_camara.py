"""Pruebas de la cámara: el apagado por inactividad, el movimiento y el encendido/apagado (sin cámara real)."""

import queue
import threading

import numpy as np

import acciones_pc
import camara


class Reloj:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class CapturaFalsa:
    def __init__(self, indice):
        self.indice = indice
        self.parar = type("E", (), {"set": lambda s: setattr(self, "parada", True)})()
        self.parada = False
        self.imagen = None
        self.movimiento = False
        self.actividad = False
        self.con_gestos = True
        self.atento = False
        self.segundos_atento = 0.0
        self.eventos = queue.Queue()
        self.lista = threading.Event()
        self.error = ""
        self.empezo = False

    def start(self):
        self.empezo = True


class VentanaFalsa:
    def __init__(self, raiz, al_cerrar, al_cambiar, indice):
        self.al_cerrar, self.al_cambiar, self.indice = al_cerrar, al_cambiar, indice
        self.cerrada = False
        self.cuadros, self.textos, self.mensajes = [], [], []

    def mostrar(self, imagen):
        self.cuadros.append(imagen)

    def texto(self, t):
        self.textos.append(t)

    def mensaje(self, t):
        self.mensajes.append(t)

    def poner_numero(self, n):
        self.indice = n

    def cerrar(self):
        self.cerrada = True


def armar(config=None, minutos=2):
    reloj = Reloj()
    config = config if config is not None else {"camara_indice": 0, "camara_apagar_min": minutos}
    guardados, apagados = [], []
    control = camara.ControlDeCamara(None, config, lambda c: guardados.append(dict(c)), apagados.append,
                                     crear_ventana=VentanaFalsa, crear_captura=CapturaFalsa, reloj=reloj)
    return control, reloj, guardados, apagados


def con_opencv(monkeypatch):
    monkeypatch.setattr(camara, "opencv_disponible", lambda: True)


# ---------------------------------------------------------------- piezas sueltas

def test_inactividad_vence_y_se_renueva():
    reloj = Reloj()
    i = camara.Inactividad(2, reloj)
    assert not i.vencio() and i.segundos_restantes() == 120
    reloj.t += 119
    assert not i.vencio()
    i.hubo_actividad()
    reloj.t += 119
    assert not i.vencio()
    reloj.t += 2
    assert i.vencio() and i.segundos_restantes() == 0


def test_cuenta_regresiva_en_texto():
    assert camara.texto_de_cuenta_regresiva(90) == "1:30"
    assert camara.texto_de_cuenta_regresiva(59.2) == "1:00"
    assert camara.texto_de_cuenta_regresiva(0) == "0:00"
    assert camara.texto_de_cuenta_regresiva(-5) == "0:00"


def test_movimiento_entre_dos_imagenes():
    quieta = np.full((48, 64), 100, dtype=np.uint8)
    assert not camara.hay_movimiento(quieta, quieta.copy())
    ruido = quieta.copy() + 3     # una variación mínima de luz no cuenta
    assert not camara.hay_movimiento(quieta, ruido)
    movida = quieta.copy()
    movida[10:30, 20:50] = 220    # una mano que cruza
    assert camara.hay_movimiento(quieta, movida)
    assert not camara.hay_movimiento(None, movida)
    assert not camara.hay_movimiento(quieta, np.zeros((10, 10), dtype=np.uint8))


def test_imagen_ppm():
    datos = camara.a_imagen_ppm(b"\x00" * 12, 2, 2)
    assert datos.startswith(b"P6 2 2 255\n") and len(datos) == len(b"P6 2 2 255\n") + 12


# ---------------------------------------------------------------- encender y apagar

def test_sin_opencv_avisa_y_no_enciende(monkeypatch):
    monkeypatch.setattr(camara, "opencv_disponible", lambda: False)
    control, *_ = armar()
    assert "OpenCV" in control.encender()
    assert not control.encendida


def test_encender_abre_ventana_y_captura(monkeypatch):
    con_opencv(monkeypatch)
    control, *_ = armar()
    assert control.encender() == ""
    assert control.encendida and control.captura.empezo and control.captura.indice == 0
    assert control.encender() == ""   # encender dos veces no abre otra cámara


def test_apagar_cierra_todo_y_avisa_el_motivo(monkeypatch):
    con_opencv(monkeypatch)
    control, _, _, apagados = armar()
    control.encender()
    captura, ventana = control.captura, control.ventana
    control.apagar("voz")
    assert not control.encendida and captura.parada and ventana.cerrada
    assert apagados == ["voz"]
    control.apagar("voz")      # ya apagada: no hace nada
    assert apagados == ["voz"]


def test_cerrar_la_ventana_apaga(monkeypatch):
    con_opencv(monkeypatch)
    control, _, _, apagados = armar()
    control.encender()
    control.ventana.al_cerrar()
    assert not control.encendida and apagados == ["ventana"]


def test_alternar(monkeypatch):
    con_opencv(monkeypatch)
    control, *_ = armar()
    control.alternar()
    assert control.encendida
    control.alternar()
    assert not control.encendida


# ---------------------------------------------------------------- vigilar

def test_se_apaga_sola_sin_movimiento(monkeypatch):
    con_opencv(monkeypatch)
    control, reloj, _, apagados = armar(minutos=2)
    control.encender()
    reloj.t += 60
    control.vigilar()
    assert control.encendida
    reloj.t += 61
    control.vigilar()
    assert not control.encendida and apagados == ["inactividad"]


def test_el_movimiento_mantiene_la_camara(monkeypatch):
    con_opencv(monkeypatch)
    control, reloj, _, apagados = armar(minutos=2)
    control.encender()
    for _ in range(5):
        reloj.t += 100
        control.captura.actividad = True
        control.vigilar()
    assert control.encendida and not apagados


def test_muestra_cada_cuadro_nuevo_una_sola_vez(monkeypatch):
    con_opencv(monkeypatch)
    control, *_ = armar()
    control.encender()
    control.captura.imagen = b"cuadro1"
    control.vigilar()
    control.vigilar()
    control.captura.imagen = b"cuadro2"
    control.vigilar()
    assert control.ventana.cuadros == [b"cuadro1", b"cuadro2"]
    assert "se apaga en " in control.ventana.textos[-1]


def test_error_de_camara_se_muestra_y_despues_apaga(monkeypatch):
    con_opencv(monkeypatch)
    control, reloj, _, apagados = armar(minutos=1)
    control.encender()
    control.captura.error = "No pude abrir esa cámara."
    control.vigilar()
    assert control.encendida and control.ventana.mensajes == ["No pude abrir esa cámara."]
    reloj.t += 61
    control.vigilar()
    assert not control.encendida and apagados == ["error"]


# ---------------------------------------------------------------- elegir cámara

def test_cambiar_de_camara_guarda_y_reabre(monkeypatch):
    con_opencv(monkeypatch)
    control, _, guardados, _ = armar()
    control.encender()
    primera = control.captura
    control.cambiar_de_camara()
    assert primera.parada and control.captura.indice == 1 and control.captura.empezo
    assert control.ventana.indice == 1
    assert guardados[-1]["camara_indice"] == 1


def test_la_camara_vuelve_a_cero_despues_de_la_ultima(monkeypatch):
    control, *_ = armar({"camara_indice": camara.MAXIMO_DE_CAMARAS - 1})
    control.cambiar_de_camara()
    assert control.indice() == 0


def test_indice_roto_en_la_config_no_rompe():
    control, *_ = armar({"camara_indice": "x"})
    assert control.indice() == 0


# ---------------------------------------------------------------- acciones de voz

def entorno_de_juguete(resultado=""):
    dichas, pedidos = [], []

    def camara_pedida(encender):
        pedidos.append(encender)
        return resultado
    return acciones_pc.Entorno(dichas.append, camara=camara_pedida), dichas, pedidos


def test_accion_encender_la_camara():
    entorno, dichas, pedidos = entorno_de_juguete()
    assert acciones_pc.ejecutar("camara_encender", entorno)
    assert pedidos == [True] and dichas == ["Cámara activada."]


def test_accion_encender_cuando_no_se_puede_dice_por_que():
    entorno, dichas, pedidos = entorno_de_juguete("Falta instalar OpenCV.")
    acciones_pc.ejecutar("camara_encender", entorno)
    assert dichas == ["Falta instalar OpenCV."]


def test_accion_apagar_la_camara():
    entorno, dichas, pedidos = entorno_de_juguete()
    acciones_pc.ejecutar("camara_apagar", entorno)
    assert pedidos == [False] and dichas == ["Cámara apagada."]


# ---------------------------------------------------------------- la lectura real (con una cámara de juguete)

class CamaraDeJuguete:
    def __init__(self, abierta=True, cuadros=None):
        self.abierta, self.cuadros, self.liberada = abierta, cuadros, False
        self.n = 0

    def isOpened(self):
        return self.abierta

    def read(self):
        self.n += 1
        brillo = 20 if self.n % 2 else 230   # cambia fuerte entre cuadros: cuenta como movimiento
        return True, np.full((480, 640, 3), brillo, dtype=np.uint8)

    def release(self):
        self.liberada = True


def test_captura_lee_cuadros_y_libera_la_camara():
    import pytest
    pytest.importorskip("cv2")
    juguete = CamaraDeJuguete()
    c = camara.Captura(0, abrir=lambda i: juguete)
    c.start()
    assert c.lista.wait(3)
    for _ in range(50):
        if c.movimiento:
            break
        c.lista.wait(0.05)
        import time
        time.sleep(0.05)
    c.parar.set()
    c.join(3)
    assert c.imagen.startswith(b"P6 320 240 255\n") and not c.error
    assert c.movimiento and juguete.liberada


def test_captura_si_no_abre_dice_por_que():
    c = camara.Captura(3, abrir=lambda i: CamaraDeJuguete(abierta=False))
    c.start()
    c.join(3)
    assert "No pude abrir" in c.error and c.lista.is_set()


# ---------------------------------------------------------------- gestos desde la cámara

def test_un_gesto_llega_a_la_aplicacion_y_cuenta_como_actividad(monkeypatch):
    con_opencv(monkeypatch)
    recibidos = []
    reloj = Reloj()
    control = camara.ControlDeCamara(None, {"camara_apagar_min": 2}, lambda c: None, None,
                                     crear_ventana=VentanaFalsa, crear_captura=CapturaFalsa, reloj=reloj,
                                     al_gesto=recibidos.append)
    control.encender()
    reloj.t += 100
    control.captura.eventos.put("deslizar_der")
    control.vigilar()
    assert recibidos == ["deslizar_der"]
    reloj.t += 100      # sin el gesto ya habría vencido (200 s > 120 s)
    control.vigilar()
    assert control.encendida


def test_texto_de_estado_segun_los_gestos(monkeypatch):
    con_opencv(monkeypatch)
    control, *_ = armar()
    control.encender()
    control.vigilar()
    assert "Palma quieta" in control.ventana.textos[-1]
    control.captura.atento, control.captura.segundos_atento = True, 4.2
    control.vigilar()
    assert control.ventana.textos[-1].startswith("ATENTO") and "5 s" in control.ventana.textos[-1]
    control.captura.con_gestos, control.captura.atento = False, False
    control.captura.lista.set()
    control.vigilar()
    assert control.ventana.textos[-1].startswith("Sin gestos")
    control.config["camara_gestos"] = False   # si los apagaste vos, no insiste con instalarlos
    control.vigilar()
    assert "Sin gestos" not in control.ventana.textos[-1]


def test_muestra_el_ultimo_gesto_entendido(monkeypatch):
    con_opencv(monkeypatch)
    control, *_ = armar()
    control.encender()
    control.captura.eventos.put("deslizar_izq")
    control.vigilar()
    assert control.ventana.textos[-1].endswith("último: ←")
