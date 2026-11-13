# Matriz de cumplimiento — Laboratorio 4 (Word del profesor vs. proyecto)

Todo el sistema está en `Laboratorio4_Asistente.ipynb` (50 celdas; "c" = número de celda).

**Estado:** ✅ implementado y probado · 🎙️ implementado, produce resultados cuando estén las grabaciones · 📝 lo completa el grupo

## 1. Descripción del problema

| # | Lo que pide el profesor | Lo que tenemos | Dónde | Estado |
|---|---|---|---|---|
| 1 | Recibir consultas habladas en español | Whisper large-v3-turbo con idioma forzado a español; entrada por micrófono (demo) o WAV (escenarios) | §6 c19–c20, §9 c31, §13 c43 | ✅🎙️ |
| 2 | Usar un modelo de lenguaje con RAG | Qwen2.5-7B-Instruct (4 bits) que llama a `buscar_productos` (BM25 + e5 + reranker) | §4 c13, §6 c18, §7 c22–c23 | ✅ |
| 3 | Ejecutar acciones sobre una tienda simulada | 9 herramientas sobre SQLite: buscar, ver, verificar atributo, restricciones, agregar, cambiar cantidad, ver carrito, cotizar, confirmar | §3 c10, §7 c22 | ✅ |
| 4 | Responder por voz con TTS y clonación de voz | XTTS-v2 con la grabación de referencia; WAV de cada respuesta | §6 c19, §9 c31, §13 c43 | ✅🎙️ |
| 5 | Buscar productos | `buscar_productos` con filtro de precio máximo | §7 c22 | ✅ |
| 6 | Comparar alternativas | Búsqueda con varios resultados y `ver_producto`; escenario T16 | §7 c22, §8 c29 | ✅ |
| 7 | Consultar precios y existencias | Precio y stock en vivo desde la tienda en cada resultado | §7 c22 | ✅ |
| 8 | Preparar una cotización | `cotizar`: total, validación de stock y presupuesto, id de cotización | §3 c10, §7 c22 | ✅ |
| 9 | Registrar el pedido tras la confirmación del usuario | `confirmar_pedido` solo con cotización ya mostrada + afirmación explícita (verificada por código) | §7 c22 | ✅ |
| 10 | Conservar cantidades, presupuesto y preferencias | `Estado` (presupuesto, preferencias, carrito, cotización, pedidos, productos mostrados) inyectado en cada turno | §7 c22–c23 | ✅ |
| 11 | Permitir aclaraciones y cambios de decisión | Regla de aclaración en el prompt + `cambiar_cantidad` / preferencias reemplazables; escenarios E02, E03, T15, T19, T20 | §7 c23, §8–§9 | ✅ |
| 12 | Ejemplo: varios productos con presupuesto, cambio de cantidad y confirmación; si cambia el stock, detectar y proponer alternativa | Escenarios T08 (varios con presupuesto), E03 (cambio de cantidad), E06 (cambio de stock → rechazo → alternativa → reconfirmación) | §7 c24, §8–§9 | ✅ |

## 2. Dataset

| # | Lo que pide el profesor | Lo que tenemos | Dónde | Estado |
|---|---|---|---|---|
| 13 | ESCI, versión reducida (small) filtrada por español | `small_version == 1` y `product_locale == "es"` | §2 c7 | ✅ |
| 14 | Catálogo ≥ 5 000 productos con títulos, descripciones, atributos e ids | 10 688 productos: id, título, descripción, características, marca y color (HTML limpio) | §2 c7–c8 → `output/datos/catalogo.parquet` | ✅ |
| 15 | ≥ 200 consultas de evaluación con todos sus productos anotados en el catálogo | 250 consultas de evaluación + aserción de que todo producto anotado está en el catálogo | §2 c7 | ✅ |
| 16 | Separar por `query_id`: train = desarrollo, test = evaluación | 150 de desarrollo (train) y 250 de evaluación (test) | §2 c7 → `consultas.parquet` | ✅ |
| 17 | Tienda: precios, existencias, carritos y pedidos | Tablas `productos`, `carritos`, `carrito_items`, `cotizaciones`, `pedidos`, `pedido_items` | §3 c10 | ✅ |
| 18 | Datos ficticios con semilla fija y restaurables | Precios y stock con `SEMILLA`; `restaurar()` copia la base; huella idéntica tras dos restauraciones | §3 c10–c11 | ✅ |
| 19 | Etiquetas ESCI solo para evaluar/ajustar; no consultables por el agente | `qrels.parquet` en carpeta aparte; aserción de que el catálogo no las contiene; las herramientas no las leen | §2 c7–c8 | ✅ |

## 3. Tareas

