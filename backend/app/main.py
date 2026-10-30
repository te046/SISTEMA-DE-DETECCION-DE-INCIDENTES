import json, re, uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import jwt as pyjwt

from . import config, db, fuentes, security

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(_app):
    db.init()
    yield


app = FastAPI(title="Vigilancia multimodal UDH · API", version="1.0.0", lifespan=lifespan)
bearer = HTTPBearer(auto_error=False)


TOLERANCIA_RELOJ_S = 2.0      # desfase admitido entre el reloj del edge y el del servidor


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def parse(s: str) -> datetime:
    return datetime.fromisoformat(s)




@app.exception_handler(RequestValidationError)
async def datos_invalidos(_req, exc: RequestValidationError):
    """Por defecto FastAPI repite lo recibido en el 422; aquí solo se nombran los campos, para no
    devolver nunca una dirección con usuario y clave."""
    campos = sorted({str(e["loc"][-1]) for e in exc.errors() if e.get("loc")})
    return JSONResponse(status_code=422, content={"detail": {
        "mensaje": "Hay datos que no son válidos" + (f": {', '.join(campos)}." if campos else "."),
        "solucion": "Revise esos campos e intente de nuevo."}})


def error(status: int, que_paso: str, como_resolver: str):
    """Errores que dicen qué pasó y cómo resolverlo (heurística H9)."""
    raise HTTPException(status, detail={"mensaje": que_paso, "solucion": como_resolver})


# ---------------------------------------------------------------- autenticación
class Credenciales(BaseModel):
    usuario: str = Field(min_length=1, max_length=64)
    clave: str = Field(min_length=1, max_length=128)


@app.post("/api/v1/auth/token")
def login(c: Credenciales):
    with db.tx() as con:
        u = con.execute("SELECT * FROM usuarios WHERE usuario = ?", (c.usuario.strip(),)).fetchone()
        mensaje = "Usuario o contraseña incorrectos."
        if u and u["bloqueado_hasta"] and parse(u["bloqueado_hasta"]) > ahora():
            error(423, "La cuenta está bloqueada por intentos fallidos.",
                  f"Espere {config.LOCK_MINUTES} minutos o pida el desbloqueo a la Oficina de Sistemas.")
        if not u or not security.verify_password(c.clave, u["pass_hash"]):
            if u:
                n = u["intentos"] + 1
                bloqueo = iso(ahora() + timedelta(minutes=config.LOCK_MINUTES)) if n >= config.MAX_FAILED_LOGINS else None
                con.execute("UPDATE usuarios SET intentos=?, bloqueado_hasta=? WHERE id=?", (0 if bloqueo else n, bloqueo, u["id"]))
                con.execute("INSERT INTO auditoria(momento,usuario,accion,detalle) VALUES (?,?,?,?)",
                            (iso(ahora()), u["usuario"], "login_fallido", f"intento {n}"))
            con.commit()
            error(401, mensaje, "Revise que el usuario y la contraseña estén bien escritos. Después de 5 intentos la cuenta se bloquea.")
        con.execute("UPDATE usuarios SET intentos=0, bloqueado_hasta=NULL WHERE id=?", (u["id"],))
        con.execute("INSERT INTO auditoria(momento,usuario,accion) VALUES (?,?,?)", (iso(ahora()), u["usuario"], "login"))
        tok, exp = security.make_token(u["usuario"], u["rol"], u["nombre"])
        return {"access_token": tok, "token_type": "bearer", "expires_in": exp,
                "usuario": {"usuario": u["usuario"], "nombre": u["nombre"], "rol": u["rol"]}}


