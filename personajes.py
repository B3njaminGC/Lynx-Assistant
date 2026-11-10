"""
Voces de personaje (estilo RVC) con Applio, sin esperas al hablar.

La conversión de voz tarda segundos por frase, así que no se hace en el momento:
  1. Cada frase que dice el asistente se genera UNA vez, en segundo plano.
  2. El resultado queda guardado en  audios\\<personaje>\\<clave>.wav
  3. Al hablar, si la frase ya está guardada suena al instante; si todavía no, el asistente
     usa su voz normal (nunca queda mudo).

Este módulo no depende de nucleo.py (así no hay importaciones circulares): recibe el registro (log)
y las rutas desde afuera.
"""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import zipfile
from pathlib import Path

CARPETA_APPLIO_POR_DEFECTO = r"C:\Applio"
TIEMPO_MAXIMO = 60 * 60  # una hora: por si la PC es lenta y no tiene placa NVIDIA


def clave_de_frase(texto, voz_base, tono):
    """Nombre del archivo de una frase: cambia si cambia el texto, la voz base o el tono."""
    crudo = f"{texto.strip()}|{voz_base}|{tono}".encode("utf-8")
    return hashlib.sha1(crudo).hexdigest()[:14]


class Personajes:
    def __init__(self, base, log, sin_ventana=0):
        self.base = Path(base)
        self.log = log
        self.sin_ventana = sin_ventana
        self.carpeta = self.base / "personajes"   # acá se ponen los .zip o carpetas de cada personaje
        self.audios = self.base / "audios"        # frases ya convertidas
        self.registro_applio = self.base / "applio.log"
        self.trabajando = False
        self.hechas = 0
        self.total = 0
        self.mensaje = ""
        self.error = ""
        self._pendiente = None
        self._cerrojo = threading.Lock()
        self._fallidas = set()       # frases que Applio no pudo hacer en esta sesión
        self._proceso = None
        self._guiones = {}           # carpeta de Applio -> ¿su CLI usa guiones (batch-infer)?

    # ------------------------------------------------------------ personajes instalados

    @staticmethod
    def _extraer(zip_ruta, destino):
        destino = Path(destino)
        destino.mkdir(parents=True, exist_ok=True)
        raiz = destino.resolve()
        with zipfile.ZipFile(zip_ruta) as z:
            for miembro in z.infolist():
                objetivo = (destino / miembro.filename).resolve()
                if raiz != objetivo and raiz not in objetivo.parents:
                    continue  # nombre raro dentro del zip: se ignora
                z.extract(miembro, destino)

    @staticmethod
    def _archivos_del_modelo(carpeta):
        """Devuelve (pth, index) de una carpeta de personaje, o (None, None) si no hay modelo."""
        pths = [p for p in Path(carpeta).rglob("*.pth") if p.is_file()]
        if not pths:
            return None, None
        # Los D_/G_ son puntos de control de entrenamiento (enormes); el modelo es el otro .pth.
        utiles = [p for p in pths if not p.name.upper().startswith(("D_", "G_"))] or pths
        pth = sorted(utiles, key=lambda p: p.stat().st_size)[0]
        indices = [p for p in Path(carpeta).rglob("*.index") if p.is_file()]
        indices.sort(key=lambda p: (not p.name.lower().startswith("added"), p.name.lower()))
        return pth, (indices[0] if indices else None)

    def descubrir(self):
        """
        Lee la carpeta `personajes`: cada subcarpeta con un .pth es un personaje, y cada .zip se
        descomprime solo la primera vez. Devuelve {nombre: (pth, index_o_None)}.
        """
        encontrados = {}
        try:
            self.carpeta.mkdir(exist_ok=True)
            for z in sorted(self.carpeta.glob("*.zip")):
                destino = self.carpeta / z.stem
                if self._archivos_del_modelo(destino)[0] is None:
                    try:
                        self.log(f"Descomprimiendo el personaje {z.name}...")
                        self._extraer(z, destino)
                    except (zipfile.BadZipFile, OSError) as error:
                        self.log(f"No pude descomprimir {z.name}:", error)
            for carpeta in sorted(p for p in self.carpeta.iterdir() if p.is_dir()):
                pth, index = self._archivos_del_modelo(carpeta)
                if pth is not None:
                    encontrados[carpeta.name] = (pth, index)
        except OSError as error:
            self.log("No pude leer la carpeta de personajes:", error)
        return encontrados

    # ------------------------------------------------------------ Applio

    @staticmethod
    def python_de_applio(applio_dir):
        return Path(applio_dir) / "env" / "python.exe"

    def applio_instalado(self, applio_dir):
        return (self.python_de_applio(applio_dir).exists()
                and (Path(applio_dir) / "core.py").exists())

    def _correr(self, argumentos, cwd, salida):
        entorno = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        self._proceso = subprocess.Popen(argumentos, cwd=str(cwd), stdout=salida,
                                         stderr=subprocess.STDOUT, env=entorno,
                                         creationflags=self.sin_ventana)
        return self._proceso

    def _instalar_requisitos(self, applio_dir):
        """Descarga los modelos base de Applio (solo hace falta la primera vez)."""
        self.mensaje = "Applio está bajando sus modelos base (solo la primera vez)..."
        self.log("Applio: prerequisites")
        with open(self.registro_applio, "a", encoding="utf-8") as salida:
            p = self._correr([str(self.python_de_applio(applio_dir)), "core.py", "prerequisites"],
                             applio_dir, salida)
            p.wait(timeout=TIEMPO_MAXIMO)

    def _usa_guiones(self, applio_dir):
        """
        Las versiones nuevas de Applio (con click) se llaman `batch-infer --input-folder ...` y las
        viejas `batch_infer --input_folder ...`. Se le pregunta a Applio cuál es la suya.
        """
        clave = str(applio_dir)
        if clave not in self._guiones:
            guiones = True  # lo más probable: la versión actual
            try:
                entorno = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
                r = subprocess.run([str(self.python_de_applio(applio_dir)), "core.py", "--help"],
                                   cwd=str(applio_dir), capture_output=True, env=entorno, timeout=300,
                                   creationflags=self.sin_ventana)
                texto = (r.stdout + r.stderr).decode("utf-8", "replace")
                if "batch_infer" in texto and "batch-infer" not in texto:
                    guiones = False
            except Exception as error:
                self.log("No pude consultar la ayuda de Applio:", error)
            self._guiones[clave] = guiones
            self.log("Applio usa", "guiones" if guiones else "guion bajo", "en sus comandos")
        return self._guiones[clave]

    def _ultima_linea(self):
        try:
            lineas = [l.strip() for l in self.registro_applio.read_text(
                encoding="utf-8", errors="replace").splitlines() if l.strip()]
            return lineas[-1][:200] if lineas else ""
        except OSError:
            return ""

    def _convertir(self, applio_dir, pth, index, entrada, salida, tono, esperadas, publicar=None):
        """Una sola llamada a Applio para todas las frases (carga el modelo una vez)."""
        s = "-" if self._usa_guiones(applio_dir) else "_"
        orden = [str(self.python_de_applio(applio_dir)), "core.py", f"batch{s}infer",
                 f"--input{s}folder", str(entrada), f"--output{s}folder", str(salida),
                 f"--pth{s}path", str(pth), f"--index{s}path", str(index) if index else "",
                 "--pitch", str(int(tono)), f"--f0{s}method", "rmvpe",
                 f"--index{s}rate", "0.5", f"--export{s}format", "WAV"]
        self.log("Applio:", " ".join(orden))
        inicio = time.time()
        with open(self.registro_applio, "a", encoding="utf-8") as registro:
            registro.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
            registro.flush()
            proceso = self._correr(orden, applio_dir, registro)
            tamanos = {}
            while proceso.poll() is None:
                self.hechas = self._contar(salida, esperadas)
                if publicar is not None:
                    self._publicar_estables(salida, esperadas, tamanos, publicar)
                if time.time() - inicio > TIEMPO_MAXIMO:
                    proceso.kill()
                    self.log("Applio tardó demasiado; lo detuve.")
                    break
                time.sleep(0.5)
        self.hechas = self._contar(salida, esperadas)
        return proceso.returncode

    def _publicar_estables(self, salida, esperadas, tamanos, publicar):
        """
        Mientras Applio sigue trabajando, deja lista cada frase en cuanto su archivo terminó de
        escribirse (mismo tamaño en dos revisiones seguidas): así se puede probar sin esperar al final.
        """
        for clave in esperadas:
            if clave in tamanos and tamanos[clave] is None:
                continue  # ya publicada
            archivo = self._buscar_salida(salida, clave)
            if archivo is None:
                continue
            try:
                tam = archivo.stat().st_size
            except OSError:
                continue
            if tamanos.get(clave) == tam:
                if publicar(clave, archivo):
                    tamanos[clave] = None
            else:
                tamanos[clave] = tam

    @staticmethod
    def _buscar_salida(salida, clave):
        for archivo in Path(salida).glob("*" + clave + "*"):
            if archivo.suffix.lower() in (".wav", ".flac", ".mp3", ".ogg") and archivo.stat().st_size > 1000:
                return archivo
        return None

    def _contar(self, salida, esperadas):
        return sum(1 for clave in esperadas if self._buscar_salida(salida, clave) is not None)

    # ------------------------------------------------------------ reproducir

    def ruta_de(self, personaje, texto, voz_base, tono):
        return self.audios / personaje / (clave_de_frase(texto, voz_base, tono) + ".wav")

    def reproducir(self, personaje, texto, voz_base, tono, reproductor=None):
        """
        Suena la frase ya convertida. Devuelve False si todavía no está lista.
        `reproductor(bytes_wav)` permite elegir por qué dispositivo suena; sin él, el predeterminado.
        """
        ruta = self.ruta_de(personaje, texto, voz_base, tono)
        try:
            datos = ruta.read_bytes()
        except OSError:
            return False
        if reproductor is not None:
            reproductor(datos)
        else:
            import winsound
            winsound.PlaySound(datos, winsound.SND_MEMORY)  # espera a que termine de hablar
        return True

    # ------------------------------------------------------------ generar

    def faltantes(self, personaje, frases, voz_base, tono):
        unicas = list(dict.fromkeys(f.strip() for f in frases if f.strip()))  # sin repetidas
        return [f for f in unicas
                if not self.ruta_de(personaje, f, voz_base, tono).exists()
                and (personaje, f, voz_base, tono) not in self._fallidas]

    def preparar(self, personaje, frases, voz_base, tono, applio_dir, sintetizar):
        """
        Genera en segundo plano las frases que falten. `sintetizar([(texto, ruta_wav), ...])` la
        pone el motor: hace la voz base (la de Windows o Piper) en archivos WAV.
        Si ya hay un trabajo en marcha, este queda en espera.
        """
        pedido = (personaje, list(frases), voz_base, tono, applio_dir, sintetizar)
        if not self.trabajando and not self.faltantes(personaje, frases, voz_base, tono):
            self.error, self.total, self.hechas = "", 0, 0
            self.mensaje = f"Voz de {personaje} lista."  # ya estaba todo preparado
            return
        with self._cerrojo:
            if self.trabajando:
                self._pendiente = pedido
                return
            self.trabajando = True
        threading.Thread(target=self._trabajo, args=(pedido,), daemon=True,
                         name="voz-de-personaje").start()

    def reintentar_fallidas(self):
        """Olvida las frases que fallaron, para volver a intentarlas (al guardar o reabrir)."""
        self._fallidas.clear()

    def detener(self):
        """Corta la conversión en curso (por ejemplo al salir del programa)."""
        self._pendiente = None
        proceso = self._proceso
        if proceso is not None and proceso.poll() is None:
            try:
                proceso.kill()
            except OSError:
                pass

    def _trabajo(self, pedido):
        try:
            while pedido is not None:
                try:
                    self._generar(*pedido)
                except Exception as error:
                    self.error = f"Falló la voz de personaje: {error}"
                    self.log("[error de voz de personaje]", repr(error))
                with self._cerrojo:
                    pedido, self._pendiente = self._pendiente, None
                    if pedido is None:
                        self.trabajando = False
        finally:
            self.trabajando = False

    def _generar(self, personaje, frases, voz_base, tono, applio_dir, sintetizar):
        self.error = ""
        pendientes = self.faltantes(personaje, frases, voz_base, tono)
        self.total, self.hechas = len(pendientes), 0
        if not pendientes:
            self.mensaje = "Voz de personaje lista."
            return
        if not self.applio_instalado(applio_dir):
            self.error = ("Falta instalar Applio: ejecutá instalar_voz_personaje.bat "
                          "(o cambiá la carpeta de Applio en la configuración).")
            self.log(self.error, "| carpeta buscada:", applio_dir)
            return
        personajes = self.descubrir()
        if personaje not in personajes:
            self.error = f"No encuentro el personaje '{personaje}' en la carpeta personajes."
            self.log(self.error)
            return
        pth, index = personajes[personaje]

        trabajo = Path(tempfile.mkdtemp(prefix="voz_", dir=str(self._asegurar(self.audios))))
        try:
            entrada, salida = trabajo / "entrada", trabajo / "salida"
            entrada.mkdir()
            salida.mkdir()
            claves = {}
            pares = []
            for numero, frase in enumerate(pendientes):
                clave = clave_de_frase(frase, voz_base, tono)
                claves[clave] = frase
                # El prefijo numérico hace que Applio las convierta en este orden (la de prueba primero).
                pares.append((frase, str(entrada / f"{numero:03d}_{clave}.wav")))
            self.mensaje = f"Preparando la voz de {personaje}: 0 de {self.total}"
            sintetizar(pares)
            hechos_base = [p for _, p in pares if Path(p).exists()]
            if not hechos_base:
                self.error = "No pude generar la voz base para convertir."
                self.log(self.error)
                return

            esperadas = list(claves)
            destino = self._asegurar(self.audios / personaje)

            def publicar(clave, origen):
                meta = destino / (clave + ".wav")
                if meta.exists():
                    return True
                try:
                    temporal = destino / (clave + ".tmp")
                    shutil.copyfile(origen, temporal)
                    os.replace(temporal, meta)  # nunca queda un archivo a medias
                    return True
                except OSError as error:
                    self.log("No pude guardar una frase:", error)
                    return False

            codigo = self._convertir(applio_dir, pth, index, entrada, salida, tono, esperadas, publicar)
            if self.hechas == 0 and codigo not in (0, None):
                # Posible primera vez: faltan los modelos base. Se bajan y se reintenta una vez.
                self._instalar_requisitos(applio_dir)
                codigo = self._convertir(applio_dir, pth, index, entrada, salida, tono, esperadas, publicar)

            for clave, frase in claves.items():
                origen = self._buscar_salida(salida, clave)
                if origen is None:
                    self._fallidas.add((personaje, frase, voz_base, tono))
                    self.log("Applio no generó la frase:", frase)
                    continue
                publicar(clave, origen)  # las que faltaban publicar
            fallaron = self.total - self._contar(salida, esperadas)
            if fallaron:
                self.error = (f"Applio no pudo convertir {fallaron} frase(s) (código {codigo}). "
                              f"Último mensaje: {self._ultima_linea()}  (detalle en applio.log)")
            self.mensaje = (f"Voz de {personaje} lista." if not fallaron
                            else f"Voz de {personaje} lista, salvo {fallaron} frase(s).")
            self.hechas = self.total
            self.log(self.mensaje)
        finally:
            shutil.rmtree(trabajo, ignore_errors=True)

    @staticmethod
    def _asegurar(carpeta):
        Path(carpeta).mkdir(parents=True, exist_ok=True)
        return Path(carpeta)

    def estado_texto(self):
        """Una línea para mostrar en la ventana."""
        if self.trabajando:
            if self.total:
                return f"Preparando la voz del personaje: {self.hechas} de {self.total} frases..."
            return "Preparando la voz del personaje..."
        return self.error or self.mensaje


