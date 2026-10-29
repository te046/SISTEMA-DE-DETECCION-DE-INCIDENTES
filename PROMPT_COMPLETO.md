Háblame en español neutro (tú, sin voseo) y escribe el README, los comentarios y los textos de la interfaz en español.

Contexto: este es mi proyecto de tesis y la carpeta ya tiene el sistema de la etapa 1 funcionando (API, base de datos y panel). Quiero que lo termines siguiendo CLAUDE.md: etapas 2, 3, 4 y 5, en el orden sugerido, con los cambios de este mensaje (que mandan sobre CLAUDE.md si hay diferencias).

Lo que quiero lograr: una aplicación de escritorio para Windows que detecte sola mis cámaras (webcam, cámaras IP por RTSP y el teléfono usado como cámara) y mis micrófonos (incluidos los Bluetooth ya emparejados en Windows), los muestre en una lista y me deje conectarlos con un botón. Con una fuente conectada, el sistema capta video y audio, detecta eventos con un modelo de audio y uno de video, los fusiona y muestra la alerta en el panel con su evidencia en 5 segundos o menos, para que el vigilante la confirme o la descarte.

Aplicación de escritorio (último paso, antes de la etapa 5):
- El panel se abre en su propia ventana de escritorio (por ejemplo pywebview), sin abrir el navegador. Una sola instancia a la vez. Al cerrar la ventana se detienen los procesos que la app abrió, y solo esos.
- Genera un .exe con PyInstaller (o la herramienta que justifiques) y un instalador (por ejemplo Inno Setup) que cree el acceso directo en el escritorio y en el menú Inicio, con el ícono del escudo de la UDH (genera un .ico a partir de frontend/logo-udh.png; si la calidad es baja, dímelo). Instalación para mi usuario, sin administrador.
- Los datos (base de datos, claves, evidencias) quedan en la carpeta de datos del usuario (por ejemplo %LOCALAPPDATA%), no dentro del programa. Al desinstalar no borres mis datos sin preguntarme.
- Al abrirse, la app elige un puerto libre sola y no toca los de mis otros proyectos.

Modelos y fusión:
- Video: detecta posible agresión física con un modelo preentrenado usando conjuntos públicos (RWF-2000, Hockey Fight, XD-Violence u otros). Antes de usar cualquiera, revisa su licencia y el acceso, y dime qué decidiste. Si no puedes descargarlo en mi laptop, dime cómo lo hago yo.
- Audio: clasificador preentrenado (YAMNet o PANNs) con clases de vidrio roto, grito, choque, disparo y voces elevadas (discusión). Dime qué clases propones.
- Fusión: solo video = prioridad baja o media; video y audio coinciden = prioridad alta. Una discusión verbal se detecta sobre todo por audio. Guarda un clip corto de video y audio alrededor del evento para que el vigilante confirme o descarte.
- No declares métricas de los modelos (precisión, recall, F1) hasta medirlas con grabaciones de prueba. Si el modelo de video es solo una línea base, dilo claro en la interfaz y en el README.

Cómo quiero que trabajes:
1. Empieza por tu plan en 10 líneas y espera mi OK. No cambies nada antes de eso.
2. Luego avanza paso a paso en el orden de CLAUDE.md. Al terminar cada paso: pruebas en verde, README actualizado y un resumen corto de lo que hiciste y cómo lo pruebo yo. Espera mi OK antes de seguir con el siguiente.
3. Antes de instalar algo, comprueba si ya está instalado. Todo va en el entorno virtual del proyecto, nada global.
4. Antes de levantar un servidor, comprueba qué puerto está libre y no toques los de mis otros proyectos. No cierres procesos que tú no hayas abierto.
5. No borres archivos ni la carpeta data/ sin preguntarme.
6. No leas ni uses contraseñas, cookies, tarjetas ni archivos fuera de esta carpeta. Si necesitas la clave de una cámara IP, pídemela y guárdala solo cifrada.
7. No inventes resultados. Lo simulado queda marcado como simulado.
8. Si algo no se puede probar sin mi hardware, déjalo implementado con pruebas que no dependan de él y dime exactamente cómo lo pruebo yo.
9. Si algo es ambiguo (por ejemplo a qué me refería con "tres tipos de cámara"), pregúntame en vez de suponer.
10. Mantén el diseño actual del panel (colores, tipografía, mensajes de error con solución, botón Deshacer). No lo rediseñes.

Definición de terminado: instalo la app con el instalador, aparece el ícono en mi escritorio, la abro, detecta y lista mi webcam y el micrófono de la laptop, los conecto desde el panel, un sonido de prueba genera una alerta con su evidencia en 5 segundos o menos, la confirmo o la descarto, el incidente se registra y los indicadores I1 a I4 se calculan con esos datos.

Empieza ahora con el paso 1: lee CLAUDE.md y README.md, revisa el código sin modificar nada, y dame tu plan.
