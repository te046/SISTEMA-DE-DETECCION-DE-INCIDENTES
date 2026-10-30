"""Validación y enmascarado de direcciones de cámaras (sin dependencias: lo usan la API y el edge).

Las direcciones RTSP/HTTP pueden llevar usuario y clave (rtsp://usuario:clave@host/ruta) o
parámetros con secretos (?user=…&pwd=…). Todo texto que vaya a consola, errores, excepciones,
auditoría o al panel pasa por `enmascarar_url` / `enmascarar_texto`.
"""
import re
from urllib.parse import quote, urlsplit, urlunsplit

ESQUEMAS = ("rtsp", "rtsps", "http", "https")
MAX_LARGO = 500
_URL_EN_TEXTO = re.compile(r"\b(?:rtsps?|https?)://[^\s'\"<>]+", re.I)


class DireccionInvalida(ValueError):
    """El mensaje es apto para mostrarse: nunca incluye la dirección recibida."""


def validar_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise DireccionInvalida("Escriba la dirección de la cámara.")
    if len(url) > MAX_LARGO:
        raise DireccionInvalida("La dirección es demasiado larga.")
    if any(c.isspace() or ord(c) < 32 for c in url):
        raise DireccionInvalida("La dirección no puede tener espacios.")
    try:
        p = urlsplit(url)
        p.port                                         # valida que el puerto sea numérico
    except ValueError:
        raise DireccionInvalida("La dirección no tiene un formato válido.") from None
    if p.scheme.lower() not in ESQUEMAS:
        raise DireccionInvalida("Use una dirección que empiece por rtsp://, rtsps://, http:// o https://.")
    if not p.hostname:
        raise DireccionInvalida("Falta la IP o el nombre del equipo, por ejemplo rtsp://192.168.1.20:554/stream.")
    return url


def con_credenciales(url: str, usuario: str | None, clave: str | None) -> str:
    """Inserta usuario y clave (escritos en campos aparte del panel) en una dirección ya validada."""
    if not usuario and not clave:
        return url
    p = urlsplit(url)
    if "@" in p.netloc:
        raise DireccionInvalida("La dirección ya trae usuario y clave: déjelos solo en un lugar.")
    cred = quote(usuario or "", safe="") + (":" + quote(clave, safe="") if clave else "")
    return urlunsplit((p.scheme, f"{cred}@{p.netloc}", p.path, p.query, p.fragment))


def tiene_credenciales(url: str) -> bool:
    p = urlsplit(url)
    return bool(p.username or p.password or p.query)


def enmascarar_url(url: str) -> str:
    """rtsp://admin:clave@192.168.1.20:554/s?pwd=x  →  rtsp://***@192.168.1.20:554/s?***"""
    try:
        p = urlsplit(url)
        host = p.netloc.rsplit("@", 1)[-1]             # host[:puerto], también IPv6 entre corchetes
        cred = "***@" if "@" in p.netloc else ""
        consulta = "?***" if p.query else ""
        return f"{p.scheme}://{cred}{host}{p.path}{consulta}"
    except ValueError:
        return "(dirección no válida)"


def enmascarar_texto(texto: str) -> str:
    """Enmascara cualquier dirección dentro de un mensaje (errores de OpenCV, excepciones, etc.)."""
    return _URL_EN_TEXTO.sub(lambda m: enmascarar_url(m.group(0)), str(texto))
