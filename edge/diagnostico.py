"""Modo diagnóstico (python -m edge --diagnostico): muestra en consola, una vez por segundo, el nivel
del micrófono y las 3 clases de AudioSet con mayor puntaje. Sirve para calibrar el umbral y el mapeo
con datos reales. No guarda ni envía audio: solo imprime texto.
"""
import time

import numpy as np


def nivel_dbfs(ventana: np.ndarray) -> float:
    """Nivel RMS en dBFS (0 = máximo digital; silencio ≈ −90)."""
    rms = float(np.sqrt(np.mean(np.square(np.asarray(ventana, dtype=np.float64))))) if len(ventana) else 0.0
    return max(-90.0, 20 * np.log10(rms)) if rms > 0 else -90.0


def top_clases(puntajes: np.ndarray, nombres: list[str], k: int = 3) -> list[tuple[str, float]]:
    """Las k clases con mayor puntaje (máximo entre los cuadros de la ventana)."""
    p = np.asarray(puntajes, dtype=np.float32)
    maximos = p.max(axis=0) if p.ndim == 2 else p
    orden = np.argsort(maximos)[::-1][:k]
    return [(nombres[i], float(maximos[i])) for i in orden]


def linea(t: float, ventana: np.ndarray, puntajes: np.ndarray, nombres: list[str]) -> str:
    hora = time.strftime("%H:%M:%S", time.localtime(t))
    clases = " · ".join(f"{n} {s:.2f}" for n, s in top_clases(puntajes, nombres))
    return f"[diag {hora}] nivel {nivel_dbfs(ventana):6.1f} dBFS | {clases}"


class Diagnostico:
    """Recibe cada ventana clasificada e imprime como máximo una línea por segundo."""

    def __init__(self, clasificador, imprimir=print, cada_s: float = 1.0):
        self.clasificador, self.imprimir, self.cada_s = clasificador, imprimir, cada_s
        self._ultimo = -1e18

    def __call__(self, ventana: np.ndarray, t: float) -> None:
        puntajes = getattr(self.clasificador, "ultimos_puntajes", None)
        if puntajes is None or t - self._ultimo < self.cada_s:
            return
        self._ultimo = t
        self.imprimir(linea(t, ventana, puntajes, self.clasificador.nombres))
