"""Buscar dispositivos, conectar fuentes y direcciones de cámaras IP (cifrado y enmascarado)."""
import json

import pytest

from conftest import INGEST

URL_SECRETA = "rtsp://admin:Sup3rClave@192.168.1.20:554/stream1?pwd=otra"


def _login(client, usuario, clave):
    r = client.post("/api/v1/auth/token", json={"usuario": usuario, "clave": clave})
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture()
def admin(client):
    return _login(client, "admin", "Prueba-Adm-1")


INVENTARIO = {
    "microfonos": [
        {"clave": "audio:microphone array (intel smart", "nombre": "Microphone Array (Intel Smart Sound)", "utilizable": True},
        {"clave": "audio:stereo mix (realtek hd audio", "nombre": "Stereo Mix (Realtek HD Audio)", "utilizable": False,
         "motivo": "Graba lo que suena en los parlantes, no el ambiente."},
        {"clave": "audio:auriculares bt hands-free", "nombre": "Auriculares BT (Hands-Free)", "bluetooth": True, "utilizable": True},
    ],
    "camaras": [],
}


def _sin_secretos(texto: str):
    assert "Sup3rClave" not in texto and "admin:" not in texto and "pwd=otra" not in texto


# ---------------------------------------------------------------- búsqueda
def test_buscar_responde_al_instante_y_el_edge_completa(client, admin):
    r = client.post("/api/v1/fuentes/buscar", headers=admin)
    assert r.status_code == 202 and r.json() == {"estado": "buscando"}
    assert client.get("/api/v1/fuentes", headers=admin).json()["buscando"] is True
    e = client.get("/api/v1/edge/estado", headers=INGEST).json()
    assert e["buscar"] is True
    assert client.post("/api/v1/edge/inventario", json=INVENTARIO, headers=INGEST).status_code == 200
    assert client.get("/api/v1/edge/estado", headers=INGEST).json()["buscar"] is False
    lista = client.get("/api/v1/fuentes", headers=admin).json()
    assert lista["buscando"] is False and lista["edge_activo"] is True and lista["camaras_locales"] == 0
    por_nombre = {f["nombre"]: f for f in lista["fuentes"]}
    assert por_nombre["Stereo Mix (Realtek HD Audio)"]["estado"] == "no_sirve"
    assert por_nombre["Auriculares BT (Hands-Free)"]["bluetooth"] is True
    assert por_nombre["Microphone Array (Intel Smart Sound)"]["estado"] == "disponible"


def test_listar_y_buscar_exigen_sesion(client):
    assert client.get("/api/v1/fuentes").status_code == 401
    assert client.post("/api/v1/fuentes/buscar").status_code == 401
    assert client.get("/api/v1/edge/estado").status_code == 401           # el edge necesita su clave


# ---------------------------------------------------------------- conexión local
def test_conectar_local_y_el_edge_la_ve(client, admin):
    client.post("/api/v1/edge/inventario", json=INVENTARIO, headers=INGEST)
    r = client.post("/api/v1/fuentes/locales", json={"clave": "audio:microphone array (intel smart", "zona": "Zona 1"}, headers=admin)
    assert r.status_code == 201 and r.json()["estado"] == "conectada"
    fuentes_edge = client.get("/api/v1/edge/estado", headers=INGEST).json()["fuentes"]
    assert any(f["clave"] == "audio:microphone array (intel smart" for f in fuentes_edge)
    fid = r.json()["id"]
    assert client.post(f"/api/v1/fuentes/{fid}/desconectar", headers=admin).json()["estado"] == "disponible"
    assert all(f["id"] != fid for f in client.get("/api/v1/edge/estado", headers=INGEST).json()["fuentes"])


def test_no_se_conecta_lo_que_no_sirve_ni_lo_inexistente(client, admin):
    client.post("/api/v1/edge/inventario", json=INVENTARIO, headers=INGEST)
    assert client.post("/api/v1/fuentes/locales", json={"clave": "audio:stereo mix (realtek hd audio", "zona": "Zona 1"}, headers=admin).status_code == 422
    assert client.post("/api/v1/fuentes/locales", json={"clave": "camara:local:9", "zona": "Zona 1"}, headers=admin).status_code == 404


