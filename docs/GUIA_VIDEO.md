# Guía del video (máximo 20 minutos)

| Bloque | Min | Qué mostrar | Material |
|---|---|---|---|
| Metodología | 4 | Problema, arquitectura (diagrama), elección de modelos y por qué, cómo se separan dev/eval y las etiquetas | `DISENO_SISTEMA.md` §1–§3, notebook §6 (tabla de modelos) |
| Implementación | 4 | RAG (BM25 + e5 + reranker), herramientas y validaciones por código, memoria/estado, confirmación atómica e idempotente, gestión de VRAM | Notebook §3 (`confirmar`), §7 (herramientas), `carga_modelos.csv` |
| Demostración | 8 | (1) Compra completa por voz hasta pedido confirmado; (2) caso con aclaración o recuperación (agotado / cambio de stock). Mostrar al menos una interacción completa **con la espera real** | Notebook §13: `MODO_INTERACTIVO = True`, `turno_voz()` |
| Resultados | 4 | nDCG@10 BM25 vs sistema, ablación, % escenarios, incumplimientos, errores de ASR, semejanza de voz, latencias y 2–3 fallos con su causa | Notebook §10–§12, `figuras/` |

## Guion sugerido para la demo

1. `SIS.reiniciar()` (mostrar que la tienda vuelve al estado inicial).
2. Compra: "Quiero dos paquetes de pilas AA, mi presupuesto es de treinta euros" → "Agrega la primera y prepárame la cotización" → "Sí, confirmo".
3. Recuperación: "Quiero un termo de la marca WNTHBJ" con ese producto agotado (`SIS.preparar([["agotar_palabras", ["termo", "wnthbj"]]])`) → el asistente propone una alternativa.
4. Mostrar la tabla de tiempos por etapa que imprime `turno_voz()` y los archivos guardados en `output/escenarios/demo/`.
