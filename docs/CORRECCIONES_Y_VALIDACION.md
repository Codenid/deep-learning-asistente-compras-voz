# Correcciones del laboratorio

## Problemas corregidos

- **Acciones que solo se describían:** el agente comprueba las acciones pendientes antes de cerrar el turno. Una confirmación o cotización se comunica como completada únicamente cuando existe el resultado correspondiente de la tienda.
- **Llamadas incompletas del modelo:** el lector recupera cada JSON por separado aunque falte una etiqueta `</tool_call>`. También admite llamadas simples escritas como funciones, mediante análisis de sintaxis y literales; no ejecuta código generado.
- **Presupuesto total y cantidades:** se conserva el presupuesto explícito y se calcula el importe para las unidades solicitadas. Seleccionar de nuevo la misma opción no duplica unidades; las cantidades se conservan al buscar sustitutos.
- **Búsquedas de varios productos:** se guardan los identificadores y la consulta de cada grupo. La elección del más barato se realiza sobre la búsqueda del producto correspondiente.
- **Filtros y alternativas:** se aplican marca, color, compatibilidad del modelo, atributos expresados por el usuario, stock y precio. Se utiliza el título completo y se completan los candidatos con artículos del tipo pedido para no ocultar alternativas disponibles. Los productos que solo incluyen el artículo como accesorio no desplazan a los artículos principales.
- **Marcas transcritas por voz:** se reconocen variantes de puntuación equivalentes, como `WNT-HBJ` y `WNTHBJ`, contrastándolas con las marcas reales del catálogo. Se conserva la transcripción original del ASR para medir sus errores.
- **Quitar sin duplicar:** cuando el usuario pide eliminar otro artículo, una llamada no solicitada para volver a añadir un producto existente se rechaza; su cantidad se conserva.
- **Cambio de precio o stock:** una confirmación rechazada obliga a recotizar. El nuevo pedido requiere que el usuario vea la cotización actualizada y confirme en otro turno. Una confirmación repetida sigue siendo idempotente.
- **Atributos desconocidos y respuestas numéricas:** una consulta fallida de atributos debe repetirse con un identificador real. Los mensajes de precio, stock, presupuesto insuficiente y atributos desconocidos se construyen con los resultados de las herramientas.
- **Resultados almacenados:** la caché de escenarios incluye el hash del código del agente y las herramientas; cambiar la implementación invalida los resultados anteriores.

## Verificación

Las definiciones y expectativas de los 20 escenarios se mantienen. La evaluación de recuperación y sus etiquetas también se mantienen.

Pruebas de regresión sin cargar modelos:

```powershell
.\.venv\Scripts\python.exe tests/verificar_regresiones.py
```

Estas pruebas ejecutan la autoprueba original y comprueban además: formatos de llamadas, rechazo de código arbitrario, consentimiento ante cambios, presupuesto por cantidad, invalidación de cotizaciones, confirmación efectiva, recotización tras cambiar el precio, alternativas fuera del límite inicial de candidatos, títulos largos, compatibilidad iPhone, exclusión de accesorios y finalización de solicitudes con varios tipos de producto.

Los resultados de la ejecución completa se guardan en el notebook y en `output/resultados/`. La tabla oficial es `metricas_escenarios.csv`; los registros por turno y estados finales están en `output/escenarios/`.

### Resultado final — 8 de noviembre de 2026

Tras la ejecución completa y las revalidaciones de los casos corregidos:

| Evaluación | Completados | Incumplimientos |
|---|---:|---:|
| Oficial: 14 texto + 6 voz | **20/20 (100 %)** | **0** |
| Texto | 14/14 | 0 |
| Voz con audio real | 6/6 | 0 |
| Voz con transcripción correcta | 6/6 | 0 |

El notebook conserva 50 celdas, incluidas **31 celdas de código ejecutadas y ninguna salida de error**. Se actualizaron las tablas, los registros de los escenarios revalidados, sus audios y los gráficos. Se comprobó que las definiciones de escenarios y el código de evaluación de recuperación son idénticos a la copia anterior.

Se conserva una copia anterior a las correcciones en `Laboratorio4_Asistente.antes_correcciones.ipynb`.
