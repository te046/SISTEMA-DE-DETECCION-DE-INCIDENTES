// Horas del panel. La API guarda todo en UTC con zona (…+00:00); aquí se muestra en la hora local del equipo.
// Si la alerta no es de hoy se antepone la fecha: sin ella, una alerta de ayer a las 12:23 parece reciente.
const dos = (n) => String(n).padStart(2, "0");

export function horaAlerta(iso, ahora = new Date()) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const hora = `${dos(d.getHours())}:${dos(d.getMinutes())}:${dos(d.getSeconds())}`;
  const mismoDia = d.getFullYear() === ahora.getFullYear() && d.getMonth() === ahora.getMonth() && d.getDate() === ahora.getDate();
  return mismoDia ? hora : `${dos(d.getDate())}/${dos(d.getMonth() + 1)} ${hora}`;
}
