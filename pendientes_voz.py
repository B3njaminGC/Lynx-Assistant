"""
Entiende las órdenes de voz sobre pendientes: "terminé comprar pan", "agregá pendiente llamar al médico"...

Recibe el texto que reconoció Vosk (en minúsculas y sin tildes) y devuelve una `Orden`, o None si no es una
orden de pendientes. No toca archivos ni habla: solo interpreta. Cada orden tiene una función corta y su patrón.
"""
import re
from collections import namedtuple
from datetime import datetime, timedelta

from pendientes import normalizar

# accion: "listar", "agregar", "terminar", "borrar" o "posponer".
# texto: de qué pendiente se habla ("" si no lo dijiste). hasta: hora de vuelta (solo "posponer", o None si no la dijiste).
Orden = namedtuple("Orden", "accion texto hasta")

HORA_DE_MANANA = 9   # "posponé X mañana" = mañana a las 9:00

# Cada orden empieza con alguno de estos verbos (ya sin tildes: "agregá" -> "agrega").
_AGREGAR = re.compile(r"^(agrega|agregame|agregar|anota|anotame|anotar|suma|sumame|crea|nuevo|otro)"
                      r"( un| el| otro)? pendientes?( de| que)?( (?P<texto>.+))?$")
_BORRAR = re.compile(r"^(borra|borrame|borrar|elimina|eliminame|eliminar|quita|quitame|saca|sacame)"
                     r"( el| un)? pendientes?( (?P<texto>.+))?$")
_POSPONER = re.compile(r"^(pospone|posponeme|posponer|atrasa|atrasame)( el pendiente)?( (?P<resto>.+))?$")
_TERMINAR = re.compile(r"^(ya )?(termine|terminamos|hice|complete|resolvi|cumpli|finalice)"
                       r"( con)?( (el|un) pendiente)?( (?P<texto>.+))?$")
_MARCAR = re.compile(r"^(marca|marcame|tacha|tachame)( como)? (hecho|hecha|terminado|terminada|listo|lista)"
                     r"( (el|un) pendiente)?( (?P<texto>.+))?$")
_LISTAR = re.compile(r"^(que (tengo|me queda|me falta|pendientes)|cuales son (mis|los) pendientes|mis pendientes|"
                     r"los pendientes|(leeme|lee|decime|dime|repetime|repeti|repite|recordame) (mis |los )?pendientes)")

_UNIDADES = {"un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
             "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14,
             "quince": 15, "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20,
             "veintiuno": 21, "veintiun": 21, "veintidos": 22, "veintitres": 23, "veinticuatro": 24,
             "veinticinco": 25, "veintiseis": 26, "veintisiete": 27, "veintiocho": 28, "veintinueve": 29}
