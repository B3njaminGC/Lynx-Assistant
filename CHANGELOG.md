# Historial de versiones

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

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
