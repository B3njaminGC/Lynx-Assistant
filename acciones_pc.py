"""
Acciones de la PC que se pueden elegir con un clic (tipo de comando "Acción de la PC").

Cada acción es una fila de la tabla CATALOGO, así que agregar una nueva es agregar una línea:

    (clave, grupo, nombre en la ventana, cómo se hace, qué dice, ¿pide confirmación?)

"Cómo se hace" es un par (modo, dato):
    ("teclas", "win+d")            aprieta esa combinación (mismos nombres que "Apretar teclas")
    ("abrir", "ms-settings:sound") abre un programa, carpeta o pantalla de Windows
    ("correr", ["shutdown", ...])  corre un comando de Windows
    ("powershell", "script")       corre un script corto de PowerShell
    ("funcion", "nombre")          una función de este archivo (ver FUNCIONES)
    ("informe", "nombre")          Lynx dice un dato en voz alta (ver INFORMES)
    ("temporizador", minutos)      avisa cuando pasa el tiempo (0 = cancela el temporizador)

Todo funciona sin internet y sin instalar nada: usa solo lo que trae Windows.
"""
import ctypes
import os
import shutil
import socket
import subprocess
import sys
import time
from collections import namedtuple
from datetime import datetime

Accion = namedtuple("Accion", "clave grupo nombre como respuesta confirmar")

SIN_VENTANA = 0x08000000 if sys.platform == "win32" else 0


def _a(clave, grupo, nombre, como, respuesta, confirmar=False):
    return Accion(clave, grupo, nombre, como, respuesta, confirmar)


ENERGIA = "Energía"
VENTANAS = "Ventanas y escritorios"
CAPTURA = "Captura y grabación"
EDICION = "Edición y navegador"
VOLUMEN = "Volumen y brillo"
SISTEMA = "Apariencia y limpieza"
PROGRAMAS = "Abrir programas de Windows"
AJUSTES = "Abrir ajustes de Windows"
CARPETAS = "Abrir carpetas"
INFO = "Información (Lynx te lo dice)"
TEMPORIZADOR = "Temporizador"

