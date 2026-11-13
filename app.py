"""
Asistente de voz - programa principal.
Corre en segundo plano con un ícono junto al reloj, el círculo animado y la ventana de
configuración. Si lo abrís otra vez estando ya abierto, te muestra la configuración.
"""
import os
import queue
import socket
import sys
import threading
import time
import traceback

if sys.stdout is None:  # programa sin consola: que las librerías no fallen al imprimir
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import tkinter as tk
from tkinter import messagebox

import estilo
import actualizar
import nucleo
import remoto
from ventanas import Circulo, VentanaConfiguracion

PUERTO = 47653  # solo sirve para detectar que ya hay otra copia abierta


def tomar_instancia_unica():
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        servidor.bind(("127.0.0.1", PUERTO))
    except OSError:
        servidor.close()
        return None
    servidor.listen(2)
    return servidor


def avisar_a_la_otra_copia():
    try:
        with socket.create_connection(("127.0.0.1", PUERTO), timeout=2) as conexion:
            conexion.sendall(b"abrir")
    except OSError:
        pass


class App:
    def __init__(self, silencioso, servidor):
        self.cola_ui = queue.Queue()
        self.config = nucleo.cargar_config()
        self.motor = None
        self.ventana = None
        self.icono = None
        self.saliendo = False
        self.error_mostrado = False
        self.actualizacion = None  # actualizar.Nueva si hay una versión nueva
        self.estado_actualizacion = ""  # texto mientras se descarga/instala
        self.actualizando = False

        self.raiz = tk.Tk()
        self.raiz.withdraw()
        estilo.aplicar_tema(self.raiz)
        self.raiz.report_callback_exception = self._error_de_tk
        self.circulo = Circulo(self.raiz, self.config, self._estado_visible, self._nivel)

        self.arrancar_motor()
        self.remoto = remoto.Remoto(self)  # control desde el celular (solo trabaja si lo activás)
        self.remoto.start()
        self._crear_bandeja()
        threading.Thread(target=self._atender_otras_copias, args=(servidor,),
                         daemon=True).start()
        threading.Thread(target=self._buscar_actualizacion, daemon=True).start()
        if not silencioso:
            self.cola_ui.put("configurar")
        self.raiz.after(100, self._bucle)

    # ------------------------------------------------------------ motor

    def arrancar_motor(self):
        self.motor = nucleo.Motor(self.config)
        self.motor.callback_config = self._config_cambiada
        self.motor.start()

    def _config_cambiada(self, clave, valor):
        """Un comando de voz cambió un ajuste (por ejemplo la salida de audio): se guarda."""
        self.config[clave] = valor
        try:
            nucleo.guardar_config(self.config)
        except OSError as error:
            nucleo.log("No pude guardar la configuración:", error)

    def reiniciar_motor(self):
        anterior = self.motor
        pausado = False
        if anterior is not None:
            pausado = anterior.pausado.is_set()
            anterior.parar.set()
            anterior.join(timeout=4)  # que suelte el micrófono antes de abrirlo de nuevo
        self.error_mostrado = False
        self.arrancar_motor()
        if pausado:
            self.motor.pausado.set()

    def _estado_visible(self):
        if self.motor is None or self.motor.pausado.is_set():
            return "dormido"
        return self.motor.estado

    def _nivel(self):
        return self.motor.nivel if self.motor is not None else 0.0

    # ------------------------------------------------------------ configuración

    def aplicar_config(self, nuevo):
        anterior = dict(self.config)
        if nuevo["iniciar_con_windows"] != anterior["iniciar_con_windows"]:
            nucleo.configurar_inicio_con_windows(nuevo["iniciar_con_windows"])
        nucleo.guardar_config(nuevo)
        self.config.clear()
        self.config.update(nuevo)  # el círculo comparte este mismo diccionario
        if nuevo["tamano_circulo"] != anterior["tamano_circulo"]:
            self.circulo.crear()
        if any(nuevo.get(k) != anterior.get(k)
               for k in ("microfono", "activacion", "responder_con_voz", "voz", "voz_velocidad",
                         "personaje", "personaje_tono", "applio_dir", "salida_audio")):
            self.reiniciar_motor()

    def abrir_configuracion(self):
        if self.ventana is not None and self.ventana.winfo_exists():
            self.ventana.deiconify()
            self.ventana.lift()
            self.ventana.focus_force()
            return
        self.ventana = VentanaConfiguracion(self.raiz, self)
        self.ventana.lift()
        self.ventana.focus_force()

    def ventana_cerrada(self):
        self.ventana = None

    # ------------------------------------------------------------ bandeja del sistema

    def _crear_bandeja(self):
        try:
            import pystray
            imagen = estilo.crear_icono(64)
            menu = pystray.Menu(
                pystray.MenuItem("Configurar", lambda *a: self.cola_ui.put("configurar"),
                                 default=True),
                pystray.MenuItem("Pausar escucha", lambda *a: self.cola_ui.put("pausar"),
                                 checked=lambda item: bool(self.motor and self.motor.pausado.is_set())),
                pystray.MenuItem("Salir", lambda *a: self.cola_ui.put("salir")))
            self.icono = pystray.Icon("asistente", imagen, "Asistente de voz (Lynx)", menu)
            self.icono.run_detached()
        except Exception as error:
            self.icono = None
            nucleo.log("Sin ícono junto al reloj:", error)

    # ------------------------------------------------------------ vida de la app

    def _buscar_actualizacion(self):
        """Al arrancar y después una vez al día. Si no hay internet, no pasa nada."""
        while not self.saliendo:
            if self.config.get("buscar_actualizaciones", True):
                hallada = actualizar.consultar()
                if hallada and hallada != self.actualizacion:
                    self.actualizacion = hallada
                    nucleo.log("[versión nueva disponible]", hallada.version)
            time.sleep(24 * 3600)

    def actualizar_ahora(self):
        """Baja el instalador nuevo, lo verifica y lo corre en silencio; Lynx se cierra y vuelve a abrir solo."""
        if self.actualizando or not self.actualizacion:
            return
        self.actualizando = True
        info = self.actualizacion

        def trabajo():
            try:
                self.estado_actualizacion = "Descargando la versión " + info.version + "..."
                ruta = actualizar.descargar_instalador(
                    info, lambda f: setattr(self, "estado_actualizacion",
                                            f"Descargando la versión {info.version}: {int(f * 100)}%"))
                self.estado_actualizacion = "Instalando... Lynx se va a reiniciar solo."
                nucleo.log("[actualización] instalando", info.version)
                actualizar.lanzar_instalador(ruta)
                time.sleep(1.5)
                self.cola_ui.put("salir")
            except Exception as error:
                nucleo.log("[actualización falló]", error)
                self.estado_actualizacion = "No pude actualizar: " + str(error)
                self.actualizando = False

        threading.Thread(target=trabajo, daemon=True).start()

    def _atender_otras_copias(self, servidor):
        while True:
            try:
                conexion, _ = servidor.accept()
            except OSError:
                return
            with conexion:
                conexion.settimeout(1)
                try:
                    datos = conexion.recv(16)
                except OSError:
                    datos = b""
            if datos.startswith(b"abrir"):
                self.cola_ui.put("configurar")

    def _error_de_tk(self, tipo, valor, rastro):
        nucleo.log("[error de interfaz]\n" + "".join(traceback.format_exception(tipo, valor, rastro)))

    def _bucle(self):
        try:
            while True:
                orden = self.cola_ui.get_nowait()
                if orden == "configurar":
                    self.abrir_configuracion()
                elif orden == "pausar":
                    self.alternar_pausa()
                elif orden == "salir":
                    self.salir()
                    return
        except queue.Empty:
            pass
        except Exception:
            nucleo.log("[error en el bucle]\n" + traceback.format_exc())

        motor = self.motor
        if motor is not None and motor.error and not self.error_mostrado:
            self.error_mostrado = True
            self.abrir_configuracion()
            messagebox.showerror(
                "Asistente de voz",
                "El motor de voz no pudo iniciar:\n\n" + motor.error.strip().splitlines()[-1] +
                "\n\nMás detalles en asistente.log (junto al programa).",
                parent=self.ventana)
        if not self.saliendo:
            self.raiz.after(100, self._bucle)

    def alternar_pausa(self):
        if self.motor is None:
            return
        if self.motor.pausado.is_set():
            self.motor.pausado.clear()
        else:
            self.motor.pausado.set()
        if self.icono is not None:
            self.icono.update_menu()

    def salir(self):
        if self.saliendo:
            return
        self.saliendo = True
        nucleo.log("Cerrando el asistente.")
        if self.motor is not None:
            self.motor.parar.set()
        self.remoto.parar.set()
        if self.icono is not None:
            try:
                self.icono.stop()
            except Exception:
                pass
        self.raiz.quit()

    def correr(self):
        self.raiz.mainloop()
        try:
            self.raiz.destroy()
        except Exception:
            pass
        try:
            nucleo.GESTOR.detener()  # que Applio no quede corriendo solo en segundo plano
        except Exception:
            pass
        os._exit(0)  # cierra también los hilos de voz y de la bandeja


def main():
    nucleo.iniciar_log()
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # círculo nítido y bien ubicado en pantallas HiDPI
    except Exception:
        pass
    servidor = tomar_instancia_unica()
    if servidor is None:
        nucleo.log("Ya hay otra copia abierta: le aviso y salgo.")
        avisar_a_la_otra_copia()
        return
    App("--silencioso" in sys.argv, servidor).correr()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        nucleo.log("ERROR FATAL:\n" + traceback.format_exc())
        try:
            raiz = tk.Tk()
            raiz.withdraw()
            messagebox.showerror("Asistente de voz",
                                 "El asistente no pudo iniciar. Mirá asistente.log junto al programa.")
        except Exception:
            pass
        sys.exit(1)
