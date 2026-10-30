"""Inventario de fuentes locales para «Buscar dispositivos».

Windows muestra el mismo micrófono hasta cuatro veces (MME, DirectSound, WASAPI y WDM-KS) y MME
corta el nombre a 31 caracteres. Aquí se agrupan en una sola entrada y se marca qué no sirve
(mezcla estéreo, asignadores virtuales, salidas de parlante). La captura usa la entrada MME porque
convierte a 16 kHz sin problemas; las que solo existen por WDM-KS quedan como «no sirve» hasta que
se implemente esa ruta.
"""
import re

from .captura import PATRON_BLUETOOTH

NO_SIRVE = [
    (re.compile(r"stereo mix|mezcla est[eé]reo|what u hear|loopback", re.I), "Graba lo que suena en los parlantes, no el ambiente."),
    (re.compile(r"asignador de sonido|sound mapper|controlador primario|primary sound", re.I), "Es una entrada virtual de Windows, no un micrófono."),
    (re.compile(r"speaker|altavoz|parlante", re.I), "Es una salida de audio, no un micrófono."),
]
PREFERENCIA_API = ["MME", "Windows DirectSound", "Windows WASAPI"]          # WDM-KS aún no soportado
LARGO_MME = 31


def _clave_nombre(nombre: str) -> str:
    return re.sub(r"\s+", " ", nombre[:LARGO_MME]).strip().lower()


def agrupar_microfonos(entradas: list[dict]) -> list[dict]:
    """`entradas`: [{'indice', 'nombre', 'api'}] de sounddevice (solo dispositivos con canales de entrada)."""
    grupos: dict[str, list[dict]] = {}
    for e in entradas:
        grupos.setdefault(_clave_nombre(e["nombre"]), []).append(e)
    salida = []
    for clave, miembros in grupos.items():
        nombre = max((m["nombre"] for m in miembros), key=len)
        motivo = next((m for patron, m in NO_SIRVE if patron.search(nombre)), None)
        usable = sorted((m for m in miembros if m["api"] in PREFERENCIA_API), key=lambda m: PREFERENCIA_API.index(m["api"]))
        if not motivo and not usable:
            motivo = "Solo tiene acceso directo (WDM-KS), que el sistema aún no usa."
        salida.append({
            "clave": f"audio:{clave}", "tipo": "audio", "nombre": nombre,
            "bluetooth": bool(PATRON_BLUETOOTH.search(nombre)),
            "utilizable": motivo is None, "motivo": motivo,
            "indice": usable[0]["indice"] if usable else None,
        })
    return sorted(salida, key=lambda m: (not m["utilizable"], m["nombre"].lower()))


def camaras_locales(probadas: list[dict]) -> list[dict]:
    """`probadas`: [{'indice', 'resolucion'}] de las cámaras que abrieron y entregaron imagen."""
    return [{"clave": f"camara:local:{c['indice']}", "tipo": "camara", "nombre": f"Cámara local {c['indice']} ({c['resolucion']})",
             "bluetooth": False, "utilizable": True, "motivo": None, "indice": c["indice"]} for c in probadas]


def inventario(camaras: bool = True, max_camaras: int = 5) -> dict:
    """Escanea el hardware de este equipo. Con cámaras tarda 1–4 s; solo audio es instantáneo."""
    from .captura import listar_fuentes
    crudo = listar_fuentes(max_camaras if camaras else 0)
    return {"microfonos": agrupar_microfonos(crudo["microfonos"]), "camaras": camaras_locales(crudo["camaras"])}


def resolver_microfono(clave: str, inv: dict) -> int | None:
    """Índice actual de sounddevice para una clave (los índices cambian al conectar/desconectar equipos)."""
    m = next((x for x in inv.get("microfonos", []) if x["clave"] == clave and x["utilizable"]), None)
    return m["indice"] if m else None
