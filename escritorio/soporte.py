"""Piezas puras de la app de escritorio (sin interfaz): carpeta de datos, puerto libre, instancia única y la
página que muestra las claves iniciales. Se prueban sin abrir ventanas."""
import html
import os
import socket
import sys
from pathlib import Path

from . import CARPETA_DATOS, NOMBRE

PUERTOS_AJENOS = {8080, 8081, 8090}      # de otros proyectos de Teo: nunca se usan


def carpeta_datos(explicita: str | None = None) -> Path:
    """%LOCALAPPDATA%\\SistemaVigilanciaUDH (nunca la carpeta de instalación ni el data\\ de desarrollo)."""
    if explicita:
        return Path(explicita)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / CARPETA_DATOS


def recursos() -> Path:
    """Raíz de los archivos de la app: la carpeta de PyInstaller si está empaquetada, si no el proyecto."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def puerto_libre(desde: int = 8000, hasta: int = 8099, host: str = "127.0.0.1", ajenos: set[int] = PUERTOS_AJENOS) -> int:
    for p in range(desde, hasta + 1):
        if p in ajenos:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((host, p)) != 0:
                return p
    raise RuntimeError(f"No hay puertos libres entre {desde} y {hasta}.")


class InstanciaUnica:
    """Mutex con nombre de Windows: si ya existe, otra ventana de la app está abierta."""
    ERROR_ALREADY_EXISTS = 183

    def __init__(self, nombre: str = "Local\\SistemaVigilanciaUDH"):
        self.nombre, self._h = nombre, None

    def adquirir(self) -> bool:
        if os.name != "nt":
            return True
        import ctypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateMutexW.restype = ctypes.c_void_p
        self._h = k32.CreateMutexW(None, False, self.nombre)
        if ctypes.get_last_error() == self.ERROR_ALREADY_EXISTS:
            k32.CloseHandle(ctypes.c_void_p(self._h)); self._h = None
            return False
        return True

    def liberar(self) -> None:
        if self._h and os.name == "nt":
            import ctypes
            ctypes.WinDLL("kernel32").CloseHandle(ctypes.c_void_p(self._h))
        self._h = None


def aviso(texto: str, titulo: str = NOMBRE) -> None:
    """Cuadro de mensaje nativo (la app empaquetada no tiene consola)."""
    if os.name == "nt":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, texto, titulo, 0x40)


def confirmar(texto: str, titulo: str = NOMBRE) -> bool:
    """Pregunta Sí/No nativa (aviso amarillo). Fuera de Windows, no confirma."""
    if os.name != "nt":
        return False
    import ctypes
    MB_YESNO, MB_ICONWARNING, MB_DEFBUTTON2, IDYES = 0x4, 0x30, 0x100, 6
    return ctypes.windll.user32.MessageBoxW(None, texto, titulo, MB_YESNO | MB_ICONWARNING | MB_DEFBUTTON2) == IDYES


def pagina_claves(cuentas: list[tuple[str, str]]) -> str:
    """HTML (escapado) de la ventana de primera ejecución. Solo vive en memoria: no se guarda ni se registra."""
    filas = "".join(f"<tr><td>{html.escape(u)}</td><td class='c'>{html.escape(c)}</td></tr>" for u, c in cuentas)
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Claves iniciales</title>
<style>body{{font-family:'Segoe UI',system-ui,sans-serif;font-size:16px;color:#10302D;background:#F4F8F7;margin:0;padding:24px}}
h1{{font-size:22px;margin:0 0 8px}}p{{margin:0 0 14px}}.aviso{{background:#FDECE8;border-left:4px solid #C93A22;color:#9E2E19;
padding:10px 14px;border-radius:10px}}table{{border-collapse:collapse;width:100%;background:#fff;border-radius:12px;margin:14px 0}}
td{{padding:10px 12px;border-bottom:1px solid #E2ECE9}}.c{{font-family:Consolas,monospace;font-size:18px;user-select:all}}</style></head>
<body><h1>Claves iniciales del sistema</h1>
<p class="aviso"><strong>Se muestran una sola vez.</strong> Anótelas en un lugar seguro antes de cerrar esta ventana.</p>
<table>{filas}</table>
<p>Con estas cuentas se ingresa a la ventana principal. Las contraseñas no se guardan en ningún archivo ni registro.</p>
</body></html>"""
