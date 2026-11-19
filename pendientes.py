"""
Pendientes: la lista guardada en `pendientes.json` y las búsquedas sobre ella.

No sabe nada de voz ni de ventanas: solo guarda, busca y marca. Así se puede probar sola.

Cada pendiente se guarda así:
    {"id": 3, "texto": "comprar pan", "hecho": false, "creado": "2026-11-19T15:50:00",
     "hecho_en": null, "posponer_hasta": null}
"""
import functools
import json
import os
import threading
import unicodedata
from collections import namedtuple
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path

VERSION_ARCHIVO = 1
DIAS_QUE_SE_GUARDAN_LOS_HECHOS = 30   # un tiempo quedan guardados por si te equivocás

# Resultado de buscar un pendiente por lo que dijiste:
#   tipo = "uno" (es ese), "dudas" (podrían ser varios: hay que preguntar) o "ninguno".
Eleccion = namedtuple("Eleccion", "tipo items")

PALABRAS_SUELTAS = {"el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "que", "a", "al",
                    "por", "para", "mi", "mis", "y", "en", "con", "lo", "se", "pendiente"}
UMBRAL_PARECIDO = 0.55     # menos que esto: no se parece a ninguno
MARGEN_DE_DUDA = 0.12      # si el segundo está así de cerca del primero, hay que preguntar

