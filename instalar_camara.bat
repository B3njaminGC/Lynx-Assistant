@echo off
setlocal
cd /d "%~dp0"
title Lynx - instalar lo necesario para la camara

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

echo Instalando OpenCV (lo que usa Lynx para ver la camara). Tarda un minuto...
%PY% -m pip install opencv-python-headless numpy
if errorlevel 1 (
  echo.
  echo Algo fallo al instalar. Sacale una captura a esta ventana y mandamela.
  pause
  exit /b 1
)

echo.
echo Listo. Cerra Lynx y abrilo de nuevo. Despues crea un comando con la accion "Camara - Encender la camara".
pause
