"""
El puente entre los pendientes y Lynx: decide cuándo leerlos y atiende las órdenes de voz.

Trabaja con un "motor" que solo tiene que ofrecer lo que se ve acá abajo, así que se prueba con uno de juguete:
    motor.config                 los ajustes (un diccionario)
    motor.despierto / .mudo      si está atento a una orden / si habla solo por el celular
    motor.pausado                un Event: puesto = Lynx está pausado
    motor.voz_activa             algo (no None) si hay voz disponible
    motor.hablar(texto)          frase de Lynx (puede sonar con la voz de personaje)
    motor.hablar_pendiente(txt)  texto tuyo (se dice con una voz de Windows)
"""
import time

import pendientes_voz

ESPERA_AL_ARRANCAR = 5          # segundos que espera antes de leerlos: que Windows termine de arrancar el audio
MINUTOS_ENTRE_LECTURAS = 10     # si Lynx se reinicia, no los vuelve a leer antes de esto
ORDENES_QUE_ATIENDE = {"listar"}


class Servicio:
    def __init__(self, motor, lista, reloj=time.monotonic):
        self.motor = motor
        self.lista = lista
        self.reloj = reloj
        self.inicio = reloj()
        self.leidos_al_arrancar = False
        self.ultima_lista = []     # lo último que se leyó, en ese orden: a eso se refiere "el dos"

    # ---------------------------------------------------------- al arrancar
    def a_su_hora(self):
        """Se llama en cada vuelta del motor. Lee los pendientes una vez, cuando llega el momento."""
        if self.leidos_al_arrancar or not self._puede_hablar():
            return
        if self.reloj() - self.inicio < ESPERA_AL_ARRANCAR:
            return
        self.leidos_al_arrancar = True
        if not self.motor.config.get("pendientes_al_arrancar", True):
            return
        minutos = self.lista.minutos_desde_la_lectura()
        if minutos is not None and minutos < MINUTOS_ENTRE_LECTURAS:
            return
        self.lista.limpiar_hechos_viejos()
        self.leer(avisar_si_no_hay=False)

    def _puede_hablar(self):
        m = self.motor
        return not (m.despierto or m.mudo or m.pausado.is_set()) and m.voz_activa is not None

    # ---------------------------------------------------------- leer
    def leer(self, avisar_si_no_hay=True):
        """Dice los pendientes. Si no hay ninguno, solo avisa cuando se lo pediste vos."""
        items = self.lista.para_leer()
        self.ultima_lista = items
        if not items and not avisar_si_no_hay:
            return
        for tipo, texto in pendientes_voz.frases_de_lectura(items):
            if tipo == "fija":
                self.motor.hablar(texto)
            else:
                self.motor.hablar_pendiente(texto)
        if items:
            self.lista.marcar_lectura()

    # ---------------------------------------------------------- órdenes de voz
    def reconoce(self, texto):
        """¿Es una orden de pendientes que sabemos atender?"""
        orden = pendientes_voz.interpretar(texto)
        return orden is not None and orden.accion in ORDENES_QUE_ATIENDE

    def atender(self, texto):
        """Cumple la orden si es de pendientes. Devuelve True si la atendió."""
        orden = pendientes_voz.interpretar(texto)
        if orden is None or orden.accion not in ORDENES_QUE_ATIENDE:
            return False
        if orden.accion == "listar":
            self.leer()
        return True
