# Sistema de vigilancia multimodal · UDH (etapa 1)

API (FastAPI + SQLite) y panel web (HTML, CSS y JavaScript) del módulo M06, con login, roles, alertas,
incidentes, indicadores I1–I4 y estado de dispositivos. La fusión de video+audio está implementada y probada
(`backend/app/fusion.py`). **Aún no incluye** la captura RTSP/audio ni los modelos de detección (etapas 2 y 3).

## Arrancar en la laptop
1. Python 3.10+ instalado. Una sola vez, dentro de esta carpeta:
   `python -m venv .venv` → activarlo (`.venv\Scripts\activate` en Windows) → `pip install -r backend/requirements.txt`
2. `python run.py`
   - Busca el primer puerto libre desde el 8000; **no toca los de sus otros proyectos**. Para uno fijo: `--port 8123`.
   - La primera vez crea la base y las cuentas y **muestra las claves una sola vez**. Para fijar una clave:
     `set CLAVE_RESPONSABLE=su-clave` (Windows) o `export CLAVE_RESPONSABLE=...` antes de la primera ejecución.
3. Abra la dirección que imprime. Documentación de la API en `/docs`.

## Probar sin cámaras
- `python scripts/simular.py --url http://127.0.0.1:<puerto> --cantidad 4` envía alertas marcadas como `simulado`.
- `python scripts/limpiar_simulados.py` las borra antes de medir con datos reales.
- Pruebas automáticas: `cd backend && python -m pytest -q`

## Cómo se conecta el módulo de detección (etapas 2 y 3)
El módulo edge envía `POST /api/v1/alertas` con el encabezado `X-Api-Key` (la clave está en `data/.ingest_key`).
Use `fusionar()` para unir las detecciones de video y audio. Sin ninguna clasificación de modelo la API rechaza
la alerta (RN-01). El tiempo de detección I1 = `generado_en − detectado_en`: el módulo debe enviar `detectado_en`
con el instante real del evento.

## Datos de diseño que debe calibrar (no son resultados)
Umbral mínimo (0,50), ventana de fusión (3 s), clases acústicas urgentes y reglas de prioridad en `fusion.py`.
Recall y F1 necesitan un conjunto etiquetado con grabaciones del pabellón.

## Paso al servidor (sustentación)
- Cambiar SQLite por PostgreSQL, poner un proxy con HTTPS (Caddy o Nginx) delante y arrancar con
  `uvicorn app.main:app --host 0.0.0.0` detrás del proxy.
- Definir `SECRET_KEY` e `INGEST_KEY` por variables de entorno; no subir la carpeta `data/` a ningún repositorio.
- Los medios de evidencia (`evidencia_video`, `evidencia_audio`) son rutas/URL; guárdelos en una carpeta servida por el proxy.

## Seguridad incluida
Contraseñas con scrypt, tokens firmados con vencimiento (8 h), bloqueo de 15 min tras 5 intentos, clave aparte para
el módulo edge, auditoría de accesos y decisiones, y escape de todo texto mostrado en el panel.
