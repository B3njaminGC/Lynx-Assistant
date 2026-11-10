"""
Interfaz del asistente: el círculo animado y la ventana de configuración.
Todo corre en el hilo principal de tkinter; el motor de voz solo se consulta.
"""
import math
import os
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

import estilo
import importar
import nucleo
from configurar import TIPOS, Dialogo, valor_en_texto

TRANSPARENTE = "#010101"  # color que Windows deja invisible alrededor del círculo
COLORES = {  # estado: (color principal, color del halo)
    "escuchando": ("#4f8cff", "#9cc0ff"),   # azul
    "ejecutando": ("#34d399", "#a7f3d0"),   # verde
    "hablando": ("#8b6cff", "#c9b8ff"),     # violeta
}
MIC_PREDETERMINADO = "Predeterminado de Windows"
VOZ_PREDETERMINADA = "Predeterminada de Windows"
SIN_PERSONAJE = "Ninguno (voz normal)"
SALIDA_PREDETERMINADA = "Predeterminada de Windows"
SITIOS_DE_VOCES = [("voice-models.com", "https://voice-models.com/"),
                   ("aivoices.gg", "https://aivoices.gg/"),
                   ("Hugging Face", "https://huggingface.co/models?search=rvc")]


class Circulo:
    """Círculo sin bordes, siempre arriba, sobre la barra de tareas en el borde izquierdo."""

    def __init__(self, raiz, config, obtener_estado, obtener_nivel):
        self.raiz = raiz
        self.config = config
        self.obtener_estado = obtener_estado
        self.obtener_nivel = obtener_nivel
        self.ventana = None
        self.visible = False
        self.t = 0.0
        self.nivel_suave = 0.0
        self.tam = 64
        self.crear()
        self._animar()

    def _posicion(self, tam):
        """Esquina inferior izquierda del área de trabajo (justo arriba de la barra de tareas)."""
        try:
            import ctypes
            from ctypes import wintypes
            area = wintypes.RECT()
            ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(area), 0)  # SPI_GETWORKAREA
            return area.left + 12, area.bottom - tam - 12
        except Exception:
            return 12, self.raiz.winfo_screenheight() - tam - 60

    def _clic_a_traves(self):
        """Que el círculo no robe el foco ni bloquee los clics de lo que tiene debajo."""
        try:
            import ctypes
            self.ventana.update_idletasks()
            usuario = ctypes.windll.user32
            ident = self.ventana.winfo_id()
            hwnd = usuario.GetParent(ident) or ident
            estilo = usuario.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
            # LAYERED | TRANSPARENT | TOOLWINDOW | NOACTIVATE
            usuario.SetWindowLongW(hwnd, -20, estilo | 0x80000 | 0x20 | 0x80 | 0x08000000)
        except Exception as error:
            nucleo.log("[círculo] no pude hacerlo transparente a los clics:", error)

    def crear(self):
        """(Re)crea la ventana del círculo, por ejemplo cuando cambia el tamaño."""
        if self.ventana is not None:
            self.ventana.destroy()
        self.tam = int(self.config.get("tamano_circulo", 64))
        ventana = tk.Toplevel(self.raiz)
        ventana.overrideredirect(True)
        ventana.attributes("-topmost", True)
        ventana.configure(bg=TRANSPARENTE)
        ventana.attributes("-transparentcolor", TRANSPARENTE)
        x, y = self._posicion(self.tam)
        ventana.geometry(f"{self.tam}x{self.tam}+{x}+{y}")
        self.lienzo = tk.Canvas(ventana, width=self.tam, height=self.tam,
                                bg=TRANSPARENTE, highlightthickness=0)
        self.lienzo.pack()
        self.ventana = ventana
        self._clic_a_traves()
        ventana.withdraw()
        self.visible = False

    def _dibujar(self, estado):
        principal, claro = COLORES[estado]
        centro = self.tam / 2
        pulso = (math.sin(self.t) + 1) / 2
        if estado == "escuchando":
            # Reacciona a la voz: cuanto más fuerte hablás, más grande el brillo.
            factor = 0.12 * pulso + 0.9 * self.nivel_suave
        else:
            factor = 0.45 * pulso
        factor = min(1.0, factor)
        radio_nucleo = centro * 0.50
        radio_brillo = centro * (0.66 + 0.34 * factor)
        c = self.lienzo
        c.delete("all")
        # Resplandor: anillos que se van apagando hacia afuera (sin transparencia real).
        pasos = 6
        for k in range(pasos):
            r = radio_brillo - (radio_brillo - radio_nucleo) * k / pasos
            color = estilo.mezclar("#0d0e14", principal, 0.25 + 0.75 * (k / pasos) ** 1.3)
            c.create_oval(centro - r, centro - r, centro + r, centro + r, fill=color, outline="")
        # Núcleo con degradado: más claro hacia el centro.
        capas = 7
        for k in range(capas):
            r = radio_nucleo * (1 - k / capas * 0.78)
            color = estilo.mezclar(principal, claro, (k / (capas - 1)) ** 1.4 * 0.75)
            desplazo = radio_nucleo * 0.16 * (k / capas)   # la luz viene de arriba a la izquierda
            c.create_oval(centro - r - desplazo, centro - r - desplazo,
                          centro + r - desplazo, centro + r - desplazo, fill=color, outline="")
        # Aro fino que gira cuando está escuchando o hablando.
        if estado != "ejecutando":
            r = radio_brillo
            c.create_arc(centro - r, centro - r, centro + r, centro + r,
                         start=(self.t * 60) % 360, extent=70, style="arc",
                         outline=claro, width=max(2, round(self.tam / 28)))

    def _animar(self):
        try:
            estado = self.obtener_estado() if self.config.get("mostrar_circulo", True) else "dormido"
            if estado in COLORES:
                if not self.visible:
                    self.ventana.deiconify()
                    self.ventana.attributes("-topmost", True)
                    self.visible = True
                self.t += 0.35 if estado == "hablando" else 0.18
                self.nivel_suave += (self.obtener_nivel() - self.nivel_suave) * 0.35
                self._dibujar(estado)
            elif self.visible:
                self.ventana.withdraw()
                self.visible = False
        except tk.TclError:
            return  # la aplicación se está cerrando
        except Exception as error:
            nucleo.log("[círculo] error al animar:", error)
        self.raiz.after(40, self._animar)


