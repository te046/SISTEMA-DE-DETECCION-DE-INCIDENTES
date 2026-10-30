"""Descubrimiento y conexión de fuentes (cámaras y micrófonos) desde el panel.

El hardware está en el equipo del edge, no en el servidor (etapa 5). Por eso:
  panel  → POST /fuentes/buscar         (la API anota el pedido y responde al instante: «Buscando…»)
  edge   → GET  /edge/estado            (cada 2 s: ve el pedido y qué fuentes deben estar conectadas)
  edge   → POST /edge/inventario        (sube lo que encontró)
  panel  → GET  /fuentes                (lista: disponible, conectada, error, no sirve)
Las direcciones de cámaras IP se guardan cifradas; el panel solo ve la versión enmascarada y la
completa solo la obtiene el edge con la clave de ingesta (GET /edge/fuentes/{id}/direccion).
"""
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from . import cifrado, db
from .urls import DireccionInvalida, con_credenciales, enmascarar_texto, enmascarar_url, validar_url

EDGE_ACTIVO_S = 10          # si el edge no consultó en este lapso, se considera cerrado
BUSQUEDA_MAX_S = 15         # tras esto, el panel deja de mostrar «Buscando…» y explica qué pasó


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _edad_s(iso: str | None) -> float | None:
    return (datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds() if iso else None


def _inventario(con) -> dict:
    fila = con.execute("SELECT * FROM inventario_edge WHERE id=1").fetchone()
    if not fila:
        con.execute("INSERT INTO inventario_edge(id) VALUES (1)")
        fila = con.execute("SELECT * FROM inventario_edge WHERE id=1").fetchone()
    return dict(fila)


def _auditar(con, usuario: str, accion: str, detalle: str):
    con.execute("INSERT INTO auditoria(momento,usuario,accion,detalle) VALUES (?,?,?,?)",
                (ahora_iso(), usuario, accion, enmascarar_texto(detalle)))


def _requiere_gestor(u: dict, error):
    if u["rol"] == "vigilante":
        error(403, "Su rol no puede conectar ni agregar dispositivos.",
                      "Pida a un responsable de vigilancia o a un administrador que lo haga.")


def _estado_fuente(f: dict) -> tuple[str, str | None]:
    """'conectada' | 'disponible' | 'error' y el motivo (sin datos sensibles)."""
    if f["uri_cifrada"]:
        try:
            cifrado.descifrar(f["uri_cifrada"])
        except cifrado.NoSePuedeDescifrar as e:
            return "error", str(e)
    if f["error"]:
        return "error", f["error"]
    return ("conectada" if f["conectada"] else "disponible"), None


def _vista_fuente(f: dict) -> dict:
    estado, motivo = _estado_fuente(f)
    return {"id": f["id"], "clave": f["clave"], "tipo": f["tipo"], "clase": f["clase"], "nombre": f["nombre"],
            "zona": f["zona"], "direccion": f["uri_visible"], "conectada": bool(f["conectada"]),
            "estado": estado, "motivo": motivo, "bluetooth": False, "utilizable": True}


def registrar(app, usuario_actual, requiere_ingesta, error):
    """Registra las rutas con las dependencias de main.py (sesión del panel y clave de ingesta)."""
    r = APIRouter()

    # ------------------------------------------------------------ panel (sesión)

    @r.get("/api/v1/fuentes")
    def listar(u=Depends(usuario_actual)):
        with db.tx() as con:
            inv = _inventario(con)
            registradas = [dict(x) for x in con.execute("SELECT * FROM fuentes ORDER BY tipo, nombre").fetchall()]
        datos = json.loads(inv["datos"] or "{}")
        por_clave = {f["clave"]: f for f in registradas}
        lista = []
        for item in datos.get("camaras", []) + datos.get("microfonos", []):       # lo que el edge encontró
            f = por_clave.pop(item["clave"], None)
            v = _vista_fuente(f) if f else {"id": None, "clave": item["clave"], "tipo": item["tipo"], "clase": "local",
                                            "nombre": item["nombre"], "zona": None, "direccion": None, "conectada": False,
                                            "estado": "disponible", "motivo": None}
            v.update(bluetooth=bool(item.get("bluetooth")), utilizable=bool(item.get("utilizable", True)))
            if not v["utilizable"]:
                v.update(estado="no_sirve", motivo=item.get("motivo"))
            lista.append(v)
        for f in por_clave.values():                   # manuales (IP/teléfono) y locales que ya no aparecen
            v = _vista_fuente(f)
            if f["clase"] == "local" and datos and v["estado"] != "error":
                v.update(estado="error", motivo="No apareció en la última búsqueda. Revise que esté conectado.")
            lista.append(v)
        visto = _edad_s(inv["edge_visto_en"])
        pedida, hecha = inv["busqueda_pedida_en"], inv["actualizado_en"]
        buscando = bool(pedida) and (not hecha or hecha < pedida) and (_edad_s(pedida) or 0) < BUSQUEDA_MAX_S
        return {
            "fuentes": lista,
            "edge_activo": visto is not None and visto < EDGE_ACTIVO_S,
            "buscando": buscando,
            "busqueda_sin_respuesta": bool(pedida) and (not hecha or hecha < pedida) and not buscando,
            "ultima_busqueda": hecha,
            "camaras_locales": len(datos.get("camaras", [])),
            "puede_cambiar": u["rol"] != "vigilante",
        }

    @r.post("/api/v1/fuentes/buscar", status_code=202)
    def buscar(u=Depends(usuario_actual)):
        """Responde al instante; el edge hace la búsqueda en su próxima consulta (≤ 2 s)."""
        with db.tx() as con:
            _inventario(con)
            con.execute("UPDATE inventario_edge SET busqueda_pedida_en=? WHERE id=1", (ahora_iso(),))
            _auditar(con, u["sub"], "buscar_dispositivos", "")
        return {"estado": "buscando"}

    class FuenteLocal(BaseModel):
        clave: str = Field(min_length=1, max_length=200)
        zona: str = Field(min_length=1, max_length=80)

    @r.post("/api/v1/fuentes/locales", status_code=201)
    def agregar_local(f: FuenteLocal, u=Depends(usuario_actual)):
        """Registra y conecta una fuente local encontrada por el edge (botón «Conectar»)."""
        _requiere_gestor(u, error)
        with db.tx() as con:
            datos = json.loads(_inventario(con)["datos"] or "{}")
            item = next((x for x in datos.get("camaras", []) + datos.get("microfonos", []) if x["clave"] == f.clave), None)
            if not item:
                error(404, "Ese dispositivo ya no aparece en la búsqueda.", "Pulse «Buscar» de nuevo.")
            if not item.get("utilizable", True):
                error(422, "Ese dispositivo no sirve para vigilancia.", item.get("motivo") or "Elija otro de la lista.")
            existente = con.execute("SELECT * FROM fuentes WHERE clave=?", (f.clave,)).fetchone()
            if existente:
                con.execute("UPDATE fuentes SET conectada=1, zona=?, error=NULL, actualizado_en=? WHERE id=?",
                            (f.zona, ahora_iso(), existente["id"]))
                fid = existente["id"]
            else:
                nombre = item["nombre"]
                if con.execute("SELECT 1 FROM fuentes WHERE nombre=?", (nombre,)).fetchone():
                    nombre = f"{nombre} ({f.clave[-6:]})"
                fid = con.execute("INSERT INTO fuentes(clave,tipo,clase,nombre,zona,conectada,actualizado_en) VALUES (?,?,?,?,?,1,?)",
                                  (f.clave, item["tipo"], "local", nombre, f.zona, ahora_iso())).lastrowid
            _auditar(con, u["sub"], "fuente_conectada", item["nombre"])
            return _vista_fuente(dict(con.execute("SELECT * FROM fuentes WHERE id=?", (fid,)).fetchone()))

    class FuenteRed(BaseModel):
        nombre: str = Field(min_length=1, max_length=80)
        clase: Literal["ip", "telefono"]
        direccion: str = Field(min_length=1, max_length=600)
        usuario: str | None = Field(default=None, max_length=120)      # campos aparte: la clave no se ve al escribirla
        clave: str | None = Field(default=None, max_length=200)
        zona: str = Field(min_length=1, max_length=80)

    @r.post("/api/v1/fuentes/red", status_code=201)
    def agregar_red(f: FuenteRed, u=Depends(usuario_actual)):
        """Guarda una cámara IP o un teléfono. NO se conecta al guardar: solo al pulsar «Conectar»."""
        _requiere_gestor(u, error)
        try:
            url = con_credenciales(validar_url(f.direccion), f.usuario, f.clave)
        except DireccionInvalida as e:
            error(422, str(e), "Ejemplos: rtsp://192.168.1.20:554/stream o http://192.168.1.30:8080/video (teléfono).")
        with db.tx() as con:
            if con.execute("SELECT 1 FROM fuentes WHERE nombre=?", (f.nombre.strip(),)).fetchone():
                error(409, "Ya hay un dispositivo con ese nombre.", "Use otro nombre, por ejemplo «Cámara pasillo 2».")
            fid = con.execute(
                "INSERT INTO fuentes(clave,tipo,clase,nombre,zona,uri_cifrada,uri_visible,conectada,actualizado_en) VALUES (?,?,?,?,?,?,?,0,?)",
                (f"red:{uuid.uuid4().hex}", "camara", f.clase, f.nombre.strip(), f.zona, cifrado.cifrar(url), enmascarar_url(url), ahora_iso())).lastrowid
            _auditar(con, u["sub"], "fuente_agregada", f"{f.nombre.strip()} · {enmascarar_url(url)}")
            return _vista_fuente(dict(con.execute("SELECT * FROM fuentes WHERE id=?", (fid,)).fetchone()))

    def _cambiar(fid: int, conectada: bool, u: dict):
        _requiere_gestor(u, error)
        with db.tx() as con:
            f = con.execute("SELECT * FROM fuentes WHERE id=?", (fid,)).fetchone()
            if not f:
                error(404, "No existe ese dispositivo.", "Pulse «Buscar» para actualizar la lista.")
            if conectada and f["uri_cifrada"]:
                try:
                    cifrado.descifrar(f["uri_cifrada"])
                except cifrado.NoSePuedeDescifrar as e:
                    error(409, str(e), "Agregue la cámara de nuevo con su dirección.")
            con.execute("UPDATE fuentes SET conectada=?, error=NULL, actualizado_en=? WHERE id=?", (int(conectada), ahora_iso(), fid))
            if not conectada:                          # el panel deja de esperar latidos de esa fuente
                con.execute("UPDATE dispositivos SET activo=0 WHERE nombre=?", (f["nombre"],))
            _auditar(con, u["sub"], "fuente_conectada" if conectada else "fuente_desconectada", f["nombre"])
            return _vista_fuente(dict(con.execute("SELECT * FROM fuentes WHERE id=?", (fid,)).fetchone()))

    @r.post("/api/v1/fuentes/{fid}/conectar")
    def conectar(fid: int, u=Depends(usuario_actual)):
        return _cambiar(fid, True, u)

    @r.post("/api/v1/fuentes/{fid}/desconectar")
    def desconectar(fid: int, u=Depends(usuario_actual)):
        return _cambiar(fid, False, u)

    # ------------------------------------------------------------ edge (clave de ingesta)
    @r.get("/api/v1/edge/estado", dependencies=[Depends(requiere_ingesta)])
    def estado_edge():
        """Lo consulta el edge cada 2 s. No incluye direcciones: esas se piden aparte."""
        with db.tx() as con:
            inv = _inventario(con)
            con.execute("UPDATE inventario_edge SET edge_visto_en=? WHERE id=1", (ahora_iso(),))
            conectadas = [dict(x) for x in con.execute("SELECT * FROM fuentes WHERE conectada=1").fetchall()]
        pedida, hecha = inv["busqueda_pedida_en"], inv["actualizado_en"]
        return {"buscar": bool(pedida) and (not hecha or hecha < pedida),
                "fuentes": [{"id": f["id"], "clave": f["clave"], "tipo": f["tipo"], "clase": f["clase"], "nombre": f["nombre"],
                             "zona": f["zona"], "red": bool(f["uri_cifrada"]), "actualizado_en": f["actualizado_en"]}
                            for f in conectadas]}

    class Inventario(BaseModel):
        microfonos: list[dict] = []
        camaras: list[dict] = []

    @r.post("/api/v1/edge/inventario", dependencies=[Depends(requiere_ingesta)])
    def subir_inventario(inv: Inventario):
        limpio = {"microfonos": [], "camaras": []}
        for campo, tipo in (("microfonos", "audio"), ("camaras", "camara")):
            for x in getattr(inv, campo)[:100]:
                if not isinstance(x.get("clave"), str) or not isinstance(x.get("nombre"), str):
                    continue
                limpio[campo].append({"clave": x["clave"][:200], "tipo": tipo, "nombre": enmascarar_texto(x["nombre"])[:120],
                                      "bluetooth": bool(x.get("bluetooth")), "utilizable": bool(x.get("utilizable", True)),
                                      "motivo": enmascarar_texto(x.get("motivo") or "")[:200] or None})
        with db.tx() as con:
            _inventario(con)
            con.execute("UPDATE inventario_edge SET datos=?, actualizado_en=? WHERE id=1", (json.dumps(limpio, ensure_ascii=False), ahora_iso()))
        return {"ok": True}

    @r.get("/api/v1/edge/fuentes/{fid}/direccion", dependencies=[Depends(requiere_ingesta)])
    def direccion(fid: int):
        """Dirección completa (con usuario y clave) SOLO para el edge. Nunca acepta la sesión del panel."""
        with db.tx() as con:
            f = con.execute("SELECT * FROM fuentes WHERE id=?", (fid,)).fetchone()
        if not f or not f["uri_cifrada"]:
            error(404, "Esa fuente no tiene dirección de red.", "Revise el id de la fuente.")
        try:
            return {"direccion": cifrado.descifrar(f["uri_cifrada"])}
        except cifrado.NoSePuedeDescifrar as e:
            error(409, str(e), "Agregue la cámara de nuevo desde el panel.")

    class EstadoFuente(BaseModel):
        ok: bool
        error: str | None = Field(default=None, max_length=500)

    @r.post("/api/v1/edge/fuentes/{fid}/estado", dependencies=[Depends(requiere_ingesta)])
    def informar_estado(fid: int, e: EstadoFuente):
        with db.tx() as con:
            con.execute("UPDATE fuentes SET error=? WHERE id=?",
                        (None if e.ok else enmascarar_texto(e.error or "La fuente no responde.")[:300], fid))
        return {"ok": True}

    app.include_router(r)
