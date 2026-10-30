"""Punto de entrada único de la aplicación de escritorio.

    python -m escritorio                     → ventana «Sistema de Vigilancia UDH»
    python -m escritorio --prueba-humo --datos <carpeta temporal>
                                             → arranca API y edge sin ventana, comprueba /salud y cierra todo

Un solo proceso: la ventana (pywebview) ocupa el hilo principal; la API (uvicorn) y el edge corren en hilos propios.
Al cerrar la ventana se detienen ambos: la app no lanza procesos hijos, así que no deja nada corriendo.
Datos en %LOCALAPPDATA%\\SistemaVigilanciaUDH (nunca en la carpeta de instalación ni en el data\\ de desarrollo).
"""
import argparse
import json
import logging
import logging.handlers
import os
import sys
import threading
import time
from pathlib import Path

from . import NOMBRE, VERSION
from .soporte import InstanciaUnica, aviso, carpeta_datos, pagina_claves, puerto_libre, recursos

log = logging.getLogger("escritorio")


def argumentos(argv=None):
    ap = argparse.ArgumentParser(prog="SistemaVigilanciaUDH", description=NOMBRE)
    ap.add_argument("--datos", help="carpeta de datos (por defecto %%LOCALAPPDATA%%\\SistemaVigilanciaUDH)")
    ap.add_argument("--sesion", choices=["prueba", "tesis"], default="prueba", help="etiqueta de las mediciones de I1")
    ap.add_argument("--diagnostico", action="store_true", help="registra cada segundo el nivel y las 3 clases de audio")
    ap.add_argument("--prueba-humo", action="store_true", help="arranca sin ventana, comprueba /salud y cierra")
    return ap.parse_args(argv)


def configurar_entorno(datos: Path) -> None:
    """Antes de importar el backend: su configuración lee estas variables al importarse."""
    datos.mkdir(parents=True, exist_ok=True)
    os.environ["VIGILANCIA_DATA"] = str(datos)
    os.environ["VIGILANCIA_FRONTEND"] = str(recursos() / "frontend")
    raiz = recursos()
    for ruta in (raiz, raiz / "backend"):
        if str(ruta) not in sys.path:
            sys.path.insert(0, str(ruta))


def configurar_registro(datos: Path) -> Path:
    """Registro en archivo (la app empaquetada no tiene consola). Nunca se registran claves."""
    carpeta = datos / "registros"
    carpeta.mkdir(exist_ok=True)
    archivo = carpeta / "app.log"
    manejador = logging.handlers.RotatingFileHandler(archivo, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    manejador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"))
    raiz = logging.getLogger()
    raiz.handlers[:] = [manejador]
    raiz.setLevel(logging.INFO)
    for ruidoso in ("httpx", "uvicorn.access"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)
    return archivo


class Sistema:
    """API + edge en hilos, con arranque y cierre ordenados."""

    def __init__(self, sesion: str = "prueba", diagnostico: bool = False):
        self.sesion, self.diagnostico = sesion, diagnostico
        self.puerto = self.servidor = self.edge = None
        self._hilo_api: threading.Thread | None = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.puerto}"

    def iniciar(self, espera_s: float = 20.0) -> None:
        import httpx
        import uvicorn
        from app import config
        from app.main import app as api

        self.puerto = puerto_libre()
        self.servidor = uvicorn.Server(uvicorn.Config(api, host="127.0.0.1", port=self.puerto, log_config=None, access_log=False))
        self._hilo_api = threading.Thread(target=self.servidor.run, name="api", daemon=True)
        self._hilo_api.start()
        limite = time.time() + espera_s
        while time.time() < limite:
            try:
                if httpx.get(self.url + "/api/v1/salud", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.2)
        else:
            raise RuntimeError("La API no respondió a tiempo.")
        (config.DATA_DIR / ".api_url").write_text(self.url, encoding="utf-8")
        log.info("API lista en %s (datos: %s).", self.url, config.DATA_DIR)
        self._iniciar_edge(config)

    def _iniciar_edge(self, config) -> None:
        from edge.clasificador_audio import ClasificadorYamnet
        from edge.cliente import ClienteApi
        from edge.servicio import ServicioEdge

        def crear_video():
            from edge.clasificador_video import ClasificadorVideo
            return ClasificadorVideo()

        cliente = ClienteApi(self.url, config.INGEST_KEY)          # en el mismo proceso: la clave no sale de memoria
        self.edge = ServicioEdge(cliente, lambda: ClasificadorYamnet(), crear_video, config.DATA_DIR / "mediciones_latencia.csv",
                                 self.sesion, imprimir_diagnostico=logging.getLogger("edge.diagnostico").info if self.diagnostico else None)
        self.edge.iniciar()
        log.info("Edge iniciado (sesión de medición: %s).", self.sesion)

    def detener(self) -> None:
        if self.edge is not None:
            log.info("Cerrando el edge (capturas y modelos)…")
            if not self.edge.detener():
                log.warning("El edge tardó más de lo esperado en cerrar.")
        if self.servidor is not None:
            self.servidor.should_exit = True
            if self._hilo_api is not None:
                self._hilo_api.join(10)
        log.info("Sistema detenido.")


