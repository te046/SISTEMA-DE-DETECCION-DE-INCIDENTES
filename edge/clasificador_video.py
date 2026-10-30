"""Clasificador de video de LÍNEA BASE: «posible agresión física» con VideoMAE afinado en RWF-2000.

Modelo y procedencia: edge/modelos/PROCEDENCIA_VIDEO.json (licencia CC BY-NC 4.0, revisión fija, SHA-256).
Se genera con scripts/exportar_modelo_video.py. Es una línea base: NO está calibrado con video del pabellón
y no hay métricas medidas en este proyecto; la exactitud que publica su autor (0,73) no es un resultado nuestro.
Latencia medida en la laptop de desarrollo (CPU, 30/10/2026): ~0,78 s por clip de 16 fotogramas.
"""
import json
from pathlib import Path

import numpy as np

MODELO = Path(__file__).resolve().parent / "modelos" / "videomae_rwf2000" / "videomae_rwf2000.onnx"
PROCEDENCIA = Path(__file__).resolve().parent / "modelos" / "PROCEDENCIA_VIDEO.json"
CLASE = "posible agresión"
FOTOGRAMAS, LADO = 16, 224
MEDIA = np.array([0.485, 0.456, 0.406], np.float32)          # preprocessor_config.json del modelo
DESV = np.array([0.229, 0.224, 0.225], np.float32)


def muestrear(fotos: list, n: int = FOTOGRAMAS) -> list:
    """n fotogramas repartidos uniformemente en la ventana (repite si hay menos)."""
    if not fotos:
        return []
    idx = np.linspace(0, len(fotos) - 1, n).round().astype(int)
    return [fotos[i] for i in idx]


def preprocesar(fotos_bgr: list) -> np.ndarray:
    """[n] imágenes BGR → tensor [1, n, 3, 224, 224]: lado corto a 224, recorte central, normalización ImageNet."""
    import cv2
    salida = []
    for f in fotos_bgr:
        h, w = f.shape[:2]
        e = LADO / min(h, w)
        r = cv2.resize(f, (max(LADO, round(w * e)), max(LADO, round(h * e))), interpolation=cv2.INTER_LINEAR)
        y, x = (r.shape[0] - LADO) // 2, (r.shape[1] - LADO) // 2
        rgb = cv2.cvtColor(r[y:y + LADO, x:x + LADO], cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        salida.append(((rgb - MEDIA) / DESV).transpose(2, 0, 1))
    return np.stack(salida)[None].astype(np.float32)


def probabilidad_pelea(logits: np.ndarray, indice_pelea: int) -> float:
    z = np.asarray(logits, dtype=np.float64).reshape(-1)
    p = np.exp(z - z.max())
    return float(p[indice_pelea] / p.sum())


class ClasificadorVideo:
    def __init__(self, umbral: float = 0.5, ruta: Path = MODELO):
        import onnxruntime as ort
        if not ruta.exists():
            raise FileNotFoundError("No está el modelo de video. Genérelo una vez con: "
                                    ".venv-export\\Scripts\\python scripts\\exportar_modelo_video.py")
        etiquetas = json.loads(PROCEDENCIA.read_text(encoding="utf-8"))["etiquetas"]
        self.indice_pelea = int(next(k for k, v in etiquetas.items() if v == "Fight"))
        self.sesion = ort.InferenceSession(str(ruta), providers=["CPUExecutionProvider"])
        self.umbral = umbral

    def probabilidad(self, fotos_bgr: list) -> float:
        logits = self.sesion.run(None, {"pixel_values": preprocesar(muestrear(fotos_bgr))})[0]
        return probabilidad_pelea(logits, self.indice_pelea)
