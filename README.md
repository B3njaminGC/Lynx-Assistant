<p align="center"><img src="icono.png" width="120" alt="Lynx"></p>

# Lynx — asistente de voz sin internet para Windows

[![Pruebas](https://github.com/B3njaminGC/Lynx-Assistant/actions/workflows/pruebas.yml/badge.svg)](https://github.com/B3njaminGC/Lynx-Assistant/actions/workflows/pruebas.yml)
[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-blue.svg)](LICENSE)

Lo llamás por su nombre ("Lynx") y le decís qué hacer: abre y cierra programas, abre páginas, reproduce
música, apaga la PC (con confirmación) y te responde hablando. Vive en la bandeja del sistema, con un círculo
animado que reacciona a tu voz. El reconocimiento de voz es **local**: tu audio no sale de tu computadora.

**Qué es:** un asistente de *comandos* hecho a medida, en español, que vos configurás frase por frase.
**Qué no es:** un chatbot. No conversa ni responde preguntas generales (por ahora).

## Qué puede hacer

- **Reconocimiento de voz local** con [Vosk](https://alphacephei.com/vosk/) (modelo en español).
- **Comandos propios**: agregás, editás y borrás frases desde la ventana de configuración, sin tocar código.
- **Voz de personaje (opcional)**: puede hablar con la voz de un personaje (modelos RVC, vía
  [Applio](https://github.com/IAHispano/Applio)). Cada frase se prepara una sola vez y después suena al instante.
- **Importar voces desde la app**: pegás el link de una voz (Hugging Face, voice-models.com...) o elegís un `.zip`.
- **Elegir por dónde habla**: parlantes o auriculares, también por voz ("Lynx, hablá por los auriculares").
- **Control desde el celular** por Telegram: batería, estado de descargas, apagar al terminar, tus comandos.
- **Respaldo** de comandos y ajustes, y **actualizaciones** desde la propia app, con la descarga verificada.

## Instalación

**Para usarlo** (lo más simple): bajá `Instalar-Lynx.exe` de la sección
[Releases](https://github.com/B3njaminGC/Lynx-Assistant/releases) y ejecutalo. No pide permisos de administrador.
Necesitás Windows 10 u 11 y un micrófono.

**Desde el código** (para probarlo o modificarlo):

1. Instalá [Python 3.10 o más nuevo](https://www.python.org/downloads/) (tildá **"Add Python to PATH"**).
2. Descargá este repositorio y ejecutá **`probar_app.bat`**. La primera vez instala las dependencias y baja el
   modelo de voz en español (unos 40 MB).
3. Aparece un ícono junto al reloj y la ventana de configuración. Decí **"Lynx"** y una frase, por ejemplo
   *"Lynx, abrí YouTube"*.

Los comandos de ejemplo están en `comandos.ejemplo.json`; la primera vez se copian a `comandos.json` y desde
ahí los editás en la pestaña **Comandos**.

## Limitaciones conocidas

- Solo Windows.
- El modelo de voz local es liviano: con ruido o con frases largas se equivoca más que un servicio en la nube.
  Por eso Lynx solo se activa si oye su nombre al principio de la frase y con buena confianza (hay un modo
  diagnóstico en la pestaña General para ver qué entiende).
- La voz de personaje necesita Applio (varios GB) y, idealmente, placa de video NVIDIA.
- El control por Telegram sí usa internet, pero solo para hablar con Telegram.

## Tipos de comandos

| Tipo | Qué hace |
|---|---|
| Abrir programa | Ejecuta un `.exe` o un programa de Windows (`notepad.exe`) |
| Cerrar programa | Cierra un proceso por su nombre (`notepad.exe`) |
| Cerrar varios | Cierra una lista de programas |
| Abrir página web | Abre un link en tu navegador |
| Apagar la PC | Apaga la computadora (siempre pide confirmación si lo marcás) |
| Cambiar salida de audio | Cambia el dispositivo por el que habla el asistente |
| Apretar teclas | Aprieta una tecla o un atajo (`enter`, `ctrl+shift+m`, `w`...), también dentro de juegos |
| Hacer clic | Hace clic en un lugar de la pantalla que marcás vos (por ejemplo el botón JUGAR de un juego) |
| Reproducir música (VLC) | Reproduce canciones o carpetas enteras con VLC |
| Música y volumen | Pista siguiente/anterior, pausa, subir/bajar volumen, silenciar (funciona con Spotify, YouTube y casi cualquier reproductor) |
| Ejecutar un comando o script | Corre un `.bat`, `.ps1`, `.py` o cualquier comando de Windows |
| Acciones de la PC | Más de cien, que aparecen directamente en la lista "¿Qué tiene que hacer?" (ver abajo) |

### Acciones de la PC

Se eligen directamente en la lista "¿Qué tiene que hacer?" del comando nuevo (vienen ordenadas por tema, por ejemplo "Energía · Suspender la PC").
Vos elegís la acción y escribís la frase que querés decir. Todo funciona sin internet y sin instalar nada extra.

| Tema | Ejemplos |
|---|---|
| Energía | suspender, hibernar, reiniciar, cerrar sesión, bloquear, apagar solo la pantalla, apagar en 30 min o 1 hora, cancelar el apagado |
| Ventanas y escritorios | mostrar el escritorio, cambiar de ventana, maximizar/minimizar, ventana a la izquierda/derecha, escritorios virtuales, proyectar |
| Captura y grabación | captura de pantalla (recorte), grabar la pantalla, Barra de juegos, historial del portapapeles, dictado |
| Edición y navegador | copiar, pegar, deshacer, guardar, nueva/cerrar/reabrir pestaña, recargar, volver atrás, buscar en la página |
| Volumen y brillo | volumen al máximo/mitad/bajito, subir/bajar el brillo, brillo al máximo/mitad/mínimo |
| Apariencia y limpieza | modo oscuro/claro, vaciar la papelera, reiniciar el Explorador |
| Programas y ajustes de Windows | administrador de tareas, calculadora, Paint, panel de control, Windows Update, sonido, Wi-Fi, Bluetooth... |
| Carpetas | Descargas, Documentos, Escritorio, Imágenes, Música, Videos, papelera |
| Información | la hora, la fecha, batería, memoria en uso, espacio libre, hace cuánto está encendida la PC, la IP |
| Temporizador | de 5, 10, 15, 30 minutos o 1 hora; avisa cuando termina (sin cortarte si le estás dando una orden) |

Las acciones que pueden hacerte perder trabajo (reiniciar, cerrar sesión, cerrar la ventana, vaciar la papelera)
vienen con confirmación. Detalles: el brillo solo funciona en pantallas de notebook (no en monitores externos), y el
volumen "al máximo/mitad" se logra bajando y subiendo con las teclas de volumen, porque Windows no deja fijarlo
sin programas extra.

### Comandos dentro de un juego

Con **Apretar teclas** y **Hacer clic** podés decir, por ejemplo, "todo listo" y que Lynx haga clic en el botón
JUGAR. En la ventana de comandos, el clic se marca llevando el mouse al botón durante 5 segundos; se guarda como
posición relativa a la pantalla, así que sigue funcionando si cambiás la resolución. Por defecto estos comandos no
hablan, para no pisar el audio del juego (podés ponerles una respuesta si querés).

Algunas advertencias:
- El juego tiene que estar en pantalla y con el mismo menú de siempre: si el botón cambia de lugar, hay que volver a marcarlo.
- Si el juego se abre como administrador, Lynx también tiene que abrirse como administrador.
- Los juegos con anticheat (por ejemplo Fortnite con Easy Anti-Cheat) pueden ignorar o rechazar teclas y clics
  simulados. Probalo con cuidado y revisá las reglas del juego: usalo solo para comodidades de menú, nunca para
  ventajas en la partida.

## Voz de personaje (opcional)

1. Ejecutá **`instalar_voz_personaje.bat`**. Instala Applio en `C:\Applio` (tarda y ocupa varios GB)
   y baja una voz de ejemplo. Si algo falla, volvé a ejecutarlo o usá `reparar_applio.bat`.
2. En la pestaña **Voz de personaje** elegí el personaje, ajustá el tono y tocá **Guardar cambios**.
3. Para sumar más voces: buscá en un sitio de voces, pegá el link y tocá **Importar**
   (o **Importar archivo** si ya bajaste el `.zip`).

> Los modelos de voz **no están incluidos** en este repositorio. Son trabajos de terceros, cada uno con
> sus propias condiciones: respetá la licencia y los créditos de quien los creó, y no uses voces de
> personas reales sin su permiso.

## Control desde el celular (Telegram)

En la pestaña **Celular** creás un bot propio con @BotFather, pegás su token y tu ID de Telegram, y desde
el celular le preguntás a tu PC "cuánto va la descarga", "cuánta batería tengo", le pedís "apagá la PC
cuando termine la descarga" (avisa y apaga con cuenta regresiva cancelable) o le mandás cualquiera de tus
comandos. Solo obedece a tu cuenta; los mensajes de otras cuentas se ignoran. Usa internet únicamente para
hablar con Telegram. El token queda en tu `config.json` (que no se sube a GitHub): no lo compartas.

## Copias de seguridad

En la pestaña **Respaldo** guardás y restaurás todos tus comandos y ajustes (el token de Telegram no se
exporta). Además Lynx hace una copia automática por día en `respaldos\` (guarda las últimas 10) y otra
antes de cada actualización. Al restaurar, primero se guarda lo que tenías.

## Errores y sugerencias

¿Algo no funciona o tenés una idea? Abrí un [issue](https://github.com/B3njaminGC/Lynx-Assistant/issues/new/choose) y completá el formulario. No pegues tu token de Telegram ni datos personales.

## Actualizaciones

Lynx busca una vez al día si hay una versión nueva en GitHub y te avisa en la ventana de configuración. Nunca instala nada sin que toques el botón, y el aviso se apaga desde la pestaña General. Si lo instalaste con `Instalar-Lynx.exe`, "Actualizar ahora" conserva tus comandos y ajustes.

## Desarrollo

Lynx lo desarrolla su autor con ayuda de Claude (de Anthropic) como asistente de programación. Cada cambio se
prueba en una PC real con Windows, y la lógica que se puede verificar sin micrófono ni ventanas tiene pruebas
automáticas:

```
pip install pytest
python -m pytest tests
```

Las pruebas corren en cada push (ver la insignia de arriba). Más detalles en [CONTRIBUTING.md](CONTRIBUTING.md), [docs/desarrollo.md](docs/desarrollo.md) (estructura del código
y cómo se compila) y el historial en [CHANGELOG.md](CHANGELOG.md).

## Licencia

[MIT](LICENSE). Vosk, Applio y los modelos de voz tienen sus propias licencias.
