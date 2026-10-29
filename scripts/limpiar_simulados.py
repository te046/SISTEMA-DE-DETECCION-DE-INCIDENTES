"""Borra las alertas SIMULADAS (y sus incidentes) antes de medir con datos reales.
Uso: python scripts/limpiar_simulados.py   (pide confirmación)"""
import sqlite3, sys
from pathlib import Path

db = Path(__file__).resolve().parents[1] / "data" / "vigilancia.db"
if input(f"Se borrarán las alertas simuladas de {db}. Escriba SI para continuar: ").strip() != "SI":
    sys.exit("Cancelado.")
con = sqlite3.connect(db)
con.execute("DELETE FROM incidentes WHERE alerta_id IN (SELECT id FROM alertas WHERE origen='simulado')")
n = con.execute("DELETE FROM alertas WHERE origen='simulado'").rowcount
con.commit(); print(f"Borradas {n} alertas simuladas.")
