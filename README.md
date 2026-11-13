<p align="center"><img src="icono.png" width="120" alt="Lynx"></p>

# Lynx — asistente de voz sin internet

Un asistente de voz para **Windows** que funciona **100 % offline**: lo llamás por su nombre
("Lynx") y le decís qué hacer. Abre y cierra programas, abre páginas web, apaga la PC (con
confirmación) y te responde hablando. Vive en la bandeja del sistema, con un círculo animado que
reacciona a tu voz.

- **Reconocimiento de voz local** con [Vosk](https://alphacephei.com/vosk/) (modelo en español).
  Nada se envía a internet.
- **Comandos propios**: agregás, editás y borrás frases desde la ventana de configuración, sin tocar código.
- **Voz de personaje (opcional)**: el asistente puede hablar con la voz de un personaje usando
  modelos RVC a través de [Applio](https://github.com/IAHispano/Applio). Cada frase se prepara una
  sola vez en segundo plano y después suena al instante.
- **Importar voces desde la app**: pegás el link de una voz (Hugging Face, voice-models.com...) o
  elegís un `.zip` que ya bajaste.
- **Elegir por dónde habla**: parlantes o auriculares, también por voz ("Lynx, habla por los auriculares").
- Tema oscuro, ícono en la bandeja, inicio automático con Windows y creación de un `.exe`.

## Requisitos

- Windows 10 u 11
- [Python 3.10 o más nuevo](https://www.python.org/downloads/) (tildá **"Add Python to PATH"** al instalarlo)
- Un micrófono
- Solo para la voz de personaje: placa de video NVIDIA recomendada y varios GB libres (Applio)

## Cómo usarlo

1. Descargá este repositorio (**Code → Download ZIP**) y descomprimilo.
2. Hacé doble clic en **`probar_app.bat`**. La primera vez instala las dependencias y baja el
   modelo de voz en español (unos 40 MB). Después abre el asistente.
3. Aparece un ícono junto al reloj y la ventana de configuración. Decí **"Lynx"** y una frase, por
   ejemplo *"Lynx, abrí YouTube"*.

Los comandos de ejemplo están en `comandos.ejemplo.json`; la primera vez se copian a `comandos.json`
y desde ahí los editás en la pestaña **Comandos**.

### Tipos de comandos

| Tipo | Qué hace |
|---|---|
| Abrir programa | Ejecuta un `.exe` o un programa de Windows (`notepad.exe`) |
| Cerrar programa | Cierra un proceso por su nombre (`notepad.exe`) |
| Cerrar varios | Cierra una lista de programas |
| Abrir página web | Abre un link en tu navegador |
| Apagar la PC | Apaga la computadora (siempre pide confirmación si lo marcás) |
| Cambiar salida de audio | Cambia el dispositivo por el que habla el asistente |
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

## Crear el `.exe`

Ejecutá **`crear_exe.bat`**. Deja el programa en `dist\Asistente\` (con el modelo de voz, tus comandos
y tus personajes al lado). Podés copiar esa carpeta entera donde quieras.

## Crear el instalador

Después de `crear_exe.bat`, ejecutá **`crear_instalador.bat`**. Arma `instalador\Instalar-Lynx.exe`
(instala Inno Setup solo si falta): un único archivo que se instala como cualquier programa, con acceso
en el menú Inicio, desinstalador y sin pedir permisos de administrador. No incluye tu configuración ni
tus comandos: cada persona arma los suyos.

## Control desde el celular (Telegram)

En la pestaña **Celular** creás un bot propio con @BotFather, pegás su token y tu ID de Telegram, y desde
el celular le preguntás a tu PC "cuánto va la descarga", "cuánta batería tengo", le pedís "apagá la PC
cuando termine la descarga" (avisa y apaga con cuenta regresiva cancelable) o le mandás cualquiera de tus
comandos. Solo obedece a tu cuenta; los mensajes de otras cuentas se ignoran. Usa internet únicamente para
hablar con Telegram. El token queda en tu `config.json` (que no se sube a GitHub): no lo compartas.

## Versiones nuevas

Lynx mira una vez al día (y al abrirse) si hay un *release* más nuevo en GitHub; si lo hay, la ventana de
configuración muestra un botón "Descargar". Si Lynx está instalado con `Instalar-Lynx.exe`, el botón dice "Actualizar ahora": baja el instalador del release, comprueba su SHA-256 y se reinstala en silencio, conservando tu configuración y tus comandos. Nunca instala nada sin que toques el botón, y el aviso se apaga desde la pestaña General.
Para sacar una versión: subí el número `VERSION` en `actualizar.py`, corré `crear_exe.bat` y
`crear_instalador.bat`, y publicá un release (con la etiqueta `v` + el número) con `Instalar-Lynx.exe` adjunto (con ese nombre exacto).

## Estructura

| Archivo | Para qué sirve |
|---|---|
| `app.py` | Arranque, bandeja del sistema y ciclo de vida |
| `nucleo.py` | Motor de voz: escucha, reconoce, ejecuta comandos y habla |
| `personajes.py` | Voz de personaje con Applio (cola, caché de frases) |
| `importar.py` | Descarga e importación de voces |
| `ventanas.py`, `configurar.py` | Ventana de configuración y círculo animado |
| `estilo.py` | Tema oscuro e ícono |

## Licencia

[MIT](LICENSE). Vosk, Applio y los modelos de voz tienen sus propias licencias.
