"""Cliente HTTP del edge hacia la API (clave X-Api-Key de data/.ingest_key)."""
from datetime import datetime, timezone

import httpx

from .fusion_compartida import enmascarar_texto


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
            raise RuntimeError(enmascarar_texto(f"API {r.status_code}: {texto}"))
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

    def estado(self) -> dict:
        """Qué fuentes deben estar conectadas y si el panel pidió una búsqueda."""
        return self._ok(self.http.get("/api/v1/edge/estado"))

    def subir_inventario(self, inv: dict) -> None:
        campos = ("clave", "nombre", "bluetooth", "utilizable", "motivo")
        self._ok(self.http.post("/api/v1/edge/inventario", json={k: [{c: x.get(c) for c in campos} for x in inv[k]]
                                                                  for k in ("microfonos", "camaras")}))

    def direccion(self, fuente_id: int) -> str:
        """Dirección completa de una cámara IP (con usuario y clave). Nunca se escribe en consola."""
        return self._ok(self.http.get(f"/api/v1/edge/fuentes/{fuente_id}/direccion"))["direccion"]

    def informar(self, fuente_id: int, ok: bool, error: str | None = None) -> None:
        self._ok(self.http.post(f"/api/v1/edge/fuentes/{fuente_id}/estado", json={"ok": ok, "error": error}))

    def subir(self, nombre: str, datos: bytes, mime: str) -> str:
        return self._ok(self.http.post("/api/v1/evidencias", files={"archivo": (nombre, datos, mime)}))["url"]

    def alerta(self, alerta: dict, evidencia_audio: str | None, evidencia_video: str | None) -> dict:
        cuerpo = {k: alerta[k] for k in ("tipo", "prioridad", "dispositivos", "zona", "confianza", "modalidades")}
        cuerpo["detectado_en"] = datetime.fromtimestamp(alerta["detectado_en"], timezone.utc).isoformat()
        cuerpo.update(origen="edge", evidencia_audio=evidencia_audio, evidencia_video=evidencia_video)
        return self._ok(self.http.post("/api/v1/alertas", json=cuerpo))
