// Cliente de la API. El token vive en sessionStorage: se borra al cerrar la pestaña.
const KEY = "vigilancia.sesion";

export function sesion() {
  try { return JSON.parse(sessionStorage.getItem(KEY)); } catch { return null; }
}
export function guardarSesion(s) {
  try { s ? sessionStorage.setItem(KEY, JSON.stringify(s)) : sessionStorage.removeItem(KEY); } catch { /* sin almacenamiento */ }
}

export class ApiError extends Error {
  constructor(status, mensaje, solucion) { super(mensaje); this.status = status; this.solucion = solucion; }
}

export async function api(ruta, { metodo = "GET", cuerpo, token } = {}) {
  const cab = { "Content-Type": "application/json" };
  if (token) cab.Authorization = "Bearer " + token;
  let r;
  try {
    r = await fetch("/api/v1" + ruta, { method: metodo, headers: cab, body: cuerpo ? JSON.stringify(cuerpo) : undefined });
  } catch {
    throw new ApiError(0, "No hay conexión con el servidor.", "Revise que el sistema esté encendido y vuelva a intentar.");
  }
  if (r.ok) return r.status === 204 ? null : r.json();
  let d = {};
  try { d = (await r.json()).detail || {}; } catch { /* sin cuerpo */ }
  if (Array.isArray(d)) d = { mensaje: "Hay datos que no son válidos.", solucion: "Revise los campos e intente de nuevo." };
  throw new ApiError(r.status, d.mensaje || "No se pudo completar la acción.", d.solucion || "Intente de nuevo.");
}
