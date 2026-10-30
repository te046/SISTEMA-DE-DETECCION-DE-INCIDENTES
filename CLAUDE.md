# CLAUDE.md · Sistema de vigilancia multimodal UDH

Proyecto de tesis de Jorge Luis Salazar Tarazona (Ing. de Sistemas e Informática, UDH, Seminario de Tesis II 2026-II):
«Influencia de un sistema de detección multimodal en la respuesta a incidentes de vigilancia universitaria en Huánuco, 2025».
Diseño pre-experimental G: O1 X O2 (censo N=15, segundo pabellón). Este sistema es la variable independiente (X).

## Reglas de trabajo con la máquina de Teo (obligatorias)
1. **Antes de instalar cualquier cosa**, comprobar si ya está instalada (`pip show`, `where`, `python -c "import x"`). No reinstalar ni cambiar versiones de lo existente.
2. Todo en un entorno virtual dentro del proyecto (`.venv`). No instalar paquetes globales.
3. Tiene otros proyectos corriendo en distintos puertos. **No tocar puertos ocupados**: usar `run.py` (busca uno libre desde el 8000). Nunca matar procesos que no levantó este proyecto.
4. No borrar archivos ni la carpeta `data/` sin pedir permiso. No subir `data/` (claves, base de datos) a ningún repositorio.
5. No leer ni enviar contraseñas, cookies ni credenciales de la laptop. Las claves de cámaras IP se piden por consola/formulario y se guardan solo en `data/` (ver «Seguridad»).
6. No inventar resultados: precisión, recall, F1 y tiempos solo se reportan si salen de una medición real. Lo simulado se marca `origen='simulado'`.
7. Responder en español, claro y sin relleno.

## Estado actual (etapa 1, terminada y probada)
- `backend/app/`: API FastAPI + SQLite. `main.py` (endpoints /api/v1: auth/token, alertas, alertas/{id}/resolucion, deshacer, incidentes, indicadores, dispositivos, salud), `db.py`, `security.py` (scrypt + JWT), `seed.py`, `fusion.py` (fusión video+audio y prioridad, función pura probada), `config.py` (secretos autogenerados en `data/`).
- `frontend/`: panel web en HTML, CSS y JavaScript sin framework (`js/app.js` renderiza por funciones; `js/api.js` cliente). Diseño aprobado por Teo: ver «Diseño».
- `scripts/simular.py` y `scripts/limpiar_simulados.py`. Pruebas: `cd backend && python -m pytest -q` (13 pasan). Debe seguir en verde.
- Arranque: `python run.py`. La ingesta de alertas usa `POST /api/v1/alertas` con `X-Api-Key` = contenido de `data/.ingest_key`.

## Lo que falta (tu trabajo): etapas 2, 3 y 4

### Requisito nuevo de Teo: multifuente con descubrimiento automático
El sistema debe **detectar solo** las fuentes disponibles, **mostrarlas en una lista y dejar conectarlas desde el panel**:
- **Cámaras:** (a) webcam o cámara USB/integrada de la laptop, (b) cámara IP por RTSP/ONVIF en la red local, (c) teléfono usado como cámara (stream RTSP/HTTP de una app como IP Webcam) — si Teo se refería a otro tercer tipo, preguntarle.
- **Micrófonos:** el integrado, USB, y los **Bluetooth ya emparejados en Windows** (aparecen como entradas de audio del sistema).
- **Bluetooth:** el escaneo debe **listar los dispositivos Bluetooth cercanos** (por ejemplo con `bleak`), pero aclarar en la interfaz que el emparejamiento se hace en Windows y que solo los de audio entran como micrófono. Las cámaras no se conectan por Bluetooth: no prometerlo.
- Cada fuente conectada actualiza la tabla `dispositivos` (estado, último latido) y aparece en «Estado del sistema». Si una se desconecta, el panel ya muestra el aviso y la alerta usa solo la evidencia disponible (RN-01).

