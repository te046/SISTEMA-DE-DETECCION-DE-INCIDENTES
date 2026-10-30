# Compila el instalador con Inno Setup 6 (si está instalado). No instala nada en el sistema.
#   powershell -ExecutionPolicy Bypass -File instalador\compilar_instalador.ps1
$ErrorActionPreference = "Stop"
$raiz = Split-Path $PSScriptRoot -Parent
$dist = Join-Path $raiz "dist\SistemaVigilanciaUDH\SistemaVigilanciaUDH.exe"
if (-not (Test-Path $dist)) {
  Write-Host "Falta la aplicación empaquetada. Primero ejecute:" -ForegroundColor Yellow
  Write-Host "  .venv\Scripts\python scripts\construir_escritorio.py"
  exit 1
}
$candidatos = @(
  (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
  "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
  "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$iscc = $candidatos | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { $iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source }
if (-not $iscc) {
  Write-Host "No encuentro Inno Setup 6 (ISCC.exe)." -ForegroundColor Yellow
  Write-Host "  1. Descárguelo de https://jrsoftware.org/isdl.php e instálelo (puede elegir 'solo para mí')."
  Write-Host "  2. Vuelva a ejecutar este script."
  Write-Host "  Alternativa sin instalador: scripts\crear_accesos_directos.ps1 crea los accesos a dist\SistemaVigilanciaUDH."
  exit 1
}
& $iscc (Join-Path $PSScriptRoot "SistemaVigilanciaUDH.iss")
if ($LASTEXITCODE -eq 0) { Write-Host "Instalador listo en: $(Join-Path $raiz 'dist\instalador')" -ForegroundColor Green }
exit $LASTEXITCODE
