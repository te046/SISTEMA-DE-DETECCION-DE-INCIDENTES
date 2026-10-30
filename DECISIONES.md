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

## b. Aplicación de escritorio
- **Un solo proceso, sin procesos hijos:** ventana pywebview en el hilo principal; API (uvicorn) y edge en hilos.
  Así «cerrar solo lo que levantó» es exacto: al cerrar la ventana se detienen ambos hilos y no queda nada vivo.
- **Instancia única** con un mutex con nombre de Windows (`Local\SistemaVigilanciaUDH`); la segunda apertura avisa y sale.
- **Puerto libre** desde 8000, saltando 8080, 8081 y 8090 aunque estén libres.
- **Datos** en `%LOCALAPPDATA%\SistemaVigilanciaUDH` (registro en `registros\app.log`). El `data\` de desarrollo no se toca.
- **Claves iniciales:** `seed.crear_cuentas()` las devuelve en memoria y la app las muestra en una ventana aparte
  («Claves iniciales: guárdelas ahora»); no se imprimen ni se registran. La app no crea los dispositivos de ejemplo.
- **Modelo de video NO empaquetado:** CC BY-NC y derivado de RWF-2000 (no redistribuir). La app lo busca en
  `%LOCALAPPDATA%\SistemaVigilanciaUDH\modelos`; `scripts\instalar_modelo_video.ps1` lo copia verificando el SHA-256.
  Sin él, las cámaras solo graban evidencia. YAMNet (Apache 2.0) sí va dentro del paquete.
- **Ícono:** se recorta el escudo del logo (527×628 px, calidad suficiente: nítido a 256 px y reconocible a 32 px;
  a 16 px pierde detalle, como todo escudo con lema) y se vuelve transparente solo el blanco del borde.
- **Python 3.10.0 y PyInstaller:** 3.10.0 tiene un fallo en `dis` (bpo-45757) que hace caer a PyInstaller. No se
  instaló otro Python (software del sistema): `scripts\construir_escritorio.py` aplica el arreglo oficial de 3.10.1
  solo dentro de su proceso. Recomendación: actualizar a 3.10.x más reciente cuando Teo lo decida.
- **Inno Setup no está instalado** (no se instala software del sistema): quedan `instalador\SistemaVigilanciaUDH.iss`
  (por usuario, sin administrador, conserva los datos al desinstalar) y `instalador\compilar_instalador.ps1`;
  alternativa sin instalador: `scripts\crear_accesos_directos.ps1`.
- **Descargas en la ventana:** `ALLOW_DOWNLOADS` activado para poder exportar CSV desde la app.

## c. Medición: etiquetado, eventos reales y CSV
- **Dos verdades de campo separadas de I3/I4** (que siguen usando la decisión del vigilante): etiqueta «real/falsa»
  por alerta (precisión etiquetada) y tabla `eventos_reales` con lo que de verdad ocurrió (recall).
- **Regla de emparejamiento** evento↔alerta: misma zona y `detectado_en` entre inicio − 1 s y fin + 5 s (el +5 s cubre
  el I1 objetivo). Está en `backend/app/medicion.py`, probada, y se muestra en la pantalla.
- Sin datos no hay métrica: con denominador 0 se muestra «—», nunca 0 % inventado.
- Etiquetar y registrar eventos: solo responsable y administrador; el vigilante solo ve.
- **CSV:** UTF-8 con BOM (Excel lee las tildes) y celdas que empiezan por = + - @ prefijadas con «'» (evita
  inyección de fórmulas). El I1 visible del CSV usa el mismo criterio que Indicadores (solo con panel abierto).
- **Caché del panel:** el servidor envía `Cache-Control: no-cache` a los archivos del panel, para no quedar con un
  `.js` viejo tras una actualización (ocurrió en la revisión de desarrollo con el navegador).
- La pantalla se revisó con Playwright sobre datos temporales (revisión de desarrollo, no reemplaza la prueba
  manual en la ventana de escritorio).

## d. Documentación
- README reorganizado alrededor del aplicativo de escritorio (el navegador queda como ayuda de desarrollo), con los
  límites al principio: video línea base, audio sin calibrar, condición de apagar las Mejoras de audio.
- MANUAL.md nuevo: instalación, vigilante, responsable y guion de sustentación con lo que SÍ y lo que NO se puede afirmar.
- CLAUDE.md: aclaración «aplicativo de escritorio», política de decisiones, estado real y pendientes honestos del
  pedido original no implementados (RNF-02 por latidos, Bluetooth con `bleak`, vista previa de cámara, ONVIF, etapa 5).

## e. Etapa 5 (Docker, Caddy, PostgreSQL)
- **No se implementó** por tiempo: queda como trabajo futuro documentado (README «Trabajo futuro» y CLAUDE.md).
  Requiere además adaptar la base a PostgreSQL y mover `panel_activo` a la base (hoy en memoria).

## Verificación en la laptop (30/10/2026, autorizada por Teo)
- Accesos directos creados con `scripts\crear_accesos_directos.ps1` en el Escritorio y en el menú Inicio; apuntan a
  `dist\SistemaVigilanciaUDH\SistemaVigilanciaUDH.exe` y usan su ícono (escudo UDH, comprobado extrayéndolo del .exe).
- Modelo de video copiado con `scripts\instalar_modelo_video.ps1` (SHA-256 verificado) a
  `%LOCALAPPDATA%\SistemaVigilanciaUDH\modelos`; la búsqueda del modelo de la app lo encuentra y lo carga. En esa
  carpeta solo quedó `modelos` (la app no se ejecutó con los datos reales).
- App empaquetada con datos TEMPORALES: responde (`/salud` ok, panel 200); la segunda instancia avisa, no abre puertos
  y queda registrada («Segunda instancia…», línea agregada al registro para poder verificarlo sin el cuadro de diálogo).
- Cierre ordenado con `taskkill` sin `/F` (equivale a la «X»): en un primer inicio hay dos ventanas (claves +
  principal) y cerrar la de claves NO apaga la app (correcto). Tras cerrar la principal: «Sistema detenido», sin
  procesos y con el puerto libre.
- **Fallo corregido en `scripts\prueba_vivo.ps1`:** la ruta del registro tenía un carácter de control (`\a` → BEL) al
  reescribir el script con Python; nunca habría encontrado el registro. Se revisaron todos los .ps1 y .iss: era el único.
- `prueba_vivo.ps1 -EnSeco`: arranque, respuesta y cierre ordenado con datos temporales, sin captura; probado: OK.
