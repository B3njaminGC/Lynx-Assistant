"""Pruebas del catálogo de acciones de la PC (sin tocar Windows: todo con un entorno de juguete)."""
from datetime import datetime
from types import SimpleNamespace

import pytest

import acciones_pc
import nucleo
import teclas


class Falso:
    """Un entorno de juguete que anota lo que se le pide."""

    def __init__(self, codigo=0):
        self.dicho, self.teclas, self.abierto, self.corrido, self.minutos = [], [], [], [], []
        self.codigo = codigo
        self.entorno = acciones_pc.Entorno(
            self.dicho.append, pulsar=self.teclas.append, abrir=self.abierto.append, correr=self._correr,
            temporizador=self.minutos.append, ahora=lambda: datetime(2026, 11, 22, 15, 20))

    def _correr(self, argumentos):
        self.corrido.append(argumentos)
        return SimpleNamespace(returncode=self.codigo)


def test_el_catalogo_esta_bien_armado():
    claves = [a.clave for a in acciones_pc.CATALOGO]
    assert len(claves) == len(set(claves))
    nombres = [acciones_pc.nombre_para_ventana(a) for a in acciones_pc.CATALOGO]
    assert len(nombres) == len(set(nombres))
    assert len(claves) >= 100
    for a in acciones_pc.CATALOGO:
        modo, dato = a.como
        assert modo in {"teclas", "abrir", "correr", "powershell", "funcion", "informe", "temporizador"}, a.clave
        assert a.frase and a.frase == a.frase.lower(), a.clave
        assert not any(c in a.frase for c in "áéíóúü¿?¡!,."), f"la frase va sin tildes ni signos: {a.clave}"


def test_las_teclas_del_catalogo_existen():
    for a in acciones_pc.CATALOGO:
        if a.como[0] == "teclas":
            teclas.analizar(a.como[1])   # lanza ErrorTecla si alguna tecla no existe


def test_las_funciones_e_informes_existen():
    for a in acciones_pc.CATALOGO:
        if a.como[0] == "funcion":
            assert a.como[1] in acciones_pc.FUNCIONES, a.clave
        if a.como[0] == "informe":
            assert a.como[1] in acciones_pc.INFORMES, a.clave


def test_decir_cada_frase_sugerida_ejecuta_su_propia_accion():
    """Con todos los sugeridos cargados, cada frase tiene que llevar a su acción (no a otra parecida)."""
    comandos = []
    for c in acciones_pc.comandos_sugeridos([]):
        c = dict(c)
        c["frase"] = nucleo.sin_tildes(c["frase"])
        comandos.append(c)
    comandos.sort(key=lambda c: len(c["frase"]), reverse=True)
    for c in comandos:
        hallado = nucleo.buscar_comando(c["frase"], comandos)
        assert hallado["valor"] == c["valor"], f"'{c['frase']}' lleva a {hallado['valor']}"
        hallado = nucleo.buscar_comando("lynx " + c["frase"] + " por favor", comandos)
        assert hallado["valor"] == c["valor"]


def test_sugeridos_no_pisan_lo_tuyo():
    tuyos = [{"frase": "Suspendé la computadora", "tipo": "abrir_web", "valor": "x"},
             {"frase": "mi frase", "tipo": "accion_pc", "valor": "reiniciar"}]
    nuevos = acciones_pc.comandos_sugeridos(tuyos)
    claves = {c["valor"] for c in nuevos}
    assert "suspender" not in claves      # esa frase ya la usás para otra cosa
    assert "reiniciar" not in claves      # esa acción ya la tenés con otra frase
    assert len(claves) == len(nuevos) > 90
    assert acciones_pc.comandos_sugeridos(tuyos + nuevos) == []


def test_las_acciones_peligrosas_piden_confirmacion():
    for clave in ("reiniciar", "cerrar_sesion", "vaciar_papelera", "cerrar_ventana", "reiniciar_explorador"):
        assert acciones_pc.POR_CLAVE[clave].confirmar, clave
    sugeridos = {c["valor"]: c for c in acciones_pc.comandos_sugeridos([])}
    assert sugeridos["reiniciar"]["confirmar"] is True
    assert sugeridos["suspender"]["confirmar"] is False


def test_ejecutar_por_teclas_abrir_y_correr():
    f = Falso()
    assert acciones_pc.ejecutar("mostrar_escritorio", f.entorno)
    assert f.teclas == ["win+d"] and f.dicho == []            # las de teclas no hablan
    acciones_pc.ejecutar("calculadora", f.entorno)
    assert f.abierto == ["calc"] and f.dicho == ["Abriendo."]
    f2 = Falso()
    acciones_pc.ejecutar("reiniciar", f2.entorno)
    assert f2.corrido == [["shutdown", "/r", "/t", "0"]] and f2.dicho == ["Reiniciando la PC."]


def test_la_respuesta_propia_manda_sobre_la_del_catalogo():
    f = Falso()
    acciones_pc.ejecutar("calculadora", f.entorno, "Ahí va")
    assert f.dicho == ["Ahí va"]


def test_suspender_usa_powershell_y_no_rundll32():
    f = Falso()
    acciones_pc.ejecutar("suspender", f.entorno)
    assert f.corrido[0][0] == "powershell" and "SetSuspendState('Suspend'" in f.corrido[0][-1]
    assert f.dicho == ["Suspendiendo."]


def test_si_powershell_falla_avisa_en_vez_de_romper():
    f = Falso(codigo=1)
    assert not acciones_pc.ejecutar("vaciar_papelera", f.entorno)
    assert f.dicho == ["No pude hacerlo."]