CATALOGO = [
    # ------------------------------------------------------------------ energía
    _a("suspender", ENERGIA, "Suspender la PC", ("funcion", "suspender"), "Suspendiendo."),
    _a("hibernar", ENERGIA, "Hibernar la PC", ("correr", ["shutdown", "/h"]), "Hibernando."),
    _a("reiniciar", ENERGIA, "Reiniciar la PC", ("correr", ["shutdown", "/r", "/t", "0"]), "Reiniciando la PC.", True),
    _a("cerrar_sesion", ENERGIA, "Cerrar la sesión de Windows", ("correr", ["shutdown", "/l"]),
       "Cerrando la sesión.", True),
    _a("bloquear", ENERGIA, "Bloquear la PC", ("correr", ["rundll32.exe", "user32.dll,LockWorkStation"]),
       "Bloqueando."),
    _a("apagar_pantalla", ENERGIA, "Apagar solo la pantalla", ("funcion", "apagar_pantalla"), ""),
    _a("apagar_en_media_hora", ENERGIA, "Apagar la PC en 30 minutos", ("correr", ["shutdown", "/s", "/t", "1800"]),
       "Listo, la PC se apaga en media hora."),
    _a("apagar_en_una_hora", ENERGIA, "Apagar la PC en 1 hora", ("correr", ["shutdown", "/s", "/t", "3600"]),
       "Listo, la PC se apaga en una hora."),
    _a("cancelar_apagado", ENERGIA, "Cancelar un apagado programado", ("correr", ["shutdown", "/a"]),
       "Listo, cancelé el apagado."),

    # ------------------------------------------------------------------ ventanas
    _a("mostrar_escritorio", VENTANAS, "Mostrar el escritorio", ("teclas", "win+d"), ""),
    _a("cambiar_ventana", VENTANAS, "Cambiar de ventana", ("teclas", "alt+tab"), ""),
    _a("vista_tareas", VENTANAS, "Ver todas las ventanas", ("teclas", "win+tab"), ""),
    _a("cerrar_ventana", VENTANAS, "Cerrar la ventana actual", ("teclas", "alt+f4"), "", True),
    _a("maximizar", VENTANAS, "Maximizar la ventana", ("teclas", "win+arriba"), ""),
    _a("minimizar", VENTANAS, "Minimizar la ventana", ("teclas", "win+abajo"), ""),
    _a("ventana_izquierda", VENTANAS, "Ventana a la mitad izquierda", ("teclas", "win+izquierda"), ""),
    _a("ventana_derecha", VENTANAS, "Ventana a la mitad derecha", ("teclas", "win+derecha"), ""),
    _a("pantalla_completa", VENTANAS, "Pantalla completa (F11)", ("teclas", "f11"), ""),
    _a("escritorio_nuevo", VENTANAS, "Nuevo escritorio virtual", ("teclas", "win+ctrl+d"), ""),
    _a("escritorio_siguiente", VENTANAS, "Escritorio virtual siguiente", ("teclas", "win+ctrl+derecha"), ""),
    _a("escritorio_anterior", VENTANAS, "Escritorio virtual anterior", ("teclas", "win+ctrl+izquierda"), ""),
    _a("proyectar", VENTANAS, "Proyectar a otra pantalla", ("teclas", "win+p"), ""),
    _a("buscador", VENTANAS, "Abrir el buscador de Windows", ("teclas", "win+s"), ""),
    _a("notificaciones", VENTANAS, "Abrir las notificaciones", ("teclas", "win+n"), ""),

    # ------------------------------------------------------------------ captura y grabación
    _a("captura_recorte", CAPTURA, "Captura de pantalla (recorte)", ("teclas", "win+shift+s"), ""),
    _a("grabar_pantalla", CAPTURA, "Grabar la pantalla (Barra de juegos)", ("teclas", "win+alt+r"), ""),
    _a("barra_juegos", CAPTURA, "Abrir la Barra de juegos", ("teclas", "win+g"), ""),
    _a("historial_portapapeles", CAPTURA, "Historial del portapapeles", ("teclas", "win+v"), ""),
    _a("dictado", CAPTURA, "Dictado de Windows", ("teclas", "win+h"), ""),

    # ------------------------------------------------------------------ edición y navegador
    _a("copiar", EDICION, "Copiar", ("teclas", "ctrl+c"), ""),
    _a("pegar", EDICION, "Pegar", ("teclas", "ctrl+v"), ""),
    _a("cortar", EDICION, "Cortar", ("teclas", "ctrl+x"), ""),
    _a("seleccionar_todo", EDICION, "Seleccionar todo", ("teclas", "ctrl+a"), ""),
    _a("deshacer", EDICION, "Deshacer", ("teclas", "ctrl+z"), ""),
    _a("rehacer", EDICION, "Rehacer", ("teclas", "ctrl+y"), ""),
    _a("guardar", EDICION, "Guardar", ("teclas", "ctrl+s"), ""),
    _a("apretar_enter", EDICION, "Apretar Enter", ("teclas", "enter"), ""),
    _a("apretar_escape", EDICION, "Apretar Escape", ("teclas", "esc"), ""),
    _a("nueva_pestana", EDICION, "Nueva pestaña", ("teclas", "ctrl+t"), ""),
    _a("cerrar_pestana", EDICION, "Cerrar la pestaña", ("teclas", "ctrl+w"), ""),
    _a("reabrir_pestana", EDICION, "Reabrir la última pestaña", ("teclas", "ctrl+shift+t"), ""),
    _a("pestana_siguiente", EDICION, "Pestaña siguiente", ("teclas", "ctrl+tab"), ""),
    _a("pestana_anterior", EDICION, "Pestaña anterior", ("teclas", "ctrl+shift+tab"), ""),
    _a("recargar", EDICION, "Recargar la página", ("teclas", "f5"), ""),
    _a("volver_atras", EDICION, "Volver atrás en el navegador", ("teclas", "alt+izquierda"), ""),
    _a("buscar_en_pagina", EDICION, "Buscar dentro de la página", ("teclas", "ctrl+f"), ""),

    # ------------------------------------------------------------------ volumen y brillo
    _a("volumen_maximo", VOLUMEN, "Volumen al máximo", ("funcion", "volumen_maximo"), ""),
    _a("volumen_medio", VOLUMEN, "Volumen a la mitad", ("funcion", "volumen_medio"), ""),
    _a("volumen_bajo", VOLUMEN, "Volumen bajito", ("funcion", "volumen_bajo"), ""),
    _a("brillo_subir", VOLUMEN, "Subir el brillo", ("funcion", "brillo_subir"), ""),
    _a("brillo_bajar", VOLUMEN, "Bajar el brillo", ("funcion", "brillo_bajar"), ""),
    _a("brillo_maximo", VOLUMEN, "Brillo al máximo", ("funcion", "brillo_maximo"), ""),
    _a("brillo_medio", VOLUMEN, "Brillo a la mitad", ("funcion", "brillo_medio"), ""),
    _a("brillo_minimo", VOLUMEN, "Brillo al mínimo", ("funcion", "brillo_minimo"), ""),

    # ------------------------------------------------------------------ apariencia y limpieza
    _a("modo_oscuro", SISTEMA, "Activar el modo oscuro", ("funcion", "modo_oscuro"), "Modo oscuro activado."),
    _a("modo_claro", SISTEMA, "Activar el modo claro", ("funcion", "modo_claro"), "Modo claro activado."),
    _a("vaciar_papelera", SISTEMA, "Vaciar la papelera",
       ("powershell", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"), "Listo, vacié la papelera.", True),
    _a("reiniciar_explorador", SISTEMA, "Reiniciar el Explorador (si Windows se traba)",
       ("powershell", "Stop-Process -Name explorer -Force"), "Listo.", True),

    # ------------------------------------------------------------------ programas de Windows
    _a("administrador_tareas", PROGRAMAS, "Administrador de tareas", ("abrir", "taskmgr"), "Abriendo."),
    _a("explorador", PROGRAMAS, "Explorador de archivos", ("abrir", "explorer"), "Abriendo."),
    _a("calculadora", PROGRAMAS, "Calculadora", ("abrir", "calc"), "Abriendo."),
    _a("bloc_de_notas", PROGRAMAS, "Bloc de notas", ("abrir", "notepad"), "Abriendo."),
    _a("paint", PROGRAMAS, "Paint", ("abrir", "mspaint"), "Abriendo."),
    _a("simbolo_del_sistema", PROGRAMAS, "Símbolo del sistema", ("abrir", "cmd"), "Abriendo."),
    _a("powershell", PROGRAMAS, "PowerShell", ("abrir", "powershell"), "Abriendo."),
    _a("panel_de_control", PROGRAMAS, "Panel de control", ("abrir", "control"), "Abriendo."),
    _a("administrador_dispositivos", PROGRAMAS, "Administrador de dispositivos", ("abrir", "devmgmt.msc"),
       "Abriendo."),
    _a("monitor_recursos", PROGRAMAS, "Monitor de recursos", ("abrir", "resmon"), "Abriendo."),
    _a("info_sistema", PROGRAMAS, "Información del sistema", ("abrir", "msinfo32"), "Abriendo."),
    _a("tienda", PROGRAMAS, "Microsoft Store", ("abrir", "ms-windows-store:"), "Abriendo."),
    _a("camara", PROGRAMAS, "Cámara", ("abrir", "microsoft.windows.camera:"), "Abriendo."),
    _a("reloj", PROGRAMAS, "Reloj y alarmas", ("abrir", "ms-clock:"), "Abriendo."),
    _a("fotos", PROGRAMAS, "Fotos", ("abrir", "ms-photos:"), "Abriendo."),
    _a("seguridad_windows", PROGRAMAS, "Seguridad de Windows", ("abrir", "windowsdefender:"), "Abriendo."),

    # ------------------------------------------------------------------ ajustes de Windows
    _a("ajustes", AJUSTES, "Configuración de Windows", ("abrir", "ms-settings:"), "Abriendo."),
    _a("ajustes_sonido", AJUSTES, "Ajustes de sonido", ("abrir", "ms-settings:sound"), "Abriendo."),
    _a("ajustes_pantalla", AJUSTES, "Ajustes de pantalla", ("abrir", "ms-settings:display"), "Abriendo."),
    _a("ajustes_wifi", AJUSTES, "Ajustes de Wi-Fi", ("abrir", "ms-settings:network-wifi"), "Abriendo."),
    _a("ajustes_bluetooth", AJUSTES, "Ajustes de Bluetooth", ("abrir", "ms-settings:bluetooth"), "Abriendo."),
    _a("ajustes_bateria", AJUSTES, "Ajustes de batería", ("abrir", "ms-settings:batterysaver"), "Abriendo."),
    _a("ajustes_actualizaciones", AJUSTES, "Windows Update", ("abrir", "ms-settings:windowsupdate"), "Abriendo."),
    _a("ajustes_aplicaciones", AJUSTES, "Programas instalados", ("abrir", "ms-settings:appsfeatures"),
       "Abriendo."),

    # ------------------------------------------------------------------ carpetas
    _a("carpeta_descargas", CARPETAS, "Carpeta Descargas", ("abrir", "shell:Downloads"), "Abriendo."),
    _a("carpeta_documentos", CARPETAS, "Carpeta Documentos", ("abrir", "shell:Personal"), "Abriendo."),
    _a("carpeta_escritorio", CARPETAS, "Carpeta Escritorio", ("abrir", "shell:Desktop"), "Abriendo."),
    _a("carpeta_imagenes", CARPETAS, "Carpeta Imágenes", ("abrir", "shell:My Pictures"), "Abriendo."),
    _a("carpeta_musica", CARPETAS, "Carpeta Música", ("abrir", "shell:My Music"), "Abriendo."),
    _a("carpeta_videos", CARPETAS, "Carpeta Videos", ("abrir", "shell:My Video"), "Abriendo."),
    _a("abrir_papelera", CARPETAS, "Abrir la papelera", ("abrir", "shell:RecycleBinFolder"), "Abriendo."),

    # ------------------------------------------------------------------ información
    _a("decir_hora", INFO, "Decir la hora", ("informe", "hora"), ""),
    _a("decir_fecha", INFO, "Decir la fecha", ("informe", "fecha"), ""),
    _a("decir_bateria", INFO, "Decir cuánta batería queda", ("informe", "bateria"), ""),
    _a("decir_memoria", INFO, "Decir cuánta memoria (RAM) se usa", ("informe", "memoria"), ""),
    _a("decir_disco", INFO, "Decir cuánto espacio libre queda", ("informe", "disco"), ""),
    _a("decir_encendida", INFO, "Decir hace cuánto está encendida la PC", ("informe", "encendida"), ""),
    _a("decir_ip", INFO, "Decir la IP de la PC", ("informe", "ip"), ""),

    # ------------------------------------------------------------------ temporizador
    _a("temporizador_5", TEMPORIZADOR, "Temporizador de 5 minutos", ("temporizador", 5),
       "Listo, te aviso en cinco minutos."),
    _a("temporizador_10", TEMPORIZADOR, "Temporizador de 10 minutos", ("temporizador", 10),
       "Listo, te aviso en diez minutos."),
    _a("temporizador_15", TEMPORIZADOR, "Temporizador de 15 minutos", ("temporizador", 15),
       "Listo, te aviso en quince minutos."),
    _a("temporizador_30", TEMPORIZADOR, "Temporizador de 30 minutos", ("temporizador", 30),
       "Listo, te aviso en media hora."),
    _a("temporizador_60", TEMPORIZADOR, "Temporizador de 1 hora", ("temporizador", 60),
       "Listo, te aviso en una hora."),
    _a("temporizador_cancelar", TEMPORIZADOR, "Cancelar los temporizadores", ("temporizador", 0),
       "Listo, cancelé los temporizadores."),
]

POR_CLAVE = {a.clave: a for a in CATALOGO}
POR_NOMBRE = {a.nombre: a for a in CATALOGO}
GRUPOS = list(dict.fromkeys(a.grupo for a in CATALOGO))
TEXTO_DE_FALLA = "No pude hacerlo."


def nombre_para_ventana(accion):
    """Cómo se ve en la lista de la ventana: el grupo, una raya y el nombre."""
    return f"{accion.grupo} · {accion.nombre}"


NOMBRES_PARA_VENTANA = {nombre_para_ventana(a): a.clave for a in CATALOGO}


def respuesta_por_defecto(clave):
    accion = POR_CLAVE.get(clave)
    return accion.respuesta if accion else "Listo."


# ====================================================================== lo que hace cada acción

class Entorno:
    """Todo lo que una acción necesita del exterior, junto en un lugar (así se puede probar con uno de juguete)."""

    def __init__(self, hablar, pulsar=None, abrir=None, correr=None, temporizador=None, ahora=datetime.now):
        self.hablar = hablar
        self.pulsar = pulsar or _pulsar_real
        self.abrir = abrir or _abrir_real
        self.correr = correr or _correr_real
        self.temporizador = temporizador
        self.ahora = ahora


def _pulsar_real(texto):
    import teclas
    teclas.pulsar(texto)


def _abrir_real(destino):
    os.startfile(destino)


def _correr_real(argumentos):
    return subprocess.run(argumentos, capture_output=True, creationflags=SIN_VENTANA)


def ejecutar(clave, entorno, respuesta=None):
    """Hace la acción. `respuesta` = lo que quiere decir el comando (si no, la del catálogo).
    Devuelve True si salió bien. Si algo falla, avisa en voz alta en vez de romper."""
    accion = POR_CLAVE.get(clave)
    if accion is None:
        entorno.hablar("Esa acción ya no existe. Editá el comando.")
        return False
    modo, dato = accion.como
    texto = accion.respuesta if respuesta is None else respuesta
    try:
        if modo == "teclas":
            entorno.pulsar(dato)
        elif modo == "abrir":
            entorno.abrir(dato)
        elif modo == "correr":
            entorno.correr(list(dato))
        elif modo == "powershell":
            _powershell(entorno, dato)
        elif modo == "funcion":
            cambio = FUNCIONES[dato](entorno)
            texto = cambio if cambio else texto
        elif modo == "informe":
            texto = INFORMES[dato](entorno)
        elif modo == "temporizador":
            entorno.temporizador(dato)
    except Exception as error:
        _registrar(f"[acción {clave}] {error}")
        entorno.hablar(TEXTO_DE_FALLA)
        return False
    if texto:
        entorno.hablar(texto)
    return True


def _registrar(texto):
    try:
        import nucleo
        nucleo.log(texto)
    except Exception:
        pass


def _powershell(entorno, script, error_si_falla=True):
    resultado = entorno.correr(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                                "-Command", script])
    codigo = getattr(resultado, "returncode", 0)
    if error_si_falla and codigo not in (0, None):
        raise RuntimeError(f"PowerShell terminó con código {codigo}")
    return resultado


# ---------------------------------------------------------------------- funciones

def suspender(entorno):
    # Con SetSuspendState('Suspend') Windows suspende de verdad (rundll32 hiberna si la hibernación está activa).
    _powershell(entorno, "Add-Type -AssemblyName System.Windows.Forms; "
                         "[System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)")


def apagar_pantalla(entorno):
    # WM_SYSCOMMAND / SC_MONITORPOWER: 2 = apagar el monitor. Se prende al mover el mouse.
    ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)


