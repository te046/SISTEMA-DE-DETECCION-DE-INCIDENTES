"""Medición para la tesis: etiquetado (verdad de campo), precisión/recall/F1 y exportación a CSV.

Dos registros de verdad de campo, independientes de la decisión del vigilante (I3/I4):
- Etiqueta de cada ALERTA: «real» o «falsa» → precisión etiquetada = reales ÷ etiquetadas.
- EVENTOS REALES ocurridos (inicio, fin, zona, tipo), p. ej. la cronología de scripts\\prueba_vivo.ps1 →
  recall = eventos con al menos una alerta emparejada ÷ eventos registrados.
Regla de emparejamiento (documentada y probada): misma zona y detectado_en ∈ [inicio − 1 s, fin + 5 s].
No se declaran métricas sin datos: con 0 en el denominador se devuelve None.
"""
import csv
import io
import json
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import db

ANTES_S, DESPUES_S = 1.0, 5.0
TIPOS_EVENTO = ["grito", "rotura de vidrio", "choque", "disparo", "voces elevadas", "posible agresión", "otro"]
REGLA = f"misma zona y detectado_en entre inicio − {ANTES_S:g} s y fin + {DESPUES_S:g} s"


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def emparejado(evento: dict, alerta: dict) -> bool:
    if alerta["zona"] != evento["zona"]:
        return False
    t = _dt(alerta["detectado_en"])
    return _dt(evento["inicio"]) - timedelta(seconds=ANTES_S) <= t <= _dt(evento["fin"]) + timedelta(seconds=DESPUES_S)


def metricas(alertas: list[dict], eventos: list[dict]) -> dict:
    reales = sum(a.get("verdad") == "real" for a in alertas)
    falsas = sum(a.get("verdad") == "falsa" for a in alertas)
    detectados = sum(any(emparejado(e, a) for a in alertas) for e in eventos)
    precision = reales / (reales + falsas) if reales + falsas else None
    recall = detectados / len(eventos) if eventos else None
    f1 = (2 * precision * recall / (precision + recall)) if precision and recall else (0.0 if precision == 0 or recall == 0 else None)
    r = lambda x: None if x is None else round(100 * x, 1)
    return {"alertas_etiquetadas": reales + falsas, "alertas_reales": reales, "alertas_falsas": falsas,
            "alertas_sin_etiqueta": len(alertas) - reales - falsas, "eventos_reales": len(eventos),
            "eventos_detectados": detectados, "precision_etiquetada_pct": r(precision), "recall_pct": r(recall),
            "f1_pct": r(f1), "regla_emparejamiento": REGLA}


def _celda(v) -> str:
    """Evita la inyección de fórmulas al abrir el CSV en Excel (=, +, -, @ al inicio)."""
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def _seg(a: str | None, b: str | None) -> float | None:
    return round((_dt(b) - _dt(a)).total_seconds(), 3) if a and b else None


COLUMNAS_ALERTAS = ["codigo", "origen", "tipo", "prioridad", "zona", "dispositivos", "modalidades", "confianza",
                    "detectado_en", "generado_en", "mostrado_en", "panel_activo", "resuelto_en", "estado", "resuelto_por",
                    "clics", "verdad", "I1_s", "I1_visible_s", "I2_s"]
COLUMNAS_EVENTOS = ["id", "inicio", "fin", "zona", "tipo", "nota", "registrado_por", "detectado"]


