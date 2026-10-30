import { api, archivo, descargar, ApiError, sesion, guardarSesion } from "./api.js";
import { horaAlerta } from "./tiempo.js";

const $app = document.getElementById("app");
const PRIO = { 1: "Alta", 2: "Media", 3: "Baja" };
const POLL_MS = 1000;       // con 4 s la alerta podía tardar hasta 4 s más en verse (RNF-01). Etapa 5: SSE o WebSocket.

const S = {
  ses: sesion(),            // {token, usuario:{nombre,rol,usuario}}
  pantalla: "login",
  cargando: false,
  alertas: [], ind: null, devs: [], incs: [],
  filtro: 0, selId: null, clics: 0, ultimosClics: null,
  msg: null, ayuda: false, errLogin: "", verClave: false, reproduciendo: false,
  vistas: new Set(), usuarioCampo: "", claveCampo: "",
  medios: {},               // url de evidencia -> "cargando" | "error" | blob:
  fuentes: null,            // respuesta de GET /fuentes
  zonaNueva: "Zona 1", ocupado: null, errRed: "",
  red: { nombre: "", clase: "ip", direccion: "", usuario: "", zona: "Zona 1" },   // sin clave: se lee del campo al guardar
};
const ZONAS = ["Zona 1", "Zona 2", "Zona 3", "Zona 4"];
const TIPOS_EVENTO = ["grito", "rotura de vidrio", "choque", "disparo", "voces elevadas", "posible agresión", "otro"];
Object.assign(S, { med: null, origenExp: "", errEvento: "", evento: { inicio: "", fin: "", zona: "Zona 1", tipo: "posible agresión", nota: "" } });

const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = (n) => (n === null || n === undefined ? "—" : String(n).replace(".", ",") + " %");
const num = (n, u = "") => (n === null || n === undefined ? "—" : String(n).replace(".", ",") + u);
const hora = (iso) => horaAlerta(iso);
const lugar = (a) => `${a.dispositivos} · ${a.zona}`;

const ICON = {
  alertas: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.9 1.9 0 0 0 3.4 0"/>',
  incidentes: '<path d="M9 11l3 3 8-8"/><path d="M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h9"/>',
  indicadores: '<path d="M4 20V10"/><path d="M10 20V4"/><path d="M16 20v-7"/><path d="M22 20H2"/>',
  estado: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8"/><path d="M12 16v4"/>',
  buscar: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
  camara: '<path d="M15 10l5-3v10l-5-3"/><rect x="3" y="6" width="12" height="12" rx="2"/>',
  audio: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/>',
  medicion: '<path d="M9 11l3 3 8-8"/><path d="M4 4h10"/><path d="M4 9h5"/><path d="M4 14h5"/><path d="M4 19h16"/>',
};
const svg = (k) => `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICON[k]}</svg>`;

// ---------------------------------------------------------------- acciones
function msg(texto, tipo = "ok", deshacerId = null) { S.msg = { texto, tipo, deshacerId }; }

async function llamar(ruta, opts) {
  try {
    return await api(ruta, { ...opts, token: S.ses?.token });
  } catch (e) {
    if (e instanceof ApiError && e.status === 401 && S.ses) { cerrarSesion("Su sesión terminó. Vuelva a iniciar sesión."); }
    throw e;
  }
}

function cerrarSesion(aviso = "") {
  Object.values(S.medios).forEach((u) => u.startsWith("blob:") && URL.revokeObjectURL(u)); S.medios = {};
  guardarSesion(null); S.ses = null; S.pantalla = "login"; S.errLogin = aviso; S.msg = null; detenerPoll(); render();
}

async function iniciarSesion() {
  const usuario = S.usuarioCampo.trim(), clave = S.claveCampo;
  if (!usuario) { S.errLogin = "Escriba su usuario. Es el nombre con el que se registró en el sistema."; return render(); }
  if (!clave) { S.errLogin = "Escriba su contraseña. Si la olvidó, pida su restablecimiento a la Oficina de Sistemas."; return render(); }
  S.errLogin = ""; S.cargando = true; render();
  try {
    const r = await api("/auth/token", { metodo: "POST", cuerpo: { usuario, clave } });
    S.ses = { token: r.access_token, usuario: r.usuario }; guardarSesion(S.ses);
    S.claveCampo = ""; S.pantalla = "panel";
    await cargarPanel(true); iniciarPoll();
  } catch (e) {
    S.cargando = false; S.errLogin = e.message + (e.solucion ? " " + e.solucion : ""); render();
  }
}

async function cargarPanel(primera = false) {
  S.cargando = primera;
  if (primera) render();
  try {
    const [alertas, ind, devs] = await Promise.all([
      llamar("/alertas?estado=pendiente"), llamar("/indicadores"), llamar("/dispositivos"),
    ]);
    const nuevas = alertas.filter((a) => !S.vistas.has(a.id));
    if (!primera && nuevas.length) anunciar(`Nueva alerta ${nuevas[0].codigo}: ${nuevas[0].tipo}, prioridad ${PRIO[nuevas[0].prioridad]}.`);
    alertas.forEach((a) => S.vistas.add(a.id));
    const cambio = JSON.stringify([alertas, ind, devs]) !== JSON.stringify([S.alertas, S.ind, S.devs]);
    S.alertas = alertas; S.ind = ind; S.devs = devs; S.cargando = false;
    if (primera || cambio) render();
    marcarMostradas(alertas);
  } catch (e) {
    S.cargando = false;
    if (S.ses) { msg(e.message + " " + (e.solucion || ""), "err"); render(); }
  }
}

// «I1 visible»: avisa a la API la primera vez que una alerta queda pintada en la cola. La hora la pone el
// servidor al recibir el aviso (no el reloj de este equipo). Solo cuenta si la pantalla de alertas está a la vista.
const marcadas = new Set();
function marcarMostradas(alertas) {
  if (S.pantalla !== "panel" || document.hidden) return;
  alertas.filter((a) => !a.mostrado_en && !marcadas.has(a.id)).forEach((a) => {
    marcadas.add(a.id);
    llamar(`/alertas/${a.id}/mostrada`, { metodo: "POST" }).catch(() => marcadas.delete(a.id));   // reintenta en el próximo sondeo
  });
}

function anunciar(texto) { const r = document.getElementById("anuncio"); if (r) { r.textContent = ""; setTimeout(() => (r.textContent = texto), 50); } }

