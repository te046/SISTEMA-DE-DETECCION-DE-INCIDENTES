"""Reutiliza la fusión del backend (backend/app/fusion.py) sin duplicarla.

fusion.py es una función pura sin dependencias del servidor, así que el edge la importa tal cual
y ambos lados aplican exactamente las mismas reglas de prioridad.
"""
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.fusion import Deteccion, fusionar  # noqa: E402

__all__ = ["Deteccion", "fusionar"]
