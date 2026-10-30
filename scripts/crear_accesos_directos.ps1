# Alternativa SIN instalador: crea los accesos directos «Sistema de Vigilancia UDH» (escritorio y menú Inicio)
# que apuntan a la carpeta empaquetada dist\SistemaVigilanciaUDH. Solo para su usuario; no pide administrador.
#   powershell -ExecutionPolicy Bypass -File scripts\crear_accesos_directos.ps1
$ErrorActionPreference = "Stop"
$raiz = Split-Path $PSScriptRoot -Parent
$exe = Join-Path $raiz "dist\SistemaVigilanciaUDH\SistemaVigilanciaUDH.exe"
if (-not (Test-Path $exe)) { Write-Host "Falta $exe. Ejecute antes: .venv\Scripts\python scripts\construir_escritorio.py" -ForegroundColor Yellow; exit 1 }
$nombre = "Sistema de Vigilancia UDH"
$shell = New-Object -ComObject WScript.Shell
$destinos = @(
  (Join-Path ([Environment]::GetFolderPath("Desktop")) "$nombre.lnk"),
  (Join-Path ([Environment]::GetFolderPath("Programs")) "$nombre.lnk")
)
foreach ($d in $destinos) {
  $lnk = $shell.CreateShortcut($d)
  $lnk.TargetPath = $exe
  $lnk.WorkingDirectory = Split-Path $exe
  $lnk.IconLocation = "$exe,0"
  $lnk.Description = $nombre
  $lnk.Save()
  Write-Host "Acceso directo creado: $d" -ForegroundColor Green
}
