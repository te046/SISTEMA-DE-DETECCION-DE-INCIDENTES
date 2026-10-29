"""Búferes circulares con marcas de tiempo reales de captura (lógica pura, sin hardware).

Cada muestra de audio y cada fotograma guardan el instante (epoch, segundos) en que se
capturaron. Así `detectado_en` es la hora del evento y no la de la inferencia (I1 honesto).
"""
import threading
from collections import deque

import numpy as np


class BufferAudio:
    """Guarda los últimos `segundos` de audio mono en bloques (índice_inicial, t0, muestras).

    Los índices son absolutos (cuentan todas las muestras recibidas desde el inicio), lo que
    permite pedir ventanas deslizantes sin perder ni repetir muestras.
    """

    def __init__(self, sr: int = 16000, segundos: float = 15.0):
        self.sr = sr
        self.max_muestras = int(sr * segundos)
        self._bloques: deque[tuple[int, float, np.ndarray]] = deque()
        self._total = 0
        self._guardadas = 0
        self._lock = threading.Lock()

    @property
    def total(self) -> int:
        return self._total

    def agregar(self, t0: float, muestras: np.ndarray) -> None:
        """`t0`: instante de la primera muestra del bloque."""
        m = np.asarray(muestras, dtype=np.float32).reshape(-1)
        if not m.size:
            return
        with self._lock:
            self._bloques.append((self._total, t0, m))
            self._total += m.size
            self._guardadas += m.size
            while self._bloques and self._guardadas - self._bloques[0][2].size >= self.max_muestras:
                self._guardadas -= self._bloques.popleft()[2].size

    def instante(self, indice: int) -> float | None:
        """Hora de captura de la muestra `indice`, o None si ya salió del búfer."""
        with self._lock:
            for ini, t0, m in self._bloques:
                if ini <= indice < ini + m.size:
                    return t0 + (indice - ini) / self.sr
        return None

    def ventana(self, indice: int, n: int) -> np.ndarray | None:
        """Devuelve las muestras [indice, indice+n) o None si aún no llegaron o ya se descartaron."""
        with self._lock:
            if indice + n > self._total or not self._bloques or indice < self._bloques[0][0]:
                return None
            partes = []
            for ini, _t0, m in self._bloques:
                a, b = max(indice, ini), min(indice + n, ini + m.size)
                if a < b:
                    partes.append(m[a - ini:b - ini])
            return np.concatenate(partes)

    def recorte(self, desde: float, hasta: float) -> np.ndarray:
        """Audio capturado entre dos instantes (para el clip de evidencia)."""
        with self._lock:
            partes = []
            for _ini, t0, m in self._bloques:
                t1 = t0 + m.size / self.sr
                if t1 <= desde or t0 >= hasta:
                    continue
                a = max(0, int(round((desde - t0) * self.sr)))
                b = min(m.size, int(round((hasta - t0) * self.sr)))
                partes.append(m[a:b])
            return np.concatenate(partes) if partes else np.zeros(0, np.float32)


class BufferVideo:
    """Últimos fotogramas muestreados, cada uno con su hora de captura."""

    def __init__(self, segundos: float = 15.0, fps: float = 10.0):
        self._fotos: deque[tuple[float, np.ndarray]] = deque(maxlen=max(1, int(segundos * fps)))
        self._lock = threading.Lock()

    def agregar(self, t: float, foto: np.ndarray) -> None:
        with self._lock:
            self._fotos.append((t, foto))

    def ultimo(self) -> tuple[float, np.ndarray] | None:
        with self._lock:
            return self._fotos[-1] if self._fotos else None

    def recorte(self, desde: float, hasta: float) -> list[tuple[float, np.ndarray]]:
        with self._lock:
            return [(t, f) for t, f in self._fotos if desde <= t <= hasta]
