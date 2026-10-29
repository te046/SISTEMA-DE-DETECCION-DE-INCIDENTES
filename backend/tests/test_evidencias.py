from conftest import INGEST, alerta_base


def test_registro_edge_es_idempotente_y_exige_clave(client, auth):
    cuerpo = {"nombre": "Micrófono de la laptop", "tipo": "audio", "zona": "Zona 1"}
    assert client.post("/api/v1/dispositivos/registro", json=cuerpo).status_code == 401
    a = client.post("/api/v1/dispositivos/registro", json=cuerpo, headers=INGEST).json()
    b = client.post("/api/v1/dispositivos/registro", json=cuerpo, headers=INGEST).json()
    assert a["id"] == b["id"]
    otro_tipo = client.post("/api/v1/dispositivos/registro", json={**cuerpo, "tipo": "camara"}, headers=INGEST)
    assert otro_tipo.status_code == 409


def test_latido_informa_desconexion(client, auth):
    d = client.post("/api/v1/dispositivos/registro", json={"nombre": "Webcam prueba", "tipo": "camara", "zona": "Zona 1"}, headers=INGEST).json()
    client.post(f"/api/v1/dispositivos/{d['id']}/latido", json={"activo": False}, headers=INGEST)
    estado = {x["id"]: x for x in client.get("/api/v1/dispositivos", headers=auth).json()}
    assert estado[d["id"]]["activo"] == 0
    client.post(f"/api/v1/dispositivos/{d['id']}/latido", headers=INGEST)          # sin cuerpo: sigue conectado
    estado = {x["id"]: x for x in client.get("/api/v1/dispositivos", headers=auth).json()}
    assert estado[d["id"]]["activo"] == 1 and estado[d["id"]]["ultimo_latido"]


def test_subir_y_ver_evidencia_con_sesion(client, auth):
    r = client.post("/api/v1/evidencias", files={"archivo": ("clip.wav", b"RIFF....WAVE", "audio/wav")}, headers=INGEST)
    assert r.status_code == 201
    url = r.json()["url"]
    assert client.get(url).status_code == 401                                     # datos sensibles: requiere sesión
    v = client.get(url, headers=auth)
    assert v.status_code == 200 and v.content == b"RIFF....WAVE" and v.headers["content-type"].startswith("audio/wav")
    a = client.post("/api/v1/alertas", json=alerta_base(evidencia_audio=url), headers=INGEST).json()
    assert a["evidencia_audio"] == url


def test_evidencia_rechaza_tipos_y_nombres_raros(client, auth):
    assert client.post("/api/v1/evidencias", files={"archivo": ("x.exe", b"MZ", "application/octet-stream")}, headers=INGEST).status_code == 415
    assert client.post("/api/v1/evidencias", files={"archivo": ("x.wav", b"", "audio/wav")}, headers=INGEST).status_code == 422
    assert client.post("/api/v1/evidencias", files={"archivo": ("x.wav", b"1", "audio/wav")}).status_code == 401
    assert client.get("/api/v1/evidencias/..%2F.secret_key", headers=auth).status_code == 404
    assert client.get("/api/v1/evidencias/" + "0" * 32 + ".wav", headers=auth).status_code == 404