def csv_alertas(filas: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(COLUMNAS_ALERTAS)
    for a in filas:
        mods = "+".join(sorted({m["modalidad"] for m in json.loads(a["modalidades"])})) if isinstance(a["modalidades"], str) else ""
        visible = _seg(a["detectado_en"], a["mostrado_en"]) if a.get("panel_activo") == 1 else None   # mismo criterio que Indicadores
        w.writerow([_celda(x) for x in (a["codigo"], a["origen"], a["tipo"], a["prioridad"], a["zona"], a["dispositivos"], mods,
                                        a["confianza"], a["detectado_en"], a["generado_en"], a.get("mostrado_en"), a.get("panel_activo"),
                                        a["resuelto_en"], a["estado"], a["resuelto_por"], a["clics"], a.get("verdad"),
                                        _seg(a["detectado_en"], a["generado_en"]), visible, _seg(a["generado_en"], a["resuelto_en"]))])
    return buf.getvalue()


def csv_eventos(eventos: list[dict], alertas: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(COLUMNAS_EVENTOS)
    for e in eventos:
        w.writerow([_celda(x) for x in (e["id"], e["inicio"], e["fin"], e["zona"], e["tipo"], e["nota"], e["registrado_por"],
                                        int(any(emparejado(e, a) for a in alertas)))])
    return buf.getvalue()


def registrar(app, usuario_actual, error, auditar):
    r = APIRouter()

    def gestor(u):
        if u["rol"] == "vigilante":
            error(403, "Su rol no puede etiquetar ni registrar eventos.", "Pida a un responsable o a un administrador que lo haga.")

    def alertas(origen: str | None) -> list[dict]:
        with db.tx() as con:
            q = "SELECT * FROM alertas" + (" WHERE origen=?" if origen else "") + " ORDER BY generado_en"
            return [dict(x) for x in con.execute(q, (origen,) if origen else ()).fetchall()]

    def eventos() -> list[dict]:
        with db.tx() as con:
            return [dict(x) for x in con.execute("SELECT * FROM eventos_reales ORDER BY inicio").fetchall()]

    class Verdad(BaseModel):
        verdad: Literal["real", "falsa"] | None

    @r.put("/api/v1/alertas/{alerta_id}/verdad")
    def etiquetar(alerta_id: int, v: Verdad, u=Depends(usuario_actual)):
        gestor(u)
        with db.tx() as con:
            a = con.execute("SELECT codigo FROM alertas WHERE id=?", (alerta_id,)).fetchone()
            if not a:
                error(404, "No existe esa alerta.", "Actualice la lista.")
            ahora = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
            con.execute("UPDATE alertas SET verdad=?, etiquetado_por=?, etiquetado_en=? WHERE id=?",
                        (v.verdad, u["sub"] if v.verdad else None, ahora if v.verdad else None, alerta_id))
            auditar(con, u["sub"], "etiqueta_" + (v.verdad or "quitada"), a["codigo"])
            return dict(con.execute("SELECT id, codigo, verdad, etiquetado_por, etiquetado_en FROM alertas WHERE id=?", (alerta_id,)).fetchone())

    class EventoReal(BaseModel):
        inicio: datetime
        fin: datetime
        zona: str = Field(min_length=1, max_length=80)
        tipo: Literal[tuple(TIPOS_EVENTO)]
        nota: str | None = Field(default=None, max_length=300)

    @r.get("/api/v1/eventos-reales")
    def listar_eventos(_u=Depends(usuario_actual)):
        return eventos()

    @r.post("/api/v1/eventos-reales", status_code=201)
    def crear_evento(e: EventoReal, u=Depends(usuario_actual)):
        gestor(u)
        if e.inicio.tzinfo is None or e.fin.tzinfo is None:
            error(422, "Las horas del evento no indican su zona horaria.", "Envíelas con zona, por ejemplo 2026-10-30T10:00:00-05:00.")
        if e.fin < e.inicio:
            error(422, "El fin del evento es anterior a su inicio.", "Revise las horas de inicio y fin.")
        with db.tx() as con:
            iso = lambda d: d.astimezone(timezone.utc).isoformat(timespec="milliseconds")
            nid = con.execute("INSERT INTO eventos_reales(inicio,fin,zona,tipo,nota,registrado_por,registrado_en) VALUES (?,?,?,?,?,?,?)",
                              (iso(e.inicio), iso(e.fin), e.zona, e.tipo, e.nota, u["sub"], iso(datetime.now(timezone.utc)))).lastrowid
            auditar(con, u["sub"], "evento_real_registrado", f"{e.tipo} · {e.zona}")
            return dict(con.execute("SELECT * FROM eventos_reales WHERE id=?", (nid,)).fetchone())

    @r.delete("/api/v1/eventos-reales/{evento_id}", status_code=204)
    def borrar_evento(evento_id: int, u=Depends(usuario_actual)):
        gestor(u)
        with db.tx() as con:
            if not con.execute("SELECT 1 FROM eventos_reales WHERE id=?", (evento_id,)).fetchone():
                error(404, "No existe ese evento.", "Actualice la lista.")
            con.execute("DELETE FROM eventos_reales WHERE id=?", (evento_id,))
            auditar(con, u["sub"], "evento_real_borrado", str(evento_id))
        return Response(status_code=204)

    @r.get("/api/v1/metricas")
    def ver_metricas(origen: Literal["edge", "simulado"] | None = Query(default=None), _u=Depends(usuario_actual)):
        return metricas(alertas(origen), eventos())

    def descarga(texto: str, nombre: str) -> Response:
        return Response(("﻿" + texto).encode("utf-8"), media_type="text/csv; charset=utf-8",   # BOM: Excel lee bien las tildes
                        headers={"Content-Disposition": f'attachment; filename="{nombre}"', "Cache-Control": "no-store"})

    @r.get("/api/v1/exportar/alertas.csv")
    def exportar_alertas(origen: Literal["edge", "simulado"] | None = Query(default=None), u=Depends(usuario_actual)):
        with db.tx() as con:
            auditar(con, u["sub"], "exportar_alertas", origen or "todas")
        return descarga(csv_alertas(alertas(origen)), f"alertas_{origen or 'todas'}_{datetime.now():%Y%m%d_%H%M}.csv")

    @r.get("/api/v1/exportar/eventos_reales.csv")
    def exportar_eventos(u=Depends(usuario_actual)):
        with db.tx() as con:
            auditar(con, u["sub"], "exportar_eventos_reales", "")
        return descarga(csv_eventos(eventos(), alertas(None)), f"eventos_reales_{datetime.now():%Y%m%d_%H%M}.csv")

    app.include_router(r)
