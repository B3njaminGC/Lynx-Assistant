@echo off
setlocal
cd /d "%~dp0"
title Lynx - crear el instalador

if not exist "dist\Asistente\Asistente.exe" (
  echo Primero hay que crear el programa: ejecuta crear_exe.bat y despues volve a abrir este.
  pause
  exit /b 1
)
if not exist "icono.ico" (
  echo Falta icono.ico: ejecuta crear_exe.bat de nuevo.
  pause
  exit /b 1
)

set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"

if not defined ISCC (
  echo Falta Inno Setup, el programa gratuito que arma instaladores. Lo instalo ahora...
  winget install --id JRSoftware.InnoSetup -e --silent --accept-package-agreements --accept-source-agreements
  if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
  if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
)
if not defined ISCC (
  echo No pude instalar Inno Setup solo. Bajalo de https://jrsoftware.org/isdl.php , instalalo y volve a abrir este archivo.
  pause
  exit /b 1
)

set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY python --version >nul 2>&1 && set "PY=python"
set "VERSION=1.0"
if defined PY for /f %%v in ('%PY% -c "import actualizar; print(actualizar.VERSION)"') do set "VERSION=%%v"
echo Armando el instalador de la version %VERSION% (puede tardar un par de minutos)...
"%ISCC%" /DVersion=%VERSION% lynx.iss
if errorlevel 1 (
  echo.
  echo Algo fallo. Sacale una captura a esta ventana y mandamela.
  pause
  exit /b 1
)
echo.
echo Listo. Tu instalador esta en:
echo   %~dp0instalador\Instalar-Lynx.exe
echo Ese unico archivo es el que le pasas a tus amigos.
pause
