"""Horas de las alertas: todo en UTC con zona explícita, para que I1 e I2 no se corran 5 h (Perú = UTC−5)."""
from datetime import datetime, timedelta, timezone

from conftest import INGEST, alerta_base


def test_detectado_en_sin_zona_se_rechaza(client):
    r = client.post("/api/v1/alertas", json=alerta_base(detectado_en="2026-10-30T00:23:43"), headers=INGEST)
    assert r.status_code == 422 and "zona horaria" in r.json()["detail"]["mensaje"]


def test_detectado_en_futuro_se_rechaza(client):
    futuro = (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()
    r = client.post("/api/v1/alertas", json=alerta_base(detectado_en=futuro), headers=INGEST)
    assert r.status_code == 422 and "futuro" in r.json()["detail"]["mensaje"]


def test_hora_local_con_zona_se_guarda_en_utc_y_i1_es_correcto(client):
    lima = timezone(timedelta(hours=-5))
    det_local = datetime.now(lima) - timedelta(seconds=3)               # 3 s antes, expresado en hora de Lima
    a = client.post("/api/v1/alertas", json=alerta_base(detectado_en=det_local.isoformat()), headers=INGEST).json()
    assert a["detectado_en"].endswith("+00:00") and a["generado_en"].endswith("+00:00")
    i1 = (datetime.fromisoformat(a["generado_en"]) - datetime.fromisoformat(a["detectado_en"])).total_seconds()
    assert 2.9 <= i1 < 4.0                                               # no 5 h ni negativo


def test_desfase_pequeno_de_reloj_se_tolera(client):
    casi = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
    assert client.post("/api/v1/alertas", json=alerta_base(detectado_en=casi), headers=INGEST).status_code == 201


def test_resuelto_en_tambien_en_utc(client, auth):
    a = client.post("/api/v1/alertas", json=alerta_base(), headers=INGEST).json()
    r = client.post(f"/api/v1/alertas/{a['id']}/resolucion", json={"accion": "descartar", "clics": 1}, headers=auth).json()
    assert r["resuelto_en"].endswith("+00:00")
