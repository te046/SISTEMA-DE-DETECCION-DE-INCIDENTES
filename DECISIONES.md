# Registro de decisiones (trabajo autónomo del 30/10/2026)

Cada línea: qué se decidió y por qué. Las decisiones de Teo están en `CLAUDE.md`.

## Permisos
- **`.claude/settings.json` NO se creó.** El hook `guardia-credenciales` bloqueó el archivo porque la lista de
  carpetas a denegar nombraba carpetas de navegadores. Por la regla de Teo («si el hook bloquea, no buscar otra vía»)
  no se reintentó con otro contenido. `.claude/settings.local.json` de Teo quedó intacto.
  **Qué hacer:** Teo crea `.claude/settings.json` a mano con las reglas pedidas (permitir leer/editar la carpeta,
  pytest y Python/pip de `.venv`, git status/diff/add/commit y Temp; denegar `data/`, `.env`, `.ingest_key`,
  `.secret_key`, archivos de claves, `.ssh`, carpetas de navegadores y de gestores de contraseñas, `rm -rf` y
  `curl | sh`). Mientras tanto siguen vigentes el hook y las reglas de `CLAUDE.md`, que se respetaron igual.
- **Verificación:** una lectura de prueba sobre `data/__prueba_bloqueo_inexistente.txt` respondió «no existe» (no
  «denegado»), lo que confirma que las reglas de bloqueo NO están cargadas. No se leyó ningún archivo real de `data/`.

## a. «I1 visible» solo con el panel abierto (aprobado por Teo)
- La API anota `panel_activo` al crear cada alerta: 1 si alguna sesión consultó `GET /api/v1/alertas` en los últimos
  3 s (el panel consulta cada 1 s). Se guarda la última consulta en memoria: vale para un solo proceso de API;
  en la etapa 5 (varios procesos) habría que guardarla en la base.
- «I1 visible» se calcula solo con alertas `panel_activo = 1`. Las demás se informan aparte en Indicadores
  («N alertas llegaron con el panel cerrado»). Las alertas anteriores a la migración quedan como «sin dato».
