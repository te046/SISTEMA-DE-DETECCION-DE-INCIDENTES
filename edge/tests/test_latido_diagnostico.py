"""Reintento del latido ante conexión cerrada y modo diagnóstico (sin hardware ni red)."""
import httpx
import numpy as np
import pytest

from edge.cliente import ClienteApi
from edge.detector import Detector
from edge.buffers import BufferAudio
from edge.diagnostico import Diagnostico, nivel_dbfs, top_clases


def _cliente(fallos: int, error=httpx.ReadError):
    llamadas = []

    def manejar(req):
        llamadas.append(req.url.path)
        if len(llamadas) <= fallos:
            raise error("[WinError 10054] conexión cerrada por el host remoto", request=req)
        return httpx.Response(200, json={"ok": True})

    return ClienteApi("http://api.prueba", "clave", transporte=httpx.MockTransport(manejar)), llamadas


@pytest.mark.parametrize("error", [httpx.ReadError, httpx.WriteError, httpx.RemoteProtocolError])
def test_latido_reintenta_una_vez_si_la_conexion_estaba_cerrada(error):
    cli, llamadas = _cliente(fallos=1, error=error)
    cli.latido(13)
    assert llamadas == ["/api/v1/dispositivos/13/latido"] * 2


def test_latido_no_reintenta_indefinidamente():
    cli, llamadas = _cliente(fallos=2)
    with pytest.raises(httpx.ReadError):
        cli.latido(13)
    assert len(llamadas) == 2                               # un intento + un solo reintento


def test_latido_sin_fallo_hace_una_sola_peticion():
    cli, llamadas = _cliente(fallos=0)
    cli.latido(13, activo=False)
    assert len(llamadas) == 1


def test_nivel_dbfs():
    assert nivel_dbfs(np.zeros(16000, np.float32)) == -90.0
    assert nivel_dbfs(np.ones(16000, np.float32)) == pytest.approx(0.0)
    assert nivel_dbfs(np.full(16000, 0.1, np.float32)) == pytest.approx(-20.0)


def test_top_clases_ordena_por_maximo_entre_cuadros():
    nombres = ["Speech", "Shatter", "Silence", "Music"]
    p = np.array([[0.2, 0.1, 0.9, 0.0], [0.7, 0.4, 0.1, 0.3]], np.float32)
    assert [(n, round(s, 2)) for n, s in top_clases(p, nombres)] == [("Silence", 0.9), ("Speech", 0.7), ("Shatter", 0.4)]


class ClasificadorConPuntajes:
    nombres = ["Speech", "Shatter", "Silence", "Music"]

    def __init__(self):
        self.ultimos_puntajes = None

    def clasificar(self, v):
        self.ultimos_puntajes = np.array([[0.1, 0.3, 0.6, 0.0]], np.float32)
        return []                                           # nada supera el umbral: igual se diagnostica


def test_diagnostico_una_linea_por_segundo_y_solo_imprime(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lineas = []
    c = ClasificadorConPuntajes()
    audio = BufferAudio(16000, 15)
    for k in range(40):                                     # 4 s de audio → 7 ventanas de 1 s con paso 0,5 s
        audio.agregar(1000 + k * 0.1, np.full(1600, 0.1, np.float32))
    d = Detector(c, audio, None, "Zona 1", "Micrófono", observador=Diagnostico(c, imprimir=lineas.append))
    assert d.procesar() == 7
    assert len(lineas) == 4                                 # t = 1000, 1001, 1002, 1003
    assert "-20.0 dBFS" in lineas[0] and "Silence 0.60 · Shatter 0.30 · Speech 0.10" in lineas[0]
    assert d.pendientes == [] and list(tmp_path.iterdir()) == []   # no genera alertas ni archivos


def test_diagnostico_sin_puntajes_no_imprime():
    lineas = []
    Diagnostico(ClasificadorConPuntajes(), imprimir=lineas.append)(np.zeros(16000, np.float32), 1.0)
    assert lineas == []
