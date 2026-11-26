# Trazabilidad de la solución y evidencia de evaluación

Nuestra solución conserva el diseño de la presentación: Whisper para voz, recuperación BM25 + e5 + reranker, un agente Qwen con nueve herramientas, una tienda SQLite y síntesis XTTS-v2. Separamos la implementación en notebooks para que cada componente pueda explicarse y ejecutarse sin duplicar lógica: las clases compartidas están en `src/lab4_asistente/`.

Las cifras de la presentación (nDCG, 3/20 escenarios, latencia y semejanza) pertenecen a una ejecución anterior del prototipo. La versión modular no las presenta como resultados nuevos. El notebook 07 genera métricas actuales desde la ejecución local o de Colab y conserva registros para contrastar cada resultado.

## Mapa de componentes

| Componente de nuestra solución | Responsabilidad | Notebook/código |
|---|---|---|
| Preparación ESCI | Selecciona productos españoles; separa desarrollo/evaluación por `query_id`; deja qrels fuera del catálogo consultable. | 01 · `datos.py` |
| Perfil de voz | Calcula y persiste latentes XTTS-v2 por identidad a partir de un WAV propio/autorizado. No requiere transcripción `.txt`. | 02 · `voz.py` |
| Recuperación RAG | BM25 como baseline; multilingual-e5-base genera candidatos densos; bge-reranker-v2-m3 reordena. α y β se ajustan en dev. | 03 · `recuperacion.py` |
| Tienda simulada | Genera precios/stock con semilla fija; persiste carrito, cotizaciones y pedidos en SQLite. Revalida y confirma en una transacción. | 04 · `tienda.py` |
| Agente y estado | Un Qwen decide cuándo llamar nueve herramientas. Python valida cantidades, atributos, presupuesto, stock, consentimiento y duplicados. | 05 · `agente.py`, `herramientas.py`, `modelos.py` |
| Integración hablada | ASR, revisión de transcripción, agente, herramientas, tienda y TTS por turnos. | 06 · `runtime.py`, `voz.py` |
| Pruebas y medición | Ejecuta 14 escenarios de texto y 6 de audio; guarda evidencia y compara audio frente a transcripción correcta. | 07 · `escenarios.py`, `evaluacion.py` |

## Requisitos de datos y separación de evaluación

El notebook 01 selecciona al menos 5 000 productos y al menos 200 consultas `test`, con todos sus productos anotados presentes en el catálogo; también conserva consultas `train` para desarrollo. Las etiquetas E/S/C/I viven en `output/datos/evaluacion/qrels.parquet`: las herramientas del agente reciben solo el catálogo y la tienda. Precios y existencias son ficticios, generados con semilla fija y restaurables.

## Recuperación, baseline y ablación

El notebook 03 evalúa BM25, e5 denso, recuperación híbrida y sistema con reranker. Se comparan las variantes con las mismas consultas; el ajuste de pesos se realiza en `train/dev`, no en `test/eval`. El nDCG@10 usa las ganancias del enunciado: E=1, S=0,1, C=0,01, I=0. Reportamos además nDCG sobre el catálogo completo como medición complementaria, separada de la métrica sobre candidatos anotados.

## Seguridad de compra y memoria

El agente es único. Su memoria conserva presupuesto, preferencias, carrito, cotización y pedidos. Una afirmación del LLM no registra una compra: el código exige una cotización mostrada y una confirmación explícita. Al confirmar, SQLite revisa de nuevo precio, stock y presupuesto; `BEGIN IMMEDIATE` evita una escritura parcial y la unicidad de la cotización evita duplicados. Los escenarios E06/T17/T18 cubren cambios entre cotización y confirmación y repetición de confirmación.

## Plan de ejecución de las pruebas requeridas

El notebook 07 restaura el estado antes de cada escenario y produce:

| Prueba solicitada | Evidencia que genera la solución |
|---|---|
| 20 escenarios: 14 texto + 6 voz | Tabla de escenarios, estado final, operaciones y archivos `registro.json` por escenario. |
| Seis situaciones de audio y al menos tres diálogos de varios turnos | Entrada WAV, transcripción ASR, respuesta y salida sintetizada, con turnos guardados. |
| Repetición con transcripción correcta | Tabla `escenarios_audio_vs_transcripcion_correcta.csv` para separar fallos de reconocimiento de fallos del agente. |
| Baseline y ablación | `recuperacion_eval.csv`, parámetros elegidos con dev y resultados por consulta en el notebook 03. |
| nDCG@10, terminación y restricciones | nDCG en notebook 03; finalización e incumplimientos en `metricas_escenarios.csv`. |
| Errores ASR en cantidades, importes y productos | WER/CER y conteo de errores por entidad en `metricas_asr.csv`. |
| Calidad de voz | WER de re-transcripción y coseno WavLM en `metricas_tts_por_respuesta.csv`. |
| Latencia de turno y carga inicial | `latencias_por_turno.csv` desglosada por ASR, recuperación, LLM, herramientas y TTS; cargas de modelos aparte. |
| Cinco aciertos y cinco fallos, con causas/evidencia | `analisis_cinco_aciertos_y_fallos.csv`: verificador, errores de herramientas, operaciones y respuestas observadas. |

Los valores se obtienen al ejecutar; esta trazabilidad no los sustituye. Las causas se derivan del estado esperado y de los registros de ejecución, no de explicaciones hipotéticas sobre el modelo.

## Gestión de recursos

En el portátil local con 12 GB de VRAM, Qwen2.5-7B es el único modelo que permanece en GPU durante la integración y se carga en 4 bits. Recuperación, Whisper y XTTS se mantienen en CPU en los notebooks integrados. El notebook de perfiles carga XTTS en GPU en una ejecución aislada; el notebook de recuperación hace lo propio con e5 y el reranker. Cerramos cada kernel pesado antes de iniciar el siguiente. Qwen no usa `device_map="auto"` ni cambia a CPU si falta VRAM: la configuración exige CUDA y muestra un error operativo claro.

El enunciado indica Colab como entorno de procesamiento para la entrega. La solución está preparada para ese runtime y no llama APIs externas; la ejecución local permite validar el flujo, pero no reemplaza evidencia en Colab cuando el curso exija ese entorno.