async function resolver(accion) {
  const a = actual(); if (!a) return;
  try {
    await llamar(`/alertas/${a.id}/resolucion`, { metodo: "POST", cuerpo: { accion, clics: S.clics + 1 } });
    S.ultimosClics = S.clics + 1; S.clics = 0; S.selId = null; S.reproduciendo = false;
    msg(accion === "confirmar" ? `Alerta ${a.codigo} confirmada y registrada como incidente.` : `Alerta ${a.codigo} descartada como falsa alarma.`, "ok", a.id);
  } catch (e) { msg(e.message + " " + (e.solucion || ""), "err"); }
  await cargarPanel();
  render();
}

async function deshacer() {
  const id = S.msg?.deshacerId; if (!id) return;
  try {
    const a = await llamar(`/alertas/${id}/deshacer`, { metodo: "POST" });
    S.selId = id; msg(`Acción deshecha: la alerta ${a.codigo} volvió a pendientes.`, "ok");
  } catch (e) { msg(e.message + " " + (e.solucion || ""), "err"); }
  await cargarPanel(); render();
}

async function ir(p) {
  S.pantalla = p; S.msg = null;
  render();
  try {
    if (p === "incidentes") S.incs = await llamar("/incidentes");
    if (p === "indicadores") S.ind = await llamar("/indicadores");
    if (p === "estado") S.devs = await llamar("/dispositivos");
    if (p === "dispositivos") S.fuentes = await llamar("/fuentes");
    if (p === "medicion") await cargarMedicion();
    if (p === "panel") await cargarPanel();
  } catch (e) { msg(e.message + " " + (e.solucion || ""), "err"); }
  render();
}

// ---------------------------------------------------------------- buscar dispositivos
const pausa = (ms) => new Promise((r) => setTimeout(r, ms));

async function cargarFuentes() {
  try { S.fuentes = await llamar("/fuentes"); } catch (e) { msg(e.message + " " + (e.solucion || ""), "err"); }
}

async function buscarDispositivos() {
  try {
    await llamar("/fuentes/buscar", { metodo: "POST" });
    S.fuentes = { ...(S.fuentes || { fuentes: [] }), buscando: true }; S.msg = null; render();
    for (let i = 0; i < 18 && S.pantalla === "dispositivos"; i++) {      // el edge responde en ≤ 2 s + escaneo
      await pausa(1000);
      await cargarFuentes();
      if (!S.fuentes?.buscando) break;
    }
  } catch (e) { msg(e.message + " " + (e.solucion || ""), "err"); }
  render();
}

async function accionFuente(clave, fn) {
  S.ocupado = clave; render();
  try { await fn(); await cargarFuentes(); S.msg = null; }
  catch (e) { msg(e.message + " " + (e.solucion || ""), "err"); }
  S.ocupado = null; render();
}

const conectarLocal = (clave) => accionFuente(clave, () => llamar("/fuentes/locales", { metodo: "POST", cuerpo: { clave, zona: S.zonaNueva } }));
const conectarFuente = (id, clave) => accionFuente(clave, () => llamar(`/fuentes/${id}/conectar`, { metodo: "POST" }));
const desconectarFuente = (id, clave) => accionFuente(clave, () => llamar(`/fuentes/${id}/desconectar`, { metodo: "POST" }));

async function agregarRed() {
  const r = S.red;
  if (!r.nombre.trim()) { S.errRed = "Escriba un nombre, por ejemplo «Cámara pasillo»."; return render(); }
  if (!r.direccion.trim()) { S.errRed = "Escriba la dirección, por ejemplo rtsp://192.168.1.20:554/stream."; return render(); }
  S.errRed = ""; S.ocupado = "red"; render();
  const clave = document.getElementById("red-pwd")?.value || null;   // la clave no se guarda en el estado del panel
  try {
    const f = await llamar("/fuentes/red", { metodo: "POST", cuerpo: { ...r, usuario: r.usuario || null, clave } });
    S.red = { nombre: "", clase: "ip", direccion: "", usuario: "", zona: r.zona };
    await cargarFuentes();
    msg(`«${f.nombre}» guardada. Pulse «Conectar» cuando quiera usarla.`, "ok");
  } catch (e) { S.errRed = e.message + " " + (e.solucion || ""); }
  S.ocupado = null; render();
}

// ---------------------------------------------------------------- medición: etiquetado, eventos reales y CSV
async function cargarMedicion() {
  const [metricas, eventos, alertas] = await Promise.all([
    llamar("/metricas" + (S.origenExp ? "?origen=" + S.origenExp : "")), llamar("/eventos-reales"), llamar("/alertas"),
  ]);
  alertas.sort((a, b) => (a.generado_en < b.generado_en ? 1 : -1));
  S.med = { metricas, eventos, alertas: alertas.filter((a) => !S.origenExp || a.origen === S.origenExp).slice(0, 60) };
}

async function accionMedicion(fn, texto) {
  try { await fn(); await cargarMedicion(); if (texto) msg(texto, "ok"); else S.msg = null; }
  catch (e) { msg(e.message + " " + (e.solucion || ""), "err"); }
  render();
}

const etiquetar = (id, verdad) => accionMedicion(() => llamar(`/alertas/${id}/verdad`, { metodo: "PUT", cuerpo: { verdad } }));

function aIso(local) { const d = new Date(local); return Number.isNaN(d.getTime()) ? null : d.toISOString(); }   // hora local → UTC con zona

async function crearEvento() {
  const e = S.evento, inicio = aIso(e.inicio), fin = aIso(e.fin);
  if (!inicio || !fin) { S.errEvento = "Indique la hora de inicio y de fin del evento."; return render(); }
  if (fin < inicio) { S.errEvento = "El fin no puede ser anterior al inicio."; return render(); }
  S.errEvento = "";
  await accionMedicion(() => llamar("/eventos-reales", { metodo: "POST", cuerpo: { inicio, fin, zona: e.zona, tipo: e.tipo, nota: e.nota || null } }),
    "Evento real registrado.");
  S.evento = { ...S.evento, inicio: "", fin: "", nota: "" }; render();
}

function borrarEvento(id) {
  if (!window.confirm("¿Borrar este evento real? Se quitará del cálculo del recall.")) return;
  accionMedicion(() => llamar(`/eventos-reales/${id}`, { metodo: "DELETE" }), "Evento borrado.");
}

