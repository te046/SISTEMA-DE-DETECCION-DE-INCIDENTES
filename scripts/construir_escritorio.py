"""Construye dist\\SistemaVigilanciaUDH\\ con PyInstaller.

    .venv\\Scripts\\python scripts\\construir_escritorio.py

Python 3.10.0 (el de la laptop de desarrollo) tiene un fallo en `dis` (bpo-45757, corregido en 3.10.1): tras un
EXTENDED_ARG seguido de una instrucción sin argumento no reinicia el acumulador y PyInstaller se cae con
«IndexError: tuple index out of range». Aquí se aplica el mismo arreglo de 3.10.1 SOLO dentro de este proceso
(no se modifica la instalación de Python). En 3.10.1 o superior no se toca nada.
"""
import dis
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _unpack_opargs_310_1(code):
    extended_arg = 0
    for i in range(0, len(code), 2):
        op = code[i]
        if op >= dis.HAVE_ARGUMENT:
            arg = code[i + 1] | extended_arg
            extended_arg = (arg << 8) if op == dis.EXTENDED_ARG else 0
        else:
            arg = None
            extended_arg = 0                       # el arreglo de bpo-45757
        yield (i, op, arg)


def main():
    if sys.version_info[:3] == (3, 10, 0):
        dis._unpack_opargs = _unpack_opargs_310_1
        print("Python 3.10.0: se aplicó el arreglo de dis (bpo-45757) dentro de este proceso.")
    import PyInstaller.__main__
    PyInstaller.__main__.run([str(RAIZ / "escritorio" / "SistemaVigilanciaUDH.spec"), "--noconfirm",
                              "--distpath", str(RAIZ / "dist"), "--workpath", str(RAIZ / "build"), "--log-level", "WARN"])
    print(f"Listo: {RAIZ / 'dist' / 'SistemaVigilanciaUDH' / 'SistemaVigilanciaUDH.exe'}")


if __name__ == "__main__":
    main()