def _volumen(entorno, bajar, subir):
    """Windows no deja fijar el volumen sin programas extra: se baja todo y se sube hasta el punto elegido
    (cada toque mueve 2 puntos)."""
    user32 = ctypes.windll.user32
    for codigo, veces in ((0xAE, bajar), (0xAF, subir)):
        for _ in range(veces):
            user32.keybd_event(codigo, 0, 0, 0)
            user32.keybd_event(codigo, 0, 2, 0)
            time.sleep(0.005)


def volumen_maximo(entorno):
    _volumen(entorno, 0, 50)


def volumen_medio(entorno):
    _volumen(entorno, 50, 25)


def volumen_bajo(entorno):
    _volumen(entorno, 50, 8)


def script_de_brillo(cambio=None, valor=None):
    """PowerShell que cambia el brillo. `cambio` = sumar o restar puntos; `valor` = dejarlo en ese número."""
    nuevo = f"$n = {int(valor)}" if valor is not None else \
        (f"$ahora = (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness | Select-Object -First 1)"
         f".CurrentBrightness; $n = [Math]::Max(0, [Math]::Min(100, $ahora + ({int(cambio or 0)})))")
    return ("$ErrorActionPreference = 'Stop'; " + nuevo + "; "
            "Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods | "
            "Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{Timeout = 1; Brightness = $n} | Out-Null")


