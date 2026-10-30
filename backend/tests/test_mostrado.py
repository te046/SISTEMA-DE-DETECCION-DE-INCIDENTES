"""«I1 visible»: hora del servidor cuando el panel pinta la alerta. I1 (hasta el servidor) no cambia."""
import sqlite3
from datetime import datetime, timedelta, timezone

from conftest import INGEST, alerta_base


def test_mostrada_la_fija_el_servidor_una_sola_vez(client, auth):
    det = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()
    a = client.post("/api/v1/alertas", json=alerta_base(detectado_en=det), headers=INGEST).json()
    assert a["mostrado_en"] is None
    assert client.post(f"/api/v1/alertas/{a['id']}/mostrada").status_code == 401             # requiere sesión
    m1 = client.post(f"/api/v1/alertas/{a['id']}/mostrada", headers=auth).json()["mostrado_en"]
    m2 = client.post(f"/api/v1/alertas/{a['id']}/mostrada", headers=auth).json()["mostrado_en"]
    assert m1 == m2 and m1.endswith("+00:00")                                                 # solo la primera vez
    assert datetime.fromisoformat(m1) >= datetime.fromisoformat(a["generado_en"])
    assert client.post("/api/v1/alertas/999999/mostrada", headers=auth).status_code == 404


def test_i1_e_i1_visible_son_indicadores_distintos(client, auth):
    antes = client.get("/api/v1/indicadores?origen=simulado", headers=auth).json()
    det = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()
    a = client.post("/api/v1/alertas", json=alerta_base(detectado_en=det), headers=INGEST).json()
    client.post(f"/api/v1/alertas/{a['id']}/mostrada", headers=auth)
    ind = client.get("/api/v1/indicadores?origen=simulado", headers=auth).json()
    assert "I1_ttd_s" in ind and "I1_visible_s" in ind and ind["I1_visible_n"] == antes["I1_visible_n"] + 1
    assert ind["I1_visible_s"] >= 0


def test_deshacer_no_borra_mostrado_en(client, auth):
    a = client.post("/api/v1/alertas", json=alerta_base(), headers=INGEST).json()
    m = client.post(f"/api/v1/alertas/{a['id']}/mostrada", headers=auth).json()["mostrado_en"]
    client.post(f"/api/v1/alertas/{a['id']}/resolucion", json={"accion": "descartar", "clics": 1}, headers=auth)
    assert client.post(f"/api/v1/alertas/{a['id']}/deshacer", headers=auth).json()["mostrado_en"] == m


def test_migracion_agrega_la_columna_a_una_base_antigua(tmp_path, monkeypatch):
    from app import config, db
    vieja = tmp_path / "vieja.db"
    con = sqlite3.connect(vieja)
    con.executescript(db.SCHEMA)                                                            # esquema anterior: sin mostrado_en
    assert "mostrado_en" not in {r[1] for r in con.execute("PRAGMA table_info(alertas)")}
    con.execute("INSERT INTO alertas(codigo,tipo,prioridad,dispositivos,zona,confianza,modalidades,detectado_en,generado_en)"
                " VALUES ('A-0001','Grito',2,'Mic','Zona 1',0.8,'[]','2026-10-29T10:00:00+00:00','2026-10-29T10:00:02+00:00')")
    con.commit(); con.close()
    monkeypatch.setattr(config, "DB_PATH", vieja)
    db.init(); db.init()                                                                    # idempotente
    con = sqlite3.connect(vieja)
    assert "mostrado_en" in {r[1] for r in con.execute("PRAGMA table_info(alertas)")}
    assert con.execute("SELECT codigo FROM alertas").fetchone()[0] == "A-0001"             # no se pierden datos
