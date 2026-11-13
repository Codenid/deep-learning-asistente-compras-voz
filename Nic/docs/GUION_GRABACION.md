# Guion de grabación — escenarios por voz (E01–E06)

Estas frases las muestra y graba `multimedia.bat` (las lee de este archivo) en `multimedia/multimediaNNN/audios/`. Habla con naturalidad; no hace falta leer signos de puntuación.

- Usa la misma voz propia (o autorizada) que en `referencia.wav` de la misma carpeta multimediaNNN.
- Deja ~0,5 s de silencio al inicio y al final. Evita ruido de fondo.
- En **E05 t1** di "A4" como **"a cuatro"**: es el caso en que el ASR puede transcribir mal y el usuario corrige la transcripción antes de ejecutar.
- Los escenarios se ejecutan en orden de turnos: cada audio responde a lo que el asistente dijo antes (las frases ya están pensadas para eso).

## E01 — compra que cumple restricciones

| Archivo | Qué decir |
|---|---|
| `E01_t1.wav` | Quiero comprar dos paquetes de pilas AA, mi presupuesto es de treinta euros. |
| `E01_t2.wav` | Agrega la primera opción y prepárame la cotización. |
| `E01_t3.wav` | Sí, confirmo el pedido. |

## E02 — solicitud ambigua con aclaración

| Archivo | Qué decir |
|---|---|
| `E02_t1.wav` | Quiero comprar una funda. |
| `E02_t2.wav` | Es para un iPhone doce, de color negro. |
| `E02_t3.wav` | Agrega la primera y dime el total. |
| `E02_t4.wav` | Sí, confirmo. |

## E03 — cambio de cantidad conservando restricciones

| Archivo | Qué decir |
|---|---|
| `E03_t1.wav` | Necesito tres botellas de agua para niños, con un máximo de cuarenta euros en total. |
| `E03_t2.wav` | Agrega la más barata. |
| `E03_t3.wav` | Mejor que sean dos en lugar de tres, y prepárame la cotización. |
| `E03_t4.wav` | Sí, confirmo la compra. |

## E04 — producto agotado con alternativa

| Archivo | Qué decir |
|---|---|
| `E04_t1.wav` | Quiero un termo de acero inoxidable de la marca WNTHBJ. |
| `E04_t2.wav` | Vale, agrega la alternativa que me propones y prepárame la cotización. |
| `E04_t3.wav` | Sí, confirmo. |

## E05 — corrección de transcripción antes de comprar

| Archivo | Qué decir |
|---|---|
| `E05_t1.wav` | Quiero dos cuadernos de bocetos tamaño A4. |
| `E05_t2.wav` | Agrega el primero y prepárame la cotización. |
| `E05_t3.wav` | Sí, confirmo. |

## E06 — cambio de stock entre cotización y confirmación

| Archivo | Qué decir |
|---|---|
| `E06_t1.wav` | Quiero dos mochilas para portátil, con un máximo de sesenta euros en total. |
| `E06_t2.wav` | Agrega la primera opción y prepárame la cotización. |
| `E06_t3.wav` | Sí, confirmo. |
| `E06_t4.wav` | Cámbiala por otra mochila que tenga dos unidades disponibles y dame la nueva cotización. |
| `E06_t5.wav` | Sí, confirmo. |
| `E06_t6.wav` | Confirmo otra vez, por si acaso. |

## Escenarios por texto (T07–T20)

No requieren grabación; se ejecutan con el texto definido en la celda de escenarios (§7) del notebook.
