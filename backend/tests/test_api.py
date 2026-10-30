from datetime import datetime, timedelta, timezone
from conftest import INGEST, alerta_base


def test_login_correcto_e_incorrecto(client):
    assert client.post("/api/v1/auth/token", json={"usuario": "admin", "clave": "mala"}).status_code == 401
    r = client.post("/api/v1/auth/token", json={"usuario": "admin", "clave": "Prueba-Adm-1"})
    assert r.status_code == 200 and r.json()["usuario"]["rol"] == "admin"


def test_bloqueo_tras_5_intentos(client):
    for _ in range(5):
        assert client.post("/api/v1/auth/token", json={"usuario": "vigilante.1", "clave": "x"}).status_code == 401
    r = client.post("/api/v1/auth/token", json={"usuario": "vigilante.1", "clave": "Prueba-Vig-1"})
    assert r.status_code == 423 and "solucion" in r.json()["detail"]


def test_endpoints_exigen_sesion(client):
    assert client.get("/api/v1/alertas").status_code == 401
    assert client.get("/api/v1/incidentes").status_code == 401


def test_ingesta_exige_clave_y_rn01(client):
    assert client.post("/api/v1/alertas", json=alerta_base()).status_code == 401
    r = client.post("/api/v1/alertas", json=alerta_base(modalidades=[]), headers=INGEST)
    assert r.status_code == 422                       # RN-01: sin clasificación de modelo no hay alerta


def test_alertas_ordenadas_por_prioridad(client, auth):
    client.post("/api/v1/alertas", json=alerta_base(prioridad=3, tipo="Baja"), headers=INGEST)
    client.post("/api/v1/alertas", json=alerta_base(prioridad=1, tipo="Alta"), headers=INGEST)
    lista = client.get("/api/v1/alertas?estado=pendiente", headers=auth).json()
    pr = [a["prioridad"] for a in lista]
    assert pr == sorted(pr) and pr[0] == 1


def test_confirmar_registra_incidente_y_deshacer(client, auth):
    a = client.post("/api/v1/alertas", json=alerta_base(tipo="Choque"), headers=INGEST).json()
    r = client.post(f"/api/v1/alertas/{a['id']}/resolucion", json={"accion": "confirmar", "clics": 1}, headers=auth)
    assert r.status_code == 200 and r.json()["estado"] == "confirmada"
    inc = client.get("/api/v1/incidentes", headers=auth).json()
    assert any(i["alerta"] == a["codigo"] for i in inc)                      # RN-02
    assert client.post(f"/api/v1/alertas/{a['id']}/resolucion", json={"accion": "descartar"}, headers=auth).status_code == 409
    d = client.post(f"/api/v1/alertas/{a['id']}/deshacer", headers=auth)
    assert d.status_code == 200 and d.json()["estado"] == "pendiente"
    assert not any(i["alerta"] == a["codigo"] for i in client.get("/api/v1/incidentes", headers=auth).json())


def test_indicadores_ttd_tta_y_tasas(client, auth):
    antes = client.get("/api/v1/indicadores?origen=simulado", headers=auth).json()
    det = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()
    a = client.post("/api/v1/alertas", json=alerta_base(detectado_en=det), headers=INGEST).json()
    client.post(f"/api/v1/alertas/{a['id']}/resolucion", json={"accion": "descartar", "clics": 2}, headers=auth)
    ind = client.get("/api/v1/indicadores?origen=simulado", headers=auth).json()
    assert ind["I1_ttd_s"] is not None and ind["I1_ttd_s"] >= 0
    assert ind["descartadas"] == antes["descartadas"] + 1
    assert 0 <= ind["I4_falsas_alarmas_pct"] <= 100


def test_dispositivos_y_roles(client, auth):
    disp = client.get("/api/v1/dispositivos", headers=auth).json()
    assert len(disp) == 4
    r = client.patch(f"/api/v1/dispositivos/{disp[0]['id']}", json={"activo": False}, headers=auth)
    assert r.status_code == 200 and r.json()["activo"] == 0
    client.patch(f"/api/v1/dispositivos/{disp[0]['id']}", json={"activo": True}, headers=auth)


def test_rn01_y_rn02_siguen_vigentes_con_la_regla_nueva(client, auth):
    sin_modelo = client.post("/api/v1/alertas", json=alerta_base(modalidades=[]), headers=INGEST)
    assert sin_modelo.status_code == 422                                        # RN-01
    mm = [{"modalidad": "audio", "clase": "voces elevadas", "confianza": 0.6}, {"modalidad": "video", "clase": "posible agresión", "confianza": 0.55}]
    a = client.post("/api/v1/alertas", json=alerta_base(prioridad=1, tipo="Voces elevadas", modalidades=mm), headers=INGEST).json()
    client.post(f"/api/v1/alertas/{a['id']}/resolucion", json={"accion": "confirmar", "clics": 1}, headers=auth)
    assert any(i["alerta"] == a["codigo"] for i in client.get("/api/v1/incidentes", headers=auth).json())   # RN-02