def usuario_actual(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if not cred:
        error(401, "Falta iniciar sesión.", "Ingrese con su usuario y contraseña.")
    try:
        return security.read_token(cred.credentials)
    except pyjwt.ExpiredSignatureError:
        error(401, "Su sesión terminó.", "Vuelva a iniciar sesión.")
    except pyjwt.PyJWTError:
        error(401, "La sesión no es válida.", "Vuelva a iniciar sesión.")


def requiere_ingesta(x_api_key: str | None = Header(default=None)):
    import hmac
    if not x_api_key or not hmac.compare_digest(x_api_key, config.INGEST_KEY):
        error(401, "Clave del módulo de detección incorrecta.", "Envíe la clave de data/.ingest_key en el encabezado X-Api-Key.")


# ---------------------------------------------------------------- alertas
class Modalidad(BaseModel):
    modalidad: Literal["video", "audio"]
    clase: str = Field(min_length=1, max_length=80)
    confianza: float = Field(ge=0, le=1)


class AlertaNueva(BaseModel):
    tipo: str = Field(min_length=1, max_length=80)
    prioridad: Literal[1, 2, 3]
    dispositivos: str = Field(min_length=1, max_length=120)
    zona: str = Field(min_length=1, max_length=80)
    confianza: float = Field(ge=0, le=1)
    modalidades: list[Modalidad]                   # RN-01: al menos un modelo clasificó el evento
    detectado_en: datetime | None = None
    origen: Literal["edge", "simulado"] = "edge"
    evidencia_video: str | None = None
    evidencia_audio: str | None = None


def fila_alerta(r) -> dict:
    d = dict(r)
    d["modalidades"] = json.loads(d["modalidades"])
    return d


@app.post("/api/v1/alertas", status_code=201, dependencies=[Depends(requiere_ingesta)])
def crear_alerta(a: AlertaNueva):
    if not a.modalidades:
        error(422, "La alerta no trae ninguna clasificación de modelo.", "Envíe al menos una modalidad (video o audio) con su clase y confianza (RN-01).")
    gen = ahora()
    det = a.detectado_en or gen
    if det.tzinfo is None:                            # suponer una zona corrompería I1 (Perú está a −5 h de UTC)
        error(422, "La hora del evento (detectado_en) no indica su zona horaria.",
              "Envíela en UTC con zona, por ejemplo 2026-10-30T05:23:43.120+00:00.")
    if (det - gen).total_seconds() > TOLERANCIA_RELOJ_S:
        error(422, "La hora del evento (detectado_en) está en el futuro.",
              "Sincronice el reloj del equipo de captura (Configuración › Hora › Sincronizar ahora).")
    with db.tx() as con:
        cur = con.execute(
            "INSERT INTO alertas(tipo,prioridad,dispositivos,zona,confianza,modalidades,origen,evidencia_video,evidencia_audio,detectado_en,generado_en)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (a.tipo, a.prioridad, a.dispositivos, a.zona, a.confianza, json.dumps([m.model_dump() for m in a.modalidades]),
             a.origen, a.evidencia_video, a.evidencia_audio, iso(det), iso(gen)))
        codigo = f"A-{cur.lastrowid:04d}"
        con.execute("UPDATE alertas SET codigo=? WHERE id=?", (codigo, cur.lastrowid))
        return fila_alerta(con.execute("SELECT * FROM alertas WHERE id=?", (cur.lastrowid,)).fetchone())


@app.get("/api/v1/alertas")
def listar_alertas(estado: Literal["pendiente", "confirmada", "descartada"] | None = None,
                   prioridad: Literal[1, 2, 3] | None = None, _u=Depends(usuario_actual)):
    sql, p = "SELECT * FROM alertas WHERE 1=1", []
    if estado:
        sql += " AND estado=?"; p.append(estado)
    if prioridad:
        sql += " AND prioridad=?"; p.append(prioridad)
    sql += " ORDER BY prioridad ASC, generado_en DESC"
    with db.tx() as con:
        return [fila_alerta(r) for r in con.execute(sql, p).fetchall()]


class Resolucion(BaseModel):
    accion: Literal["confirmar", "descartar"]
    clics: int | None = Field(default=None, ge=1, le=50)   # clics usados (RNF-03)


@app.post("/api/v1/alertas/{alerta_id}/resolucion")
def resolver(alerta_id: int, r: Resolucion, u=Depends(usuario_actual)):
    with db.tx() as con:
        a = con.execute("SELECT * FROM alertas WHERE id=?", (alerta_id,)).fetchone()
        if not a:
            error(404, "No existe esa alerta.", "Actualice la lista de alertas.")
        if a["estado"] != "pendiente":
            error(409, f"La alerta {a['codigo']} ya fue {a['estado']}.", "Actualice la lista: otra persona pudo resolverla antes.")
        now = ahora()
        estado = "confirmada" if r.accion == "confirmar" else "descartada"
        con.execute("UPDATE alertas SET estado=?, resuelto_en=?, resuelto_por=?, clics=? WHERE id=?",
                    (estado, iso(now), u["sub"], r.clics, alerta_id))
        if estado == "confirmada":                      # RN-02: toda alerta confirmada se registra
            local = now.astimezone()
            con.execute("INSERT INTO incidentes(alerta_id,fecha,hora,lugar,tipo,registrado_por) VALUES (?,?,?,?,?,?)",
                        (alerta_id, local.strftime("%d/%m/%Y"), local.strftime("%H:%M:%S"),
                         f"{a['dispositivos']} · {a['zona']}", a["tipo"], u["sub"]))
        con.execute("INSERT INTO auditoria(momento,usuario,accion,detalle) VALUES (?,?,?,?)",
                    (iso(now), u["sub"], r.accion, a["codigo"]))
        return fila_alerta(con.execute("SELECT * FROM alertas WHERE id=?", (alerta_id,)).fetchone())


