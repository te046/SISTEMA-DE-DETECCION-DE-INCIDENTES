# Plan de trabajo · Sistema de vigilancia multimodal UDH

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

## Qué es (aclaración de Teo, 30/10/2026)
Es un **APLICATIVO DE ESCRITORIO** (ventana propia con pywebview, ícono en el escritorio, instalador). El panel en el
navegador (`python run.py`) es solo ayuda de desarrollo: **toda prueba manual y todo script usan la ventana de escritorio.**

## Política de decisiones (trabajo autónomo; registrar en DECISIONES.md)
- Decidir lo técnico reversible: nombres, estructura, pruebas, correcciones, documentación.
- Corregir errores y pruebas rotas por cuenta propia (hasta 3 intentos distintos); si no se resuelve, documentar y seguir.
- En la duda, la opción más segura y simple, con una línea de razón en DECISIONES.md.
- Puerto libre antes de levantar algo; solo procesos propios; nunca 8080, 8081 ni 8090. Comprobar antes de instalar;
  instalar solo en `.venv`. No instalar software del sistema (p. ej. Inno Setup): dejar archivos y un script.
- No cambiar umbral ni mapeo de audio, no inventar métricas, no leer claves ni `.ingest_key`, no usar cuentas de Teo.
- PARAR y avisar en el resumen final (sin preguntar) solo si algo es irreversible o borra datos, requiere cuenta o
  credencial, una descarga supera 500 MB, hay que tocar algo fuera de la carpeta, o hay riesgo de privacidad.
- Si el hook `guardia-credenciales` bloquea algo, no buscar otra vía: documentarlo.

## Estado actual (30/10/2026) — detalle en README.md, MANUAL.md y DECISIONES.md
- `backend/app/`: API FastAPI + SQLite (alertas, incidentes, indicadores I1, I1 visible, I2–I4, dispositivos,
  fuentes con direcciones cifradas, evidencias, medición: etiquetado, eventos reales, precisión/recall/F1, CSV).
- `edge/`: captura de audio y video, YAMNet (audio), VideoMAE RWF-2000 (video, LÍNEA BASE), coordinador de zona,
  gestor sincronizado con el panel, servicio detenible (`edge/servicio.py`).
- `escritorio/`: aplicativo (ventana + API + edge en un proceso), instancia única, puerto libre, datos en
  `%LOCALAPPDATA%\SistemaVigilanciaUDH`, ícono, `.spec` de PyInstaller; `instalador/`: Inno Setup por usuario.
- Pruebas: `cd backend && ..\.venv\Scripts\python -m pytest -q`; `.venv\Scripts\python -m pytest edge/tests escritorio/tests -q`;
  `set TZ=America/Lima&& node --test frontend/tests/tiempo.test.mjs`. Deben seguir en verde.
- Del pedido original quedan **sin implementar** (ver Pendientes): disponibilidad RNF-02 calculada a partir de los
  latidos (hoy solo se guarda el último latido), escaneo Bluetooth cercano con `bleak` (hoy solo se marcan los
  micrófonos Bluetooth ya emparejados), vista previa en vivo de la cámara, búsqueda ONVIF y la etapa 5 (Docker).

## Pendientes acordados con Teo (no hacer sin su OK)
- **Condición de uso del audio:** apagar las «Mejoras de audio» de Windows del micrófono (con ellas, el Intel Smart
  Sound entregó silencio digital). Está en README y MANUAL; repetirlo en toda guía de prueba.
- **RNF-02 (disponibilidad ≥ 95 %):** guardar el historial de latidos (hoy solo `ultimo_latido`) y calcular el % por fuente.
- **Bluetooth cercano (`bleak`) y vista previa en vivo de la cámara** (MJPEG o instantánea cada 1 s): del pedido original, no hechos.
- **Etapa 5:** Docker + compose (API, Caddy HTTPS, PostgreSQL), SSE/WebSocket en lugar del sondeo, `panel_activo` en la base.
- **`.claude/settings.json`:** el hook bloqueó crearlo (nombraba carpetas de navegadores); Teo lo crea a mano (ver DECISIONES.md).
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
