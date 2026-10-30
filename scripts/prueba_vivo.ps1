# Prueba guiada EN VIVO con la webcam y el micrófono: movimiento normal y pelea SIMULADA (coreografiada, sin contacto).
#   powershell -ExecutionPolicy Bypass -File scripts\prueba_vivo.ps1                (sesión «prueba»)
#   powershell -ExecutionPolicy Bypass -File scripts\prueba_vivo.ps1 -Sesion tesis  (solo con umbrales por defecto)
# Levanta la API y el edge en un puerto libre, guía 90 s con cuenta regresiva y cierra SOLO los procesos que abrió.
# Las mediciones de I1 quedan en data\mediciones_latencia.csv. Los registros de esta prueba (solo texto) van a %TEMP%;
# el video y el audio de las alertas quedan únicamente en data\evidencias\.
param([ValidateSet("prueba", "tesis")][string]$Sesion = "prueba")
$ErrorActionPreference = "Stop"
$raiz = Split-Path $PSScriptRoot -Parent
$py = Join-Path $raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Host "No encuentro .venv en $raiz. Crea el entorno virtual del proyecto primero." -ForegroundColor Red; exit 1 }

# Puerto libre desde el 8000, sin tocar los de otros proyectos (8080, 8081, 8090).
$reservados = @(8080, 8081, 8090)
$puerto = $null
foreach ($p in 8000..8099) {
  if ($reservados -contains $p) { continue }
  if (-not (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue)) { $puerto = $p; break }
}
if (-not $puerto) { Write-Host "No hay puertos libres entre 8000 y 8099. No toco nada." -ForegroundColor Red; exit 1 }
$base = "http://127.0.0.1:$puerto"

