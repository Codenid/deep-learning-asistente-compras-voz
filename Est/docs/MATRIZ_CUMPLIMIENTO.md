# Matriz de cumplimiento — Laboratorio 4

Estado: ✅ implementado en el código · 🎙️ implementado; requiere las grabaciones del grupo para producir resultados ·
📝 lo completa el grupo tras ejecutar.

| # | Requisito del enunciado | Estado | Dónde |
|---|---|---|---|
| **Dataset** ||||
| 1 | ESCI small filtrado por español | ✅ | `src/datos.py` (`small_version == 1`, `product_locale == "es"`) |
| 2 | Catálogo ≥ 5 000 productos con títulos, descripciones, atributos e ids | ✅ | 10 688 productos; completa con distractores si faltara |
| 3 | ≥ 200 consultas de evaluación con todos sus productos anotados en el catálogo | ✅ | 250 eval; aserción de cobertura |
| 4 | Separadas por `query_id`: train = desarrollo, test = evaluación | ✅ | `consultas.parquet` (`conjunto` dev/eval) |
| 5 | Tienda simulada: precios, existencias, carritos y pedidos; semilla fija y restaurable | ✅ | `src/tienda.py`, notebook §3 (huella idéntica tras restaurar) |
| 6 | Etiquetas ESCI solo para evaluar/ajustar; no consultables por el agente | ✅ | `output/datos/evaluacion/qrels.parquet`; el agente solo ve catálogo y tienda |
| **Tareas** ||||
| 7 | ASR integrado con la conversación en español | ✅ 🎙️ | `src/voz.py` (Whisper large-v3-turbo), §9 y §13 |
| 8 | RAG sobre el catálogo; recomendaciones sustentadas en lo recuperado | ✅ | `buscar_productos`, `ver_producto` |
| 9 | Atributos no verificables = desconocidos | ✅ | `consultar_atributo` + campos vacíos → "desconocido"; escenario T10 |
| 10 | Agente que elige operaciones: consultar, carrito, cotización, pedido | ✅ | `src/agente.py` + 9 herramientas |
| 11 | Estado de la conversación y aclaraciones | ✅ | `Estado` inyectado en cada turno; E02, T19 |
| 12 | Validar cantidades, presupuesto y existencias por código | ✅ | `src/herramientas.py`, `src/tienda.py` |
| 13 | Revalidar al confirmar; sin cambios parciales ni pedidos duplicados | ✅ | `Tienda.confirmar` (transacción + UNIQUE); E06, T17, T18; autoprueba |
| 14 | TTS con voz propia/autorizada clonada; textos distintos a la referencia | ✅ 🎙️ | `TTSClonado` (XTTS-v2) con verificación de texto |
| 15 | Modelo base léxico + ablación con las mismas consultas | ✅ | BM25 vs sistema; ablaciones sin reranker y sin denso (§5) |
| 16 | Modelos preentrenados; recuperación, control, memoria, herramientas y validaciones propios | ✅ | Todo `src/` es del grupo; solo se usan pesos preentrenados |
| 17 | Todo en Colab/notebook, sin APIs externas de inferencia | ✅ | Modelos locales; notebook ejecutable en local o Colab |
| 18 | Justificar modelos y gestionar memoria | ✅ | Tabla §6, `carga_modelos.csv` (tiempo y VRAM por modelo), nf4 |
| **Pruebas** ||||
| 19 | ≥ 20 escenarios con estados iniciales reproducibles | ✅ | `src/escenarios.py` (20) + `factibilidad()` |
| 20 | 6 por audio: compra OK, ambigua, cambio, agotado, corrección de transcripción, cambio de stock + reconfirmación | ✅ 🎙️ | E01–E06 |
| 21 | ≥ 3 pruebas por voz con varias intervenciones | ✅ | Las 6 tienen 3 a 6 turnos |
| 22 | Conservar audios, transcripciones, operaciones y estado final | ✅ | `output/escenarios/<modo>/<id>/` (`registro.json`, `estado_final.json`, wav) |
| 23 | Repetir los casos de voz con la transcripción correcta | ✅ | §9.2 y tabla "diferencia atribuible al ASR" |
| **Métricas** ||||
| 24 | nDCG@10 sobre candidatos anotados con E = 1, S = 0,1, C = 0,01, I = 0 | ✅ | `GANANCIAS`, `recuperacion.ndcg` |
| 25 | % de escenarios completados correctamente | ✅ | `metricas_escenarios.csv` |
| 26 | Incumplimientos de restricciones | ✅ | presupuesto, cantidad, consentimiento, duplicado, stock negativo |
| 27 | Errores de transcripción en cantidades, importes y productos | ✅ 🎙️ | `metricas_asr.csv`, `asr_por_turno.csv` |
| 28 | Inteligibilidad y semejanza con la voz de referencia | ✅ 🎙️ | `metricas_tts_por_respuesta.csv` |
| 29 | Latencia desde el fin de la grabación por etapa; carga inicial aparte | ✅ | `latencias_por_turno.csv`, `latencias_resumen.csv`, `carga_modelos.csv` |
| 30 | No ajustar con las consultas de evaluación | ✅ | α y β elegidos solo en dev |
| **Entrega** ||||
| 31 | Notebook: datos, índice, restauración de la tienda | ✅ | §2–§4 |
| 32 | Notebook: voz, agente, memoria, herramientas, validaciones | ✅ | §6–§9, §13 |
| 33 | Notebook: modelo base, ablación y resultados de las pruebas | ✅ | §5, §8–§11 |
| 34 | Instrucciones de ejecución, versiones, modelos y configuración | ✅ | §1 (`versiones.json`), §14, `requirements.txt` |
| 35 | ≥ 5 aciertos y 5 fallos con causas y limitaciones | ✅ 📝 | §12: candidatos automáticos + tabla a completar |
| 36 | Video ≤ 20 min (4 + 4 + 8 + 4) | 📝 | `docs/GUIA_VIDEO.md` |
