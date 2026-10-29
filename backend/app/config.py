"""Configuración. Los secretos se generan solos la primera vez y se guardan en data/."""
import os, secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("VIGILANCIA_DATA", ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.environ.get("VIGILANCIA_DB", DATA_DIR / "vigilancia.db"))
FRONTEND_DIR = Path(os.environ.get("VIGILANCIA_FRONTEND", ROOT / "frontend"))

TOKEN_MINUTES = int(os.environ.get("TOKEN_MINUTES", "480"))      # turno de 8 h
MAX_FAILED_LOGINS = 5                                               # control de seguridad del diseño
LOCK_MINUTES = 15


def _secret(env_name: str, filename: str) -> str:
    """Lee el secreto del entorno o de data/<archivo>; si no existe, lo crea."""
    if os.environ.get(env_name):
        return os.environ[env_name]
    f = DATA_DIR / filename
    if not f.exists():
        f.write_text(secrets.token_urlsafe(32), encoding="utf-8")
        try:
            f.chmod(0o600)
        except OSError:
            pass
    return f.read_text(encoding="utf-8").strip()


SECRET_KEY = _secret("SECRET_KEY", ".secret_key")      # firma de tokens de sesión
INGEST_KEY = _secret("INGEST_KEY", ".ingest_key")      # clave del módulo de detección (edge)
