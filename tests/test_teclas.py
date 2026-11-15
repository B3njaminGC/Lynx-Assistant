import pytest

import nucleo
import teclas


def apretar(texto, **kw):
    """Corre `pulsar` sin tocar el teclado: devuelve [(scan, extendida, soltar)] en orden."""
    registro = []
    teclas.pulsar(texto, enviar=lambda t, soltar: registro.append((t.scan, t.extendida, soltar)),
                  esperar=lambda _: None, **kw)
    return registro


def test_una_tecla_se_aprieta_y_se_suelta():
    assert apretar("enter") == [(0x1C, False, False), (0x1C, False, True)]


def test_los_modificadores_se_sueltan_al_reves():
    assert apretar("ctrl+shift+m") == [
        (0x1D, False, False), (0x2A, False, False), (0x32, False, False),   # ctrl, shift, m abajo
        (0x32, False, True), (0x2A, False, True), (0x1D, False, True),       # m, shift, ctrl arriba
    ]


def test_varias_lineas_se_aprietan_en_orden():
    assert [e[0] for e in apretar("w\nenter") if not e[2]] == [0x11, 0x1C]


@pytest.mark.parametrize("nombre,esperado", [
    ("Intro", 0x1C), ("ESC", 0x01), ("Escape", 0x01), ("espacio", 0x39), ("Space", 0x39),
    ("f5", 0x3F), ("F12", 0x58), ("a", 0x1E), ("1", 0x02), ("0", 0x0B),
])
def test_nombres_en_espanol_e_ingles_y_mayusculas(nombre, esperado):
    assert apretar(nombre)[0][0] == esperado


def test_las_flechas_son_teclas_extendidas():
    assert apretar("flecha arriba")[0] == (0x48, True, False)
    assert apretar("Flecha Derecha")[0] == (0x4D, True, False)


@pytest.mark.parametrize("texto", ["", "   \n  ", "unatecla", "ctrl+", "+a", "a+ctrl", "enter+a"])
def test_rechaza_lo_mal_escrito(texto):
    with pytest.raises(teclas.ErrorTecla):
        teclas.analizar(texto)


def test_el_mensaje_de_error_nombra_la_tecla():
    with pytest.raises(teclas.ErrorTecla, match="unatecla"):
        teclas.analizar("unatecla")


def test_mantiene_cada_tecla_un_ratito_para_que_los_juegos_la_lean():
    esperas = []
    teclas.pulsar("enter", enviar=lambda *_: None, esperar=esperas.append, mantener=0.08)
    assert 0.08 in esperas


def test_una_lista_guardada_en_comandos_json_tambien_sirve():
    assert len(teclas.analizar(["enter", "ctrl+c"])) == 2


# ---------- dentro del motor ----------
@pytest.fixture
def motor():
    m = nucleo.Motor(dict(nucleo.CONFIG_BASE))
    m.dichas = []
    m.hablar = m.dichas.append
    return m


def test_el_comando_aprieta_las_teclas_y_no_habla_por_defecto(motor, monkeypatch):
    llamadas = []
    monkeypatch.setattr(teclas, "pulsar", llamadas.append)
    motor._ejecutar({"frase": "listo", "tipo": "enviar_teclas", "valor": ["enter"]})
    assert llamadas == [["enter"]] and motor.dichas == []


def test_si_le_ponemos_una_respuesta_la_dice(motor, monkeypatch):
    monkeypatch.setattr(teclas, "pulsar", lambda _: None)
    motor._ejecutar({"frase": "listo", "tipo": "enviar_teclas", "valor": ["enter"], "respuesta": "Dale."})
    assert motor.dichas == ["Dale."]


def test_una_respuesta_vacia_no_se_prepara_con_la_voz_de_personaje(motor):
    motor.comandos = [{"frase": "listo", "tipo": "enviar_teclas", "valor": ["enter"]}]
    assert "" not in motor.frases_del_asistente()