| # | Lo que pide el profesor | Lo que tenemos | Dónde | Estado |
|---|---|---|---|---|
| 20 | ASR integrado con la conversación en español | Audio → Whisper → (corrección opcional) → agente, en escenarios y en la demo | §6 c19, §9 c31, §13 c43 | ✅🎙️ |
| 21 | RAG sobre el catálogo; recomendaciones sustentadas en lo recuperado | Búsqueda híbrida + reranker; el prompt obliga a usar herramientas y no inventar datos | §4 c13, §7 c23 | ✅ |
| 22 | Atributos no verificables = desconocidos | `consultar_atributo` busca en el texto del producto; campos vacíos devuelven "desconocido"; escenario T10 | §7 c22 | ✅ |
| 23 | Agente que elige operaciones: consultar, carrito, cotización, pedido | Bucle LLM → llamada a herramienta → validación → resultado → LLM (máx. 8 pasos por turno) | §7 c23 | ✅ |
| 24 | Mantener estado y pedir aclaración ante falta de información o ambigüedad | Estado persistente + regla de aclaración + errores de herramienta que piden la cantidad faltante; E02, T19 | §7 c22–c23 | ✅ |
| 25 | Validar cantidades, presupuesto y existencias por código | Enteros 1..20, stock, presupuesto, producto existente, carrito abierto | §3 c10, §7 c22 | ✅ |
| 26 | Al confirmar: revalidar y actualizar sin cambios parciales ni duplicados | Transacción `BEGIN IMMEDIATE` con rollback; `UNIQUE` por cotización; repetir devuelve el mismo pedido | §3 c10; autoprueba c26 | ✅ |
| 27 | Voz propia o autorizada con grabación de referencia | `multimedia/<voz activa>/referencia.wav`, grabada con `multimedia.bat` (guía en `docs/GUIA_VOZ_REFERENCIA.md`) | §6 c19–c20 | ✅🎙️ |
| 28 | Textos generados distintos de la referencia | Verificación por código antes de sintetizar | §6 c19 | ✅ |
| 29 | Comparar con un modelo base de búsqueda léxica | BM25 vs. sistema completo, mismas consultas de evaluación | §5 c16 | ✅ |
| 30 | Ablación sobre un componente | Sistema sin reranker y sistema sin búsqueda densa | §5 c16 | ✅ |
| 31 | Componentes propios; modelos preentrenados permitidos; un solo agente | Recuperación, control, memoria, herramientas y validaciones escritos por el grupo; un solo LLM | c4–c25 | ✅ |
| 32 | Procesamiento dentro del notebook, sin APIs externas | Todos los modelos se descargan y corren localmente | Notebook completo | ✅ |
| 33 | Interacción por turnos desde el notebook | `turno_voz()`: graba, transcribe, permite corregir, responde y reproduce | §13 c43 | ✅ |
| 34 | Justificar modelos y gestionar memoria | Tabla de modelos con motivo y VRAM; LLM en 4 bits; tiempo y VRAM de cada carga | §6 c17, c20 → `carga_modelos.csv` | ✅ |

## 4. Pruebas de funcionamiento

| # | Lo que pide el profesor | Lo que tenemos | Dónde | Estado |
|---|---|---|---|---|
| 35 | ≥ 20 escenarios con estados iniciales reproducibles | 20 escenarios: restaurar + preparación determinista + eventos entre turnos; verificación de factibilidad | §7 c24, c26 | ✅ |
| 36 | Audio: compra que cumple restricciones con pedido confirmado | E01 (pilas AA, presupuesto 30 €) | §9 c31 | ✅🎙️ |
| 37 | Audio: solicitud ambigua que requiere aclaración | E02 ("Quiero comprar una funda") | §9 c31 | ✅🎙️ |
| 38 | Audio: cambio de cantidad o preferencia conservando restricciones | E03 (de 3 a 2 botellas, mismo presupuesto) | §9 c31 | ✅🎙️ |
| 39 | Audio: producto agotado → alternativa o sin solución | E04 (termo agotado → alternativa); en texto, T11 (sin solución) | §9 c31 | ✅🎙️ |
| 40 | Audio: corrección de la transcripción antes de comprar | E05 (el usuario revisa y corrige; se registra si era necesario) | §9 c31 | ✅🎙️ |
| 41 | Audio: cambio de stock entre cotización y confirmación + repetir confirmación sin duplicar | E06 (6 turnos: rechazo, alternativa, confirmación, reconfirmación) | §9 c31 | ✅🎙️ |
| 42 | ≥ 3 pruebas de voz con varias intervenciones | Las 6 tienen de 3 a 6 turnos | §7 c24 | ✅ |
| 43 | Conservar audios, transcripciones, operaciones y estado final | Por escenario: WAV de usuario y asistente, `registro.json`, `estado_final.json` | §8 c29, §9 c31 → `output/escenarios/` | ✅ |
| 44 | Repetir los casos de voz con la transcripción correcta | Segunda corrida de E01–E06 en texto + tabla de diferencias atribuibles al ASR | §9 c31 | ✅🎙️ |