Propuesta técnica (puedes mejorarla, pero justifica los cambios):
- Nuevo paquete `edge/` (Python) que corre como proceso aparte y habla con la API por HTTP; no mezclar captura pesada dentro del proceso web.
- `edge/descubrir.py`: cámaras locales con OpenCV (backend DirectShow en Windows; usar `pygrabber` solo si ya está o es necesario para los nombres), cámaras IP con WS-Discovery/ONVIF y prueba de URL RTSP, audio con `sounddevice` (lista de entradas, marcando las Bluetooth por nombre/API), Bluetooth con `bleak`.
- API nueva (con rol responsable/admin): `GET /api/v1/descubrimiento` (lanza o consulta el escaneo), `POST /api/v1/dispositivos` (registrar fuente: tipo, nombre, URI o índice, zona), `POST /api/v1/dispositivos/{id}/conectar` y `/desconectar`, `DELETE` con confirmación. Las URIs RTSP con usuario y clave se guardan cifradas con una clave derivada de `SECRET_KEY`; nunca se devuelven completas al frontend.
- Panel: pantalla «Dispositivos» (o ampliar «Estado del sistema»): botón «Buscar dispositivos», lista de lo encontrado con tipo e icono, botón «Conectar», formulario para agregar una cámara IP a mano (nombre, URL RTSP, zona), estados cargando/vacío/error con solución, y vista previa en vivo de la cámara conectada (MJPEG o instantáneas cada 1 s servidas por la API; sin WebRTC al inicio).

### Etapa 2: captura
- Video: lectura continua con reconexión automática (backoff), reducción de resolución y muestreo de fotogramas configurable. Medir y registrar el retraso real de captura.
- Audio: ventanas deslizantes (por ejemplo 1 s con paso de 0,5 s) a 16 kHz mono. Guardar clips cortos (5–10 s alrededor del evento) como evidencia, no el audio continuo.
- Cada evento lleva `detectado_en` con el instante real del evento (hora de la captura, no la hora de la inferencia) para que I1 TTD sea honesto.

### Etapa 3: modelos
- **Audio:** clasificador de eventos (empezar con YAMNet o PANNs preentrenados) mapeando a las clases del diseño: rotura de vidrio, grito, choque, disparo. Umbral configurable.
- **Video:** partir de un detector preentrenado (por ejemplo YOLO nano) para personas/objetos y una regla de «evento visual» documentada. **Dejar claro que es una línea base**: la detección de eventos de seguridad propiamente dicha requiere datos del pabellón; no declarar métricas sin medirlas.
- Fusión: reutilizar `fusion.py` (agrupa por zona y ventana de 3 s). Emitir la alerta con `POST /api/v1/alertas`, adjuntando `evidencia_video` y `evidencia_audio` (archivos en `data/evidencias/`, servidos por la API con autenticación) para que el panel los reproduzca.
- Objetivo de diseño RNF-01: alerta visible en ≤ 5 s desde la detección. Medirlo y mostrarlo en Indicadores (I1); si no se cumple, informar el cuello de botella real.
- Aceleración: usar la GPU (CUDA) solo si está disponible; si no, CPU con modelos pequeños. Comprobar antes qué hay instalado.

### Etapa 4: medición para la tesis
- Exportar a CSV las alertas con sus marcas de tiempo (`detectado_en`, `generado_en`, `resuelto_en`), decisión y clics, para el pretest/postest.
- Herramienta de **etiquetado** (verdad de campo): marcar si el evento fue real para poder calcular recall y F1 (hoy solo hay precisión = confirmadas ÷ resueltas).
- Registro de disponibilidad (RNF-02 ≥ 95 %) a partir de los latidos de los dispositivos.

### Etapa 5: paso al servidor (sustentación)
Dockerfile + `docker-compose` (API, proxy Caddy con HTTPS, PostgreSQL), variables de entorno para secretos, guía de despliegue en el README. Probar en local antes. La captura se queda en el equipo edge; el servidor recibe alertas y sirve el panel.

## Pendientes acordados con Teo (no hacer sin su OK)
- **Calibración del audio:** calibrar el umbral por clase con un conjunto de calibración y otro de evaluación
  separados (sin mezclar grabaciones), y medir las falsas alarmas con audio ambiente del pabellón. Hasta
  entonces no cambiar el umbral (0,50) ni el mapeo de clases de `edge/clasificador_audio.py`.
  Contexto: con `python -m edge --microfono 1 --diagnostico` el micrófono Intel Smart Sound de la laptop entregó
  muchos tramos de −90 dBFS exactos y ninguna clase del mapeo; la causa (¿supresión de ruido de Windows?) no está probada.
  La ruta WDM-KS (sin efectos de Windows) también queda pendiente.
- **Regla de persistencia (propuesta, NO aplicada):** alertar solo si la clase supera el umbral de la fusión en
  k = 2 ventanas seguidas (paso 0,5 s; suma ~0,5 s a I1). Para clases impulsivas (vidrio, disparo, choque) evaluar
  también «2 de 3». Evaluación: elegir k ∈ {1, 2, 3, 2 de 3} solo con el conjunto de calibración; informar en el de
  evaluación precisión, recall, F1 y falsas alarmas por hora (audio ambiente) por clase, e I1, con y sin la regla.