NUMEROS = {"uno": 1, "una": 1, "primero": 1, "primer": 1, "dos": 2, "segundo": 2, "tres": 3, "tercero": 3,
           "cuatro": 4, "cuarto": 4, "cinco": 5, "quinto": 5, "seis": 6, "sexto": 6, "siete": 7,
           "septimo": 7, "ocho": 8, "octavo": 8, "nueve": 9, "noveno": 9, "diez": 10, "decimo": 10,
           "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16,
           "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20}


def normalizar(texto):
    """Minúsculas, sin tildes ni signos, con espacios simples ("¿Comprar Pan?" -> "comprar pan")."""
    sin_marcas = unicodedata.normalize("NFKD", str(texto).lower())
    letras = "".join(c if c.isalnum() else " " for c in sin_marcas if not unicodedata.combining(c))
    return " ".join(letras.split())


def _claves(texto):
    """Las palabras que importan de un texto (sin "el", "de", etc.)."""
    return [p for p in normalizar(texto).split() if p not in PALABRAS_SUELTAS]


def _parecidas(a, b):
    return a == b or SequenceMatcher(None, a, b).ratio() >= 0.8


def puntaje(consulta, texto):
    """Qué tanto se parece lo que dijiste a un pendiente: de 0 (nada) a 1 (igual)."""
    pedidas, tiene = _claves(consulta), _claves(texto)
    if not pedidas or not tiene:
        return 0.0
    cubiertas = sum(1 for p in pedidas if any(_parecidas(p, q) for q in tiene)) / len(pedidas)
    entero = SequenceMatcher(None, " ".join(pedidas), " ".join(tiene)).ratio()
    return 0.7 * cubiertas + 0.3 * entero


def numero_de(texto):
    """"el dos", "número 2", "segundo" -> 2. Si no hay un número solo, None."""
    palabras = [p for p in normalizar(texto).split() if p not in PALABRAS_SUELTAS and p != "numero"]
    if len(palabras) != 1:
        return None
    palabra = palabras[0]
    if palabra.isdigit():
        return int(palabra)
    return NUMEROS.get(palabra)


def _con_candado(funcion):
    """La ventana y el motor de voz usan la misma lista a la vez: de a una operación por vez."""
    @functools.wraps(funcion)
    def envuelta(self, *args, **kwargs):
        with self.candado:
            return funcion(self, *args, **kwargs)
    return envuelta


class Pendientes:
    """La lista de pendientes guardada en un archivo."""

    def __init__(self, ruta, ahora=datetime.now, avisar=lambda *a: None):
        self.ruta = Path(ruta)
        self.ahora = ahora          # se puede reemplazar en las pruebas
        self.avisar = avisar        # dónde anotar los problemas (en Lynx: el registro)
        self.items = []
        self.ultimo_id = 0          # el id más alto que se usó alguna vez (no se vuelve a usar aunque borres)
        self.ultima_lectura = None  # cuándo se leyeron en voz alta por última vez (evita repetir al reiniciar)
        self.candado = threading.RLock()
        self.cargar()

    # ---------------------------------------------------------- archivo
    @_con_candado
    def cargar(self):
        """Lee el archivo. Si no existe, empieza vacío; si está roto, lo aparta (no lo pisa) y empieza vacío."""
        self.items = []
        self.ultimo_id = 0
        self.ultima_lectura = None
        if not self.ruta.exists():
            return
        try:
            datos = json.loads(self.ruta.read_text(encoding="utf-8"))
            self.items = [self._validar(i) for i in datos["pendientes"]]
            self.ultimo_id = max([int(datos.get("ultimo_id", 0))] + [i["id"] for i in self.items])
            self.ultima_lectura = datos.get("ultima_lectura")
        except (OSError, ValueError, KeyError, TypeError):
            apartado = self.ruta.with_name(f"pendientes.roto-{self.ahora():%Y%m%d-%H%M%S}.json")
            self.avisar("[pendientes] el archivo está dañado; lo guardé aparte como", apartado.name)
            try:
                os.replace(self.ruta, apartado)
            except OSError:
                pass
            self.items = []
            self.ultimo_id = 0
            self.ultima_lectura = None

    @staticmethod
    def _validar(item):
        """Deja un pendiente con todos sus campos. Si le falta algo esencial, falla (y se aparta el archivo)."""
        texto = str(item["texto"]).strip()
        if not texto:
            raise ValueError("pendiente sin texto")
        return {"id": int(item["id"]), "texto": texto, "hecho": bool(item.get("hecho", False)),
                "creado": item.get("creado"), "hecho_en": item.get("hecho_en"),
                "posponer_hasta": item.get("posponer_hasta")}

    def guardar(self):
        """Guarda sin riesgo de dejar el archivo a medias: escribe uno nuevo y recién después lo cambia."""
        temporal = self.ruta.with_name(self.ruta.name + ".tmp")
        datos = {"version": VERSION_ARCHIVO, "ultimo_id": self.ultimo_id, "ultima_lectura": self.ultima_lectura,
                 "pendientes": self.items}
        temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporal, self.ruta)

    # ---------------------------------------------------------- consultas
    def abiertos(self):
        """Los que todavía no hiciste (incluye los pospuestos)."""
        return [i for i in self.items if not i["hecho"]]

    def para_leer(self):
        """Los que se leen ahora: sin hacer y no pospuestos."""
        ahora = self.ahora()
        return [i for i in self.abiertos() if not self._pospuesto(i, ahora)]

    def _pospuesto(self, item, ahora):
        hasta = item.get("posponer_hasta")
        try:
            return bool(hasta) and datetime.fromisoformat(hasta) > ahora
        except ValueError:
            return False

    def minutos_desde_la_lectura(self):
        """Cuántos minutos pasaron desde la última lectura en voz alta (None si nunca se leyeron)."""
        try:
            return (self.ahora() - datetime.fromisoformat(self.ultima_lectura)).total_seconds() / 60
        except (TypeError, ValueError):
            return None

    @_con_candado
    def marcar_lectura(self):
        """Anota que acaba de leerlos."""
        self.ultima_lectura = self.ahora().isoformat(timespec="seconds")
        self.guardar()

    def por_id(self, id_):
        return next((i for i in self.items if i["id"] == id_), None)

    # ---------------------------------------------------------- cambios
    @_con_candado
    def agregar(self, texto):
        """Suma un pendiente. Si ya hay uno abierto igual, no lo repite y devuelve ese. -> (item, es_nuevo)"""
        texto = " ".join(str(texto).split())
        if not texto:
            raise ValueError("El pendiente está vacío.")
        for item in self.abiertos():
            if normalizar(item["texto"]) == normalizar(texto):
                return item, False
        self.ultimo_id += 1
        nuevo_id = self.ultimo_id
        item = {"id": nuevo_id, "texto": texto, "hecho": False, "creado": self.ahora().isoformat(timespec="seconds"),
                "hecho_en": None, "posponer_hasta": None}
        self.items.append(item)
        self.guardar()
        return item, True

    @_con_candado
    def marcar_hecho(self, id_):
        item = self.por_id(id_)
        if item is None:
            return None
        item["hecho"] = True
        item["hecho_en"] = self.ahora().isoformat(timespec="seconds")
        item["posponer_hasta"] = None
        self.guardar()
        return item

    @_con_candado
    def borrar(self, id_):
        self.items = [i for i in self.items if i["id"] != id_]
        self.guardar()

    @_con_candado
    def posponer(self, id_, hasta):
        """Lo deja callado hasta `hasta` (un datetime)."""
        item = self.por_id(id_)
        if item is None:
            return None
        item["posponer_hasta"] = hasta.isoformat(timespec="seconds")
        self.guardar()
        return item

    @_con_candado
    def limpiar_hechos_viejos(self):
        """Saca del archivo los hechos de hace más de 30 días. Devuelve cuántos sacó."""
        limite = self.ahora() - timedelta(days=DIAS_QUE_SE_GUARDAN_LOS_HECHOS)
        quedan = []
        for i in self.items:
            try:
                viejo = i["hecho"] and i["hecho_en"] and datetime.fromisoformat(i["hecho_en"]) < limite
            except ValueError:
                viejo = False
            if not viejo:
                quedan.append(i)
        sacados = len(self.items) - len(quedan)
        if sacados:
            self.items = quedan
            self.guardar()
        return sacados

    # ---------------------------------------------------------- búsqueda
    def elegir(self, consulta, numeracion=None):
        """
        Encuentra el pendiente abierto al que te referís.
        `numeracion` es la lista tal como se leyó en voz alta (para "el dos"); si no se da, la de para_leer().
        """
        abiertos = self.abiertos()
        numero = numero_de(consulta)
        if numero is not None:
            lista = self.para_leer() if numeracion is None else numeracion
            return Eleccion("uno", [lista[numero - 1]]) if 1 <= numero <= len(lista) else Eleccion("ninguno", [])
        puntajes = sorted(((puntaje(consulta, i["texto"]), i) for i in abiertos), key=lambda p: -p[0])
        puntajes = [p for p in puntajes if p[0] >= UMBRAL_PARECIDO]
        if not puntajes:
            return Eleccion("ninguno", [])
        mejor = puntajes[0][0]
        cercanos = [i for p, i in puntajes if p >= mejor - MARGEN_DE_DUDA][:3]
        return Eleccion("uno" if len(cercanos) == 1 else "dudas", cercanos)
