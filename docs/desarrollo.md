# Guía para quien mantiene el proyecto

Notas para compilar, empaquetar y publicar Lynx. Si solo querés usarlo, alcanza con el [README](../README.md).

## Compilar y publicar versiones

### Crear el `.exe`

Ejecutá **`crear_exe.bat`**. Deja el programa en `dist\Asistente\` (con el modelo de voz, tus comandos
y tus personajes al lado). Podés copiar esa carpeta entera donde quieras.

### Crear el instalador

Después de `crear_exe.bat`, ejecutá **`crear_instalador.bat`**. Arma `instalador\Instalar-Lynx.exe`
(instala Inno Setup solo si falta): un único archivo que se instala como cualquier programa, con acceso
en el menú Inicio, desinstalador y sin pedir permisos de administrador. No incluye tu configuración ni
tus comandos: cada persona arma los suyos.

### Publicar un release

Lynx mira una vez al día (y al abrirse) si hay un *release* más nuevo en GitHub; si lo hay, la ventana de
configuración muestra un botón "Descargar". Si Lynx está instalado con `Instalar-Lynx.exe`, el botón dice "Actualizar ahora": baja el instalador del release, comprueba su SHA-256 y se reinstala en silencio, conservando tu configuración y tus comandos. Nunca instala nada sin que toques el botón, y el aviso se apaga desde la pestaña General.
Para sacar una versión: subí el número `VERSION` en `actualizar.py`, corré `crear_exe.bat` y
`crear_instalador.bat`, y publicá un release (con la etiqueta `v` + el número) con `Instalar-Lynx.exe` adjunto (con ese nombre exacto).

### Actualizaciones por parche (sin reinstalar)

Para cambios chicos de código: `python empaquetar.py` genera `codigo-base1.zip` y su suma de control.
Subilo a un release (etiqueta `v` + número, por ejemplo `v1.5`) con ese nombre exacto, y la app instalada
lo aplica sola cuando tocás "Actualizar ahora". Si el parche falla al arrancar, vuelve a la versión
anterior. Si el cambio suma librerías nuevas, hace falta un release completo con `Instalar-Lynx.exe`.

## Estructura

| Archivo | Para qué sirve |
|---|---|
| `app.py` | Arranque, bandeja del sistema y ciclo de vida |
| `nucleo.py` | Motor de voz: escucha, reconoce, ejecuta comandos y habla |
| `personajes.py` | Voz de personaje con Applio (cola, caché de frases) |
| `importar.py` | Descarga e importación de voces |
| `ventanas.py`, `configurar.py` | Ventana de configuración y círculo animado |
| `estilo.py` | Tema oscuro e ícono |
| `remoto.py` | Control desde el celular (Telegram) |
| `respaldo.py` | Exportar, restaurar y copias automáticas |
| `actualizar.py` | Buscar e instalar versiones nuevas |
| `lanzador.py`, `empaquetar.py` | Arranque del `.exe` y armado de parches |
| `lynx.iss` | Receta del instalador (Inno Setup) |
| `tests/` | Pruebas automáticas (pytest) |

## Agregar una acción de la PC

Las acciones del tipo "Acción de la PC" están todas en `acciones_pc.py`, en la tabla `CATALOGO`: una línea por acción
(clave, grupo, nombre, cómo se hace, qué dice, ¿pide confirmación?). Para sumar una de teclas o de
"abrir" alcanza con una línea nueva; para algo más especial se agrega una función en `FUNCIONES` o `INFORMES`.
`tests/test_acciones_pc.py` revisa que las teclas existan y que no se repitan claves.

## Cámara (`camara.py`)

La cámara se maneja desde el hilo de las ventanas (tkinter), no desde el de la voz. El camino de una orden de voz es:
acción `camara_encender` → `Entorno.camara(True)` → `Motor.pedir_camara` → `App._pedido_de_camara` (solo avisa por
`cola_ui`) → `App._encender_camara` → `ControlDeCamara.encender()`. Para apagarse sola, `App._camara_apagada` le pide al
motor que lo diga con `Motor.avisar` (lo habla cuando está libre).

- `Captura` (hilo) lee la cámara a 8 cuadros por segundo en 320x240 y deja el último cuadro como imagen PPM, que
  tkinter muestra sin librerías extra. Detecta movimiento comparando cuadros en gris (`hay_movimiento`).
- `ControlDeCamara.vigilar()` se llama cada 100 ms desde `App._bucle`: dibuja el cuadro y apaga si venció `Inactividad`.
- Las pruebas (`tests/test_camara.py`) usan una ventana y una cámara de juguete: no hace falta cámara ni pantalla.

### Gestos (`gestos.py`)

- `DetectorDeManos` (MediaPipe) devuelve los 21 puntos de la mano; es lo único de los gestos que no se prueba sin cámara.
  `Captura` lo crea dentro de su hilo y, si MediaPipe no está, la cámara sigue sin gestos.
- `clasificar_mano` mira cuántos dedos están estirados (palma / puño / otro) y `Reconocedor.paso(puntos, ahora)`
  es una máquina de estados: palma quieta 1 s → "activado" → deslizar o puño → "desactivado" por tiempo. Todo recibe el
  tiempo desde afuera, así `tests/test_gestos.py` lo prueba con manos dibujadas a mano.
- `valor_de_gesto(gesto, exe, config)` elige qué hacer: tu config, el perfil de la app (`PERFILES_POR_APP`) o el del
  escritorio. Los valores son claves de `acciones_pc`, `teclas:...` o `media:...`. Para sumar una app, una línea en
  `PERFILES_POR_APP` (el nombre del `.exe` en minúsculas).
- `App._hacer_gesto` ejecuta el gesto en un hilo aparte con la app que esté adelante (`ventana_activa_exe`).
- Falta: una pantalla en la configuración para editar los gestos por app (hoy se hace en `config.json`),
  y el dedo como mouse (pellizco para hacer clic).