def test_vigilante_ve_pero_no_conecta_ni_agrega(client):
    from app import db, security                       # vigilante propio: vigilante.1 queda bloqueado por otra prueba
    with db.tx() as con:
        con.execute("INSERT OR IGNORE INTO usuarios(usuario,nombre,rol,pass_hash) VALUES (?,?,?,?)",
                    ("vigilante.fuentes", "Vigilante F", "vigilante", security.hash_password("Prueba-VigF-1")))
    vig = _login(client, "vigilante.fuentes", "Prueba-VigF-1")
    lista = client.get("/api/v1/fuentes", headers=vig)
    assert lista.status_code == 200 and lista.json()["puede_cambiar"] is False
    assert client.post("/api/v1/fuentes/red", json={"nombre": "Cam vig", "clase": "ip", "direccion": "rtsp://10.0.0.5/s", "zona": "Zona 1"}, headers=vig).status_code == 403
    assert client.post("/api/v1/fuentes/locales", json={"clave": "x", "zona": "Zona 1"}, headers=vig).status_code == 403
    resp = _login(client, "responsable.vigilancia", "Prueba-Resp-1")      # el responsable sí puede
    f = client.post("/api/v1/fuentes/red", json={"nombre": "Cam resp", "clase": "ip", "direccion": "rtsp://10.0.0.5/s", "zona": "Zona 1"}, headers=resp)
    assert f.status_code == 201
    assert client.post(f"/api/v1/fuentes/{f.json()['id']}/conectar", headers=vig).status_code == 403


def test_error_del_edge_se_muestra_enmascarado(client, admin):
    f = client.post("/api/v1/fuentes/red", json={"nombre": "Cam error", "clase": "ip", "direccion": URL_SECRETA, "zona": "Zona 2"}, headers=admin).json()
    client.post(f"/api/v1/edge/fuentes/{f['id']}/estado", json={"ok": False, "error": f"no abre {URL_SECRETA}"}, headers=INGEST)
    v = next(x for x in client.get("/api/v1/fuentes", headers=admin).json()["fuentes"] if x["id"] == f["id"])
    assert v["estado"] == "error" and "192.168.1.20" in v["motivo"]
    _sin_secretos(v["motivo"])


# ---------------------------------------------------------------- cámaras IP y teléfono
@pytest.mark.parametrize("mala", ["ftp://u:s3creto@10.0.0.1/x", "file:///C:/s3creto", "javascript:alert('s3creto')", "rtsp://u:s3creto@",
                                  "rtsp://u:s3creto@10.0.0.1:abc/s", "rtsp://10.0.0.1/s3creto con espacio"])
def test_direccion_invalida_se_rechaza_sin_eco(client, admin, mala):
    r = client.post("/api/v1/fuentes/red", json={"nombre": "X", "clase": "ip", "direccion": mala, "zona": "Zona 1"}, headers=admin)
    assert r.status_code == 422 and "s3creto" not in r.text                  # el error nunca repite la dirección


def test_agregar_ip_no_conecta_ni_expone_credenciales(client, admin):
    r = client.post("/api/v1/fuentes/red", json={"nombre": "Cámara pasillo", "clase": "ip", "direccion": URL_SECRETA, "zona": "Zona 1"}, headers=admin)
    assert r.status_code == 201
    f = r.json()
    assert f["conectada"] is False and f["estado"] == "disponible"            # se guarda, pero NO se conecta
    assert f["direccion"] == "rtsp://***@192.168.1.20:554/stream1?***"
    _sin_secretos(r.text)
    _sin_secretos(client.get("/api/v1/fuentes", headers=admin).text)
    _sin_secretos(client.get("/api/v1/edge/estado", headers=INGEST).text)   # el estado del edge tampoco la lleva


def test_credenciales_cifradas_en_la_base_y_auditoria(client, admin):
    from app import db
    client.post("/api/v1/fuentes/red", json={"nombre": "Teléfono puerta", "clase": "telefono", "direccion": URL_SECRETA, "zona": "Zona 3"}, headers=admin)
    with db.tx() as con:
        volcado = json.dumps([dict(r) for r in con.execute("SELECT * FROM fuentes")] + [dict(r) for r in con.execute("SELECT * FROM auditoria")])
    _sin_secretos(volcado)
    assert "192.168.1.20" in volcado                                         # la parte visible sí queda


def test_direccion_completa_solo_con_clave_de_ingesta(client, admin):
    f = client.post("/api/v1/fuentes/red", json={"nombre": "Cam edge", "clase": "ip", "direccion": URL_SECRETA, "zona": "Zona 1"}, headers=admin).json()
    ruta = f"/api/v1/edge/fuentes/{f['id']}/direccion"
    assert client.get(ruta).status_code == 401
    assert client.get(ruta, headers=admin).status_code == 401                # la sesión del panel NO sirve
    assert client.get(ruta, headers={**admin, "X-Api-Key": "incorrecta"}).status_code == 401
    r = client.get(ruta, headers=INGEST)
    assert r.status_code == 200 and r.json()["direccion"] == URL_SECRETA