async function exportar(tipo) {
  const ruta = tipo === "alertas" ? "/exportar/alertas.csv" + (S.origenExp ? "?origen=" + S.origenExp : "") : "/exportar/eventos_reales.csv";
  const nombre = (tipo === "alertas" ? `alertas_${S.origenExp || "todas"}` : "eventos_reales") + `_${new Date().toISOString().slice(0, 10)}.csv`;
  try { await descargar(ruta, S.ses?.token, nombre); msg(`Exportado: ${nombre}`, "ok"); }
  catch (e) { msg(e.message + " " + (e.solucion || ""), "err"); }
  render();
}

async function alternarDispositivo(id, activo) {
  try { await llamar(`/dispositivos/${id}`, { metodo: "PATCH", cuerpo: { activo } }); S.devs = await llamar("/dispositivos"); S.msg = null; }
  catch (e) { msg(e.message + " " + (e.solucion || ""), "err"); }
  render();
}

// ---------------------------------------------------------------- vistas
const lista = () => (S.filtro ? S.alertas.filter((a) => a.prioridad === S.filtro) : S.alertas);
const actual = () => { const l = lista(); return l.find((a) => a.id === S.selId) || l[0] || null; };

function vMsg() {
  if (!S.msg) return "";
  return `<div class="msg ${S.msg.tipo === "err" ? "err" : ""}"><strong>${S.msg.tipo === "err" ? "Revise." : "Listo."}</strong>
    <span style="flex-grow:1">${esc(S.msg.texto)}</span>
    ${S.msg.deshacerId ? '<button class="btn btn-ghost" style="min-height:44px;padding:6px 16px" data-a="deshacer">Deshacer</button>' : ""}
    <button class="btn-link" data-a="cerrar-msg" aria-label="Cerrar mensaje">Cerrar</button></div>`;
}

function vLogin() {
  return `<div class="wrap"><main id="contenido"><section class="login">
    <img src="logo-udh.png" alt="Universidad de Huánuco">
    <div class="card"><h1>Iniciar sesión</h1><p class="lbl" style="margin:0 0 24px">Vea las alertas de su turno.</p>
    <form class="col" id="f-login" novalidate>
      <div class="field"><label for="usr">Usuario</label>
        <input id="usr" type="text" autocomplete="username" value="${esc(S.usuarioCampo)}" aria-describedby="usr-h"><span id="usr-h" class="lbl">Ejemplo: responsable.vigilancia</span></div>
      <div class="field"><label for="pwd">Contraseña</label>
        <input id="pwd" type="${S.verClave ? "text" : "password"}" autocomplete="current-password" value="${esc(S.claveCampo)}">
        <div class="check"><input id="chk" type="checkbox" ${S.verClave ? "checked" : ""}><label for="chk">Mostrar contraseña</label></div></div>
      ${S.errLogin ? `<div role="alert" class="err-box"><strong>No se pudo iniciar sesión.</strong> ${esc(S.errLogin)}</div>` : ""}
      <button type="submit" class="btn btn-primary" style="font-size:18px" ${S.cargando ? "disabled" : ""}>${S.cargando ? "Ingresando…" : "Ingresar"}</button>
    </form></div>
    <p class="lbl" style="margin:0;text-align:center">Tras 5 intentos fallidos, la cuenta se bloquea 15 minutos.</p>
  </section></main></div>`;
}

function vShell(titulo, contenido) {
  const n = S.alertas.length, u = S.ses.usuario;
  const nav = (id, txt, ic, extra = "") => `<button class="nav-i" data-nav="${id}" ${S.pantalla === id ? 'aria-current="page"' : ""}>${svg(ic)}<span class="grow">${txt}</span>${extra}</button>`;
  const ini = u.nombre.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  return `<aside class="side"><img src="logo-udh.png" alt="Universidad de Huánuco">
    <div><div style="font-weight:800;font-size:18px;line-height:1.25">Vigilancia multimodal</div><div class="lbl">Segundo pabellón</div></div>
    <nav aria-label="Menú principal">${nav("panel", "Alertas", "alertas", n ? `<span class="badge">${n}</span>` : "")}${nav("incidentes", "Incidentes", "incidentes")}${nav("indicadores", "Indicadores", "indicadores")}${nav("estado", "Estado del sistema", "estado")}${nav("dispositivos", "Buscar dispositivos", "buscar")}${nav("medicion", "Medición", "medicion")}</nav>
    <div class="note"><b>Sistema v1.0</b><span class="lbl">Las alertas «simuladas» se marcan como tales.</span></div></aside>
    <div class="wrap">
    <header class="topbar"><p class="lbl" style="margin:0">Inicio › ${esc(titulo)}</p>
      <div class="right"><button class="btn-link" data-a="ayuda" aria-expanded="${S.ayuda}">Ayuda</button>
      <span class="user"><span class="avatar" aria-hidden="true">${esc(ini)}</span>${esc(u.nombre)}</span><button class="btn-link" data-a="salir">Salir</button></div></header>
    <main id="contenido"><div role="status" aria-live="polite">${vMsg()}</div>${contenido}</main>
    <footer><span>Universidad de Huánuco · Ingeniería de Sistemas e Informática</span><span>M06 Panel web de alertas · v1.0</span></footer></div>`;
}

// Las evidencias exigen sesión: se descargan con el token y se muestran como blob: (se piden una sola vez).
function medio(url) {
  if (!url.startsWith("/api/v1/evidencias/")) return url;
  if (!(url in S.medios)) {
    S.medios[url] = "cargando";
    archivo(url, S.ses?.token).then((b) => { S.medios[url] = b; }).catch(() => { S.medios[url] = "error"; }).finally(render);
  }
  return S.medios[url];
}

function reproductor(tipo, url, a) {
  const src = medio(url), nombre = tipo === "video" ? "Video" : "Audio";
  if (src === "cargando") return `<figure><div class="sin-evidencia" aria-busy="true">Cargando ${nombre.toLowerCase()}…</div><figcaption class="lbl">${nombre}</figcaption></figure>`;
  if (src === "error") return `<figure><div class="sin-evidencia">No se pudo cargar el ${nombre.toLowerCase()}. Vuelva a abrir la alerta; si sigue igual, pudo borrarse por la política de retención.</div><figcaption class="lbl">${nombre}</figcaption></figure>`;
  return `<figure><${tipo} controls preload="metadata" src="${esc(src)}" aria-label="Evidencia de ${nombre.toLowerCase()} de la alerta ${esc(a.codigo)}"></${tipo}><figcaption class="lbl">${nombre} · clip alrededor del evento</figcaption></figure>`;
}

