"""Arma la evidencia de un evento, la sube, crea la alerta y registra los tiempos medidos.

Los tiempos se guardan en data/mediciones_latencia.csv para ubicar el cuello de botella de I1:
  espera_post_s  = lo que se espera para grabar el post-evento del clip
  inferencia_s   = fin del modelo − inicio de la ventana
  subida_s       = escribir y subir los clips
  total_s        = generado_en (servidor) − detectado_en (captura)  → es el I1 de esa alerta
"""
import csv
import logging
import tempfile
import time
from datetime import datetime
from pathlib import Path

from .detector import Detector, EventoPendiente
from .evidencia import escribir_webm, wav_bytes

log = logging.getLogger("edge.entrega")
COLUMNAS = ["codigo", "tipo", "detectado_en", "generado_en", "inferencia_s", "espera_post_s", "subida_s", "total_s", "con_video"]


def entregar(e: EventoPendiente, detector: Detector, cliente, registro_csv: Path | None = None) -> dict:
    t_inicio_entrega = time.time()
    audio, fotos = detector.clips(e)
    sr = detector.audio.sr if detector.audio is not None else 16000     # un evento de video puede no tener micrófono
    url_audio = cliente.subir("clip.wav", wav_bytes(audio, sr), "audio/wav") if audio.size else None
    url_video = None
    if fotos:
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "clip.webm"
            if escribir_webm(fotos, ruta):
                url_video = cliente.subir("clip.webm", ruta.read_bytes(), "video/webm")
    subida = time.time() - t_inicio_entrega
    creada = cliente.alerta(e.alerta, url_audio, url_video)
    total = (datetime.fromisoformat(creada["generado_en"]) - datetime.fromisoformat(creada["detectado_en"])).total_seconds()
    fila = {
        "codigo": creada.get("codigo"), "tipo": creada.get("tipo"),
        "detectado_en": creada["detectado_en"], "generado_en": creada["generado_en"],
        "inferencia_s": round(e.t_inferencia - e.t_evento, 3),
        "espera_post_s": round(max(0.0, t_inicio_entrega - e.t_inferencia), 3),
        "subida_s": round(subida, 3), "total_s": round(total, 3), "con_video": bool(url_video),
    }
    log.info("Alerta %s enviada: I1 = %.2f s (inferencia %.2f · espera post-evento %.2f · subida %.2f)",
             fila["codigo"], total, fila["inferencia_s"], fila["espera_post_s"], fila["subida_s"])
    if total > 5:
        log.warning("I1 superó 5 s (RNF-01). Revise el tramo más largo en la línea anterior.")
    if registro_csv:
        nuevo = not registro_csv.exists()
        with open(registro_csv, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNAS)
            if nuevo:
                w.writeheader()
            w.writerow(fila)
    return creada
