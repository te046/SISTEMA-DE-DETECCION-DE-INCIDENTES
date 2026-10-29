"""Envía alertas SIMULADAS al sistema, como lo haría el módulo de detección.

Sirve para probar el panel y el cálculo de indicadores sin cámaras ni micrófonos.
Las alertas quedan marcadas con origen='simulado' y nunca se mezclan con las reales.

    python scripts/simular.py --url http://127.0.0.1:8000 --cantidad 4
"""
import argparse, json, random, sys, time, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.fusion import Deteccion, fusionar  # noqa: E402

ESCENAS = [
    [Deteccion("audio", "rotura de vidrio", .91, "Nodo de audio 1", "Zona 1", 0), Deteccion("video", "evento visual", .88, "Cámara 2", "Zona 1", 0.4)],
    [Deteccion("audio", "grito", .84, "Nodo de audio 2", "Zona 2", 0)],
    [Deteccion("audio", "choque", .72, "Nodo de audio 1", "Zona 1", 0)],
    [Deteccion("video", "evento visual (persona / acción)", .78, "Cámara 1", "Zona 3", 0)],
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--cantidad", type=int, default=4)
    ap.add_argument("--clave", help="clave de ingesta; por defecto se lee de data/.ingest_key")
    a = ap.parse_args()
    clave = a.clave or (ROOT / "data" / ".ingest_key").read_text().strip()
    for i in range(a.cantidad):
        escena = ESCENAS[i % len(ESCENAS)]
        t0 = datetime.now(timezone.utc).timestamp() - random.uniform(1.5, 4.0)   # latencia simulada de detección
        det = [Deteccion(d.modalidad, d.clase, d.confianza, d.dispositivo, d.zona, t0 + d.instante) for d in escena]
        alerta = fusionar(det)
        if not alerta:
            continue
        alerta["detectado_en"] = datetime.fromtimestamp(alerta["detectado_en"], timezone.utc).isoformat()
        alerta["origen"] = "simulado"
        req = urllib.request.Request(a.url + "/api/v1/alertas", data=json.dumps(alerta).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "X-Api-Key": clave})
        with urllib.request.urlopen(req) as r:
            print("creada", json.loads(r.read())["codigo"], alerta["tipo"], "prioridad", alerta["prioridad"])
        time.sleep(0.3)


if __name__ == "__main__":
    main()
