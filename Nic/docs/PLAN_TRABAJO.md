# TAREAML4 — Plan de trabajo: asistente de compras por voz

Enunciado: Laboratorio 4 (ESCI + ASR + RAG + agente + TTS con clonación). Diseño: `DISENO_SISTEMA.md`.
Cumplimiento punto por punto: `MATRIZ_CUMPLIMIENTO.md`. Video: `GUIA_VIDEO.md`.

## Estructura

```
TAREAML4/
├── Laboratorio4_Asistente.ipynb  TODO el sistema: tablero, datos, tienda, RAG, agente, voz, escenarios, evaluación
├── requirements.txt              versiones verificadas juntas (Python 3.11)
├── update.bat                    crea/actualiza el entorno .venv (doble clic)
├── multimedia.bat                abre el grabador de voces en el navegador (doble clic)
├── input/                        ESCI (parquet)
├── multimedia/                   grabador_voz.py · multimedia001, 002…: referencia.wav, audios/, entrenamiento/ · ACTIVA.txt
├── output/                       datos, indice, tienda, escenarios, resultados (bitácora, métricas, figuras)
└── docs/                         enunciado (Word), plan, diseño, matriz, guías de grabación y video, version_anterior/
```

## Fases

| Fase | Actividad | Quién / dónde | Estado |
|---|---|---|---|
| 0 | `update.bat`: entorno `.venv` (Python 3.11 + torch CUDA + requirements + kernel Jupyter) | Laptop 16 GB | Pendiente |
| 1 | `multimedia.bat`: grabar referencia, entrenar y elegir voz (*Usar en el programa*) | Grupo | Pendiente |
| 2 | Grabar los 23 audios de E01–E06 en el mismo grabador (frases de `docs/GUION_GRABACION.md`) | Grupo | Pendiente |
| 3 | Autoprueba sin modelos | Notebook §7 (celda 26) | Listo en el código |
| 4 | Ejecutar notebook §1–§5: datos, tienda, índice, recuperación (BM25 vs sistema + ablación) | Notebook | Pendiente |
| 5 | §6–§9: carga de modelos y 20 escenarios + repetición de voz con transcripción correcta | Notebook | Pendiente |
| 6 | §10–§12: métricas, gráficos; completar tabla de 5 aciertos y 5 fallos | Notebook | Pendiente |
| 7 | Ensayar demo (`MODO_INTERACTIVO = True`, `turno_voz()`) y grabar video ≤ 20 min | Grupo | Pendiente |

## Tiempos esperados (GPU 16 GB, a validar con la bitácora)

| Paso | Estimado |
|---|---|
| Datos + tienda | < 1 min |
| Embeddings del catálogo (10,7k) | 1–2 min (en caché después) |
| Evaluación de recuperación (400 consultas + grillas) | 3–6 min |
| Carga de modelos (primera vez, con descarga) | 10–20 min; luego 1–2 min |
| 14 escenarios de texto | 10–25 min |
| 6 escenarios de voz + repetición | 10–20 min |
| Latencia por turno de voz | ~5–15 s (ASR ~0,5 s, LLM 2–10 s según pasos, TTS 2–5 s) |

## Checklist de entrega

- [ ] Notebook ejecutado con salidas visibles
- [ ] `output/resultados/`: métricas, latencias, carga de modelos, aciertos y fallos, figuras
- [ ] `output/escenarios/`: audios, transcripciones, operaciones y estado final por escenario
- [ ] Tabla 12.1 completada (5 aciertos y 5 fallos con causa) y limitaciones revisadas
- [ ] Celda de enunciado pegada
- [ ] Video ≤ 20 min con demo por voz y espera real visible
