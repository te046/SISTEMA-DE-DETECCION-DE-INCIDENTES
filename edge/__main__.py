"""Arranca el módulo edge (captura y detección) en esta laptop.

    python -m edge                          → modo panel: conecta lo que se elija en «Buscar dispositivos»
    python -m edge --listar                 → muestra micrófonos y cámaras detectados y termina
    python -m edge --microfono 1 --camara ninguna --diagnostico
                                            → modo manual (pruebas y calibración): fuentes por índice

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
SINCRONIZAR_S = 2.0
LATIDO_S = 5.0


def leer(archivo: str, por_defecto: str | None = None) -> str | None:
    f = DATA_DIR / archivo
    return f.read_text(encoding="utf-8").strip() if f.exists() else por_defecto


def argumentos():
    ap = argparse.ArgumentParser(prog="python -m edge", description="Captura y detección (módulo edge).")
    ap.add_argument("--listar", action="store_true", help="lista micrófonos y cámaras y termina")
    ap.add_argument("--api", default=os.environ.get("VIGILANCIA_API") or leer(".api_url", "http://127.0.0.1:8000"))
    ap.add_argument("--microfono", type=int, default=None, help="modo manual: índice de --listar")
    ap.add_argument("--camara", default=None, help="modo manual: índice, URL RTSP/HTTP o 'ninguna'")
    ap.add_argument("--zona", default="Zona 1", help="modo manual: zona de las fuentes")
    ap.add_argument("--nombre-microfono", default="Micrófono de la laptop")
    ap.add_argument("--nombre-camara", default="Webcam de la laptop")
    ap.add_argument("--umbral", type=float, default=0.5, help="confianza mínima del modelo de audio (0–1)")
    ap.add_argument("--fps", type=float, default=10.0, help="fotogramas por segundo que se guardan")
    ap.add_argument("--diagnostico", action="store_true",
                    help="muestra en consola, cada segundo, el nivel del micrófono y las 3 clases con mayor puntaje (no guarda audio)")
    return ap.parse_args()


def preparar(a):
    """Clave de ingesta, cliente y fábrica del clasificador. Sale con un mensaje claro si falta algo."""
    from .clasificador_audio import ClasificadorYamnet
    from .cliente import ClienteApi
    clave = os.environ.get("INGEST_KEY") or leer(".ingest_key")
    if not clave:
        sys.exit(f"No encuentro la clave del módulo edge en {DATA_DIR / '.ingest_key'}. Arranque primero la API con: python run.py")

    def crear_clasificador():
        return ClasificadorYamnet(umbral=a.umbral)

    try:
        crear_clasificador()                             # verifica el modelo antes de empezar
    except FileNotFoundError as e:
        sys.exit(str(e))
    from .fusion_compartida import umbral_de_fusion
    if a.umbral < umbral_de_fusion():
        log.warning("--umbral %.2f solo cambia qué clases son candidatas. La fusión exige %.2f para alertar: "
                    "por debajo verá «Decisión … sin alerta» en el registro, pero no alertas.", a.umbral, umbral_de_fusion())
    return ClienteApi(a.api, clave), crear_clasificador


def observador_diagnostico(a, clasificador_de):
    if not a.diagnostico:
        return None
    from .diagnostico import Diagnostico
    log.info("Modo diagnóstico activo: solo se imprime texto en esta consola; no se guarda ni envía audio.")

    class Perezoso:                                     # el clasificador puede crearse después (modo panel)
        def __call__(self, ventana, t):
            if not hasattr(self, "d"):
                self.d = Diagnostico(clasificador_de(), imprimir=lambda s: print(s, flush=True))
            self.d(ventana, t)
    return Perezoso()


def entregar_listos(detectores, cliente):
    from .entrega import entregar
    for detector in detectores:
        detector.procesar()
        for evento in detector.listos():
            try:
                entregar(evento, detector, cliente, DATA_DIR / "mediciones_latencia.csv")
            except Exception as e:
                from .fusion_compartida import enmascarar_texto
                log.error("No se pudo enviar la alerta: %s", enmascarar_texto(e))


# ---------------------------------------------------------------- modo panel (por defecto)
def modo_panel(a):
    from .buffers import BufferAudio, BufferVideo
    from .captura import CapturaAudio, CapturaVideo
    from .descubrir import inventario
    from .fusion_compartida import enmascarar_texto
    from .gestor import Gestor

    cliente, crear_clasificador = preparar(a)

    def abrir_audio(indice):
        return CapturaAudio(BufferAudio(segundos=15), indice)

    def abrir_video(fuente):
        return CapturaVideo(BufferVideo(segundos=15, fps=a.fps), fuente, fps=a.fps)

    g = Gestor(cliente, abrir_audio, abrir_video, inventario, crear_clasificador=crear_clasificador)
    g.observador = observador_diagnostico(a, lambda: g.clasificador)
    log.info("Modo panel: esperando las fuentes que se conecten en «Buscar dispositivos». API: %s. Ctrl+C para detener.", a.api)
    proxima_sync = proximo_latido = 0.0
    try:
        while True:
            ahora = time.time()
            if ahora >= proxima_sync:
                try:
                    g.sincronizar()
                except Exception as e:
                    log.warning("No se pudo sincronizar con la API (%s). Reintento en %.0f s.", enmascarar_texto(e), SINCRONIZAR_S)
                proxima_sync = ahora + SINCRONIZAR_S
            if ahora >= proximo_latido:
                g.latidos()
                proximo_latido = ahora + LATIDO_S
            entregar_listos(g.detectores(), cliente)
            time.sleep(0.05)
    except KeyboardInterrupt:
        log.info("Deteniendo…")
    finally:
        g.cerrar_todo()


# ---------------------------------------------------------------- modo manual (pruebas y calibración)
def modo_manual(a):
    from .buffers import BufferAudio, BufferVideo
    from .captura import CapturaAudio, CapturaVideo
    from .detector import Detector

    cliente, crear_clasificador = preparar(a)
    clasificador = crear_clasificador()
    sin_video = a.camara is None or a.camara.lower() == "ninguna"
    try:
        id_audio = cliente.registrar(a.nombre_microfono, "audio", a.zona)
        id_video = None if sin_video else cliente.registrar(a.nombre_camara, "camara", a.zona)
    except Exception as e:
        sys.exit(f"No pude conectarme con la API en {a.api} ({e}). Revise que python run.py esté corriendo.")

    b_audio = BufferAudio(segundos=15)
    cap_audio = CapturaAudio(b_audio, a.microfono)
    b_video, cap_video = None, None
    if not sin_video:
        b_video = BufferVideo(segundos=15, fps=a.fps)
        cap_video = CapturaVideo(b_video, int(a.camara) if a.camara.isdigit() else a.camara, fps=a.fps)
    detector = Detector(clasificador, b_audio, b_video, a.zona, a.nombre_microfono, a.nombre_camara if cap_video else None,
                        observador=observador_diagnostico(a, lambda: clasificador))
    detener = threading.Event()

    def latidos():                                      # RF-01/RNF-02: estado real de cada fuente cada 5 s
        while not detener.is_set():
            for disp_id, cap in ((id_audio, cap_audio), (id_video, cap_video)):
                if disp_id is not None and cap is not None:
                    try:
                        cliente.latido(disp_id, cap.vivo)
                    except Exception as e:
                        log.warning("No se pudo enviar el latido: %s", e)
            detener.wait(LATIDO_S)

    cap_audio.iniciar()
    if cap_video:
        cap_video.iniciar()
    threading.Thread(target=latidos, name="latidos", daemon=True).start()
    log.info("Escuchando en %s. API: %s. Ctrl+C para detener.", a.zona, a.api)
    ultimo_informe = time.time()
    try:
        while True:
            entregar_listos([detector], cliente)
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


def main():
    a = argumentos()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)     # sus líneas incluirían rutas de la API en cada latido
    if a.listar:
        from .descubrir import inventario
        print(json.dumps(inventario(), ensure_ascii=False, indent=2))
        return
    if a.microfono is not None or a.camara is not None:
        modo_manual(a)
    else:
        modo_panel(a)


if __name__ == "__main__":
    main()
