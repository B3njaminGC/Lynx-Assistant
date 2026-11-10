"""
Importar personajes (modelos RVC): desde un link, desde la página de un sitio de voces o desde un
archivo que ya bajaste. Todo con la librería estándar de Python.

Qué entiende `resolver`:
  - un link directo a un .zip / .pth / .index (de cualquier sitio)
  - una página de Hugging Face (usuario/repositorio): lista sus archivos por la API
  - la página de un sitio de voces (voice-models.com, aivoices.gg...): busca adentro los links de
    descarga
MediaFire, Google Drive o Mega no se pueden bajar solos: ahí se baja con el navegador y se usa
"Importar archivo".
"""
import html
import json
import re
import shutil
import threading
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

AGENTE = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Lynx-Asistente/1.0"
EXTENSIONES = (".zip", ".pth", ".index")
MAX_PAGINA = 3_000_000  # bytes que se leen de una página web


class ErrorImportar(Exception):
    """Mensaje pensado para mostrárselo tal cual al usuario."""


# ---------------------------------------------------------------- utilidades

def limpiar_nombre(texto, largo=60):
    """Nombre seguro para una carpeta/archivo de Windows."""
    texto = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", texto or "").strip(" .")
    texto = re.sub(r"\s+", " ", texto)
    return texto[:largo].strip(" .") or "Personaje"


def _ruta(url):
    return urllib.parse.unquote(urllib.parse.urlparse(url).path)


def extension_de(url):
    ruta = _ruta(url).lower()
    for ext in EXTENSIONES:
        if ruta.endswith(ext):
            return ext
    return ""


def nombre_de_archivo(url):
    return limpiar_nombre(Path(_ruta(url)).name, 120)


def normalizar_enlace(texto):
    texto = (texto or "").strip().strip('"\'<>')
    if not texto:
        raise ErrorImportar("Pegá primero un link.")
    if not re.match(r"^https?://", texto, re.I):
        texto = "https://" + texto
    partes = urllib.parse.urlparse(texto)
    if "." not in partes.netloc:
        raise ErrorImportar("Ese link no parece una página web.")
    return texto


def _es_modelo_pth(url):
    return extension_de(url) == ".pth" and not nombre_de_archivo(url).upper().startswith(("D_", "G_"))


def _agrupar(urls):
    """
    De una lista de links de archivos hace 'candidatos': cada .zip es uno, y los .pth van con los
    .index que están en la misma carpeta. Devuelve [{'titulo', 'urls', 'nombre'}].
    """
    vistos, candidatos = set(), []
    urls = [u for u in urls if not (u in vistos or vistos.add(u))]
    for u in urls:
        if extension_de(u) == ".zip":
            archivo = nombre_de_archivo(u)
            candidatos.append({"titulo": archivo, "urls": [u], "nombre": Path(archivo).stem})
    for u in urls:
        if _es_modelo_pth(u):
            carpeta = _ruta(u).rsplit("/", 1)[0]
            indices = [i for i in urls if extension_de(i) == ".index" and _ruta(i).rsplit("/", 1)[0] == carpeta]
            indices.sort(key=lambda i: (not nombre_de_archivo(i).lower().startswith("added"), i))
            archivo = nombre_de_archivo(u)
            candidatos.append({"titulo": archivo + (" + index" if indices else ""),
                               "urls": [u] + indices[:1], "nombre": Path(archivo).stem})
    return candidatos


def _abrir(url, tiempo=30):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": AGENTE}),
                                  timeout=tiempo)


def _leer_texto(url):
    with _abrir(url) as r:
        return r.read(MAX_PAGINA).decode("utf-8", "replace")


# ---------------------------------------------------------------- resolver

def _resolver_huggingface(partes, leer_texto):
    ruta = [urllib.parse.unquote(p) for p in partes.path.split("/") if p]
    if len(ruta) >= 4 and ruta[2] in ("resolve", "blob"):
        ruta[2] = "resolve"
        url = "https://huggingface.co/" + "/".join(urllib.parse.quote(p) for p in ruta) + "?download=true"
        return _agrupar([url]) if extension_de(url) else []
    repo = "/".join(ruta[:2])
    try:
        datos = json.loads(leer_texto(f"https://huggingface.co/api/models/{repo}"))
    except urllib.error.HTTPError as error:
        if error.code in (401, 403, 404):
            raise ErrorImportar("No pude entrar a ese repositorio de Hugging Face (¿es privado o "
                                "está mal escrito el link?).")
        raise
    archivos = [s["rfilename"] for s in datos.get("siblings", []) if "rfilename" in s]
    base = f"https://huggingface.co/{repo}/resolve/main/"
    urls = [base + urllib.parse.quote(a) + "?download=true" for a in archivos if extension_de(a)]
    return _agrupar(urls)


