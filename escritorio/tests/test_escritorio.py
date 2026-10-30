"""Aplicación de escritorio sin abrir ventanas: piezas puras y prueba de humo completa en un subproceso."""
import json
import os
import socket
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from escritorio.soporte import InstanciaUnica, carpeta_datos, pagina_claves, puerto_libre  # noqa: E402


def test_puerto_libre_salta_ocupados_y_los_de_otros_proyectos():
    with socket.socket() as ocupado:
        ocupado.bind(("127.0.0.1", 0)); ocupado.listen()
        p = ocupado.getsockname()[1]
        assert puerto_libre(p, p + 5, ajenos=set()) != p
    with pytest.raises(RuntimeError):
        puerto_libre(8080, 8081)                                                      # ambos son de otros proyectos


@pytest.mark.skipif(os.name != "nt", reason="mutex con nombre de Windows")
def test_instancia_unica():
    nombre = f"Local\\PruebaVigilancia-{uuid.uuid4().hex}"
    a, b = InstanciaUnica(nombre), InstanciaUnica(nombre)
    assert a.adquirir() and not b.adquirir()                                         # la segunda no arranca
    a.liberar()
    assert b.adquirir()
    b.liberar()


def test_datos_en_localappdata_y_nunca_en_el_proyecto(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    d = carpeta_datos()
    assert d == tmp_path / "SistemaVigilanciaUDH"
    assert RAIZ not in d.parents and d != RAIZ / "data"


def test_pagina_de_claves_escapa_html():
    html = pagina_claves([("admin", "<script>x</script>&")])
    assert "<script>x" not in html and "&lt;script&gt;" in html and "una sola vez" in html


def test_prueba_de_humo_arranca_responde_y_cierra(tmp_path):
    entorno = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    entorno.pop("VIGILANCIA_DATA", None)
    r = subprocess.run([sys.executable, "-m", "escritorio", "--prueba-humo", "--datos", str(tmp_path)],
                       cwd=RAIZ, capture_output=True, text=True, timeout=90, env=entorno)
    informe = json.loads((tmp_path / "prueba_humo.json").read_text(encoding="utf-8"))
    assert r.returncode == 0, informe
    assert informe["salud"]["estado"] == "ok" and informe["edge_sincronizo"] and informe["panel"] == 200 and informe["modelo_audio"]
    assert informe["hilos_vivos"] == []                                               # cerró la API y el edge
    with socket.socket() as s:                                                         # el puerto quedó libre
        assert s.connect_ex(("127.0.0.1", informe["puerto"])) != 0
    assert "Cuentas creadas" not in r.stdout + r.stderr                                # las claves no salen por consola
    registro = (tmp_path / "registros" / "app.log").read_text(encoding="utf-8")
    assert "API lista" in registro and "Sistema detenido" in registro
    assert not (RAIZ / "data" / "prueba_humo.json").exists()                           # no tocó el data\ de desarrollo
