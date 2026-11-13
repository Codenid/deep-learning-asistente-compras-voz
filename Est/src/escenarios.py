"""20 escenarios operativos con estado inicial reproducible (restaurar + preparacion), ejecucion y verificacion.

E01-E06: por voz (audios en input/audios/<id>_t<n>.wav), todos con varias intervenciones del usuario.
T07-T20: por texto.
Cada escenario guarda: audios, transcripciones, operaciones ejecutadas y estado final de la tienda.
"""
import json
import shutil
import time

from .agente import Agente
from .herramientas import Herramientas, es_confirmacion
from .recuperacion import normalizar, tokens

ESCENARIOS = [
    # ---------------- voz (6) ----------------
    {"id": "E01", "modo": "voz", "tipo": "compra que cumple restricciones", "presupuesto": 30,
     "turnos": [{"texto": "Quiero comprar dos paquetes de pilas AA, mi presupuesto es de treinta euros."},
                {"texto": "Agrega la primera opción y prepárame la cotización."},
                {"texto": "Sí, confirmo el pedido."}],
     "esperado": {"pedidos": 1, "items": [{"palabras": ["pilas"], "cantidad": 2}], "total_max": 30}},
    {"id": "E02", "modo": "voz", "tipo": "solicitud ambigua con aclaración",
     "turnos": [{"texto": "Quiero comprar una funda."},
                {"texto": "Es para un iPhone doce, de color negro."},
                {"texto": "Agrega la primera y dime el total."},
                {"texto": "Sí, confirmo."}],
     "esperado": {"pedidos": 1, "aclaracion_en": [1], "items": [{"palabras": ["funda"], "cantidad": 1}]}},
    {"id": "E03", "modo": "voz", "tipo": "cambio de cantidad conservando restricciones", "presupuesto": 40,
     "turnos": [{"texto": "Necesito tres botellas de agua para niños, con un máximo de cuarenta euros en total."},
                {"texto": "Agrega la más barata."},
                {"texto": "Mejor que sean dos en lugar de tres, y prepárame la cotización."},
                {"texto": "Sí, confirmo la compra."}],
     "esperado": {"pedidos": 1, "items": [{"palabras": ["botella"], "cantidad": 2}], "total_max": 40}},
    {"id": "E04", "modo": "voz", "tipo": "producto agotado con alternativa",
     "preparar": [["agotar_palabras", ["termo", "wnthbj"]]],
     "turnos": [{"texto": "Quiero un termo de acero inoxidable de la marca WNTHBJ."},
                {"texto": "Vale, agrega la alternativa que me propones y prepárame la cotización."},
                {"texto": "Sí, confirmo."}],
     "esperado": {"pedidos": 1, "items": [{"palabras": ["termo"], "cantidad": 1}],
                  "excluir_palabras": ["wnthbj"]}},
    {"id": "E05", "modo": "voz", "tipo": "corrección de transcripción antes de comprar",
     "turnos": [{"texto": "Quiero dos cuadernos de bocetos tamaño A4.", "revisar_transcripcion": True},
                {"texto": "Agrega el primero y prepárame la cotización."},
                {"texto": "Sí, confirmo."}],
     "esperado": {"pedidos": 1, "items": [{"palabras": ["cuaderno"], "cantidad": 2}]}},
    {"id": "E06", "modo": "voz", "tipo": "cambio de stock entre cotización y confirmación", "presupuesto": 60,
     "turnos": [{"texto": "Quiero dos mochilas para portátil, con un máximo de sesenta euros en total."},
                {"texto": "Agrega la primera opción y prepárame la cotización."},
                {"texto": "Sí, confirmo.", "antes": [["stock_carrito", 0, 1]]},
                {"texto": "Cámbiala por otra mochila que tenga dos unidades disponibles y dame la nueva cotización."},
                {"texto": "Sí, confirmo."},
                {"texto": "Confirmo otra vez, por si acaso."}],
     "esperado": {"pedidos": 1, "items": [{"palabras": ["mochila"], "cantidad": 2}], "total_max": 60,
                  "sin_pedido_en": [3]}},
    # ---------------- texto (14) ----------------
    {"id": "T07", "modo": "texto", "tipo": "compra simple con presupuesto", "presupuesto": 30,
     "turnos": [{"texto": "Quiero comprar un altavoz bluetooth Sony, máximo 30 euros."},
                {"texto": "Agrega el primero y cotiza."},
                {"texto": "Confirmo."}],
     "esperado": {"pedidos": 1, "items": [{"palabras": ["altavoz"], "cantidad": 1}], "total_max": 30}},
    {"id": "T08", "modo": "texto", "tipo": "varios productos con presupuesto total", "presupuesto": 40,
     "turnos": [{"texto": "Necesito un paquete de pilas AA y un cargador de pared USB, con un presupuesto de "
                          "40 euros en total."},
                {"texto": "Agrega la opción más barata de cada uno y cotiza."},
                {"texto": "Sí, confirmo."}],
     "esperado": {"pedidos": 1, "items": [{"palabras": ["pilas"], "cantidad": 1},
                                          {"palabras": ["cargador"], "cantidad": 1}], "total_max": 40}},
    {"id": "T09", "modo": "texto", "tipo": "presupuesto insuficiente", "presupuesto": 10,
     "turnos": [{"texto": "Quiero cinco altavoces bluetooth, pero solo tengo 10 euros en total."},
                {"texto": "Agrégalos igual y confirma la compra."}],
     "esperado": {"pedidos": 0, "respuesta_en": [[1, ["presupuesto", "no alcanza", "supera", "insuficiente",
                                                     "no es posible", "no puedo", "excede"]]]}},
    {"id": "T10", "modo": "texto", "tipo": "atributo no verificable",
     "turnos": [{"texto": "¿El altavoz Mangobeat con base de madera es resistente al agua?"}],
     "esperado": {"pedidos": 0, "sin_carrito": True,
                  "herramienta_en": [[1, ["consultar_atributo", "ver_producto"]]],
                  "respuesta_en": [[1, ["descono", "no figura", "no aparece", "no se indica", "no consta",
                                        "no especifica", "no menciona", "no tengo informacion", "no hay informacion"]]]}},
    {"id": "T11", "modo": "texto", "tipo": "agotado sin solución",
     "preparar": [["agotar_palabras", ["bombilla"]]],
     "turnos": [{"texto": "Quiero dos bombillas LED H7 para los faros del coche."}],
     "esperado": {"pedidos": 0, "sin_carrito": True,
                  "respuesta_en": [[1, ["agotad", "no hay", "sin stock", "no tenemos", "no dispon", "no quedan",
                                        "sin existencias", "no encontr"]]]}},
    {"id": "T12", "modo": "texto", "tipo": "cantidad mayor que el stock",
     "preparar": [["stock_palabras", ["regleta", "aigostar"], 2]],
     "turnos": [{"texto": "Quiero cinco regletas Aigostar de cinco enchufes."},
                {"texto": "Vale, entonces pon las dos que quedan y cotiza."},
                {"texto": "Sí, confirmo."}],
     "esperado": {"pedidos": 1, "items": [{"palabras": ["regleta"], "cantidad": 2}]}},
    {"id": "T13", "modo": "texto", "tipo": "compra sin cotización previa (consentimiento)",
     "turnos": [{"texto": "Agrega unas pilas AA Energizer al carrito y cómpralas ya, sin preguntarme."},
                {"texto": "Sí, confirmo."}],
     "esperado": {"pedidos": 1, "sin_pedido_en": [1], "items": [{"palabras": ["pilas"], "cantidad": 1}]}},
    {"id": "T14", "modo": "texto", "tipo": "quitar un producto del carrito",
     "turnos": [{"texto": "Agrega un altavoz bluetooth Sony y una funda para iPhone 12."},
                {"texto": "Quita la funda y cotiza solo el altavoz."},
                {"texto": "Confirmo."}],
     "esperado": {"pedidos": 1, "items": [{"palabras": ["altavoz"], "cantidad": 1}], "items_exactos": True}},
    {"id": "T15", "modo": "texto", "tipo": "cambio de preferencia (color)", "presupuesto": 30,
     "turnos": [{"texto": "Quiero una mochila para portátil de color gris, máximo 30 euros."},
                {"texto": "Mejor que sea de color negro, con el mismo presupuesto."},
                {"texto": "Agrega la primera y cotiza."},
                {"texto": "Sí, confirmo."}],
     "esperado": {"pedidos": 1, "items": [{"palabras": ["mochila", "negro"], "cantidad": 1}], "total_max": 30}},
    {"id": "T16", "modo": "texto", "tipo": "comparar alternativas",
     "turnos": [{"texto": "Compara los dos altavoces bluetooth más baratos que tengas."}],
     "esperado": {"pedidos": 0, "sin_carrito": True, "herramienta_en": [[1, ["buscar_productos"]]]}},
    {"id": "T17", "modo": "texto", "tipo": "cambio de precio entre cotización y confirmación",
     "turnos": [{"texto": "Quiero una taza para café."},
                {"texto": "Agrega la primera y cotiza."},
                {"texto": "Sí, confirmo.", "antes": [["precio_carrito", 0, 300]]},
                {"texto": "De acuerdo, confirmo con el nuevo precio."}],
     "esperado": {"pedidos": 1, "sin_pedido_en": [3], "items": [{"palabras": ["taza"], "cantidad": 1}]}},
    {"id": "T18", "modo": "texto", "tipo": "confirmación repetida sin duplicar",
     "turnos": [{"texto": "Quiero un cable HDMI."},
                {"texto": "Agrega el más barato y cotiza."},
                {"texto": "Confirmo."},
                {"texto": "Confirmo otra vez, por favor."}],
     "esperado": {"pedidos": 1, "items": [{"palabras": ["hdmi"], "cantidad": 1}]}},
    {"id": "T19", "modo": "texto", "tipo": "cantidad faltante e inválida",
     "turnos": [{"texto": "Agrega cuadernos al carrito."},
                {"texto": "Menos dos cuadernos."},
                {"texto": "Dos cuadernos de bocetos Artway."}],
     "esperado": {"pedidos": 0, "aclaracion_en": [1, 2],
                  "carrito_final": [{"palabras": ["cuaderno"], "cantidad": 2}]}},
    {"id": "T20", "modo": "texto", "tipo": "rechazo de la cotización", "presupuesto": 25,
     "turnos": [{"texto": "Quiero unos auriculares bluetooth, máximo 25 euros."},
                {"texto": "Agrega los primeros y cotiza."},
                {"texto": "No, mejor no los compres por ahora."}],
     "esperado": {"pedidos": 0, "carrito_final": [{"palabras": ["auriculares"], "cantidad": 1}]}},
]
for _e in ESCENARIOS:
    for _n, _t in enumerate(_e["turnos"], 1):
        _t.setdefault("audio", f"{_e['id']}_t{_n}.wav")


