"""Mantiene el edge sincronizado con el panel, sin reiniciarlo a mano.

Cada 2 s pregunta a la API qué fuentes deben estar conectadas y si se pidió una búsqueda:
abre las nuevas, cierra las que se desconectaron y reabre las que cambiaron (por ejemplo, de zona).
Informa al panel si cada fuente entrega datos o qué error tiene (siempre enmascarado).
El hardware y la red se inyectan (`abrir_audio`, `abrir_video`, `inventario`) para probarlo sin ellos.
"""
import logging
import time
from dataclasses import dataclass, field

from .coordinador import Coordinador
from .descubrir import resolver_microfono
from .detector import Detector
from .detector_video import MonitorVideo
from .fusion_compartida import enmascarar_texto

log = logging.getLogger("edge.gestor")
MSG_MICRO_NO_ESTA = "No se encuentra este micrófono. Revise que esté conectado y pulse «Buscar»."
MSG_SIN_DATOS = {"audio": "El micrófono no entrega audio.", "camara": "La cámara no entrega imágenes."}


@dataclass
class Activa:
    fuente: dict
    captura: object                     # CapturaAudio | CapturaVideo (o un doble en las pruebas)
    dispositivo_id: int | None
    detector: Detector | MonitorVideo | None = None    # audio: Detector · cámara: MonitorVideo (si hay modelo)
    informado: tuple | None = None      # último (ok, error) enviado, para no repetirlo


