# Plan de cierre — Laboratorio 4

El proyecto mantiene una arquitectura académica sencilla: notebook único, recuperación local, agente con herramientas y tienda simulada SQLite. No se agregan servicios ni bases externas.

## Estado observado en el repositorio

| Área | Evidencia actual | Estado para la entrega |
|---|---|---|
| Código | Notebook con datos, RAG, tienda, agente, voz y métricas | Estructura presente; salidas no actualizadas tras las últimas correcciones |
| Dataset | `input/` contiene el archivo de fuentes; los Parquet no están versionados | Prepararlos localmente según la guía y ejecutar la preparación |
| Voz | Hay grabaciones de referencia y escenarios; notebook detecta los audios de `multimedia001` | Confirmar voz elegida y resultado de ASR/TTS en la corrida final |
| Pruebas de negocio | La última salida guardada muestra 3/20 escenarios oficiales completados | Reejecutar y corregir las causas restantes hasta demostrar los casos previstos |
| Análisis | §12.1 genera aciertos/fallos a partir de evidencia; causas se marcan como hipótesis | Contrastar las diez filas con registros y estados finales |
| Presentación | Usa cifras de una corrida anterior | Sincronizarla con la ejecución final |
| Video | Existe guion por bloques de 4 + 4 + 8 + 4 minutos | Grabar y comprobar duración máxima de 20 minutos |

## Secuencia mínima de cierre

1. Preparar el entorno y los Parquet del catálogo en `input/`.
2. Reiniciar el kernel y ejecutar el notebook de arriba abajo. La primera celda advierte que las salidas previas son históricas.
3. Revisar `metricas_escenarios.csv`, los 20 registros y cada `estado_final.json`. El verificador debe confirmar resultado, carrito/pedido y restricciones; una respuesta afirmativa del modelo no basta.
4. Si hay escenarios fallidos, revisar el turno, las llamadas a herramientas y el estado persistido. Corregir el flujo mínimo necesario y repetir la corrida completa para regenerar las métricas.
5. Revisar §12.1–§12.2: conservar cinco aciertos y cinco fallos reales, y validar cada causa probable contra los registros. Si la corrida no produce cinco casos de cada tipo, informar que el requisito sigue pendiente.
6. Actualizar la presentación con las cifras de esa misma ejecución y grabar el video siguiendo `GUIA_VIDEO.md`.

## Verificación ejecutada durante esta revisión

- Todas las celdas Python del notebook compilan sintácticamente.
- La nueva celda de análisis se probó con datos controlados y genera diez filas (cinco aciertos y cinco fallos).
- `tests/verificar_regresiones.py` no pudo completar su autoprueba: en esta copia de trabajo no existe `output/datos/catalogo.parquet`. Se requiere preparar el dataset; no se infiere un resultado de regresión a partir de esta ejecución incompleta.
