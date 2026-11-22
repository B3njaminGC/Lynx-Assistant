"""
Ventana para configurar los comandos del asistente (edita comandos.json).
Usa tkinter, que ya viene con Python: no hay que instalar nada.
"""
import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import acciones_pc
import apps_instaladas
import clic
import teclas

ARCHIVO = Path(__file__).resolve().parent / "comandos.json"

TIPOS = {
    "abrir_programa": "Abrir programa",
    "abrir_web": "Abrir página web",
    "cerrar_programa": "Cerrar programa",
    "cerrar_varios": "Cerrar varios programas",
    "apagar": "Apagar la PC",
    "cambiar_salida": "Cambiar salida de audio",
    "tecla_multimedia": "Música y volumen (pista, pausa, volumen)",
    "reproducir_musica": "Reproducir canciones en VLC",
    "enviar_teclas": "Apretar teclas (para juegos y programas)",
    "hacer_clic": "Hacer clic en un lugar de la pantalla (ej: botón JUGAR)",
    "accion_pc": "Acción de la PC",   # en la lista del diálogo se reemplaza por cada acción por separado
    "ejecutar_comando": "Ejecutar un comando o script (.bat, .ps1, .py)",
}
# Opciones de la acción de música y volumen: nombre que se muestra -> clave que guarda el comando.
MULTIMEDIA = {
    "Pista siguiente": "siguiente",
    "Pista anterior": "anterior",
    "Pausa / reproducir": "pausa",
    "Subir el volumen": "subir_volumen",
    "Bajar el volumen": "bajar_volumen",
    "Silenciar / activar sonido": "silenciar",
}
MULTIMEDIA_POR_CLAVE = {clave: nombre for nombre, clave in MULTIMEDIA.items()}
TIPO_POR_NOMBRE = {nombre: clave for clave, nombre in TIPOS.items()}
# La lista de "¿Qué tiene que hacer?": los tipos de siempre y, después, cada acción de la PC directamente.
OPCIONES_DE_ACCION = [n for t, n in TIPOS.items() if t != "accion_pc"] + list(acciones_pc.NOMBRES_PARA_VENTANA)

# Etiqueta y ayuda del campo "valor" según el tipo de acción.
VALOR_AYUDA = {
    "abrir_programa": "Programa a abrir (elegí de tus apps instaladas o buscá el archivo):",
    "abrir_web": "Dirección de la página (ej: https://www.youtube.com):",
    "cerrar_programa": "Programa a cerrar (elegilo de la lista o escribí su nombre, ej: brave.exe):",
    "cerrar_varios": "Programas a cerrar, uno por línea (agregalos de la lista o escribilos):",
    "apagar": "",
    "cambiar_salida": "Nombre (o parte) del dispositivo de sonido (ej: Speaker (Realtek):",
    "reproducir_musica": "Canciones o carpetas a reproducir, una por línea (usá los botones de abajo):",
    "tecla_multimedia": "Qué hacer (funciona con Spotify, YouTube y casi cualquier reproductor):",
    "enviar_teclas": "Teclas a apretar, una combinación por línea (ej: enter  o  ctrl+shift+m):",
    "hacer_clic": "Dónde hacer clic: tocá Marcar y poné el mouse sobre el botón durante 5 segundos:",
    "accion_pc": "",   # no necesita nada más: la acción ya se eligió arriba
    "ejecutar_comando": "Comando o archivo a ejecutar (ej: C:\\scripts\\limpiar.bat):",
}
CONFIRMAR_POR_DEFECTO = {"cerrar_programa", "cerrar_varios", "apagar"}

# El reconocedor de voz devuelve todo en minúsculas y sin tildes.
SIN_TILDES = str.maketrans("áéíóúü", "aeiouu")


def normalizar(frase):
    return " ".join(frase.lower().translate(SIN_TILDES).split())


def cargar():
    if not ARCHIVO.exists():
        return []
    with open(ARCHIVO, encoding="utf-8") as f:
        return json.load(f)