function evidencia(a) {
  const mods = a.modalidades.map((m) => m.modalidad);
  const v = a.evidencia_video, au = a.evidencia_audio;
  let html = "";
  if (v) html += reproductor("video", v, a);
  if (au) html += reproductor("audio", au, a);
  if (!html && a.origen === "simulado") {
    if (mods.includes("video")) html += `<figure><svg viewBox="0 0 320 180" role="img" aria-label="Ilustración simulada de un recuadro de detección"><rect y="120" width="320" height="60" fill="#12403B"/><rect x="28" y="38" width="74" height="82" fill="#12403B"/><rect x="212" y="28" width="82" height="92" fill="#0F3631"/><rect x="128" y="62" width="64" height="84" fill="none" stroke="#FF7A5C" stroke-width="4" rx="4"/><rect x="128" y="38" width="172" height="24" fill="#FF7A5C" rx="4"/><text x="135" y="55" font-size="13" font-family="Plus Jakarta Sans,sans-serif" fill="#0C2B28" font-weight="800">${esc(a.tipo.split(" (")[0].slice(0, 18))} ${Math.round(a.confianza * 100)} %</text></svg><figcaption class="lbl">Video (ilustración simulada)</figcaption></figure>`;
    if (mods.includes("audio")) html += `<figure><svg viewBox="0 0 320 180" role="img" aria-label="Ilustración simulada de una onda de audio"><g fill="#1FB09E">${[20, 40, 10, 60, 30, 80, 120, 140, 100, 70, 110, 50, 24, 10, 36, 16, 6, 20, 8, 12].map((h, i) => `<rect x="${10 + i * 14}" y="${90 - h / 2}" width="8" height="${h}" rx="3"/>`).join("")}</g></svg><figcaption class="lbl">Audio (ilustración simulada)</figcaption></figure>`;
  }
  return html ? `<div class="media">${html}</div>` : `<div class="sin-evidencia">No hay evidencia adjunta en esta alerta.</div>`;
}

function vPanel() {
  const l = lista(), a = actual(), n = (p) => S.alertas.filter((x) => x.prioridad === p).length;
  const off = S.devs.filter((d) => !d.activo);
  const filas = l.map((x) => `<li><button class="row" data-sel="${x.id}" aria-pressed="${a && a.id === x.id}">
    <span class="dot p${x.prioridad}" aria-hidden="true"></span>
    <span class="mid"><span style="font-weight:700">${esc(x.tipo)}</span><span class="lbl">${esc(lugar(x))}</span></span>
    <span class="end"><span class="t${x.prioridad}">${PRIO[x.prioridad]}</span><span class="lbl">${hora(x.generado_en)}</span></span></button></li>`).join("");
  const mods = a ? a.modalidades.map((m) => m.modalidad) : [];
  const por = mods.includes("video") && mods.includes("audio") ? "video y audio" : mods.includes("video") ? "video" : "audio";
  const detalle = a ? `<div class="head"><h2>${esc(a.tipo)}</h2><span class="pill p${a.prioridad}">Prioridad ${PRIO[a.prioridad]}</span></div>
    <div class="lbl" style="padding:2px 24px 0">Alerta ${esc(a.codigo)} · ${esc(lugar(a))} · ${hora(a.generado_en)}${a.origen === "simulado" ? " · simulada" : ""}</div>
    <div class="body">${evidencia(a)}
    <div class="facts"><div><span class="lbl">Confianza </span><strong>${Math.round(a.confianza * 100)} %</strong></div><div><span class="lbl">Detectada por </span><strong>${por}</strong></div>
      ${mods.includes("video") ? '<div><span class="pill neutral" title="Modelo preentrenado sin calibrar con video del pabellón; sin métricas medidas.">Video: línea base</span></div>' : ""}</div>
    <div style="display:flex;flex-direction:column;gap:10px"><div class="actions"><button class="btn btn-primary" data-a="confirmar">Confirmar incidente</button><button class="btn btn-ghost" data-a="descartar">Descartar</button></div>
    <p class="lbl" style="margin:0">Se registra con fecha, hora, zona y tipo. Clics usados: ${S.clics + 1} de 3.</p></div></div>`
    : `<div class="empty lbl">${S.alertas.length ? "Elija una alerta de la lista para ver su evidencia." : "Cuando llegue una alerta, aparecerá aquí."}</div>`;
  const ind = S.ind || {};
  return `<section style="display:flex;flex-direction:column;gap:20px">
    <div><h1 class="h-title">Alertas pendientes</h1><p class="lbl h-sub">Se muestra primero la más urgente</p></div>
    ${S.ayuda ? '<div class="help"><strong>Cómo atender una alerta</strong><ol><li>Abra la primera de la lista.</li><li>Compare el video y el audio.</li><li>Pulse <strong>Confirmar incidente</strong> o <strong>Descartar</strong>. Puede deshacerlo.</li></ol></div>' : ""}
    ${off.length ? `<div role="alert" class="warn"><strong>Atención:</strong> ${esc(off.map((d) => d.nombre + " está desconectado.").join(" "))} Esa zona usará solo la evidencia disponible.</div>` : ""}
    <div class="stats"><div class="card stat" style="border-top-color:var(--acc)"><div class="lbl">Pendientes</div><div class="n">${S.alertas.length}</div></div>
      <div class="card stat" style="border-top-color:var(--green)"><div class="lbl">Confirmadas</div><div class="n">${ind.confirmadas ?? 0}</div></div>
      <div class="card stat" style="border-top-color:#B7CAC5"><div class="lbl">Descartadas</div><div class="n">${ind.descartadas ?? 0}</div></div>
      <div class="card stat" style="border-top-color:var(--brand)"><div class="lbl">Clics de la última acción</div><div class="n">${S.ultimosClics ?? "—"} <span class="lbl" style="font-size:16px;font-weight:600">meta ≤ 3</span></div></div></div>
    <div class="split"><div class="card list"><header><h2>Cola de alertas</h2>
      <div class="seg" role="group" aria-label="Filtrar por prioridad">${[[0, "Todas", S.alertas.length], [1, "Alta", n(1)], [2, "Media", n(2)], [3, "Baja", n(3)]].map(([f, t, c]) => `<button data-f="${f}" aria-pressed="${S.filtro === f}">${t} ${c}</button>`).join("")}</div></header>
      ${S.alertas.length === 0 ? '<div class="empty"><b>Todo al día</b><span class="lbl">No hay alertas pendientes. El sistema sigue monitoreando.</span></div>' : l.length === 0 ? '<div class="lbl" style="padding:20px">No hay alertas con esta prioridad. Pulse «Todas» para ver el resto.</div>' : `<ul class="rows">${filas}</ul>`}</div>
    <div class="card detail">${detalle}</div></div></section>`;
}

