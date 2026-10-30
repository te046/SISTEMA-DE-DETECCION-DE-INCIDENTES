# Sistema de vigilancia multimodal · UDH (etapas 1–3 y búsqueda de dispositivos)

API (FastAPI + SQLite) y panel web (HTML, CSS y JavaScript) del módulo M06, con login, roles, alertas,
incidentes, indicadores I1–I4 y estado de dispositivos. Desde las etapas 2 y 3, el **módulo edge** (`edge/`)
captura audio y video de la laptop, clasifica el audio con YAMNet y envía alertas con su evidencia (clip de
audio y de video) que el vigilante reproduce en el panel.

Desde el panel, la pantalla **«Buscar dispositivos»** lista las cámaras y los micrófonos del equipo y permite
conectarlos. También se pueden agregar cámaras IP o un teléfono por su dirección.

**Video: línea base.** El modelo de video («posible agresión», VideoMAE afinado con RWF-2000) es una **línea base**:
no está calibrado con video del pabellón y **no tiene métricas medidas en este proyecto**.

**Aún no incluye:** la búsqueda automática de cámaras IP (ONVIF), la exportación para la tesis, la app de
escritorio ni Docker. Los pendientes acordados están en `CLAUDE.md`.

## Instalar (una sola vez, dentro de esta carpeta)
1. Python 3.10 o superior.
2. `python -m venv .venv` y luego `.venv\Scripts\activate`.
3. `pip install -r backend/requirements.txt -r edge/requirements.txt`.
4. `python -m edge.descargar_modelos`. Descarga YAMNet (16 MB) y verifica su SHA-256.

## Arrancar
1. **API y panel:** `python run.py`
   - Busca el primer puerto libre desde el 8000 y **no toca los de sus otros proyectos**. Para uno fijo: `--port 8123`.
   - Deja su dirección en `data/.api_url` para el módulo edge.
   - La primera vez crea la base y las cuentas, y **muestra las claves una sola vez**. Para fijar una clave:
     `set CLAVE_RESPONSABLE=su-clave` antes de la primera ejecución.
2. **Captura y detección**, en otra consola: `python -m edge`
   - **Modo panel (por defecto):** el edge consulta la API cada 2 s y abre o cierra las fuentes que se
     conecten o desconecten en «Buscar dispositivos», **sin reiniciarlo**.
   - **Modo manual (pruebas y calibración):** `python -m edge --microfono 1 --camara ninguna`. Cualquiera
     de las dos opciones activa este modo.
   - `python -m edge --listar` muestra el mismo inventario que ve el panel.
   - `--diagnostico` imprime en la consola, una vez por segundo, el nivel del micrófono (dBFS) y las 3 clases
     de AudioSet con mayor puntaje. Sirve para calibrar el umbral y el mapeo. No guarda ni envía audio.
   - Cada fuente conectada aparece en «Estado del sistema» y envía latidos cada 5 s. Si falla, el panel la
     muestra con error y el edge reintenta con espera creciente (1, 2, 4… 30 s).
3. Abra la dirección que imprimió `run.py`. La documentación de la API está en `/docs`.

## Buscar dispositivos
- **Buscar:** responde al instante con «Buscando…». El edge hace el escaneo en su próxima consulta (≤ 2 s;
  probar las cámaras tarda 1–4 s más). Si el edge no está abierto, el panel lo dice y explica cómo abrirlo.
- **Micrófonos:** el mismo micrófono aparece hasta cuatro veces en Windows (MME, DirectSound, WASAPI y WDM-KS);
  se muestra una sola vez y se captura por MME. Se marcan los **Bluetooth** (ya emparejados en Windows) y los
  que **no sirven**: Stereo Mix (graba lo que suena en los parlantes), entradas virtuales, salidas de audio y
  los que solo existen por WDM-KS (ruta aún no soportada).
- **Cámaras IP y teléfono:** se agregan con nombre, dirección (`rtsp`, `rtsps`, `http` o `https`), usuario y
  clave opcionales (en campos aparte) y zona. **Guardar no conecta:** solo «Conectar» lo hace.
  Ejemplo de teléfono con una app tipo IP Webcam: `http://192.168.1.30:8080/video`.
- **Usuario y clave:** la dirección completa se guarda **cifrada** (Fernet, con una clave derivada de
  `SECRET_KEY`). El panel, la consola, los errores y la auditoría solo muestran la versión enmascarada
  (`rtsp://***@192.168.1.20:554/stream`). La dirección completa solo la entrega
  `GET /api/v1/edge/fuentes/{id}/direccion`, que acepta la clave de ingesta del edge y **nunca** la sesión del panel.
- **Si `SECRET_KEY` cambia o se pierde:** las direcciones guardadas ya no se pueden descifrar. La cámara aparece
  con «▲ Error» y el aviso «Vuelva a agregar la cámara»; el sistema sigue funcionando.