def coincide(texto, palabras):
    T = set(tokens(texto))
    return all(any(t in (w, w + "s", w + "es") for t in T) for w in map(normalizar, palabras))


class Sistema:
    """Catalogo + recuperador + tienda + LLM; reiniciar() deja estado inicial reproducible."""
    def __init__(self, catalogo, recuperador, tienda, llm, k_resultados=5, max_pasos=8, turnos_historial=6):
        self.cat, self.rec, self.tienda, self.llm = catalogo, recuperador, tienda, llm
        self.texto = (catalogo["titulo"] + " " + catalogo["marca"] + " " + catalogo["color"]).tolist()
        self.ids = catalogo["product_id"].tolist()
        self.kw = dict(k_resultados=k_resultados, max_pasos=max_pasos, turnos_historial=turnos_historial)
        self.reiniciar()

    def reiniciar(self):
        self.tienda.restaurar()
        self.h = Herramientas(self.cat, self.rec, self.tienda, self.kw["k_resultados"])
        self.agente = Agente(self.llm, self.h, self.kw["max_pasos"], self.kw["turnos_historial"])

    def ids_con(self, palabras):
        return [p for p, t in zip(self.ids, self.texto) if coincide(t, palabras)]

    def preparar(self, acciones):
        for a in acciones or []:
            if a[0] == "agotar_palabras":
                for p in self.ids_con(a[1]):
                    self.tienda.fijar_stock(p, 0)
            elif a[0] == "stock_palabras":
                for p in self.ids_con(a[1]):
                    self.tienda.fijar_stock(p, a[2])
            else:
                raise ValueError(a)

    def evento(self, ev):
        items = self.tienda.carrito(self.h.estado.carrito_id)["items"] if self.h.estado.carrito_id else []
        if not items:
            return {"evento": ev, "aplicado": False, "motivo": "carrito vacio"}
        it = items[min(ev[1], len(items) - 1)]
        if ev[0] == "stock_carrito":
            self.tienda.fijar_stock(it["product_id"], ev[2])
        elif ev[0] == "precio_carrito":
            self.tienda.fijar_precio(it["product_id"], it["precio_cent"] + ev[2])
        return {"evento": ev, "aplicado": True, "product_id": it["product_id"]}

    def descripcion(self, pid):
        return self.texto[self.rec.pos[pid]]


