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
| Reproducir música (VLC) | Reproduce canciones o carpetas enteras con VLC |
| Música y volumen | Pista siguiente/anterior, pausa, subir/bajar volumen, silenciar (funciona con Spotify, YouTube y casi cualquier reproductor) |

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
