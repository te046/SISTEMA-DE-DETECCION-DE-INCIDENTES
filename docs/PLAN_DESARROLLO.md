# Plan de desarrollo · Sistema de Vigilancia UDH

**Proyecto:** Sistema de detección multimodal (audio y video) de incidentes para el segundo pabellón de la Universidad de Huánuco.
**Autor y responsable:** Jorge Luis Salazar Tarazona.
**Unidad:** III, Desarrollo e integración de la solución tecnológica (semanas 9 a 12).
**Última actualización:** 06/11/2026.

## 1. Objetivo y alcance

**Objetivo:** entregar una versión funcional integrada que detecte eventos de riesgo por audio y video, genere una alerta con evidencia, permita al vigilante confirmarla o descartarla, registre el incidente y calcule los indicadores I1 a I4.

**Dentro del alcance de la Unidad III:**
- API REST con base de datos (alertas, incidentes, indicadores, dispositivos, medición).
- Módulo edge: captura, clasificación de audio (YAMNet) y de video (VideoMAE, línea base), fusión por zona.
- Panel de operación y aplicativo de escritorio para Windows.
- Roles, permisos y controles básicos de seguridad.
- Pruebas automáticas, registro de incidencias y documentación técnica.

**Fuera del alcance (trabajo futuro):** servidor con Docker, Caddy (HTTPS) y PostgreSQL; Bluetooth cercano; búsqueda automática de cámaras IP (ONVIF); vista previa en vivo de la cámara.

## 2. Metodología

Desarrollo **iterativo e incremental por bloques**:

1. Cada bloque toma una o más historias del backlog (sección 5).
2. El bloque se cierra solo cuando sus pruebas automáticas están en verde.
3. Cada bloque cerrado queda como un commit con la convención `feat`, `fix`, `docs` o `chore`.
4. Los ajustes de cada iteración se registran con su motivo (sección 4).
5. Los fallos encontrados se registran como incidencias con su causa, su corrección y su estado.

No se usó Scrum ni Kanban de forma formal: el proyecto tiene un solo desarrollador, y el ciclo es «bloque → pruebas → commit → revisión».

## 3. Cronograma e hitos

| Semana | Fase | Hito verificable | Responsable | Evidencia | Estado |
|---|---|---|---|---|---|
| 9 | Planificación y configuración | Entorno `.venv`, estructura del repositorio, etapa 1 (API, base de datos y panel) respaldada | J. Salazar | Commit `1354fcf` (29/10) | Cumplido |
| 10 | Núcleo funcional | Captura de audio y video y alerta de punta a punta con YAMNet | J. Salazar | `091d337`, `47e0746`, `599d48b` (29/10) | Cumplido |
| 10 | Núcleo funcional | Búsqueda y conexión de dispositivos desde el panel | J. Salazar | `9e456c6` (30/10) | Cumplido |
| 11 | Interfaces e integración | Fusión audio y video, horas en UTC, I1 visible | J. Salazar | `377b220`, `2df62e9`, `9f73b74` (30/10) | Cumplido |
| 11 | Interfaces e integración | Aplicativo de escritorio e instalador | J. Salazar | `727aea8` (30/10) | Cumplido; instalador sin compilar |
| 12 | Seguridad, calidad y documentación | Medición (precisión, recall, F1), exportación CSV, restablecer claves | J. Salazar | `18d2478`, `d0d3f4f` (30/10) | Cumplido |
| 12 | Seguridad, calidad y documentación | README, manual, publicación en GitHub | J. Salazar | `54746dd`, `1464c3f`, `8bf6e41` (02/11) | Cumplido |
| 12 | Entrega | Pruebas completas en la laptop y presentación del producto | J. Salazar | 124 pruebas en verde (06/11) | Cumplido |

## 4. Ajustes por iteración