- **Sin cámaras:** si no se detecta ninguna, el panel sugiere revisar el obturador o la tecla de cámara, el
  permiso de Windows (Privacidad › Cámara › aplicaciones de escritorio) y otras aplicaciones que la usen.
- Conectar, desconectar y agregar solo lo pueden hacer los roles responsable y administrador. Los vigilantes ven la lista.

**Cómo se probó:** la cámara local se probó **solo con pruebas automáticas**, porque en la laptop de desarrollo
la webcam todavía no se detecta. Las cámaras IP y el teléfono también se probaron solo con pruebas automáticas
y con un edge simulado, porque no había ninguna disponible. La pantalla se revisó en el navegador con un edge simulado.

**Limitaciones conocidas:** un micrófono enchufado después de abrir el edge aparece recién al reiniciar el
edge, porque PortAudio lee la lista al arrancar y refrescarla cortaría las capturas abiertas. Mientras el edge
tiene abierta una cámara local, esa cámara no responde al escaneo; por eso se mantiene en la lista como «en uso».

## Cómo funciona la detección (etapas 2 y 3)
- **Audio:** 16 kHz mono, en ventanas de 1 s con paso de 0,5 s. Cada muestra guarda su hora real de captura,
  así `detectado_en` es el instante del evento y no el de la inferencia.
- **Video:** cámara local (DirectShow) o URL, reducida a 640 px de ancho y muestreada a 10 fotogramas/s (`--fps`).
- **Modelo de video — LÍNEA BASE:** VideoMAE afinado con RWF-2000 (CC BY-NC 4.0). Cada 1 s clasifica los últimos
  1,6 s (16 fotogramas) en un hilo aparte y da la probabilidad de «posible agresión».
  - **Latencia medida** en la laptop de desarrollo (CPU, 16 núcleos lógicos): **~0,78 s por clip** (mediana; máx. 0,87 s).
  - Licencia, revisión fija y SHA-256 en `edge/modelos/PROCEDENCIA.md`. **No hay métricas medidas**: la exactitud
    de 0,73 que publica su autor no es un resultado de este proyecto. El panel lo marca como «Video: línea base».
  - Se genera **una vez** en un entorno aparte, que no forma parte de la app (~870 MB):
    `python -m venv .venv-export`, luego `.venv-export\Scripts\pip install --index-url https://download.pytorch.org/whl/cpu torch`
    y `.venv-export\Scripts\pip install "transformers>=4.40,<5" safetensors onnx onnxruntime`, y después
    `.venv-export\Scripts\python scripts\exportar_modelo_video.py`. Usa `safetensors` (nunca el `.bin`) y verifica el SHA-256.
  - Sin el modelo, la cámara solo graba evidencia y el edge lo avisa una vez.