def _brillo(entorno, cambio=None, valor=None):
    try:
        _powershell(entorno, script_de_brillo(cambio, valor))
    except RuntimeError:
        return "No pude cambiar el brillo. En monitores externos no funciona."


def brillo_subir(entorno):
    return _brillo(entorno, cambio=20)


def brillo_bajar(entorno):
    return _brillo(entorno, cambio=-20)


def brillo_maximo(entorno):
    return _brillo(entorno, valor=100)


def brillo_medio(entorno):
    return _brillo(entorno, valor=50)


def brillo_minimo(entorno):
    return _brillo(entorno, valor=5)


def _tema(claro):
    import winreg
    clave = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
    with clave:
        for nombre in ("AppsUseLightTheme", "SystemUsesLightTheme"):
            winreg.SetValueEx(clave, nombre, 0, winreg.REG_DWORD, 1 if claro else 0)


def modo_oscuro(entorno):
    _tema(False)


def modo_claro(entorno):
    _tema(True)


FUNCIONES = {
    "suspender": suspender, "apagar_pantalla": apagar_pantalla,
    "volumen_maximo": volumen_maximo, "volumen_medio": volumen_medio, "volumen_bajo": volumen_bajo,
    "brillo_subir": brillo_subir, "brillo_bajar": brillo_bajar, "brillo_maximo": brillo_maximo,
    "brillo_medio": brillo_medio, "brillo_minimo": brillo_minimo,
    "modo_oscuro": modo_oscuro, "modo_claro": modo_claro,
}


