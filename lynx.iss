; Instalador de Lynx (Inno Setup). Lo genera crear_instalador.bat, no hace falta tocarlo.
#define NombreApp "Lynx"
#ifndef Version
  #define Version "1.0"
#endif

[Setup]
AppId={{6F1B7A52-3C1E-4D8B-9A47-2E5C0D7B91A3}
AppName={#NombreApp}
AppVersion={#Version}
AppPublisher=B3njaminGC
DefaultDirName={localappdata}\Programs\Lynx
DefaultGroupName=Lynx
DisableProgramGroupPage=yes
; Se instala en la carpeta del usuario: no pide permisos de administrador y el programa puede guardar su configuración ahí.
PrivilegesRequired=lowest
OutputDir=instalador
OutputBaseFilename=Instalar-Lynx
SetupIconFile=icono.ico
UninstallDisplayIcon={app}\Asistente.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"; Flags: unchecked

[Files]
; Programa y modelo de voz. NO se copian tu config.json, tus comandos ni tus voces de personaje: cada persona arma los suyos.
Source: "dist\Asistente\*"; DestDir: "{app}"; Excludes: "config.json,comandos.json,asistente.log,personajes\*,audios\*,codigo\*,codigo.anterior\*,codigo.fallido\*,respaldos\*"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\Lynx"; Filename: "{app}\Asistente.exe"
Name: "{autodesktop}\Lynx"; Filename: "{app}\Asistente.exe"; Tasks: escritorio

[Run]
Filename: "{app}\Asistente.exe"; Description: "Abrir Lynx ahora"; Flags: nowait postinstall skipifsilent
; Cuando Lynx se actualiza solo (instalación silenciosa) se vuelve a abrir sin preguntar.
Filename: "{app}\Asistente.exe"; Flags: nowait skipifnotsilent