- **Modelo de audio:** YAMNet preentrenado en AudioSet, como [conversión ONNX sin reentrenar](https://huggingface.co/audiomagic/yamnet-onnx)
  (Apache 2.0). Corre en CPU, unos 13 ms por ventana en la laptop de desarrollo, así que no necesita GPU.
  Las clases del diseño son grupos de clases de AudioSet (`edge/clasificador_audio.py`):

  | Clase del diseño | Clases de AudioSet |
  |---|---|
  | rotura de vidrio | Shatter, Glass |
  | grito | Screaming |
  | choque | Smash, crash · Breaking · Bang · Slam |
  | disparo | Gunshot, gunfire · Machine gun |
  | voces elevadas (discusión) | Shout · Yell · Children shouting |

- **Dos umbrales en serie:** `--umbral` (0,50 por defecto) decide qué clases del mapeo son *candidatas*; la
  fusión exige además **0,50** (`UMBRAL_MINIMO` en `backend/app/fusion.py`) para generar la alerta. Bajar solo
  `--umbral` muestra más candidatas en el registro, pero **no** produce más alertas; el edge lo avisa al arrancar.
- **Registro de decisiones:** cada candidata deja una línea `Decisión HH:MM:SS: clase confianza (clase de
  AudioSet) · umbral clasificador · umbral fusión → ALERTA | sin alerta: motivo`. Los motivos posibles son:
  bajo el umbral de la fusión, enfriamiento (misma clase hace menos de 8 s) o la alerta y su prioridad.
  Solo se escribe texto: no se guarda audio.
- **Fusión y prioridad** (`backend/app/fusion.py`, regla aprobada el 30/10/2026):
  - **Video y audio coinciden** (misma zona, ±3 s): **alta**, siempre.
  - **Solo video:** **baja**, o **media** si la confianza es ≥ 0,80. Nunca alta.
  - **Solo audio:** media si es urgente (vidrio, grito, disparo); si no, baja o media según la confianza.
  - Un incidente genera **una sola** alerta: el coordinador de zona (`edge/coordinador.py`) junta audio y video,
    y la segunda modalidad que llega se registra como «ya cubierto».
  - Una misma clase no se repite en la misma zona antes de 8 s. RN-01 (sin clasificación de modelo no hay alerta)
    y RN-02 (toda alerta confirmada se registra como incidente) siguen vigentes, con pruebas.
- **Umbral de fusión PROVISIONAL:** para demostraciones, `--umbral-fusion 0.30` o `set VIGILANCIA_UMBRAL_FUSION=0.30`.
  El edge avisa al arrancar. **No usar en las mediciones de la tesis** hasta calibrar; el valor por defecto es 0,50.
- **Horas:** todas se guardan en UTC con zona (`…+00:00`); el panel las muestra en hora local, con la fecha si no
  son de hoy. La API rechaza un `detectado_en` sin zona horaria o en el futuro (más de 2 s), porque corrompería I1.
- **Evidencia:** 5 s antes del evento y 1,5 s después. Se guarda en WAV (audio) y WebM/VP8 (video), formatos
  que reproducen Chrome, Edge y WebView2. Se sube con la clave del edge (`POST /api/v1/evidencias`) y solo se
  ve con sesión iniciada (`GET /api/v1/evidencias/{archivo}`).
- **Tiempos (I1, RNF-01 ≤ 5 s):** cada alerta deja una fila en `data/mediciones_latencia.csv` con los
  tramos de inferencia, espera del post-evento y subida, para ubicar el cuello de botella. Por diseño, el
  I1 incluye la ventana de 1 s y la espera de 1,5 s del clip.

## Probar
- **Pruebas automáticas (no necesitan hardware):**
  - `cd backend && ..\.venv\Scripts\python -m pytest -q`
  - `.venv\Scripts\python -m pytest edge/tests -q` (la prueba del modelo de video real se omite si no se exportó)
  - Panel (horas en zona de Lima, sin dependencias): `set TZ=America/Lima&& node --test frontend/tests/tiempo.test.mjs`
- **Sin cámaras:** `python scripts/simular.py --url http://127.0.0.1:<puerto> --cantidad 4` envía alertas
  marcadas como `simulado`. `python scripts/limpiar_simulados.py` las borra antes de medir con datos reales.
- **Prueba guiada de audio (calibración):** `powershell -ExecutionPolicy Bypass -File scripts\prueba_audio.ps1 -Microfono 1`
  - Comprueba que el puerto 8000 esté libre y abre Configuración › Sonido para apagar las «Mejoras de audio».
  - Levanta la API y el edge en modo manual con `--diagnostico` y guía 90 s con una cronología fija: silencio,
    voz, grito y vidrio desde el teléfono, y un grito propio.
  - Al final cierra solo los procesos que abrió y deja un resumen en `%TEMP%\prueba_audio_<fecha>\resumen.txt`:
    líneas en −90 dBFS, nivel máximo y líneas con nivel > −60 dBFS o con una clase del mapeo.
  - Usa la carpeta `data/` real, igual que `run.py`. Sus resultados sirven para diagnosticar; **no son métricas
    del modelo**.
- **Con la laptop:** arranque `run.py` y `python -m edge`. Luego reproduzca cerca del micrófono, desde el
  teléfono y con volumen alto, un audio de prueba de vidrio rompiéndose o de un grito. Un aplauso **no**
  sirve: no es una de las clases del diseño.

## Datos de diseño que debe calibrar (no son resultados)
Umbral mínimo (0,50), ventana de fusión (3 s), clases urgentes, mapeo de clases de AudioSet, pre/post del
clip y enfriamiento (8 s). **No hay métricas medidas del modelo de audio:** la precisión, el recall y el F1 se
medirán con grabaciones de prueba etiquetadas (etapa 4).

## Paso al servidor (sustentación)
- Cambiar SQLite por PostgreSQL, poner un proxy con HTTPS (Caddy o Nginx) delante y arrancar con
  `uvicorn app.main:app --host 0.0.0.0` detrás del proxy.
- Definir `SECRET_KEY` e `INGEST_KEY` por variables de entorno. No subir la carpeta `data/` a ningún repositorio.
- El edge se queda en el equipo del pabellón (`--api https://servidor`) y sube las evidencias por HTTP.

## Seguridad incluida
Contraseñas con scrypt, tokens firmados con vencimiento (8 h), bloqueo de 15 min tras 5 intentos, clave aparte
para el módulo edge, auditoría de accesos y decisiones, y escape de todo texto mostrado en el panel.
Las evidencias son datos sensibles: el nombre lo asigna el servidor, solo se sirven con sesión iniciada, y el
panel las libera de memoria al cerrar sesión.
