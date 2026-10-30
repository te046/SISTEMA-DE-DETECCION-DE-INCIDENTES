# Prueba guiada EN VIVO con la webcam y el micrófono, usando la APLICACIÓN DE ESCRITORIO (no el navegador):
# movimiento normal y pelea SIMULADA (coreografiada, sin contacto).
#   powershell -ExecutionPolicy Bypass -File scripts\prueba_vivo.ps1                (sesión «prueba»)
#   powershell -ExecutionPolicy Bypass -File scripts\prueba_vivo.ps1 -Sesion tesis  (solo con umbrales por defecto)
# Abre la app (instalada, o la de dist\, o desde el código), guía 90 s y al final cierra SOLO el proceso que abrió.
# La app elige sola un puerto libre (nunca 8080, 8081 ni 8090). Las mediciones de I1 quedan en
# %LOCALAPPDATA%\SistemaVigilanciaUDH\mediciones_latencia.csv; los clips, solo en ...\SistemaVigilanciaUDH\evidencias\.
param([ValidateSet("prueba", "tesis")][string]$Sesion = "prueba",
      [switch]$EnSeco)   # -EnSeco: solo arranque y cierre con datos TEMPORALES; sin captura ni preguntas
$ErrorActionPreference = "Stop"
$raiz = Split-Path $PSScriptRoot -Parent
$datos = if ($EnSeco) { Join-Path $env:TEMP ("prueba_vivo_seco_" + (Get-Date -Format "yyyyMMdd_HHmmss")) } else { Join-Path $env:LOCALAPPDATA "SistemaVigilanciaUDH" }
$registro = Join-Path $datos "registros\app.log"
$instalada = Join-Path $env:LOCALAPPDATA "Programs\SistemaVigilanciaUDH\SistemaVigilanciaUDH.exe"
$empaquetada = Join-Path $raiz "dist\SistemaVigilanciaUDH\SistemaVigilanciaUDH.exe"
if (Test-Path $instalada) { $ejecutable = $instalada; $argsApp = @() }
elseif (Test-Path $empaquetada) { $ejecutable = $empaquetada; $argsApp = @() }
else {
  $ejecutable = Join-Path $raiz ".venv\Scripts\pythonw.exe"; $argsApp = @("-m", "escritorio")
  if (-not (Test-Path $ejecutable)) { Write-Host "No encuentro la aplicación ni .venv. Instálela o construya dist\ primero." -ForegroundColor Red; exit 1 }
}
if (Get-Process -Name "SistemaVigilanciaUDH" -ErrorAction SilentlyContinue) {
  Write-Host "La aplicación ya está abierta. Ciérrela y vuelva a ejecutar este script (no cierro procesos que no abrí)." -ForegroundColor Red; exit 1
}

