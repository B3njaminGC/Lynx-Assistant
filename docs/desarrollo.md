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
