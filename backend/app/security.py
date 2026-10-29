import hashlib, hmac, os, base64
from datetime import datetime, timedelta, timezone
import jwt
from . import config

ALG = "HS256"


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(h).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        _, s, h = stored.split("$")
        salt, expected = base64.b64decode(s), base64.b64decode(h)
    except ValueError:
        return False
    got = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return hmac.compare_digest(got, expected)


def make_token(usuario: str, rol: str, nombre: str) -> tuple[str, int]:
    exp = datetime.now(timezone.utc) + timedelta(minutes=config.TOKEN_MINUTES)
    tok = jwt.encode({"sub": usuario, "rol": rol, "nombre": nombre, "exp": exp}, config.SECRET_KEY, algorithm=ALG)
    return tok, config.TOKEN_MINUTES * 60


def read_token(token: str) -> dict:
    return jwt.decode(token, config.SECRET_KEY, algorithms=[ALG])
