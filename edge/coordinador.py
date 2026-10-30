"""Coordina audio y video de una misma zona para que un incidente genere UNA alerta.

- Guarda las detecciones recientes de ambos modelos (solo clase, confianza, zona y hora; nada de audio ni imagen).
- Al cerrar un evento, la fusión se hace con TODO lo detectado en la zona dentro de la ventana de fusión:
  así un grito con video simultáneo sube a prioridad alta aunque el video haya llegado después.
- El primer evento que «reclama» un instante de la zona emite la alerta; los demás de esa ventana se descartan.
"""
import threading
from collections import deque

from .fusion_compartida import Deteccion

VENTANA_FUSION_S = 3.0       # la misma de backend/app/fusion.py (VENTANA_SEGUNDOS)


class Coordinador:
    def __init__(self, ventana_s: float = VENTANA_FUSION_S, memoria: int = 500):
        self.ventana_s = ventana_s
        self._recientes: deque[Deteccion] = deque(maxlen=memoria)
        self._emitidas: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def registrar(self, d: Deteccion) -> None:
        with self._lock:
            self._recientes.append(d)

    def en_ventana(self, zona: str, t: float) -> list[Deteccion]:
        with self._lock:
            return [d for d in self._recientes if d.zona == zona and abs(d.instante - t) <= self.ventana_s]

    def reclamar(self, zona: str, t: float) -> bool:
        """True si nadie emitió una alerta de esta zona dentro de la ventana; en ese caso la reserva."""
        with self._lock:
            previas = self._emitidas.setdefault(zona, [])
            if any(abs(t - x) <= self.ventana_s for x in previas):
                return False
            previas.append(t)
            del previas[:-50]
            return True
