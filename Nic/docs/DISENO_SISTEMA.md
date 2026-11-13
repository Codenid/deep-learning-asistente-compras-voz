# Diseño del sistema — Asistente de compras por voz

## 1. Arquitectura

```mermaid
flowchart LR
    MIC[Micrófono / WAV] --> ASR[ASR<br/>Whisper large-v3-turbo]
    ASR --> COR{¿Usuario corrige<br/>la transcripción?}
    COR --> AG[Agente LLM<br/>Qwen2.5-7B nf4]
    AG -- tool_call --> HER[Herramientas<br/>validación por código]
    HER --> RAG[RAG<br/>BM25 + e5 + reranker]
    HER --> TDA[(Tienda SQLite<br/>precios, stock,<br/>carritos, pedidos)]
    RAG --> CAT[(Catálogo ESCI<br/>sin etiquetas)]
    HER -- resultado JSON --> AG
    MEM[(Memoria / Estado)] <--> AG
    AG --> TTS[TTS XTTS-v2<br/>voz clonada]
    TTS --> SAL[Respuesta hablada]
    QR[(qrels ESCI)] -.solo evaluación.-> EV[nDCG@10]
    RAG -.-> EV
```

## 2. Datos

| Elemento | Detalle | Archivo |
|---|---|---|
| Catálogo | 10 688 productos ES (título, descripción, características, marca, color, id) | `output/datos/catalogo.parquet` |
| Consultas | 250 eval (split test) + 150 dev (split train), separadas por `query_id` | `output/datos/consultas.parquet` |
| Etiquetas | E/S/C/I de los 10 928 pares anotados; **solo evaluación** | `output/datos/evaluacion/qrels.parquet` |
| Tienda | Precios log-normal (,99), stock 0–25 (8 % agotado), semilla fija | `output/tienda/tienda_base.sqlite` |

Todos los productos anotados de cada consulta están en el catálogo (aserción en la celda de datos, §2).

## 3. Recuperación (RAG)

| Componente | Función |
|---|---|
| BM25 | Modelo base léxico (título + marca + color + características + descripción) |
| e5-base | Embeddings densos con prefijos `query:` / `passage:`, caché en `output/indice/` |
| Híbrido | `α·denso + (1−α)·BM25` (min-max por consulta) sobre la unión de los top-50 de cada uno |
| Reranker | bge-reranker-v2-m3 sobre los top-30 híbridos: `β·reranker + (1−β)·híbrido` |
| Ajuste | α y β por grilla 0..1 **solo con dev**; eval se mide una vez |
| Ablación | Sin reranker (= híbrido) y sin denso (BM25 + reranker), mismas consultas |

Métrica oficial: nDCG@10 sobre los candidatos anotados (E = 1, S = 0,1, C = 0,01, I = 0). Complemento: nDCG@10 sobre el
catálogo completo (no anotados = 0).

## 4. Agente

Un solo LLM con llamado nativo a herramientas (`<tool_call>` de Qwen). Bucle por turno: el LLM propone llamadas → el
código las valida y ejecuta → el resultado vuelve al LLM → se comprueban las acciones pendientes antes de terminar
(máx. 16 pasos). Los mensajes de cotización, pedido, precios, stock y atributos desconocidos usan los resultados
reales de las herramientas. El lector admite varias llamadas aunque el modelo omita etiquetas de cierre.

| Herramienta | Qué hace | Validaciones por código |
|---|---|---|
| `buscar_productos` | RAG, filtros de tienda y orden por precio | consulta no vacía, `precio_max > 0`, k ∈ 1..10, cantidad, marca, color y compatibilidad; presupuesto total restante |
| `ver_producto` | Detalle; campos vacíos = "desconocido" | id existente |
| `consultar_atributo` | Busca el atributo en el texto del producto | si no aparece → "desconocido" |
| `registrar_restricciones` | Presupuesto y preferencias en memoria | presupuesto > 0, lista de textos |
| `agregar_al_carrito` / `cambiar_cantidad` | Modifica el carrito | entero, 1..20 (0 = quitar), ≤ stock, carrito abierto |
| `ver_carrito` | Contenido y total | — |
| `cotizar` | Total + validación de stock y presupuesto | cotización inválida si algo falla |
| `confirmar_pedido` | Registra el pedido | cotización **mostrada en un turno anterior** + afirmación explícita del usuario; transacción atómica; UNIQUE por cotización |

**Memoria (`Estado`)**: presupuesto, preferencias, carrito, última cotización (y si fue mostrada), pedidos y productos
mostrados, cantidades solicitadas y búsquedas por tipo de producto. Se inyecta en el prompt de sistema en cada turno,
así sobrevive aunque el historial se recorte a 6 turnos.

Los cambios de precio o stock obligan a recotizar. La cotización actualizada se presenta antes de permitir otra
confirmación. Los detalles de las correcciones y las pruebas están en [CORRECCIONES_Y_VALIDACION.md](CORRECCIONES_Y_VALIDACION.md).

**Confirmación sin cambios parciales ni duplicados** (celda de la tienda, §3): `BEGIN IMMEDIATE` → revalida versión del carrito,
stock, precio y presupuesto → descuenta stock con `UPDATE ... WHERE stock >= cantidad` → inserta pedido → `COMMIT`; ante
cualquier problema `ROLLBACK`. Repetir la confirmación devuelve el mismo pedido (`ya_registrado`).

## 5. Voz

| Etapa | Implementación |
|---|---|
| ASR | Whisper large-v3-turbo fp16, idioma forzado a español |
| Corrección | El usuario ve la transcripción y puede corregirla antes de ejecutar (E05 y demo) |
| TTS | XTTS-v2 con latentes de la referencia calculados una sola vez; el texto nunca coincide con el de la referencia |
| Inteligibilidad | WER entre el texto sintetizado y su re-transcripción con el ASR |
| Semejanza | Coseno de x-vectors WavLM-SV entre la respuesta y la referencia (techo opcional con `referencia_2.wav`) |
| Errores ASR | WER/CER + errores en cantidades, importes (número + euros) y términos de producto |

## 6. Memoria GPU (16 GB)

| Modelo | VRAM aprox. |
|---|---|
| Qwen2.5-7B-Instruct nf4 | 5,5 GB |
| Whisper large-v3-turbo fp16 | 1,6 GB |
| XTTS-v2 | 2,0 GB |
| e5-base + bge-reranker-v2-m3 fp16 | 1,7 GB |
| **Total** | **≈ 11 GB** (+ caché KV) |

Si la VRAM no alcanza: `LLM_4BIT = True` ya está activo; bajar a `Qwen/Qwen2.5-3B-Instruct` o usar
`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` como reranker.

## 7. Escenarios y verificación

20 escenarios (celda de escenarios, §7): 6 por voz (todos con varias intervenciones) y 14 por texto. Cada uno parte de
`restaurar()` + una preparación determinista (agotar productos, fijar stock) y puede tener eventos entre turnos (cambio de
stock o precio). La verificación es automática: pedidos, ítems y cantidades, total ≤ presupuesto, aclaración en el turno
esperado, pedidos solo con consentimiento, sin duplicados y estado final de la tienda.
