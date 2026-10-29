"""Fusión de evidencias de video y audio (RF-05) y prioridad de la alerta (RF-06).

Es una función pura: recibe las detecciones de los modelos y devuelve la alerta a
registrar. Así se puede probar sin cámaras ni micrófonos. Los umbrales y las reglas de
prioridad son parámetros de diseño y deben calibrarse con la línea base (O1) y con
grabaciones reales del pabellón: aquí no son resultados medidos.
"""
from dataclasses import dataclass

UMBRAL_MINIMO = 0.50          # por debajo de este valor un modelo no genera evidencia
VENTANA_SEGUNDOS = 3.0        # video y audio se fusionan si ocurren dentro de esta ventana

# Clases acústicas de mayor urgencia (ajustar con las clases reales del modelo de audio).
AUDIO_URGENTE = {"rotura de vidrio", "grito", "disparo"}


@dataclass
class Deteccion:
    modalidad: str            # 'video' | 'audio'
    clase: str
    confianza: float
    dispositivo: str
    zona: str
    instante: float           # segundos (epoch) del evento


def fusionar(detecciones: list[Deteccion]) -> dict | None:
    """Devuelve {'tipo','prioridad','confianza','modalidades','dispositivos','zona'} o None.

    RN-01: solo se genera alerta si al menos un modelo clasificó el evento con confianza
    suficiente.
    """
    validas = [d for d in detecciones if d.confianza >= UMBRAL_MINIMO]
    if not validas:
        return None
    base = max(validas, key=lambda d: d.confianza)
    cercanas = [d for d in validas if abs(d.instante - base.instante) <= VENTANA_SEGUNDOS and d.zona == base.zona]
    mods = {d.modalidad for d in cercanas}
    audio_urgente = any(d.modalidad == "audio" and d.clase.lower() in AUDIO_URGENTE for d in cercanas)

    if mods == {"video", "audio"} and audio_urgente:
        prioridad = 1
    elif audio_urgente or mods == {"video", "audio"}:
        prioridad = 2
    else:
        prioridad = 3 if base.confianza < 0.80 else 2

    conf = sum(d.confianza for d in cercanas) / len(cercanas)
    tipo = next((d.clase for d in cercanas if d.modalidad == "audio" and d.clase.lower() in AUDIO_URGENTE), base.clase)
    return {
        "tipo": tipo[:1].upper() + tipo[1:],
        "prioridad": prioridad,
        "confianza": round(conf, 3),
        "modalidades": [{"modalidad": d.modalidad, "clase": d.clase, "confianza": round(d.confianza, 3)} for d in cercanas],
        "dispositivos": " + ".join(sorted({d.dispositivo for d in cercanas})),
        "zona": base.zona,
        "detectado_en": min(d.instante for d in cercanas),
    }
