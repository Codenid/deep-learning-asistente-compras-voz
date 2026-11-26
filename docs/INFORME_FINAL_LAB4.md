# Informe final — Laboratorio 4

## Solución implementada

Desarrollamos un asistente de compras por voz en español que recupera productos del catálogo ESCI, conserva las restricciones de la conversación y opera sobre una tienda simulada. Un modelo de lenguaje coordina herramientas; el código valida cantidades, presupuesto, existencias y consentimiento. La respuesta se sintetiza con XTTS-v2 a partir de una voz propia o autorizada.

## Recorrido de la solución

1. **Datos y catálogo:** el notebook 01 prepara el catálogo en español, separa consultas de desarrollo y evaluación por `query_id`, y mantiene las etiquetas ESCI fuera de la información consultable por el asistente.
2. **Perfil de voz:** el notebook 02 calcula las representaciones de una grabación autorizada para reutilizarlas con XTTS-v2. No entrena XTTS desde cero.
3. **Recuperación:** el notebook 03 compara BM25 con recuperación densa e híbrida, aplica un reranker y ajusta los pesos con desarrollo. También ejecuta las ablaciones sobre las mismas consultas.
4. **Tienda:** el notebook 04 prepara precios y existencias ficticios con semilla fija. SQLite permite restaurar la tienda y confirmar pedidos en una transacción, sin actualizaciones parciales ni duplicados.
5. **Agente:** el notebook 05 integra un único agente, nueve herramientas y memoria para presupuesto, preferencias, carrito, cotización y pedidos. Las reglas críticas se validan en Python.
6. **Integración de voz:** el notebook 06 conecta ASR, revisión de transcripción, agente, tienda y TTS en una interacción por turnos.
7. **Evaluación:** el notebook 07 ejecuta 14 escenarios de texto y seis de audio; compara los resultados de audio con las transcripciones correctas y genera métricas de finalización, restricciones, ASR, voz y latencia.

## Resultado funcional comunicado por el equipo

La última ejecución local reportada por el equipo completó **20 de 20 escenarios** y registró **cero incumplimientos** de las reglas de compra. El análisis de recuperación incluye ejemplos de aciertos y fallos de ranking; completar los escenarios operativos no elimina las limitaciones del recuperador.

La copia del repositorio revisada para este informe no contiene la carpeta `output/` ni las salidas de la última ejecución. Por eso, los valores finales de nDCG, WER/CER, métricas TTS y latencia deben quedar respaldados por el notebook 07 ejecutado o por sus CSV/JSON finales antes de entregar. Las cifras de ejecuciones anteriores no se presentan aquí como métricas finales.

## Entorno de ejecución y alcance

La ejecución final comunicada se realizó **localmente en WSL2, no en Google Colab**, y no utilizó APIs externas de inferencia. La solución satisface el flujo funcional del laboratorio en ese entorno. El enunciado pide que el procesamiento de modelos para la entrega se ejecute en Colab; por tanto, no afirmamos haber cumplido ese requisito de entorno.

## Límites identificados

- La tienda usa precios y existencias ficticios; no representa inventario comercial real.
- Algunos productos no tienen descripción, color u otros atributos. El asistente debe declarar como desconocido aquello que no pueda verificar.
- XTTS-v2 usa una grabación de referencia y su uso debe respetar la licencia aplicable y la autorización de la persona cuya voz se utiliza.
- La interacción es por turnos; el costo de carga inicial de modelos se reporta separado de la latencia de cada consulta.

## Cierre

La solución integra datos ESCI, recuperación con baseline y ablación, tienda transaccional, agente con memoria, entrada hablada y respuesta sintetizada. Según la ejecución local reportada, los 20 escenarios operativos pasan sin incumplimientos. La diferencia pendiente respecto del enunciado es el entorno: el equipo ejecutó localmente y no en Colab. Los resultados cuantitativos finales deben acompañar la entrega desde la última ejecución del notebook 07.