def _resolver_pagina(url, leer_texto):
    texto = html.unescape(leer_texto(url)).replace("\\/", "/")
    links = re.findall(r"https?://[^\s\"'<>\\]+", texto)
    modelos = []
    for l in links:
        l = l.rstrip(".,;")
        while l.endswith(")") and l.count(")") > l.count("("):  # paréntesis de cierre de un texto
            l = l[:-1]
        if extension_de(l) and l not in modelos:
            modelos.append(l)
    return _agrupar(modelos)


def resolver(texto, leer_texto=_leer_texto):
    """Devuelve la lista de candidatos para descargar; falla con ErrorImportar si no hay."""
    url = normalizar_enlace(texto)
    partes = urllib.parse.urlparse(url)
    host = partes.netloc.lower()
    try:
        if extension_de(url) and not host.endswith("huggingface.co"):
            candidatos = _agrupar([url])
        elif host.endswith("huggingface.co") and len([p for p in partes.path.split("/") if p]) >= 2 \
                and partes.path.split("/")[1] not in ("spaces", "datasets", "models"):
            candidatos = _resolver_huggingface(partes, leer_texto)
        else:
            candidatos = _resolver_pagina(url, leer_texto)
    except ErrorImportar:
        raise
    except urllib.error.URLError as error:
        raise ErrorImportar(f"No pude conectarme a esa página ({getattr(error, 'reason', error)}). "
                            "Revisá el link y tu conexión.")
    except (OSError, ValueError) as error:
        raise ErrorImportar(f"No pude leer esa página: {error}")
    if not candidatos:
        raise ErrorImportar(
            "No encontré ningún archivo de voz (.zip, .pth) en ese link.\n\n"
            "Si el sitio guarda el modelo en MediaFire, Google Drive o Mega, bajalo con el "
            "navegador y usá \"Importar archivo\".")
    return candidatos


# ---------------------------------------------------------------- descargar

