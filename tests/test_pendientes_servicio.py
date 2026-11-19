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
        self.respuestas = []      # lo que "dictás" cuando Lynx pregunta (en orden)
        self.dice_si = True

    def escuchar_libre(self):
        return self.respuestas.pop(0) if self.respuestas else ""

    def confirmar_si_no(self):
        return self.dice_si

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


def test_todas_las_frases_de_la_gramatica_se_interpretan():
    for frase in pendientes_voz.FRASES_FIJAS_DE_VOZ:
        assert pendientes_voz.interpretar(frase) is not None, frase


def textos(motor):
    return [t for _, t in motor.dicho]


def test_agregar_con_texto_en_la_misma_frase(tmp_path):
    motor, lista, reloj, serv = armar(tmp_path)
    assert serv.atender("agrega pendiente comprar pan")
    assert [i["texto"] for i in lista.abiertos()] == ["comprar pan"]
    assert "Anotado." in textos(motor)


def test_agregar_sin_texto_pregunta_y_dicta(tmp_path):
    motor, lista, reloj, serv = armar(tmp_path)
    motor.respuestas = ["llamar al medico"]
    serv.atender("agrega un pendiente")
    assert "¿Qué anoto?" in textos(motor)
    assert lista.abiertos()[0]["texto"] == "llamar al medico"


def test_agregar_sin_texto_y_sin_dictado_no_anota(tmp_path):
    motor, lista, reloj, serv = armar(tmp_path)
    serv.atender("agrega un pendiente")
    assert lista.abiertos() == []
    assert "No te escuché." in textos(motor)


def test_agregar_repetido_avisa(tmp_path):
    motor, lista, reloj, serv = armar(tmp_path, ["comprar pan"])
    serv.atender("agrega pendiente comprar pan")
    assert "Ya lo tenías anotado." in textos(motor)
    assert len(lista.abiertos()) == 1


def test_terminar_por_texto(tmp_path):
    motor, lista, reloj, serv = armar(tmp_path, ["comprar pan", "llamar al medico"])
    serv.atender("termine comprar pan")
    assert [i["texto"] for i in lista.abiertos()] == ["llamar al medico"]


def test_terminar_por_numero_despues_de_leer(tmp_path):
    motor, lista, reloj, serv = armar(tmp_path, ["comprar pan", "llamar al medico"])
    serv.atender("que tengo pendiente")
    serv.atender("termine el dos")
    assert [i["texto"] for i in lista.abiertos()] == ["comprar pan"]


def test_terminar_que_no_existe_no_toca_nada(tmp_path):
    motor, lista, reloj, serv = armar(tmp_path, ["comprar pan"])
    serv.atender("termine sacar la basura")
    assert len(lista.abiertos()) == 1
    assert "No encontré ese pendiente." in textos(motor)


def test_terminar_con_dudas_pregunta_cual(tmp_path):
    motor, lista, reloj, serv = armar(tmp_path, ["llamar a Juan", "llamar a Pedro"])
    motor.respuestas = ["el dos"]
    serv.atender("termine llamar")
    assert [i["texto"] for i in lista.abiertos()] == ["llamar a Juan"]
    assert "Hay varios parecidos. ¿Cuál?" in textos(motor)


def test_terminar_con_dudas_sin_respuesta_no_toca_nada(tmp_path):
    motor, lista, reloj, serv = armar(tmp_path, ["llamar a Juan", "llamar a Pedro"])
    serv.atender("termine llamar")
    assert len(lista.abiertos()) == 2
    assert "No pude decidir, no toqué nada." in textos(motor)


def test_terminar_sin_texto_pregunta(tmp_path):
    motor, lista, reloj, serv = armar(tmp_path, ["comprar pan"])
    motor.respuestas = ["comprar pan"]
    serv.atender("termine un pendiente")
    assert lista.abiertos() == []


def test_borrar_pide_confirmacion(tmp_path):
    motor, lista, reloj, serv = armar(tmp_path, ["comprar pan"])
    motor.dice_si = False
    serv.atender("borra pendiente comprar pan")
    assert len(lista.abiertos()) == 1
    assert "Cancelado." in textos(motor)
    motor.dice_si = True
    serv.atender("borra pendiente comprar pan")
    assert lista.abiertos() == [] and lista.items == []


