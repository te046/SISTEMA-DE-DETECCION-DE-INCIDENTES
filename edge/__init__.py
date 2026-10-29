"""Módulo edge: captura video y audio, ejecuta los modelos y envía alertas a la API por HTTP.

Corre como proceso aparte del servidor web (python -m edge) para que la captura pesada no
bloquee la API, y para que en la etapa 5 pueda quedarse en el equipo del pabellón mientras
la API corre en el servidor.
"""
