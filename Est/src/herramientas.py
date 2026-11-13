"""Herramientas del agente, memoria (Estado) y validaciones por codigo.

Cada herramienta recibe argumentos del LLM, los valida y devuelve un dict JSON con ok / error.
Las etiquetas ESCI no estan aqui: el agente solo ve catalogo + tienda.
"""
import re
import time
from dataclasses import dataclass, field

from .recuperacion import normalizar, tokens
from .tienda import ErrorTienda, euros

NEGACION = re.compile(r"^\s*no\b|\bno (lo |la )?(confirm|compr|quiero)|\bmejor no\b|\bcancel|\bespera\b|\btodavia no\b")
AFIRMACION = re.compile(r"\b(si|confirmo|confirma|confirmar|confirmado|confirmalo|adelante|procede|dale|de acuerdo|"
                        r"ok|okay|vale|compralo|comprala|hazlo|perfecto|correcto)\b")


def es_confirmacion(texto):
    """Consentimiento explicito del usuario (validacion por codigo, no por el LLM)."""
    t = normalizar(texto)
    return bool(AFIRMACION.search(t)) and not NEGACION.search(t)


@dataclass
class Estado:
    presupuesto_cent: int = None
    preferencias: list = field(default_factory=list)
    carrito_id: int = None
    cotizacion: dict = None            # ultima cotizacion {cotizacion_id, total_cent, valida}
    cotizacion_mostrada: bool = False  # se presento al usuario en un turno anterior
    cotizo_en_turno: bool = False
    pedidos: list = field(default_factory=list)
    mostrados: list = field(default_factory=list)   # ultimos productos presentados
    texto_usuario: str = ""
    historial: list = field(default_factory=list)   # [(usuario, asistente)]


def _f(x):
    return None if x is None else euros(x)


ESQUEMAS = [
    {"type": "function", "function": {
        "name": "buscar_productos",
        "description": "Busca productos en el catalogo (RAG). Devuelve titulo, marca, color, precio y existencias.",
        "parameters": {"type": "object", "properties": {
            "consulta": {"type": "string", "description": "Descripcion del producto en palabras clave"},
            "precio_max": {"type": "number", "description": "Precio unitario maximo en euros (opcional)"},
            "k": {"type": "integer", "description": "Cantidad de resultados (1 a 10)"}},
            "required": ["consulta"]}}},
    {"type": "function", "function": {
        "name": "ver_producto",
        "description": "Detalle de un producto: descripcion, caracteristicas, marca, color, precio y existencias.",
        "parameters": {"type": "object", "properties": {"product_id": {"type": "string"}},
                       "required": ["product_id"]}}},
    {"type": "function", "function": {
        "name": "consultar_atributo",
        "description": "Verifica si un atributo (p. ej. 'resistente al agua', '500 ml') aparece en la informacion "
                       "del producto. Si no aparece, el atributo es desconocido.",
        "parameters": {"type": "object", "properties": {"product_id": {"type": "string"},
                                                        "atributo": {"type": "string"}},
                       "required": ["product_id", "atributo"]}}},
    {"type": "function", "function": {
        "name": "registrar_restricciones",
        "description": "Guarda en memoria el presupuesto total maximo y/o las preferencias del usuario. "
                       "preferencias reemplaza la lista completa.",
        "parameters": {"type": "object", "properties": {
            "presupuesto_max": {"type": "number", "description": "Presupuesto total en euros"},
            "preferencias": {"type": "array", "items": {"type": "string"}}}}}},
    {"type": "function", "function": {
        "name": "agregar_al_carrito",
        "description": "Agrega unidades de un producto al carrito (suma a las que ya hubiera).",
        "parameters": {"type": "object", "properties": {"product_id": {"type": "string"},
                                                        "cantidad": {"type": "integer"}},
                       "required": ["product_id", "cantidad"]}}},
    {"type": "function", "function": {
        "name": "cambiar_cantidad",
        "description": "Fija la cantidad de un producto del carrito. 0 lo elimina.",
        "parameters": {"type": "object", "properties": {"product_id": {"type": "string"},
                                                        "cantidad": {"type": "integer"}},
                       "required": ["product_id", "cantidad"]}}},
    {"type": "function", "function": {
        "name": "ver_carrito", "description": "Contenido del carrito y total.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "cotizar",
        "description": "Calcula la cotizacion del carrito y valida existencias y presupuesto. "
                       "Presenta el total y pide confirmacion al usuario.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "confirmar_pedido",
        "description": "Registra el pedido de la ultima cotizacion. Solo si el usuario confirmo explicitamente "
                       "la cotizacion en su ultimo mensaje.",
        "parameters": {"type": "object", "properties": {}}}},
]
MODIFICAN_CARRITO = {"agregar_al_carrito", "cambiar_cantidad", "confirmar_pedido"}


