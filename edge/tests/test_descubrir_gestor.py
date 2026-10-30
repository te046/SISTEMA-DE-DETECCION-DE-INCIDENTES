"""Inventario de fuentes y gestor de conexiones (sin hardware ni red)."""
import logging

import numpy as np
import pytest

from edge.buffers import BufferAudio, BufferVideo
from edge.captura import CapturaVideo
from edge.descubrir import agrupar_microfonos, camaras_locales, resolver_microfono
from edge.gestor import MSG_MICRO_NO_ESTA, Gestor

URL_SECRETA = "rtsp://admin:Sup3rClave@192.168.1.20:554/stream1"

# Lista real de esta laptop (python -m edge --listar, 29/10/2026), con los nombres tal como los da Windows.
ENTRADAS_LAPTOP = [
    {"indice": 0, "nombre": "Asignador de sonido Microsoft - Input", "api": "MME"},
    {"indice": 1, "nombre": "Microphone Array (Intel® Smart ", "api": "MME"},
    {"indice": 4, "nombre": "Controlador primario de captura de sonido", "api": "Windows DirectSound"},
    {"indice": 5, "nombre": "Microphone Array (Intel® Smart Sound Technology for Digital Microphones)", "api": "Windows DirectSound"},
    {"indice": 9, "nombre": "Microphone Array (Intel® Smart Sound Technology for Digital Microphones)", "api": "Windows WASAPI"},
    {"indice": 10, "nombre": "Stereo Mix (Realtek HD Audio Stereo input)", "api": "Windows WDM-KS"},
    {"indice": 13, "nombre": "PC Speaker (Realtek HD Audio 2nd output with SST)", "api": "Windows WDM-KS"},
    {"indice": 17, "nombre": "Microphone (Realtek HD Audio Mic input)", "api": "Windows WDM-KS"},
    {"indice": 18, "nombre": "Microphone Array 1 ()", "api": "Windows WDM-KS"},
    {"indice": 30, "nombre": "Auriculares (WH-1000XM4 Hands-Free AG Audio)", "api": "MME"},
]


def test_agrupa_el_mismo_microfono_y_usa_mme():
    m = {x["nombre"]: x for x in agrupar_microfonos(ENTRADAS_LAPTOP)}
    intel = m["Microphone Array (Intel® Smart Sound Technology for Digital Microphones)"]
    assert intel["utilizable"] and intel["indice"] == 1                   # 3 entradas → 1, captura por MME
    assert sum("Intel" in n for n in m) == 1


def test_marca_lo_que_no_sirve_y_bluetooth():
    m = {x["nombre"]: x for x in agrupar_microfonos(ENTRADAS_LAPTOP)}
    for nombre in ("Stereo Mix (Realtek HD Audio Stereo input)", "Asignador de sonido Microsoft - Input",
                   "Controlador primario de captura de sonido", "PC Speaker (Realtek HD Audio 2nd output with SST)"):
        assert not m[nombre]["utilizable"] and m[nombre]["motivo"]
    assert "WDM-KS" in m["Microphone Array 1 ()"]["motivo"]               # solo WDM-KS: aún no soportado
    bt = m["Auriculares (WH-1000XM4 Hands-Free AG Audio)"]
    assert bt["bluetooth"] and bt["utilizable"]
    orden = agrupar_microfonos(ENTRADAS_LAPTOP)
    assert all(x["utilizable"] for x in orden[:2]) and not orden[-1]["utilizable"]   # primero los que sirven


def test_resolver_microfono_y_camaras():
    inv = {"microfonos": agrupar_microfonos(ENTRADAS_LAPTOP), "camaras": camaras_locales([{"indice": 0, "resolucion": "1280x720"}])}
    clave = next(x["clave"] for x in inv["microfonos"] if "Intel" in x["nombre"])
    assert resolver_microfono(clave, inv) == 1
    assert resolver_microfono("audio:stereo mix (realtek hd audio", inv) is None
    assert inv["camaras"][0]["clave"] == "camara:local:0"


def test_captura_video_nunca_muestra_la_direccion(caplog):
    c = CapturaVideo(BufferVideo(), URL_SECRETA)
    assert "Sup3rClave" not in c.descripcion and "192.168.1.20" in c.descripcion
    assert "Sup3rClave" not in repr(c)


