"""Bitacora de pasos (CSV + MD), progreso en vivo y registro de lo ya ejecutado (hash de configuracion)."""
import csv
import datetime as dt
import hashlib
import json
import time
from contextlib import contextmanager
from pathlib import Path

COLS = ["ejecucion", "paso", "inicio", "fin", "duracion_s", "tiempo_usado", "avance", "estado", "comentario"]


def hms(seg):
    h, r = divmod(seg, 3600)
    m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def hash_cfg(cfg):
    return hashlib.sha256(json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()[:12]


class Bitacora:
    def __init__(self, carpeta, forzar=False):
        self.carpeta = Path(carpeta)
        self.carpeta.mkdir(parents=True, exist_ok=True)
        self.forzar = forzar
        self.ej = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.csv = self.carpeta / "bitacora_pasos.csv"
        self.md = self.carpeta / "bitacora_pasos.md"
        self.progreso = self.carpeta / "progreso.md"
        self.reg = self.carpeta / "registro.json"
        self.filas = list(csv.DictReader(open(self.csv, encoding="utf-8"))) if self.csv.exists() else []
        self.actual = "-"

    # --- registro de lo ya ejecutado ---
    def leer_registro(self):
        return json.loads(self.reg.read_text(encoding="utf-8")) if self.reg.exists() else {}

    def registrar(self, clave, info):
        r = self.leer_registro()
        r[clave] = info
        self.reg.write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")

    def ya_ejecutado(self, clave, h, salidas=()):
        e = self.leer_registro().get(clave)
        return (not self.forzar and e is not None and e.get("hash") == h
                and all(Path(s).exists() for s in salidas))

    # --- tabla de pasos ---
    def _guardar(self):
        with open(self.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, COLS, extrasaction="ignore")
            w.writeheader()
            w.writerows(self.filas)
        lin = ["| " + " | ".join(COLS) + " |", "|" + "---|" * len(COLS)]
        lin += ["| " + " | ".join(str(r.get(c, "")).replace("|", "/") for c in COLS) + " |" for r in self.filas]
        self.md.write_text("\n".join(lin) + "\n", encoding="utf-8")
        mios = [r for r in self.filas if r["ejecucion"] == self.ej]
        hechos = sum(1 for r in mios if str(r["avance"]) == "1")
        self.progreso.write_text(f"# Progreso (ejecucion {self.ej})\n\nPasos completados: {hechos} de {len(mios)}\n"
                                 f"Paso en curso: {self.actual}\n", encoding="utf-8")

    @contextmanager
    def paso(self, nombre, comentario=""):
        info = {"estado": "OK", "comentario": comentario}
        t0 = time.time()
        fila = {"ejecucion": self.ej, "paso": nombre, "inicio": dt.datetime.now().strftime("%H:%M:%S"),
                "fin": "", "duracion_s": "", "tiempo_usado": "", "avance": 0, "estado": "EN CURSO",
                "comentario": comentario}
        self.filas.append(fila)
        self.actual = nombre
        self._guardar()
        print(f"> {nombre}")
        try:
            yield info
        except Exception as e:
            info["estado"] = "ERROR"
            info["comentario"] = f"{info['comentario']} | {type(e).__name__}: {e}"
            raise
        finally:
            seg = time.time() - t0
            fila.update({"fin": dt.datetime.now().strftime("%H:%M:%S"), "duracion_s": f"{seg:.3f}",
                         "tiempo_usado": hms(seg), "avance": 1 if info["estado"] in ("OK", "OMITIDO") else 0,
                         "estado": info["estado"], "comentario": info["comentario"]})
            self.actual = "-"
            self._guardar()
            print(f"  {info['estado']} | {hms(seg)}")

    def ejecutar(self, clave, cfg, salidas, fn):
        """Ejecuta fn() salvo que ya se haya ejecutado con la misma configuracion y existan las salidas."""
        h = hash_cfg(cfg)
        if self.ya_ejecutado(clave, h, salidas):
            with self.paso(clave) as info:
                info["estado"], info["comentario"] = "OMITIDO", f"ya ejecutado (hash {h})"
            return h
        with self.paso(clave, f"hash {h}"):
            fn()
            faltan = [str(s) for s in salidas if not Path(s).exists()]
            if faltan:
                raise RuntimeError(f"salidas faltantes: {faltan}")
            self.registrar(clave, {"hash": h, "fecha": dt.datetime.now().strftime("%Y-%m-%d %H:%M")})
        return h