def guardar(comandos):
    with open(ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(comandos, f, ensure_ascii=False, indent=2)


def accion_en_texto(cmd):
    """Lo que se muestra en la columna "Acción" de la lista de comandos."""
    if cmd.get("tipo") == "accion_pc":
        accion = acciones_pc.POR_CLAVE.get(cmd.get("valor"))
        return accion.nombre if accion else "Acción que ya no existe"
    return TIPOS.get(cmd.get("tipo"), cmd.get("tipo"))


def valor_de_comando(cmd):
    """Lo que se muestra en la columna del programa o dirección: el nombre de la app si la elegiste de la lista."""
    if cmd.get("tipo") == "accion_pc":
        return ""
    return cmd.get("etiqueta") or valor_en_texto(cmd.get("valor", ""))


def valor_en_texto(valor):
    if isinstance(valor, dict):
        return clic.en_texto(valor)
    return ", ".join(valor) if isinstance(valor, list) else valor


try:
    from estilo import interruptor
except Exception:  # sin el tema: casilla común
    def interruptor(padre, text, variable):
        return ttk.Checkbutton(padre, text=text, variable=variable)


class Dialogo(tk.Toplevel):
    """Ventana para crear o editar un comando."""

    def __init__(self, padre, cmd=None):
        super().__init__(padre)
        self.title("Editar comando" if cmd else "Nuevo comando")
        try:
            import estilo
            estilo.preparar_ventana(self)
        except Exception:
            pass
        self.resizable(False, False)
        self.transient(padre)
        self.resultado = None

        marco = ttk.Frame(self, padding=14)
        marco.grid()

        ttk.Label(marco, text="Frase que vas a decir (sin 'Lynx'):").grid(sticky="w")
        self.var_frase = tk.StringVar(value=cmd["frase"] if cmd else "")
        ttk.Entry(marco, textvariable=self.var_frase, width=50).grid(sticky="we", pady=(0, 10))

        ttk.Label(marco, text="¿Qué tiene que hacer?").grid(sticky="w")
        self.var_tipo = tk.StringVar(value=self._nombre_de(cmd) if cmd else TIPOS["abrir_programa"])
        combo = ttk.Combobox(marco, textvariable=self.var_tipo, state="readonly",
                             values=OPCIONES_DE_ACCION, width=47, height=22)
        combo.grid(sticky="we", pady=(0, 10))
        combo.bind("<<ComboboxSelected>>", lambda e: self.cambio_tipo(True))

        self.lbl_valor = ttk.Label(marco, text="")
        self.lbl_valor.grid(sticky="w")

        self.fila_valor = ttk.Frame(marco)
        self.fila_valor.grid(sticky="we", pady=(0, 10))
        self.var_valor = tk.StringVar()
        self.ent_valor = ttk.Entry(self.fila_valor, textvariable=self.var_valor, width=40)
        self.btn_buscar = ttk.Button(self.fila_valor, text="Buscar...", command=self.buscar_programa)
        self.btn_apps = ttk.Button(self.fila_valor, text="Elegir de mis apps instaladas...", command=self.elegir_app)
        self.btn_cerrar = ttk.Button(self.fila_valor, text="Elegir de mis programas...", command=self.elegir_para_cerrar)
        self.btn_cerrar_varios = ttk.Button(self.fila_valor, text="Agregar de mis programas...",
                                            command=self.agregar_para_cerrar)
        self.destino_app = None      # si elegiste una app de la lista: cómo se abre de verdad
        self.nombre_app = None       # y cómo se llama (es lo que se ve en el campo)
        self.txt_valor = tk.Text(self.fila_valor, width=38, height=5)
        self.btn_canciones = ttk.Button(self.fila_valor, text="Agregar canciones...", command=self.agregar_canciones)
        self.btn_carpeta = ttk.Button(self.fila_valor, text="Agregar carpeta...", command=self.agregar_carpeta)
        self.posicion = None
        self.btn_marcar = ttk.Button(self.fila_valor, text="Marcar posición...", command=self.marcar_posicion)
        self.lbl_posicion = ttk.Label(self.fila_valor, text="")
        self.combo_multimedia = ttk.Combobox(self.fila_valor, values=list(MULTIMEDIA), state="readonly",
                                             width=38)

        ttk.Label(marco, text="Qué dice el asistente al hacerlo (opcional):").grid(sticky="w")
        self.var_respuesta = tk.StringVar(value=cmd.get("respuesta", "") if cmd else "")
        ttk.Entry(marco, textvariable=self.var_respuesta, width=50).grid(sticky="we", pady=(0, 10))

        self.var_confirmar = tk.BooleanVar(value=cmd.get("confirmar", False) if cmd else False)
        interruptor(marco, "Pedir confirmación antes de hacerlo",
                    self.var_confirmar).grid(sticky="w", pady=(0, 12))

        botones = ttk.Frame(marco)
        botones.grid(sticky="e")
        ttk.Button(botones, text="Cancelar", command=self.destroy).grid(row=0, column=0, padx=6)
        ttk.Button(botones, text="Guardar", command=self.aceptar).grid(row=0, column=1)

        self.cambio_tipo(False)
        if cmd:
            valor = cmd.get("valor", "")
            if isinstance(valor, list):
                self.txt_valor.insert("1.0", "\n".join(valor))
            elif cmd["tipo"] == "enviar_teclas":
                self.txt_valor.insert("1.0", valor)
            elif cmd["tipo"] == "hacer_clic":
                self.posicion = dict(valor)
                self.lbl_posicion.config(text="Posición guardada: " + clic.en_texto(valor))
            elif cmd["tipo"] == "tecla_multimedia":
                self.combo_multimedia.set(MULTIMEDIA_POR_CLAVE.get(valor, ""))
            elif cmd["tipo"] == "accion_pc":
                pass   # la acción ya quedó elegida arriba
            elif cmd["tipo"] == "abrir_programa" and cmd.get("etiqueta") and apps_instaladas.PREFIJO in str(valor):
                self.destino_app, self.nombre_app = valor, cmd["etiqueta"]
                self.var_valor.set(cmd["etiqueta"])
            else:
                self.var_valor.set(valor)

        self.grab_set()
        self.wait_visibility()
        self.focus_force()

    @staticmethod
    def _nombre_de(cmd):
        """Lo que se ve elegido en la lista para ese comando."""
        if cmd["tipo"] == "accion_pc":
            accion = acciones_pc.POR_CLAVE.get(cmd.get("valor"))
            if accion is not None:
                return acciones_pc.nombre_para_ventana(accion)
        return TIPOS.get(cmd["tipo"], TIPOS["abrir_programa"])

    def tipo_actual(self):
        elegido = self.var_tipo.get()
        return "accion_pc" if elegido in acciones_pc.NOMBRES_PARA_VENTANA else TIPO_POR_NOMBRE[elegido]

    def cambio_tipo(self, es_cambio_del_usuario):
        tipo = self.tipo_actual()
        self.lbl_valor.config(text=VALOR_AYUDA[tipo])
        for w in (self.ent_valor, self.btn_buscar, self.btn_apps, self.btn_cerrar,
                  self.btn_cerrar_varios, self.txt_valor, self.combo_multimedia,
                  self.btn_canciones, self.btn_carpeta, self.btn_marcar, self.lbl_posicion):
            w.grid_forget()
        if tipo == "hacer_clic":
            self.btn_marcar.grid(row=0, column=0, sticky="w")
            self.lbl_posicion.grid(row=1, column=0, sticky="w", pady=(6, 0))
            if es_cambio_del_usuario:
                self.var_confirmar.set(False)
            return
        if tipo in ("cerrar_varios", "enviar_teclas"):
            self.txt_valor.grid(row=0, column=0)
            if tipo == "cerrar_varios":
                self.btn_cerrar_varios.grid(row=1, column=0, sticky="w", pady=(6, 0))
        elif tipo == "reproducir_musica":
            self.txt_valor.grid(row=0, column=0, columnspan=2)
            self.btn_canciones.grid(row=1, column=0, sticky="w", pady=(6, 0))
            self.btn_carpeta.grid(row=1, column=1, sticky="w", pady=(6, 0), padx=(6, 0))
        elif tipo == "tecla_multimedia":
            self.combo_multimedia.grid(row=0, column=0, sticky="we")
            if not self.combo_multimedia.get():
                self.combo_multimedia.set(next(iter(MULTIMEDIA)))
        elif tipo == "accion_pc":
            if es_cambio_del_usuario:
                self._cambio_accion()
            return
        elif tipo != "apagar":
            self.ent_valor.grid(row=0, column=0, sticky="we")
            if tipo == "abrir_programa":
                self.btn_buscar.grid(row=0, column=1, padx=(6, 0))
                self.btn_apps.grid(row=1, column=0, sticky="w", pady=(6, 0))
            elif tipo == "cerrar_programa":
                self.btn_cerrar.grid(row=1, column=0, sticky="w", pady=(6, 0))
        if es_cambio_del_usuario:
            self.var_confirmar.set(tipo in CONFIRMAR_POR_DEFECTO)

    def _cambio_accion(self):
        """Al elegir una acción: marca si pide confirmación (reiniciar, cerrar sesión...)."""
        accion = acciones_pc.POR_CLAVE.get(acciones_pc.NOMBRES_PARA_VENTANA.get(self.var_tipo.get(), ""))
        if accion is not None:
            self.var_confirmar.set(accion.confirmar)

    def marcar_posicion(self, restantes=5):
        """Cuenta regresiva para que lleves el mouse al botón; después anota dónde quedó."""
        if restantes > 0:
            self.lbl_posicion.config(text=f"Poné el mouse sobre el botón... {restantes}")
            self.after(1000, lambda: self.marcar_posicion(restantes - 1))
            return
        try:
            self.posicion = clic.marcar_posicion()
        except Exception as error:
            self.lbl_posicion.config(text="No pude leer el mouse.")
            messagebox.showwarning("No pude marcarlo", str(error), parent=self)
            return
        self.lbl_posicion.config(text="Posición guardada: " + clic.en_texto(self.posicion))

    def _agregar_lineas(self, rutas):
        actual = self.txt_valor.get("1.0", "end").strip()
        nuevas = "\n".join(r.replace("/", "\\") for r in rutas)
        self.txt_valor.delete("1.0", "end")
        self.txt_valor.insert("1.0", (actual + "\n" if actual else "") + nuevas)

    def agregar_canciones(self):
        rutas = filedialog.askopenfilenames(
            parent=self, title="Elegí las canciones (podés marcar varias)",
            filetypes=[("Música y video", "*.mp3 *.flac *.wav *.m4a *.aac *.ogg *.opus *.wma *.mp4 *.mkv"),
                       ("Todos", "*.*")])
        if rutas:
            self._agregar_lineas(rutas)

    def agregar_carpeta(self):
        ruta = filedialog.askdirectory(parent=self, title="Elegí la carpeta (suenan todas sus canciones)")
        if ruta:
            self._agregar_lineas([ruta])

    def elegir_app(self):
        """Abre la lista de apps instaladas (como el "Abrir con" de Windows) y deja la que elijas."""
        elegidas = SelectorDeApps.pedir(self, "abrir")
        if elegidas:
            self.nombre_app, self.destino_app = elegidas[0]
            self.var_valor.set(self.nombre_app)

    def elegir_para_cerrar(self):
        elegidas = SelectorDeApps.pedir(self, "cerrar")
        if elegidas:
            self.var_valor.set(elegidas[0][1])

    def agregar_para_cerrar(self):
        elegidas = SelectorDeApps.pedir(self, "cerrar", varios=True)
        if elegidas:
            actual = {l.strip().lower() for l in self.txt_valor.get("1.0", "end").splitlines()}
            self._agregar_lineas([exe for _, exe in elegidas if exe.lower() not in actual])

    def buscar_programa(self):
        ruta = filedialog.askopenfilename(
            parent=self, title="Elegí el programa",
            filetypes=[("Programas y accesos directos", "*.exe *.lnk"), ("Todos", "*.*")])
        if ruta:
            self.var_valor.set(ruta.replace("/", "\\"))

    def aceptar(self):
        frase = normalizar(self.var_frase.get())
        tipo = self.tipo_actual()
        if not frase:
            messagebox.showwarning("Falta algo", "Escribí la frase que vas a decir.", parent=self)
            return

        if tipo == "apagar":
            valor = ""
        elif tipo == "tecla_multimedia":
            valor = MULTIMEDIA.get(self.combo_multimedia.get(), "")
        elif tipo == "accion_pc":
            valor = acciones_pc.NOMBRES_PARA_VENTANA.get(self.var_tipo.get(), "")
        elif tipo == "reproducir_musica":
            valor = [l.strip().strip('"') for l in self.txt_valor.get("1.0", "end").splitlines() if l.strip()]
        elif tipo == "hacer_clic":
            if not self.posicion:
                messagebox.showwarning("Falta algo", "Tocá Marcar posición y poné el mouse sobre el botón.",
                                       parent=self)
                return
            valor = dict(self.posicion, volver=True)
        elif tipo == "enviar_teclas":
            valor = [l.strip() for l in self.txt_valor.get("1.0", "end").splitlines() if l.strip()]
            try:
                teclas.analizar(valor)
            except teclas.ErrorTecla as error:
                messagebox.showwarning("Revisá las teclas", str(error), parent=self)
                return
        elif tipo == "cerrar_varios":
            lineas = [l.strip() for l in self.txt_valor.get("1.0", "end").splitlines() if l.strip()]
            valor = [l if l.lower().endswith(".exe") else l + ".exe" for l in lineas]
        else:
            valor = self.var_valor.get().strip().strip('"')
            if tipo == "abrir_programa" and self.destino_app and valor == self.nombre_app:
                valor = self.destino_app     # eligió una app de la lista
            if tipo == "cerrar_programa" and valor and not valor.lower().endswith(".exe"):
                valor += ".exe"

        if tipo not in ("apagar", "accion_pc") and not valor:
            messagebox.showwarning("Falta algo", "Completá el campo de abajo.", parent=self)
            return

        self.resultado = {"frase": frase, "tipo": tipo, "valor": valor,
                          "respuesta": self.var_respuesta.get().strip(),
                          "confirmar": self.var_confirmar.get()}
        if tipo == "abrir_programa" and valor == self.destino_app:
            self.resultado["etiqueta"] = self.nombre_app     # para mostrar "Spotify" y no la ruta técnica
        self.destroy()


class SelectorDeApps(tk.Toplevel):
    """Lista con buscador para elegir apps, sin escribir nada.
    modo "abrir": tus apps instaladas. modo "cerrar": los programas abiertos ahora y los instalados.
    `SelectorDeApps.pedir(ventana, modo, varios)` devuelve una lista de (texto, valor) o [] si cancelaste."""
    _guardadas = {}   # la lista se pide una sola vez por sesión y modo (tarda un par de segundos)

    @classmethod
    def pedir(cls, padre, modo, varios=False):
        selector = cls(padre, modo, varios)
        padre.wait_window(selector)
        return selector.resultado

    def __init__(self, padre, modo, varios):
        super().__init__(padre)
        self.modo, self.varios = modo, varios
        self.title("Mis apps instaladas" if modo == "abrir" else "Mis programas")
        self.transient(padre)
        self.resultado = []
        self.apps = []
        marco = ttk.Frame(self, padding=14)
        marco.grid()
        ayuda = "Escribí para buscar y elegí la app (doble clic para aceptar):" if modo == "abrir" else \
            ("Elegí los programas (Ctrl o Shift para varios):" if varios else
             "Elegí el programa (doble clic para aceptar):")
        ttk.Label(marco, text=ayuda).grid(sticky="w")
        self.var_busqueda = tk.StringVar()
        self.var_busqueda.trace_add("write", lambda *a: self._mostrar())
        entrada = ttk.Entry(marco, textvariable=self.var_busqueda, width=50)
        entrada.grid(sticky="we", pady=(0, 8))
        cuerpo = ttk.Frame(marco)
        cuerpo.grid(sticky="nsew")
        self.lista = tk.Listbox(cuerpo, width=60, height=16, activestyle="none", exportselection=False,
                                selectmode="extended" if varios else "browse")
        self.lista.grid(row=0, column=0)
        barra = ttk.Scrollbar(cuerpo, orient="vertical", command=self.lista.yview)
        barra.grid(row=0, column=1, sticky="ns")
        self.lista.configure(yscrollcommand=barra.set)
        self.lista.bind("<Double-1>", lambda e: self.aceptar())
        self.lista.bind("<Return>", lambda e: self.aceptar())
        entrada.bind("<Return>", lambda e: self.aceptar())
        self.var_estado = tk.StringVar(value="Buscando tus apps...")
        ttk.Label(marco, textvariable=self.var_estado).grid(sticky="w", pady=(8, 0))
        botones = ttk.Frame(marco)
        botones.grid(sticky="e", pady=(8, 0))
        ttk.Button(botones, text="Cancelar", command=self.destroy).grid(row=0, column=0, padx=6)
        ttk.Button(botones, text="Elegir", command=self.aceptar).grid(row=0, column=1)

        if modo in SelectorDeApps._guardadas:
            self._llegaron(SelectorDeApps._guardadas[modo])
        else:
            self._pedido = {}
            threading.Thread(target=self._buscar_en_segundo_plano, daemon=True).start()
            self.after(150, self._esperar)
        self.grab_set()
        self.wait_visibility()
        entrada.focus_force()

    def _buscar_en_segundo_plano(self):
        try:
            if self.modo == "abrir":
                self._pedido["apps"] = apps_instaladas.leer()
            else:
                try:
                    instaladas = apps_instaladas.leer()
                except Exception:
                    instaladas = []     # aunque falle la lista de instaladas, sirven los abiertos
                self._pedido["apps"] = apps_instaladas.para_cerrar(apps_instaladas.leer_abiertas(), instaladas)
        except Exception as error:
            self._pedido["error"] = str(error)

    def _esperar(self):
        if not self.winfo_exists():
            return
        if "apps" in self._pedido:
            self._llegaron(self._pedido["apps"])
        elif "error" in self._pedido:
            self._llegaron(None)
        else:
            self.after(150, self._esperar)

    def _llegaron(self, apps):
        if apps is None:
            self.var_estado.set("No pude leer la lista. Cerrá esto y escribí el nombre a mano.")
            return
        SelectorDeApps._guardadas[self.modo] = apps
        self.apps = apps
        self._mostrar()

    def _mostrar(self):
        self.visibles = apps_instaladas.filtrar(self.apps, self.var_busqueda.get())
        self.lista.delete(0, "end")
        for texto, _ in self.visibles:
            self.lista.insert("end", texto)
        if self.visibles:
            self.lista.selection_set(0)
        self.var_estado.set(f"{len(self.visibles)} de {len(self.apps)}")

    def aceptar(self):
        seleccion = self.lista.curselection()
        if seleccion:
            self.resultado = [self.visibles[i] for i in seleccion]
            self.destroy()


class Ventana(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Comandos del asistente")
        self.geometry("820x420")
        self.comandos = cargar()

        marco = ttk.Frame(self, padding=10)
        marco.pack(fill="both", expand=True)
        marco.rowconfigure(1, weight=1)
        marco.columnconfigure(0, weight=1)

        ttk.Label(marco, text="Decí 'Lynx' y después una de estas frases. "
                              "Los cambios se aplican solos, sin reiniciar el asistente."
                  ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        columnas = ("frase", "accion", "valor", "confirma")
        self.tabla = ttk.Treeview(marco, columns=columnas, show="headings", selectmode="browse")
        for col, titulo, ancho in (("frase", "Frase", 170), ("accion", "Acción", 150),
                                   ("valor", "Programa / dirección", 350), ("confirma", "Confirma", 70)):
            self.tabla.heading(col, text=titulo)
            self.tabla.column(col, width=ancho, anchor="w")
        self.tabla.grid(row=1, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(marco, orient="vertical", command=self.tabla.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        self.tabla.configure(yscrollcommand=scroll.set)
        self.tabla.bind("<Double-1>", lambda e: self.editar())
        self.tabla.bind("<Delete>", lambda e: self.borrar())

        botones = ttk.Frame(marco)
        botones.grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))
        ttk.Button(botones, text="Agregar", command=self.agregar).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(botones, text="Editar", command=self.editar).grid(row=0, column=1, padx=6)
        ttk.Button(botones, text="Borrar", command=self.borrar).grid(row=0, column=2, padx=6)

        self.refrescar()

    def refrescar(self):
        self.tabla.delete(*self.tabla.get_children())
        for i, c in enumerate(self.comandos):
            self.tabla.insert("", "end", iid=str(i), values=(
                c["frase"], accion_en_texto(c), valor_de_comando(c),
                "Sí" if c.get("confirmar") else "No"))

    def seleccionado(self):
        sel = self.tabla.selection()
        return int(sel[0]) if sel else None

    def pedir(self, cmd=None):
        dialogo = Dialogo(self, cmd)
        self.wait_window(dialogo)
        return dialogo.resultado

    def agregar(self):
        nuevo = self.pedir()
        if nuevo:
            self.comandos.append(nuevo)
            guardar(self.comandos)
            self.refrescar()

    def editar(self):
        i = self.seleccionado()
        if i is None:
            messagebox.showinfo("Editar", "Elegí un comando de la lista.")
            return
        editado = self.pedir(self.comandos[i])
        if editado:
            self.comandos[i] = editado
            guardar(self.comandos)
            self.refrescar()

    def borrar(self):
        i = self.seleccionado()
        if i is None:
            messagebox.showinfo("Borrar", "Elegí un comando de la lista.")
            return
        if messagebox.askyesno("Borrar", f"¿Borrar el comando '{self.comandos[i]['frase']}'?"):
            del self.comandos[i]
            guardar(self.comandos)
            self.refrescar()


if __name__ == "__main__":
    Ventana().mainloop()