@app.post("/api/v1/alertas/{alerta_id}/deshacer")
def deshacer(alerta_id: int, u=Depends(usuario_actual)):
    with db.tx() as con:
        a = con.execute("SELECT * FROM alertas WHERE id=?", (alerta_id,)).fetchone()
        if not a or a["estado"] == "pendiente":
            error(409, "No hay nada que deshacer en esa alerta.", "Actualice la lista de alertas.")
        if a["resuelto_por"] != u["sub"]:
            error(403, "Solo quien resolvió la alerta puede deshacerla.", "Pida a esa persona o a un responsable que la reabra.")
        con.execute("DELETE FROM incidentes WHERE alerta_id=?", (alerta_id,))
        con.execute("UPDATE alertas SET estado='pendiente', resuelto_en=NULL, resuelto_por=NULL, clics=NULL WHERE id=?", (alerta_id,))
        con.execute("INSERT INTO auditoria(momento,usuario,accion,detalle) VALUES (?,?,?,?)", (iso(ahora()), u["sub"], "deshacer", a["codigo"]))
        return fila_alerta(con.execute("SELECT * FROM alertas WHERE id=?", (alerta_id,)).fetchone())


# ---------------------------------------------------------------- incidentes e indicadores
@app.get("/api/v1/incidentes")
def incidentes(_u=Depends(usuario_actual)):
    with db.tx() as con:
        rows = con.execute("SELECT i.*, a.codigo FROM incidentes i JOIN alertas a ON a.id=i.alerta_id ORDER BY i.id DESC").fetchall()
        return [{**dict(r), "codigo": f"INC-{r['id']:04d}", "alerta": r["codigo"]} for r in rows]


def _media(xs):
    return round(sum(xs) / len(xs), 2) if xs else None


@app.get("/api/v1/indicadores")
def indicadores(origen: Literal["edge", "simulado"] | None = None, _u=Depends(usuario_actual)):
    """I1 TTD, I2 TTA, I3 precisión, I4 falsas alarmas. I5 se mide con la encuesta Likert, no desde el panel.
    El recall y el F1 requieren un conjunto etiquetado aparte (verdad de campo)."""
    with db.tx() as con:
        q = "SELECT * FROM alertas" + (" WHERE origen=?" if origen else "")
        rows = con.execute(q, (origen,) if origen else ()).fetchall()
    ttd = [(parse(r["generado_en"]) - parse(r["detectado_en"])).total_seconds() for r in rows]
    tta = [(parse(r["resuelto_en"]) - parse(r["generado_en"])).total_seconds() for r in rows if r["resuelto_en"]]
    conf = sum(r["estado"] == "confirmada" for r in rows)
    desc = sum(r["estado"] == "descartada" for r in rows)
    res = conf + desc
    return {
        "alertas_total": len(rows), "pendientes": len(rows) - res, "confirmadas": conf, "descartadas": desc,
        "I1_ttd_s": _media(ttd), "I1_cumple_rnf01": (round(100 * sum(t <= 5 for t in ttd) / len(ttd), 1) if ttd else None),
        "I2_tta_s": _media(tta),
        "I3_precision_pct": round(100 * conf / res, 1) if res else None,
        "I4_falsas_alarmas_pct": round(100 * desc / res, 1) if res else None,
        "clics_medios": _media([r["clics"] for r in rows if r["clics"]]),
        "nota": "I5 se mide con la encuesta Likert. Recall y F1 requieren un conjunto etiquetado.",
    }


# ---------------------------------------------------------------- dispositivos
@app.get("/api/v1/dispositivos")
def dispositivos(_u=Depends(usuario_actual)):
    with db.tx() as con:
        return [dict(r) for r in con.execute("SELECT * FROM dispositivos ORDER BY tipo, nombre").fetchall()]


class CambioDispositivo(BaseModel):
    activo: bool


@app.patch("/api/v1/dispositivos/{disp_id}")
def cambiar_dispositivo(disp_id: int, c: CambioDispositivo, u=Depends(usuario_actual)):
    if u["rol"] == "vigilante":
        error(403, "Su rol no puede cambiar el estado de un dispositivo.", "Pida a un responsable de vigilancia o a un administrador que lo haga.")
    with db.tx() as con:
        if not con.execute("SELECT 1 FROM dispositivos WHERE id=?", (disp_id,)).fetchone():
            error(404, "No existe ese dispositivo.", "Actualice la lista.")
        con.execute("UPDATE dispositivos SET activo=? WHERE id=?", (int(c.activo), disp_id))
        con.execute("INSERT INTO auditoria(momento,usuario,accion,detalle) VALUES (?,?,?,?)",
                    (iso(ahora()), u["sub"], "dispositivo_activo" if c.activo else "dispositivo_inactivo", str(disp_id)))
        return dict(con.execute("SELECT * FROM dispositivos WHERE id=?", (disp_id,)).fetchone())


