"""Bucle de detección: ventanas deslizantes de audio → modelo → fusión → alerta con evidencia.

No toca hardware ni red: recibe los búferes, el clasificador y una función `enviar`. Por eso se
prueba con audio sintético y un clasificador falso.
"""
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from .buffers import BufferAudio, BufferVideo
from .fusion_compartida import Deteccion, fusionar, umbral_de_fusion

log = logging.getLogger("edge.detector")


@dataclass
class Decision:
    """Por qué una clase candidata alertó o no. Hay dos umbrales en serie: el del clasificador decide qué
    clases son candidatas, y el de la fusión (backend/app/fusion.py) decide cuáles pueden alertar."""
    t: float
    clase: str
    confianza: float
    clase_audioset: str
    umbral_clasificador: float
    umbral_fusion: float
    alerto: bool
    motivo: str


def cerrar_con_coordinador(coordinador, e: "EventoPendiente", zona: str, decidir) -> bool:
    """Al cerrar un evento: fusiona con todo lo detectado en la zona (audio y video) y evita duplicados.
    Devuelve False si otro evento de la zona ya emitió la alerta de este incidente."""
    if coordinador is None:
        return True
    alerta = fusionar(coordinador.en_ventana(zona, e.t_evento))
    if alerta:
        e.alerta = alerta
    if not coordinador.reclamar(zona, e.t_evento):
        decidir(e.t_evento, e.alerta["tipo"].lower(), e.alerta["confianza"], "-", False,
                "ya cubierto por otra alerta de la misma zona e instante")
        return False
    return True


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
    coordinador: object = None       # Coordinador de zona (audio + video); None = solo audio, como antes
    _siguiente: int = 0
    _ultima_por_clase: dict = field(default_factory=dict)
    pendientes: list = field(default_factory=list)
    decisiones: deque = field(default_factory=lambda: deque(maxlen=200))   # últimas decisiones (para pruebas y diagnóstico)

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
        if not resultados:                              # ninguna clase del mapeo llegó al umbral del clasificador
            return
        detecciones = [Deteccion("audio", clase, conf, self.nombre_audio, self.zona, t) for clase, conf, _ in resultados]
        if self.coordinador is not None:
            for d in detecciones:
                self.coordinador.registrar(d)
        alerta = fusionar(detecciones)
        umbral_fusion = umbral_de_fusion()
        if not alerta:
            for clase, conf, origen in resultados:
                self._decidir(t, clase, conf, origen, False, f"bajo el umbral de la fusión ({umbral_fusion:.2f})")
            return
        clase = alerta["tipo"].lower()
        transcurrido = t - self._ultima_por_clase.get(clase, -1e18)
        if transcurrido < self.enfriamiento_s:
            for c, conf, origen in resultados:
                self._decidir(t, c, conf, origen, False, f"enfriamiento: «{clase}» alertó hace {transcurrido:.1f} s (< {self.enfriamiento_s:.0f} s)")
            return
        self._ultima_por_clase[clase] = t
        for c, conf, origen in resultados:
            fue = c == clase or any(m["clase"] == c for m in alerta["modalidades"])
            self._decidir(t, c, conf, origen, fue, f"alerta «{alerta['tipo']}», prioridad {alerta['prioridad']}" if fue
                          else f"bajo el umbral de la fusión ({umbral_fusion:.2f})")
        self.pendientes.append(EventoPendiente(alerta, t, self.reloj(), t + self.ventana_s + self.post_s))

    def _decidir(self, t: float, clase: str, conf: float, origen: str, alerto: bool, motivo: str):
        """Registra cada decisión (solo texto: no se guarda audio)."""
        d = Decision(t, clase, round(conf, 3), origen, self.umbral_clasificador(), umbral_de_fusion(), alerto, motivo)
        self.decisiones.append(d)
        log.info("Decisión %s: %s %.2f (%s) · umbral clasificador %.2f · umbral fusión %.2f → %s: %s",
                 time.strftime("%H:%M:%S", time.localtime(t)), clase, conf, origen, d.umbral_clasificador,
                 d.umbral_fusion, "ALERTA" if alerto else "sin alerta", motivo)

    def umbral_clasificador(self) -> float:
        return float(getattr(self.clasificador, "umbral", float("nan")))

    def listos(self) -> list[EventoPendiente]:
        """Eventos cuyo post-evento ya se grabó; se sacan de la lista de pendientes."""
        ahora = self.reloj()
        listos = [e for e in self.pendientes if ahora >= e.listo_en]
        self.pendientes = [e for e in self.pendientes if ahora < e.listo_en]
        return [e for e in listos if cerrar_con_coordinador(self.coordinador, e, self.zona, self._decidir)]

    def clips(self, e: EventoPendiente) -> tuple[np.ndarray, list]:
        desde, hasta = e.t_evento - self.pre_s, e.listo_en
        fotos = self.video.recorte(desde, hasta) if self.video is not None else []
        return self.audio.recorte(desde, hasta), fotos
