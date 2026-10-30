"""Reutiliza la fusión del backend (backend/app/fusion.py) sin duplicarla.

fusion.py es una función pura sin dependencias del servidor, así que el edge la importa tal cual
y ambos lados aplican exactamente las mismas reglas de prioridad.
"""
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app import fusion as _fusion  # noqa: E402
from app.fusion import Deteccion, fusionar  # noqa: E402
from app.urls import enmascarar_texto, enmascarar_url  # noqa: E402  (sin dependencias, igual que fusion.py)


def umbral_de_fusion() -> float:
    """Confianza mínima que exige la fusión para generar una alerta (se lee en cada uso, no se copia)."""
    return _fusion.UMBRAL_MINIMO


def fijar_umbral_fusion(valor: str) -> float:
    """PROVISIONAL (--umbral-fusion): solo para demostraciones, mismas validaciones que VIGILANCIA_UMBRAL_FUSION."""
    _fusion.UMBRAL_MINIMO = _fusion.umbral_desde_entorno(valor)
    return _fusion.UMBRAL_MINIMO


__all__ = ["Deteccion", "fusionar", "umbral_de_fusion", "fijar_umbral_fusion", "enmascarar_texto", "enmascarar_url"]