- **Umbral de fusión provisional:** `VIGILANCIA_UMBRAL_FUSION` / `--umbral-fusion` existen solo para demostraciones.
  Las mediciones de la tesis usan 0,50 hasta calibrar.
- **Video (línea base):** VideoMAE RWF-2000 (CC BY-NC 4.0, procedencia en `edge/modelos/PROCEDENCIA.md`). Medir
  precisión/recall con grabaciones de prueba etiquetadas antes de declarar cualquier métrica; la exactitud del autor
  (0,73) no es un resultado del proyecto.
- **Definición operativa de I1 (actualizar en la documentación de Teo):** hay DOS indicadores con nombre distinto.
  «I1 · Detección (hasta el servidor)» = generado_en − detectado_en (sin cambios). «I1 visible (hasta el panel)» =
  mostrado_en − detectado_en, donde mostrado_en lo fija el SERVIDOR al recibir el aviso del panel (incluye el
  trayecto de red del aviso y requiere el panel abierto en «Alertas»). RNF-01 («visible en ≤ 5 s») se evalúa con
  «I1 visible». Teo debe reflejarlo en la operacionalización de variables de su tesis.
- **Etapa 5: cambiar el sondeo del panel (hoy cada 1 s) por SSE o WebSocket**, para no cargar el servidor y
  bajar el «I1 visible».
- **Sesiones de medición:** `python -m edge --sesion tesis` etiqueta las filas de `data/mediciones_latencia.csv`
  que van al análisis; por defecto es «prueba». Una sesión «tesis» no admite el umbral de fusión provisional.
- **`.venv-export/` (869 MB):** entorno aparte con PyTorch CPU y transformers que solo sirve para re-exportar el
  modelo de video (`scripts/exportar_modelo_video.py`). No forma parte de la app. Teo decide cuándo borrarlo:
  no tocarlo sin su OK.
- **Cámaras IP automáticas:** búsqueda ONVIF/WS-Discovery de cámaras en la red local. Hoy se agregan a mano en
  «Buscar dispositivos» (dirección validada y cifrada).
- **Webcam local:** en la laptop de Teo no se detecta (permiso de Windows, obturador u otra app). Ese camino solo
  está cubierto por pruebas automáticas.

## Orden sugerido
1. Descubrimiento y registro de dispositivos (API + panel), con pruebas. 2. Captura de video y audio con una webcam y el micrófono de la laptop. 3. Audio YAMNet → alertas de punta a punta. 4. Video base → fusión. 5. Cámaras IP/RTSP y Bluetooth. 6. Medición y exportación. 7. Docker. Al terminar cada paso: pruebas en verde, README actualizado y un resumen corto para Teo.

## Diseño del panel (no cambiar sin pedirlo)
Plus Jakarta Sans; verde UDH `#0B5F55` (acciones), `#1FB09E` (decoración), menta `#E6F5F2`, fondo `#F4F8F7`, texto `#10302D`; coral `#C93A22` solo para urgencia (prioridad alta, avisos, errores). Texto ≥ 16 px, objetivos táctiles ≥ 44 px, contraste AA, el estado nunca solo por color, mensajes de error que dicen qué pasó y cómo resolverlo, botón «Deshacer» tras confirmar/descartar. Mantener pocas palabras por pantalla.

## Seguridad y ética
- Roles: responsable, vigilante, admin. Los vigilantes no cambian dispositivos.
- Credenciales de cámaras cifradas; auditoría de acciones en `auditoria`.
- Audio y video del pabellón son datos sensibles: guardar solo evidencias de alertas, con retención configurable y borrado; mostrar aviso de privacidad. La tesis ya cuenta con documentos de autorización de la entidad; no grabar fuera de la zona autorizada.
- Escapar todo texto que se pinta en el panel (ya hay `esc()` en `app.js`).

## Definición de terminado
Con una webcam y un micrófono reales: el sistema los detecta y lista, se conectan desde el panel, un sonido de prueba (por ejemplo un aplauso fuerte o un audio de prueba reproducido) genera una alerta en el panel con su evidencia en ≤ 5 s, se puede confirmar o descartar, el incidente queda registrado y los indicadores I1–I4 se calculan con esos datos. Pruebas automáticas en verde y README al día.
