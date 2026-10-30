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


# ---------------------------------------------------------------- regla aprobada el 30/10/2026
def test_video_y_audio_es_alta_siempre_aunque_el_audio_no_sea_urgente():
    a = fusionar([d("audio", "voces elevadas", .60), d("video", "posible agresión", .55, t=1)])
    assert a["prioridad"] == 1 and {m["modalidad"] for m in a["modalidades"]} == {"video", "audio"}


def test_solo_video_nunca_es_alta():
    assert fusionar([d("video", "posible agresión", .55)])["prioridad"] == 3          # baja
    assert fusionar([d("video", "posible agresión", .95)])["prioridad"] == 2          # media, nunca alta


def test_video_y_audio_en_zonas_distintas_no_suben_a_alta():
    a = fusionar([d("video", "posible agresión", .90, z="Zona 1"), d("audio", "grito", .60, z="Zona 2")])
    assert a["prioridad"] != 1 and len(a["modalidades"]) == 1


def test_rn01_video_bajo_el_umbral_no_genera_alerta():
    assert fusionar([d("video", "posible agresión", .49)]) is None


# ---------------------------------------------------------------- umbral provisional
def test_umbral_desde_entorno():
    import pytest
    from app.fusion import umbral_desde_entorno
    assert umbral_desde_entorno(None) == 0.50 and umbral_desde_entorno("") == 0.50
    assert umbral_desde_entorno("0.30") == 0.30 and umbral_desde_entorno("0,25") == 0.25
    for malo in ("abc", "0", "1.5", "-0.2"):
        with pytest.raises(ValueError):
            umbral_desde_entorno(malo)


def test_umbral_provisional_cambia_lo_que_alerta(monkeypatch):
    from app import fusion
    monkeypatch.setattr(fusion, "UMBRAL_MINIMO", 0.25)
    assert fusionar([d("audio", "grito", .30)])["prioridad"] == 2