def _bajar(url, destino, progreso, abrir=_abrir):
    """Baja `url` a `destino` (con .part mientras se descarga). progreso(bytes_bajados, total)."""
    destino = Path(destino)
    parcial = destino.with_name(destino.name + ".part")
    try:
        with abrir(url) as r, open(parcial, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            bajado = 0
            while True:
                bloque = r.read(1 << 20)
                if not bloque:
                    break
                f.write(bloque)
                bajado += len(bloque)
                progreso(bajado, total)
        parcial.replace(destino)
    except BaseException:
        try:
            parcial.unlink()
        except OSError:
            pass
        raise


def _libre(ruta):
    """Si ya existe, agrega ' (2)', ' (3)'... para no pisar nada."""
    ruta = Path(ruta)
    candidato, n = ruta, 2
    while candidato.exists():
        candidato = ruta.with_name(f"{ruta.stem} ({n}){ruta.suffix}")
        n += 1
    return candidato


def descargar(candidato, carpeta, progreso, abrir=_abrir):
    """
    Baja un candidato a la carpeta de personajes. Un .zip queda como `personajes/<nombre>.zip`
    (la app lo descomprime sola); un .pth con su .index queda en `personajes/<nombre>/`.
    Devuelve el nombre del personaje.
    """
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    urls = candidato["urls"]
    nombre = limpiar_nombre(candidato["nombre"], 50)
    n = len(urls)

    def parte(i):
        return lambda b, t: progreso((i + (b / t if t else 0.5)) / n, b, t)

    try:
        if extension_de(urls[0]) == ".zip":
            destino = _libre(carpeta / (nombre + ".zip"))
            _bajar(urls[0], destino, parte(0), abrir)
            if not zipfile.is_zipfile(destino):
                destino.unlink()
                raise ErrorImportar("Lo que se bajó no es un .zip válido (la página pidió iniciar "
                                    "sesión o el link venció). Probá bajarlo con el navegador.")
            return destino.stem
        destino = _libre(carpeta / nombre)
        destino.mkdir()
        try:
            for i, u in enumerate(urls):
                _bajar(u, destino / nombre_de_archivo(u), parte(i), abrir)
        except BaseException:
            shutil.rmtree(destino, ignore_errors=True)
            raise
        return destino.name
    except urllib.error.HTTPError as error:
        raise ErrorImportar(f"El sitio rechazó la descarga (error {error.code}).")
    except urllib.error.URLError as error:
        raise ErrorImportar(f"Se cortó la conexión ({getattr(error, 'reason', error)}).")
    except OSError as error:
        raise ErrorImportar(f"No pude guardar el archivo: {error}")


def importar_archivos(rutas, carpeta):
    """Copia .zip sueltos, o un .pth (+ .index) elegidos a mano, a la carpeta de personajes."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    rutas = [Path(r) for r in rutas]
    nombres = []
    try:
        zips = [r for r in rutas if r.suffix.lower() == ".zip"]
        for z in zips:
            if not zipfile.is_zipfile(z):
                raise ErrorImportar(f"{z.name} no es un .zip válido.")
            if z.parent.resolve() == carpeta.resolve():
                nombres.append(z.stem)
                continue
            destino = _libre(carpeta / (limpiar_nombre(z.stem, 50) + ".zip"))
            shutil.copy2(z, destino)
            nombres.append(destino.stem)
        modelos = [r for r in rutas if r.suffix.lower() in (".pth", ".index")]
        pths = [r for r in modelos if r.suffix.lower() == ".pth"
                and not r.name.upper().startswith(("D_", "G_"))]
        if modelos:
            if not pths:
                raise ErrorImportar("Falta el archivo .pth del modelo (el .index solo no alcanza).")
            destino = _libre(carpeta / limpiar_nombre(pths[0].stem, 50))
            destino.mkdir()
            for r in modelos:
                shutil.copy2(r, destino / limpiar_nombre(r.name, 120))
            nombres.append(destino.name)
    except OSError as error:
        raise ErrorImportar(f"No pude copiar los archivos: {error}")
    if not nombres:
        raise ErrorImportar("Elegí un .zip, o un .pth (con su .index).")
    return nombres


# ---------------------------------------------------------------- tarea en segundo plano

class Importacion:
    """
    Corre la importación en un hilo. La ventana la consulta cada ratito (no se toca tkinter desde
    el hilo): `activa`, `fraccion` (0..1), `texto`, `error`, `candidatos` (a elegir) y `resultado`.
    """

    def __init__(self, carpeta, leer_texto=_leer_texto, abrir=_abrir):
        self.carpeta = Path(carpeta)
        self._leer, self._abrir = leer_texto, abrir
        self.activa = False
        self.fraccion = 0.0
        self.texto = ""
        self.error = None
        self.candidatos = None   # no es None cuando hay que elegir entre varios
        self.resultado = None    # nombre del personaje cuando terminó bien

    def _lanzar(self, destino, *args):
        self.activa = True
        self.error = self.resultado = self.candidatos = None
        self.fraccion = 0.0
        threading.Thread(target=destino, args=args, daemon=True).start()

    def desde_enlace(self, texto):
        if self.activa:
            return
        self._lanzar(self._buscar, texto)

    def elegir(self, candidato):
        self.candidatos = None
        self._lanzar(self._bajar, candidato)

    def cancelar_eleccion(self):
        self.candidatos = None
        self.texto = ""

    def desde_archivos(self, rutas):
        if self.activa:
            return
        self._lanzar(self._copiar, list(rutas))

    # ---- hilos
    def _buscar(self, texto):
        try:
            self.texto = "Buscando el archivo de la voz..."
            candidatos = resolver(texto, self._leer)
            if len(candidatos) == 1:
                self._bajar_directo(candidatos[0])
            else:
                self.candidatos = candidatos
                self.texto = "Elegí cuál querés importar."
                self.activa = False
        except ErrorImportar as e:
            self.error = str(e)
            self.activa = False
        except Exception as e:  # nunca dejar la barra colgada
            self.error = f"Algo salió mal: {e}"
            self.activa = False

    def _bajar(self, candidato):
        self._bajar_directo(candidato)

    def _bajar_directo(self, candidato):
        try:
            self.texto = f"Descargando {candidato['titulo']}..."

            def progreso(frac, bajado, total):
                self.fraccion = frac
                mb = bajado / 1_048_576
                self.texto = (f"Descargando {candidato['titulo']}: {mb:.0f} MB"
                              + (f" de {total / 1_048_576:.0f} MB" if total else ""))
            self.resultado = descargar(candidato, self.carpeta, progreso, self._abrir)
            self.fraccion = 1.0
            self.texto = f"Listo: {self.resultado} se agregó a tus personajes. Elegilo y tocá \"Guardar cambios\"."
        except ErrorImportar as e:
            self.error = str(e)
        except Exception as e:
            self.error = f"Algo salió mal: {e}"
        finally:
            self.activa = False

    def _copiar(self, rutas):
        try:
            nombres = importar_archivos(rutas, self.carpeta)
            self.resultado = nombres[0]
            self.fraccion = 1.0
            self.texto = f"Listo: {', '.join(nombres)} se agregó a tus personajes. Elegilo y tocá \"Guardar cambios\"."
        except ErrorImportar as e:
            self.error = str(e)
        except Exception as e:
            self.error = f"Algo salió mal: {e}"
        finally:
            self.activa = False
