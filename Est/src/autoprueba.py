"""Autoprueba sin modelos (BM25 + LLM con guion): tienda, validaciones, agente y verificacion de escenarios.

Uso (desde la carpeta del proyecto, despues del paso de datos del notebook):  python -m src.autoprueba
"""
import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import configuracion as C  # noqa: E402
from src.escenarios import ESCENARIOS, Sistema, ejecutar, factibilidad  # noqa: E402
from src.herramientas import es_confirmacion  # noqa: E402
from src.llm import LLMGuion, analizar_salida  # noqa: E402
from src.recuperacion import Recuperador  # noqa: E402
from src.tienda import Tienda  # noqa: E402
from src.voz import entidades, errores_entidades  # noqa: E402


def llamada(nombre, **args):
    return f'<tool_call>\n{json.dumps({"name": nombre, "arguments": args}, ensure_ascii=False)}\n</tool_call>'


def ultimo_resultado(msgs):
    return json.loads(next(m for m in reversed(msgs) if m["role"] == "tool")["content"])


def main():
    cat = pd.read_parquet(C.RUTA_DATOS / "catalogo.parquet")
    tmp = Path(tempfile.mkdtemp())
    Tienda.crear_base(tmp / "base.sqlite", cat["product_id"], C.SEMILLA, *C.PRECIO_LOGNORMAL, C.PRECIO_RANGO,
                      C.PROB_AGOTADO, C.STOCK_MAX)
    tienda = Tienda(tmp / "base.sqlite", tmp / "trabajo.sqlite", C.CANTIDAD_MAX)
    rec = Recuperador(cat, C.MAX_CHARS_TEXTO)       # solo BM25
    sis = Sistema(cat, rec, tienda, None)
    h = sis.h

    # 1. restauracion reproducible
    h1 = tienda.huella()
    tienda.fijar_stock(cat["product_id"][0], 0)
    sis.reiniciar()
    assert tienda.huella() == h1, "restaurar no reproduce el estado inicial"

    # 2. validaciones por codigo
    h = sis.h
    pid = next(r["product_id"] for r in h.buscar_productos("mochila portatil")["resultados"] if r["stock"] >= 2)
    stock = tienda.producto(pid)["stock"]
    for malo in (None, -1, 2.5, "dos", C.CANTIDAD_MAX + 1, stock + 1):
        assert not h.ejecutar("agregar_al_carrito", {"product_id": pid, "cantidad": malo})["ok"], malo
    assert not h.ejecutar("agregar_al_carrito", {"product_id": "NOEXISTE", "cantidad": 1})["ok"]
    assert not h.ejecutar("registrar_restricciones", {"presupuesto_max": -5})["ok"]
    assert h.ejecutar("agregar_al_carrito", {"product_id": pid, "cantidad": 1})["ok"]
    h.estado.texto_usuario = "si, confirmo"
    assert not h.ejecutar("confirmar_pedido", {})["ok"], "confirmo sin cotizacion"
    assert h.ejecutar("cotizar", {})["valida"]
    assert not h.ejecutar("confirmar_pedido", {})["ok"], "confirmo una cotizacion no mostrada al usuario"
    h.estado.cotizacion_mostrada = True
    h.estado.texto_usuario = "no, mejor no"
    assert not h.ejecutar("confirmar_pedido", {})["ok"], "confirmo sin consentimiento"
    # presupuesto: cotizacion invalida y confirmacion rechazada
    h.ejecutar("registrar_restricciones", {"presupuesto_max": 0.5})
    assert not h.ejecutar("cotizar", {})["valida"]
    h.estado.cotizacion_mostrada, h.estado.texto_usuario = True, "confirmo"
    assert h.ejecutar("confirmar_pedido", {})["estado"] == "rechazado"
    # stock cambia tras cotizar: rechazo sin cambios parciales
    sis.reiniciar()
    h = sis.h
    a, b = [r["product_id"] for r in h.buscar_productos("pilas aa")["resultados"] if r["stock"] >= 2][:2]
    h.ejecutar("agregar_al_carrito", {"product_id": a, "cantidad": 1})
    h.ejecutar("agregar_al_carrito", {"product_id": b, "cantidad": 2})
    h.ejecutar("cotizar", {})
    h.estado.cotizacion_mostrada, h.estado.texto_usuario = True, "si, confirmo"
    tienda.fijar_stock(b, 1)
    sa = tienda.producto(a)["stock"]
    assert h.ejecutar("confirmar_pedido", {})["estado"] == "rechazado"
    assert tienda.producto(a)["stock"] == sa and not tienda.resumen()["pedidos"], "cambio parcial"
    # confirmacion valida + repeticion idempotente
    h.ejecutar("cambiar_cantidad", {"product_id": b, "cantidad": 1})
    h.ejecutar("cotizar", {})
    h.estado.cotizacion_mostrada = True
    r1, r2 = h.ejecutar("confirmar_pedido", {}), h.ejecutar("confirmar_pedido", {})
    assert r1["estado"] == "registrado" and r2["estado"] == "ya_registrado" and r1["pedido_id"] == r2["pedido_id"]
    assert len(tienda.resumen()["pedidos"]) == 1 and tienda.producto(a)["stock"] == sa - 1
    # atributo no verificable
    mango = next(p for p in sis.ids_con(["mangobeat"]))
    assert h.consultar_atributo(mango, "resistente al agua")["valor"] == "desconocido"
    assert h.consultar_atributo(mango, "madera")["valor"] == "verificado"

    # 3. utilidades
    assert es_confirmacion("Sí, confirmo.") and es_confirmacion("Confirmo otra vez, por si acaso.")
    assert not es_confirmacion("No, mejor no los compres por ahora.") and not es_confirmacion("Cámbiala por otra")
    s = analizar_salida('Busco.<tool_call>\n{"name": "cotizar", "arguments": {}}\n</tool_call>')
    assert s["llamadas"] == [{"nombre": "cotizar", "argumentos": {}}] and s["texto"] == "Busco."
    assert entidades("quiero tres pilas de doce con cincuenta euros")["importes"] == {12.5: 1}
    assert entidades("veintidos unidades y cuarenta y cinco euros")["cantidades"] == {22: 1}
    assert errores_entidades("dos cuadernos A4", "doce cuadernos A4")["err_cantidades"] == 1

    # 4. escenario completo con LLM de guion (E06: cambio de stock + repeticion de la confirmacion)
    def elegir(minimo):
        return lambda m: llamada("agregar_al_carrito", cantidad=2, product_id=next(
            r["product_id"] for r in ultimo_resultado(m).get("resultados", []) if r["stock"] >= minimo))
    guion = [llamada("registrar_restricciones", presupuesto_max=60),
             llamada("buscar_productos", consulta="mochila portatil", precio_max=30),
             "Tengo estas mochilas. ¿Cual prefieres?",
             llamada("buscar_productos", consulta="mochila portatil", precio_max=30), elegir(2),
             llamada("cotizar"), "El total es X euros. ¿Confirmas?",
             llamada("confirmar_pedido"), "El stock cambio. ¿Quieres otra mochila?",
             lambda m: llamada("cambiar_cantidad", cantidad=0, product_id=m[0]["content"].split("* ")[1].split(" |")[0]),
             llamada("buscar_productos", consulta="mochila portatil", precio_max=30),
             elegir(4), llamada("cotizar"), "Nueva cotizacion. ¿Confirmas?",
             llamada("confirmar_pedido"), "Pedido registrado.",
             llamada("confirmar_pedido"), "Ya estaba registrado, no se duplico."]
    sis.llm = LLMGuion(guion)
    sis.reiniciar()
    e06 = next(e for e in ESCENARIOS if e["id"] == "E06")
    r = ejecutar({**e06, "modo": "texto"}, sis, "texto", tmp / "E06")
    assert r["completado"], (r["fallos"], r["incumplimientos"])
    assert not sis.llm.salidas, "sobraron salidas del guion"

    fac = pd.DataFrame(factibilidad(sis))
    assert fac["factible"].all(), fac[~fac["factible"]]
    print("AUTOPRUEBA OK:", len(ESCENARIOS), "escenarios factibles; tienda, validaciones, agente y verificacion")


if __name__ == "__main__":
    main()
