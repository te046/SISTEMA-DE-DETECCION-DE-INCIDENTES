# Copia el modelo de video (línea base, CC BY-NC) a la carpeta de datos de la app instalada.
# El instalador no lo incluye para no redistribuir los pesos. Antes, expórtelo una vez:
#   .venv-export\Scripts\python scripts\exportar_modelo_video.py
#   powershell -ExecutionPolicy Bypass -File scripts\instalar_modelo_video.ps1
$ErrorActionPreference = "Stop"
$raiz = Split-Path $PSScriptRoot -Parent
$onnx = Join-Path $raiz "edge\modelos\videomae_rwf2000\videomae_rwf2000.onnx"
$proc = Join-Path $raiz "edge\modelos\PROCEDENCIA_VIDEO.json"
if (-not (Test-Path $onnx)) { Write-Host "Falta $onnx. Expórtelo primero (ver README)." -ForegroundColor Yellow; exit 1 }
$esperado = (Get-Content $proc -Raw | ConvertFrom-Json).sha256."videomae_rwf2000.onnx"
$real = (Get-FileHash $onnx -Algorithm SHA256).Hash.ToLower()
if ($real -ne $esperado) { Write-Host "El SHA-256 del modelo no coincide con PROCEDENCIA_VIDEO.json. No se copió." -ForegroundColor Red; exit 1 }
$destino = Join-Path $env:LOCALAPPDATA "SistemaVigilanciaUDH\modelos"
New-Item -ItemType Directory -Force -Path $destino | Out-Null
Copy-Item $onnx, $proc -Destination $destino -Force
Write-Host "Modelo de video (línea base) copiado y verificado en $destino. Reinicie la aplicación." -ForegroundColor Green
