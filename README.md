# Sistema de vigilancia multimodal · UDH (etapas 1–3)

API (FastAPI + SQLite) y panel web (HTML, CSS y JavaScript) del módulo M06, con login, roles, alertas,
incidentes, indicadores I1–I4 y estado de dispositivos. Desde las etapas 2 y 3, el **módulo edge** (`edge/`)
captura audio y video de la laptop, clasifica el audio con YAMNet y envía alertas con su evidencia (clip de
audio y de video) que el vigilante reproduce en el panel.

**Aún no incluye:** el modelo de video (agresión física), el descubrimiento de cámaras IP, del teléfono y de
Bluetooth desde el panel, la exportación para la tesis, la app de escritorio ni Docker.

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
   - `python -m edge --listar` muestra los micrófonos (marca los Bluetooth) y las cámaras con su índice.
   - Ejemplo: `python -m edge --microfono 2 --camara 0 --zona "Zona 1"`. Use `--camara ninguna` para solo audio.
   - Al arrancar registra el micrófono y la cámara en «Estado del sistema» y envía latidos cada 5 s. Si una
     fuente falla, el panel la muestra desconectada y el edge reintenta con espera creciente (1, 2, 4… 30 s).
3. Abra la dirección que imprimió `run.py`. La documentación de la API está en `/docs`.

## Cómo funciona la detección (etapas 2 y 3)
- **Audio:** 16 kHz mono, en ventanas de 1 s con paso de 0,5 s. Cada muestra guarda su hora real de captura,
  así `detectado_en` es el instante del evento y no el de la inferencia.
- **Video:** cámara local (DirectShow) o URL, reducida a 640 px de ancho y muestreada a 10 fotogramas/s
  (`--fps`). Por ahora solo sirve de evidencia: **todavía no hay modelo de video**.
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

- **Fusión y prioridad:** se reutiliza `backend/app/fusion.py`, la misma función que en la etapa 1. Una misma
  clase no se repite en la misma zona antes de 8 s.
- **Evidencia:** 5 s antes del evento y 1,5 s después. Se guarda en WAV (audio) y WebM/VP8 (video), formatos
  que reproducen Chrome, Edge y WebView2. Se sube con la clave del edge (`POST /api/v1/evidencias`) y solo se
  ve con sesión iniciada (`GET /api/v1/evidencias/{archivo}`).
- **Tiempos (I1, RNF-01 ≤ 5 s):** cada alerta deja una fila en `data/mediciones_latencia.csv` con los
  tramos de inferencia, espera del post-evento y subida, para ubicar el cuello de botella. Por diseño, el
  I1 incluye la ventana de 1 s y la espera de 1,5 s del clip.

## Probar
- **Pruebas automáticas (no necesitan hardware):**
  - `cd backend && ..\.venv\Scripts\python -m pytest -q`
  - `.venv\Scripts\python -m pytest edge/tests -q`
- **Sin cámaras:** `python scripts/simular.py --url http://127.0.0.1:<puerto> --cantidad 4` envía alertas
  marcadas como `simulado`. `python scripts/limpiar_simulados.py` las borra antes de medir con datos reales.
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