# ---------------------------------------------------------------- gestor
class CapturaFalsa:
    def __init__(self, fuente):
        self.fuente, self.buffer = fuente, BufferAudio() if isinstance(fuente, int) and fuente >= 100 else BufferVideo()
        self.iniciada = self.detenida = False
        self.vivo, self.ultimo_error = True, None

    def iniciar(self):
        self.iniciada = True

    def detener(self):
        self.detenida = True


class ApiFalsa:
    def __init__(self):
        self.fuentes, self.buscar = [], False
        self.inventarios, self.informes, self.latidos_enviados, self.registros = [], [], [], []
        self.direccion_error = None

    def estado(self):
        return {"buscar": self.buscar, "fuentes": list(self.fuentes)}

    def subir_inventario(self, inv):
        self.inventarios.append(inv); self.buscar = False

    def direccion(self, fid):
        if self.direccion_error:
            raise RuntimeError(self.direccion_error)
        return URL_SECRETA

    def informar(self, fid, ok, error=None):
        self.informes.append((fid, ok, error))

    def registrar(self, nombre, tipo, zona):
        self.registros.append(nombre); return 100 + len(self.registros)

    def latido(self, disp_id, activo=True):
        self.latidos_enviados.append((disp_id, activo))


def _gestor(api, abiertas):
    def abrir_audio(indice):
        c = CapturaFalsa(100 + indice); abiertas.append(c); return c

    def abrir_video(fuente):
        c = CapturaFalsa(fuente); abiertas.append(c); return c

    def inventario(camaras=True):
        return {"microfonos": agrupar_microfonos(ENTRADAS_LAPTOP),
                "camaras": camaras_locales([{"indice": 0, "resolucion": "640x480"}] if camaras else [])}

    class Clasif:
        def clasificar(self, v):
            return []
    return Gestor(api, abrir_audio, abrir_video, inventario, crear_clasificador=Clasif)


MIC = {"id": 1, "clave": "audio:microphone array (intel® smart", "tipo": "audio", "clase": "local", "nombre": "Mic", "zona": "Zona 1", "red": False, "actualizado_en": "t1"}
CAM = {"id": 2, "clave": "camara:local:0", "tipo": "camara", "clase": "local", "nombre": "Cam", "zona": "Zona 1", "red": False, "actualizado_en": "t1"}
IP = {"id": 3, "clave": "red:abc", "tipo": "camara", "clase": "ip", "nombre": "Cam IP", "zona": "Zona 2", "red": True, "actualizado_en": "t1"}


def test_conecta_y_desconecta_sin_reiniciar():
    api, abiertas = ApiFalsa(), []
    g = _gestor(api, abiertas)
    api.fuentes = [MIC, CAM]
    g.sincronizar()
    assert set(g.activas) == {1, 2} and all(c.iniciada for c in abiertas)
    assert abiertas[0].fuente == 101                                    # micrófono Intel → índice MME 1
    assert g.activas[1].detector.video is abiertas[1].buffer            # evidencia de video de la misma zona
    assert (1, True, None) in api.informes and (2, True, None) in api.informes
    api.fuentes = [MIC]                                                  # el panel desconecta la cámara
    g.sincronizar()
    assert set(g.activas) == {1} and abiertas[1].detenida
    assert g.activas[1].detector.video is None
    api.fuentes = [{**MIC, "zona": "Zona 3", "actualizado_en": "t2"}]  # cambio de zona: se reabre
    g.sincronizar()
    assert abiertas[0].detenida and g.activas[1].fuente["zona"] == "Zona 3" and len(abiertas) == 3


def test_busqueda_pedida_sube_inventario_e_incluye_camara_en_uso():
    api, abiertas = ApiFalsa(), []
    g = _gestor(api, abiertas)
    api.fuentes = [{**CAM, "clave": "camara:local:3"}]                 # abierta por nosotros: no responde al escaneo
    g.sincronizar()
    api.buscar = True
    g.sincronizar()
    inv = api.inventarios[-1]
    claves = [c["clave"] for c in inv["camaras"]]
    assert "camara:local:0" in claves and "camara:local:3" in claves
    assert api.buscar is False


