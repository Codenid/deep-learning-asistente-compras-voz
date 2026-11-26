# Matriz de cumplimiento — Laboratorio 4

## Estado de la entrega revisada

La solución está organizada en siete notebooks y clases compartidas en `src/lab4_asistente/`. La trazabilidad detallada de los componentes y de las salidas requeridas está en [`LAB4_MODULAR_ALINEACION.md`](LAB4_MODULAR_ALINEACION.md).

| Criterio | Implementación/evidencia | Estado actual |
|---|---|---|
| Catálogo ESCI en español, consultas separadas por `query_id` y etiquetas fuera del agente | Notebook 01; catálogo y qrels separados | Implementado |
| Baseline léxico, recuperación RAG y ablaciones | Notebook 03; BM25, recuperación híbrida, reranker, ajuste en dev y evaluación | Implementado; adjuntar métricas finales |
| Tienda simulada reproducible y transaccional | Notebook 04; SQLite, restauración, revalidación de stock/presupuesto y pedido idempotente | Implementado |
| Agente único con memoria y herramientas | Notebook 05; validaciones críticas en Python | Implementado |
| ASR, revisión de transcripción y TTS con voz autorizada | Notebooks 02 y 06 | Implementado |
| 20 escenarios, 14 de texto y 6 de voz | Notebook 07; la última ejecución comunicada por el equipo completó 20/20, con 0 incumplimientos | Resultado reportado; adjuntar registros de la corrida final |
| Métricas de recuperación, ASR/TTS y latencia por etapa | Notebooks 03 y 07 generan CSV/JSON correspondientes | Pendiente de adjuntar y contrastar con la última ejecución |
| Entorno solicitado | La ejecución comunicada se realizó localmente en WSL2, no en Google Colab | Diferencia respecto al enunciado; declararla explícitamente |
| Dependencias | `requirements.txt` y `requirements-lab4-modular.txt` contienen versiones distintas | Mapa consolidado en [`DEPENDENCIAS_LAB4_CONSOLIDADO.md`](DEPENDENCIAS_LAB4_CONSOLIDADO.md); no se instalaron |
| Presentación y reporte | PPT actualizada y [`INFORME_FINAL_LAB4.md`](INFORME_FINAL_LAB4.md) | Revisar integrantes y adjuntar resultados finales antes de entregar |

## Organización de notebooks

1. `01_datos_y_catalogo.ipynb`: prepara ESCI, catálogo, particiones y qrels.
2. `02_preparar_perfil_de_voz.ipynb`: prepara perfiles XTTS-v2 desde grabaciones autorizadas.
3. `03_rag_y_ablacion.ipynb`: baseline, recuperación y evaluación/ablación.
4. `04_tienda_sqlite.ipynb`: estado determinista, cotizaciones y pedidos transaccionales.
5. `05_agente_y_memoria.ipynb`: herramientas y estado conversacional.
6. `06_integracion_voz_y_compra.ipynb`: integración por turnos de ASR, agente, tienda y TTS.
7. `07_pruebas_y_resultados.ipynb`: escenarios, análisis y métricas finales.

## Evidencia aún necesaria para cerrar la entrega

- Incorporar los registros de escenario que respaldan el resultado 20/20.
- Adjuntar desde la última corrida los resultados nDCG@10/ablación, métricas ASR y TTS, latencias por turno y carga inicial.
- Confirmar que la PPT use esos mismos archivos y cifras.
- Declarar que se ejecutó en local y que no se realizó una corrida en Colab.
- Definir una sola combinación de dependencias antes de una instalación posterior. El consolidado no implica ejecutar instalaciones.
