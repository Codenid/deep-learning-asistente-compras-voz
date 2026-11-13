"""Agente de compras: un solo LLM que elige herramientas en un bucle por turno.

Control implementado por el grupo:
- Memoria: Estado (presupuesto, preferencias, carrito, cotizacion, pedidos, productos mostrados) inyectado en
  cada turno + historial recortado.
- Bucle: el LLM propone llamadas a herramientas; el codigo las valida y ejecuta; termina cuando responde texto.
- Reglas duras por codigo (no dependen del LLM): consentimiento explicito, validacion de cantidades,
  presupuesto y existencias, confirmacion atomica e idempotente.
"""
import json
import re
import time

from .herramientas import ESQUEMAS, MODIFICAN_CARRITO

SISTEMA = """Eres un asistente de compras por voz de una tienda en linea. Hablas en espanol y respondes breve \
(maximo 3 frases), porque tu respuesta se leera en voz alta.
Reglas:
1. Usa SIEMPRE las herramientas para obtener productos, precios, existencias y atributos. No inventes datos.
2. Si un atributo no figura en la informacion del producto, dilo como desconocido (usa consultar_atributo).
3. Si falta informacion para actuar (que producto, para que dispositivo, talla, cantidad) o hay una ambiguedad \
relevante, haz UNA pregunta de aclaracion antes de tocar el carrito.
4. Cuando el usuario mencione presupuesto o preferencias, guardalos con registrar_restricciones y respetalos al \
buscar y al elegir.
5. Para comprar: agrega al carrito, usa cotizar, presenta el total y pide confirmacion explicita. Llama a \
confirmar_pedido solo si el ultimo mensaje del usuario confirma la cotizacion ya presentada.
6. Si un producto esta agotado o no alcanza el stock, propone una alternativa disponible o explica que no hay solucion.
7. Si confirmar_pedido informa problemas (stock o precio cambiados), explicalo, propone una solucion y vuelve a \
cotizar. Si el pedido ya existe, no lo repitas.
8. Si el usuario cambia una cantidad o preferencia, conserva las demas restricciones.
9. Nombra los productos por su nombre corto y precio; no leas identificadores. Importes en euros con dos decimales."""

ID_RE = re.compile(r"\bB0[0-9A-Z]{8}\b")


def limpiar_respuesta(t):
    """Texto apto para TTS: sin markdown ni identificadores."""
    t = re.sub(r"[*#`_]+", "", t or "")
    t = ID_RE.sub("", t)
    t = re.sub(r"\(\s*\)", "", t)
    return re.sub(r"\s+", " ", t).strip()


def es_aclaracion(t):
    return "?" in t


class Agente:
    def __init__(self, llm, herramientas, max_pasos=8, turnos_historial=6):
        self.llm, self.h = llm, herramientas
        self.max_pasos, self.turnos = max_pasos, turnos_historial

    @property
    def estado(self):
        return self.h.estado

    def turno(self, texto):
        e = self.estado
        e.texto_usuario = texto
        e.cotizo_en_turno = False
        self.h.t_recuperacion = 0.0
        msgs = [{"role": "system", "content": SISTEMA + "\n\n" + self.h.resumen_estado()}]
        for u, a in e.historial[-self.turnos:]:
            msgs += [{"role": "user", "content": u}, {"role": "assistant", "content": a}]
        msgs.append({"role": "user", "content": texto})
        ops, t_llm, t_tools, respuesta, crudo = [], 0.0, 0.0, None, []
        for paso in range(1, self.max_pasos + 1):
            t0 = time.perf_counter()
            out = self.llm.generar(msgs, ESQUEMAS)
            t_llm += time.perf_counter() - t0
            crudo.append(out["crudo"])
            if not out["llamadas"]:
                respuesta = limpiar_respuesta(out["texto"])
                break
            msgs.append({"role": "assistant", "content": out["texto"],
                         "tool_calls": [{"type": "function", "function": {"name": c["nombre"],
                                                                          "arguments": c["argumentos"]}}
                                        for c in out["llamadas"]]})
            for c in out["llamadas"]:
                t1 = time.perf_counter()
                res = self.h.ejecutar(c["nombre"], c["argumentos"])
                t_tools += time.perf_counter() - t1
                ops.append({"paso": paso, "herramienta": c["nombre"], "argumentos": c["argumentos"], "resultado": res})
                msgs.append({"role": "tool", "name": c["nombre"], "content": json.dumps(res, ensure_ascii=False)})
        if not respuesta:
            respuesta = "Disculpa, no pude completar la solicitud. ¿Puedes repetirla con mas detalle?"
        if e.cotizo_en_turno:           # la cotizacion queda "mostrada" recien al entregar esta respuesta
            e.cotizacion_mostrada = True
        e.historial.append((texto, respuesta))
        return {"entrada": texto, "respuesta": respuesta, "operaciones": ops, "pasos_llm": len(crudo),
                "aclaracion": es_aclaracion(respuesta) and not any(
                    o["herramienta"] in MODIFICAN_CARRITO and o["resultado"].get("ok") for o in ops),
                "t_llm": t_llm, "t_herramientas": t_tools - self.h.t_recuperacion,
                "t_recuperacion": self.h.t_recuperacion, "crudo": crudo}
