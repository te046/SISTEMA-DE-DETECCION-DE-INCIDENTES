import sqlite3
from contextlib import contextmanager
from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  usuario TEXT UNIQUE NOT NULL,
  nombre TEXT NOT NULL,
  rol TEXT NOT NULL CHECK (rol IN ('responsable','vigilante','admin')),
  pass_hash TEXT NOT NULL,
  intentos INTEGER NOT NULL DEFAULT 0,
  bloqueado_hasta TEXT
);
CREATE TABLE IF NOT EXISTS dispositivos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT UNIQUE NOT NULL,
  tipo TEXT NOT NULL CHECK (tipo IN ('camara','audio')),
  zona TEXT NOT NULL,
  activo INTEGER NOT NULL DEFAULT 1,
  ultimo_latido TEXT
);
CREATE TABLE IF NOT EXISTS alertas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  codigo TEXT UNIQUE,
  tipo TEXT NOT NULL,
  prioridad INTEGER NOT NULL CHECK (prioridad IN (1,2,3)),
  dispositivos TEXT NOT NULL,          -- texto: «Cámara 2 + Nodo de audio 1»
  zona TEXT NOT NULL,
  confianza REAL NOT NULL CHECK (confianza >= 0 AND confianza <= 1),
  modalidades TEXT NOT NULL,           -- JSON: [{"modalidad":"audio","clase":"grito","confianza":0.84}]
  origen TEXT NOT NULL DEFAULT 'edge', -- 'edge' o 'simulado'
  evidencia_video TEXT,
  evidencia_audio TEXT,
  estado TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente','confirmada','descartada')),
  detectado_en TEXT NOT NULL,          -- instante del evento (para I1 TTD)
  generado_en TEXT NOT NULL,           -- instante en que el panel puede mostrarla
  resuelto_en TEXT,                    -- para I2 TTA
  resuelto_por TEXT,
  clics INTEGER
);
CREATE INDEX IF NOT EXISTS ix_alertas_estado ON alertas(estado, prioridad);
CREATE TABLE IF NOT EXISTS incidentes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  alerta_id INTEGER UNIQUE NOT NULL REFERENCES alertas(id),
  fecha TEXT NOT NULL, hora TEXT NOT NULL,
  lugar TEXT NOT NULL, tipo TEXT NOT NULL,
  registrado_por TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fuentes (    -- fuentes elegidas en «Buscar dispositivos»
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  clave TEXT UNIQUE NOT NULL,          -- local: la del inventario del edge; manual: 'ip:<uuid>'
  tipo TEXT NOT NULL CHECK (tipo IN ('camara','audio')),
  clase TEXT NOT NULL CHECK (clase IN ('local','ip','telefono')),
  nombre TEXT UNIQUE NOT NULL,
  zona TEXT NOT NULL,
  uri_cifrada TEXT,                    -- solo ip/telefono: dirección completa cifrada (nunca en texto plano)
  uri_visible TEXT,                    -- la misma dirección sin usuario, clave ni parámetros
  conectada INTEGER NOT NULL DEFAULT 0,
  error TEXT,                          -- último error informado por el edge (ya enmascarado)
  actualizado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS inventario_edge (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  datos TEXT NOT NULL DEFAULT '{}',    -- JSON con micrófonos y cámaras detectados
  actualizado_en TEXT,
  busqueda_pedida_en TEXT,
  edge_visto_en TEXT                   -- última consulta del edge (para saber si está abierto)
);
CREATE TABLE IF NOT EXISTS auditoria (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  momento TEXT NOT NULL, usuario TEXT, accion TEXT NOT NULL, detalle TEXT
);
"""


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(config.DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


@contextmanager
def tx():
    con = connect()
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


MIGRACIONES = [   # (tabla, columna, definición): se agregan solo si faltan; nunca se borran datos
    ("alertas", "mostrado_en", "TEXT"),   # hora del SERVIDOR al recibir el aviso del panel (para «I1 visible»)
]


def init():
    with tx() as con:
        con.executescript(SCHEMA)
        for tabla, columna, definicion in MIGRACIONES:
            if columna not in {r["name"] for r in con.execute(f"PRAGMA table_info({tabla})")}:
                con.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}")
