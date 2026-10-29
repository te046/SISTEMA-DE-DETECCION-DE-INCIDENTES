import os, sys, tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ["VIGILANCIA_DATA"] = _tmp
os.environ["SECRET_KEY"] = "clave-solo-para-pruebas-0123456789"
os.environ["INGEST_KEY"] = "ingesta-pruebas"
os.environ["CLAVE_RESPONSABLE"] = "Prueba-Resp-1"
os.environ["CLAVE_VIGILANTE"] = "Prueba-Vig-1"
os.environ["CLAVE_ADMIN"] = "Prueba-Adm-1"
os.environ["VIGILANCIA_FRONTEND"] = str(Path(_tmp) / "no-existe")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    from app import seed
    from app.main import app
    seed.main()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth(client):
    r = client.post("/api/v1/auth/token", json={"usuario": "responsable.vigilancia", "clave": "Prueba-Resp-1"})
    assert r.status_code == 200
    return {"Authorization": "Bearer " + r.json()["access_token"]}


INGEST = {"X-Api-Key": "ingesta-pruebas"}


def alerta_base(**kw):
    d = {"tipo": "Grito", "prioridad": 2, "dispositivos": "Nodo de audio 2", "zona": "Zona 2", "confianza": 0.84,
         "modalidades": [{"modalidad": "audio", "clase": "grito", "confianza": 0.84}], "origen": "simulado"}
    d.update(kw)
    return d