def guion_voz_base(lista_json, voz, rate):
    """Guion de PowerShell: crea todos los WAV de la voz de Windows en un solo proceso (rápido)."""
    nombre = (voz or "").replace("'", "''")
    seleccion = ""
    if nombre:
        seleccion = (f"$n='{nombre}';"
                     "foreach($v in $s.GetInstalledVoices()){"
                     "if($v.Enabled -and $n -like ('*'+$v.VoiceInfo.Name+'*')){"
                     "$s.SelectVoice($v.VoiceInfo.Name);break}};")
    ruta = str(lista_json).replace("'", "''")
    return ("Add-Type -AssemblyName System.Speech;"
            "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
            f"{seleccion}$s.Rate={int(rate)};"
            f"$items=Get-Content -Raw -Encoding UTF8 '{ruta}'|ConvertFrom-Json;"
            "foreach($i in $items){$s.SetOutputToWaveFile($i.archivo);$s.Speak($i.texto);"
            "$s.SetOutputToNull()};$s.Dispose()")


def escribir_lista(pares):
    """Archivo temporal con la lista de (texto, archivo) para el guion de PowerShell."""
    marco = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    with marco:
        json.dump([{"texto": t, "archivo": a} for t, a in pares], marco, ensure_ascii=False)
    return Path(marco.name)
