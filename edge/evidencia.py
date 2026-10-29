"""Escribe los clips de evidencia: audio WAV (16 bits) y video WebM (VP8).

WebM/VP8 se eligió porque lo reproducen Chrome, Edge y WebView2 sin complementos, y la
compilación de OpenCV para Windows lo codifica sin la librería OpenH264 (H.264 no está).
"""
import io
import wave
from pathlib import Path

import numpy as np


def wav_bytes(muestras: np.ndarray, sr: int = 16000) -> bytes:
    pcm = (np.clip(np.asarray(muestras, dtype=np.float32), -1.0, 1.0) * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def escribir_webm(fotos: list[tuple[float, np.ndarray]], ruta: Path) -> bool:
    """Escribe los fotogramas con la cadencia real a la que se capturaron. Devuelve False si no hay video."""
    import cv2
    if len(fotos) < 2:
        return False
    duracion = fotos[-1][0] - fotos[0][0]
    fps = max(1.0, min(30.0, (len(fotos) - 1) / duracion)) if duracion > 0 else 10.0
    alto, ancho = fotos[0][1].shape[:2]
    w = cv2.VideoWriter(str(ruta), cv2.VideoWriter_fourcc(*"VP80"), fps, (ancho, alto))
    if not w.isOpened():
        return False
    try:
        for _t, f in fotos:
            w.write(f if f.shape[:2] == (alto, ancho) else cv2.resize(f, (ancho, alto)))
    finally:
        w.release()
    return ruta.exists() and ruta.stat().st_size > 0