def test_brillo_falla_con_mensaje_claro():
    f = Falso(codigo=1)
    assert acciones_pc.ejecutar("brillo_subir", f.entorno)
    assert "monitores externos" in f.dicho[0]
    ok = Falso()
    acciones_pc.ejecutar("brillo_subir", ok.entorno)
    assert ok.dicho == []


def test_script_de_brillo():
    assert "+ (20)" in acciones_pc.script_de_brillo(cambio=20)
    assert "+ (-20)" in acciones_pc.script_de_brillo(cambio=-20)
    assert "$n = 100" in acciones_pc.script_de_brillo(valor=100)
    assert "WmiSetBrightness" in acciones_pc.script_de_brillo(valor=5)


def test_accion_que_ya_no_existe():
    f = Falso()
    assert not acciones_pc.ejecutar("inventada", f.entorno)
    assert "ya no existe" in f.dicho[0]


def test_informes_de_hora_y_fecha():
    f = Falso()
    acciones_pc.ejecutar("decir_hora", f.entorno)
    acciones_pc.ejecutar("decir_fecha", f.entorno)
    assert f.dicho == ["Son las 3 y 20 de la tarde.", "Hoy es domingo 22 de noviembre de 2026."]


@pytest.mark.parametrize("hora,minuto,esperado", [
    (1, 0, "Es la una en punto de la madrugada."), (13, 15, "Es la una y cuarto de la tarde."),
    (9, 30, "Son las 9 y media de la mañana."), (0, 5, "Son las 12 y 5 de la madrugada."),
    (23, 45, "Son las 11 y 45 de la noche."),
])
def test_texto_de_la_hora(hora, minuto, esperado):
    assert acciones_pc.texto_hora(datetime(2026, 1, 1, hora, minuto)) == esperado


def test_textos_de_duracion_y_bateria():
    assert acciones_pc.texto_duracion(59 * 60) == "59 minutos"
    assert acciones_pc.texto_duracion(3600) == "1 hora"
    assert acciones_pc.texto_duracion(3 * 3600 + 12 * 60) == "3 horas y 12 minutos"
    assert acciones_pc.texto_duracion(86400 * 2 + 3600 + 60) == "2 días, 1 hora y 1 minuto"
    assert acciones_pc.texto_bateria(None, True) == "Esta PC no tiene batería."
    assert acciones_pc.texto_bateria(40, True) == "La batería está al 40 por ciento y está cargando."
    assert acciones_pc.texto_bateria(40, False).endswith("no está enchufada.")


def test_temporizador_llama_al_motor():
    f = Falso()
    acciones_pc.ejecutar("temporizador_10", f.entorno)
    acciones_pc.ejecutar("temporizador_cancelar", f.entorno)
    assert f.minutos == [10, 0]


def _motor_de_juguete(**extra):
    dicho = []
    motor = SimpleNamespace(temporizadores=[], despierto=False, mudo=False,
                            pausado=SimpleNamespace(is_set=lambda: False), hablar=dicho.append, dicho=dicho)
    motor.__dict__.update(extra)
    return motor


def test_el_motor_avisa_cuando_vence_un_temporizador(monkeypatch):
    motor = _motor_de_juguete()
    reloj = [1000.0]
    monkeypatch.setattr(nucleo.time, "monotonic", lambda: reloj[0])
    nucleo.Motor.poner_temporizador(motor, 5)
    nucleo.Motor._avisar_temporizadores(motor)
    assert motor.dicho == []
    reloj[0] += 301
    motor.despierto = True                      # está atento a una orden: espera
    nucleo.Motor._avisar_temporizadores(motor)
    assert motor.dicho == []
    motor.despierto = False
    nucleo.Motor._avisar_temporizadores(motor)
    nucleo.Motor._avisar_temporizadores(motor)
    assert motor.dicho == ["Se terminó el tiempo."]


def test_cancelar_temporizadores(monkeypatch):
    motor = _motor_de_juguete()
    nucleo.Motor.poner_temporizador(motor, 5)
    nucleo.Motor.poner_temporizador(motor, 0)
    assert motor.temporizadores == []


def test_respuesta_de_cada_tipo_de_comando():
    assert nucleo.respuesta_de_comando({"tipo": "accion_pc", "valor": "suspender"}) == "Suspendiendo."
    assert nucleo.respuesta_de_comando({"tipo": "accion_pc", "valor": "suspender", "respuesta": "Chau"}) == "Chau"
    assert nucleo.respuesta_de_comando({"tipo": "accion_pc", "valor": "copiar"}) == ""
    assert nucleo.respuesta_de_comando({"tipo": "abrir_web"}) == "Abriendo."
    assert nucleo.respuesta_de_comando({"tipo": "apagar"}) == "Apagando la PC."


def test_la_lista_del_dialogo_muestra_cada_accion_directamente():
    """Pedido del usuario: en "¿Qué tiene que hacer?" aparece cada acción, no un tipo genérico con otra lista."""
    pytest.importorskip("tkinter")
    import configurar
    assert "Acción de la PC" not in configurar.OPCIONES_DE_ACCION
    assert "Energía · Suspender la PC" in configurar.OPCIONES_DE_ACCION
    assert "Abrir programa" in configurar.OPCIONES_DE_ACCION
    assert len(configurar.OPCIONES_DE_ACCION) == len(set(configurar.OPCIONES_DE_ACCION)) > 100
    assert configurar.accion_en_texto({"tipo": "accion_pc", "valor": "suspender"}) == "Suspender la PC"
