"""Bucle de detección: ventanas deslizantes de audio → modelo → fusión → alerta con evidencia.

No toca hardware ni red: recibe los búferes, el clasificador y una función `enviar`. Por eso se
prueba con audio sintético y un clasificador falso.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from .buffers import BufferAudio, BufferVideo
from .fusion_compartida import Deteccion, fusionar

log = logging.getLogger("edge.detector")


@dataclass
class EventoPendiente:
    alerta: dict
    t_evento: float                  # hora de captura del inicio de la ventana que disparó la alerta
    t_inferencia: float              # cuándo terminó el modelo (para ubicar el cuello de botella de I1)
    listo_en: float                  # se espera el post-evento para que el clip lo incluya


@dataclass
class Detector:
    clasificador: object             # .clasificar(ventana) -> [(clase, confianza, clase_audioset)]
    audio: BufferAudio
    video: BufferVideo | None
    zona: str
    nombre_audio: str
    nombre_video: str | None = None
    ventana_s: float = 1.0
    paso_s: float = 0.5
    pre_s: float = 5.0
    post_s: float = 1.5
    enfriamiento_s: float = 8.0      # no repetir la misma clase en la misma zona dentro de este lapso
    reloj: Callable[[], float] = time.time
    observador: Callable[[np.ndarray, float], None] | None = None   # --diagnostico: ve cada ventana ya clasificada
    _siguiente: int = 0
    _ultima_por_clase: dict = field(default_factory=dict)
    pendientes: list = field(default_factory=list)

    def procesar(self) -> int:
        """Clasifica todas las ventanas completas que haya en el búfer. Devuelve cuántas procesó."""
        sr = self.audio.sr
        n, paso = int(self.ventana_s * sr), int(self.paso_s * sr)
        hechas = 0
        while True:
            ventana = self.audio.ventana(self._siguiente, n)
            if ventana is None:
                if self.audio.total - self._siguiente > 2 * n:          # nos atrasamos: saltar a lo más reciente
                    log.warning("El modelo no alcanza al audio en vivo; se saltan ventanas.")
                    self._siguiente = max(0, self.audio.total - n)
                    continue
                return hechas
            t = self.audio.instante(self._siguiente)
            self._siguiente += paso
            hechas += 1
            self._evaluar(ventana, t)

    def _evaluar(self, ventana: np.ndarray, t: float):
        resultados = self.clasificador.clasificar(ventana)
        if self.observador:
            self.observador(ventana, t)
        if not resultados:
            return
        detecciones = [Deteccion("audio", clase, conf, self.nombre_audio, self.zona, t) for clase, conf, _ in resultados]
        alerta = fusionar(detecciones)
        if not alerta:
            return
        clase = alerta["tipo"].lower()
        if t - self._ultima_por_clase.get(clase, -1e18) < self.enfriamiento_s:
            return
        self._ultima_por_clase[clase] = t
        log.info("Evento: %s (%.2f) a las %.3f", alerta["tipo"], alerta["confianza"], t)
        self.pendientes.append(EventoPendiente(alerta, t, self.reloj(), t + self.ventana_s + self.post_s))

    def listos(self) -> list[EventoPendiente]:
        """Eventos cuyo post-evento ya se grabó; se sacan de la lista de pendientes."""
        ahora = self.reloj()
        listos = [e for e in self.pendientes if ahora >= e.listo_en]
        self.pendientes = [e for e in self.pendientes if ahora < e.listo_en]
        return listos

    def clips(self, e: EventoPendiente) -> tuple[np.ndarray, list]:
        desde, hasta = e.t_evento - self.pre_s, e.listo_en
        fotos = self.video.recorte(desde, hasta) if self.video is not None else []
        return self.audio.recorte(desde, hasta), fotos
