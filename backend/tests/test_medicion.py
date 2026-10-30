"""Etiquetado (verdad de campo), precisión/recall/F1 y exportación a CSV."""
import csv
import io
from datetime import datetime, timedelta, timezone

import pytest

from app.medicion import emparejado, metricas
from conftest import INGEST, alerta_base

T0 = datetime(2026, 10, 30, 15, 0, tzinfo=timezone.utc)
iso = lambda dt: dt.isoformat()


# ---------------------------------------------------------------- lógica pura
def _a(seg, zona="Zona 1", verdad=None):
    return {"zona": zona, "detectado_en": iso(T0 + timedelta(seconds=seg)), "verdad": verdad}


def _e(ini, fin, zona="Zona 1"):
    return {"zona": zona, "inicio": iso(T0 + timedelta(seconds=ini)), "fin": iso(T0 + timedelta(seconds=fin))}


def test_regla_de_emparejamiento():
    e = _e(35, 50)
    assert emparejado(e, _a(34)) and emparejado(e, _a(55))          # inicio − 1 s … fin + 5 s
    assert not emparejado(e, _a(33.9)) and not emparejado(e, _a(55.1))
    assert not emparejado(e, _a(40, zona="Zona 2"))


def test_metricas_con_y_sin_datos():
    vacio = metricas([], [])
    assert vacio["precision_etiquetada_pct"] is None and vacio["recall_pct"] is None and vacio["f1_pct"] is None
    alertas = [_a(40, verdad="real"), _a(70, verdad="real"), _a(5, verdad="falsa"), _a(200)]
    eventos = [_e(35, 50), _e(60, 75), _e(100, 110)]                  # el tercero no se detectó
    m = metricas(alertas, eventos)
    assert (m["alertas_etiquetadas"], m["alertas_sin_etiqueta"], m["eventos_detectados"]) == (3, 1, 2)
    assert m["precision_etiquetada_pct"] == pytest.approx(66.7) and m["recall_pct"] == pytest.approx(66.7)
    assert m["f1_pct"] == pytest.approx(66.7)
    assert metricas([_a(5, verdad="falsa")], [_e(35, 50)])["f1_pct"] == 0.0


# ---------------------------------------------------------------- API
def _vigilante(client):
    from app import db, security
    with db.tx() as con:
        con.execute("INSERT OR IGNORE INTO usuarios(usuario,nombre,rol,pass_hash) VALUES (?,?,?,?)",
                    ("vigilante.medicion", "Vigilante M", "vigilante", security.hash_password("Prueba-VigM-1")))
    r = client.post("/api/v1/auth/token", json={"usuario": "vigilante.medicion", "clave": "Prueba-VigM-1"})
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_etiquetar_alerta_y_roles(client, auth):
    a = client.post("/api/v1/alertas", json=alerta_base(), headers=INGEST).json()
    r = client.put(f"/api/v1/alertas/{a['id']}/verdad", json={"verdad": "real"}, headers=auth)
    assert r.status_code == 200 and r.json()["verdad"] == "real" and r.json()["etiquetado_por"] == "responsable.vigilancia"
    assert client.put(f"/api/v1/alertas/{a['id']}/verdad", json={"verdad": None}, headers=auth).json()["verdad"] is None
    assert client.put(f"/api/v1/alertas/{a['id']}/verdad", json={"verdad": "quizas"}, headers=auth).status_code == 422
    assert client.put(f"/api/v1/alertas/{a['id']}/verdad", json={"verdad": "real"}, headers=_vigilante(client)).status_code == 403
    assert client.put("/api/v1/alertas/999999/verdad", json={"verdad": "real"}, headers=auth).status_code == 404


def test_eventos_reales_y_metricas_por_api(client, auth):
    lima = timezone(timedelta(hours=-5))
    ini = datetime.now(lima) - timedelta(seconds=20)
    e = client.post("/api/v1/eventos-reales", json={"inicio": ini.isoformat(), "fin": (ini + timedelta(seconds=10)).isoformat(),
                                                    "zona": "Zona 7", "tipo": "posible agresión", "nota": "prueba_vivo 35-50 s"}, headers=auth)
    assert e.status_code == 201 and e.json()["inicio"].endswith("+00:00")            # se guarda en UTC
    det = (ini + timedelta(seconds=3)).isoformat()
    a = client.post("/api/v1/alertas", json=alerta_base(zona="Zona 7", detectado_en=det), headers=INGEST).json()
    client.put(f"/api/v1/alertas/{a['id']}/verdad", json={"verdad": "real"}, headers=auth)
    m = client.get("/api/v1/metricas", headers=auth).json()
    assert m["eventos_detectados"] >= 1 and m["recall_pct"] is not None and "misma zona" in m["regla_emparejamiento"]
    malo = {"inicio": ini.isoformat(), "fin": (ini - timedelta(seconds=1)).isoformat(), "zona": "Zona 7", "tipo": "grito"}
    assert client.post("/api/v1/eventos-reales", json=malo, headers=auth).status_code == 422
    sin_zona = {**malo, "inicio": "2026-10-30T10:00:00", "fin": "2026-10-30T10:00:05"}
    assert client.post("/api/v1/eventos-reales", json=sin_zona, headers=auth).status_code == 422
    assert client.post("/api/v1/eventos-reales", json={**malo, "fin": ini.isoformat(), "tipo": "inventado"}, headers=auth).status_code == 422
    assert client.post("/api/v1/eventos-reales", json={**malo, "fin": ini.isoformat()}, headers=_vigilante(client)).status_code == 403
    assert client.delete(f"/api/v1/eventos-reales/{e.json()['id']}", headers=auth).status_code == 204
    assert client.delete(f"/api/v1/eventos-reales/{e.json()['id']}", headers=auth).status_code == 404


def test_exportar_csv_alertas_y_eventos(client, auth):
    a = client.post("/api/v1/alertas", json=alerta_base(tipo="=HYPERLINK(\"x\")"), headers=INGEST).json()   # intento de fórmula
    client.post(f"/api/v1/alertas/{a['id']}/mostrada", headers=auth)
    assert client.get("/api/v1/exportar/alertas.csv").status_code == 401
    r = client.get("/api/v1/exportar/alertas.csv?origen=simulado", headers=auth)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"] and r.content.startswith(b"\xef\xbb\xbf")
    filas = list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
    fila = next(f for f in filas if f["codigo"] == a["codigo"])
    assert fila["tipo"].startswith("'=")                                              # neutralizada para Excel
    assert fila["I1_s"] and fila["origen"] == "simulado" and fila["modalidades"] == "audio"
    assert {"verdad", "I1_visible_s", "I2_s", "panel_activo"} <= set(filas[0])
    ev = client.get("/api/v1/exportar/eventos_reales.csv", headers=auth)
    assert ev.status_code == 200 and ev.content.decode("utf-8-sig").splitlines()[0] == "id,inicio,fin,zona,tipo,nota,registrado_por,detectado"
