"""Cifrado de las direcciones de cámaras (pueden llevar usuario y clave).

Fernet (AES-128-CBC + HMAC-SHA256, de la librería `cryptography`) con una clave derivada de
SECRET_KEY mediante HKDF-SHA256. Si SECRET_KEY cambia o se pierde, el HMAC no coincide:
`descifrar` lanza `NoSePuedeDescifrar` y la API lo informa sin caerse.
"""
import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from . import config

MENSAJE_CLAVE_CAMBIO = ("No se puede leer la dirección guardada: la clave del sistema (SECRET_KEY) cambió o se perdió. "
                        "Vuelva a agregar la cámara con su dirección.")


class NoSePuedeDescifrar(Exception):
    pass


def _fernet(secreto: str | None = None) -> Fernet:
    clave = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"vigilancia-udh", info=b"direcciones-camaras").derive(
        (secreto or config.SECRET_KEY).encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(clave))


def cifrar(texto: str, secreto: str | None = None) -> str:
    return _fernet(secreto).encrypt(texto.encode("utf-8")).decode("ascii")


def descifrar(token: str, secreto: str | None = None) -> str:
    try:
        return _fernet(secreto).decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError):
        raise NoSePuedeDescifrar(MENSAJE_CLAVE_CAMBIO) from None
