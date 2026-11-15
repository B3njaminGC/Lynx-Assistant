"""
Hacer clic con el mouse en un lugar de la pantalla (por ejemplo el botón JUGAR de un juego).

La posición se guarda como fracción de la pantalla (0 a 1), así sigue sirviendo si cambiás la resolución.
Con dos monitores cuenta todo el escritorio junto. El análisis es puro y se prueba en cualquier sistema;
solo mover el mouse y clickear necesita Windows.
"""
import time

PRECISION = 4


class ErrorClic(ValueError):
    """Una posición guardada que no sirve."""


def a_fracciones(x, y, pantalla):
    """De píxeles a fracciones. `pantalla` = (izquierda, arriba, ancho, alto) del escritorio completo."""
    izq, arr, ancho, alto = pantalla
    if ancho <= 0 or alto <= 0:
        raise ErrorClic("No pude medir la pantalla.")
    return {"x": round((x - izq) / ancho, PRECISION), "y": round((y - arr) / alto, PRECISION)}


def a_pixeles(valor, pantalla):
    """De la posición guardada a píxeles de hoy."""
    try:
        fx, fy = float(valor["x"]), float(valor["y"])
    except (TypeError, KeyError, ValueError):
        raise ErrorClic("La posición del clic no está bien guardada. Volvé a marcarla.") from None
    if not (0 <= fx <= 1 and 0 <= fy <= 1):
        raise ErrorClic("La posición del clic cae fuera de la pantalla. Volvé a marcarla.")
    izq, arr, ancho, alto = pantalla
    return izq + round(fx * (ancho - 1)), arr + round(fy * (alto - 1))


def en_texto(valor):
    """Cómo se ve en la lista de comandos."""
    try:
        return f"clic en {round(float(valor['x']) * 100)} % × {round(float(valor['y']) * 100)} %"
    except (TypeError, KeyError, ValueError):
        return "clic (sin posición)"


def hacer_clic(valor, sistema=None, esperar=time.sleep):
    """Mueve el mouse, hace clic y, si el comando lo pide, devuelve el mouse a donde estaba."""
    sistema = sistema or SistemaWindows()
    x, y = a_pixeles(valor, sistema.pantalla())
    volver = valor.get("volver", True) if isinstance(valor, dict) else True
    antes = sistema.posicion() if volver else None
    sistema.mover(x, y)
    esperar(0.05)                 # que el juego note el mouse encima antes del clic
    sistema.apretar(False)
    esperar(0.06)
    sistema.apretar(True)
    if antes is not None:
        esperar(0.05)
        sistema.mover(*antes)


class SistemaWindows:
    """El mouse real (solo Windows)."""

    def __init__(self):
        import ctypes
        self._u = ctypes.windll.user32
        self._ctypes = ctypes

    def pantalla(self):
        u = self._u
        return u.GetSystemMetrics(76), u.GetSystemMetrics(77), u.GetSystemMetrics(78), u.GetSystemMetrics(79)

    def posicion(self):
        from ctypes import wintypes
        punto = wintypes.POINT()
        if not self._u.GetCursorPos(self._ctypes.byref(punto)):
            raise OSError("No pude leer dónde está el mouse.")
        return punto.x, punto.y

    def mover(self, x, y):
        if not self._u.SetCursorPos(int(x), int(y)):
            raise OSError("Windows no me dejó mover el mouse.")

    def apretar(self, soltar):
        self._u.mouse_event(0x0004 if soltar else 0x0002, 0, 0, 0, 0)   # soltar / apretar el botón izquierdo


def marcar_posicion(sistema=None):
    """La posición actual del mouse, ya como fracciones. Para el botón "Marcar posición"."""
    sistema = sistema or SistemaWindows()
    x, y = sistema.posicion()
    return a_fracciones(x, y, sistema.pantalla())
