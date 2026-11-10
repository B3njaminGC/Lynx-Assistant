@echo off
setlocal
cd /d "%~dp0"
title Asistente de voz - reparar Applio

set "APPLIO=C:\Applio"
rem Que la descarga espere mucho mas antes de rendirse (el servidor de NVIDIA a veces es lento)
set "UV_HTTP_TIMEOUT=900"
set "UV_HTTP_RETRIES=8"

echo ==============================================================
echo  Repara la instalacion de Applio: vuelve a bajar lo que fallo
echo  y comprueba que quede funcionando. Dejalo abierto.
echo ==============================================================
echo.

if not exist "%APPLIO%\core.py" (
  echo No encuentro Applio en %APPLIO%.
  echo Ejecuta primero instalar_voz_personaje.bat.
  pause
  exit /b 1
)

set "INTENTO=0"

:intento
"%APPLIO%\env\python.exe" -c "import click, torch" >nul 2>&1
if not errorlevel 1 goto :dependencias_ok
set /a INTENTO+=1
if %INTENTO% GTR 3 goto :fallo
echo.
echo Instalando las dependencias de Applio - intento %INTENTO% de 3...
pushd "%APPLIO%"
cmd /c "run-install.bat" <nul
popd
goto :intento

:dependencias_ok
echo.
echo Las dependencias de Applio estan bien instaladas.
"%APPLIO%\env\python.exe" -c "import torch; print('Placa de video NVIDIA detectada:', torch.cuda.is_available())"

echo.
echo Bajando los modelos base de Applio...
pushd "%APPLIO%"
"env\python.exe" core.py prerequisites
set "CODIGO=%errorlevel%"
popd
if not "%CODIGO%"=="0" goto :fallo

echo.
echo ==============================================================
echo  Listo. Abri el asistente, entra a la pestana "Voz de personaje",
echo  elegi "Fleetway" y toca "Guardar cambios".
echo ==============================================================
pause
exit /b 0

:fallo
echo.
echo Algo fallo. Sacale una captura a esta ventana y mandamela.
echo (Si dice "timed out" o "Failed to download": proba de nuevo, desactiva
echo  un rato el antivirus y el firewall, y fijate que no tengas VPN prendida.)
pause
exit /b 1
