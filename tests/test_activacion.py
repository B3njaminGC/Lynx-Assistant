"""Cuándo Lynx se da por llamado: el nombre debe estar al principio de la frase y con suficiente confianza."""
import pytest

import nucleo


def oido(texto, confianza):
    return {"text": texto, "result": [{"word": w, "conf": confianza} for w in texto.split()]}


@pytest.fixture
def motor():
    return nucleo.Motor(dict(nucleo.CONFIG_BASE))


NOMBRES = {"links", "lynx"}


@pytest.mark.parametrize("texto,confianza,esperado", [
    ("links", 0.5, []),                          # 1ª palabra: alcanza con poca confianza
    ("links", 0.4, None),
    ("bueno links", 0.65, []),                   # 2ª palabra: pide más
    ("bueno links", 0.5, None),
    ("che bueno links abri", 0.8, ["abri"]),     # 3ª palabra, y trae la orden pegada
    ("che bueno links", 0.7, None),
    ("che bueno links abri algo", 0.99, None),   # frase larga: es charla, no una llamada
    ("hola que tal links", 0.99, None),          # 4ª palabra: demasiado lejos
])
def test_posicion_y_confianza(motor, texto, confianza, esperado):
    assert motor._detectar_llamada(oido(texto, confianza), NOMBRES) == esperado


@pytest.mark.parametrize("texto,confianza,esperado", [
    ("pese", 0.7, []),                  # "pece" mal escrito por el modelo
    ("link", 0.7, []),
    ("pese", 0.3, None),                # sin seguridad no cuenta
    ("peso", 0.9, None),                # parecido pero distinto
    ("pese a todo lo que paso", 0.9, None),
    ("lince", 0.9, None),               # otra palabra
])
def test_nombres_mal_escritos_en_frases_cortas(motor, texto, confianza, esperado):
    assert motor._detectar_llamada(oido(texto, confianza), {"pece", "links", "lynx", "compu"}) == esperado
