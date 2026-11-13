@echo off
setlocal
cd /d "%~dp0"
title Asistente de voz - crear el programa .exe

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

echo ============================================
echo  1/3  Instalando las herramientas
echo ============================================
%PY% -m pip install -r requisitos_app.txt pyinstaller
if errorlevel 1 goto fallo

if not exist "modelo-es" (
  echo.
  echo No esta la carpeta modelo-es. Ejecuta primero probar_app.bat, que la descarga.
  pause
  exit /b 1
)

echo.
echo ============================================
echo  2/3  Creando el programa (puede tardar unos minutos)
echo ============================================
set "EXTRA="
%PY% -c "import estilo; estilo.guardar_ico('icono.ico')"
set "ICONO="
if exist "icono.ico" set "ICONO=--icon icono.ico"
%PY% -c "import piper" >nul 2>&1 && set "EXTRA=--collect-all piper --collect-all onnxruntime"
%PY% -m PyInstaller --noconfirm --clean --windowed --name Asistente %ICONO% ^
  --collect-all vosk --collect-all sounddevice ^
  --hidden-import win32com.client --hidden-import pythoncom --hidden-import pywintypes ^
  --hidden-import comtypes --hidden-import comtypes.client --hidden-import pystray._win32 --hidden-import PIL.ImageTk ^
  %EXTRA% ^
  lanzador.py
if errorlevel 1 goto fallo

echo.
echo ============================================
echo  3/3  Copiando el modelo de voz y tus comandos
echo ============================================
xcopy /E /I /Y "modelo-es" "dist\Asistente\modelo-es" >nul
if exist "voces" xcopy /E /I /Y "voces" "dist\Asistente\voces" >nul
if exist "personajes" xcopy /E /I /Y "personajes" "dist\Asistente\personajes" >nul
if exist "audios" xcopy /E /I /Y "audios" "dist\Asistente\audios" >nul
if exist "comandos.json" copy /Y "comandos.json" "dist\Asistente\" >nul
if exist "comandos.ejemplo.json" copy /Y "comandos.ejemplo.json" "dist\Asistente\" >nul
if exist "config.json" copy /Y "config.json" "dist\Asistente\" >nul

echo.
echo Listo. Tu programa esta en:
echo   %~dp0dist\Asistente\Asistente.exe
echo Podes copiar la carpeta "Asistente" entera a donde quieras (por ejemplo, Documentos).
pause
exit /b

:fallo
echo.
echo Algo fallo en el paso anterior. Sacale una captura a esta ventana y mandamela.
pause
exit /b 1