function vIncidentes() {
  const filas = S.incs.map((i) => `<tr><td style="font-weight:700">${esc(i.codigo)} (${esc(i.alerta)})</td><td>${esc(i.fecha)}</td><td>${esc(i.hora)}</td><td>${esc(i.lugar)}</td><td>${esc(i.tipo)}</td></tr>`).join("");
  return `<section style="display:flex;flex-direction:column;gap:20px"><div><h1 class="h-title">Incidentes</h1><p class="lbl h-sub">Alertas confirmadas</p></div>
    <div class="card" style="overflow:hidden">${S.incs.length ? "" : '<div class="empty"><b>Aún no hay incidentes</b><span class="lbl" style="display:block;margin:6px 0 18px">Al confirmar una alerta aparecerá aquí.</span><button class="btn btn-primary" data-nav="panel">Ir a las alertas</button></div>'}
    <div class="tw"><table style="min-width:600px"><caption class="sr">Alertas confirmadas como reales</caption><thead><tr><th scope="col">Incidente</th><th scope="col">Fecha</th><th scope="col">Hora</th><th scope="col">Cámara / zona</th><th scope="col">Tipo</th></tr></thead><tbody>${filas}</tbody></table></div></div></section>`;
}

function vIndicadores() {
  const i = S.ind || {};
  const k = (t, v, extra) => `<div class="card kpi"><div class="lbl">${t}</div><div class="n">${v}</div>${extra}</div>`;
  return `<section style="display:flex;flex-direction:column;gap:20px"><div><h1 class="h-title">Indicadores</h1>
    <p class="lbl h-sub" style="max-width:760px">Calculados con las marcas de tiempo y las decisiones registradas. Los valores de la tesis se toman en el pretest y el postest.</p></div>
    <div class="kpis">
    ${k("I1 · Detección (hasta el servidor)", num(i.I1_ttd_s, " s"), i.I1_cumple_rnf01 === null || i.I1_cumple_rnf01 === undefined ? '<span class="pill neutral">Sin datos</span>' : `<span class="pill ${i.I1_cumple_rnf01 >= 95 ? "ok" : "off"}">${pct(i.I1_cumple_rnf01)} de alertas en ≤ 5 s</span>`)}
    ${k("I1 visible · hasta el panel", num(i.I1_visible_s, " s"), i.I1_visible_cumple_rnf01 === null || i.I1_visible_cumple_rnf01 === undefined ? '<span class="pill neutral">Sin datos</span>' : `<span class="pill ${i.I1_visible_cumple_rnf01 >= 95 ? "ok" : "off"}">${pct(i.I1_visible_cumple_rnf01)} visibles en ≤ 5 s</span>`)}
    ${i.alertas_con_panel_cerrado ? `<div class="lbl" style="grid-column:1/-1;margin-top:-8px">${i.alertas_con_panel_cerrado} alertas llegaron con el panel cerrado: no cuentan en «I1 visible».</div>` : ""}
    ${k("I2 · Tiempo de atención", num(i.I2_tta_s, " s"), '<div class="lbl" style="margin-top:10px">Desde que aparece la alerta hasta que se resuelve.</div>')}
    ${k("I3 · Precisión", pct(i.I3_precision_pct), '<div class="lbl" style="margin-top:10px">Confirmadas ÷ resueltas. El recall y el F1 requieren un conjunto etiquetado.</div>')}
    ${k("I4 · Falsas alarmas", pct(i.I4_falsas_alarmas_pct), '<div class="lbl" style="margin-top:10px">Descartadas ÷ resueltas.</div>')}
    ${k("I5 · Satisfacción", "Encuesta", '<div class="lbl" style="margin-top:10px">Cuestionario Likert 1–5, fuera del panel.</div>')}
    ${k("Clics por decisión", num(i.clics_medios), '<div class="lbl" style="margin-top:10px">Meta de diseño: ≤ 3 (RNF-03).</div>')}
    </div></section>`;
}

function vEstado() {
  const puede = S.ses.usuario.rol !== "vigilante";
  const filas = S.devs.map((d) => `<tr><td style="font-weight:700">${esc(d.nombre)}</td><td>${d.tipo === "camara" ? "Cámara" : "Micrófono"}</td><td>${esc(d.zona)}</td>
    <td><span class="pill ${d.activo ? "ok" : "off"}">${d.activo ? "● Activo" : "▲ Desconectado"}</span></td>
    <td>${puede ? `<button class="btn btn-ghost" style="min-height:44px;padding:6px 16px" data-disp="${d.id}" data-activo="${d.activo ? 0 : 1}">${d.activo ? "Marcar desconectado" : "Restablecer"}</button>` : '<span class="lbl">Solo responsables</span>'}</td></tr>`).join("");
  return `<section style="display:flex;flex-direction:column;gap:20px"><div><h1 class="h-title">Estado del sistema</h1><p class="lbl h-sub">Cámaras y nodos de audio</p></div>
    <div class="card" style="overflow:hidden"><div class="tw"><table style="min-width:640px"><caption class="sr">Cámaras y nodos de audio</caption><thead><tr><th scope="col">Dispositivo</th><th scope="col">Tipo</th><th scope="col">Zona</th><th scope="col">Estado</th><th scope="col">Acción</th></tr></thead><tbody>${filas}</tbody></table></div></div>
    <p class="lbl" style="margin:0">Metas de diseño: alerta en ≤ 5 s · disponibilidad ≥ 95 % · confirmar o descartar en ≤ 3 clics.</p></section>`;
}

const ESTADO_FUENTE = {          // el estado nunca solo por color: símbolo + texto
  conectada: ["ok", "● Conectada"], disponible: ["neutral", "○ Disponible"], error: ["off", "▲ Error"], no_sirve: ["neutral", "— No sirve"],
};

