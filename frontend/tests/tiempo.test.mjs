// Ejecutar con la zona de Perú (sin dependencias):  set TZ=America/Lima&& node --test frontend/tests/tiempo.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { horaAlerta } from "../js/tiempo.js";

test("la zona del sistema es la de Lima (UTC−5)", () => {
  assert.equal(new Date("2026-10-30T05:00:00+00:00").getTimezoneOffset(), 300);
});

test("una hora UTC se muestra en hora local de Lima", () => {
  const ahora = new Date("2026-10-30T05:30:00+00:00");                 // 00:30 en Lima
  assert.equal(horaAlerta("2026-10-30T05:23:43.120+00:00", ahora), "00:23:43");
});

test("una alerta de otro día muestra la fecha", () => {
  const ahora = new Date("2026-10-30T05:30:00+00:00");                 // 30/10 00:30 en Lima
  assert.equal(horaAlerta("2026-10-29T17:23:10.000+00:00", ahora), "29/10 12:23:10");
});

test("el cambio de día se decide en hora local, no en UTC", () => {
  // 04:59 UTC del 30/10 es todavía 29/10 23:59 en Lima: no es «hoy» si ahora es 30/10 00:30 en Lima.
  const ahora = new Date("2026-10-30T05:30:00+00:00");
  assert.equal(horaAlerta("2026-10-30T04:59:00+00:00", ahora), "29/10 23:59:00");
});

test("una hora inválida no rompe el panel", () => {
  assert.equal(horaAlerta("no-es-fecha"), "—");
});