class Latido(BaseModel):
    activo: bool = True


@app.post("/api/v1/dispositivos/{disp_id}/latido", dependencies=[Depends(requiere_ingesta)])
def latido(disp_id: int, l: Latido | None = None):
    """El módulo edge avisa si el dispositivo sigue conectado (RF-01, RF-02).
    Con {"activo": false} informa que la captura falló y el panel muestra el aviso."""
    activo = l.activo if l else True
    with db.tx() as con:
        if activo:
            con.execute("UPDATE dispositivos SET ultimo_latido=?, activo=1 WHERE id=?", (iso(ahora()), disp_id))
        else:
            con.execute("UPDATE dispositivos SET activo=0 WHERE id=?", (disp_id,))
    return {"ok": True}


class RegistroEdge(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    tipo: Literal["camara", "audio"]
    zona: str = Field(min_length=1, max_length=80)


@app.post("/api/v1/dispositivos/registro", dependencies=[Depends(requiere_ingesta)])
def registrar_desde_edge(r: RegistroEdge):
    """El módulo edge registra (o reutiliza por nombre) la fuente que está capturando y obtiene su id."""
    with db.tx() as con:
        fila = con.execute("SELECT * FROM dispositivos WHERE nombre=?", (r.nombre,)).fetchone()
        if fila and fila["tipo"] != r.tipo:
            error(409, f"Ya existe «{r.nombre}» con otro tipo.", "Use otro nombre para esta fuente.")
        if not fila:
            con.execute("INSERT INTO dispositivos(nombre,tipo,zona) VALUES (?,?,?)", (r.nombre, r.tipo, r.zona))
            con.execute("INSERT INTO auditoria(momento,usuario,accion,detalle) VALUES (?,?,?,?)",
                        (iso(ahora()), "edge", "dispositivo_registrado", r.nombre))
        else:
            con.execute("UPDATE dispositivos SET zona=? WHERE id=?", (r.zona, fila["id"]))
        return dict(con.execute("SELECT * FROM dispositivos WHERE nombre=?", (r.nombre,)).fetchone())


# ---------------------------------------------------------------- evidencias (clips de audio y video)
EVIDENCIA_TIPOS = {".webm": "video/webm", ".wav": "audio/wav"}
EVIDENCIA_NOMBRE = re.compile(r"^[a-f0-9]{32}\.(webm|wav)$")


@app.post("/api/v1/evidencias", status_code=201, dependencies=[Depends(requiere_ingesta)])
async def subir_evidencia(archivo: UploadFile = File(...)):
    """El módulo edge sube el clip de una alerta. El nombre lo pone el servidor (no se confía en el del cliente)."""
    ext = Path(archivo.filename or "").suffix.lower()
    if ext not in EVIDENCIA_TIPOS:
        error(415, "Tipo de evidencia no admitido.", "Envíe un clip .webm (video) o .wav (audio).")
    datos = await archivo.read(config.EVIDENCIA_MAX_BYTES + 1)
    if len(datos) > config.EVIDENCIA_MAX_BYTES:
        error(413, "El clip es demasiado grande.", "Reduzca la duración del clip o la resolución del video.")
    if not datos:
        error(422, "El clip está vacío.", "Revise que la captura esté funcionando.")
    nombre = uuid.uuid4().hex + ext
    (config.EVIDENCIAS_DIR / nombre).write_bytes(datos)
    return {"url": f"/api/v1/evidencias/{nombre}"}


@app.get("/api/v1/evidencias/{nombre}")
def ver_evidencia(nombre: str, u=Depends(usuario_actual)):
    if not EVIDENCIA_NOMBRE.match(nombre):
        error(404, "No existe esa evidencia.", "Actualice la lista de alertas.")
    ruta = config.EVIDENCIAS_DIR / nombre
    if not ruta.is_file():
        error(404, "La evidencia ya no está disponible.", "Pudo borrarse por la política de retención.")
    return FileResponse(ruta, media_type=EVIDENCIA_TIPOS[ruta.suffix], headers={"Cache-Control": "private, no-store"})


@app.get("/api/v1/salud")
def salud():
    return {"estado": "ok", "version": app.version}


fuentes.registrar(app, usuario_actual, requiere_ingesta, error)   # «Buscar dispositivos» y canal del edge

# El panel web se sirve desde el mismo servidor (carpeta frontend/).
if config.FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIR, html=True), name="panel")
