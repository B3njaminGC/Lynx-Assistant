"""
Aspecto visual del asistente: tema oscuro, colores y el ícono.
Si algo de acá falla, la app sigue andando con el aspecto normal de Windows.
"""
import tkinter as tk
from tkinter import ttk

import nucleo

P = {
    "fondo": "#13141a",     # fondo de las ventanas
    "panel": "#1b1d26",     # tarjetas / zonas de contenido
    "campo": "#242734",     # cajas de texto, listas
    "borde": "#2f3343",
    "texto": "#e9ebf2",
    "suave": "#9aa1b6",     # textos secundarios
    "acento": "#7c5cff",    # violeta
    "acento_claro": "#9a82ff",
    "azul": "#4f8cff",
    "ok": "#34d399",
    "aviso": "#f5b94a",
    "error": "#f87171",
}
FUENTE = "Segoe UI"


# ---------------------------------------------------------------- ícono

def mezclar(c1, c2, t):
    """Color intermedio entre dos '#rrggbb' (t=0 -> c1, t=1 -> c2)."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def crear_icono(tam=256):
    """Ícono del asistente (PIL.Image RGBA): círculo degradado violeta-azul con ondas de voz."""
    from PIL import Image, ImageDraw, ImageOps

    s = tam * 4  # se dibuja grande y se achica: bordes suaves
    degradado = ImageOps.colorize(Image.linear_gradient("L").resize((s, s)).rotate(35),
                                  black=P["azul"], white=P["acento"]).convert("RGBA")
    mascara = Image.new("L", (s, s), 0)
    margen = int(s * 0.04)
    ImageDraw.Draw(mascara).ellipse((margen, margen, s - margen, s - margen), fill=255)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    img.paste(degradado, (0, 0), mascara)

    brillo = Image.new("RGBA", (s, s), (0, 0, 0, 0))   # reflejo suave arriba
    ImageDraw.Draw(brillo).ellipse((s * 0.14, s * 0.07, s * 0.86, s * 0.52), fill=(255, 255, 255, 40))
    img = Image.alpha_composite(img, Image.composite(brillo, Image.new("RGBA", (s, s)), mascara))

    d = ImageDraw.Draw(img)
    alturas = [0.20, 0.38, 0.54, 0.38, 0.20]            # 5 barras: la onda de voz
    ancho = s * 0.075
    paso = s * 0.125
    x0 = s / 2 - paso * 2
    for i, h in enumerate(alturas):
        x = x0 + paso * i
        alto = s * h
        d.rounded_rectangle((x - ancho / 2, s / 2 - alto / 2, x + ancho / 2, s / 2 + alto / 2),
                            radius=ancho / 2, fill=(255, 255, 255, 245))
    return img.resize((tam, tam), Image.LANCZOS)


def guardar_ico(ruta):
    """Escribe el .ico (varios tamaños) para el .exe."""
    crear_icono(256).save(ruta, format="ICO",
                          sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def poner_icono(ventana):
    """Ícono en la barra de título y en la barra de tareas."""
    try:
        from PIL import ImageTk
        imagenes = [ImageTk.PhotoImage(crear_icono(t)) for t in (32, 64)]
        ventana.iconphoto(True, *imagenes)
        ventana._iconos = imagenes  # tkinter olvida la imagen si no se guarda una referencia
    except Exception as error:
        nucleo.log("[estilo] sin ícono de ventana:", error)


def barra_oscura(ventana):
    """Barra de título oscura (Windows 10/11). Se llama con la ventana ya creada."""
    def aplicar():
        try:
            import ctypes
            ventana.update_idletasks()
            ident = ventana.winfo_id()
            hwnd = ctypes.windll.user32.GetParent(ident) or ident
            valor = ctypes.c_int(1)
            for atributo in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (Win11/Win10 nuevo, Win10 viejo)
                if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, atributo, ctypes.byref(valor),
                                                              ctypes.sizeof(valor)) == 0:
                    break
        except Exception:
            pass
    try:
        ventana.after(30, aplicar)
    except Exception:
        pass


# ---------------------------------------------------------------- tema

def aplicar_tema(raiz):
    """Tema oscuro para todos los widgets ttk y los clásicos de tk."""
    try:
        estilo = ttk.Style(raiz)
        estilo.theme_use("clam")
        f = (FUENTE, 10)
        estilo.configure(".", background=P["fondo"], foreground=P["texto"], font=f,
                         fieldbackground=P["campo"], bordercolor=P["borde"],
                         lightcolor=P["borde"], darkcolor=P["borde"], troughcolor=P["campo"],
                         focuscolor=P["fondo"], insertcolor=P["texto"], selectbackground=P["acento"],
                         selectforeground="#ffffff")
        estilo.configure("TFrame", background=P["fondo"])
        estilo.configure("TLabel", background=P["fondo"], foreground=P["texto"])
        estilo.configure("Suave.TLabel", foreground=P["suave"])
        estilo.configure("Titulo.TLabel", font=(FUENTE, 15, "bold"))
        estilo.configure("Seccion.TLabel", font=(FUENTE, 11, "bold"))
        estilo.configure("TSeparator", background=P["borde"])
        estilo.configure("Aviso.TLabel", foreground=P["aviso"])
        estilo.configure("Estado.TLabel", foreground=P["acento_claro"])

        estilo.configure("TButton", background=P["campo"], foreground=P["texto"], padding=(14, 7),
                         borderwidth=0, relief="flat", focusthickness=0)
        estilo.map("TButton", background=[("pressed", P["borde"]), ("active", "#2e3245"),
                                          ("disabled", P["panel"])],
                   foreground=[("disabled", P["suave"])])
        estilo.configure("Accent.TButton", background=P["acento"], foreground="#ffffff",
                         padding=(18, 8), font=(FUENTE, 10, "bold"))
        estilo.map("Accent.TButton", background=[("pressed", "#6847e6"), ("active", P["acento_claro"]),
                                                 ("disabled", P["borde"])])

        estilo.configure("TEntry", fieldbackground=P["campo"], foreground=P["texto"], padding=6,
                         bordercolor=P["borde"], lightcolor=P["borde"], darkcolor=P["borde"])
        estilo.map("TEntry", bordercolor=[("focus", P["acento"])], lightcolor=[("focus", P["acento"])],
                   darkcolor=[("focus", P["acento"])])
        estilo.configure("TCombobox", fieldbackground=P["campo"], background=P["campo"],
                         foreground=P["texto"], arrowcolor=P["suave"], padding=6,
                         bordercolor=P["borde"], lightcolor=P["borde"], darkcolor=P["borde"])
        estilo.map("TCombobox", fieldbackground=[("readonly", P["campo"])],
                   foreground=[("readonly", P["texto"])],
                   selectbackground=[("readonly", P["campo"])],
                   selectforeground=[("readonly", P["texto"])],
                   bordercolor=[("focus", P["acento"])], arrowcolor=[("active", P["texto"])])
        raiz.option_add("*TCombobox*Listbox.background", P["campo"])
        raiz.option_add("*TCombobox*Listbox.foreground", P["texto"])
        raiz.option_add("*TCombobox*Listbox.selectBackground", P["acento"])
        raiz.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        raiz.option_add("*TCombobox*Listbox.font", f)

        estilo.configure("TCheckbutton", background=P["fondo"], foreground=P["texto"],
                         indicatorcolor=P["campo"], indicatorbackground=P["campo"], padding=4)
        estilo.map("TCheckbutton", background=[("active", P["fondo"])],
                   indicatorcolor=[("selected", P["acento"]), ("pressed", P["acento_claro"])])

        estilo.configure("TNotebook", background=P["fondo"], borderwidth=0, tabmargins=(0, 4, 0, 0))
        estilo.configure("TNotebook.Tab", background=P["fondo"], foreground=P["suave"],
                         padding=(18, 9), borderwidth=0, font=(FUENTE, 10))
        estilo.map("TNotebook.Tab", background=[("selected", P["panel"]), ("active", P["campo"])],
                   foreground=[("selected", P["texto"]), ("active", P["texto"])],
                   expand=[("selected", (0, 0, 0, 0))])

        estilo.configure("Treeview", background=P["panel"], fieldbackground=P["panel"],
                         foreground=P["texto"], rowheight=30, borderwidth=0, font=f)
        estilo.map("Treeview", background=[("selected", P["acento"])],
                   foreground=[("selected", "#ffffff")])
        estilo.configure("Treeview.Heading", background=P["campo"], foreground=P["suave"],
                         padding=(8, 7), borderwidth=0, font=(FUENTE, 9, "bold"), relief="flat")
        estilo.map("Treeview.Heading", background=[("active", "#2e3245")])

        estilo.configure("Vertical.TScrollbar", background=P["campo"], troughcolor=P["panel"],
                         bordercolor=P["panel"], arrowcolor=P["suave"], lightcolor=P["campo"],
                         darkcolor=P["campo"], gripcount=0, relief="flat")
        estilo.configure("Horizontal.TScrollbar", background=P["campo"], troughcolor=P["panel"],
                         bordercolor=P["panel"], arrowcolor=P["suave"], lightcolor=P["campo"],
                         darkcolor=P["campo"], gripcount=0, relief="flat")
        estilo.map("TScrollbar", background=[("active", P["borde"])])
        estilo.configure("Horizontal.TProgressbar", background=P["acento"], troughcolor=P["campo"],
                         bordercolor=P["campo"], lightcolor=P["acento"], darkcolor=P["acento"])

        # Widgets clásicos de tk (Scale, Text, ventanas)
        raiz.option_add("*Toplevel.background", P["fondo"])
        raiz.option_add("*Scale.background", P["fondo"])
        raiz.option_add("*Scale.foreground", P["texto"])
        raiz.option_add("*Scale.troughColor", P["campo"])
        raiz.option_add("*Scale.activeBackground", P["acento"])
        raiz.option_add("*Scale.highlightThickness", 0)
        raiz.option_add("*Scale.borderWidth", 0)
        raiz.option_add("*Scale.sliderRelief", "flat")
        raiz.option_add("*Scale.font", f)
        raiz.option_add("*Text.background", P["campo"])
        raiz.option_add("*Text.foreground", P["texto"])
        raiz.option_add("*Text.insertBackground", P["texto"])
        raiz.option_add("*Text.selectBackground", P["acento"])
        raiz.option_add("*Text.relief", "flat")
        raiz.option_add("*Text.font", f)
        raiz.option_add("*Text.highlightThickness", 1)
        raiz.option_add("*Text.highlightBackground", P["borde"])
        raiz.option_add("*Text.highlightColor", P["acento"])
        raiz.option_add("*Listbox.background", P["campo"])
        raiz.option_add("*Listbox.foreground", P["texto"])
        return True
    except Exception as error:
        nucleo.log("[estilo] no pude aplicar el tema oscuro:", error)
        return False


def preparar_ventana(ventana):
    """Fondo, barra de título e ícono de una ventana nueva."""
    try:
        ventana.configure(bg=P["fondo"])
    except Exception:
        pass
    barra_oscura(ventana)
    poner_icono(ventana)
