from app.fusion import Deteccion, fusionar


def d(m, c, conf, dev="X", z="Zona 1", t=0):
    return Deteccion(m, c, conf, dev, z, t)


def test_sin_modelo_confiable_no_hay_alerta():
    assert fusionar([d("audio", "grito", .30)]) is None          # RN-01
    assert fusionar([]) is None


def test_video_y_audio_urgente_es_prioridad_alta():
    a = fusionar([d("audio", "rotura de vidrio", .91, "Nodo 1"), d("video", "evento visual", .88, "Cámara 2", t=.5)])
    assert a["prioridad"] == 1 and len(a["modalidades"]) == 2 and a["tipo"] == "Rotura de vidrio"


def test_solo_audio_urgente_es_media():
    assert fusionar([d("audio", "grito", .84)])["prioridad"] == 2


def test_video_con_poca_confianza_es_baja():
    assert fusionar([d("video", "evento visual", .60)])["prioridad"] == 3


def test_eventos_lejanos_en_el_tiempo_no_se_fusionan():
    a = fusionar([d("audio", "grito", .90, t=0), d("video", "evento visual", .85, t=30)])
    assert len(a["modalidades"]) == 1