def test_conectar_ip_al_pulsar_conectar(client, admin):
    f = client.post("/api/v1/fuentes/red", json={"nombre": "Cam conectar", "clase": "ip", "direccion": "http://10.0.0.9:8080/video", "zona": "Zona 1"}, headers=admin).json()
    assert all(x["id"] != f["id"] for x in client.get("/api/v1/edge/estado", headers=INGEST).json()["fuentes"])
    assert client.post(f"/api/v1/fuentes/{f['id']}/conectar", headers=admin).json()["estado"] == "conectada"
    edge = next(x for x in client.get("/api/v1/edge/estado", headers=INGEST).json()["fuentes"] if x["id"] == f["id"])
    assert edge["red"] is True and "direccion" not in edge


def test_si_cambia_secret_key_avisa_y_no_se_cae(client, admin):
    from app import cifrado, db
    f = client.post("/api/v1/fuentes/red", json={"nombre": "Cam clave vieja", "clase": "ip", "direccion": URL_SECRETA, "zona": "Zona 1"}, headers=admin).json()
    with db.tx() as con:                                                     # simula una dirección cifrada con otra SECRET_KEY
        con.execute("UPDATE fuentes SET uri_cifrada=? WHERE id=?", (cifrado.cifrar(URL_SECRETA, secreto="otra-clave-anterior"), f["id"]))
    lista = client.get("/api/v1/fuentes", headers=admin)
    assert lista.status_code == 200
    v = next(x for x in lista.json()["fuentes"] if x["id"] == f["id"])
    assert v["estado"] == "error" and "SECRET_KEY" in v["motivo"]
    c = client.post(f"/api/v1/fuentes/{f['id']}/conectar", headers=admin)
    assert c.status_code == 409 and "Vuelva a agregar" in c.json()["detail"]["mensaje"]
    d = client.get(f"/api/v1/edge/fuentes/{f['id']}/direccion", headers=INGEST)
    assert d.status_code == 409
    _sin_secretos(lista.text + c.text + d.text)


def test_enmascarado_de_textos():
    from app.urls import enmascarar_texto, enmascarar_url
    assert enmascarar_url("rtsp://u:p@[fe80::1]:554/s") == "rtsp://***@[fe80::1]:554/s"
    assert enmascarar_url("http://10.0.0.1:8080/video") == "http://10.0.0.1:8080/video"
    t = enmascarar_texto(f"Error abriendo {URL_SECRETA}: 401")
    assert "192.168.1.20" in t
    _sin_secretos(t)


def test_error_de_validacion_no_repite_la_direccion(client, admin):
    larga = "rtsp://admin:Sup3rClave@10.0.0.1/" + "x" * 700                 # supera max_length: lo rechaza Pydantic
    r = client.post("/api/v1/fuentes/red", json={"nombre": "Larga", "clase": "ip", "direccion": larga, "zona": "Zona 1"}, headers=admin)
    assert r.status_code == 422 and "direccion" in r.json()["detail"]["mensaje"]
    _sin_secretos(r.text)


def test_usuario_y_clave_en_campos_aparte(client, admin):
    r = client.post("/api/v1/fuentes/red", json={"nombre": "Cam campos", "clase": "ip", "direccion": "rtsp://192.168.1.20:554/stream1",
                                                "usuario": "admin", "clave": "Sup3r:Cl@ve/x", "zona": "Zona 1"}, headers=admin)
    assert r.status_code == 201 and r.json()["direccion"] == "rtsp://***@192.168.1.20:554/stream1"
    _sin_secretos(r.text)
    d = client.get(f"/api/v1/edge/fuentes/{r.json()['id']}/direccion", headers=INGEST).json()["direccion"]
    assert d == "rtsp://admin:Sup3r%3ACl%40ve%2Fx@192.168.1.20:554/stream1"      # caracteres especiales codificados
    doble = client.post("/api/v1/fuentes/red", json={"nombre": "Cam doble", "clase": "ip", "direccion": URL_SECRETA,
                                                    "usuario": "otro", "zona": "Zona 1"}, headers=admin)
    assert doble.status_code == 422
    _sin_secretos(doble.text)
