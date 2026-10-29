"""Cliente HTTP del edge hacia la API (clave X-Api-Key de data/.ingest_key)."""
from datetime import datetime, timezone

import httpx


class ClienteApi:
    def __init__(self, base: str, clave: str, timeout: float = 5.0, transporte=None):
        kw = {"transport": transporte} if transporte else {}
        self.http = httpx.Client(base_url=base.rstrip("/"), headers={"X-Api-Key": clave}, timeout=timeout, **kw)

    def _ok(self, r: httpx.Response) -> dict:
        if r.is_error:
            try:
                d = r.json().get("detail", {})
                texto = f"{d.get('mensaje')} {d.get('solucion')}" if isinstance(d, dict) else str(d)
            except ValueError:
                texto = r.text[:200]
            raise RuntimeError(f"API {r.status_code}: {texto}")
        return r.json()

    def registrar(self, nombre: str, tipo: str, zona: str) -> int:
        return self._ok(self.http.post("/api/v1/dispositivos/registro", json={"nombre": nombre, "tipo": tipo, "zona": zona}))["id"]

    def latido(self, disp_id: int, activo: bool = True) -> None:
        """Un reintento inmediato si la conexión reutilizada ya estaba cerrada (WinError 10053/10054):
        el servidor cierra las conexiones inactivas y el latido puede tomar una justo cuando eso ocurre.
        Es seguro repetirlo porque el latido es idempotente."""
        ruta, cuerpo = f"/api/v1/dispositivos/{disp_id}/latido", {"activo": activo}
        try:
            r = self.http.post(ruta, json=cuerpo)
        except (httpx.ReadError, httpx.WriteError, httpx.RemoteProtocolError):
            r = self.http.post(ruta, json=cuerpo)
        self._ok(r)

    def subir(self, nombre: str, datos: bytes, mime: str) -> str:
        return self._ok(self.http.post("/api/v1/evidencias", files={"archivo": (nombre, datos, mime)}))["url"]

    def alerta(self, alerta: dict, evidencia_audio: str | None, evidencia_video: str | None) -> dict:
        cuerpo = {k: alerta[k] for k in ("tipo", "prioridad", "dispositivos", "zona", "confianza", "modalidades")}
        cuerpo["detectado_en"] = datetime.fromtimestamp(alerta["detectado_en"], timezone.utc).isoformat()
        cuerpo.update(origen="edge", evidencia_audio=evidencia_audio, evidencia_video=evidencia_video)
        return self._ok(self.http.post("/api/v1/alertas", json=cuerpo))