def factibilidad(sis, escenarios=ESCENARIOS):
    """Verifica que exista al menos un producto que cumpla cada item esperado (stock y presupuesto)."""
    filas = []
    for e in escenarios:
        sis.reiniciar()
        sis.preparar(e.get("preparar"))
        for it in e["esperado"].get("items", []) + e["esperado"].get("carrito_final", []):
            cant = it["cantidad"] if isinstance(it["cantidad"], int) else max(it["cantidad"])
            ok = []
            for p in sis.ids_con(it["palabras"]):
                if any(coincide(sis.descripcion(p), [x]) for x in e["esperado"].get("excluir_palabras", [])):
                    continue
                ps = sis.tienda.producto(p)
                tope = e.get("presupuesto")
                if ps["stock"] >= cant and (tope is None or ps["precio_cent"] * cant <= tope * 100):
                    ok.append(p)
            filas.append({"escenario": e["id"], "item": " ".join(it["palabras"]), "cantidad": cant,
                          "productos_validos": len(ok), "factible": len(ok) > 0})
    sis.reiniciar()
    return filas


def verificar(e, turnos, estado, sis):
    esp, fallos, inc = e["esperado"], [], []
    pedidos = estado["pedidos"]
    items = pedidos[-1]["items"] if pedidos else []
    if "pedidos" in esp and len(pedidos) != esp["pedidos"]:
        fallos.append(f"pedidos {len(pedidos)} (esperado {esp['pedidos']})")
        if len(pedidos) > esp["pedidos"]:
            inc.append("pedido_extra_o_duplicado")
    for it in esp.get("items", []):
        cand = [i for i in items if coincide(sis.descripcion(i["product_id"]), it["palabras"])]
        if not cand:
            fallos.append(f"sin item {it['palabras']}")
        elif not any(i["cantidad"] == it["cantidad"] for i in cand):
            fallos.append(f"cantidad de {it['palabras']}: {[i['cantidad'] for i in cand]} (esperado {it['cantidad']})")
            inc.append("cantidad")
    if esp.get("items_exactos") and len(items) != len(esp.get("items", [])):
        fallos.append(f"items en pedido {len(items)} (esperado {len(esp['items'])})")
    for i in items:
        if any(coincide(sis.descripcion(i["product_id"]), [x]) for x in esp.get("excluir_palabras", [])):
            fallos.append(f"vendio un producto excluido {i['product_id']}")
    if "total_max" in esp and pedidos and pedidos[-1]["total_cent"] > esp["total_max"] * 100:
        fallos.append(f"total {pedidos[-1]['total_cent'] / 100} > {esp['total_max']}")
    for n in esp.get("aclaracion_en", []):
        if not turnos[n - 1]["aclaracion"]:
            fallos.append(f"turno {n}: no pidio aclaracion o modifico el carrito")
    for n in esp.get("sin_pedido_en", []):
        if any(o["herramienta"] == "confirmar_pedido" and o["resultado"].get("estado") == "registrado"
               for o in turnos[n - 1]["operaciones"]):
            fallos.append(f"turno {n}: registro un pedido que no debia")
    for n, nombres in esp.get("herramienta_en", []):
        if not any(o["herramienta"] in nombres for o in turnos[n - 1]["operaciones"]):
            fallos.append(f"turno {n}: no uso {nombres}")
    for n, frases in esp.get("respuesta_en", []):
        r = normalizar(turnos[n - 1]["respuesta"])
        if not any(f in r for f in frases):
            fallos.append(f"turno {n}: la respuesta no menciona {frases[:3]}...")
    if esp.get("sin_carrito") and any(o["herramienta"] in ("agregar_al_carrito", "cambiar_cantidad")
                                      and o["resultado"].get("ok") for t in turnos for o in t["operaciones"]):
        fallos.append("modifico el carrito sin que correspondiera")
    if "carrito_final" in esp:
        abiertos = [c for c in estado["carritos"] if c["estado"] == "abierto" and c["items"]]
        fin = abiertos[-1]["items"] if abiertos else []
        for it in esp["carrito_final"]:
            if not any(coincide(sis.descripcion(i["product_id"]), it["palabras"]) and i["cantidad"] == it["cantidad"]
                       for i in fin):
                fallos.append(f"carrito final sin {it['palabras']} x{it['cantidad']}")
    # incumplimientos de restricciones (para todos los escenarios)
    if e.get("presupuesto") and any(p["total_cent"] > e["presupuesto"] * 100 for p in pedidos):
        inc.append("presupuesto")
    for t in turnos:
        if any(o["herramienta"] == "confirmar_pedido" and o["resultado"].get("estado") == "registrado"
               for o in t["operaciones"]) and not es_confirmacion(t["entrada"]):
            inc.append("pedido_sin_consentimiento")
    if len({p["cotizacion_id"] for p in pedidos}) != len(pedidos):
        inc.append("pedido_duplicado")
    if estado["stock_negativo"]:
        inc.append("stock_negativo")
    return {"ok": not fallos and not inc, "fallos": fallos, "incumplimientos": inc}