function filaFuente(f, puede) {
  const [clase, texto] = ESTADO_FUENTE[f.estado] || ESTADO_FUENTE.disponible;
  const etiquetas = [f.bluetooth ? "Bluetooth" : "", f.clase === "ip" ? "Cámara IP" : f.clase === "telefono" ? "Teléfono" : "", f.zona || ""].filter(Boolean);
  const ocupada = S.ocupado === f.clave;
  let boton = "";
  if (puede && f.estado !== "no_sirve") {
    if (f.conectada) boton = `<button class="btn btn-ghost btn-s" data-desc="${f.id}" data-clave="${esc(f.clave)}" ${ocupada ? "disabled" : ""}>Desconectar</button>`;
    else boton = `<button class="btn btn-primary btn-s" ${f.id ? `data-con="${f.id}"` : ""} data-clave="${esc(f.clave)}" ${ocupada ? "disabled" : ""}>${ocupada ? "Conectando…" : "Conectar"}</button>`;
  }
  return `<li class="dev"><span class="dev-ic" aria-hidden="true">${svg(f.tipo === "camara" ? "camara" : "audio")}</span>
    <span class="mid"><span style="font-weight:700">${esc(f.nombre)}</span>
      ${etiquetas.length ? `<span class="lbl">${esc(etiquetas.join(" · "))}</span>` : ""}
      ${f.direccion ? `<span class="lbl mono">${esc(f.direccion)}</span>` : ""}
      ${f.motivo ? `<span class="${f.estado === "error" ? "dev-err" : "lbl"}">${esc(f.motivo)}</span>` : ""}</span>
    <span class="pill ${clase}">${texto}</span>${boton}</li>`;
}

function vDispositivos() {
  const d = S.fuentes || { fuentes: [], puede_cambiar: false };
  const puede = d.puede_cambiar, todas = d.fuentes || [];
  const cams = todas.filter((f) => f.tipo === "camara"), mics = todas.filter((f) => f.tipo === "audio");
  const opZona = (sel) => ZONAS.map((z) => `<option ${z === sel ? "selected" : ""}>${z}</option>`).join("");
  const lista = (titulo, items, vacio) => `<div class="card dev-list"><h2>${titulo}</h2>${items.length ? `<ul class="devs">${items.map((f) => filaFuente(f, puede)).join("")}</ul>` : vacio}</div>`;
  const sinCamaras = d.ultima_busqueda && !cams.some((f) => f.clase === "local")
    ? `<div class="help"><strong>No se encontró ninguna cámara de este equipo.</strong><ul>
        <li>Abra el obturador o pulse la tecla de cámara del teclado.</li>
        <li>Windows: Configuración › Privacidad › Cámara › permita el acceso a las aplicaciones de escritorio.</li>
        <li>Cierre otras aplicaciones que usen la cámara (Teams, Zoom, Cámara) y pulse «Buscar».</li></ul></div>` : "";
  const avisos = !d.edge_activo
    ? '<div role="alert" class="warn"><strong>El módulo de captura no está abierto.</strong> Ábralo con <b>python -m edge</b> y pulse «Buscar».</div>'
    : d.busqueda_sin_respuesta ? '<div role="alert" class="warn"><strong>La búsqueda no respondió.</strong> Revise que el módulo de captura siga abierto y pulse «Buscar» otra vez.</div>' : "";
  const r = S.red;
  const formRed = puede ? `<div class="card dev-list"><h2>Agregar cámara IP o teléfono</h2>
    <form class="dev-form" id="f-red" novalidate autocomplete="off">
      <div class="field"><label for="red-nombre">Nombre</label><input id="red-nombre" type="text" value="${esc(r.nombre)}" placeholder="Cámara pasillo"></div>
      <div class="field"><label for="red-clase">Tipo</label><select id="red-clase"><option value="ip" ${r.clase === "ip" ? "selected" : ""}>Cámara IP</option><option value="telefono" ${r.clase === "telefono" ? "selected" : ""}>Teléfono como cámara</option></select></div>
      <div class="field wide"><label for="red-dir">Dirección</label><input id="red-dir" type="text" spellcheck="false" value="${esc(r.direccion)}" placeholder="rtsp://192.168.1.20:554/stream" aria-describedby="red-dir-h"><span id="red-dir-h" class="lbl">rtsp, rtsps, http o https. Teléfono: http://IP:puerto/video</span></div>
      <div class="field"><label for="red-usr">Usuario <span class="lbl">(opcional)</span></label><input id="red-usr" type="text" spellcheck="false" autocomplete="off" value="${esc(r.usuario)}"></div>
      <div class="field"><label for="red-pwd">Clave <span class="lbl">(opcional)</span></label><input id="red-pwd" type="password" autocomplete="new-password" value=""></div>
      <div class="field"><label for="red-zona">Zona</label><select id="red-zona">${opZona(r.zona)}</select></div>
      ${S.errRed ? `<div role="alert" class="err-box wide"><strong>No se guardó.</strong> ${esc(S.errRed)}</div>` : ""}
      <div class="wide dev-form-pie"><button type="submit" class="btn btn-primary" ${S.ocupado === "red" ? "disabled" : ""}>${S.ocupado === "red" ? "Guardando…" : "Guardar"}</button>
        <span class="lbl">Se guarda cifrada. Se conecta al pulsar «Conectar».</span></div>
    </form></div>` : "";
  return `<section style="display:flex;flex-direction:column;gap:20px">
    <div class="dev-top"><div><h1 class="h-title">Buscar dispositivos</h1><p class="lbl h-sub">Cámaras y micrófonos disponibles</p></div>
      <div class="dev-acc">${puede ? `<div class="field"><label for="zona-nueva">Conectar en</label><select id="zona-nueva">${opZona(S.zonaNueva)}</select></div>` : ""}
      <button class="btn btn-primary" data-a="buscar" ${d.buscando ? "disabled" : ""}>${d.buscando ? '<span class="spinner spinner-s" aria-hidden="true"></span>Buscando…' : svg("buscar") + "Buscar"}</button></div></div>
    ${avisos}
    ${d.buscando ? '<p class="lbl" role="status" style="margin:0">Buscando cámaras y micrófonos… puede tardar unos segundos.</p>' : ""}
    ${!todas.length && !d.buscando ? '<div class="card empty"><b>Aún no hay dispositivos en la lista</b><span class="lbl">Pulse «Buscar» para ver las cámaras y los micrófonos.</span></div>' : ""}
    ${todas.length ? lista("Cámaras", cams, '<p class="lbl" style="margin:0">Ninguna en la lista.</p>') : ""}${sinCamaras}
    ${todas.length ? lista("Micrófonos", mics, '<p class="lbl" style="margin:0">Ninguno en la lista.</p>') : ""}
    ${todas.length ? '<p class="lbl" style="margin:0">Los Bluetooth se emparejan en Windows; aquí aparecen solo los de audio.</p>' : ""}
    ${formRed}
    ${puede ? "" : '<p class="lbl" style="margin:0">Solo responsables y administradores pueden conectar dispositivos.</p>'}</section>`;
}