## 5. Métricas

| # | Lo que pide el profesor | Lo que tenemos | Dónde | Estado |
|---|---|---|---|---|
| 45 | nDCG@10 sobre candidatos anotados (E = 1, S = 0,1, C = 0,01, I = 0) | Para las 5 variantes, en desarrollo y evaluación; además, sobre el catálogo completo | §5 c16, §11 c37 → `recuperacion_eval.csv` | ✅ |
| 46 | % de escenarios completados correctamente | Global (14 texto + 6 voz) y por conjunto | §10 c33, §11 c38 → `metricas_escenarios.csv` | ✅ |
| 47 | Incumplimientos de restricciones | Presupuesto, cantidad, pedido sin consentimiento, duplicado, stock negativo | §10 c33 | ✅ |
| 48 | Errores de transcripción en cantidades, importes y productos | WER/CER + errores por entidad (números en palabras o dígitos, montos en euros, términos de producto) | §10 c33 → `metricas_asr.csv`, `asr_por_turno.csv` | ✅🎙️ |
| 49 | Inteligibilidad de la voz | WER de la re-transcripción de cada respuesta sintetizada | §10 c34 → `metricas_tts_por_respuesta.csv` | ✅🎙️ |
| 50 | Semejanza con la voz de referencia | Coseno de x-vectors WavLM; techo opcional con `referencia_2.wav` | §10 c34 | ✅🎙️ |
| 51 | Tiempo desde fin de grabación hasta respuesta reproducible, por etapa | ASR, recuperación, LLM, herramientas, TTS y total, por turno | §10 c35, §11 c38, §13 c43 → `latencias_por_turno.csv` | ✅ |
| 52 | Separar la carga inicial de los modelos | Tabla de carga con tiempo y VRAM por modelo, fuera de la latencia por turno | §10 c35 → `carga_modelos.csv` | ✅ |
| 53 | No ajustar con las consultas de evaluación | α y β elegidos solo con desarrollo; evaluación calculada una vez | §5 c16 → `recuperacion_ajuste_dev.csv` | ✅ |

## 6. Entrega

| # | Lo que pide el profesor | Lo que tenemos | Dónde | Estado |
|---|---|---|---|---|
| 54 | Ejecución principal en un Jupyter Notebook | `Laboratorio4_Asistente.ipynb` autocontenido | — | ✅ |
| 55 | Preparación de datos, índice y restauración de la tienda | §2–§4 | c6–c14 | ✅ |
| 56 | Integración de voz, agente, memoria, herramientas y validaciones | §6, §7, §13 | c17–c27, c43 | ✅ |
| 57 | Evaluación del modelo base, ablación y resultados de las pruebas | §5, §8–§11 | c15–c16, c28–c38 | ✅ |
| 58 | Instrucciones de ejecución, versiones, modelos y configuración | Tablero (c3), versiones (c5), tabla de modelos (c17), instrucciones (c46), `requirements.txt` | §1, §6, §14 | ✅ |
| 59 | Gráficos y resultados en celdas o en Markdown | 4 figuras en §11 + CSV en `output/resultados/` | §11 c37–c38 | ✅ |
| 60 | ≥ 5 aciertos y 5 fallos con causas | Candidatos automáticos (recuperación y escenarios) + tabla a completar | §12 c40–c41 | ✅📝 |
| 61 | Limitaciones de la solución | Lista inicial en §12.2 (revisar con los resultados reales) | §12 c41 | ✅📝 |
| 62 | Video ≤ 20 min: metodología 4, implementación 4, demostración 8, resultados 4 | Guion por bloque en `docs/GUIA_VIDEO.md`; demo con espera real en §13 | §13 c43 | 📝 |

## Resumen

| Bloque | Puntos | ✅ | ✅🎙️ (requiere grabaciones) | 📝 (grupo) |
|---|---|---|---|---|
| Problema | 12 | 10 | 2 | 0 |
| Dataset | 7 | 7 | 0 | 0 |
| Tareas | 15 | 13 | 2 | 0 |
| Pruebas | 10 | 3 | 7 | 0 |
| Métricas | 9 | 6 | 3 | 0 |
| Entrega | 9 | 6 | 0 | 3 |
| **Total** | **62** | **45** | **14** | **3** |

**Extra:** §15 (c47–c49) aplicativo de prueba: panel para escribir o hablar una consulta y ver la respuesta del agente con lo que devolvió la base de datos (productos, carrito, pedidos) y el tiempo por etapa.

**Pendientes del grupo:** grabar `referencia.wav` y los 23 audios, ejecutar el notebook, pegar el enunciado en §0, completar §12 y grabar el video.
