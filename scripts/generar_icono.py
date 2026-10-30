"""Genera escritorio/recursos/udh.ico (16–256 px) a partir del escudo de frontend/logo-udh.png.

    .venv\\Scripts\\python scripts\\generar_icono.py

El logo (1290×645, sin transparencia) tiene el escudo a la izquierda y el texto «UDH» a la derecha. Se recorta el
escudo (hasta la primera franja vertical en blanco), y el fondo blanco CONECTADO AL BORDE se vuelve transparente
(relleno desde las esquinas), para no borrar los blancos internos del escudo.
"""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
ORIGEN = RAIZ / "frontend" / "logo-udh.png"
DESTINO = RAIZ / "escritorio" / "recursos"
TAMANOS = [16, 24, 32, 48, 64, 128, 256]


def recortar_escudo(bgr: np.ndarray) -> np.ndarray:
    gris = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    tinta = gris < 235
    cols = np.where(tinta.any(axis=0))[0]
    x0 = cols.min()
    x1 = next((x for x in range(x0, cols.max()) if not tinta[:, x].any()), cols.max())   # fin del escudo
    filas = np.where(tinta[:, x0:x1].any(axis=1))[0]
    return bgr[filas.min():filas.max() + 1, x0:x1]


def fondo_transparente(bgr: np.ndarray) -> np.ndarray:
    h, w = bgr.shape[:2]
    lienzo = cv2.copyMakeBorder(bgr, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    mascara = np.zeros((h + 6, w + 6), np.uint8)
    cv2.floodFill(lienzo, mascara, (0, 0), (255, 255, 255), (12, 12, 12), (12, 12, 12), cv2.FLOODFILL_MASK_ONLY | 4 | (255 << 8))
    fondo = mascara[3:-3, 3:-3] == 255
    rgba = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA)
    rgba[fondo, 3] = 0
    return rgba


def cuadrado(rgba: np.ndarray, margen: float = 0.04) -> Image.Image:
    h, w = rgba.shape[:2]
    lado = int(max(h, w) * (1 + 2 * margen))
    lienzo = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    lienzo.paste(Image.fromarray(rgba), ((lado - w) // 2, (lado - h) // 2))
    return lienzo


def main():
    escudo = recortar_escudo(cv2.imread(str(ORIGEN)))
    img = cuadrado(fondo_transparente(escudo))
    DESTINO.mkdir(parents=True, exist_ok=True)
    img.resize((256, 256), Image.LANCZOS).save(DESTINO / "udh-256.png")
    img.save(DESTINO / "udh.ico", sizes=[(t, t) for t in TAMANOS])
    print(f"Escudo recortado: {escudo.shape[1]}x{escudo.shape[0]} px -> udh.ico con {TAMANOS} px")


if __name__ == "__main__":
    main()
