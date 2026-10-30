param([int]$Microfono = 1)
$ErrorActionPreference = "Stop"
$raiz = Split-Path $PSScriptRoot -Parent   # el script vive en scripts\; la raíz del proyecto es la carpeta de arriba
$py = Join-Path $raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Host "No encuentro .venv en $raiz. Crea el entorno virtual del proyecto primero." -ForegroundColor Red; exit 1 }

# 1) Puerto 8000: si está ocupado, no se toca nada.
if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
  Write-Host "El puerto 8000 está ocupado. No toco nada." -ForegroundColor Red; exit 1
}

# 2) Mejoras de audio de Windows (se apagan a mano)
Write-Host "Abro Sonido. Entrada > Microphone Array > apaga 'Mejoras de audio' (o 'Claridad de voz')." -ForegroundColor Yellow
Start-Process "ms-settings:sound"
Read-Host "Cuando termines presiona Enter (si ya estaba apagado, también Enter)"

$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
$carpeta = Join-Path $env:TEMP ("prueba_audio_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
New-Item -ItemType Directory -Path $carpeta | Out-Null
$api = $null; $edge = $null; $falla = $false
$crono = New-Object System.Collections.Generic.List[string]

try {
  Write-Host "Levantando la API..." -ForegroundColor Green
  $api = Start-Process -FilePath $py -ArgumentList "run.py","--port","8000" -WorkingDirectory $raiz `
    -RedirectStandardOutput "$carpeta\api.out" -RedirectStandardError "$carpeta\api.err" -WindowStyle Hidden -PassThru
  $listo = $false
  for ($i = 0; $i -lt 40 -and -not $listo; $i++) {
    Start-Sleep -Milliseconds 500
    try { Invoke-RestMethod "http://127.0.0.1:8000/api/v1/salud" -TimeoutSec 2 | Out-Null; $listo = $true }
    catch { if ($_.Exception.Response) { $listo = $true } }
  }
  if (-not $listo) { throw "La API no respondió en 20 s. Revisa $carpeta\api.err" }

  Write-Host "Levantando el edge (micrófono $Microfono, sin cámara)..." -ForegroundColor Green
  $edge = Start-Process -FilePath $py -ArgumentList "-m","edge","--microfono","$Microfono","--camara","ninguna","--diagnostico" `
    -WorkingDirectory $raiz -RedirectStandardOutput "$carpeta\edge.out" -RedirectStandardError "$carpeta\edge.err" -WindowStyle Hidden -PassThru
  $ok = $false
  for ($i = 0; $i -lt 60 -and -not $ok; $i++) {
    Start-Sleep -Milliseconds 500
    if ($edge.HasExited) { throw "El edge se cerró. Revisa $carpeta\edge.err" }
    $txt = Get-Content "$carpeta\edge.out" -Raw -ErrorAction SilentlyContinue
    if ($txt -match "\[diag") { $ok = $true }
  }
  if (-not $ok) { throw "El edge no imprimió diagnóstico en 30 s. Revisa $carpeta\edge.err" }

  $pasos = @(
    @(0, 10, "SILENCIO (no te muevas ni hables)", "DarkGray"),
    @(10, 20, "HABLA con voz normal: 'prueba uno, dos, tres'", "Cyan"),
    @(20, 30, "SILENCIO", "DarkGray"),
    @(30, 38, ">>> GRITO DE MUJER desde el teléfono (máximo, a 15 cm)", "Yellow"),
    @(38, 50, "SILENCIO (detén el audio)", "DarkGray"),
    @(50, 58, ">>> VIDRIO ROTO desde el teléfono (máximo, a 15 cm)", "Yellow"),
    @(58, 70, "SILENCIO (detén el audio)", "DarkGray"),
    @(70, 74, ">>> GRITA TÚ: un grito breve y fuerte", "Magenta"),
    @(74, 90, "SILENCIO", "DarkGray")
  )

  Write-Host ""
  for ($i = 5; $i -ge 1; $i--) { Write-Host ("  Empieza en {0}... teléfono en mano, a 15 cm del micrófono" -f $i) -ForegroundColor Green; Start-Sleep 1 }
  $inicio = Get-Date
  for ($s = 0; $s -lt 90; $s++) {
    $paso = $null
    foreach ($q in $pasos) { if ($s -ge $q[0] -and $s -lt $q[1]) { $paso = $q; break } }
    if ($s -eq $paso[0]) {
      Write-Host ""
      $crono.Add(("{0}  (seg {1,2})  {2}" -f (Get-Date -Format "HH:mm:ss"), $s, $paso[2]))
    }
    $linea = ("  [{0,2}/90]  {1}  - faltan {2} s" -f $s, $paso[2], ($paso[1] - $s)).PadRight(105)
    Write-Host ("`r" + $linea) -NoNewline -ForegroundColor $paso[3]
    $espera = (($inicio.AddSeconds($s + 1)) - (Get-Date)).TotalMilliseconds
    if ($espera -gt 0) { Start-Sleep -Milliseconds ([int]$espera) }
  }
  Write-Host ""
  Write-Host "Listo. Cerrando..." -ForegroundColor Green
  Start-Sleep 3
}
catch { $falla = $true; Write-Host ("`nERROR: " + $_.Exception.Message) -ForegroundColor Red }
finally {
  # Solo se cierran los procesos que este script levantó.
  foreach ($proc in @($edge, $api)) {
    if ($proc -and -not $proc.HasExited) { & taskkill /PID $proc.Id /T /F | Out-Null }
  }
}

Start-Sleep 1
if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
  Write-Host "Aviso: el puerto 8000 sigue ocupado." -ForegroundColor Yellow
} else { Write-Host "Puerto 8000 libre. Tus puertos 8080, 8081 y 8090 no se tocaron." -ForegroundColor Green }

if (-not $falla) {
  $lineas = @(Get-Content "$carpeta\edge.out" -Encoding UTF8 | Where-Object { $_ -match "^\[diag" })
  $niveles = @(foreach ($l in $lineas) { if ($l -match "nivel\s+(-?\d+(?:\.\d+)?)\s*dBFS") { [double]$Matches[1] } })
  $ceros = @($niveles | Where-Object { $_ -le -89.9 }).Count
  $max = ($niveles | Measure-Object -Maximum).Maximum
  $rel = @($lineas | Where-Object {
    ($_ -match "nivel\s+(-?\d+(?:\.\d+)?)\s*dBFS" -and [double]$Matches[1] -gt -60) -or
    $_ -match "Glass|Shatter|Scream|Shout|Yell|Gunshot|Explosion|Crash|Breaking"
  })
  $alertas = @(Get-Content "$carpeta\edge.err" -Encoding UTF8 -ErrorAction SilentlyContinue | Select-String -Pattern "alerta" -SimpleMatch)

  $res = @()
  $res += "CRONOLOGÍA (hora real de cada paso):"; $res += $crono
  $res += ""; $res += ("Líneas de diagnóstico: {0} | en -90 dBFS: {1} | nivel máximo: {2} dBFS" -f $lineas.Count, $ceros, $max)
  $res += ("Líneas del edge que mencionan 'alerta': {0}" -f $alertas.Count)
  $res += ""; $res += "LÍNEAS CON NIVEL > -60 dBFS O CON CLASE DEL MAPEO:"; $res += $rel
  $res | Out-File "$carpeta\resumen.txt" -Encoding UTF8
  Write-Host ""; $res | ForEach-Object { Write-Host $_ }
  Write-Host ("`nResumen guardado en: $carpeta\resumen.txt") -ForegroundColor Cyan
}