def test_microfono_que_no_esta_informa_error_util_y_no_reintenta_en_bucle():
    api, abiertas = ApiFalsa(), []
    g = _gestor(api, abiertas)
    api.fuentes = [{**MIC, "clave": "audio:microfono que ya no esta"}]
    g.sincronizar(); g.sincronizar()
    assert api.informes == [(1, False, MSG_MICRO_NO_ESTA)] and not abiertas
    api.fuentes = [{**MIC, "clave": "audio:microfono que ya no esta", "actualizado_en": "t2"}]   # pulsó «Conectar» otra vez
    g.sincronizar()
    assert len(api.informes) == 2


def test_camara_ip_usa_la_direccion_sin_registrarla(caplog):
    caplog.set_level(logging.DEBUG)
    api, abiertas = ApiFalsa(), []
    g = _gestor(api, abiertas)
    api.fuentes = [IP]
    g.sincronizar()
    assert abiertas[0].fuente == URL_SECRETA                            # el edge sí recibe la dirección completa…
    assert "Sup3rClave" not in caplog.text                              # …pero nunca la escribe
    assert all("Sup3rClave" not in str(i) for i in api.informes)


def test_error_al_abrir_se_informa_enmascarado(caplog):
    api, abiertas = ApiFalsa(), []
    g = _gestor(api, abiertas)
    api.direccion_error = f"fallo conectando {URL_SECRETA}"
    api.fuentes = [IP]
    g.sincronizar()
    fid, ok, motivo = api.informes[-1]
    assert (fid, ok) == (3, False) and "192.168.1.20" in motivo and "Sup3rClave" not in motivo
    assert "Sup3rClave" not in caplog.text


def test_fuente_sin_datos_se_informa_y_latidos():
    api, abiertas = ApiFalsa(), []
    g = _gestor(api, abiertas)
    api.fuentes = [MIC]
    g.sincronizar()
    abiertas[0].vivo = False
    g.informar_estados()
    assert api.informes[-1] == (1, False, "El micrófono no entrega audio.")
    g.informar_estados()
    assert len([i for i in api.informes if i[0] == 1]) == 2             # no repite el mismo estado
    g.latidos()
    assert api.latidos_enviados[-1] == (101, False)
    g.cerrar_todo()
    assert abiertas[0].detenida and api.latidos_enviados[-1] == (101, False)


def test_detector_del_gestor_procesa_audio():
    api, abiertas = ApiFalsa(), []
    g = _gestor(api, abiertas)
    api.fuentes = [MIC]
    g.sincronizar()
    buf = abiertas[0].buffer
    for k in range(20):
        buf.agregar(1000 + k * 0.1, np.zeros(1600, np.float32))
    assert g.detectores()[0].procesar() == 3


def test_camara_conectada_crea_monitor_de_video_y_lo_detiene_al_desconectar():
    from edge.detector_video import MonitorVideo

    class VideoFalso:
        umbral = 0.5
        def probabilidad(self, fotos):
            return 0.1
    api, abiertas = ApiFalsa(), []
    g = _gestor(api, abiertas)
    g.crear_clasificador_video = VideoFalso
    api.fuentes = [MIC, CAM]
    g.sincronizar()
    mon = g.activas[2].detector
    assert isinstance(mon, MonitorVideo) and mon.audio is abiertas[0].buffer      # evidencia de audio de la zona
    assert g.activas[1].detector.coordinador is mon.coordinador                   # mismo coordinador de zona
    api.fuentes = [MIC]
    g.sincronizar()
    assert mon._detener.is_set()


def test_sin_modelo_de_video_la_camara_solo_graba_y_avisa_una_vez(caplog):
    api, abiertas = ApiFalsa(), []
    g = _gestor(api, abiertas)
    llamadas = []

    def sin_modelo():
        llamadas.append(1); raise FileNotFoundError("No está el modelo de video.")
    g.crear_clasificador_video = sin_modelo
    api.fuentes = [CAM, {**CAM, "id": 4, "clave": "camara:local:1", "nombre": "Cam 2"}]
    g.sincronizar()
    assert g.activas[2].detector is None and g.activas[4].detector is None and len(llamadas) == 1
    assert caplog.text.count("Sin modelo de video") == 1