| Iteración | Ajuste | Motivo |
|---|---|---|
| Semana 10 | Se fijó pytest a la serie 8 | pytest 9.2.0 fallaba en Python 3.10.0 |
| Semana 10 | Margen de 5 s al abrir el micrófono | El primer bloque de audio tarda más de 0,5 s |
| Semana 11 | Se añadió el aplicativo de escritorio al plan | El sistema se presenta como aplicación, no como sitio web |
| Semana 11 | «I1 visible» cuenta solo alertas con el panel abierto | El promedio salía en 297,97 s por alertas llegadas con el panel cerrado |
| Semana 12 | Bluetooth, ONVIF y la etapa del servidor pasan a trabajo futuro | Prioridad a lo que bloquea la medición de los indicadores |

## 5. Backlog con criterios de aceptación

| ID | Historia | Prioridad | Criterio de aceptación | Estado |
|---|---|---|---|---|
| B01 | Como responsable, quiero detectar y conectar cámaras y micrófonos desde el panel | Alta | El micrófono de la laptop aparece en «Buscar dispositivos» y queda «Conectado» al pulsar conectar | Hecho; webcam local sin verificar |
| B02 | Como vigilante, quiero recibir una alerta con evidencia cuando hay un sonido de riesgo | Alta | Un sonido de prueba genera una alerta con audio WAV de 5 s antes y 1,5 s después | Hecho; umbral sin calibrar |
| B03 | Como vigilante, quiero que audio y video de la misma zona den una sola alerta priorizada | Alta | Dos detecciones en la misma zona en ±3 s producen una alerta de prioridad alta | Hecho |
| B04 | Como vigilante, quiero confirmar o descartar una alerta y poder deshacerlo | Alta | Confirmar crea un incidente; «Deshacer» lo revierte y solo lo puede hacer quien resolvió | Hecho |
| B05 | Como responsable, quiero ver los indicadores I1 a I4 | Alta | La pantalla «Indicadores» muestra I1, I1 visible, I2, I3 e I4 calculados con los datos guardados | Hecho |
| B06 | Como responsable, quiero etiquetar alertas y exportar los datos | Alta | Precisión, recall y F1 se calculan con etiquetas reales y el CSV se descarga en UTF-8 | Hecho |
| B07 | Como usuario, quiero abrir el sistema como aplicación de escritorio | Alta | Un ícono abre una sola ventana; una segunda apertura no crea otra instancia | Hecho |
| B08 | Como administrador, quiero roles y protección de cuentas | Alta | El vigilante recibe rechazo al conectar dispositivos; 5 intentos fallidos bloquean la cuenta 15 min | Hecho |
| B09 | Calibrar el umbral de audio por clase | Alta | Umbral elegido con un conjunto de calibración y evaluado en otro separado | Pendiente |
| B10 | Medir el video con grabaciones etiquetadas | Alta | Precisión y recall del video reportados con grabaciones propias | Pendiente |

Las historias B11 a B15 (persistencia, disponibilidad RNF-02, servidor, Bluetooth y ONVIF) están en el documento del producto de la Unidad III.

## 6. Criterio de terminado

Con una webcam y un micrófono reales, el sistema los detecta y los lista, se conectan desde el panel, un sonido de prueba genera una alerta con evidencia visible en 5 s o menos, se puede confirmar o descartar, el incidente queda registrado y los indicadores I1 a I4 se calculan con esos datos.

## 7. Riesgos

| Riesgo | Impacto | Respuesta |
|---|---|---|
| El audio real no alcanza el umbral de 0,50 | No hay alerta en la demostración | Calibración por clase (B09); umbral provisional solo para demostraciones, declarado como tal |
| La webcam local no se detecta | El flujo de video no se demuestra en vivo | Revisar permiso de Windows, obturador y otras aplicaciones |
| Las «Mejoras de audio» de Windows silencian el micrófono | Silencio digital (−90 dBFS) | Apagarlas antes de usar el sistema |