_DECENAS = {"treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60}


def interpretar(texto, ahora=None):
    """El texto dicho -> Orden, o None si no es una orden de pendientes."""
    limpio = normalizar(texto)
    limpio = re.sub(r"^(por favor |lynx |che )+", "", limpio)
    ahora = ahora or datetime.now()
    for funcion in (_orden_agregar, _orden_borrar, _orden_posponer, _orden_terminar, _orden_listar):
        orden = funcion(limpio, ahora)
        if orden is not None:
            return orden
    return None


def _orden_agregar(texto, ahora):
    m = _AGREGAR.match(texto)
    return Orden("agregar", (m.group("texto") or "").strip(), None) if m else None


def _orden_borrar(texto, ahora):
    m = _BORRAR.match(texto)
    return Orden("borrar", (m.group("texto") or "").strip(), None) if m else None


def _orden_terminar(texto, ahora):
    m = _TERMINAR.match(texto) or _MARCAR.match(texto)
    return Orden("terminar", (m.group("texto") or "").strip(), None) if m else None


def _orden_listar(texto, ahora):
    return Orden("listar", "", None) if _LISTAR.match(texto) else None


def _orden_posponer(texto, ahora):
    m = _POSPONER.match(texto)
    if not m:
        return None
    palabras = (m.group("resto") or "").split()
    inicio, fin, hasta = _buscar_tiempo(palabras, ahora)
    if hasta is not None:
        palabras = palabras[:inicio] + palabras[fin:]
    return Orden("posponer", _sin_nexos(palabras), hasta)


def tiempo_de(texto, ahora=None):
    """Solo la hora de vuelta de una frase suelta ("una hora", "media hora", "mañana"). None si no hay."""
    palabras = normalizar(texto).split()
    return _buscar_tiempo(palabras, ahora or datetime.now())[2]


def _sin_nexos(palabras):
    """Saca "por", "para", "durante" sueltos de los bordes ("comprar pan por" -> "comprar pan")."""
    sobran = {"por", "para", "durante", "dentro", "de", "en", "hasta"}
    while palabras and palabras[-1] in sobran:
        palabras = palabras[:-1]
    while palabras and palabras[0] in sobran:
        palabras = palabras[1:]
    return " ".join(palabras)


# ------------------------------------------------------------ tiempos
def _buscar_tiempo(palabras, ahora):
    """Busca "una hora", "media hora", "treinta minutos" o "mañana" en las palabras. -> (desde, hasta, cuándo)."""
    for desde in range(len(palabras)):
        for hasta in range(len(palabras), desde, -1):
            cuando = _tiempo_exacto(palabras[desde:hasta], ahora)
            if cuando is not None:
                return desde, hasta, cuando
    return 0, 0, None


def _tiempo_exacto(p, ahora):
    """Si estas palabras son justo un tiempo ("dos horas"), devuelve cuándo vuelve; si no, None."""
    if p == ["manana"]:
        return (ahora + timedelta(days=1)).replace(hour=HORA_DE_MANANA, minute=0, second=0, microsecond=0)
    minutos = _minutos(p)
    return ahora + timedelta(minutes=minutos) if minutos else None


def _minutos(p):
    """["una","hora","y","media"] -> 90. Si no es una duración, None."""
    if p == ["media", "hora"]:
        return 30
    if p == ["un", "cuarto", "de", "hora"]:
        return 15
    if len(p) >= 2 and p[-1] == "media" and p[-2] in ("y",):
        base = _minutos(p[:-2])
        return base + 30 if base and base % 60 == 0 else None
    if len(p) >= 2 and p[-1] in ("hora", "horas"):
        n = _numero(p[:-1])
        return n * 60 if n else None
    if len(p) >= 2 and p[-1] in ("minuto", "minutos"):
        return _numero(p[:-1])
    return None


def _numero(p):
    """["treinta","y","cinco"] -> 35; ["dos"] -> 2; ["15"] -> 15. Si no es un número, None."""
    if len(p) == 1:
        if p[0].isdigit():
            return int(p[0])
        return _UNIDADES.get(p[0]) or _DECENAS.get(p[0])
    if len(p) == 3 and p[0] in _DECENAS and p[1] == "y" and p[2] in _UNIDADES and _UNIDADES[p[2]] < 10:
        return _DECENAS[p[0]] + _UNIDADES[p[2]]
    return None


# ------------------------------------------------------------ lo que se dice al leerlos
_ORDINALES = ["uno", "dos", "tres", "cuatro", "cinco"]
MAXIMO_A_LEER = len(_ORDINALES)   # si hay más, se leen los primeros y se dice cuántos faltan


def frases_de_lectura(items):
    """
    Lo que Lynx dice al leer los pendientes: una lista de (tipo, texto).
    tipo "fija" = frase que ya viene preparada (puede sonar con la voz de personaje);
    tipo "item" = texto tuyo, que se dice con una voz de Windows.
    """
    if not items:
        return [("fija", "No tenés pendientes.")]
    if len(items) == 1:
        return [("fija", "Tenés un pendiente."), ("item", items[0]["texto"] + ".")]
    frases = [("fija", "Tenés estos pendientes.")]
    for numero, item in enumerate(items[:MAXIMO_A_LEER]):
        frases.append(("item", f"{_ORDINALES[numero].capitalize()}, {item['texto']}."))
    resto = len(items) - MAXIMO_A_LEER
    if resto == 1:
        frases.append(("fija", "Y uno más."))
    elif resto > 1:
        frases.append(("item", f"Y {resto} más."))
    return frases


# Frases que se pueden decir con Lynx ya despierto (las entiende el reconocedor de frases fijas).
FRASES_FIJAS_DE_VOZ = (
    ["que tengo pendiente", "que pendientes tengo", "mis pendientes", "leeme mis pendientes",
     "agrega un pendiente", "anota un pendiente", "agrega pendiente", "termine un pendiente",
     "borra un pendiente", "borra pendiente", "pospone un pendiente"]
    + [f"termine el {n}" for n in _ORDINALES]
    + [f"borra el pendiente {n}" for n in _ORDINALES]
    + [f"pospone el {n}" for n in _ORDINALES]
)