# ---------------------------------------------------------------------- informes (lo que Lynx dice)

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]


def texto_hora(ahora):
    hora12 = ahora.hour % 12 or 12
    comienzo = "Es la una" if hora12 == 1 else f"Son las {hora12}"
    minutos = {0: "en punto", 15: "y cuarto", 30: "y media"}.get(ahora.minute, f"y {ahora.minute}")
    if ahora.hour < 6:
        momento = "de la madrugada"
    elif ahora.hour < 12:
        momento = "de la mañana"
    elif ahora.hour < 20:
        momento = "de la tarde"
    else:
        momento = "de la noche"
    return f"{comienzo} {minutos} {momento}."


def texto_fecha(ahora):
    return f"Hoy es {DIAS[ahora.weekday()]} {ahora.day} de {MESES[ahora.month - 1]} de {ahora.year}."


def texto_duracion(segundos):
    minutos = int(segundos // 60)
    dias, resto = divmod(minutos, 1440)
    horas, minutos = divmod(resto, 60)
    partes = []
    if dias:
        partes.append(f"{dias} día" + ("s" if dias != 1 else ""))
    if horas:
        partes.append(f"{horas} hora" + ("s" if horas != 1 else ""))
    if minutos or not partes:
        partes.append(f"{minutos} minuto" + ("s" if minutos != 1 else ""))
    return " y ".join(partes) if len(partes) < 3 else f"{partes[0]}, {partes[1]} y {partes[2]}"


def texto_bateria(porcentaje, enchufada):
    if porcentaje is None:
        return "Esta PC no tiene batería."
    estado = "y está cargando" if enchufada else "y no está enchufada"
    return f"La batería está al {porcentaje} por ciento {estado}."


class _EstadoEnergia(ctypes.Structure):
    _fields_ = [("linea", ctypes.c_ubyte), ("bandera", ctypes.c_ubyte), ("porcentaje", ctypes.c_ubyte),
                ("ahorro", ctypes.c_ubyte), ("segundos", ctypes.c_ulong), ("segundos_carga", ctypes.c_ulong)]


def _leer_bateria():
    estado = _EstadoEnergia()
    ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(estado))
    sin_bateria = estado.porcentaje == 255 or estado.bandera & 128
    return (None if sin_bateria else estado.porcentaje), estado.linea == 1


