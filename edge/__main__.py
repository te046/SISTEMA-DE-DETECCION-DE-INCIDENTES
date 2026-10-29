"""Arranca la captura y la detección de audio en esta laptop.

    python -m edge --listar                 → muestra micrófonos y cámaras disponibles
    python -m edge                          → micrófono y cámara predeterminados (índice 0)
    python -m edge --microfono 3 --camara 1 --zona "Zona 1"
    python -m edge --camara ninguna         → solo audio

Primero arranque la API con python run.py (deja su dirección en data/.api_url).
"""
import argparse
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("VIGILANCIA_DATA", ROOT / "data"))
log = logging.getLogger("edge")


def leer(archivo: str, por_defecto: str | None = None) -> str | None:
    f = DATA_DIR / archivo
    return f.read_text(encoding="utf-8").strip() if f.exists() else por_defecto


def argumentos():
    ap = argparse.ArgumentParser(prog="python -m edge", description="Captura y detección (módulo edge).")
    ap.add_argument("--listar", action="store_true", help="lista micrófonos y cámaras y termina")
    ap.add_argument("--api", default=os.environ.get("VIGILANCIA_API") or leer(".api_url", "http://127.0.0.1:8000"))
    ap.add_argument("--microfono", type=int, default=None, help="índice de --listar (por defecto: el de Windows)")
    ap.add_argument("--camara", default="0", help="índice, URL RTSP/HTTP o 'ninguna'")
    ap.add_argument("--zona", default="Zona 1")
    ap.add_argument("--nombre-microfono", default="Micrófono de la laptop")
    ap.add_argument("--nombre-camara", default="Webcam de la laptop")
    ap.add_argument("--umbral", type=float, default=0.5, help="confianza mínima del modelo de audio (0–1)")
    ap.add_argument("--fps", type=float, default=10.0, help="fotogramas por segundo que se guardan")
    ap.add_argument("--diagnostico", action="store_true",
                    help="muestra en consola, cada segundo, el nivel del micrófono y las 3 clases con mayor puntaje (no guarda audio)")
    return ap.parse_args()


def main():
    a = argumentos()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    from .captura import CapturaAudio, CapturaVideo, listar_fuentes
    if a.listar:
        print(json.dumps(listar_fuentes(), ensure_ascii=False, indent=2))
        return

    from .buffers import BufferAudio, BufferVideo
    from .clasificador_audio import ClasificadorYamnet
    from .cliente import ClienteApi
    from .detector import Detector
    from .entrega import entregar

    clave = os.environ.get("INGEST_KEY") or leer(".ingest_key")
    if not clave:
        sys.exit(f"No encuentro la clave del módulo edge en {DATA_DIR / '.ingest_key'}. Arranque primero la API con: python run.py")
    try:
        clasificador = ClasificadorYamnet(umbral=a.umbral)
    except FileNotFoundError as e:
        sys.exit(str(e))
    cliente = ClienteApi(a.api, clave)
    try:
        id_audio = cliente.registrar(a.nombre_microfono, "audio", a.zona)
        sin_video = a.camara.lower() == "ninguna"
        id_video = None if sin_video else cliente.registrar(a.nombre_camara, "camara", a.zona)
    except Exception as e:
        sys.exit(f"No pude conectarme con la API en {a.api} ({e}). Revise que python run.py esté corriendo.")

    b_audio = BufferAudio(segundos=15)
    cap_audio = CapturaAudio(b_audio, a.microfono)
    b_video, cap_video = None, None
    if not sin_video:
        b_video = BufferVideo(segundos=15, fps=a.fps)
        cap_video = CapturaVideo(b_video, int(a.camara) if a.camara.isdigit() else a.camara, fps=a.fps)
    detector = Detector(clasificador, b_audio, b_video, a.zona, a.nombre_microfono, a.nombre_camara if cap_video else None)
    if a.diagnostico:
        from .diagnostico import Diagnostico
        detector.observador = Diagnostico(clasificador, imprimir=lambda s: print(s, flush=True))
        log.info("Modo diagnóstico activo: solo se imprime texto en esta consola; no se guarda ni envía audio.")

    detener = threading.Event()

    def latidos():                                      # RF-01/RNF-02: estado real de cada fuente cada 5 s
        while not detener.is_set():
            for disp_id, cap in ((id_audio, cap_audio), (id_video, cap_video)):
                if disp_id is not None and cap is not None:
                    try:
                        cliente.latido(disp_id, cap.vivo)
                    except Exception as e:
                        log.warning("No se pudo enviar el latido: %s", e)
            detener.wait(5)

    cap_audio.iniciar()
    if cap_video:
        cap_video.iniciar()
    threading.Thread(target=latidos, name="latidos", daemon=True).start()
    log.info("Escuchando en %s. API: %s. Ctrl+C para detener.", a.zona, a.api)
    ultimo_informe = time.time()
    try:
        while True:
            detector.procesar()
            for evento in detector.listos():
                try:
                    entregar(evento, detector, cliente, DATA_DIR / "mediciones_latencia.csv")
                except Exception as e:
                    log.error("No se pudo enviar la alerta: %s", e)
            if time.time() - ultimo_informe > 60:
                log.info("Captura: audio %s · video %s", cap_audio.metricas, cap_video.metricas if cap_video else "sin cámara")
                ultimo_informe = time.time()
            time.sleep(0.05)
    except KeyboardInterrupt:
        log.info("Deteniendo…")
    finally:
        detener.set()
        cap_audio.detener()
        if cap_video:
            cap_video.detener()
        for disp_id in (id_audio, id_video):
            if disp_id is not None:
                try:
                    cliente.latido(disp_id, False)
                except Exception:
                    pass


if __name__ == "__main__":
    main()
