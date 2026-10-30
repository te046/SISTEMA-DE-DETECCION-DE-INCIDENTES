; Instalador de «Sistema de Vigilancia UDH» (Inno Setup 6). Por usuario, SIN permisos de administrador.
; Compilar: powershell -ExecutionPolicy Bypass -File instalador\compilar_instalador.ps1
; Requiere haber construido antes dist\SistemaVigilanciaUDH\ (scripts\construir_escritorio.py).
; Los datos del usuario viven en %LOCALAPPDATA%\SistemaVigilanciaUDH y el desinstalador NO los borra.

#define Nombre "Sistema de Vigilancia UDH"
#define Version "1.0.0"
#define Exe "SistemaVigilanciaUDH.exe"

[Setup]
AppId={{6F3B1C52-9E1A-4C7B-8D21-5A0C2E7B9F14}
AppName={#Nombre}
AppVersion={#Version}
AppPublisher=Universidad de Huánuco · Ingeniería de Sistemas e Informática
DefaultDirName={localappdata}\Programs\SistemaVigilanciaUDH
DefaultGroupName={#Nombre}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=
OutputDir=..\dist\instalador
OutputBaseFilename=Instalar_SistemaVigilanciaUDH_{#Version}
SetupIconFile=..\escritorio\recursos\udh.ico
UninstallDisplayIcon={app}\{#Exe}
UninstallDisplayName={#Nombre}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "..\dist\SistemaVigilanciaUDH\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#Nombre}"; Filename: "{app}\{#Exe}"; IconFilename: "{app}\{#Exe}"
Name: "{autodesktop}\{#Nombre}"; Filename: "{app}\{#Exe}"; IconFilename: "{app}\{#Exe}"; Tasks: escritorio

[Run]
Filename: "{app}\{#Exe}"; Description: "Abrir {#Nombre}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    MsgBox('Se desinstaló el programa. Sus datos (base de datos, claves y evidencias) se CONSERVARON en:' + #13#10 +
           ExpandConstant('{localappdata}\SistemaVigilanciaUDH') + #13#10#13#10 +
           'Si quiere borrarlos, hágalo a mano después de respaldarlos.', mbInformation, MB_OK);
end;
