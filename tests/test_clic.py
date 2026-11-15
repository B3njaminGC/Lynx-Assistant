import pytest

import clic
import nucleo

# Dos monitores de 1920x1080 lado a lado: el segundo empieza en x=1920.
DOS_MONITORES = (0, 0, 3840, 1080)


class MouseFalso:
    def __init__(self, pantalla=(0, 0, 1920, 1080), donde=(10, 20)):
        self._pantalla, self.donde, self.registro = pantalla, donde, []

    def pantalla(self):
        return self._pantalla

    def posicion(self):
        return self.donde

    def mover(self, x, y):
        self.donde = (x, y)
        self.registro.append(("mover", x, y))

    def apretar(self, soltar):
        self.registro.append(("soltar" if soltar else "apretar",))


def test_ida_y_vuelta_de_la_posicion():
    guardado = clic.a_fracciones(1500, 900, (0, 0, 1920, 1080))
    assert guardado["x"] == pytest.approx(1500 / 1920, abs=1e-4) and guardado["y"] == pytest.approx(900 / 1080, abs=1e-4)
    x, y = clic.a_pixeles(guardado, (0, 0, 1920, 1080))
    assert abs(x - 1500) <= 2 and abs(y - 900) <= 2


def test_sigue_sirviendo_si_cambia_la_resolucion():
    guardado = clic.a_fracciones(960, 540, (0, 0, 1920, 1080))          # centro
    x, y = clic.a_pixeles(guardado, (0, 0, 1280, 720))
    assert abs(x - 640) <= 1 and abs(y - 360) <= 1


def test_con_dos_monitores_cuenta_el_escritorio_completo():
    guardado = clic.a_fracciones(2880, 540, DOS_MONITORES)              # tres cuartos: segundo monitor
    assert guardado["x"] == 0.75
    assert clic.a_pixeles(guardado, DOS_MONITORES)[0] in (2879, 2880)


def test_un_monitor_a_la_izquierda_del_principal_tiene_coordenadas_negativas():
    pantalla = (-1920, 0, 3840, 1080)
    guardado = clic.a_fracciones(-960, 540, pantalla)
    assert guardado["x"] == 0.25
    assert clic.a_pixeles(guardado, pantalla)[0] < 0


@pytest.mark.parametrize("valor", [None, {}, {"x": "a", "y": 0.5}, {"x": 1.5, "y": 0.5}, {"x": 0.5, "y": -0.1}])
def test_rechaza_posiciones_rotas(valor):
    with pytest.raises(clic.ErrorClic):
        clic.a_pixeles(valor, (0, 0, 1920, 1080))


def test_hace_clic_y_vuelve_el_mouse_a_donde_estaba():
    mouse = MouseFalso()
    clic.hacer_clic({"x": 0.5, "y": 0.5, "volver": True}, sistema=mouse, esperar=lambda _: None)
    assert [e[0] for e in mouse.registro] == ["mover", "apretar", "soltar", "mover"]
    assert mouse.registro[-1] == ("mover", 10, 20)


def test_sin_volver_el_mouse_se_queda_en_el_boton():
    mouse = MouseFalso()
    clic.hacer_clic({"x": 0.5, "y": 0.5, "volver": False}, sistema=mouse, esperar=lambda _: None)
    assert [e[0] for e in mouse.registro] == ["mover", "apretar", "soltar"]


def test_marcar_posicion_lee_el_mouse_actual():
    assert clic.marcar_posicion(MouseFalso(donde=(960, 540))) == {"x": 0.5, "y": 0.5}


def test_texto_para_la_lista_de_comandos():
    assert clic.en_texto({"x": 0.78, "y": 0.83}) == "clic en 78 % × 83 %"
    assert clic.en_texto("basura") == "clic (sin posición)"


def test_el_comando_hace_el_clic_y_no_habla_por_defecto(monkeypatch):
    motor = nucleo.Motor(dict(nucleo.CONFIG_BASE))
    dichas, llamadas = [], []
    motor.hablar = dichas.append
    monkeypatch.setattr(clic, "hacer_clic", llamadas.append)
    posicion = {"x": 0.5, "y": 0.9, "volver": True}
    motor._ejecutar({"frase": "todo listo", "tipo": "hacer_clic", "valor": posicion})
    assert llamadas == [posicion] and dichas == []
