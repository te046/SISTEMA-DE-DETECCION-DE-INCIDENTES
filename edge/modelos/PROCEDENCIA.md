# Procedencia de los modelos

Los pesos no se guardan en Git: se descargan de una revisión fija y se verifican con SHA-256.
Ninguna métrica de esta tabla es un resultado del proyecto; las del autor se citan solo como referencia.

## Audio: YAMNet (ONNX)
| Campo | Valor |
|---|---|
| Fuente | https://huggingface.co/audiomagic/yamnet-onnx (conversión tf2onnx de google/yamnet v1, pesos sin cambios) |
| Licencia | Apache 2.0 (modelo y código de Google); ontología AudioSet CC BY 4.0 |
| Archivo | `yamnet.onnx` |
| SHA-256 | `d3835ffbbd4a1bb3e777f0ca217b5007907f5171dd5d17c4236b95b2af8f908e` |
| Cómo se obtiene | `python -m edge.descargar_modelos` |
| Latencia medida (laptop de desarrollo, CPU) | ~13 ms por ventana de 1 s |

## Video: VideoMAE afinado con RWF-2000 — **LÍNEA BASE**
| Campo | Valor |
|---|---|
| Repositorio | https://huggingface.co/lmazzon70/videomae-base-finetuned-kinetics-finetuned-rwf2000-epochs8-batch8-kb |
| Revisión usada | `bb28180b42bfa4d8b3a2e1c7a77d741ca7f7d7b8` = PR #2 (abierta, **sin fusionar por el autor**), creada por `SFconvertbot`, el bot oficial de Hugging Face, como variante `safetensors` del `pytorch_model.bin` |
| Por qué esa revisión | `safetensors` no puede ejecutar código al cargarse; así nunca se abrió el `.bin` (pickle) |
| Licencia del modelo | CC BY-NC 4.0 (uso no comercial, con atribución al autor) |
| Base | MCG-NJU/videomae-base-finetuned-kinetics |
| Datos de entrenamiento | La ficha dice «unknown dataset»; que sea RWF-2000 solo lo indica el nombre. RWF-2000 (SMIIP Lab) no permite uso comercial ni modificar o redistribuir la base sin su aprobación: por eso aquí no se redistribuyen pesos |
| Etiquetas | 0 = Fight → «posible agresión», 1 = NonFight |
| SHA-256 `model.safetensors` | `083a6e539404103b1712c6dbf8aeca320043598269ac3ee6e6cfe2ccc5562021` (coincide con el publicado) |
| SHA-256 `videomae_rwf2000.onnx` | `7642d868dfd6384220930847c42da621a97d5be6c7f52059dc0c848505c0d07b` (exportado aquí, opset 17, PyTorch 2.14.1 CPU) |
| Verificación de la exportación | diferencia máxima ONNX vs PyTorch: 2,4 × 10⁻⁷ |
| Exactitud declarada por el autor | 0,73 en su conjunto de evaluación. **No medida en este proyecto** |
| Latencia medida (laptop de desarrollo, CPU, 30/10/2026) | preprocesado 22 ms + inferencia 763 ms = **784 ms por clip** de 16 fotogramas (mediana de 10; máx. 867 ms) |
| Cómo se obtiene | `.venv-export\Scripts\python scripts\exportar_modelo_video.py` (una vez; detalles en `PROCEDENCIA_VIDEO.json`) |

**Limitaciones:** el modelo no fue calibrado con video del pabellón; RWF-2000 son peleas grabadas por cámaras de
seguridad, distintas del encuadre de una webcam. Sus resultados son una línea base y no deben presentarse como
desempeño del sistema hasta medirlos con grabaciones de prueba etiquetadas.
