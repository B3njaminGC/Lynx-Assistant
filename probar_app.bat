@echo off
setlocal
cd /d "%~dp0"
title Asistente de voz - probar la aplicacion

set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (
  python --version >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo No encuentro Python. Instalalo desde python.org tildando "Add Python to PATH".
  pause
  exit /b 1
)

echo Instalando lo necesario (la primera vez tarda un poco)...
%PY% -m pip install -r requisitos_app.txt
if errorlevel 1 (
  echo.
  echo Algo fallo al instalar. Sacale una captura a esta ventana y mandamela.
  pause
  exit /b 1
)

if not exist "modelo-es" (
  echo Descargando el modelo de voz en espanol...
  powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip' -OutFile 'modelo.zip'; Expand-Archive -Path 'modelo.zip' -DestinationPath '.' -Force"
  ren "vosk-model-small-es-0.42" "modelo-es"
  del modelo.zip
)

echo.
echo Abriendo el asistente. Aparece un icono azul junto al reloj y la ventana de configuracion.
echo Si algo falla, queda escrito en asistente.log (en esta misma carpeta).
%PY% app.py
echo.
echo El asistente se cerro. Si fue por un error, mira asistente.log.
pause