@dataclass
class Gestor:
    cliente: object
    abrir_audio: object                 # (indice) -> captura con .buffer
    abrir_video: object                 # (indice | url) -> captura con .buffer
    inventario: object                  # (camaras: bool) -> {'microfonos': [...], 'camaras': [...]}
    clasificador: object = None         # se crea al conectar el primer micrófono
    crear_clasificador: object = None
    observador: object = None           # --diagnostico
    crear_clasificador_video: object = None             # None o sin modelo: la cámara solo graba evidencia
    clasificador_video: object = None
    coordinador: Coordinador = field(default_factory=Coordinador)
    _sin_modelo_video: bool = False
    activas: dict = field(default_factory=dict)
    fallidas: dict = field(default_factory=dict)        # id -> actualizado_en con el que falló (no reintentar en bucle)
    _inv: dict | None = None

    # ------------------------------------------------------------ sincronización
    def sincronizar(self) -> None:
        estado = self.cliente.estado()
        if estado.get("buscar"):
            self.buscar()
        deseadas = {f["id"]: f for f in estado.get("fuentes", [])}
        for fid in list(self.activas):
            f = deseadas.get(fid)
            if f is None or f["actualizado_en"] != self.activas[fid].fuente["actualizado_en"]:
                self.cerrar(fid, informar_desconexion=f is None)
        for fid, f in deseadas.items():
            if fid not in self.activas and self.fallidas.get(fid) != f["actualizado_en"]:
                self.abrir(f)
        self._enlazar_video()
        self.informar_estados()

    def buscar(self) -> None:
        log.info("Búsqueda pedida desde el panel.")
        self._inv = self.inventario(camaras=True)
        self.fallidas.clear()                           # tras buscar, se reintenta lo que había fallado
        for a in self.activas.values():                 # una cámara abierta por nosotros no responde al escaneo
            f = a.fuente
            if f["tipo"] == "camara" and f["clase"] == "local" and all(c["clave"] != f["clave"] for c in self._inv["camaras"]):
                self._inv["camaras"].append({"clave": f["clave"], "tipo": "camara", "nombre": f["nombre"],
                                             "bluetooth": False, "utilizable": True, "motivo": None})
        self.cliente.subir_inventario(self._inv)

    # ------------------------------------------------------------ abrir y cerrar
    def abrir(self, f: dict) -> None:
        try:
            if f["tipo"] == "audio":
                if self._inv is None:
                    self._inv = self.inventario(camaras=False)
                indice = resolver_microfono(f["clave"], self._inv)
                if indice is None:
                    self._inv = self.inventario(camaras=False)        # quizá se acaba de enchufar
                    indice = resolver_microfono(f["clave"], self._inv)
                if indice is None:
                    return self._fallo(f, MSG_MICRO_NO_ESTA)
                captura = self.abrir_audio(indice)
            elif f.get("red"):
                captura = self.abrir_video(self.cliente.direccion(f["id"]))     # la dirección no se registra en ningún lado
            else:
                captura = self.abrir_video(int(f["clave"].rsplit(":", 1)[-1]))
        except Exception as e:
            return self._fallo(f, enmascarar_texto(e))
        disp_id = None
        try:
            disp_id = self.cliente.registrar(f["nombre"], f["tipo"], f["zona"])
        except Exception as e:
            log.warning("No se pudo registrar %s para los latidos: %s", f["nombre"], enmascarar_texto(e))
        activa = Activa(f, captura, disp_id)
        if f["tipo"] == "audio":
            if self.clasificador is None:
                self.clasificador = self.crear_clasificador()
            activa.detector = Detector(self.clasificador, captura.buffer, None, f["zona"], f["nombre"],
                                       observador=self.observador, coordinador=self.coordinador)
        elif self._modelo_video() is not None:
            activa.detector = MonitorVideo(self.clasificador_video, captura.buffer, f["zona"], f["nombre"], self.coordinador)
            activa.detector.iniciar()
        captura.iniciar()
        self.activas[f["id"]] = activa
        self.fallidas.pop(f["id"], None)
        log.info("Conectada: %s (%s).", f["nombre"], f["zona"])

    def _fallo(self, f: dict, motivo: str) -> None:
        self.fallidas[f["id"]] = f["actualizado_en"]
        log.warning("No se pudo conectar %s: %s", f["nombre"], motivo)
        try:
            self.cliente.informar(f["id"], False, motivo)
        except Exception as e:
            log.warning("No se pudo informar el error al panel: %s", enmascarar_texto(e))

    def cerrar(self, fid: int, informar_desconexion: bool = True) -> None:
        a = self.activas.pop(fid)
        a.captura.detener()
        if isinstance(a.detector, MonitorVideo):
            a.detector.detener()
        if informar_desconexion and a.dispositivo_id is not None:
            try:
                self.cliente.latido(a.dispositivo_id, False)
            except Exception:
                pass
        log.info("Desconectada: %s.", a.fuente["nombre"])

    def cerrar_todo(self) -> None:
        for fid in list(self.activas):
            self.cerrar(fid)

    def _modelo_video(self):
        """Clasificador de video (línea base), creado una vez. Si falta el modelo, se avisa una sola vez."""
        if self.clasificador_video is None and self.crear_clasificador_video and not self._sin_modelo_video:
            try:
                self.clasificador_video = self.crear_clasificador_video()
            except FileNotFoundError as e:
                self._sin_modelo_video = True
                log.warning("Sin modelo de video: las cámaras solo graban evidencia. %s", e)
        return self.clasificador_video

    def _enlazar_video(self) -> None:
        """Evidencia cruzada por zona: el micrófono usa la cámara de su zona y la cámara usa el micrófono."""
        camaras = {a.fuente["zona"]: a for a in self.activas.values() if a.fuente["tipo"] == "camara"}
        micros = {a.fuente["zona"]: a for a in self.activas.values() if a.fuente["tipo"] == "audio"}
        for a in self.activas.values():
            if isinstance(a.detector, Detector):
                cam = camaras.get(a.fuente["zona"])
                a.detector.video = cam.captura.buffer if cam else None
                a.detector.nombre_video = cam.fuente["nombre"] if cam else None
            elif isinstance(a.detector, MonitorVideo):
                mic = micros.get(a.fuente["zona"])
                a.detector.audio = mic.captura.buffer if mic else None

    # ------------------------------------------------------------ estado, latidos y detección
    def informar_estados(self) -> None:
        for fid, a in self.activas.items():
            ok = bool(a.captura.vivo)
            motivo = None if ok else (getattr(a.captura, "ultimo_error", None) or MSG_SIN_DATOS[a.fuente["tipo"]])
            if (ok, motivo) != a.informado:
                try:
                    self.cliente.informar(fid, ok, motivo)
                    a.informado = (ok, motivo)
                except Exception as e:
                    log.warning("No se pudo informar el estado: %s", enmascarar_texto(e))

    def latidos(self) -> None:
        for a in self.activas.values():
            if a.dispositivo_id is not None:
                try:
                    self.cliente.latido(a.dispositivo_id, a.captura.vivo)
                except Exception as e:
                    log.warning("No se pudo enviar el latido: %s", enmascarar_texto(e))

    def detectores(self) -> list:
        return [a.detector for a in self.activas.values() if a.detector is not None]