$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
$carpeta = Join-Path $env:TEMP ("prueba_vivo_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
New-Item -ItemType Directory -Path $carpeta | Out-Null
$api = $null; $edge = $null; $falla = $false
$script:crono = New-Object System.Collections.Generic.List[string]
$resp = New-Object System.Collections.Generic.List[string]
$inicioUtc = (Get-Date).ToUniversalTime()

function Pregunta($texto) { $r = Read-Host ("  " + $texto + " (s/n, o escribe una nota)"); $resp.Add(("{0}  =>  {1}" -f $texto, $r)) }
function Paso($num, $texto) { Write-Host ""; Write-Host ("PASO {0}: {1}" -f $num, $texto) -ForegroundColor Yellow }
function Cuenta($pasos, $total) {
  $inicio = Get-Date
  for ($s = 0; $s -lt $total; $s++) {
    $paso = $null
    foreach ($q in $pasos) { if ($s -ge $q[0] -and $s -lt $q[1]) { $paso = $q; break } }
    if ($s -eq $paso[0]) { Write-Host ""; $script:crono.Add(("{0}  (seg {1,2})  {2}" -f (Get-Date -Format "HH:mm:ss"), $s, $paso[2])) }
    $linea = ("  [{0,2}/{1}]  {2}  - faltan {3} s" -f $s, $total, $paso[2], ($paso[1] - $s)).PadRight(110)
    Write-Host ("`r" + $linea) -NoNewline -ForegroundColor $paso[3]
    $espera = (($inicio.AddSeconds($s + 1)) - (Get-Date)).TotalMilliseconds
    if ($espera -gt 0) { Start-Sleep -Milliseconds ([int]$espera) }
  }
  Write-Host ""
}

Write-Host ""
Write-Host "=== ANTES DE EMPEZAR: SEGURIDAD Y CONSENTIMIENTO ===" -ForegroundColor Red
Write-Host "  - La 'pelea' es una SIMULACION COREOGRAFIADA y SIN CONTACTO: empujones al aire, brazos rápidos," -ForegroundColor Yellow
Write-Host "    nadie toca a nadie ni golpea objetos. Lejos de muebles, vidrios y bordes. Paren ante cualquier molestia." -ForegroundColor Yellow
Write-Host "  - Toda persona que salga en cámara debe haber dado su PERMISO para ser grabada." -ForegroundColor Yellow
Write-Host "  - Grabe solo en un espacio autorizado. Los clips quedan en data\evidencias\ (datos sensibles)." -ForegroundColor Yellow
if ((Read-Host "  Escribe 'acepto' para continuar") -ne "acepto") { Write-Host "Prueba cancelada. No se levantó nada." -ForegroundColor Red; exit 1 }

try {
  Write-Host "Levantando la API en el puerto $puerto..." -ForegroundColor Green
  $api = Start-Process -FilePath $py -ArgumentList "run.py", "--port", "$puerto" -WorkingDirectory $raiz `
    -RedirectStandardOutput "$carpeta\api.out" -RedirectStandardError "$carpeta\api.err" -WindowStyle Hidden -PassThru
  $listo = $false
  for ($i = 0; $i -lt 40 -and -not $listo; $i++) {
    Start-Sleep -Milliseconds 500
    try { Invoke-RestMethod "$base/api/v1/salud" -TimeoutSec 2 | Out-Null; $listo = $true } catch { }
  }
  if (-not $listo) { throw "La API no respondió en 20 s. Revisa $carpeta\api.err" }

  Write-Host "Levantando el edge (modo panel, sesión '$Sesion', diagnóstico)..." -ForegroundColor Green
  $edge = Start-Process -FilePath $py -ArgumentList "-m", "edge", "--diagnostico", "--sesion", $Sesion -WorkingDirectory $raiz `
    -RedirectStandardOutput "$carpeta\edge.out" -RedirectStandardError "$carpeta\edge.err" -WindowStyle Hidden -PassThru
  $ok = $false
  for ($i = 0; $i -lt 40 -and -not $ok; $i++) {
    Start-Sleep -Milliseconds 500
    if ($edge.HasExited) { throw "El edge se cerró. Revisa $carpeta\edge.err" }
    if ((Get-Content "$carpeta\edge.err" -Raw -ErrorAction SilentlyContinue) -match "Modo panel") { $ok = $true }
  }
  if (-not $ok) { throw "El edge no arrancó en 20 s. Revisa $carpeta\edge.err" }

  Start-Process $base
  Paso 1 "Inicia sesión en el panel ($base) con responsable.vigilancia (escribe tú la clave)."
  Read-Host "  Enter cuando hayas entrado"

  Paso 2 "En 'Buscar dispositivos': elige 'Zona 1', pulsa 'Buscar' y luego 'Conectar' en la WEBCAM y en el micrófono Intel."
  Read-Host "  Enter cuando ambos digan 'Conectada'"
  Start-Sleep 3
  $err = Get-Content "$carpeta\edge.err" -Raw -ErrorAction SilentlyContinue
  $conectadas = ([regex]::Matches($err, "Conectada: ")).Count
  if ($conectadas -lt 2) { Write-Host "  Aviso: el edge registra $conectadas fuente(s) conectada(s); se esperaban 2 (cámara y micrófono)." -ForegroundColor Yellow }
  if ($err -match "Sin modelo de video") { Write-Host "  Aviso: no está el modelo de video; la cámara solo grabará evidencia." -ForegroundColor Yellow }
  Pregunta "¿La webcam y el micrófono aparecen 'Conectada' en Zona 1?"

  Paso 3 "Deja el panel en la pantalla 'Alertas' (así se mide el I1 visible). Colócate a 1-2 m de la webcam."
  Read-Host "  Enter para empezar la cuenta de 5 s"
  for ($i = 5; $i -ge 1; $i--) { Write-Host ("  Empieza en {0}... recuerda: coreografía SIN CONTACTO" -f $i) -ForegroundColor Green; Start-Sleep 1 }
  $pasos = @(
    @(0, 10, "QUIETO frente a la cámara (línea base)", "DarkGray"),
    @(10, 25, "MOVIMIENTO NORMAL: camina, saluda, siéntate y levántate", "Cyan"),
    @(25, 35, "QUIETO", "DarkGray"),
    @(35, 50, ">>> PELEA SIMULADA SIN CONTACTO + VOCES ELEVADAS (discusión fuerte)", "Magenta"),
    @(50, 60, "QUIETO y en silencio", "DarkGray"),
    @(60, 75, ">>> PELEA SIMULADA SIN CONTACTO, EN SILENCIO (solo video)", "Yellow"),
    @(75, 90, "QUIETO y en silencio", "DarkGray")
  )
  Cuenta $pasos 90
  Write-Host "  Esperando 5 s a que se cierren los últimos eventos..." -ForegroundColor DarkGray
  Start-Sleep 5

  Paso 4 "Mira la cola de alertas y abre cada una."
  Read-Host "  Enter cuando las hayas revisado"
  Pregunta "¿Cuántas alertas aparecieron, de qué tipo y con qué prioridad?"
  Pregunta "¿Se reproducen el video y el audio de la evidencia?"
  Write-Host "  El 'I1 visible' (hasta que se pinta en el panel) se ve en la pantalla 'Indicadores'." -ForegroundColor DarkGray
  Read-Host "  Enter para cerrar y ver el resumen"
}
catch { $falla = $true; Write-Host ("`nERROR: " + $_.Exception.Message) -ForegroundColor Red }
finally {
  foreach ($proc in @($edge, $api)) {                 # solo los procesos que abrió este script
    if ($proc -and -not $proc.HasExited) { & taskkill /PID $proc.Id /T /F | Out-Null }
  }
}

Start-Sleep 1
if (Get-NetTCPConnection -LocalPort $puerto -State Listen -ErrorAction SilentlyContinue) {
  Write-Host "Aviso: el puerto $puerto sigue ocupado." -ForegroundColor Yellow
} else { Write-Host "Puerto $puerto libre. Los puertos 8080, 8081 y 8090 no se tocaron." -ForegroundColor Green }

$errLineas = @(Get-Content "$carpeta\edge.err" -Encoding UTF8 -ErrorAction SilentlyContinue)
$decisiones = @($errLineas | Where-Object { $_ -match "Decisión" })
$enviadas = @($errLineas | Where-Object { $_ -match "Alerta .* enviada" })
$csv = Join-Path $raiz "data\mediciones_latencia.csv"
$filas = @()
if (Test-Path $csv) {
  $filas = @(Import-Csv $csv -Encoding UTF8 | Where-Object { $_.sesion -eq $Sesion -and ([datetime]::Parse($_.generado_en)).ToUniversalTime() -ge $inicioUtc })
}
$res = @()
$res += "SESIÓN: $Sesion   PUERTO: $puerto"
$res += ""; $res += "RESPUESTAS:"; $res += $resp
$res += ""; $res += "CRONOLOGÍA (hora real de cada tramo; sirve como verdad de campo para etiquetar):"; $res += $script:crono
$res += ""; $res += ("DECISIONES DEL DETECTOR ({0}):" -f $decisiones.Count); $res += $decisiones
$res += ""; $res += ("ALERTAS ENVIADAS ({0}):" -f $enviadas.Count); $res += $enviadas
$res += ""; $res += "MEDICIONES DE ESTA PRUEBA (data\mediciones_latencia.csv) — I1 hasta el servidor:"
$res += ($filas | Select-Object codigo, tipo, prioridad, modalidades, inferencia_s, espera_post_s, subida_s, total_s, con_video | Format-Table -AutoSize | Out-String).TrimEnd()
$res += ""; $res += "I1 visible (hasta el panel): pantalla 'Indicadores' del panel."
$res | Out-File "$carpeta\resumen.txt" -Encoding UTF8
Write-Host ""; $res | ForEach-Object { Write-Host $_ }
Write-Host ("`nResumen (solo texto) guardado en: $carpeta\resumen.txt") -ForegroundColor Cyan