$carpeta = Join-Path $env:TEMP ("prueba_vivo_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
New-Item -ItemType Directory -Path $carpeta | Out-Null
$app = $null; $falla = $false
$script:crono = New-Object System.Collections.Generic.List[string]
$resp = New-Object System.Collections.Generic.List[string]
$inicioUtc = (Get-Date).ToUniversalTime()
$lineasPrevias = if (Test-Path $registro) { @(Get-Content $registro -Encoding UTF8).Count } else { 0 }
function LineasNuevas { if (Test-Path $registro) { @(Get-Content $registro -Encoding UTF8 | Select-Object -Skip $lineasPrevias) } else { @() } }

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
Write-Host "  - Grabe solo en un espacio autorizado. Los clips quedan en la carpeta de datos de la app, subcarpeta evidencias\ (datos sensibles)." -ForegroundColor Yellow
if ($EnSeco) { $argsApp += @("--datos", $datos); Write-Host "MODO EN SECO: datos temporales en $datos; no se conecta cámara ni micrófono." -ForegroundColor Cyan }
elseif ((Read-Host "  Escribe 'acepto' para continuar") -ne "acepto") { Write-Host "Prueba cancelada. No se levantó nada." -ForegroundColor Red; exit 1 }

try {
  Write-Host "Abriendo la aplicación de escritorio (sesión '$Sesion', diagnóstico)..." -ForegroundColor Green
  $app = Start-Process -FilePath $ejecutable -ArgumentList ($argsApp + @("--sesion", $Sesion, "--diagnostico")) -WorkingDirectory $raiz -PassThru
  $ok = $false
  for ($i = 0; $i -lt 60 -and -not $ok; $i++) {
    Start-Sleep -Milliseconds 500
    if ($app.HasExited) { throw "La aplicación se cerró al iniciar. Revise $registro" }
    if ((LineasNuevas) -match "Edge iniciado") { $ok = $true }
  }
  if (-not $ok) { throw "La aplicación no terminó de iniciar en 30 s. Revise $registro" }

  if ($EnSeco) {
    $url = (Get-Content (Join-Path $datos ".api_url") -Raw).Trim()
    $salud = Invoke-RestMethod "$url/api/v1/salud" -TimeoutSec 5
    $panel = (Invoke-WebRequest "$url/" -UseBasicParsing -TimeoutSec 5).StatusCode
    Write-Host ("  La aplicación responde en {0}: salud={1}, panel HTTP {2}." -f $url, $salud.estado, $panel) -ForegroundColor Green
    if ($salud.estado -ne "ok" -or $panel -ne 200) { throw "La aplicación arrancó pero no responde bien." }
    # Cierre ordenado como el botón «X» (sin /F). En un primer inicio hay 2 ventanas (claves + principal).
    for ($i = 0; $i -lt 3 -and -not $app.HasExited; $i++) { & taskkill /PID $app.Id 2>&1 | Out-Null; try { $app | Wait-Process -Timeout 10 } catch { } }
    if (-not $app.HasExited) { throw "La aplicación no se cerró con el cierre ordenado." }
    $finales = LineasNuevas
    if (-not ($finales -match "Sistema detenido")) { throw "La aplicación se cerró sin registrar 'Sistema detenido'." }
    Write-Host "  Cierre ordenado: 'Sistema detenido' registrado; el proceso terminó." -ForegroundColor Green
    $script:secoOk = $true
  }

  if (-not $EnSeco) {
  Paso 1 "En la VENTANA de la aplicación inicie sesión con responsable.vigilancia (escriba usted la clave)."
  Write-Host "  Si es la primera vez, se abrió además la ventana 'Claves iniciales': anótelas antes de cerrarla." -ForegroundColor DarkGray
  Read-Host "  Enter cuando haya entrado"

  Paso 2 "En 'Buscar dispositivos': elija 'Zona 1', pulse 'Buscar' y luego 'Conectar' en la WEBCAM y en el micrófono Intel."
  Read-Host "  Enter cuando ambos digan 'Conectada'"
  Start-Sleep 3
  $nuevas = LineasNuevas
  $conectadas = @($nuevas | Where-Object { $_ -match "Conectada: " }).Count
  if ($conectadas -lt 2) { Write-Host "  Aviso: el registro muestra $conectadas fuente(s) conectada(s); se esperaban 2 (cámara y micrófono)." -ForegroundColor Yellow }
  if ($nuevas -match "Sin modelo de video") { Write-Host "  Aviso: no está el modelo de video; la cámara solo grabará evidencia (scripts\instalar_modelo_video.ps1)." -ForegroundColor Yellow }
  Pregunta "¿La webcam y el micrófono aparecen 'Conectada' en Zona 1?"

  Paso 3 "Deje la ventana en la pantalla 'Alertas' (así se mide el I1 visible). Colóquese a 1-2 m de la webcam."
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
  Read-Host "  Cierre la ventana de la aplicación y pulse Enter para ver el resumen"
  }
}
catch { $falla = $true; Write-Host ("`nERROR: " + $_.Exception.Message) -ForegroundColor Red }
finally {
  if ($app -and -not $app.HasExited) {                 # solo el proceso que abrió este script
    try { $app | Wait-Process -Timeout 20 } catch { }
    if (-not $app.HasExited) { & taskkill /PID $app.Id /T /F | Out-Null; Write-Host "La aplicación no se cerró sola: se cerró el proceso que abrió este script." -ForegroundColor Yellow }
  }
}

$puerto = $null
$archivoUrl = Join-Path $datos ".api_url"
if (Test-Path $archivoUrl) { $puerto = ([uri](Get-Content $archivoUrl -Raw).Trim()).Port }
if ($puerto -and (Get-NetTCPConnection -LocalPort $puerto -State Listen -ErrorAction SilentlyContinue)) {
  Write-Host "Aviso: el puerto $puerto sigue ocupado." -ForegroundColor Yellow
} elseif ($puerto) { Write-Host "Puerto $puerto libre. Los puertos 8080, 8081 y 8090 no se tocaron." -ForegroundColor Green }

if ($EnSeco) {
  if ($script:secoOk -and -not $falla) { Write-Host "PRUEBA EN SECO: OK (arranque, respuesta y cierre ordenado)." -ForegroundColor Green; exit 0 }
  Write-Host "PRUEBA EN SECO: FALLÓ. Registro: $registro" -ForegroundColor Red; exit 1
}
$errLineas = LineasNuevas
$decisiones = @($errLineas | Where-Object { $_ -match "Decisión" })
$enviadas = @($errLineas | Where-Object { $_ -match "Alerta .* enviada" })
$csv = Join-Path $datos "mediciones_latencia.csv"
$filas = @()
if (Test-Path $csv) {
  $filas = @(Import-Csv $csv -Encoding UTF8 | Where-Object { $_.sesion -eq $Sesion -and ([datetime]::Parse($_.generado_en)).ToUniversalTime() -ge $inicioUtc })
}
$res = @()
$res += "SESIÓN: $Sesion   PUERTO: $puerto   APLICACIÓN: $ejecutable"
$res += ""; $res += "RESPUESTAS:"; $res += $resp
$res += ""; $res += "CRONOLOGÍA (hora real de cada tramo; sirve como verdad de campo para etiquetar):"; $res += $script:crono
$res += ""; $res += ("DECISIONES DEL DETECTOR ({0}):" -f $decisiones.Count); $res += $decisiones
$res += ""; $res += ("ALERTAS ENVIADAS ({0}):" -f $enviadas.Count); $res += $enviadas
$res += ""; $res += "MEDICIONES DE ESTA PRUEBA (mediciones_latencia.csv de la app) — I1 hasta el servidor:"
$res += ($filas | Select-Object codigo, tipo, prioridad, modalidades, inferencia_s, espera_post_s, subida_s, total_s, con_video | Format-Table -AutoSize | Out-String).TrimEnd()
$res += ""; $res += "I1 visible (hasta el panel): pantalla 'Indicadores' del panel."
$res | Out-File "$carpeta\resumen.txt" -Encoding UTF8
Write-Host ""; $res | ForEach-Object { Write-Host $_ }
Write-Host ("`nResumen (solo texto) guardado en: $carpeta\resumen.txt") -ForegroundColor Cyan
