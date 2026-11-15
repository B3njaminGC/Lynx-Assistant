"""
Apretar teclas como si las tocaras vos, también dentro de juegos.

Usa códigos de teclado físicos ("scan codes") en vez de códigos virtuales: es lo que leen la mayoría de los
juegos. No depende de nada de Windows hasta el momento de enviar, así que el análisis se puede probar en
cualquier sistema.

Un comando de tipo "enviar_teclas" guarda una lista de combinaciones, una por línea:
    enter
    ctrl+shift+m
    w
Cada línea se aprieta en orden. Los nombres pueden estar en español o en inglés (enter/intro, esc/escape,
espacio/space, flecha arriba...).
"""
import time
from collections import namedtuple

Tecla = namedtuple("Tecla", "scan extendida")
Combinacion = namedtuple("Combinacion", "modificadores tecla texto")


class ErrorTecla(ValueError):
    """Un nombre de tecla que no conozco o una combinación mal escrita."""


# Códigos de teclado físicos (conjunto 1). Las teclas "extendidas" llevan un aviso aparte al enviarlas.
_LETRAS = dict(zip("qwertyuiop", range(0x10, 0x1A)))
_LETRAS.update(zip("asdfghjkl", range(0x1E, 0x27)))
_LETRAS.update(zip("zxcvbnm", range(0x2C, 0x33)))
_NUMEROS = dict(zip("1234567890", range(0x02, 0x0C)))

TECLAS = {nombre: Tecla(scan, False) for nombre, scan in {**_LETRAS, **_NUMEROS}.items()}
TECLAS.update({
    "enter": Tecla(0x1C, False), "esc": Tecla(0x01, False), "espacio": Tecla(0x39, False),
    "tab": Tecla(0x0F, False), "retroceso": Tecla(0x0E, False),
    "ctrl": Tecla(0x1D, False), "alt": Tecla(0x38, False), "shift": Tecla(0x2A, False),
    "win": Tecla(0x5B, True),
    "arriba": Tecla(0x48, True), "abajo": Tecla(0x50, True), "izquierda": Tecla(0x4B, True),
    "derecha": Tecla(0x4D, True), "inicio": Tecla(0x47, True), "fin": Tecla(0x4F, True),
    "repag": Tecla(0x49, True), "avpag": Tecla(0x51, True), "insertar": Tecla(0x52, True),
    "suprimir": Tecla(0x53, True),
    "menos": Tecla(0x0C, False), "igual": Tecla(0x0D, False), "coma": Tecla(0x33, False),
    "punto": Tecla(0x34, False), "barra": Tecla(0x35, False), "puntoycoma": Tecla(0x27, False),
    "comilla": Tecla(0x28, False), "corchete_izq": Tecla(0x1A, False), "corchete_der": Tecla(0x1B, False),
    "contrabarra": Tecla(0x2B, False), "acento_grave": Tecla(0x29, False),
})
TECLAS.update({f"f{n}": Tecla(0x3A + n, False) for n in range(1, 11)})
TECLAS.update({"f11": Tecla(0x57, False), "f12": Tecla(0x58, False)})

MODIFICADORES = ("ctrl", "alt", "shift", "win")

# Otros nombres para la misma tecla.
SINONIMOS = {
    "intro": "enter", "return": "enter", "escape": "esc", "space": "espacio", "barra espaciadora": "espacio",
    "tabulador": "tab", "backspace": "retroceso", "borrar": "retroceso",
    "control": "ctrl", "mayus": "shift", "mayuscula": "shift", "windows": "win", "inicio de windows": "win",
    "up": "arriba", "flecha arriba": "arriba", "down": "abajo", "flecha abajo": "abajo",
    "left": "izquierda", "flecha izquierda": "izquierda", "right": "derecha", "flecha derecha": "derecha",
    "home": "inicio", "end": "fin", "pgup": "repag", "pageup": "repag", "pgdn": "avpag", "pagedown": "avpag",
    "insert": "insertar", "delete": "suprimir", "supr": "suprimir", "del": "suprimir",
    "minus": "menos", "guion": "menos", "equals": "igual", "comma": "coma", "period": "punto",
    "slash": "barra", "semicolon": "puntoycoma", "apostrophe": "comilla", "backslash": "contrabarra",
    "grave": "acento_grave",
}

