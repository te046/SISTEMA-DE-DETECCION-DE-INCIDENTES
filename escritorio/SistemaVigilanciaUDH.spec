# PyInstaller: carpeta dist\SistemaVigilanciaUDH\ con SistemaVigilanciaUDH.exe (sin consola).
#   .venv\Scripts\pyinstaller escritorio\SistemaVigilanciaUDH.spec --noconfirm --distpath dist --workpath build
# Incluye: panel (frontend), YAMNet (Apache 2.0) y el ícono. NO incluye el modelo de video (CC BY-NC, derivado de
# RWF-2000): no se redistribuye; se copia a %LOCALAPPDATA%\SistemaVigilanciaUDH\modelos con scripts\instalar_modelo_video.ps1.
from pathlib import Path

RAIZ = Path(SPECPATH).parent

datos = [
    (str(RAIZ / "frontend"), "frontend"),
    (str(RAIZ / "edge" / "modelos" / "yamnet.onnx"), "edge/modelos"),
    (str(RAIZ / "edge" / "modelos" / "yamnet_class_map.csv"), "edge/modelos"),
    (str(RAIZ / "edge" / "modelos" / "PROCEDENCIA.md"), "edge/modelos"),
    (str(RAIZ / "escritorio" / "recursos" / "udh.ico"), "escritorio/recursos"),
]
ocultos = [
    "uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto", "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto", "uvicorn.lifespan.on", "multipart", "python_multipart",
    "app.main", "app.fuentes", "app.cifrado", "app.urls", "app.seed",
    "edge.servicio", "edge.gestor", "edge.clasificador_audio", "edge.clasificador_video", "edge.detector_video",
]

a = Analysis(
    [str(RAIZ / "escritorio" / "lanzador.py")],
    pathex=[str(RAIZ), str(RAIZ / "backend")],
    datas=datos,
    hiddenimports=ocultos,
    excludes=["tkinter", "torch", "transformers", "pytest", "matplotlib", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="SistemaVigilanciaUDH",
    icon=str(RAIZ / "escritorio" / "recursos" / "udh.ico"),
    console=False,
    version=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="SistemaVigilanciaUDH")
