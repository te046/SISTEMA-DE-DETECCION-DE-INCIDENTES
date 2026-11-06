# Sistema de Vigilancia UDH · aplicativo de escritorio

Sistema de detección multimodal (audio + video) para la tesis «Influencia de un sistema de detección multimodal en
la respuesta a incidentes de vigilancia universitaria en Huánuco, 2025». Es un **aplicativo de escritorio para
Windows**: abre su propia ventana, se instala con ícono en el escritorio y en el menú Inicio, detecta y conecta
cámaras y micrófonos, genera alertas con evidencia (clip de audio y video), y registra incidentes, indicadores I1–I4
y la verdad de campo para precisión, recall y F1.

> El panel también se puede abrir en un navegador, **solo como ayuda de desarrollo** (`python run.py`). Toda prueba
> manual y todo script usan la ventana de escritorio.

Manual breve para el vigilante y para la sustentación: [`MANUAL.md`](MANUAL.md). Decisiones técnicas: [`DECISIONES.md`](DECISIONES.md).

## Estado y límites (léase antes de presentar resultados)
- **Video = línea base.** «Posible agresión» con VideoMAE afinado en RWF-2000 (CC BY-NC 4.0). No está calibrado con
  video del pabellón y **no hay métricas medidas en este proyecto** (la exactitud 0,73 del autor no es nuestra).
  El panel lo marca «Video: línea base».
- **Audio sin calibrar.** YAMNet con umbral 0,50 y el mapeo de clases de diseño. La calibración por clase y la regla
  de persistencia están **pendientes** (ver `plan_de_trabajo.md`). No hay métricas medidas del audio.
- **Condición de uso:** apague las **«Mejoras de audio»** del micrófono en Windows (Configuración › Sistema ›
  Sonido › Entrada › su micrófono). Con ellas encendidas, el micrófono Intel Smart Sound entregó largos tramos de
  silencio digital (−90 dBFS) y ninguna clase del mapeo.
- **Webcam local:** en la laptop de desarrollo no se detectaba al construir esta parte; ese camino solo está cubierto
  por pruebas automáticas. Las cámaras IP y el teléfono, también.
- Sin búsqueda automática de cámaras IP (ONVIF): se agregan a mano. Docker/servidor: trabajo futuro (sección final).

## Instalar (usuario final)
1. Ejecute `Instalar_SistemaVigilanciaUDH_1.0.0.exe` (se instala **solo para su usuario**, sin administrador).
   Crea los accesos «Sistema de Vigilancia UDH» en el escritorio y en el menú Inicio.
   *Si aún no hay instalador:* `powershell -ExecutionPolicy Bypass -File scripts\crear_accesos_directos.ps1`
   crea los mismos accesos a la carpeta empaquetada `dist\SistemaVigilanciaUDH`.
2. Ábralo. La **primera vez** aparece la ventana «Claves iniciales»: anótelas, **se muestran una sola vez** y no
   quedan en ningún archivo ni registro.
3. *(Opcional)* Modelo de video: `powershell -ExecutionPolicy Bypass -File scripts\instalar_modelo_video.ps1`
   (copia el modelo exportado verificando su SHA-256). Sin él, las cámaras solo graban evidencia.
- **Datos** (base de datos, claves internas, evidencias, registro): `%LOCALAPPDATA%\SistemaVigilanciaUDH`.
  El programa se instala en `%LOCALAPPDATA%\Programs\SistemaVigilanciaUDH`. **Desinstalar no borra los datos.**
- **Una sola instancia:** si ya está abierta, la segunda avisa y no arranca. Elige sola un puerto libre (nunca
  8080, 8081 ni 8090). Al cerrar la ventana se detienen la API y la captura: no queda nada corriendo.
- Registro de la aplicación: `%LOCALAPPDATA%\SistemaVigilanciaUDH\registros\app.log`.

## Desarrollo
1. Python 3.10+ y `python -m venv .venv`; luego, dentro de esta carpeta:
   `.venv\Scripts\pip install -r backend/requirements.txt -r edge/requirements.txt -r escritorio/requirements.txt`
