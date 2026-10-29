"""Clasificador de eventos de audio con YAMNet (preentrenado en AudioSet, 521 clases).

Modelo: conversión ONNX sin reentrenar de google/yamnet v1 (Apache 2.0),
https://huggingface.co/audiomagic/yamnet-onnx  ·  SHA-256 de yamnet.onnx:
d3835ffbbd4a1bb3e777f0ca217b5007907f5171dd5d17c4236b95b2af8f908e

El mapeo de clases de AudioSet a las clases del diseño es una decisión de diseño que se debe
calibrar con grabaciones del pabellón. Ninguna métrica (precisión, recall, F1) está medida aún.
"""
import csv
from pathlib import Path

import numpy as np

MODELOS_DIR = Path(__file__).resolve().parent / "modelos"
SHA256_YAMNET = "d3835ffbbd4a1bb3e777f0ca217b5007907f5171dd5d17c4236b95b2af8f908e"

# Clase del diseño -> nombres exactos de AudioSet (yamnet_class_map.csv) que la representan.
CLASES_DISENO = {
    "rotura de vidrio": ["Shatter", "Glass"],
    "grito": ["Screaming"],
    "choque": ["Smash, crash", "Breaking", "Bang", "Slam"],
    "disparo": ["Gunshot, gunfire", "Machine gun"],
    "voces elevadas": ["Shout", "Yell", "Children shouting"],     # discusión verbal: se detecta por audio
}


def leer_nombres(ruta: Path = MODELOS_DIR / "yamnet_class_map.csv") -> list[str]:
    with open(ruta, encoding="utf-8", newline="") as f:
        return [fila["display_name"] for fila in csv.DictReader(f)]


def indices_por_clase(nombres: list[str]) -> dict[str, list[int]]:
    pos = {n: i for i, n in enumerate(nombres)}
    faltan = [n for ns in CLASES_DISENO.values() for n in ns if n not in pos]
    if faltan:
        raise ValueError(f"El mapa de clases no tiene: {faltan}. Revise que el CSV sea el de YAMNet.")
    return {clase: [pos[n] for n in ns] for clase, ns in CLASES_DISENO.items()}


def mapear_puntajes(puntajes: np.ndarray, indices: dict[str, list[int]], umbral: float) -> list[tuple[str, float, int]]:
    """De los puntajes de YAMNet [cuadros, 521] a [(clase_diseño, confianza, clase_audioset)].

    YAMNet es multietiqueta: cada clase tiene su propio puntaje 0–1. Se toma el máximo entre
    los cuadros de la ventana y entre las clases de AudioSet que forman cada clase del diseño.
    """
    p = np.asarray(puntajes, dtype=np.float32)
    if p.ndim == 1:
        p = p[None, :]
    maximos = p.max(axis=0)
    salida = []
    for clase, idx in indices.items():
        j = max(idx, key=lambda i: maximos[i])
        if maximos[j] >= umbral:
            salida.append((clase, float(maximos[j]), j))
    return sorted(salida, key=lambda x: -x[1])


class ClasificadorYamnet:
    def __init__(self, ruta_modelo: Path = MODELOS_DIR / "yamnet.onnx", umbral: float = 0.5):
        import onnxruntime as ort                       # importación diferida: las pruebas puras no la necesitan
        if not ruta_modelo.exists():
            raise FileNotFoundError(f"No está el modelo {ruta_modelo}. Ejecute: python -m edge.descargar_modelos")
        self.sesion = ort.InferenceSession(str(ruta_modelo), providers=["CPUExecutionProvider"])
        self.nombres = leer_nombres()
        self.indices = indices_por_clase(self.nombres)
        self.umbral = umbral
        self.ultimos_puntajes: np.ndarray | None = None      # los usa --diagnostico sin repetir la inferencia

    def puntajes(self, ventana: np.ndarray) -> np.ndarray:
        """`ventana`: audio mono float32 a 16 kHz en [-1, 1]."""
        return self.sesion.run(["output_0"], {"waveform": np.asarray(ventana, dtype=np.float32)})[0]

    def clasificar(self, ventana: np.ndarray) -> list[tuple[str, float, str]]:
        self.ultimos_puntajes = self.puntajes(ventana)
        return [(c, conf, self.nombres[j]) for c, conf, j in mapear_puntajes(self.ultimos_puntajes, self.indices, self.umbral)]
