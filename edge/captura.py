"""Captura de audio (sounddevice) y video (OpenCV) con reconexión automática.

Ambas clases corren en hilos propios, escriben en los búferes con la hora real de captura y
exponen `vivo` para los latidos (RNF-02). Los retrasos medidos quedan en `metricas`.
"""
import logging
import os
import re
import threading
import time

import numpy as np

from .buffers import BufferAudio, BufferVideo
from .fusion_compartida import enmascarar_texto

# OpenCV/FFmpeg pueden imprimir la dirección de la cámara (con usuario y clave) en sus propios mensajes.
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
os.environ.setdefault("OPENCV_FFMPEG_LOGLEVEL", "-8")     # AV_LOG_QUIET

log = logging.getLogger("edge.captura")
PATRON_BLUETOOTH = re.compile(r"bluetooth|hands-?free|headset|airpods|buds", re.I)


def esperas_backoff(inicial: float = 1.0, maximo: float = 30.0):
    """1, 2, 4, 8 … hasta `maximo` segundos entre reintentos."""
    espera = inicial
    while True:
        yield espera
        espera = min(maximo, espera * 2)


LIMITE_SIN_AUDIO_S = 3.0      # si ya entregaba audio y deja de hacerlo por más de esto, se considera caído
MARGEN_ARRANQUE_S = 5.0       # tiempo que se espera el primer bloque tras abrir (MME puede tardar ~2 s)
MARGEN_ARRANQUE_VIDEO_S = 10.0


def fuente_viva(ahora: float, abierto_en: float | None, ultimo_bloque: float,
               limite_s: float = LIMITE_SIN_AUDIO_S, margen_arranque_s: float = MARGEN_ARRANQUE_S) -> bool:
    """¿La fuente (micrófono o cámara) está entregando datos? Distingue el arranque (aún sin bloques) de un corte real."""
    if abierto_en is None:
        return False
    if ultimo_bloque >= abierto_en:                    # ya llegó audio desde esta apertura
        return ahora - ultimo_bloque < limite_s
    return ahora - abierto_en < margen_arranque_s     # recién abierto: se le da margen al primer bloque


class CapturaAudio:
    """Micrófono a 16 kHz mono. `dispositivo`: índice de sounddevice o None (predeterminado de Windows)."""

    def __init__(self, buffer: BufferAudio, dispositivo: int | None = None, bloque_s: float = 0.1):
        self.buffer, self.dispositivo, self.bloque_s = buffer, dispositivo, bloque_s
        self._detener = threading.Event()
        self._abierto_en: float | None = None
        self.ultimo_error: str | None = None
        self._ultimo_bloque = 0.0
        self._latencia = 0.0
        self.metricas = {"latencia_entrada_ms": None, "reconexiones": 0}
        self._hilo = threading.Thread(target=self._bucle, name="captura-audio", daemon=True)

    @property
    def vivo(self) -> bool:
        return fuente_viva(time.time(), self._abierto_en, self._ultimo_bloque)

    def iniciar(self):
        self._hilo.start()

    def detener(self):
        self._detener.set()

    def _callback(self, datos, frames, _info, estado):
        # Hora de la primera muestra = ahora − duración del bloque − latencia de entrada informada por PortAudio.
        t0 = time.time() - frames / self.buffer.sr - (self._latencia or 0.0)
        if estado:
            log.debug("estado de audio: %s", estado)
        self.buffer.agregar(t0, datos[:, 0].copy())
        self._ultimo_bloque = time.time()

    def _bucle(self):
        import sounddevice as sd
        esperas = esperas_backoff()
        while not self._detener.is_set():
            try:
                self._latencia = 0.0
                with sd.InputStream(samplerate=self.buffer.sr, channels=1, dtype="float32", device=self.dispositivo,
                                    blocksize=int(self.buffer.sr * self.bloque_s), callback=self._callback) as s:
                    self._abierto_en = time.time()
                    self._latencia = float(s.latency)
                    self.metricas["latencia_entrada_ms"] = round(self._latencia * 1000, 1)
                    log.info("Micrófono abierto (latencia de entrada %.0f ms).", self._latencia * 1000)
                    esperas = esperas_backoff()
                    while not self._detener.is_set():
                        time.sleep(0.5)
                        if not self.vivo:
                            raise RuntimeError("el micrófono dejó de enviar audio")
            except Exception as e:                       # desconexión, dispositivo ocupado, etc.
                self._abierto_en = None                  # cerrado: los latidos lo informan como desconectado
                espera = next(esperas)
                self.metricas["reconexiones"] += 1
                self.ultimo_error = enmascarar_texto(e)
                log.warning("Micrófono no disponible (%s). Reintento en %.0f s.", self.ultimo_error, espera)
                self._detener.wait(espera)