function vMedicion() {
  const d = S.med || { metricas: {}, eventos: [], alertas: [] }, m = d.metricas || {};
  const puede = S.ses.usuario.rol !== "vigilante";
  const opZona = (sel) => ZONAS.map((z) => `<option ${z === sel ? "selected" : ""}>${z}</option>`).join("");
  const verdad = { real: ["ok", "● Real"], falsa: ["off", "▲ Falsa"] };
  const filasAlertas = d.alertas.map((a) => {
    const [c, t] = verdad[a.verdad] || ["neutral", "○ Sin etiqueta"];
    const btn = (v, txt) => `<button class="btn ${a.verdad === v ? "btn-primary" : "btn-ghost"} btn-s" data-verdad="${v ?? ""}" data-id="${a.id}" aria-pressed="${a.verdad === v}">${txt}</button>`;
    return `<tr><td style="font-weight:700">${esc(a.codigo)}</td><td>${esc(a.tipo)}</td><td>${esc(a.zona)}</td><td>${hora(a.detectado_en)}</td>
      <td>${esc(a.origen)}</td><td><span class="pill ${c}">${t}</span></td>
      <td>${puede ? `<div class="acc-fila">${btn("real", "Real")}${btn("falsa", "Falsa")}${a.verdad ? btn(null, "Quitar") : ""}</div>` : '<span class="lbl">Solo responsables</span>'}</td></tr>`;
  }).join("");
  const filasEventos = d.eventos.map((e) => `<tr><td>${hora(e.inicio)} – ${hora(e.fin)}</td><td>${esc(e.zona)}</td><td>${esc(e.tipo)}</td><td>${esc(e.nota || "")}</td>
      <td>${puede ? `<button class="btn btn-ghost btn-s" data-borrar-evento="${e.id}">Borrar</button>` : ""}</td></tr>`).join("");
  const ev = S.evento;
  const kpi = (t, v, extra) => `<div class="card kpi"><div class="lbl">${t}</div><div class="n">${v}</div><div class="lbl" style="margin-top:10px">${extra}</div></div>`;
  return `<section style="display:flex;flex-direction:column;gap:20px">
    <div class="dev-top"><div><h1 class="h-title">Medición</h1><p class="lbl h-sub">Verdad de campo, métricas y exportación para la tesis</p></div>
      <div class="dev-acc"><div class="field"><label for="origen-exp">Alertas</label><select id="origen-exp">
        <option value="" ${!S.origenExp ? "selected" : ""}>Todas</option><option value="edge" ${S.origenExp === "edge" ? "selected" : ""}>Reales (edge)</option>
        <option value="simulado" ${S.origenExp === "simulado" ? "selected" : ""}>Simuladas</option></select></div>
        <button class="btn btn-primary" data-exportar="alertas">Exportar alertas (CSV)</button>
        <button class="btn btn-ghost" data-exportar="eventos">Exportar eventos reales (CSV)</button></div></div>
    <div class="kpis">
      ${kpi("Precisión etiquetada", pct(m.precision_etiquetada_pct), `${m.alertas_reales ?? 0} reales de ${m.alertas_etiquetadas ?? 0} etiquetadas · ${m.alertas_sin_etiqueta ?? 0} sin etiqueta`)}
      ${kpi("Recall", pct(m.recall_pct), `${m.eventos_detectados ?? 0} de ${m.eventos_reales ?? 0} eventos reales con alerta`)}
      ${kpi("F1", pct(m.f1_pct), "Media armónica de precisión y recall")}
    </div>
    <p class="lbl" style="margin:0">Solo se calculan con alertas etiquetadas y eventos reales registrados (${esc(m.regla_emparejamiento || "")}). Son métricas de la tesis solo con un conjunto de prueba suficiente; I3 e I4 siguen usando la decisión del vigilante.</p>
    <div class="card dev-list"><h2>Alertas por etiquetar</h2><p class="lbl" style="margin:0">¿Ocurrió de verdad lo que avisó la alerta? Últimas 60.</p>
      ${d.alertas.length ? `<div class="tw"><table style="min-width:760px"><caption class="sr">Alertas y su etiqueta de verdad de campo</caption><thead><tr><th scope="col">Alerta</th><th scope="col">Tipo</th><th scope="col">Zona</th><th scope="col">Detectada</th><th scope="col">Origen</th><th scope="col">Etiqueta</th><th scope="col">Acción</th></tr></thead><tbody>${filasAlertas}</tbody></table></div>`
        : '<p class="lbl" style="margin:0">Aún no hay alertas.</p>'}</div>
    <div class="card dev-list"><h2>Eventos reales</h2><p class="lbl" style="margin:0">Lo que de verdad ocurrió (por ejemplo, la cronología de la prueba en vivo). Sirve para el recall.</p>
      ${puede ? `<form class="dev-form" id="f-evento" novalidate>
        <div class="field"><label for="ev-ini">Inicio</label><input id="ev-ini" type="datetime-local" step="1" value="${esc(ev.inicio)}"></div>
        <div class="field"><label for="ev-fin">Fin</label><input id="ev-fin" type="datetime-local" step="1" value="${esc(ev.fin)}"></div>
        <div class="field"><label for="ev-zona">Zona</label><select id="ev-zona">${opZona(ev.zona)}</select></div>
        <div class="field"><label for="ev-tipo">Tipo</label><select id="ev-tipo">${TIPOS_EVENTO.map((t) => `<option ${t === ev.tipo ? "selected" : ""}>${t}</option>`).join("")}</select></div>
        <div class="field wide"><label for="ev-nota">Nota <span class="lbl">(opcional)</span></label><input id="ev-nota" type="text" value="${esc(ev.nota)}" placeholder="Prueba en vivo, tramo 35–50 s"></div>
        ${S.errEvento ? `<div role="alert" class="err-box wide"><strong>No se registró.</strong> ${esc(S.errEvento)}</div>` : ""}
        <div class="wide"><button type="submit" class="btn btn-primary">Registrar evento real</button></div></form>` : ""}
      ${d.eventos.length ? `<div class="tw"><table style="min-width:600px"><caption class="sr">Eventos reales registrados</caption><thead><tr><th scope="col">Hora</th><th scope="col">Zona</th><th scope="col">Tipo</th><th scope="col">Nota</th><th scope="col">Acción</th></tr></thead><tbody>${filasEventos}</tbody></table></div>`
        : '<p class="lbl" style="margin:0">Aún no hay eventos reales registrados.</p>'}</div>
  </section>`;
}