2. `.venv\Scripts\python -m edge.descargar_modelos` (YAMNet, 16 MB, verificado con SHA-256).
3. Abrir el aplicativo desde el código: `.venv\Scripts\python -m escritorio` (mismos datos que la versión instalada).
   Opciones: `--sesion tesis`, `--diagnostico`, `--datos <carpeta>` y `--prueba-humo` (sin ventana: arranca,
   comprueba `/salud`, el edge y los modelos, y cierra).
4. Ayudas de desarrollo con el `data\` del proyecto: `python run.py` (API + panel en el navegador) y
   `python -m edge` (modo panel) o `python -m edge --microfono 1 --camara ninguna --diagnostico` (modo manual).
- **Pruebas automáticas** (sin hardware):
  - `cd backend && ..\.venv\Scripts\python -m pytest -q`
  - `.venv\Scripts\python -m pytest edge/tests escritorio/tests -q` (incluye la prueba de humo del aplicativo)
  - `set TZ=America/Lima&& node --test frontend/tests/tiempo.test.mjs`

## Construir el ejecutable y el instalador
1. Ícono (ya generado): `.venv\Scripts\python scripts\generar_icono.py` → `escritorio\recursos\udh.ico`
   (escudo recortado del logo, 16–256 px).
2. Ejecutable: `.venv\Scripts\python scripts\construir_escritorio.py` → `dist\SistemaVigilanciaUDH\` (~240 MB).
   Incluye un arreglo para **Python 3.10.0** (fallo de `dis`, bpo-45757) que solo actúa dentro del proceso de
   PyInstaller. Compruebe: `dist\SistemaVigilanciaUDH\SistemaVigilanciaUDH.exe --prueba-humo --datos %TEMP%\humo`.
3. Instalador: instale Inno Setup 6 (https://jrsoftware.org/isdl.php; puede ser «solo para mí») y ejecute
   `powershell -ExecutionPolicy Bypass -File instalador\compilar_instalador.ps1` → `dist\instalador\`.
- El **modelo de video no va en el paquete** (licencia no comercial, derivado de RWF-2000): se exporta una vez en
  `.venv-export` (~870 MB, aparte de la app) y se copia con `scripts\instalar_modelo_video.ps1`.
  Exportar: `python -m venv .venv-export`; `.venv-export\Scripts\pip install --index-url https://download.pytorch.org/whl/cpu torch`;
  `.venv-export\Scripts\pip install "transformers>=4.40,<5" safetensors onnx onnxruntime`;
  `.venv-export\Scripts\python scripts\exportar_modelo_video.py` (usa `safetensors`, nunca el `.bin`).

## Cómo funciona
- **Proceso único:** la ventana (pywebview/WebView2) ocupa el hilo principal; la API (FastAPI + SQLite) y el edge
  (captura y modelos) corren en hilos propios.
- **Buscar dispositivos:** «Buscar» responde al instante con «Buscando…»; el edge escanea en ≤ 2 s (cámaras, 1–4 s
  más). Los micrófonos repetidos por Windows (MME, DirectSound, WASAPI, WDM-KS) se muestran una vez; se marcan los
  **Bluetooth** y los que **no sirven** (Stereo Mix, entradas virtuales, salidas, solo WDM-KS). Las cámaras IP y el
  teléfono se agregan con dirección `rtsp/rtsps/http/https` y usuario y clave en campos aparte; **guardar no
  conecta**. La dirección se guarda **cifrada** (Fernet derivada de `SECRET_KEY`) y solo se muestra enmascarada
  (`rtsp://***@192.168.1.20:554/stream`); si `SECRET_KEY` cambia, la cámara queda en «▲ Error» con un aviso claro.
  Si no hay cámaras, el panel sugiere revisar el obturador, el permiso de Windows y otras aplicaciones.
- **Audio:** 16 kHz mono, ventanas de 1 s con paso de 0,5 s; YAMNet en CPU (~13 ms por ventana).

  | Clase del diseño | Clases de AudioSet |
  |---|---|
  | rotura de vidrio | Shatter, Glass |
  | grito | Screaming |
  | choque | Smash, crash · Breaking · Bang · Slam |
  | disparo | Gunshot, gunfire · Machine gun |
  | voces elevadas (discusión) | Shout · Yell · Children shouting |

- **Video (línea base):** 640 px y 10 fotogramas/s; cada 1 s clasifica los últimos 1,6 s (16 fotogramas) en un hilo
  aparte. Latencia medida en la laptop de desarrollo (CPU): **~0,78 s por clip** (mediana; máx. 0,87 s).
