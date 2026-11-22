# Historial de versiones

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [1.6] — 2026-11-22
### Agregado
- Más de sesenta **acciones de la PC** que aparecen directamente en la lista "¿Qué tiene que hacer?" (suspender, hibernar,
  reiniciar, bloquear, apagar la pantalla, apagar en X tiempo, ventanas y escritorios virtuales, captura y grabación de
  pantalla, copiar/pegar y atajos del navegador, volumen y brillo, modo oscuro/claro, vaciar la papelera, temporizadores).
- **Abrir programa** ahora deja elegir de la lista de apps instaladas (programas de escritorio y de la Store), con buscador.
- La lista de comandos permite **seleccionar varios** (Ctrl para sueltos, Shift para un rango) y borrarlos juntos.
- Tipo **Ejecutar un comando o script** (`.bat`, `.ps1`, `.py` o cualquier comando).
- Los temporizadores avisan en voz alta al terminar, sin interrumpir mientras Lynx espera una orden.

## [1.5] — 2026-11-15
### Agregado
- Acción **Apretar teclas**: pulsa teclas o atajos (`enter`, `ctrl+shift+m`...) con códigos físicos de teclado,
  pensada para juegos.
- Acción **Hacer clic**: hace clic en un lugar de la pantalla que se marca desde la ventana (por ejemplo el botón
  JUGAR); la posición se guarda como fracción de la pantalla y funciona con dos monitores.
- Estos comandos no hablan por defecto, para no tapar el audio del juego.

## [1.4] — 2026-11-13
### Agregado
- Control desde el celular por Telegram: batería, progreso de descargas, "avisame / apagá cuando termine" (con
  cuenta regresiva cancelable), lista de comandos y ejecución de cualquiera de tus comandos. Solo obedece a tu cuenta.
- Pestaña **Respaldo**: guardar y restaurar comandos y ajustes (sin el token de Telegram), copia automática diaria y
  copia antes de cada actualización.
- Actualizaciones por parche de código sin reinstalar (con suma de control, validación y vuelta atrás si falla).
- Pruebas automáticas (`tests/`) y verificación en cada push.

## [1.3] — 2026-11-13
### Agregado
- Control remoto por Telegram (primera versión).
### Cambiado
- Activación: acepta nombres mal escritos por el modelo en frases de una o dos palabras.

## [1.2] — 2026-11-13
### Cambiado
- Activación más permisiva (segunda o tercera palabra, menor confianza) para que detecte mejor.
### Agregado
- Modo diagnóstico para ver qué entiende el reconocimiento de voz.

## [1.1] — 2026-11-11
### Corregido
- Guardar la configuración ya no pisa la salida de audio cambiada por voz.
### Agregado
- Acción para reproducir canciones o carpetas en VLC.
- Instalador de Windows y actualización desde la app (descarga verificada con SHA-256).
- Aviso de versión nueva desde GitHub.

## [1.0] — 2026-11-10
### Agregado
- Primera versión: asistente de voz sin internet, comandos propios, voz de personaje opcional, bandeja del sistema.
