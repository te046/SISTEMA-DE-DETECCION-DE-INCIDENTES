"""Margen de arranque del micrófono: no declararlo caído antes de que entregue su primer bloque."""
from edge.buffers import BufferAudio
from edge.captura import LIMITE_SIN_AUDIO_S, MARGEN_ARRANQUE_S, CapturaAudio, fuente_viva


def test_recien_abierto_sin_bloques_tiene_margen():
    # Caso real observado: MME tardó ~2 s en entregar el primer bloque y se marcó caído a los 0,5 s.
    assert fuente_viva(ahora=100.5, abierto_en=100.0, ultimo_bloque=0.0)
    assert fuente_viva(ahora=102.0, abierto_en=100.0, ultimo_bloque=0.0)
    assert fuente_viva(ahora=100.0 + MARGEN_ARRANQUE_S - 0.01, abierto_en=100.0, ultimo_bloque=0.0)


def test_sin_primer_bloque_tras_el_margen_se_considera_caido():
    assert not fuente_viva(ahora=100.0 + MARGEN_ARRANQUE_S, abierto_en=100.0, ultimo_bloque=0.0)


def test_corte_tras_haber_entregado_audio_usa_el_limite_normal():
    assert fuente_viva(ahora=103.0, abierto_en=100.0, ultimo_bloque=101.0)
    assert not fuente_viva(ahora=101.0 + LIMITE_SIN_AUDIO_S, abierto_en=100.0, ultimo_bloque=101.0)


def test_bloque_de_una_apertura_anterior_no_cuenta_como_audio_nuevo():
    # Tras reconectar, el último bloque es de la sesión previa: rige el margen de arranque, no el límite.
    assert fuente_viva(ahora=202.0, abierto_en=200.0, ultimo_bloque=150.0)
    assert not fuente_viva(ahora=200.0 + MARGEN_ARRANQUE_S, abierto_en=200.0, ultimo_bloque=150.0)


def test_cerrado_nunca_esta_vivo():
    assert not fuente_viva(ahora=100.0, abierto_en=None, ultimo_bloque=99.9)


def test_captura_sin_abrir_no_esta_viva():
    assert not CapturaAudio(BufferAudio()).vivo        # los latidos no la informan conectada antes de abrir
