"""Tienda simulada en SQLite: precios, existencias, carritos, cotizaciones y pedidos.

- Datos ficticios generados con semilla fija en una base "base"; restaurar() copia la base sobre la de trabajo.
- Montos en centimos (enteros) para evitar errores de redondeo.
- confirmar() es atomico (BEGIN IMMEDIATE): o se registra todo (pedido + inventario) o nada.
- Un pedido por cotizacion (UNIQUE): repetir la confirmacion devuelve el mismo pedido, sin duplicar.
"""
import hashlib
import json
import shutil
import sqlite3

import numpy as np

ESQUEMA = """
CREATE TABLE productos(product_id TEXT PRIMARY KEY, precio_cent INTEGER NOT NULL CHECK(precio_cent > 0),
                       stock INTEGER NOT NULL CHECK(stock >= 0));
CREATE TABLE carritos(id INTEGER PRIMARY KEY AUTOINCREMENT, estado TEXT NOT NULL DEFAULT 'abierto',
                      version INTEGER NOT NULL DEFAULT 0);
CREATE TABLE carrito_items(carrito_id INTEGER NOT NULL, product_id TEXT NOT NULL,
                           cantidad INTEGER NOT NULL CHECK(cantidad > 0), PRIMARY KEY(carrito_id, product_id));
CREATE TABLE cotizaciones(id TEXT PRIMARY KEY, carrito_id INTEGER, version INTEGER, total_cent INTEGER,
                          presupuesto_cent INTEGER, items TEXT, valida INTEGER);
CREATE TABLE pedidos(id INTEGER PRIMARY KEY AUTOINCREMENT, cotizacion_id TEXT UNIQUE NOT NULL,
                     carrito_id INTEGER, total_cent INTEGER);
CREATE TABLE pedido_items(pedido_id INTEGER, product_id TEXT, cantidad INTEGER, precio_cent INTEGER);
"""


def euros(cent):
    return None if cent is None else round(cent / 100, 2)


class ErrorTienda(Exception):
    pass