class Herramientas:
    def __init__(self, catalogo, recuperador, tienda, k_resultados=5, metodo="sistema"):
        self.cat = catalogo.set_index("product_id")
        self.rec, self.tienda, self.k, self.metodo = recuperador, tienda, k_resultados, metodo
        self.estado = Estado()
        self.t_recuperacion = 0.0

    # --- utilidades ---
    def _existe(self, pid):
        if not isinstance(pid, str) or pid not in self.cat.index:
            raise ErrorTienda(f"product_id desconocido: {pid!r}. Usa un id devuelto por buscar_productos")

    @staticmethod
    def _numero(x, nombre):
        if isinstance(x, str):
            try:
                x = float(x.replace(",", ".").replace("€", "").strip())
            except ValueError:
                pass
        if isinstance(x, bool) or not isinstance(x, (int, float)) or x <= 0:
            raise ErrorTienda(f"{nombre} debe ser un numero positivo")
        return float(x)

    @staticmethod
    def _entero(x, nombre="cantidad"):
        if isinstance(x, str) and x.strip().lstrip("-").isdigit():
            x = int(x)
        if isinstance(x, float) and x.is_integer():
            x = int(x)
        if x is None:
            raise ErrorTienda(f"falta {nombre}: pregunta al usuario cuantas unidades quiere")
        if not isinstance(x, int) or isinstance(x, bool):
            raise ErrorTienda(f"{nombre} debe ser un numero entero")
        return x

    def _ficha(self, pid, extra=None):
        r = self.cat.loc[pid]
        ps = self.tienda.producto(pid)
        d = {"product_id": pid, "titulo": r["titulo"][:140], "marca": r["marca"] or "desconocido",
             "color": r["color"] or "desconocido", "precio": euros(ps["precio_cent"]), "stock": ps["stock"],
             "disponible": ps["stock"] > 0}
        return {**d, **(extra or {})}

    def _carrito(self):
        e = self.estado
        if e.carrito_id is None:
            return {"items": [], "total": 0.0}
        car = self.tienda.carrito(e.carrito_id)
        return {"items": [{"product_id": i["product_id"], "titulo": self.cat.loc[i["product_id"], "titulo"][:80],
                           "cantidad": i["cantidad"], "precio": euros(i["precio_cent"]), "stock": i["stock"],
                           "subtotal": euros(i["subtotal_cent"])} for i in car["items"]],
                "total": euros(car["total_cent"])}

    def _carrito_abierto(self):
        e = self.estado
        if e.carrito_id is None or self.tienda.carrito(e.carrito_id)["estado"] != "abierto":
            e.carrito_id = self.tienda.nuevo_carrito()
        return e.carrito_id

    def _invalidar_cotizacion(self):
        self.estado.cotizacion_mostrada = self.estado.cotizo_en_turno = False

    # --- herramientas ---
    def buscar_productos(self, consulta, precio_max=None, k=None):
        if not isinstance(consulta, str) or not consulta.strip():
            raise ErrorTienda("consulta vacia")
        k = min(max(self._entero(k if k is not None else self.k, "k"), 1), 10)
        if precio_max is not None:
            precio_max = self._numero(precio_max, "precio_max")
        t0 = time.perf_counter()
        idx = self.rec.buscar(consulta, k=30, metodo=self.metodo)
        self.t_recuperacion += time.perf_counter() - t0
        res = []
        for i in idx:
            f = self._ficha(self.rec.ids[i])
            if precio_max is None or f["precio"] <= precio_max:
                res.append({"posicion": len(res) + 1, **f})
            if len(res) == k:
                break
        self.estado.mostrados = res
        return {"ok": True, "resultados": res,
                "nota": "sin resultados con esos filtros" if not res else "precios unitarios en euros"}

    def ver_producto(self, product_id):
        self._existe(product_id)
        r = self.cat.loc[product_id]
        return {"ok": True, **self._ficha(product_id, {
            "descripcion": r["descripcion"][:500] or "desconocido",
            "caracteristicas": r["caracteristicas"][:500] or "desconocido"})}

    def consultar_atributo(self, product_id, atributo):
        self._existe(product_id)
        r = self.cat.loc[product_id]
        texto = " ".join([r["titulo"], r["marca"], r["color"], r["caracteristicas"], r["descripcion"]])
        objetivo = tokens(atributo)
        if not objetivo:
            raise ErrorTienda("atributo vacio")
        for frase in re.split(r"(?<=[.;\n])\s+", texto):
            if all(t in tokens(frase) for t in objetivo):
                return {"ok": True, "atributo": atributo, "valor": "verificado", "evidencia": frase[:200]}
        return {"ok": True, "atributo": atributo, "valor": "desconocido",
                "nota": "no aparece en la informacion del producto; no afirmes ni niegues el atributo"}

    def registrar_restricciones(self, presupuesto_max=None, preferencias=None):
        e = self.estado
        if presupuesto_max is not None:
            e.presupuesto_cent = int(round(self._numero(presupuesto_max, "presupuesto_max") * 100))
        if preferencias is not None:
            if not isinstance(preferencias, list) or not all(isinstance(p, str) for p in preferencias):
                raise ErrorTienda("preferencias debe ser una lista de textos")
            e.preferencias = [p.strip() for p in preferencias if p.strip()]
        return {"ok": True, "presupuesto_max": _f(e.presupuesto_cent), "preferencias": e.preferencias}

    def _fijar(self, product_id, cantidad):
        cid = self._carrito_abierto()
        self.tienda.fijar_cantidad(cid, product_id, cantidad)
        self._invalidar_cotizacion()
        car = self._carrito()
        out = {"ok": True, "carrito": car}
        p = self.estado.presupuesto_cent
        if p is not None and car["total"] * 100 > p:
            out["aviso"] = f"el total {car['total']} supera el presupuesto {_f(p)}"
        return out

    def agregar_al_carrito(self, product_id, cantidad=None):
        self._existe(product_id)
        cantidad = self._entero(cantidad)
        if cantidad < 1:
            raise ErrorTienda("la cantidad a agregar debe ser al menos 1")
        actual = {i["product_id"]: i["cantidad"] for i in self._carrito()["items"]}.get(product_id, 0)
        return self._fijar(product_id, actual + cantidad)

    def cambiar_cantidad(self, product_id, cantidad=None):
        self._existe(product_id)
        cantidad = self._entero(cantidad)
        if product_id not in {i["product_id"] for i in self._carrito()["items"]}:
            raise ErrorTienda("ese producto no esta en el carrito")
        return self._fijar(product_id, cantidad)

    def ver_carrito(self):
        return {"ok": True, "carrito": self._carrito(), "presupuesto_max": _f(self.estado.presupuesto_cent)}

    def cotizar(self):
        e = self.estado
        if e.carrito_id is None:
            raise ErrorTienda("el carrito esta vacio")
        c = self.tienda.cotizar(e.carrito_id, e.presupuesto_cent)
        e.cotizacion = {"cotizacion_id": c["cotizacion_id"], "total_cent": c["total_cent"], "valida": c["valida"]}
        e.cotizo_en_turno = c["valida"]
        return {"ok": True, "cotizacion_id": c["cotizacion_id"], "carrito": self._carrito(),
                "total": euros(c["total_cent"]), "presupuesto_max": _f(e.presupuesto_cent),
                "valida": c["valida"], "problemas": c["problemas"],
                "siguiente_paso": "presenta el total y pide confirmacion" if c["valida"]
                else "explica los problemas y propone una solucion"}

    def confirmar_pedido(self):
        e = self.estado
        if e.cotizacion is None:
            raise ErrorTienda("no hay cotizacion: arma el carrito y usa cotizar primero")
        ya = any(p["cotizacion_id"] == e.cotizacion["cotizacion_id"] for p in e.pedidos)
        if not ya and not (e.cotizacion_mostrada and es_confirmacion(e.texto_usuario)):
            raise ErrorTienda("el usuario no confirmo explicitamente la cotizacion vigente: presentala y pide "
                              "confirmacion antes de registrar el pedido")
        r = self.tienda.confirmar(e.cotizacion["cotizacion_id"], e.presupuesto_cent)
        if r["estado"] == "rechazado":
            self._invalidar_cotizacion()
            return {"ok": False, "estado": "rechazado", "problemas": r["problemas"], "carrito": self._carrito(),
                    "siguiente_paso": "explica el problema y propone una alternativa; vuelve a cotizar"}
        if r["estado"] == "registrado":
            e.pedidos.append({"pedido_id": r["pedido_id"], "cotizacion_id": r["cotizacion_id"],
                              "total_cent": r["total_cent"]})
            e.carrito_id = None
        return {"ok": True, "estado": r["estado"], "pedido_id": r["pedido_id"], "total": euros(r["total_cent"]),
                "nota": "pedido ya registrado antes; no se duplico" if r["estado"] == "ya_registrado" else
                "pedido registrado e inventario actualizado"}

    # --- despacho ---
    def ejecutar(self, nombre, argumentos):
        fn = getattr(self, nombre, None) if nombre in {s["function"]["name"] for s in ESQUEMAS} else None
        if fn is None:
            return {"ok": False, "error": f"herramienta desconocida: {nombre}"}
        if not isinstance(argumentos, dict):
            return {"ok": False, "error": "argumentos deben ser un objeto JSON"}
        try:
            return fn(**argumentos)
        except TypeError as ex:
            return {"ok": False, "error": f"argumentos invalidos: {ex}"}
        except ErrorTienda as ex:
            return {"ok": False, "error": str(ex)}

    def resumen_estado(self):
        """Memoria que se inyecta en cada turno (sobrevive aunque el historial se recorte)."""
        e = self.estado
        lin = ["ESTADO ACTUAL (memoria del sistema):",
               f"- Presupuesto total maximo: {_f(e.presupuesto_cent) or 'no indicado'} euros",
               f"- Preferencias: {', '.join(e.preferencias) or 'ninguna'}"]
        car = self._carrito()
        if car["items"]:
            lin.append(f"- Carrito (total {car['total']} euros):")
            lin += [f"  * {i['product_id']} | {i['titulo']} | {i['cantidad']} x {i['precio']} | stock {i['stock']}"
                    for i in car["items"]]
        else:
            lin.append("- Carrito: vacio")
        if e.cotizacion:
            lin.append(f"- Ultima cotizacion: {e.cotizacion['cotizacion_id']} total {_f(e.cotizacion['total_cent'])} "
                       f"(valida: {'si' if e.cotizacion['valida'] else 'no'}; mostrada al usuario: "
                       f"{'si' if e.cotizacion_mostrada else 'no'})")
        if e.pedidos:
            lin.append("- Pedidos confirmados: " + ", ".join(f"{p['pedido_id']} ({p['cotizacion_id']}, "
                                                            f"{_f(p['total_cent'])})" for p in e.pedidos))
        if e.mostrados:
            lin.append("- Productos mostrados en la ultima busqueda:")
            lin += [f"  {m['posicion']}) {m['product_id']} | {m['titulo'][:90]} | {m['precio']} euros | "
                    f"stock {m['stock']}" for m in e.mostrados]
        return "\n".join(lin)