class CapturaVideo:
    """Cámara local (índice DirectShow) o URL (RTSP/HTTP). Reduce resolución y muestrea `fps` por segundo."""

    def __init__(self, buffer: BufferVideo, fuente: int | str = 0, fps: float = 10.0, ancho: int = 640):
        self.buffer, self.fuente, self.fps, self.ancho = buffer, fuente, fps, ancho
        # Lo único que se escribe en consola o se envía al servidor: nunca la dirección completa.
        self.descripcion = f"índice {fuente}" if isinstance(fuente, int) else enmascarar_texto(fuente)
        self.ultimo_error: str | None = None
        self._detener = threading.Event()
        self._abierta_en: float | None = None
        self._ultima_foto = 0.0
        self.metricas = {"lectura_ms": None, "fps_real": None, "reconexiones": 0}
        self._hilo = threading.Thread(target=self._bucle, name="captura-video", daemon=True)

    def __repr__(self):
        return f"CapturaVideo({self.descripcion})"

    @property
    def vivo(self) -> bool:
        # RTSP puede tardar varios segundos en entregar la primera imagen: margen mayor que el del micrófono.
        return fuente_viva(time.time(), self._abierta_en, self._ultima_foto, margen_arranque_s=MARGEN_ARRANQUE_VIDEO_S)

    def iniciar(self):
        self._hilo.start()

    def detener(self):
        self._detener.set()

    def _abrir(self):
        import cv2
        cap = cv2.VideoCapture(self.fuente, cv2.CAP_DSHOW) if isinstance(self.fuente, int) else cv2.VideoCapture(self.fuente)
        if isinstance(self.fuente, int):
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)          # pedir el fotograma más reciente, no uno encolado
        if not cap.isOpened():
            cap.release()
            raise RuntimeError("no se pudo abrir la cámara")
        return cap

    def _bucle(self):
        import cv2
        esperas = esperas_backoff()
        while not self._detener.is_set():
            cap = None
            try:
                cap = self._abrir()
                self._abierta_en, self.ultimo_error = time.time(), None
                log.info("Cámara abierta: %s", self.descripcion)
                esperas = esperas_backoff()
                periodo, siguiente, lecturas, fallos = 1.0 / self.fps, 0.0, [], 0
                inicio, n = time.time(), 0
                while not self._detener.is_set():
                    t_pedido = time.time()
                    ok, foto = cap.read()
                    t = time.time()                      # hora de captura (al salir del controlador)
                    if not ok:
                        fallos += 1
                        if fallos >= 10:
                            raise RuntimeError("la cámara dejó de enviar imágenes")
                        time.sleep(0.05)
                        continue
                    fallos = 0
                    lecturas.append((t - t_pedido) * 1000)
                    self._ultima_foto = t
                    if t < siguiente:                    # muestreo: se descartan los fotogramas sobrantes
                        continue
                    siguiente = t + periodo
                    if foto.shape[1] > self.ancho:
                        alto = int(foto.shape[0] * self.ancho / foto.shape[1])
                        foto = cv2.resize(foto, (self.ancho, alto), interpolation=cv2.INTER_AREA)
                    self.buffer.agregar(t, foto)
                    n += 1
                    if len(lecturas) >= 50:
                        self.metricas["lectura_ms"] = round(float(np.median(lecturas)), 1)
                        self.metricas["fps_real"] = round(n / (t - inicio), 1)
                        lecturas.clear()
            except Exception as e:
                espera = next(esperas)
                self.metricas["reconexiones"] += 1
                self._abierta_en, self.ultimo_error = None, enmascarar_texto(e)
                log.warning("Cámara %s no disponible (%s). Reintento en %.0f s.", self.descripcion, self.ultimo_error, espera)
                self._detener.wait(espera)
            finally:
                if cap is not None:
                    cap.release()


def listar_fuentes(max_camaras: int = 5) -> dict:
    """Entradas de audio y cámaras locales que entregan imagen (max_camaras=0: solo audio, es instantáneo).

    Limitación conocida: PortAudio lee la lista de audio al arrancar el edge; un micrófono enchufado
    después aparece recién al reiniciar el edge (refrescarla cortaría las capturas abiertas)."""
    import cv2
    import sounddevice as sd
    microfonos = []
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            api = sd.query_hostapis(d["hostapi"])["name"]
            microfonos.append({"indice": i, "nombre": d["name"], "api": api, "bluetooth": bool(PATRON_BLUETOOTH.search(d["name"]))})
    camaras = []
    for i in range(max_camaras):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened() and cap.read()[0]:
            camaras.append({"indice": i, "resolucion": f"{int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}"})
        cap.release()
    return {"microfonos": microfonos, "camaras": camaras}
