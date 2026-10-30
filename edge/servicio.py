"""Servicio edge en «modo panel» que se puede detener: lo usan `python -m edge` y la aplicación de escritorio.

Sincroniza con la API cada 2 s (fuentes conectadas, búsquedas), envía latidos cada 5 s y entrega las alertas.
`detener()` cierra capturas y modelos de forma ordenada y espera al hilo.
"""
import logging
import threading
import time
from pathlib import Path

from .fusion_compartida import enmascarar_texto

log = logging.getLogger("edge")
SINCRONIZAR_S = 2.0
LATIDO_S = 5.0


def entregar_listos(detectores, cliente, registro_csv: Path | None, sesion: str = "prueba"):
    from .entrega import entregar
    for detector in detectores:
        detector.procesar()
        for evento in detector.listos():
            try:
                entregar(evento, detector, cliente, registro_csv, sesion)
            except Exception as e:
                log.error("No se pudo enviar la alerta: %s", enmascarar_texto(e))


class ServicioEdge:
    def __init__(self, cliente, crear_clasificador, crear_clasificador_video=None, registro_csv: Path | None = None,
                 sesion: str = "prueba", fps: float = 10.0, imprimir_diagnostico=None):
        from .buffers import BufferAudio, BufferVideo
        from .captura import CapturaAudio, CapturaVideo
        from .descubrir import inventario
        from .gestor import Gestor

        self.cliente, self.registro_csv, self.sesion = cliente, registro_csv, sesion
        self.gestor = Gestor(cliente, lambda i: CapturaAudio(BufferAudio(segundos=15), i),
                             lambda f: CapturaVideo(BufferVideo(segundos=15, fps=fps), f, fps=fps), inventario,
                             crear_clasificador=crear_clasificador, crear_clasificador_video=crear_clasificador_video)
        if imprimir_diagnostico:
            from .diagnostico import Diagnostico
            g = self.gestor

            class Perezoso:                              # el clasificador se crea al conectar el primer micrófono
                def __call__(self, ventana, t):
                    if not hasattr(self, "d"):
                        self.d = Diagnostico(g.clasificador, imprimir=imprimir_diagnostico)
                    self.d(ventana, t)
            self.gestor.observador = Perezoso()
        self._detener = threading.Event()
        self._hilo: threading.Thread | None = None
        self.sincronizaciones = 0                         # para la prueba de humo: el bucle realmente habla con la API

    def bucle(self) -> None:
        proxima_sync = proximo_latido = 0.0
        try:
            while not self._detener.is_set():
                ahora = time.time()
                if ahora >= proxima_sync:
                    try:
                        self.gestor.sincronizar()
                        self.sincronizaciones += 1
                    except Exception as e:
                        log.warning("No se pudo sincronizar con la API (%s). Reintento en %.0f s.", enmascarar_texto(e), SINCRONIZAR_S)
                    proxima_sync = ahora + SINCRONIZAR_S
                if ahora >= proximo_latido:
                    self.gestor.latidos()
                    proximo_latido = ahora + LATIDO_S
                entregar_listos(self.gestor.detectores(), self.cliente, self.registro_csv, self.sesion)
                self._detener.wait(0.05)
        finally:
            self.gestor.cerrar_todo()

    def iniciar(self) -> None:
        self._hilo = threading.Thread(target=self.bucle, name="edge", daemon=True)
        self._hilo.start()

    def detener(self, espera_s: float = 10.0) -> bool:
        """Cierra capturas y modelos. Devuelve True si el hilo terminó a tiempo."""
        self._detener.set()
        if self._hilo is not None:
            self._hilo.join(espera_s)
            return not self._hilo.is_alive()
        return True