def prueba_humo(datos: Path, sesion: str) -> int:
    """Sin ventana: arranca, comprueba /salud y que el edge habla con la API, cierra y deja un informe JSON."""
    import httpx
    t0 = time.time()
    s = Sistema(sesion)
    resultado = {"version": VERSION, "ok": False}
    try:
        from app import seed
        seed.crear_cuentas(dispositivos_de_ejemplo=False)
        s.iniciar()
        resultado["puerto"] = s.puerto
        resultado["salud"] = httpx.get(s.url + "/api/v1/salud", timeout=2).json()
        limite = time.time() + 10
        while s.edge.sincronizaciones < 1 and time.time() < limite:
            time.sleep(0.1)
        resultado["edge_sincronizo"] = s.edge.sincronizaciones >= 1
        resultado["panel"] = httpx.get(s.url + "/", timeout=2).status_code
        from edge.clasificador_audio import ClasificadorYamnet          # el modelo empaquetado se puede cargar
        import numpy as np
        resultado["modelo_audio"] = ClasificadorYamnet().puntajes(np.zeros(16000, np.float32)).shape[1] == 521
        try:
            from edge.clasificador_video import ClasificadorVideo
            ClasificadorVideo()
            resultado["modelo_video"] = "instalado (línea base)"
        except FileNotFoundError:
            resultado["modelo_video"] = "no instalado: las cámaras solo graban evidencia"
        resultado["ok"] = (resultado["salud"].get("estado") == "ok" and resultado["edge_sincronizo"]
                           and resultado["panel"] == 200 and resultado["modelo_audio"])
    except Exception as e:
        resultado["error"] = str(e)
        log.exception("Fallo en la prueba de humo")
    finally:
        s.detener()
        resultado["hilos_vivos"] = sorted(h.name for h in threading.enumerate() if h.name in ("api", "edge"))
        resultado["segundos"] = round(time.time() - t0, 2)
        (datos / "prueba_humo.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if resultado["ok"] and not resultado["hilos_vivos"] else 1


def abrir_ventana(sistema: Sistema, cuentas: list[tuple[str, str]]) -> None:
    import webview
    webview.settings["ALLOW_DOWNLOADS"] = True                 # exportar CSV desde la ventana
    principal = webview.create_window(NOMBRE, sistema.url, width=1320, height=860, min_size=(900, 600), background_color="#F4F8F7")
    claves = None
    if cuentas:                                                 # primera ejecución: solo en esta ventana, nunca en consola ni registros
        claves = webview.create_window("Claves iniciales: guárdelas ahora", html=pagina_claves(cuentas), width=600, height=560, on_top=True)
        cuentas.clear()

    def al_cerrar_principal():
        if claves is not None:
            try:
                claves.destroy()
            except Exception:
                pass
    principal.events.closed += al_cerrar_principal
    icono = recursos() / "escritorio" / "recursos" / "udh.ico"
    webview.start(icon=str(icono) if icono.exists() else None, private_mode=True)


def main(argv=None) -> int:
    a = argumentos(argv)
    datos = carpeta_datos(a.datos)
    configurar_entorno(datos)
    registro = configurar_registro(datos)
    if a.prueba_humo:
        return prueba_humo(datos, a.sesion)

    instancia = InstanciaUnica()
    if not instancia.adquirir():
        log.warning("Segunda instancia: %s ya está abierto; esta no arranca ni abre puertos.", NOMBRE)
        aviso(f"{NOMBRE} ya está abierto. Use la ventana que ya está en la barra de tareas.")
        return 0
    sistema = Sistema(a.sesion, a.diagnostico)
    try:
        from app import seed
        cuentas = seed.crear_cuentas(dispositivos_de_ejemplo=False)
        sistema.iniciar()
        abrir_ventana(sistema, cuentas)
        return 0
    except Exception as e:
        log.exception("Error al iniciar")
        aviso(f"No se pudo iniciar {NOMBRE}.\n\n{e}\n\nRegistro: {registro}")
        return 1
    finally:
        sistema.detener()
        instancia.liberar()
