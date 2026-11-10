@echo off
setlocal
cd /d "%~dp0"
title Asistente de voz - instalar voz de personaje (Applio)

set "APPLIO=C:\Applio"
rem Que la descarga espere mucho mas antes de rendirse (el servidor de NVIDIA a veces es lento)
set "UV_HTTP_TIMEOUT=900"
set "UV_HTTP_RETRIES=8"

echo ==============================================================
echo  Voz de personaje: instala Applio (el programa que cambia la voz)
echo  y descarga la voz de Taeyai.
echo  Ocupa varios GB y tarda un buen rato la primera vez. Dejalo abierto.
echo  Si algo se corta, vuelve a ejecutar este archivo: retoma donde quedo.
echo ==============================================================
echo.

rem ---------------------------------------------------------- 1) Applio
echo [1/3] Descargando Applio...
if exist "%APPLIO%\core.py" (
  echo Ya estaba descargado. Sigo.
) else (
  powershell -NoProfile -Command "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; $z=Join-Path $env:TEMP 'applio.zip'; Invoke-WebRequest 'https://github.com/IAHispano/Applio/archive/refs/heads/main.zip' -OutFile $z; Expand-Archive -Force $z 'C:\'; Remove-Item $z"
  if errorlevel 1 goto :fallo
  if exist "C:\Applio-main" (
    if exist "%APPLIO%" rmdir /s /q "%APPLIO%"
    ren "C:\Applio-main" Applio
  )
)
if not exist "%APPLIO%\core.py" goto :fallo

rem ---------------------------------------------------------- 2) dependencias (con reintentos y comprobacion)
echo.
echo [2/3] Instalando Applio (baja Python y PyTorch; es lo que mas tarda)...
set "INTENTO=0"
:intento
if exist "%APPLIO%\env\python.exe" (
  "%APPLIO%\env\python.exe" -c "import click, torch" >nul 2>&1
  if not errorlevel 1 goto :dependencias_ok
)
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
echo Bajando los modelos base de Applio...
pushd "%APPLIO%"
"env\python.exe" core.py prerequisites
set "CODIGO=%errorlevel%"
popd
if not "%CODIGO%"=="0" goto :fallo

rem ---------------------------------------------------------- 3) personaje
echo.
echo [3/3] Descargando la voz de Taeyai...
if not exist "personajes" mkdir "personajes"
if exist "personajes\Taeyai.zip" (
  echo Ya estaba descargada.
) else if exist "personajes\Taeyai\Taeyai.pth" (
  echo Ya estaba descargada.
) else (
  powershell -NoProfile -Command "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; Invoke-WebRequest 'https://huggingface.co/Timur04129/Taeyai-FNF/resolve/main/Taeyai%%20(FNF%%2C%%20Cyber%%20Sensation).zip?download=true' -OutFile 'personajes\Taeyai.zip'"
  if errorlevel 1 goto :fallo
)

echo.
echo ==============================================================
echo  Listo. Abri el asistente, entra a la pestana "Voz de personaje",
echo  elegi "Taeyai" y toca "Guardar cambios".
echo  Va a preparar las frases solo (unos minutos la primera vez).
echo  Para sumar mas voces: en esa misma pestana pega el link de una voz
echo  y toca "Importar".
echo ==============================================================
pause
exit /b 0

:fallo
echo.
echo Algo fallo. Sacale una captura a esta ventana y mandamela.
echo (Si dice "timed out" o "Failed to download": proba de nuevo, desactiva
echo  un rato el antivirus y el firewall, y fijate que no tengas VPN prendida.
echo  Podes volver a ejecutar este archivo: sigue desde donde quedo.)
pause
exit /b 1
