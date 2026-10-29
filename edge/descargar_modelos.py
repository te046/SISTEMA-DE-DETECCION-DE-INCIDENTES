"""Descarga YAMNet (ONNX, 16 MB) y verifica su SHA-256.  Uso: python -m edge.descargar_modelos"""
import hashlib
import sys
import urllib.request

from .clasificador_audio import MODELOS_DIR, SHA256_YAMNET

URL = "https://huggingface.co/audiomagic/yamnet-onnx/resolve/main/yamnet.onnx"


def sha256(ruta) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for trozo in iter(lambda: f.read(1 << 20), b""):
            h.update(trozo)
    return h.hexdigest()


def main():
    destino = MODELOS_DIR / "yamnet.onnx"
    if destino.exists() and sha256(destino) == SHA256_YAMNET:
        print("YAMNet ya está descargado y verificado.")
        return
    temporal = destino.with_suffix(".parcial")
    print("Descargando YAMNet (16 MB)…")
    urllib.request.urlretrieve(URL, temporal)
    if sha256(temporal) != SHA256_YAMNET:
        temporal.unlink(missing_ok=True)
        sys.exit("La descarga no coincide con el SHA-256 esperado. No se instaló. Revise su conexión y vuelva a intentar.")
    temporal.replace(destino)
    print("Listo: YAMNet verificado.")


if __name__ == "__main__":
    main()
