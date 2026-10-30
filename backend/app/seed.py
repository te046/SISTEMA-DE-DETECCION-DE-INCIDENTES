"""Crea la base, las cuentas y los dispositivos. Uso: python -m app.seed [--demo]

Las contraseñas NO están en el código: se leen de variables de entorno o se generan al azar
y se muestran una sola vez.
"""
import os, secrets, sys
from . import db, security

DISPOSITIVOS = [
    ("Cámara 1", "camara", "Zona 3"), ("Cámara 2", "camara", "Zona 1"),
    ("Nodo de audio 1", "audio", "Zona 1"), ("Nodo de audio 2", "audio", "Zona 2"),
]
CUENTAS = [  # usuario, nombre, rol, variable de entorno con la clave
    ("responsable.vigilancia", "Responsable de vigilancia", "responsable", "CLAVE_RESPONSABLE"),
    ("vigilante.1", "Vigilante 1", "vigilante", "CLAVE_VIGILANTE"),
    ("admin", "Administrador", "admin", "CLAVE_ADMIN"),
]


def main():
    nuevas = crear_cuentas()
    if nuevas:
        print("Cuentas creadas (guarde estas claves ahora; no se vuelven a mostrar):")
        for u, c in nuevas:
            print(f"  {u:26s} {c}")
    else:
        print("Las cuentas ya existían; no se cambió nada.")


def crear_cuentas(dispositivos_de_ejemplo: bool = True) -> list[tuple[str, str]]:
    """Crea la base, las cuentas que falten y (en desarrollo) los dispositivos de ejemplo. Devuelve [(usuario, clave)]
    de las cuentas NUEVAS sin imprimir ni registrar nada: la app de escritorio las muestra solo dentro de su ventana
    y no crea dispositivos de ejemplo (las fuentes reales se conectan en «Buscar dispositivos»)."""
    db.init()
    nuevas = []
    with db.tx() as con:
        for u, n, rol, env in CUENTAS:
            if con.execute("SELECT 1 FROM usuarios WHERE usuario=?", (u,)).fetchone():
                continue
            clave = os.environ.get(env) or secrets.token_urlsafe(9)
            con.execute("INSERT INTO usuarios(usuario,nombre,rol,pass_hash) VALUES (?,?,?,?)", (u, n, rol, security.hash_password(clave)))
            nuevas.append((u, clave if not os.environ.get(env) else "(la definida en " + env + ")"))
        for n, t, z in (DISPOSITIVOS if dispositivos_de_ejemplo else []):
            con.execute("INSERT OR IGNORE INTO dispositivos(nombre,tipo,zona) VALUES (?,?,?)", (n, t, z))
    return nuevas


def restablecer_claves() -> list[tuple[str, str]]:
    """Genera contraseñas NUEVAS para las cuentas del sistema (las anteriores dejan de funcionar) y desbloquea las
    cuentas. Las antiguas no se pueden recuperar: solo se guardó su hash. Devuelve [(usuario, clave)] sin
    imprimir ni registrar las claves; la auditoría solo anota que hubo un restablecimiento."""
    from datetime import datetime, timezone
    db.init()
    nuevas = []
    with db.tx() as con:
        for u, n, rol, _env in CUENTAS:
            clave = secrets.token_urlsafe(9)
            if con.execute("SELECT 1 FROM usuarios WHERE usuario=?", (u,)).fetchone():
                con.execute("UPDATE usuarios SET pass_hash=?, intentos=0, bloqueado_hasta=NULL WHERE usuario=?",
                            (security.hash_password(clave), u))
            else:
                con.execute("INSERT INTO usuarios(usuario,nombre,rol,pass_hash) VALUES (?,?,?,?)", (u, n, rol, security.hash_password(clave)))
            nuevas.append((u, clave))
        con.execute("INSERT INTO auditoria(momento,usuario,accion,detalle) VALUES (?,?,?,?)",
                    (datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "sistema", "claves_restablecidas",
                     ", ".join(u for u, _ in nuevas)))
    return nuevas


if __name__ == "__main__":
    main()
