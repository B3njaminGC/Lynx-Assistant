"""Pruebas de la lectura de pendientes (con un motor de juguete, sin audio)."""
import threading
from datetime import datetime, timedelta

import pendientes_servicio
import pendientes_voz
from pendientes import Pendientes


class MotorFalso:
    def __init__(self, config=None):
        self.config = config or {}
        self.despierto = False
        self.mudo = False
        self.pausado = threading.Event()
        self.voz_activa = object()
        self.dicho = []

    def hablar(self, texto):
        self.dicho.append(("fija", texto))

    def hablar_pendiente(self, texto):
        self.dicho.append(("item", texto))


class Reloj:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def armar(tmp_path, textos=(), config=None, ahora=None):
    lista = Pendientes(tmp_path / "p.json", ahora=ahora or datetime.now)
    for t in textos:
        lista.agregar(t)
    motor = MotorFalso(config)
    reloj = Reloj()
    return motor, lista, reloj, pendientes_servicio.Servicio(motor, lista, reloj)


def test_frases_de_lectura_numeradas():
    items = [{"texto": "comprar pan"}, {"texto": "llamar a Juan"}]
    frases = pendientes_voz.frases_de_lectura(items)
    assert frases[0] == ("fija", "Tenés estos pendientes.")
    assert frases[1] == ("item", "Uno, comprar pan.")
    assert frases[2] == ("item", "Dos, llamar a Juan.")


def test_un_solo_pendiente_y_ninguno():
    assert pendientes_voz.frases_de_lectura([{"texto": "x"}])[0] == ("fija", "Tenés un pendiente.")
    assert pendientes_voz.frases_de_lectura([]) == [("fija", "No tenés pendientes.")]


def test_mas_de_cinco_dice_cuantos_faltan():
    items = [{"texto": f"t{i}"} for i in range(8)]
    frases = pendientes_voz.frases_de_lectura(items)
    assert len([f for f in frases if f[0] == "item"]) == 6
    assert frases[-1] == ("item", "Y 3 más.")


def test_espera_antes_de_leer_y_lee_una_sola_vez(tmp_path):
    motor, lista, reloj, serv = armar(tmp_path, ["comprar pan"])
    serv.a_su_hora()
    assert motor.dicho == []
    reloj.t = 10
    serv.a_su_hora()
    assert ("item", "Uno, comprar pan.") not in motor.dicho   # con uno solo no se numera
    assert ("item", "comprar pan.") in motor.dicho
    cantidad = len(motor.dicho)
    serv.a_su_hora()
    assert len(motor.dicho) == cantidad


def test_sin_pendientes_al_arrancar_no_dice_nada(tmp_path):
    motor, lista, reloj, serv = armar(tmp_path)
    reloj.t = 10
    serv.a_su_hora()
    assert motor.dicho == []


def test_no_habla_si_esta_despierto_o_pausado(tmp_path):
    motor, lista, reloj, serv = armar(tmp_path, ["a"])
    reloj.t = 10
    motor.despierto = True
    serv.a_su_hora()
    assert motor.dicho == []
    motor.despierto = False
    motor.pausado.set()
    serv.a_su_hora()
    assert motor.dicho == []
    motor.pausado.clear()
    serv.a_su_hora()
    assert motor.dicho


def test_desactivado_en_la_configuracion(tmp_path):
    motor, lista, reloj, serv = armar(tmp_path, ["a"], {"pendientes_al_arrancar": False})
    reloj.t = 10
    serv.a_su_hora()
    assert motor.dicho == []


def test_no_repite_si_lynx_se_reinicia_enseguida(tmp_path):
    motor, lista, reloj, serv = armar(tmp_path, ["a"])
    reloj.t = 10
    serv.a_su_hora()
    motor2 = MotorFalso()
    serv2 = pendientes_servicio.Servicio(motor2, Pendientes(tmp_path / "p.json"), reloj)
    reloj.t = 20
    serv2.a_su_hora()
    assert motor2.dicho == []


def test_vuelve_a_leer_pasado_el_tiempo(tmp_path):
    hora = [datetime(2026, 1, 1, 8, 0)]
    motor, lista, reloj, serv = armar(tmp_path, ["a"], ahora=lambda: hora[0])
    reloj.t = 10
    serv.a_su_hora()
    hora[0] += timedelta(minutes=11)
    motor2 = MotorFalso()
    serv2 = pendientes_servicio.Servicio(motor2, Pendientes(tmp_path / "p.json", ahora=lambda: hora[0]), reloj)
    reloj.t = 30
    serv2.a_su_hora()
    assert motor2.dicho


def test_orden_que_tengo_pendiente(tmp_path):
    motor, lista, reloj, serv = armar(tmp_path, ["a", "b"])
    assert serv.reconoce("que tengo pendiente")
    assert serv.atender("lynx que tengo pendiente")
    assert motor.dicho[0] == ("fija", "Tenés estos pendientes.")


def test_orden_que_no_es_de_pendientes(tmp_path):
    motor, lista, reloj, serv = armar(tmp_path, ["a"])
    assert not serv.atender("abri youtube")
    assert motor.dicho == []


def test_pedido_explicito_sin_pendientes_avisa(tmp_path):
    motor, lista, reloj, serv = armar(tmp_path)
    serv.atender("que tengo pendiente")
    assert motor.dicho == [("fija", "No tenés pendientes.")]


def test_frases_de_la_gramatica_se_interpretan_como_listar():
    for frase in pendientes_voz.FRASES_FIJAS_DE_VOZ:
        orden = pendientes_voz.interpretar(frase)
        assert orden is not None and orden.accion == "listar", frase
