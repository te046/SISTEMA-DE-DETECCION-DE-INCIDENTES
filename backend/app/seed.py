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
    db.init()
    nuevas = []
    with db.tx() as con:
        for u, n, rol, env in CUENTAS:
            if con.execute("SELECT 1 FROM usuarios WHERE usuario=?", (u,)).fetchone():
                continue
            clave = os.environ.get(env) or secrets.token_urlsafe(9)
            con.execute("INSERT INTO usuarios(usuario,nombre,rol,pass_hash) VALUES (?,?,?,?)", (u, n, rol, security.hash_password(clave)))
            nuevas.append((u, clave if not os.environ.get(env) else "(la definida en " + env + ")"))
        for n, t, z in DISPOSITIVOS:
            con.execute("INSERT OR IGNORE INTO dispositivos(nombre,tipo,zona) VALUES (?,?,?)", (n, t, z))
    if nuevas:
        print("Cuentas creadas (guarde estas claves ahora; no se vuelven a mostrar):")
        for u, c in nuevas:
            print(f"  {u:26s} {c}")
    else:
        print("Las cuentas ya existían; no se cambió nada.")


if __name__ == "__main__":
    main()