_SIN_TILDES = str.maketrans("áéíóúü", "aeiouu")


def _normalizar(nombre):
    return " ".join(nombre.lower().translate(_SIN_TILDES).split())


def buscar_tecla(nombre):
    """Devuelve (nombre canónico, Tecla) o lanza ErrorTecla."""
    limpio = _normalizar(nombre)
    limpio = SINONIMOS.get(limpio, limpio)
    if limpio not in TECLAS:
        raise ErrorTecla(f"No conozco la tecla \"{nombre.strip()}\".")
    return limpio, TECLAS[limpio]


def analizar(texto):
    """Pasa el texto (una combinación por línea) a una lista de Combinacion. Lanza ErrorTecla si algo está mal."""
    if isinstance(texto, (list, tuple)):
        lineas = [str(t) for t in texto]
    else:
        lineas = str(texto).splitlines()
    combinaciones = []
    for linea in lineas:
        if not linea.strip():
            continue
        partes = [p for p in linea.split("+")]
        if any(not p.strip() for p in partes):
            raise ErrorTecla(f"La combinación \"{linea.strip()}\" está incompleta.")
        nombres = [buscar_tecla(p) for p in partes]
        *previas, (nombre_final, tecla_final) = nombres
        for nombre, _ in previas:
            if nombre not in MODIFICADORES:
                raise ErrorTecla(f"En \"{linea.strip()}\", \"{nombre}\" tiene que ir al final: "
                                 "antes del + solo pueden ir ctrl, alt, shift o win.")
        combinaciones.append(Combinacion(tuple(t for _, t in previas), tecla_final, linea.strip()))
    if not combinaciones:
        raise ErrorTecla("No hay ninguna tecla para apretar.")
    return combinaciones


def eventos(combinacion):
    """Los pasos de una combinación, en orden: [(Tecla, soltar?)]."""
    pasos = [(m, False) for m in combinacion.modificadores]
    pasos.append((combinacion.tecla, False))
    return pasos, [(combinacion.tecla, True)] + [(m, True) for m in reversed(combinacion.modificadores)]


def pulsar(texto, enviar=None, esperar=time.sleep, mantener=0.08, entre=0.15):
    """Aprieta las combinaciones en orden. `mantener` = cuánto se sostiene cada tecla (los juegos ignoran
    toques demasiado cortos); `entre` = pausa entre combinaciones."""
    combinaciones = analizar(texto)
    enviar = enviar or _enviar_windows
    for i, combinacion in enumerate(combinaciones):
        bajar, soltar = eventos(combinacion)
        for tecla, _ in bajar:
            enviar(tecla, False)
            esperar(0.01)
        esperar(mantener)
        for tecla, _ in soltar:
            enviar(tecla, True)
            esperar(0.01)
        if i < len(combinaciones) - 1:
            esperar(entre)
    return len(combinaciones)


def _enviar_windows(tecla, soltar):
    """Un evento de teclado con SendInput y código físico (solo Windows)."""
    import ctypes
    from ctypes import wintypes

    class TECLADO(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class MOUSE(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class HARDWARE(ctypes.Structure):
        _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

    class UNION(ctypes.Union):
        _fields_ = [("ki", TECLADO), ("mi", MOUSE), ("hi", HARDWARE)]

    class ENTRADA(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", UNION)]

    banderas = 0x0008                      # KEYEVENTF_SCANCODE
    if tecla.extendida:
        banderas |= 0x0001                 # KEYEVENTF_EXTENDEDKEY
    if soltar:
        banderas |= 0x0002                 # KEYEVENTF_KEYUP
    entrada = ENTRADA(type=1, u=UNION(ki=TECLADO(0, tecla.scan, banderas, 0, 0)))
    if ctypes.windll.user32.SendInput(1, ctypes.byref(entrada), ctypes.sizeof(entrada)) != 1:
        raise OSError("Windows no aceptó la tecla (puede que el programa esté abierto como administrador).")
