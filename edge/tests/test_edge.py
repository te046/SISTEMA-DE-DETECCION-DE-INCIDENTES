"""Pruebas del edge sin cámara ni micrófono: audio sintético, clasificador falso y API falsa."""
import io
import wave

import numpy as np
import pytest

from edge.buffers import BufferAudio, BufferVideo
from edge.captura import PATRON_BLUETOOTH, esperas_backoff
from edge.clasificador_audio import CLASES_DISENO, indices_por_clase, leer_nombres, mapear_puntajes
from edge.detector import Detector
from edge.entrega import entregar
from edge.evidencia import escribir_webm, wav_bytes

SR = 16000


def test_buffer_audio_ventanas_y_hora_de_captura():
    b = BufferAudio(SR, segundos=3)
    for k in range(10):                                    # 10 bloques de 0,5 s que empiezan en t=100
        b.agregar(100 + 0.5 * k, np.full(SR // 2, k, np.float32))
    assert b.total == 5 * SR
    assert b.ventana(0, SR) is None                        # ya salió del búfer (solo guarda ~3 s)
    v = b.ventana(4 * SR, SR)
    assert v.size == SR and v[0] == 8 and v[-1] == 9
    assert b.instante(4 * SR + SR // 4) == pytest.approx(104.25)   # bloque 8 (t=104) + 0,25 s
    assert b.instante(0) is None
    assert b.ventana(5 * SR - 10, SR) is None              # aún no llegan esas muestras
    assert b.recorte(103.0, 104.0).size == SR              # 1 s exacto entre dos instantes
    assert b.recorte(104.5, 110.0).size == SR // 2         # solo hay audio hasta t=105


def test_buffer_video_recorte_por_tiempo():
    b = BufferVideo(segundos=1, fps=10)
    for k in range(20):
        b.agregar(10 + k * 0.1, np.zeros((4, 4, 3), np.uint8))
    assert len(b.recorte(0, 100)) == 10                    # maxlen = 1 s × 10 fps
    assert b.ultimo()[0] == pytest.approx(11.9)


def test_mapa_de_clases_existe_en_yamnet():
    idx = indices_por_clase(leer_nombres())
    assert set(idx) == set(CLASES_DISENO) and all(idx.values())


def test_mapear_puntajes_toma_maximo_y_aplica_umbral():
    nombres = ["Speech", "Shatter", "Glass", "Screaming", "Shout", "Yell", "Children shouting",
               "Smash, crash", "Breaking", "Bang", "Slam", "Gunshot, gunfire", "Machine gun"]
    idx = indices_por_clase(nombres)
    p = np.zeros((2, len(nombres)), np.float32)
    p[0, nombres.index("Glass")] = 0.6
    p[1, nombres.index("Shatter")] = 0.9
    p[1, nombres.index("Shout")] = 0.3                     # bajo el umbral: no cuenta
    r = mapear_puntajes(p, idx, umbral=0.5)
    assert [(c, round(conf, 2)) for c, conf, _ in r] == [("rotura de vidrio", 0.9)]
    assert nombres[r[0][2]] == "Shatter"


def test_backoff_duplica_hasta_el_maximo():
    g = esperas_backoff(1, 8)
    assert [next(g) for _ in range(6)] == [1, 2, 4, 8, 8, 8]


def test_patron_bluetooth():
    assert PATRON_BLUETOOTH.search("Auriculares (WH-1000XM4 Hands-Free AG Audio)")
    assert not PATRON_BLUETOOTH.search("Micrófono (Realtek(R) Audio)")


def test_wav_y_webm_validos(tmp_path):
    datos = wav_bytes(np.sin(np.linspace(0, 100, SR)).astype(np.float32))
    with wave.open(io.BytesIO(datos)) as w:
        assert (w.getframerate(), w.getnchannels(), w.getnframes()) == (SR, 1, SR)
    fotos = [(k * 0.1, np.full((120, 160, 3), k * 10, np.uint8)) for k in range(12)]
    assert escribir_webm(fotos, tmp_path / "c.webm")
    assert (tmp_path / "c.webm").read_bytes()[:4] == b"\x1a\x45\xdf\xa3"   # cabecera EBML de WebM
    assert not escribir_webm(fotos[:1], tmp_path / "d.webm")


class ClasificadorFalso:
    """Dispara 'grito' cuando la ventana tiene energía alta (como un sonido fuerte de prueba)."""
    def clasificar(self, v):
        return [("grito", 0.84, "Screaming")] if np.abs(v).mean() > 0.3 else []


class ApiFalsa:
    def __init__(self):
        self.subidas, self.alertas = [], []

    def subir(self, nombre, datos, mime):
        self.subidas.append((nombre, len(datos), mime))
        return f"/api/v1/evidencias/{len(self.subidas):032x}{nombre[-5:] if nombre.endswith('.webm') else '.wav'}"

    def alerta(self, alerta, ea, ev):
        self.alertas.append((alerta, ea, ev))
        from datetime import datetime, timezone
        det = datetime.fromtimestamp(alerta["detectado_en"], timezone.utc)
        return {"codigo": "A-0001", "tipo": alerta["tipo"], "detectado_en": det.isoformat(), "generado_en": det.isoformat()}


def _escena(reloj):
    """8 s de silencio con un golpe fuerte de 0,6 s en t0+4 s, más video a 10 fps."""
    t0 = 1000.0
    audio, video = BufferAudio(SR, 15), BufferVideo(15, 10)
    for k in range(80):                                    # bloques de 0,1 s
        t = t0 + k * 0.1
        audio.agregar(t, np.full(SR // 10, 0.8 if 4.0 <= k * 0.1 < 4.6 else 0.01, np.float32))
        video.agregar(t, np.zeros((90, 160, 3), np.uint8))
    return Detector(ClasificadorFalso(), audio, video, "Zona 1", "Micrófono de la laptop", "Webcam de la laptop", reloj=reloj), t0


def test_detector_un_evento_con_hora_de_captura_y_enfriamiento():
    ahora = [0.0]
    d, t0 = _escena(lambda: ahora[0])
    assert d.procesar() == 15                              # (8 s − 1 s) / 0,5 s + 1 ventanas
    assert len(d.pendientes) == 1                          # varias ventanas lo ven; el enfriamiento evita duplicados
    e = d.pendientes[0]
    assert t0 + 3.0 <= e.t_evento <= t0 + 4.5              # hora de la captura, no de la inferencia
    assert e.alerta["tipo"] == "Grito" and e.alerta["prioridad"] == 2
    ahora[0] = e.listo_en - 0.01
    assert d.listos() == []                                # espera el post-evento
    ahora[0] = e.listo_en
    assert len(d.listos()) == 1 and d.pendientes == []


def test_entrega_sube_audio_y_video_y_registra_tiempos(tmp_path):
    ahora = [1e12]
    d, _ = _escena(lambda: ahora[0])
    d.procesar()
    e = d.listos()[0]
    api = ApiFalsa()
    csv_path = tmp_path / "m.csv"
    entregar(e, d, api, csv_path)
    mimes = sorted(m for _, _, m in api.subidas)
    assert mimes == ["audio/wav", "video/webm"]
    alerta, ea, ev = api.alertas[0]
    assert ea.endswith(".wav") and ev.endswith(".webm")
    assert alerta["modalidades"] == [{"modalidad": "audio", "clase": "grito", "confianza": 0.84}]
    lineas = csv_path.read_text(encoding="utf-8").splitlines()
    assert lineas[0].startswith("sesion,codigo,tipo,prioridad") and lineas[1].startswith("prueba,") and len(lineas) == 2


def test_yamnet_real_no_alerta_con_silencio_ni_ruido_suave():
    from edge.clasificador_audio import MODELOS_DIR, ClasificadorYamnet
    if not (MODELOS_DIR / "yamnet.onnx").exists():
        pytest.skip("Modelo no descargado: python -m edge.descargar_modelos")
    c = ClasificadorYamnet(umbral=0.5)
    assert c.puntajes(np.zeros(SR, np.float32)).shape[1] == 521
    assert c.clasificar(np.zeros(SR, np.float32)) == []
    ruido = (np.random.default_rng(0).standard_normal(SR) * 0.005).astype(np.float32)
    assert c.clasificar(ruido) == []


def test_csv_con_sesion_y_rotacion_del_formato_anterior(tmp_path):
    from edge.entrega import COLUMNAS, preparar_registro
    ruta = tmp_path / "mediciones_latencia.csv"
    ruta.write_text("codigo,tipo,detectado_en,generado_en,inferencia_s,espera_post_s,subida_s,total_s,con_video\nA-1,Grito,x,y,1,1,1,2,False\n", encoding="utf-8")
    renombrado = preparar_registro(ruta)
    assert renombrado is not None and renombrado.exists() and not ruta.exists()
    assert "A-1" in renombrado.read_text(encoding="utf-8")                     # no se perdió nada
    ahora = [1e12]
    d, _ = _escena(lambda: ahora[0]); d.procesar()
    entregar(d.listos()[0], d, ApiFalsa(), ruta, sesion="tesis")
    filas = ruta.read_text(encoding="utf-8").splitlines()
    assert filas[0] == ",".join(COLUMNAS) and filas[1].startswith("tesis,A-0001,Grito,2,audio,0.5,")
    assert preparar_registro(ruta) is None                                      # mismo formato: no se toca
    with pytest.raises(ValueError):
        entregar(None, d, ApiFalsa(), ruta, sesion="otra")              # se valida antes de tocar nada