function render() {
  const foco = document.activeElement?.id;
  if (!S.ses) { $app.innerHTML = vLogin(); enlazarLogin(); if (foco) document.getElementById(foco)?.focus(); return; }
  if (S.cargando) { $app.innerHTML = '<div class="wrap"><main id="contenido"><section class="card empty" aria-busy="true"><div class="spinner" aria-hidden="true"></div><b>Cargando alertas del turno…</b><span class="lbl">Conectando con el servidor.</span></section></main></div>'; return; }
  const v = { panel: ["Alertas", vPanel], incidentes: ["Incidentes", vIncidentes], indicadores: ["Indicadores", vIndicadores], estado: ["Estado del sistema", vEstado], dispositivos: ["Buscar dispositivos", vDispositivos], medicion: ["Medición", vMedicion] }[S.pantalla];
  $app.innerHTML = vShell(v[0], v[1]()) + '<div id="anuncio" class="sr" role="status" aria-live="polite"></div>';
  enlazar();
}

function enlazarLogin() {
  const f = document.getElementById("f-login");
  document.getElementById("usr").addEventListener("input", (e) => (S.usuarioCampo = e.target.value));
  document.getElementById("pwd").addEventListener("input", (e) => (S.claveCampo = e.target.value));
  document.getElementById("chk").addEventListener("change", (e) => { S.verClave = e.target.checked; render(); document.getElementById("chk").focus(); });
  f.addEventListener("submit", (e) => { e.preventDefault(); iniciarSesion(); });
}

function enlazar() {
  $app.querySelectorAll("[data-nav]").forEach((b) => b.addEventListener("click", () => ir(b.dataset.nav)));
  $app.querySelectorAll("[data-sel]").forEach((b) => b.addEventListener("click", () => {
    const id = Number(b.dataset.sel), ya = actual()?.id === id; S.selId = id; if (!ya) S.clics = 1; render();
  }));
  $app.querySelectorAll("[data-f]").forEach((b) => b.addEventListener("click", () => { S.filtro = Number(b.dataset.f); S.selId = null; S.clics = 0; render(); }));
  $app.querySelectorAll("[data-disp]").forEach((b) => b.addEventListener("click", () => alternarDispositivo(Number(b.dataset.disp), b.dataset.activo === "1")));
  $app.querySelectorAll("[data-clave]").forEach((b) => b.addEventListener("click", () => {
    const clave = b.dataset.clave;
    if (b.dataset.desc) desconectarFuente(Number(b.dataset.desc), clave);
    else if (b.dataset.con) conectarFuente(Number(b.dataset.con), clave);
    else conectarLocal(clave);
  }));
  const vincular = (id, fn, ev = "input") => document.getElementById(id)?.addEventListener(ev, (e) => fn(e.target.value));
  vincular("zona-nueva", (v) => (S.zonaNueva = v), "change");
  vincular("red-nombre", (v) => (S.red.nombre = v));
  vincular("red-dir", (v) => (S.red.direccion = v));
  vincular("red-usr", (v) => (S.red.usuario = v));
  vincular("red-clase", (v) => (S.red.clase = v), "change");
  vincular("red-zona", (v) => (S.red.zona = v), "change");
  document.getElementById("f-red")?.addEventListener("submit", (e) => { e.preventDefault(); agregarRed(); });
  $app.querySelectorAll("[data-verdad]").forEach((b) => b.addEventListener("click", () => etiquetar(Number(b.dataset.id), b.dataset.verdad || null)));
  $app.querySelectorAll("[data-borrar-evento]").forEach((b) => b.addEventListener("click", () => borrarEvento(Number(b.dataset.borrarEvento))));
  $app.querySelectorAll("[data-exportar]").forEach((b) => b.addEventListener("click", () => exportar(b.dataset.exportar)));
  vincular("origen-exp", async (v) => { S.origenExp = v; try { await cargarMedicion(); } catch (e) { msg(e.message, "err"); } render(); }, "change");
  vincular("ev-ini", (v) => (S.evento.inicio = v)); vincular("ev-fin", (v) => (S.evento.fin = v));
  vincular("ev-zona", (v) => (S.evento.zona = v), "change"); vincular("ev-tipo", (v) => (S.evento.tipo = v), "change");
  vincular("ev-nota", (v) => (S.evento.nota = v));
  document.getElementById("f-evento")?.addEventListener("submit", (e) => { e.preventDefault(); crearEvento(); });
  const acc = { buscar: buscarDispositivos, confirmar: () => resolver("confirmar"), descartar: () => resolver("descartar"), deshacer, salir: () => cerrarSesion(), "cerrar-msg": () => { S.msg = null; render(); }, ayuda: () => { S.ayuda = !S.ayuda; if (S.pantalla !== "panel") S.pantalla = "panel"; render(); } };
  $app.querySelectorAll("[data-a]").forEach((b) => b.addEventListener("click", acc[b.dataset.a]));
}

// ---------------------------------------------------------------- sondeo (RF-07: el panel muestra alertas nuevas solo)
let timer = null;
function detenerPoll() { clearInterval(timer); timer = null; }
function iniciarPoll() { detenerPoll(); timer = setInterval(() => { if (S.ses && S.pantalla === "panel" && !document.hidden) cargarPanel(); }, POLL_MS); }

if (S.ses) { S.pantalla = "panel"; cargarPanel(true).then(iniciarPoll); } else render();
document.addEventListener("visibilitychange", () => { if (!document.hidden && S.ses && S.pantalla === "panel") cargarPanel(); });