class _EstadoMemoria(ctypes.Structure):
    _fields_ = [("largo", ctypes.c_ulong), ("uso", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                ("libre", ctypes.c_ulonglong), ("pag_total", ctypes.c_ulonglong),
                ("pag_libre", ctypes.c_ulonglong), ("virt_total", ctypes.c_ulonglong),
                ("virt_libre", ctypes.c_ulonglong), ("ext", ctypes.c_ulonglong)]


def _leer_memoria():
    estado = _EstadoMemoria()
    estado.largo = ctypes.sizeof(_EstadoMemoria)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(estado))
    return estado.uso, estado.total / 2 ** 30


def _informe_hora(entorno):
    return texto_hora(entorno.ahora())


def _informe_fecha(entorno):
    return texto_fecha(entorno.ahora())


def _informe_bateria(entorno):
    return texto_bateria(*_leer_bateria())


def _informe_memoria(entorno):
    uso, total = _leer_memoria()
    return f"Estás usando el {uso} por ciento de la memoria, de {total:.0f} gigas."


def _informe_disco(entorno):
    libre = shutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\").free / 2 ** 30
    return f"Quedan {libre:.0f} gigas libres en el disco del sistema."


def _informe_encendida(entorno):
    segundos = ctypes.windll.kernel32.GetTickCount64() / 1000
    return f"La PC lleva encendida {texto_duracion(segundos)}."


def _informe_ip(entorno):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))   # no manda nada: solo averigua por qué placa saldría
        ip = s.getsockname()[0]
    finally:
        s.close()
    return "La IP de esta PC es " + ip.replace(".", " punto ") + "."


INFORMES = {"hora": _informe_hora, "fecha": _informe_fecha, "bateria": _informe_bateria,
            "memoria": _informe_memoria, "disco": _informe_disco, "encendida": _informe_encendida, "ip": _informe_ip}
