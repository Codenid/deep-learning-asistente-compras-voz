# Voz de referencia

Se graba con `multimedia.bat` (abre http://localhost:5000), que la guarda en `multimedia/multimediaNNN/referencia.wav` (6 a 15 s, mono, sin ruido). Hay que leer exactamente este texto (es `TEXTO_REF` en la celda *Tablero de control* del notebook):

> Hola, esta es mi voz de referencia para el asistente de compras. La grabo en un lugar tranquilo, hablando con calma y a un ritmo natural.

- Debe ser tu voz o una voz con autorización explícita.
- Las respuestas sintetizadas nunca repiten este texto (el código lo verifica).
- Opcional: `referencia_2.wav` con otra frase tuya, para medir el techo de semejanza (misma persona, otra grabación).
