"""Detección de video de LÍNEA BASE («posible agresión») sobre una cámara conectada.

Cada `paso_s` toma los últimos `ventana_s` de fotogramas, los clasifica en un hilo aparte (~0,8 s por clip
en CPU, para no frenar el audio) y registra la detección en el Coordinador de la zona. Si supera el umbral
de la fusión crea un evento; al cerrarlo se fusiona con el audio de la zona: solo video = baja o media,
video + audio = alta. Expone la misma interfaz que el Detector de audio (procesar, listos, clips).
"""
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from .buffers import BufferAudio, BufferVideo
from .clasificador_video import CLASE
from .detector import Decision, EventoPendiente, cerrar_con_coordinador
from .fusion_compartida import Deteccion, fusionar, umbral_de_fusion

log = logging.getLogger("edge.video")


@dataclass
class MonitorVideo:
    clasificador: object               # .probabilidad(fotos) -> 0..1 y .umbral
    video: BufferVideo
    zona: str
    nombre_video: str
    coordinador: object = None
    audio: BufferAudio | None = None    # micrófono de la misma zona (evidencia), si hay
    ventana_s: float = 1.6              # 16 fotogramas a 10 fps
    paso_s: float = 1.0
    pre_s: float = 5.0
    post_s: float = 1.0
    enfriamiento_s: float = 8.0
    min_fotos: int = 8
    reloj: Callable[[], float] = time.time
    pendientes: list = field(default_factory=list)
    decisiones: deque = field(default_factory=lambda: deque(maxlen=200))
    _ultima_alerta: float = -1e18
    _ultimo_fin: float = -1e18
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _hilo: threading.Thread | None = None
    _detener: threading.Event = field(default_factory=threading.Event)

    # ------------------------------------------------------------ hilo
    def iniciar(self) -> None:
        self._hilo = threading.Thread(target=self._bucle, name=f"video-{self.nombre_video}", daemon=True)
        self._hilo.start()

    def detener(self) -> None:
        self._detener.set()

    def _bucle(self) -> None:
        while not self._detener.is_set():
            inicio = time.time()
            try:
                self.evaluar_ahora()
            except Exception as e:                       # un fallo del modelo no debe tumbar el edge
                log.warning("Fallo del modelo de video: %s", e)
            self._detener.wait(max(0.05, self.paso_s - (time.time() - inicio)))

    # ------------------------------------------------------------ lógica (probada sin hilos)
    def evaluar_ahora(self) -> float | None:
        """Clasifica la ventana más reciente si hay fotogramas nuevos. Devuelve la probabilidad o None."""
        ultimo = self.video.ultimo()
        if ultimo is None or ultimo[0] <= self._ultimo_fin:
            return None
        fotos = self.video.recorte(ultimo[0] - self.ventana_s, ultimo[0])
        if len(fotos) < self.min_fotos:
            return None
        self._ultimo_fin = ultimo[0]
        t0 = fotos[0][0]                                  # hora de captura del inicio de la ventana (I1 honesto)
        p = self.clasificador.probabilidad([f for _, f in fotos])
        if p < self.clasificador.umbral:
            return p
        d = Deteccion("video", CLASE, p, self.nombre_video, self.zona, t0)
        if self.coordinador is not None:
            self.coordinador.registrar(d)
        if p < umbral_de_fusion():
            self._decidir(t0, p, False, f"bajo el umbral de la fusión ({umbral_de_fusion():.2f})")
        elif t0 - self._ultima_alerta < self.enfriamiento_s:
            self._decidir(t0, p, False, f"enfriamiento: hace {t0 - self._ultima_alerta:.1f} s (< {self.enfriamiento_s:.0f} s)")
        else:
            self._ultima_alerta = t0
            alerta = fusionar([d])
            self._decidir(t0, p, True, f"evento de video (línea base), prioridad provisional {alerta['prioridad']}")
            with self._lock:
                self.pendientes.append(EventoPendiente(alerta, t0, self.reloj(), t0 + self.ventana_s + self.post_s))
        return p

    def _decidir(self, t: float, p: float, alerto: bool, motivo: str, clase: str = CLASE, *_):
        d = Decision(t, clase, round(p, 3), "Fight (VideoMAE RWF-2000, línea base)", self.clasificador.umbral,
                     umbral_de_fusion(), alerto, motivo)
        self.decisiones.append(d)
        log.info("Decisión video %s: %s %.2f · umbral %.2f · fusión %.2f → %s: %s", time.strftime("%H:%M:%S", time.localtime(t)),
                 clase, p, d.umbral_clasificador, d.umbral_fusion, "EVENTO" if alerto else "sin alerta", motivo)

    # ------------------------------------------------------------ interfaz común con Detector
    def procesar(self) -> int:
        return 0                                          # la inferencia corre en su hilo

    def listos(self) -> list[EventoPendiente]:
        ahora = self.reloj()
        with self._lock:
            listos = [e for e in self.pendientes if ahora >= e.listo_en]
            self.pendientes = [e for e in self.pendientes if ahora < e.listo_en]
        decidir = lambda t, clase, conf, _o, alerto, motivo: self._decidir(t, conf, alerto, motivo, clase)
        return [e for e in listos if cerrar_con_coordinador(self.coordinador, e, self.zona, decidir)]

    def clips(self, e: EventoPendiente) -> tuple[np.ndarray, list]:
        desde, hasta = e.t_evento - self.pre_s, e.listo_en
        audio = self.audio.recorte(desde, hasta) if self.audio is not None else np.zeros(0, np.float32)
        return audio, self.video.recorte(desde, hasta)
