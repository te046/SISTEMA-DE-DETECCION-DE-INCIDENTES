"""Modelo de video de línea base, coordinación audio + video por zona y nueva regla de prioridad (sin cámara)."""
import numpy as np
import pytest

from edge.buffers import BufferAudio, BufferVideo
from edge.clasificador_video import CLASE, MODELO, muestrear, preprocesar, probabilidad_pelea
from edge.coordinador import Coordinador
from edge.detector import Detector
from edge.detector_video import MonitorVideo
from edge.entrega import entregar

SR = 16000


# ---------------------------------------------------------------- preprocesado (puro)
def test_muestrear_reparte_y_repite():
    assert muestrear(list(range(32)))[0] == 0 and muestrear(list(range(32)))[-1] == 31
    assert len(muestrear(list(range(8)))) == 16 and muestrear([]) == []


def test_preprocesar_forma_y_normalizacion():
    blanco = [np.full((480, 640, 3), 255, np.uint8)] * 16
    x = preprocesar(blanco)
    assert x.shape == (1, 16, 3, 224, 224) and x.dtype == np.float32
    assert x[0, 0, 0, 0, 0] == pytest.approx((1 - 0.485) / 0.229, rel=1e-4)       # canal R (BGR → RGB)
    assert preprocesar([np.zeros((120, 100, 3), np.uint8)] * 16).shape == (1, 16, 3, 224, 224)   # imagen chica


def test_probabilidad_pelea_softmax():
    assert probabilidad_pelea(np.array([[2.0, 0.0]]), 0) == pytest.approx(1 / (1 + np.exp(-2)))
    assert probabilidad_pelea(np.array([[0.0, 0.0]]), 0) == pytest.approx(0.5)


# ---------------------------------------------------------------- monitor y coordinación
class VideoFalso:
    def __init__(self, p, umbral=0.5):
        self.p, self.umbral = p, umbral

    def probabilidad(self, fotos):
        return self.p


class AudioFalso:
    def __init__(self, resultados):
        self.resultados, self.umbral = resultados, 0.5

    def clasificar(self, v):
        return self.resultados if np.abs(v).mean() > 0.3 else []


def _video(segundos=3.0, t0=1000.0):
    b = BufferVideo(15, 10)
    for k in range(int(segundos * 10)):
        b.agregar(t0 + k * 0.1, np.zeros((48, 64, 3), np.uint8))
    return b


def _audio(t0=1000.0, segundos=4.0, fuerte_desde=1.0, fuerte_hasta=1.6):
    b = BufferAudio(SR, 15)
    for k in range(int(segundos * 10)):
        t = k * 0.1
        b.agregar(t0 + t, np.full(SR // 10, 0.8 if fuerte_desde <= t < fuerte_hasta else 0.01, np.float32))
    return b


def test_solo_video_genera_evento_de_prioridad_baja_o_media():
    ahora = [0.0]
    m = MonitorVideo(VideoFalso(0.70), _video(), "Zona 1", "Webcam", Coordinador(), reloj=lambda: ahora[0])
    assert m.evaluar_ahora() == pytest.approx(0.70)
    ahora[0] = 1e12
    e = m.listos()[0]
    assert e.alerta["prioridad"] == 3 and e.alerta["modalidades"][0]["modalidad"] == "video"
    assert e.alerta["tipo"] == "Posible agresión"
    assert m.evaluar_ahora() is None                       # sin fotogramas nuevos no repite la inferencia
    m2 = MonitorVideo(VideoFalso(0.95), _video(), "Zona 1", "Webcam", Coordinador(), reloj=lambda: 1e12)
    m2.evaluar_ahora()
    assert m2.listos()[0].alerta["prioridad"] == 2         # solo video nunca es alta


def test_video_bajo_umbral_no_crea_evento_y_queda_registrado():
    m = MonitorVideo(VideoFalso(0.40), _video(), "Zona 1", "Webcam", Coordinador(), reloj=lambda: 1e12)
    m.evaluar_ahora()
    assert m.listos() == [] and list(m.decisiones) == []   # bajo el umbral del clasificador: ni candidata


def test_video_y_audio_misma_zona_una_sola_alerta_de_prioridad_alta():
    coord, ahora = Coordinador(), [0.0]
    audio = _audio()
    det = Detector(AudioFalso([("voces elevadas", 0.60, "Shout")]), audio, None, "Zona 1", "Mic", coordinador=coord, reloj=lambda: ahora[0])
    mon = MonitorVideo(VideoFalso(0.65), _video(), "Zona 1", "Webcam", coord, audio=audio, reloj=lambda: ahora[0])
    mon.evaluar_ahora()
    det.procesar()
    ahora[0] = 1e12
    eventos = mon.listos() + det.listos()
    assert len(eventos) == 1                               # un incidente, una alerta
    a = eventos[0].alerta
    assert a["prioridad"] == 1 and {m["modalidad"] for m in a["modalidades"]} == {"video", "audio"}
    assert any("ya cubierto" in d.motivo for d in list(det.decisiones) + list(mon.decisiones))


def test_video_y_audio_en_zonas_distintas_no_se_fusionan():
    coord, ahora = Coordinador(), [0.0]
    det = Detector(AudioFalso([("grito", 0.80, "Screaming")]), _audio(), None, "Zona 2", "Mic", coordinador=coord, reloj=lambda: ahora[0])
    mon = MonitorVideo(VideoFalso(0.65), _video(), "Zona 1", "Webcam", coord, reloj=lambda: ahora[0])
    mon.evaluar_ahora(); det.procesar()
    ahora[0] = 1e12
    eventos = mon.listos() + det.listos()
    assert sorted(e.alerta["prioridad"] for e in eventos) == [2, 3]


def test_evento_de_video_sin_microfono_se_entrega_solo_con_video(tmp_path):
    m = MonitorVideo(VideoFalso(0.70), _video(), "Zona 1", "Webcam", Coordinador(), reloj=lambda: 1e12)
    m.evaluar_ahora()

    class Api:
        subidas = []
        def subir(self, nombre, datos, mime):
            self.subidas.append(mime); return f"/api/v1/evidencias/{'0' * 32}.webm"
        def alerta(self, alerta, ea, ev):
            from datetime import datetime, timezone
            iso = datetime.fromtimestamp(alerta["detectado_en"], timezone.utc).isoformat()
            return {"codigo": "A-1", "tipo": alerta["tipo"], "detectado_en": iso, "generado_en": iso}
    api = Api()
    entregar(m.listos()[0], m, api, tmp_path / "m.csv")
    assert api.subidas == ["video/webm"]


# ---------------------------------------------------------------- modelo real (si ya se exportó)
def test_modelo_onnx_real_devuelve_una_probabilidad():
    if not MODELO.exists():
        pytest.skip("Modelo de video no exportado: .venv-export\\Scripts\\python scripts\\exportar_modelo_video.py")
    from edge.clasificador_video import ClasificadorVideo
    c = ClasificadorVideo()
    p = c.probabilidad([np.random.default_rng(1).integers(0, 255, (480, 640, 3), np.uint8) for _ in range(16)])
    assert 0.0 <= p <= 1.0 and CLASE == "posible agresión"
