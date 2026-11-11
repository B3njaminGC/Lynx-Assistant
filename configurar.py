"""
Ventana para configurar los comandos del asistente (edita comandos.json).
Usa tkinter, que ya viene con Python: no hay que instalar nada.
"""
import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

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

# Etiqueta y ayuda del campo "valor" según el tipo de acción.
VALOR_AYUDA = {
    "abrir_programa": "Programa a abrir (usá Buscar para elegirlo):",
    "abrir_web": "Dirección de la página (ej: https://www.youtube.com):",
    "cerrar_programa": "Nombre del programa a cerrar (ej: brave.exe):",
    "cerrar_varios": "Programas a cerrar, uno por línea (ej: brave.exe):",
    "apagar": "",
    "cambiar_salida": "Nombre (o parte) del dispositivo de sonido (ej: Speaker (Realtek):",
    "reproducir_musica": "Canciones o carpetas a reproducir, una por línea (usá los botones de abajo):",
    "tecla_multimedia": "Qué hacer (funciona con Spotify, YouTube y casi cualquier reproductor):",
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


def valor_en_texto(valor):
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
        self.var_tipo = tk.StringVar(value=TIPOS[cmd["tipo"]] if cmd else TIPOS["abrir_programa"])
        combo = ttk.Combobox(marco, textvariable=self.var_tipo, state="readonly",
                             values=list(TIPOS.values()), width=47)
        combo.grid(sticky="we", pady=(0, 10))
        combo.bind("<<ComboboxSelected>>", lambda e: self.cambio_tipo(True))

        self.lbl_valor = ttk.Label(marco, text="")
        self.lbl_valor.grid(sticky="w")

        self.fila_valor = ttk.Frame(marco)
        self.fila_valor.grid(sticky="we", pady=(0, 10))
        self.var_valor = tk.StringVar()
        self.ent_valor = ttk.Entry(self.fila_valor, textvariable=self.var_valor, width=40)
        self.btn_buscar = ttk.Button(self.fila_valor, text="Buscar...", command=self.buscar_programa)
        self.txt_valor = tk.Text(self.fila_valor, width=38, height=5)
        self.btn_canciones = ttk.Button(self.fila_valor, text="Agregar canciones...", command=self.agregar_canciones)
        self.btn_carpeta = ttk.Button(self.fila_valor, text="Agregar carpeta...", command=self.agregar_carpeta)
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
            elif cmd["tipo"] == "tecla_multimedia":
                self.combo_multimedia.set(MULTIMEDIA_POR_CLAVE.get(valor, ""))
            else:
                self.var_valor.set(valor)

        self.grab_set()
        self.wait_visibility()
        self.focus_force()

    def tipo_actual(self):
        return TIPO_POR_NOMBRE[self.var_tipo.get()]

    def cambio_tipo(self, es_cambio_del_usuario):
        tipo = self.tipo_actual()
        self.lbl_valor.config(text=VALOR_AYUDA[tipo])
        for w in (self.ent_valor, self.btn_buscar, self.txt_valor, self.combo_multimedia,
                  self.btn_canciones, self.btn_carpeta):
            w.grid_forget()
        if tipo == "cerrar_varios":
            self.txt_valor.grid(row=0, column=0)
        elif tipo == "reproducir_musica":
            self.txt_valor.grid(row=0, column=0, columnspan=2)
            self.btn_canciones.grid(row=1, column=0, sticky="w", pady=(6, 0))
            self.btn_carpeta.grid(row=1, column=1, sticky="w", pady=(6, 0), padx=(6, 0))
        elif tipo == "tecla_multimedia":
            self.combo_multimedia.grid(row=0, column=0, sticky="we")
            if not self.combo_multimedia.get():
                self.combo_multimedia.set(next(iter(MULTIMEDIA)))
        elif tipo != "apagar":
            self.ent_valor.grid(row=0, column=0, sticky="we")
            if tipo == "abrir_programa":
                self.btn_buscar.grid(row=0, column=1, padx=(6, 0))
        if es_cambio_del_usuario:
            self.var_confirmar.set(tipo in CONFIRMAR_POR_DEFECTO)

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
        elif tipo == "reproducir_musica":
            valor = [l.strip().strip('"') for l in self.txt_valor.get("1.0", "end").splitlines() if l.strip()]
        elif tipo == "cerrar_varios":
            lineas = [l.strip() for l in self.txt_valor.get("1.0", "end").splitlines() if l.strip()]
            valor = [l if l.lower().endswith(".exe") else l + ".exe" for l in lineas]
        else:
            valor = self.var_valor.get().strip().strip('"')
            if tipo == "cerrar_programa" and valor and not valor.lower().endswith(".exe"):
                valor += ".exe"

        if tipo != "apagar" and not valor:
            messagebox.showwarning("Falta algo", "Completá el campo de abajo.", parent=self)
            return

        self.resultado = {"frase": frase, "tipo": tipo, "valor": valor,
                          "respuesta": self.var_respuesta.get().strip(),
                          "confirmar": self.var_confirmar.get()}
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
        ttk.Button(botones, text="Add", command=self.agregar).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(botones, text="Editar", command=self.editar).grid(row=0, column=1, padx=6)
        ttk.Button(botones, text="Borrar", command=self.borrar).grid(row=0, column=2, padx=6)

        self.refrescar()

    def refrescar(self):
        self.tabla.delete(*self.tabla.get_children())
        for i, c in enumerate(self.comandos):
            self.tabla.insert("", "end", iid=str(i), values=(
                c["frase"], TIPOS.get(c["tipo"], c["tipo"]), valor_en_texto(c.get("valor", "")),
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