class VentanaConfiguracion(tk.Toplevel):
    """Comandos, micrófono y opciones generales."""

    def __init__(self, raiz, app):
        super().__init__(raiz)
        self.app = app
        self.vivo = True
        self.title("Lynx - Configuración")
        estilo.preparar_ventana(self)
        self.geometry("900x760")
        self.minsize(780, 560)
        self.protocol("WM_DELETE_WINDOW", self.cerrar)

        # El pie va primero y pegado abajo: así el botón Guardar nunca queda tapado.
        pie = ttk.Frame(self)
        pie.pack(side="bottom", fill="x", padx=14, pady=14)
        self.var_pie = tk.StringVar(value="")
        ttk.Label(pie, textvariable=self.var_pie, style="Suave.TLabel").pack(side="left")
        ttk.Button(pie, text="Guardar cambios", style="Accent.TButton",
                   command=self.guardar).pack(side="right")
        ttk.Button(pie, text="Salir del asistente",
                   command=self.salir_del_asistente).pack(side="right", padx=(0, 10))

        self._encabezado()
        cuaderno = ttk.Notebook(self)
        cuaderno.pack(side="top", fill="both", expand=True, padx=14, pady=(6, 0))
        self._pestana_comandos(cuaderno)
        self._pestana_microfono(cuaderno)
        self._pestana_general(cuaderno)
        self._pestana_personaje(cuaderno)

        self._tic()

    def _encabezado(self):
        cab = ttk.Frame(self)
        cab.pack(side="top", fill="x", padx=18, pady=(14, 4))
        try:
            from PIL import ImageTk
            self._logo = ImageTk.PhotoImage(estilo.crear_icono(44))
            ttk.Label(cab, image=self._logo).pack(side="left", padx=(0, 12))
        except Exception:
            pass
        textos = ttk.Frame(cab)
        textos.pack(side="left")
        ttk.Label(textos, text="Lynx", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(textos, text="Tu asistente de voz, sin internet", style="Suave.TLabel").pack(anchor="w")

    # ------------------------------------------------------------ comandos

    def _pestana_comandos(self, cuaderno):
        marco = ttk.Frame(cuaderno, padding=10)
        cuaderno.add(marco, text="Comandos")
        marco.rowconfigure(2, weight=1)
        marco.columnconfigure(0, weight=1)

        ttk.Label(marco, text="Decí \"Lynx\" y después una de estas frases. Los cambios de esta "
                              "pestaña se aplican al instante."
                  ).grid(row=0, column=0, columnspan=2, sticky="w")
        self.var_avisos = tk.StringVar(value="")
        ttk.Label(marco, textvariable=self.var_avisos, wraplength=800, foreground=estilo.P["aviso"]
                  ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 8))

        self.tabla = ttk.Treeview(marco, columns=("frase", "accion", "valor", "respuesta", "confirma"),
                                  show="headings", selectmode="browse")
        for col, titulo, ancho in (("frase", "Frase", 160), ("accion", "Acción", 130),
                                   ("valor", "Programa / dirección", 260), ("respuesta", "Responde", 170),
                                   ("confirma", "Confirma", 65)):
            self.tabla.heading(col, text=titulo)
            self.tabla.column(col, width=ancho, anchor="w")
        self.tabla.grid(row=2, column=0, sticky="nsew")
        barra = ttk.Scrollbar(marco, orient="vertical", command=self.tabla.yview)
        barra.grid(row=2, column=1, sticky="ns")
        self.tabla.configure(yscrollcommand=barra.set)
        self.tabla.bind("<Double-1>", lambda e: self.editar())
        self.tabla.bind("<Delete>", lambda e: self.borrar())

        botones = ttk.Frame(marco)
        botones.grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))
        ttk.Button(botones, text="Add", command=self.agregar).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(botones, text="Editar", command=self.editar).grid(row=0, column=1, padx=6)
        ttk.Button(botones, text="Borrar", command=self.borrar).grid(row=0, column=2, padx=6)

        self.comandos = nucleo.leer_comandos()
        self.refrescar()

    def refrescar(self):
        self.tabla.delete(*self.tabla.get_children())
        for i, c in enumerate(self.comandos):
            self.tabla.insert("", "end", iid=str(i), values=(
                c["frase"], TIPOS.get(c["tipo"], c["tipo"]), valor_en_texto(c.get("valor", "")),
                c.get("respuesta") or "(automática)", "Sí" if c.get("confirmar") else "No"))

    def _seleccionado(self):
        seleccion = self.tabla.selection()
        return int(seleccion[0]) if seleccion else None

    def _pedir(self, comando=None):
        dialogo = Dialogo(self, comando)
        self.wait_window(dialogo)
        return dialogo.resultado

    def _guardar_comandos(self):
        nucleo.guardar_comandos(self.comandos)
        if self.app.motor is not None:
            self.app.motor.recargar.set()
        self.refrescar()

    def agregar(self):
        nuevo = self._pedir()
        if nuevo:
            self.comandos.append(nuevo)
            self._guardar_comandos()

    def editar(self):
        i = self._seleccionado()
        if i is None:
            messagebox.showinfo("Editar", "Elegí un comando de la lista.", parent=self)
            return
        editado = self._pedir(self.comandos[i])
        if editado:
            self.comandos[i] = editado
            self._guardar_comandos()

    def borrar(self):
        i = self._seleccionado()
        if i is None:
            messagebox.showinfo("Borrar", "Elegí un comando de la lista.", parent=self)
            return
        if messagebox.askyesno("Borrar", f"¿Borrar el comando '{self.comandos[i]['frase']}'?",
                               parent=self):
            del self.comandos[i]
            self._guardar_comandos()

    # ------------------------------------------------------------ micrófono

    def _pestana_microfono(self, cuaderno):
        marco = ttk.Frame(cuaderno, padding=16)
        cuaderno.add(marco, text="Micrófono")

        ttk.Label(marco, text="Micrófono con el que te escucha el asistente:").pack(anchor="w")
        try:
            self.microfonos = nucleo.listar_microfonos()
        except Exception as error:
            nucleo.log("No pude listar los micrófonos:", error)
            self.microfonos = []
        nombres = [MIC_PREDETERMINADO] + [nombre for _, nombre in self.microfonos]
        actual = self.app.config.get("microfono")
        self.var_mic = tk.StringVar(value=actual if actual in nombres else MIC_PREDETERMINADO)
        ttk.Combobox(marco, textvariable=self.var_mic, values=nombres, state="readonly",
                     width=70).pack(anchor="w", pady=8)

        ttk.Label(marco, text="Nivel de entrada: hablá y mirá si la barra se mueve."
                  ).pack(anchor="w", pady=(18, 4))
        self.barra_nivel = ttk.Progressbar(marco, maximum=100, length=400)
        self.barra_nivel.pack(anchor="w")
        ttk.Label(marco, text="Después de elegir otro micrófono, tocá \"Guardar cambios\".",
                  foreground=estilo.P["suave"]).pack(anchor="w", pady=(18, 0))

    # ------------------------------------------------------------ voz de personaje

    def _pestana_personaje(self, cuaderno):
        cfg = self.app.config
        marco = ttk.Frame(cuaderno, padding=16)
        cuaderno.add(marco, text="Voz de personaje")

        self.var_personaje = tk.StringVar(value=cfg.get("personaje") or SIN_PERSONAJE)
        self.var_tono = tk.IntVar(value=int(cfg.get("personaje_tono", 0)))
        self.var_applio = tk.StringVar(value=cfg.get("applio_dir") or r"C:\Applio")
        self.var_estado_personaje = tk.StringVar(value="")
        self.personajes_cargados = False
        self.lista_personajes = None
        self.importacion = importar.Importacion(nucleo.GESTOR.carpeta)
        self.var_enlace = tk.StringVar(value="")
        self.var_importar = tk.StringVar(value="")
        self.dialogo_eleccion = None

        ttk.Label(marco, text="Con una voz de personaje el asistente habla con la voz de un personaje "
                              "(modelos RVC). Cada frase se prepara una sola vez en segundo plano y "
                              "después suena al instante; mientras no esté lista, usa la voz normal.",
                  wraplength=800, justify="left", style="Suave.TLabel").pack(anchor="w", pady=(0, 10))

        ttk.Label(marco, text="Personaje:").pack(anchor="w")
        fila = ttk.Frame(marco)
        fila.pack(anchor="w", pady=4)
        self.combo_personaje = ttk.Combobox(fila, textvariable=self.var_personaje, state="readonly",
                                            values=[SIN_PERSONAJE], width=40)
        self.combo_personaje.grid(row=0, column=0)
        ttk.Button(fila, text="Probar personaje", command=self.probar_personaje
                   ).grid(row=0, column=1, padx=8)
        ttk.Button(fila, text="Abrir carpeta de personajes", command=self.abrir_carpeta_personajes
                   ).grid(row=0, column=2)

        ttk.Separator(marco).pack(fill="x", pady=(14, 8))
        ttk.Label(marco, text="Agregar personajes", style="Seccion.TLabel").pack(anchor="w")
        fila_web = ttk.Frame(marco)
        fila_web.pack(anchor="w", pady=(6, 4))
        ttk.Label(fila_web, text="1. Buscá una voz en:").grid(row=0, column=0, padx=(0, 8))
        for i, (nombre, url) in enumerate(SITIOS_DE_VOCES):
            ttk.Button(fila_web, text=nombre, command=lambda u=url: webbrowser.open(u)
                       ).grid(row=0, column=i + 1, padx=3)
        fila_link = ttk.Frame(marco)
        fila_link.pack(anchor="w", pady=4)
        ttk.Label(fila_link, text="2. Pegá el link de la voz:").grid(row=0, column=0, padx=(0, 8))
        ttk.Entry(fila_link, textvariable=self.var_enlace, width=42).grid(row=0, column=1)
        ttk.Button(fila_link, text="Pegar", command=self.pegar_enlace).grid(row=0, column=2, padx=(6, 0))
        self.boton_importar = ttk.Button(fila_link, text="Importar", style="Accent.TButton",
                                         command=self.importar_enlace)
        self.boton_importar.grid(row=0, column=3, padx=(6, 0))
        fila_arch = ttk.Frame(marco)
        fila_arch.pack(anchor="w", pady=4)
        ttk.Label(fila_arch, text="¿Ya bajaste el archivo?").grid(row=0, column=0, padx=(0, 8))
        ttk.Button(fila_arch, text="Importar archivo (.zip, .pth)...", command=self.importar_archivo
                   ).grid(row=0, column=1)
        self.barra_importar = ttk.Progressbar(marco, maximum=100, length=520)
        self.barra_importar.pack(anchor="w", pady=(6, 0))
        ttk.Label(marco, textvariable=self.var_importar, wraplength=800, justify="left",
                  style="Estado.TLabel").pack(anchor="w", pady=(4, 0))
        ttk.Separator(marco).pack(fill="x", pady=(10, 0))

        ttk.Label(marco, text="Tono (semitonos). Bajalo (-12) si la voz base es de mujer y el personaje "
                              "es hombre; subilo en el caso contrario:").pack(anchor="w", pady=(14, 0))
        tk.Scale(marco, from_=-12, to=12, orient="horizontal", length=320,
                 variable=self.var_tono).pack(anchor="w")

        ttk.Label(marco, text="Carpeta donde está instalado Applio:").pack(anchor="w", pady=(10, 0))
        ttk.Entry(marco, textvariable=self.var_applio, width=50).pack(anchor="w", pady=4)

        ttk.Label(marco, text="Después de cambiar algo tocá \"Guardar cambios\": ahí empieza a preparar las frases.",
                  wraplength=800, justify="left", style="Suave.TLabel").pack(anchor="w", pady=(10, 0))
        ttk.Label(marco, textvariable=self.var_estado_personaje, wraplength=780, justify="left",
                  foreground=estilo.P["acento_claro"]).pack(anchor="w", pady=(10, 0))

        # Buscar personajes puede descomprimir un zip: se hace fuera del hilo de la ventana.
        threading.Thread(target=self._buscar_personajes, daemon=True).start()

    def _buscar_personajes(self):
        self.lista_personajes = sorted(nucleo.GESTOR.descubrir())

    def probar_personaje(self):
        if self.app.motor is not None:
            self.app.motor.probar_personaje()

    def abrir_carpeta_personajes(self):
        carpeta = nucleo.GESTOR.carpeta
        try:
            carpeta.mkdir(exist_ok=True)
            os.startfile(str(carpeta))
        except OSError as error:
            messagebox.showerror("No pude abrirla", str(error), parent=self)

    # ---- importar personajes
    def pegar_enlace(self):
        try:
            self.var_enlace.set(self.clipboard_get().strip())
        except tk.TclError:
            messagebox.showinfo("Pegar", "No hay nada copiado todavía.", parent=self)

    def importar_enlace(self):
        if self.importacion.activa:
            return
        self.var_importar.set("")
        self.importacion.desde_enlace(self.var_enlace.get())

    def importar_archivo(self):
        if self.importacion.activa:
            return
        rutas = filedialog.askopenfilenames(
            parent=self, title="Elegí el .zip del personaje (o su .pth y su .index)",
            filetypes=[("Modelos de voz", "*.zip *.pth *.index"), ("Todos los archivos", "*.*")])
        if rutas:
            self.var_importar.set("")
            self.importacion.desde_archivos(rutas)

    def _elegir_archivo(self, candidatos):
        """Ventanita para elegir cuando el link tiene varios archivos."""
        dialogo = tk.Toplevel(self)
        self.dialogo_eleccion = dialogo
        dialogo.title("Elegí qué importar")
        estilo.preparar_ventana(dialogo)
        dialogo.geometry("560x340")
        dialogo.transient(self)
        ttk.Label(dialogo, text="Ese link tiene varios archivos. ¿Cuál querés importar?",
                  padding=(14, 14, 14, 6)).pack(anchor="w")
        lista = tk.Listbox(dialogo, activestyle="none", borderwidth=0, highlightthickness=1,
                           highlightbackground=estilo.P["borde"], font=(estilo.FUENTE, 10),
                           selectbackground=estilo.P["acento"], selectforeground="#ffffff")
        for c in candidatos:
            lista.insert("end", c["titulo"])
        lista.selection_set(0)
        lista.pack(fill="both", expand=True, padx=14, pady=6)

        def cerrar():
            self.dialogo_eleccion = None
            dialogo.destroy()

        def aceptar():
            seleccion = lista.curselection()
            elegido = candidatos[seleccion[0]] if seleccion else None
            cerrar()
            if elegido:
                self.importacion.elegir(elegido)
            else:
                self.importacion.cancelar_eleccion()

        def cancelar():
            cerrar()
            self.importacion.cancelar_eleccion()
        botones = ttk.Frame(dialogo)
        botones.pack(fill="x", padx=14, pady=(4, 14))
        ttk.Button(botones, text="Importar", style="Accent.TButton", command=aceptar).pack(side="right")
        ttk.Button(botones, text="Cancelar", command=cancelar).pack(side="right", padx=(0, 10))
        lista.bind("<Double-Button-1>", lambda e: aceptar())
        dialogo.protocol("WM_DELETE_WINDOW", cancelar)

    def _estado_importacion(self):
        imp = self.importacion
        self.barra_importar["value"] = imp.fraccion * 100
        if imp.error:
            messagebox.showerror("No pude importar la voz", imp.error, parent=self)
            imp.error = None
            self.var_importar.set("")
            return
        if imp.candidatos and self.dialogo_eleccion is None:
            self._elegir_archivo(imp.candidatos)
        if imp.texto:
            self.var_importar.set(imp.texto)
        if imp.resultado and not imp.activa:
            # Terminó bien: se vuelve a leer la carpeta y se deja elegido el personaje nuevo.
            nuevo = imp.resultado
            imp.resultado = None
            self.var_enlace.set("")
            self.personajes_cargados = False
            self.lista_personajes = None
            self.personaje_a_elegir = nuevo
            threading.Thread(target=self._buscar_personajes, daemon=True).start()
        self.boton_importar.state(["disabled"] if imp.activa else ["!disabled"])

    def _estado_personaje(self):
        gestor = nucleo.GESTOR
        self._estado_importacion()
        if self.lista_personajes is not None and not self.personajes_cargados:
            actual = self.var_personaje.get()
            valores = [SIN_PERSONAJE] + self.lista_personajes
            if actual != SIN_PERSONAJE and actual not in valores:
                valores.append(actual)
            self.combo_personaje["values"] = valores
            self.personajes_cargados = True
            nuevo = getattr(self, "personaje_a_elegir", None)
            if nuevo:
                self.personaje_a_elegir = None
                if nuevo in valores:
                    self.var_personaje.set(nuevo)
        if gestor.trabajando or gestor.error or gestor.mensaje:
            self.var_estado_personaje.set(gestor.estado_texto())
        elif self.personajes_cargados and not self.lista_personajes:
            self.var_estado_personaje.set("Todavía no hay personajes: importá uno con el link de una voz o con un archivo.")
        elif not gestor.applio_instalado(self.var_applio.get()):
            self.var_estado_personaje.set("Applio todavía no está instalado: ejecutá instalar_voz_personaje.bat.")
        else:
            self.var_estado_personaje.set("")

    # ------------------------------------------------------------ general

    def _pestana_general(self, cuaderno):
        cfg = self.app.config
        marco = ttk.Frame(cuaderno, padding=16)
        cuaderno.add(marco, text="General")

        self.var_circulo = tk.BooleanVar(value=cfg["mostrar_circulo"])
        self.var_voz = tk.BooleanVar(value=cfg["responder_con_voz"])
        self.var_inicio = tk.BooleanVar(value=cfg["iniciar_con_windows"])
        self.var_tamano = tk.IntVar(value=cfg["tamano_circulo"])
        self.var_una_orden = tk.BooleanVar(value=cfg.get("una_orden", True))
        self.var_estricta = tk.BooleanVar(value=cfg.get("activacion_estricta", True))
        self.var_atento = tk.IntVar(value=cfg.get("segundos_atento", 8))
        self.var_activacion = tk.StringVar(value=", ".join(cfg["activacion"]))
        voz_guardada = cfg.get("voz")
        if voz_guardada and voz_guardada.startswith(nucleo.PREFIJO_NATURAL) and not cfg.get("voces_naturales"):
            voz_guardada = None  # las voces de Piper están desactivadas: se muestra la de Windows
        self.var_voz_nombre = tk.StringVar(value=voz_guardada or VOZ_PREDETERMINADA)
        self.var_voz_velocidad = tk.IntVar(value=cfg.get("voz_velocidad", 170))
        self.voces_cargadas = False

        ttk.Checkbutton(marco, text="Mostrar el círculo animado", variable=self.var_circulo
                        ).pack(anchor="w", pady=3)
        ttk.Checkbutton(marco, text="Que el asistente responda con voz", variable=self.var_voz
                        ).pack(anchor="w", pady=3)
        ttk.Checkbutton(marco, text="Iniciar el asistente al encender Windows",
                        variable=self.var_inicio).pack(anchor="w", pady=3)

        ttk.Checkbutton(marco, text="Activación estricta: solo despertarse si oye bien su nombre "
                                    "(evita que responda a otras palabras)",
                        variable=self.var_estricta).pack(anchor="w", pady=3)
        ttk.Checkbutton(marco, text="Dormirse después de cada orden (hay que decir su nombre de nuevo)",
                        variable=self.var_una_orden).pack(anchor="w", pady=3)
        fila_atento = ttk.Frame(marco)
        fila_atento.pack(anchor="w", pady=3)
        ttk.Label(fila_atento, text="Segundos que espera una orden después de decir su nombre:"
                  ).pack(side="left", padx=(0, 8))
        ttk.Spinbox(fila_atento, from_=3, to=30, width=4, textvariable=self.var_atento
                    ).pack(side="left")

        ttk.Label(marco, text="Tamaño del círculo:").pack(anchor="w", pady=(14, 0))
        tk.Scale(marco, from_=40, to=120, orient="horizontal", length=260,
                 variable=self.var_tamano).pack(anchor="w")

        ttk.Label(marco, text="Palabras para llamarlo (separadas por coma). El modelo tiene que "
                              "conocerlas; si no, la pestaña Comandos avisa:").pack(anchor="w", pady=(14, 0))
        ttk.Entry(marco, textvariable=self.var_activacion, width=50).pack(anchor="w", pady=4)

        ttk.Label(marco, text="Voz del asistente (las voces instaladas en Windows):"
                  ).pack(anchor="w", pady=(14, 0))
        fila_voz = ttk.Frame(marco)
        fila_voz.pack(anchor="w", pady=4)
        self.combo_voz = ttk.Combobox(fila_voz, textvariable=self.var_voz_nombre, state="readonly",
                                      values=[VOZ_PREDETERMINADA], width=58)
        self.combo_voz.grid(row=0, column=0)
        ttk.Button(fila_voz, text="Probar voz", command=self.probar_voz).grid(row=0, column=1, padx=8)
        ttk.Label(marco, text="Velocidad de la voz:").pack(anchor="w", pady=(8, 0))
        tk.Scale(marco, from_=100, to=260, orient="horizontal", length=260,
                 variable=self.var_voz_velocidad).pack(anchor="w")

        ttk.Label(marco, text="Dispositivo por donde habla el asistente (también se cambia por "
                              "voz con el comando \"cambiar salida de audio\"):").pack(anchor="w", pady=(8, 0))
        try:
            salidas = [nombre for _, nombre in nucleo.listar_salidas()]
        except Exception as error:
            nucleo.log("No pude listar las salidas de audio:", error)
            salidas = []
        actual = cfg.get("salida_audio")
        valores = [SALIDA_PREDETERMINADA] + salidas
        if actual and actual not in valores:
            valores.append(actual)
        self.var_salida = tk.StringVar(value=actual or SALIDA_PREDETERMINADA)
        ttk.Combobox(marco, textvariable=self.var_salida, values=valores, state="readonly",
                     width=58).pack(anchor="w", pady=4)

    def probar_voz(self):
        """Suena con la voz y velocidad elegidas, sin guardar nada."""
        if self.app.motor is None:
            return
        nombre = self.var_voz_nombre.get()
        self.app.motor.probar_voz(None if nombre == VOZ_PREDETERMINADA else nombre,
                                  int(self.var_voz_velocidad.get()))

    def guardar(self):
        variantes = [p.strip().lower() for p in self.var_activacion.get().split(",") if p.strip()]
        if not variantes:
            messagebox.showwarning("Falta algo", "Poné al menos una palabra para llamarlo.", parent=self)
            return
        nuevo = dict(self.app.config)
        nombre = self.var_mic.get()
        nuevo["microfono"] = None if nombre == MIC_PREDETERMINADO else nombre
        nuevo["mostrar_circulo"] = self.var_circulo.get()
        nuevo["responder_con_voz"] = self.var_voz.get()
        nuevo["iniciar_con_windows"] = self.var_inicio.get()
        nuevo["tamano_circulo"] = int(self.var_tamano.get())
        nuevo["una_orden"] = self.var_una_orden.get()
        nuevo["activacion_estricta"] = self.var_estricta.get()
        try:
            nuevo["segundos_atento"] = max(3, min(30, int(self.var_atento.get())))
        except (tk.TclError, ValueError):
            nuevo["segundos_atento"] = 8
        nuevo["activacion"] = variantes
        voz = self.var_voz_nombre.get()
        nuevo["voz"] = None if voz == VOZ_PREDETERMINADA else voz
        nuevo["voz_velocidad"] = int(self.var_voz_velocidad.get())
        salida = self.var_salida.get()
        nuevo["salida_audio"] = None if salida == SALIDA_PREDETERMINADA else salida
        personaje = self.var_personaje.get()
        nuevo["personaje"] = None if personaje == SIN_PERSONAJE else personaje
        nuevo["personaje_tono"] = int(self.var_tono.get())
        nuevo["applio_dir"] = self.var_applio.get().strip() or r"C:\Applio"
        try:
            self.app.aplicar_config(nuevo)
        except Exception as error:
            nucleo.log("[error al guardar la configuración]", error)
            messagebox.showerror("No pude guardar", str(error), parent=self)
            return
        self.var_pie.set("Cambios guardados.")

    # ------------------------------------------------------------ estado en vivo

    def _tic(self):
        if not self.vivo:
            return
        motor = self.app.motor
        self._estado_personaje()
        if motor is not None:
            self.barra_nivel["value"] = motor.nivel * 100
            if motor.voces and not self.voces_cargadas:
                # El motor lista las voces al arrancar; recién entonces se llena el selector.
                self.combo_voz["values"] = [VOZ_PREDETERMINADA] + list(motor.voces)
                self.voces_cargadas = True
            if motor.error:
                texto = "El motor de voz falló: " + motor.error.strip().splitlines()[-1]
            elif not motor.listo:
                texto = "Cargando el modelo de voz..."
            elif motor.avisos:
                texto = "Aviso: " + "  |  ".join(motor.avisos)
            else:
                texto = "Todo listo: escucho todas las frases."
            if motor.aviso_voz:
                texto += "  |  " + motor.aviso_voz
            self.var_avisos.set(texto)
        self.after(120, self._tic)

    def cerrar(self):
        self.vivo = False
        self.destroy()
        self.app.ventana_cerrada()

    def salir_del_asistente(self):
        if messagebox.askyesno("Salir", "¿Cerrar el asistente por completo?\n"
                                        "Dejará de escucharte hasta que lo vuelvas a abrir.",
                               parent=self):
            self.app.cola_ui.put("salir")
