"""Lanzador para PyInstaller (importa el paquete por nombre absoluto)."""
import multiprocessing
import sys

from escritorio.app import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