- **Dos umbrales en serie:** `--umbral` (0,50) decide qué clases son candidatas; la fusión exige 0,50 para alertar.
  Para demostraciones existe un umbral de fusión **PROVISIONAL** (`--umbral-fusion` o `VIGILANCIA_UMBRAL_FUSION`),
  prohibido en sesiones `tesis`.
- **Fusión y prioridad:** video + audio en la misma zona (±3 s) = **alta**; solo video = **baja o media** (media si
  ≥ 0,80); solo audio = media si es urgente (vidrio, grito, disparo). Un incidente genera **una** alerta. Enfriamiento
  de 8 s por clase y zona. RN-01 y RN-02 vigentes.
- **Registro de decisiones:** cada candidata deja «Decisión … → ALERTA | sin alerta: motivo» en el registro (solo texto).
- **Evidencia:** 5 s antes y 1,5 s después, en WAV y WebM/VP8; se ve solo con sesión iniciada.
- **Horas:** todo en UTC con zona; el panel muestra hora local y la fecha si no es de hoy. La API rechaza horas sin zona o futuras.
- **Indicadores:**
  - **I1 · Detección (hasta el servidor)** = `generado_en − detectado_en` (tramos en `mediciones_latencia.csv`).
  - **I1 visible (hasta el panel)** = `mostrado_en − detectado_en`; `mostrado_en` lo fija el servidor al recibir el
    aviso del panel (incluye el trayecto de red) y solo cuenta alertas llegadas **con el panel abierto**; las demás
    se informan aparte. Es el que corresponde a RNF-01. El panel consulta cada 1 s.
  - **I2** (atención), **I3** (precisión = confirmadas ÷ resueltas) e **I4** (falsas alarmas) usan la decisión del vigilante.
  - **Sesión** `prueba` / `tesis` en `mediciones_latencia.csv`; solo `tesis` va al análisis.
- **Medición (pantalla «Medición»):** etiqueta real/falsa por alerta (precisión etiquetada) y registro de **eventos
  reales** (recall). Emparejamiento: misma zona y `detectado_en` entre inicio − 1 s y fin + 5 s. F1 a partir de
  ambos. Sin datos se muestra «—». Exporta `alertas_*.csv` y `eventos_reales_*.csv` (UTF-8 con BOM, sin fórmulas).

## Pruebas guiadas (usan la ventana de escritorio)
- **En vivo con webcam y micrófono:** `powershell -ExecutionPolicy Bypass -File scripts\prueba_vivo.ps1` (o `-Sesion tesis`).
  Con `-EnSeco` solo comprueba arranque, respuesta y cierre ordenado de la app con datos temporales (sin cámara ni micrófono).
  Pide aceptar: pelea **simulada, coreografiada, sin contacto** y con permiso de quien salga en cámara. Abre la app,
  guía 90 s (quieto, movimiento normal, pelea simulada con voces elevadas, pelea simulada en silencio), cierra solo el
  proceso que abrió y resume cronología, decisiones, alertas e I1. La cronología sirve para registrar los eventos reales.
- **Calibración de audio:** `scripts\prueba_audio.ps1` (con el `data\` de desarrollo; resultados solo de diagnóstico).
- Simulación sin cámaras (desarrollo): `scripts\simular.py` y `scripts\limpiar_simulados.py`.

## Seguridad y privacidad
Contraseñas con scrypt, tokens con vencimiento (8 h), bloqueo de 15 min tras 5 intentos, clave aparte para el edge,
auditoría de accesos y decisiones, escape de todo texto en el panel. Evidencias con nombre asignado por el servidor,
solo con sesión, liberadas de memoria al salir. Direcciones de cámaras cifradas y enmascaradas en consola, errores,
auditoría y validaciones. Claves iniciales solo en la ventana. Audio y video del pabellón son datos sensibles: grabe
solo en zonas autorizadas.

## Trabajo futuro (etapa 5: servidor)
Docker + `docker-compose` (API, Caddy con HTTPS, PostgreSQL), secretos por variables de entorno, el edge en el equipo
del pabellón apuntando a `https://servidor`, sondeo del panel reemplazado por SSE o WebSocket, y `panel_activo`
guardado en la base (hoy en memoria, válido para un solo proceso). No se implementó en esta entrega.
