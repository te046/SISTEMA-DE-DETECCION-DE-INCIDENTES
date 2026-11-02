# Manual breve · Sistema de Vigilancia UDH

## 1. Instalación (una vez)
1. Ejecute el instalador `Instalar_SistemaVigilanciaUDH_1.0.0.exe`. No pide administrador; se instala para su usuario.
2. Deje marcada la casilla «Crear un acceso directo en el escritorio».
3. Abra **Sistema de Vigilancia UDH** desde el escritorio o el menú Inicio.
4. **Primera vez:** aparece la ventana «Claves iniciales». Anote las tres cuentas en un lugar seguro antes de
   cerrarla: **no se vuelven a mostrar**.
5. En Windows, apague las **Mejoras de audio** del micrófono: Configuración › Sistema › Sonido › Entrada › su
   micrófono › «Mejoras de audio: desactivado». Sin este paso, el audio puede llegar como silencio.

Desinstalar (Configuración › Aplicaciones) **no borra** sus datos: quedan en `%LOCALAPPDATA%\SistemaVigilanciaUDH`.

## 2. Vigilante: atender una alerta
1. Inicie sesión con su usuario y contraseña. Deje la pantalla **Alertas** abierta durante el turno.
2. Cuando llega una alerta, el panel la muestra sola, con la más urgente primero:
   - **Alta**: video y audio coinciden en la misma zona.
   - **Media / Baja**: una sola fuente (audio, o video «línea base»).
3. Abra la alerta, **reproduzca el video y el audio** y decida:
   - **Confirmar incidente**: queda registrado con fecha, hora, zona y tipo.
   - **Descartar**: falsa alarma.
   - Si se equivocó, pulse **Deshacer** en el mensaje que aparece.
4. «Video: línea base» significa que el modelo de video no está calibrado: su criterio manda.

Si aparece «X está desconectado», esa zona usa solo la evidencia disponible; avise al responsable.

## 3. Responsable o administrador
- **Conectar cámara y micrófono:** menú **Buscar dispositivos** → elija la zona → **Buscar** → **Conectar**.
  - Los que dicen «No sirve» (por ejemplo Stereo Mix) no se pueden usar, y la pantalla explica por qué.
  - Si no aparece la cámara: abra el obturador o pulse la tecla de cámara, revise Configuración › Privacidad ›
    Cámara (permitir a aplicaciones de escritorio) y cierre Teams, Zoom u otras aplicaciones que la usen.
- **Cámara IP o teléfono:** en la misma pantalla, «Agregar cámara IP o teléfono». Escriba la dirección
  (`rtsp://…` o `http://IP:puerto/video`) y, si la cámara los pide, el usuario y la clave en sus campos. Se guarda
  cifrada; se conecta solo al pulsar **Conectar**.
- **Estado del sistema:** muestra cada fuente con su último latido.
- **Medición (para la tesis):**
  - Etiquete cada alerta como **Real** o **Falsa** según lo que de verdad ocurrió.
  - Registre los **eventos reales** (inicio, fin, zona y tipo); por ejemplo, la cronología que imprime la prueba en vivo.
  - Con eso, la pantalla calcula la **precisión etiquetada, el recall y el F1**. Mientras no haya datos muestra «—».
  - **Exportar alertas (CSV)** y **Exportar eventos reales (CSV)** guardan los archivos para el análisis.
- **Indicadores:** I1 (hasta el servidor), I1 visible (hasta el panel; RNF-01 ≤ 5 s), I2, I3 e I4. I5 se mide con
  la encuesta Likert, fuera del sistema.

## 4. Sustentación: guion de demostración (15 min)
1. Abra la aplicación desde el escritorio: ventana propia, ícono del escudo y una sola instancia (intente abrirla
   otra vez y verá el aviso).
2. **Buscar dispositivos** → conecte la webcam y el micrófono en Zona 1 → **Estado del sistema**: ambos conectados.
3. Ejecute `scripts\prueba_vivo.ps1` (o actúe a mano) con una **pelea simulada, coreografiada y sin contacto**,
   con el permiso de quien salga en cámara, y voces elevadas: debe llegar una alerta **Alta** con video y audio.
4. Abra la alerta, reproduzca la evidencia, **Confirmar** → **Incidentes** → **Deshacer** para mostrar la reversión.
5. **Indicadores**: I1 e I1 visible. **Medición**: etiquete la alerta, registre el evento real y exporte el CSV.

**Qué SÍ se puede afirmar** (medido en la laptop de desarrollo, CPU):
- Inferencia del audio: ~13 ms por ventana.
- Video: ~0,78 s por clip de 16 fotogramas.
- Con datos sintéticos, el panel pintó una alerta 0,49 s después de recibirla.

**Qué NO se puede afirmar todavía:**
- Precisión, recall o F1 de los modelos, hasta medirlos con un conjunto de prueba etiquetado.
- La exactitud de 0,73 del modelo de video: la publicó su autor; no es un resultado propio.
- Las alertas generadas con el umbral de fusión provisional no son medición de la tesis.

## 5. Problemas frecuentes
| Qué pasa | Qué hacer |
|---|---|
| «Ya está abierto» al iniciar | Use la ventana que ya está en la barra de tareas. |
| No llegan alertas de audio | Apague las Mejoras de audio; acerque la fuente de sonido; un aplauso no es una clase del diseño. |
| La cámara IP queda en «▲ Error» | Revise la dirección, el usuario y la clave; si dice «SECRET_KEY cambió», vuelva a agregarla. |
| «No está el modelo de video» | Las cámaras solo graban evidencia; instálelo con `scripts\instalar_modelo_video.ps1`. |
| Olvidé o no anoté las claves iniciales | No se pueden volver a ver (solo se guarda su huella cifrada). Cierre la app y ejecute `scripts\restablecer_claves.ps1`: genera claves **nuevas** para las 3 cuentas y las muestra una sola vez. |
| La aplicación no abre | Revise `%LOCALAPPDATA%\SistemaVigilanciaUDH\registros\app.log`. |
