"""Exporta a ONNX el modelo de video de línea base (VideoMAE afinado con RWF-2000). Se ejecuta UNA vez.

    .venv-export\\Scripts\\python scripts\\exportar_modelo_video.py

Usa un entorno aparte (.venv-export, con PyTorch CPU y transformers) que no forma parte de la app.
- Descarga sin cuenta ni credenciales una revisión FIJA del repositorio y verifica el SHA-256.
- Carga solo `model.safetensors` (no puede ejecutar código al cargarse). Nunca abre pytorch_model.bin (pickle).
- Exporta a ONNX, compara las salidas de PyTorch y ONNX, y escribe los hashes en edge/modelos/PROCEDENCIA_VIDEO.json.
"""
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

REPO = "lmazzon70/videomae-base-finetuned-kinetics-finetuned-rwf2000-epochs8-batch8-kb"
# PR #2 del repositorio, creada por SFconvertbot (bot oficial de Hugging Face): variante safetensors de pytorch_model.bin.
REVISION = "bb28180b42bfa4d8b3a2e1c7a77d741ca7f7d7b8"
ARCHIVOS = {
    "model.safetensors": "083a6e539404103b1712c6dbf8aeca320043598269ac3ee6e6cfe2ccc5562021",
    "config.json": None,
    "preprocessor_config.json": None,
}
DESTINO = Path(__file__).resolve().parents[1] / "edge" / "modelos" / "videomae_rwf2000"
ONNX = DESTINO / "videomae_rwf2000.onnx"


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for trozo in iter(lambda: f.read(1 << 20), b""):
            h.update(trozo)
    return h.hexdigest()


def descargar():
    DESTINO.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for nombre, esperado in ARCHIVOS.items():
        ruta = DESTINO / nombre
        if not (ruta.exists() and (esperado is None or sha256(ruta) == esperado)):
            url = f"https://huggingface.co/{REPO}/resolve/{REVISION}/{nombre}"
            print(f"Descargando {nombre}…")
            temporal = ruta.with_suffix(ruta.suffix + ".parcial")
            urllib.request.urlretrieve(url, temporal)
            temporal.replace(ruta)
        hashes[nombre] = sha256(ruta)
        if esperado and hashes[nombre] != esperado:
            ruta.unlink()
            sys.exit(f"{nombre}: el SHA-256 no coincide con el publicado. No se usó. Revise la conexión y vuelva a intentar.")
    return hashes


def main():
    import numpy as np
    import onnxruntime as ort
    import torch
    from safetensors.torch import load_file
    from transformers import VideoMAEConfig, VideoMAEForVideoClassification

    hashes = descargar()
    config = VideoMAEConfig.from_json_file(DESTINO / "config.json")
    modelo = VideoMAEForVideoClassification(config)
    faltan, sobran = modelo.load_state_dict(load_file(DESTINO / "model.safetensors"), strict=False)
    if faltan or sobran:
        sys.exit(f"Los pesos no coinciden con la arquitectura (faltan {len(faltan)}, sobran {len(sobran)}).")
    modelo.eval()

    entrada = torch.randn(1, config.num_frames, 3, config.image_size, config.image_size, generator=torch.Generator().manual_seed(0))
    with torch.no_grad():
        esperado = modelo(pixel_values=entrada).logits.numpy()
        torch.onnx.export(modelo, (entrada,), str(ONNX), input_names=["pixel_values"], output_names=["logits"],
                          dynamic_axes={"pixel_values": {0: "lote"}, "logits": {0: "lote"}}, opset_version=17, dynamo=False)
    obtenido = ort.InferenceSession(str(ONNX), providers=["CPUExecutionProvider"]).run(None, {"pixel_values": entrada.numpy()})[0]
    dif = float(np.abs(esperado - obtenido).max())
    if dif > 1e-3:
        sys.exit(f"ONNX y PyTorch no coinciden (diferencia máxima {dif:.2e}). No se usa el ONNX.")

    procedencia = {
        "repositorio": f"https://huggingface.co/{REPO}",
        "revision": REVISION,
        "nota_revision": "PR #2 (abierta, sin fusionar por el autor) creada por SFconvertbot: variante safetensors de pytorch_model.bin",
        "licencia": "CC BY-NC 4.0 (declarada en la ficha del modelo)",
        "base": "MCG-NJU/videomae-base-finetuned-kinetics",
        "etiquetas": config.id2label,
        "sha256": {**hashes, ONNX.name: sha256(ONNX)},
        "exportado_con": {"torch": torch.__version__, "opset": 17},
        "diferencia_max_onnx_vs_pytorch": dif,
    }
    (DESTINO.parent / "PROCEDENCIA_VIDEO.json").write_text(json.dumps(procedencia, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(procedencia, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
