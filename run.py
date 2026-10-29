"""Arranca el sistema (API + panel web) en esta laptop.

    python run.py            → busca un puerto libre desde el 8000 y no toca los de otros proyectos
    python run.py --port 8123  → usa ese puerto solo si está libre

Primero ejecute una vez:  pip install -r backend/requirements.txt
"""
import argparse, socket, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))


def libre(puerto: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, puerto)) != 0       # si nadie responde, está libre


def elegir(preferido: int | None) -> int:
    if preferido:
        if libre(preferido):
            return preferido
        sys.exit(f"El puerto {preferido} ya está en uso (otro proyecto). Elija otro con --port o no use la opción.")
    for p in range(8000, 8100):
        if libre(p):
            return p
    sys.exit("No hay puertos libres entre 8000 y 8099.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    try:
        import uvicorn  # noqa: F401
        import fastapi  # noqa: F401
        import jwt  # noqa: F401
    except ImportError:
        sys.exit("Faltan dependencias. Ejecute una vez:  pip install -r backend/requirements.txt")
    from app import seed
    seed.main()
    puerto = elegir(a.port)
    from app import config
    (config.DATA_DIR / ".api_url").write_text(f"http://{a.host}:{puerto}", encoding="utf-8")   # lo lee python -m edge
    print(f"\nPanel:  http://{a.host}:{puerto}/\nAPI:    http://{a.host}:{puerto}/docs\n(Ctrl+C para detener)\n")
    import uvicorn
    uvicorn.run("app.main:app", host=a.host, port=puerto, log_level="info")


if __name__ == "__main__":
    main()
