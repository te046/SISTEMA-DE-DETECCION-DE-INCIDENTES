# Genera contraseñas NUEVAS para las 3 cuentas y las muestra UNA sola vez en la ventana «Claves iniciales».
# Las contraseñas anteriores no se pueden recuperar (solo se guardó su hash) y dejan de funcionar.
#   powershell -ExecutionPolicy Bypass -File scripts\restablecer_claves.ps1
$ErrorActionPreference = "Stop"
$raiz = Split-Path $PSScriptRoot -Parent
$instalada = Join-Path $env:LOCALAPPDATA "Programs\SistemaVigilanciaUDH\SistemaVigilanciaUDH.exe"
$empaquetada = Join-Path $raiz "dist\SistemaVigilanciaUDH\SistemaVigilanciaUDH.exe"
$exe = @($instalada, $empaquetada) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $exe) { Write-Host "No encuentro la aplicación (ni instalada ni en dist\)." -ForegroundColor Red; exit 1 }
if (Get-Process -Name "SistemaVigilanciaUDH" -ErrorAction SilentlyContinue) {
  Write-Host "Cierre primero la aplicación y vuelva a ejecutar este script." -ForegroundColor Yellow; exit 1
}
Write-Host "Se abrirá la aplicación y le pedirá confirmar. Tenga a mano dónde anotar las claves nuevas." -ForegroundColor Cyan
Start-Process -FilePath $exe -ArgumentList "--restablecer-claves"