def test_por_celular_no_pregunta_si_falta_el_texto(tmp_path):
    motor, lista, reloj, serv = armar(tmp_path)
    motor.mudo = True
    serv.atender("agrega un pendiente")
    assert lista.abiertos() == []
    assert any("mismo mensaje" in t for t in textos(motor))


def test_las_frases_de_la_gramatica_se_entienden():
    acciones = {"que tengo pendiente": "listar", "agrega un pendiente": "agregar", "termine un pendiente": "terminar",
                "borra un pendiente": "borrar", "termine el tres": "terminar", "borra el pendiente cinco": "borrar"}
    for frase, accion in acciones.items():
        assert frase in pendientes_voz.FRASES_FIJAS_DE_VOZ
        assert pendientes_voz.interpretar(frase).accion == accion


def test_posponer_con_tiempo_en_la_frase(tmp_path):
    hora = datetime(2026, 1, 1, 8, 0)
    motor, lista, reloj, serv = armar(tmp_path, ["comprar pan", "llamar al medico"], ahora=lambda: hora)
    serv.atender("pospone comprar pan una hora")
    assert [i["texto"] for i in lista.para_leer()] == ["llamar al medico"]
    assert lista.por_id(1)["posponer_hasta"].startswith("2026-01-01T09:00")


def test_posponer_pregunta_cuanto_tiempo(tmp_path):
    hora = datetime(2026, 1, 1, 8, 0)
    motor, lista, reloj, serv = armar(tmp_path, ["comprar pan"], ahora=lambda: hora)
    motor.respuestas = ["media hora"]
    serv.atender("pospone comprar pan")
    assert "¿Por cuánto tiempo?" in textos(motor)
    assert lista.por_id(1)["posponer_hasta"].startswith("2026-01-01T08:30")


def test_posponer_sin_entender_el_tiempo_no_toca_nada(tmp_path):
    motor, lista, reloj, serv = armar(tmp_path, ["comprar pan"])
    motor.respuestas = ["cualquier cosa"]
    serv.atender("pospone comprar pan")
    assert lista.por_id(1)["posponer_hasta"] is None


def test_insiste_cada_tantos_minutos(tmp_path):
    motor, lista, reloj, serv = armar(tmp_path, ["a"], {"pendientes_insistir": True, "pendientes_cada_min": 10})
    reloj.t = 10
    serv.a_su_hora()                      # lectura al arrancar
    antes = len(motor.dicho)
    reloj.t = 10 + 9 * 60
    serv.a_su_hora()
    assert len(motor.dicho) == antes      # todavía no pasaron 10 minutos
    reloj.t = 10 + 10 * 60 + 1
    serv.a_su_hora()
    assert len(motor.dicho) > antes


def test_no_insiste_si_esta_apagado_o_si_ya_no_hay(tmp_path):
    motor, lista, reloj, serv = armar(tmp_path, ["a"])
    reloj.t = 10
    serv.a_su_hora()
    antes = len(motor.dicho)
    reloj.t = 10_000
    serv.a_su_hora()
    assert len(motor.dicho) == antes
    motor.config.update({"pendientes_insistir": True, "pendientes_cada_min": 5})
    lista.marcar_hecho(1)
    reloj.t = 20_000
    serv.a_su_hora()
    assert len(motor.dicho) == antes


def test_insistir_no_habla_si_esta_despierto(tmp_path):
    motor, lista, reloj, serv = armar(tmp_path, ["a"], {"pendientes_insistir": True, "pendientes_cada_min": 5})
    reloj.t = 10
    serv.a_su_hora()
    antes = len(motor.dicho)
    motor.despierto = True
    reloj.t = 5000
    serv.a_su_hora()
    assert len(motor.dicho) == antes


def test_pospuesto_no_se_insiste_hasta_que_vence(tmp_path):
    hora = [datetime(2026, 1, 1, 8, 0)]
    motor, lista, reloj, serv = armar(tmp_path, ["comprar pan"], {"pendientes_insistir": True, "pendientes_cada_min": 5},
                                      ahora=lambda: hora[0])
    serv.atender("pospone comprar pan dos horas")
    antes = len(motor.dicho)
    reloj.t = 600
    serv.a_su_hora()
    assert len(motor.dicho) == antes          # pospuesto: calla
    hora[0] += timedelta(hours=3)
    reloj.t = 1200
    serv.a_su_hora()
    assert len(motor.dicho) > antes           # ya venció: vuelve a avisar
