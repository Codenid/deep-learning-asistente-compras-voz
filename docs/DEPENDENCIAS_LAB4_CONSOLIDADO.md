# Mapa de dependencias del Laboratorio 4

Este documento compara los manifiestos disponibles. **No se instalaron ni ejecutaron dependencias durante esta revisión.** Sirve para decidir qué entorno usar antes de una instalación posterior.

## Manifiestos encontrados

| Archivo | Uso declarado | Nota |
|---|---|---|
| `requirements.txt` | Instalación general descrita en `README.md` | Fija un conjunto reciente: Transformers 4.51.3 y `coqui-tts` 0.26.0. |
| `requirements-lab4-modular.txt` | Instalación llamada por las celdas `%pip` de los notebooks 01–07 | Fija otro conjunto: Transformers 4.46.2 y `TTS` 0.22.0. |

Los dos archivos no son intercambiables sin resolver sus diferencias. El README principal indica `requirements.txt`, mientras que los notebooks modulares instalan `requirements-lab4-modular.txt`.

## Comparación de versiones

| Dependencia | `requirements.txt` | `requirements-lab4-modular.txt` | Observación |
|---|---:|---:|---|
| PyTorch | `torch==2.7.1` | No fijado; comentario pide instalarlo primero | El README indica CUDA 12.8 para GPU. |
| TorchAudio | `torchaudio==2.7.1` | No fijado | Debe corresponder a la versión de PyTorch instalada. |
| Transformers | `4.51.3` | `4.46.2` | Diferencia importante para la carga de XTTS-v2. |
| Accelerate | `1.6.0` | `1.16.0` | Versiones distintas. |
| BitsAndBytes | `>=0.50.2` | `==0.50.2` | El manifiesto modular fija una versión exacta. |
| Sentence Transformers | `4.1.0` | `3.4.1` | Diferencia importante para e5 y el cross-encoder. |
| XTTS | `coqui-tts==0.26.0` | `TTS==0.22.0` | Distribuciones/versiones distintas que publican el espacio de importación `TTS`. |
| Rank BM25 | `0.2.2` | `0.2.2` | Coinciden. |
| JiWER | `3.1.0` | `3.1.0` | Coinciden. |
| SoundFile | `0.13.1` | `0.13.1` | Coinciden. |
| Librosa | `0.10.2.post1` | `0.10.2.post1` | Coinciden. |
| NumPy | `1.26.4` | `1.26.4` | Coinciden. |
| Pandas | `2.2.3` | `2.2.3` | Coinciden. |
| PyArrow | `19.0.1` | `20.0.0` | Diferencia menor, pero debe quedar una versión definida. |
| Matplotlib | `3.10.1` | `3.10.1` | Coinciden. |
| Jupyter / ipywidgets | Incluidos | ipywidgets incluido | Jupyter aparece solo en el manifiesto general. |
| SoundDevice / Flask | Incluidos | No incluidos | Usados por utilidades de grabación local/web, no por todos los notebooks. |

## Dependencias por componente

| Componente | Paquetes principales |
|---|---|
| CUDA y agente Qwen | PyTorch, Transformers, Accelerate, BitsAndBytes |
| Recuperación RAG | Sentence Transformers, Rank BM25, PyTorch |
| ASR Whisper | Transformers, PyTorch, Librosa, SoundFile |
| TTS XTTS-v2 y perfiles | TTS / coqui-tts, Transformers, PyTorch, TorchAudio, SoundFile |
| Métricas de voz | JiWER, Transformers, PyTorch |
| Catálogo ESCI | Pandas, PyArrow, NumPy |
| Notebooks y controles | Jupyter, ipywidgets |

## Decisiones pendientes antes de instalar

1. Elegir un manifiesto único para la entrega y hacer que el README y las celdas de instalación apunten al mismo archivo.
2. Resolver explícitamente la pareja de versiones XTTS/Transformers y la versión de Sentence Transformers.
3. Mantener PyTorch y TorchAudio emparejados y definir cómo se instala la variante CUDA requerida por la GPU seleccionada.
4. Separar, si corresponde, dependencias opcionales de grabación local (`sounddevice`, `flask`) de las necesarias para ejecutar los notebooks.

No ejecutar `pip install` hasta que el equipo apruebe una combinación única. Este mapa no afirma compatibilidad; documenta las diferencias para una decisión posterior.