class Tienda:
    def __init__(self, ruta_base, ruta_trabajo, cantidad_max):
        self.base, self.trabajo, self.cmax = ruta_base, ruta_trabajo, cantidad_max
        self.con = None

    # --- creacion y restauracion ---
    @staticmethod
    def crear_base(ruta_base, product_ids, semilla, mu, sigma, rango, prob_agotado, stock_max):
        rng = np.random.default_rng(semilla)
        ids = sorted(product_ids)
        precio = np.clip(np.exp(rng.normal(mu, sigma, len(ids))), *rango)
        cent = (np.floor(precio) * 100 + 99).astype(int)                       # precios x,99
        stock = np.where(rng.random(len(ids)) < prob_agotado, 0, rng.integers(1, stock_max + 1, len(ids)))
        ruta_base.parent.mkdir(parents=True, exist_ok=True)
        ruta_base.unlink(missing_ok=True)
        con = sqlite3.connect(ruta_base)
        con.executescript(ESQUEMA)
        con.executemany("INSERT INTO productos VALUES (?,?,?)",
                        zip(ids, map(int, cent), map(int, stock)))
        con.commit()
        con.close()

    def restaurar(self):
        if self.con is not None:
            self.con.close()
        shutil.copyfile(self.base, self.trabajo)
        self.con = sqlite3.connect(self.trabajo, isolation_level=None)   # transacciones explicitas
        self.con.execute("PRAGMA foreign_keys=ON")

    def huella(self):
        """Hash del inventario y pedidos: dos restauraciones deben dar la misma huella."""
        filas = self.con.execute("SELECT * FROM productos ORDER BY product_id").fetchall()
        filas += self.con.execute("SELECT * FROM pedidos ORDER BY id").fetchall()
        return hashlib.sha256(json.dumps(filas).encode()).hexdigest()[:16]

    # --- consultas ---
    def producto(self, pid):
        r = self.con.execute("SELECT precio_cent, stock FROM productos WHERE product_id=?", (pid,)).fetchone()
        return None if r is None else {"precio_cent": r[0], "stock": r[1]}

    def precios_stock(self, pids):
        q = f"SELECT product_id, precio_cent, stock FROM productos WHERE product_id IN ({','.join('?' * len(pids))})"
        return {p: {"precio_cent": c, "stock": s} for p, c, s in self.con.execute(q, list(pids))}

    # --- carrito ---
    def nuevo_carrito(self):
        return self.con.execute("INSERT INTO carritos DEFAULT VALUES").lastrowid

    def carrito(self, cid):
        est = self.con.execute("SELECT estado, version FROM carritos WHERE id=?", (cid,)).fetchone()
        if est is None:
            raise ErrorTienda("carrito inexistente")
        items = [{"product_id": p, "cantidad": c, "precio_cent": pc, "stock": s, "subtotal_cent": c * pc}
                 for p, c, pc, s in self.con.execute(
                     "SELECT i.product_id, i.cantidad, p.precio_cent, p.stock FROM carrito_items i "
                     "JOIN productos p USING(product_id) WHERE i.carrito_id=? ORDER BY i.rowid", (cid,))]
        return {"carrito_id": cid, "estado": est[0], "version": est[1], "items": items,
                "total_cent": sum(i["subtotal_cent"] for i in items)}

    def fijar_cantidad(self, cid, pid, cantidad):
        """cantidad = 0 elimina la linea. Valida entero, limite, stock y carrito abierto."""
        if not isinstance(cantidad, int) or isinstance(cantidad, bool) or cantidad < 0:
            raise ErrorTienda("cantidad invalida: debe ser un entero mayor o igual a 0")
        if cantidad > self.cmax:
            raise ErrorTienda(f"cantidad maxima por producto: {self.cmax}")
        prod = self.producto(pid)
        if prod is None:
            raise ErrorTienda("producto inexistente")
        if self.carrito(cid)["estado"] != "abierto":
            raise ErrorTienda("el carrito ya fue cerrado por un pedido")
        if cantidad > prod["stock"]:
            raise ErrorTienda(f"stock insuficiente: disponibles {prod['stock']}")
        self.con.execute("BEGIN")
        if cantidad == 0:
            self.con.execute("DELETE FROM carrito_items WHERE carrito_id=? AND product_id=?", (cid, pid))
        else:
            self.con.execute("INSERT INTO carrito_items VALUES (?,?,?) ON CONFLICT(carrito_id, product_id) "
                             "DO UPDATE SET cantidad=excluded.cantidad", (cid, pid, cantidad))
        self.con.execute("UPDATE carritos SET version=version+1 WHERE id=?", (cid,))
        self.con.execute("COMMIT")
        return self.carrito(cid)

    # --- cotizacion y pedido ---
    def cotizar(self, cid, presupuesto_cent=None):
        car = self.carrito(cid)
        problemas = []
        if car["estado"] != "abierto":
            problemas.append("el carrito ya fue cerrado por un pedido")
        if not car["items"]:
            problemas.append("el carrito esta vacio")
        for i in car["items"]:
            if i["cantidad"] > i["stock"]:
                problemas.append(f"{i['product_id']}: stock insuficiente (disponibles {i['stock']})")
        if presupuesto_cent is not None and car["total_cent"] > presupuesto_cent:
            problemas.append(f"el total {euros(car['total_cent'])} supera el presupuesto {euros(presupuesto_cent)}")
        cot_id = f"COT-{cid}-{car['version']}"
        items = [{k: i[k] for k in ("product_id", "cantidad", "precio_cent")} for i in car["items"]]
        self.con.execute("INSERT OR REPLACE INTO cotizaciones VALUES (?,?,?,?,?,?,?)",
                         (cot_id, cid, car["version"], car["total_cent"], presupuesto_cent,
                          json.dumps(items), int(not problemas)))
        return {"cotizacion_id": cot_id, "items": car["items"], "total_cent": car["total_cent"],
                "valida": not problemas, "problemas": problemas}

    def pedido(self, pedido_id):
        tot, cot = self.con.execute("SELECT total_cent, cotizacion_id FROM pedidos WHERE id=?", (pedido_id,)).fetchone()
        items = [{"product_id": p, "cantidad": c, "precio_cent": pc} for p, c, pc in self.con.execute(
            "SELECT product_id, cantidad, precio_cent FROM pedido_items WHERE pedido_id=?", (pedido_id,))]
        return {"pedido_id": pedido_id, "cotizacion_id": cot, "total_cent": tot, "items": items}

    def confirmar(self, cot_id, presupuesto_cent=None):
        """Revalida todo dentro de una transaccion. Devuelve estado: registrado | ya_registrado | rechazado."""
        c = self.con
        c.execute("BEGIN IMMEDIATE")
        try:
            prev = c.execute("SELECT id FROM pedidos WHERE cotizacion_id=?", (cot_id,)).fetchone()
            if prev:
                c.execute("ROLLBACK")
                return {"estado": "ya_registrado", **self.pedido(prev[0])}
            cot = c.execute("SELECT carrito_id, version, items FROM cotizaciones WHERE id=?", (cot_id,)).fetchone()
            if cot is None:
                c.execute("ROLLBACK")
                return {"estado": "rechazado", "problemas": ["cotizacion inexistente"]}
            cid, version, items_cot = cot[0], cot[1], {i["product_id"]: i for i in json.loads(cot[2])}
            car = self.carrito(cid)
            problemas = []
            if car["estado"] != "abierto":
                problemas.append("el carrito ya fue cerrado")
            if car["version"] != version:
                problemas.append("el carrito cambio despues de la cotizacion")
            for i in car["items"]:
                if i["cantidad"] > i["stock"]:
                    problemas.append(f"{i['product_id']}: stock insuficiente (pedido {i['cantidad']}, "
                                     f"disponibles {i['stock']})")
                ref = items_cot.get(i["product_id"])
                if ref and ref["precio_cent"] != i["precio_cent"]:
                    problemas.append(f"{i['product_id']}: el precio cambio de {euros(ref['precio_cent'])} "
                                     f"a {euros(i['precio_cent'])}")
            if presupuesto_cent is not None and car["total_cent"] > presupuesto_cent:
                problemas.append(f"el total {euros(car['total_cent'])} supera el presupuesto {euros(presupuesto_cent)}")
            if not car["items"]:
                problemas.append("el carrito esta vacio")
            if problemas:
                c.execute("ROLLBACK")
                return {"estado": "rechazado", "problemas": problemas}
            for i in car["items"]:
                cur = c.execute("UPDATE productos SET stock=stock-? WHERE product_id=? AND stock>=?",
                                (i["cantidad"], i["product_id"], i["cantidad"]))
                if cur.rowcount != 1:
                    raise ErrorTienda("stock modificado durante la confirmacion")
            pid = c.execute("INSERT INTO pedidos(cotizacion_id, carrito_id, total_cent) VALUES (?,?,?)",
                            (cot_id, cid, car["total_cent"])).lastrowid
            c.executemany("INSERT INTO pedido_items VALUES (?,?,?,?)",
                          [(pid, i["product_id"], i["cantidad"], i["precio_cent"]) for i in car["items"]])
            c.execute("UPDATE carritos SET estado='cerrado' WHERE id=?", (cid,))
            c.execute("COMMIT")
            return {"estado": "registrado", **self.pedido(pid)}
        except Exception:
            if c.in_transaction:
                c.execute("ROLLBACK")
            raise

    # --- eventos de escenarios (no los usa el agente) ---
    def fijar_stock(self, pid, stock):
        self.con.execute("UPDATE productos SET stock=? WHERE product_id=?", (int(stock), pid))

    def fijar_precio(self, pid, precio_cent):
        self.con.execute("UPDATE productos SET precio_cent=? WHERE product_id=?", (int(precio_cent), pid))

    def resumen(self):
        """Estado final: pedidos con items, carritos y productos cuyo stock/precio cambio respecto de la base."""
        pedidos = [self.pedido(r[0]) for r in self.con.execute("SELECT id FROM pedidos ORDER BY id")]
        carritos = [self.carrito(r[0]) for r in self.con.execute("SELECT id FROM carritos ORDER BY id")]
        self.con.execute("ATTACH DATABASE ? AS b", (str(self.base),))
        cambios = [{"product_id": p, "stock_base": sb, "stock": s, "precio_base_cent": pb, "precio_cent": pc}
                   for p, sb, s, pb, pc in self.con.execute(
                       "SELECT p.product_id, q.stock, p.stock, q.precio_cent, p.precio_cent FROM productos p "
                       "JOIN b.productos q USING(product_id) WHERE p.stock<>q.stock OR p.precio_cent<>q.precio_cent")]
        self.con.execute("DETACH DATABASE b")
        negativos = self.con.execute("SELECT COUNT(*) FROM productos WHERE stock<0").fetchone()[0]
        return {"huella": self.huella(), "pedidos": pedidos, "carritos": carritos,
                "productos_modificados": cambios, "stock_negativo": negativos}
