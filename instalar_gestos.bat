@echo off
setlocal
cd /d "%~dp0"
title Lynx - instalar lo necesario para los gestos

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

echo Instalando MediaPipe (lo que usa Lynx para reconocer tu mano). Pesa unos 100 MB, tarda un poco...
%PY% -m pip install opencv-python-headless numpy mediapipe
if errorlevel 1 (
  echo.
  echo Algo fallo al instalar. Puede ser que tu version de Python sea muy nueva para MediaPipe.
  echo Sacale una captura a esta ventana y mandamela.
  pause
  exit /b 1
)

%PY% -c "import mediapipe as mp; mp.tasks.vision.HandLandmarker; print('MediaPipe funciona.')"
if errorlevel 1 (
  echo.
  echo MediaPipe se instalo pero no arranca. Sacale una captura a esta ventana y mandamela.
  pause
  exit /b 1
)

echo.
echo La primera vez que prendas la camara, Lynx baja un archivo de 7 MB con el modelo de manos (hace falta internet solo esa vez).
echo Listo. Cerra Lynx y abrilo de nuevo. Con la camara encendida, mostra la palma abierta quieta un segundo.
pause
