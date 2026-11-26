# Asistente de compras por voz

Nuestra solución convierte una consulta hablada en español en una recomendación sustentada en el catálogo, conserva las restricciones de la conversación y puede preparar y registrar una compra en una tienda simulada. La respuesta se sintetiza con XTTS-v2 usando un perfil de voz propio o autorizado.

## Estructura de ejecución

La implementación está dividida en notebooks cortos que comparten clases sencillas de Python en `src/lab4_asistente/`. Ejecutamos los notebooks en este orden:

1. [`01_datos_y_catalogo.ipynb`](notebooks/01_datos_y_catalogo.ipynb): catálogo ESCI en español, consultas dev/eval y qrels separados.
2. [`02_preparar_perfil_de_voz.ipynb`](notebooks/02_preparar_perfil_de_voz.ipynb): genera un perfil `.pt` por grabación WAV; no requiere crear un `.txt`.
3. [`03_rag_y_ablacion.ipynb`](notebooks/03_rag_y_ablacion.ipynb): baseline BM25, sistema híbrido, ajuste solo en dev y ablaciones.
4. [`04_tienda_sqlite.ipynb`](notebooks/04_tienda_sqlite.ipynb): restauración determinista, cotización y pedido atómico/idempotente.
5. [`05_agente_y_memoria.ipynb`](notebooks/05_agente_y_memoria.ipynb): un agente Qwen con nueve herramientas y estado persistente.
6. [`06_integracion_voz_y_compra.ipynb`](notebooks/06_integracion_voz_y_compra.ipynb): turno de voz completo con transcripción revisable.
7. [`07_pruebas_y_resultados.ipynb`](notebooks/07_pruebas_y_resultados.ipynb): 14 escenarios de texto, 6 de audio, métricas y evidencias.

El notebook integrado previo [`00_Asistente.ipynb`](notebooks/demo/00_Asistente.ipynb) queda como prototipo de referencia. La ejecución recomendada es la modular.

## Preparación local en WSL/Linux

Usa Python 3.11 y el entorno CUDA del proyecto. En la carpeta raíz del repositorio:

```bash
source .venv-dl-cuda/bin/activate
python -m pip install --upgrade pip
python -m pip install torch==2.7.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu128
python -m pip install -r requirements-lab4-modular.txt
python -m ipykernel install --user --name lab4-voz --display-name "Python (Lab4 voz)"
```

En VS Code selecciona **Python (Lab4 voz)** como kernel. Comprueba CUDA antes de abrir los notebooks:

```bash
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'GPU no disponible')"
```

La integración usa una política fija para la GPU local de 12 GB: Qwen2.5-7B corre en CUDA con cuantización de 4 bits; recuperación, Whisper y XTTS corren en CPU durante la integración. Así no compiten simultáneamente por VRAM. El notebook 02 prepara perfiles XTTS en GPU y el notebook 03 ejecuta recuperación en GPU cuando Qwen no está cargado. **Cierra o apaga el kernel de cada notebook pesado antes de abrir el siguiente**, para que sus modelos no se queden ocupando memoria.

Si CUDA falla, la solución se detiene con una instrucción; Qwen no pasa silenciosamente a CPU. Cierra otras aplicaciones que usen GPU, reinicia el kernel y revisa `torch.cuda.is_available()` y la VRAM libre.

## Ejecución de referencia para la entrega

El enunciado solicita que el procesamiento de modelos para la evaluación se ejecute en Google Colab, sin APIs externas de inferencia. Para la evidencia de entrega, sube/clona el repositorio en Colab, activa una GPU y ejecuta los mismos notebooks en orden. El código no usa endpoints de inferencia externos. La configuración local documentada arriba sirve para la validación y el desarrollo en el equipo; no sustituye una corrida en Colab si la evaluación del curso exige ese entorno.

## Datos y perfiles privados

Descarga los dos archivos de la versión small ESCI y guárdalos en `data/raw/`:

- `shopping_queries_dataset_products.parquet`
- `shopping_queries_dataset_examples.parquet`

No se suben los Parquet al repositorio. El notebook 01 valida el tamaño del catálogo, la separación por `query_id` y la cobertura completa de los productos anotados.

El notebook 02 acepta una grabación propia/autorizada en `data/voice_samples/<voz>.wav`. El menú permite elegir el perfil. Las grabaciones y perfiles contienen información de voz. Los WAV no se suben; el `.gitignore` protege nuevas grabaciones, perfiles generados y audios de escenario. El repositorio ya incluye perfiles `.pt` versionados: si esos perfiles no deben ser públicos, hay que retirarlos y limpiar también su historial antes de compartirlo.

Los audios de los seis escenarios se buscan en `data/scenario_audio/<voz>/`. Si faltan, el notebook 07 enumera los nombres requeridos. Cada turno conserva transcripción, operaciones, estado final, audio de entrada y respuesta generada bajo `output/`.

## Evidencia producida

El notebook 03 guarda los parámetros ajustados solo en desarrollo y reporta nDCG@10 de BM25, sistema completo y ablaciones con las mismas consultas de evaluación. El notebook 07 produce porcentaje de escenarios completados, incumplimientos, WER/CER y errores de entidades ASR, comparación con transcripción correcta, inteligibilidad/semejanza TTS, latencias por etapa y carga inicial separada. También genera cinco aciertos y cinco fallos con el diagnóstico del verificador y operaciones como evidencia.

Los archivos generados quedan en `output/resultados/` y `output/escenarios/`; no se incluyen en el commit ni se deben completar con resultados históricos. La matriz de trazabilidad está en [`docs/LAB4_MODULAR_ALINEACION.md`](docs/LAB4_MODULAR_ALINEACION.md).
