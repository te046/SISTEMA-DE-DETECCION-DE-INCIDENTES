"""Registro de decisiones del detector: clase, confianza, umbrales y por qué alertó o no.

Reproduce los dos casos de la prueba guiada del 30/10/2026 (umbral del clasificador 0,15):
  00:23:43 «Glass 0,22» y 00:24:29 «Screaming 0,30» → ninguno alerta: la fusión exige 0,50.
"""
import logging

import numpy as np

from edge.buffers import BufferAudio
from edge.detector import Detector

SR = 16000


class ClasificadorGuion:
    """Devuelve, ventana por ventana, lo que diga el guion (como hace YAMNet ya mapeado)."""
    def __init__(self, guion, umbral=0.15):
        self.guion, self.umbral, self.i = guion, umbral, 0

    def clasificar(self, v):
        r = self.guion[self.i] if self.i < len(self.guion) else []
        self.i += 1
        return [x for x in r if x[1] >= self.umbral]


def _detector(guion, segundos):
    audio = BufferAudio(SR, 30)
    for k in range(int(segundos * 10)):
        audio.agregar(1000 + k * 0.1, np.zeros(SR // 10, np.float32))
    return Detector(ClasificadorGuion(guion), audio, None, "Zona 1", "Mic", reloj=lambda: 0.0)


def test_casos_de_la_prueba_guiada_no_alertan_por_el_umbral_de_la_fusion(caplog):
    caplog.set_level(logging.INFO, logger="edge.detector")
    d = _detector([[("rotura de vidrio", 0.22, "Glass")], [], [("grito", 0.30, "Screaming")]], 2.0)
    d.procesar()
    assert d.pendientes == []
    assert [(x.clase, x.confianza, x.alerto) for x in d.decisiones] == [("rotura de vidrio", 0.22, False), ("grito", 0.30, False)]
    assert all("bajo el umbral de la fusión (0.50)" in x.motivo for x in d.decisiones)
    assert all(x.umbral_clasificador == 0.15 and x.umbral_fusion == 0.50 for x in d.decisiones)
    assert "Decisión" in caplog.text and "Screaming" in caplog.text and "sin alerta" in caplog.text


def test_alerta_y_luego_enfriamiento_quedan_registrados():
    d = _detector([[("grito", 0.70, "Screaming")], [("grito", 0.80, "Screaming")], [], [], [], [], [], [], [], [], [], [], [], [], [], [],
                   [("grito", 0.75, "Screaming")]], 10.0)
    d.procesar()
    alertas = [x for x in d.decisiones if x.alerto]
    assert len(d.pendientes) == 2 and len(alertas) == 2                    # t=1000 y t=1008 (8 s después)
    enfriada = d.decisiones[1]
    assert not enfriada.alerto and enfriada.motivo.startswith("enfriamiento: «grito» alertó hace 0.5 s")
    assert "prioridad 2" in alertas[0].motivo


def test_varias_clases_en_una_ventana_cada_una_con_su_motivo():
    d = _detector([[("grito", 0.90, "Screaming"), ("voces elevadas", 0.30, "Shout")]], 1.0)
    d.procesar()
    por_clase = {x.clase: x for x in d.decisiones}
    assert por_clase["grito"].alerto
    assert not por_clase["voces elevadas"].alerto and "fusión" in por_clase["voces elevadas"].motivo


def test_sin_candidatas_no_se_registra_nada():
    d = _detector([[("grito", 0.10, "Screaming")]], 1.0)                 # bajo el umbral del clasificador (0,15)
    d.procesar()
    assert list(d.decisiones) == []