def _json(x):
    return json.loads(json.dumps(x, ensure_ascii=False, default=str))


def ejecutar(e, sis, modo, carpeta, ruta_audios=None, asr=None, tts=None, sintetizar=False):
    """modo: 'voz' (audio -> ASR) o 'texto' (transcripcion correcta). Guarda registro y estado final."""
    carpeta.mkdir(parents=True, exist_ok=True)
    sis.reiniciar()
    sis.preparar(e.get("preparar"))
    turnos = []
    for n, t in enumerate(e["turnos"], 1):
        eventos = [sis.evento(ev) for ev in t.get("antes", [])]
        reg = {"turno": n, "texto_correcto": t["texto"], "eventos": eventos}
        tiempos = {}
        if modo == "voz":
            wav = carpeta / f"t{n}_usuario.wav"
            shutil.copyfile(ruta_audios / t["audio"], wav)
            t0 = time.perf_counter()
            reg["transcripcion_asr"] = asr.transcribir(wav)
            tiempos["asr"] = time.perf_counter() - t0
            entrada = reg["transcripcion_asr"]
            if t.get("revisar_transcripcion"):        # el usuario revisa y corrige antes de ejecutar
                reg["correccion_usuario"] = t["texto"]
                reg["correccion_necesaria"] = normalizar(entrada) != normalizar(t["texto"])
                entrada = t["texto"]
        else:
            entrada = t["texto"]
        r = sis.agente.turno(entrada)
        tiempos.update(llm=r["t_llm"], recuperacion=r["t_recuperacion"], herramientas=r["t_herramientas"])
        if tts is not None and sintetizar:
            t0 = time.perf_counter()
            tts.sintetizar(r["respuesta"], carpeta / f"t{n}_asistente.wav", semilla=n)
            tiempos["tts"] = time.perf_counter() - t0
        tiempos["total"] = sum(tiempos.values())
        reg.update(entrada=entrada, respuesta=r["respuesta"], aclaracion=r["aclaracion"], pasos_llm=r["pasos_llm"],
                   operaciones=r["operaciones"], tiempos=tiempos, salida_llm=r["crudo"])
        turnos.append(reg)
    estado = sis.tienda.resumen()
    ver = verificar(e, turnos, estado, sis)
    (carpeta / "registro.json").write_text(json.dumps(_json({"escenario": e, "modo": modo, "turnos": turnos,
                                                             "verificacion": ver}), indent=1, ensure_ascii=False),
                                           encoding="utf-8")
    (carpeta / "estado_final.json").write_text(json.dumps(_json(estado), indent=1, ensure_ascii=False),
                                               encoding="utf-8")
    return {"id": e["id"], "modo": modo, "tipo": e["tipo"], "turnos": len(turnos), "completado": ver["ok"],
            "fallos": "; ".join(ver["fallos"]), "incumplimientos": ",".join(ver["incumplimientos"]),
            "pedidos": len(estado["pedidos"]), "registro": turnos}
