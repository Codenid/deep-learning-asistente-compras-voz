"""Recuperacion sobre el catalogo: BM25 (modelo base lexico), denso (e5), hibrido y reranker.

Metodos (mismos para evaluacion y para el agente):
  bm25            modelo base lexico
  denso           e5 (coseno)
  hibrido         alpha * denso + (1 - alpha) * bm25         (min-max por consulta)
  bm25+reranker   beta * reranker + (1 - beta) * bm25        (ablacion: sin denso)
  sistema         beta * reranker + (1 - beta) * hibrido     (completo)
alpha y beta se ajustan SOLO con consultas dev.
"""
import hashlib
import re
import unicodedata

import numpy as np
import pandas as pd
from rank_bm25 import BM25Okapi

STOP = set("a al ante con contra de del desde el en entre es la las lo los o para por que se sin sobre su sus "
           "un una unas unos y e u".split())
METODOS = ["bm25", "denso", "hibrido", "bm25+reranker", "sistema"]


def normalizar(t):
    t = unicodedata.normalize("NFKD", str(t).lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def tokens(t):
    return [w for w in re.findall(r"[a-z0-9]+", normalizar(t)) if w not in STOP]


def minmax(x):
    x = np.asarray(x, dtype=float)
    r = x.max() - x.min() if len(x) else 0
    return (x - x.min()) / r if r > 0 else np.zeros_like(x)


def ndcg(ganancias_rank, ganancias_todas, k):
    g = np.asarray(ganancias_rank[:k], dtype=float)
    ideal = np.sort(np.asarray(ganancias_todas, dtype=float))[::-1][:k]
    desc = 1 / np.log2(np.arange(2, k + 2))
    idcg = (ideal * desc[:len(ideal)]).sum()
    return float((g * desc[:len(g)]).sum() / idcg) if idcg > 0 else 0.0


class Recuperador:
    def __init__(self, catalogo, max_chars=600):
        self.cat = catalogo.reset_index(drop=True)
        self.ids = self.cat["product_id"].tolist()
        self.pos = {p: i for i, p in enumerate(self.ids)}
        c = self.cat
        self.docs = (c["titulo"] + ". " + c["marca"] + ". " + c["color"] + ". "
                     + c["caracteristicas"].str[:max_chars] + " " + c["descripcion"].str[:max_chars // 2]).tolist()
        self.docs_rr = (c["titulo"] + ". " + c["marca"] + ". " + c["color"] + ". "
                        + c["caracteristicas"].str[:300]).tolist()
        self.bm25 = BM25Okapi([tokens(d) for d in self.docs])
        self.encoder = self.emb = self.reranker = None
        self.alpha, self.beta = 0.5, 0.5

    # --- modelos ---
    def cargar_denso(self, modelo, dispositivo, ruta_cache):
        from sentence_transformers import SentenceTransformer
        self.encoder = SentenceTransformer(modelo, device=dispositivo)
        h = hashlib.sha256((modelo + "|".join(self.ids)).encode()).hexdigest()[:12]
        ruta = ruta_cache / f"emb_{h}.npy"
        if ruta.exists():
            self.emb = np.load(ruta)
        else:
            self.emb = self.encoder.encode(["passage: " + d for d in self.docs], batch_size=64,
                                           normalize_embeddings=True, show_progress_bar=True).astype(np.float32)
            ruta_cache.mkdir(parents=True, exist_ok=True)
            np.save(ruta, self.emb)
        return ruta

    def cargar_reranker(self, modelo, dispositivo):
        from sentence_transformers import CrossEncoder
        self.reranker = CrossEncoder(modelo, device=dispositivo, max_length=256)
        if str(dispositivo).startswith("cuda"):
            self.reranker.model.half()

    # --- puntajes ---
    def s_bm25(self, q, idx=None):
        t = tokens(q)
        return self.bm25.get_scores(t) if idx is None else np.asarray(self.bm25.get_batch_scores(t, list(idx)))

    def s_denso(self, q, idx=None):
        v = self.encoder.encode(["query: " + q], normalize_embeddings=True)[0]
        return self.emb @ v if idx is None else self.emb[list(idx)] @ v

    def s_rerank(self, q, idx):
        return np.asarray(self.reranker.predict([(q, self.docs_rr[i]) for i in idx], batch_size=32,
                                                show_progress_bar=False), dtype=float)

    @staticmethod
    def combinar(metodo, bm, den=None, rr=None, alpha=0.5, beta=0.5):
        if metodo == "bm25":
            return np.asarray(bm, dtype=float)
        if metodo == "denso":
            return np.asarray(den, dtype=float)
        hib = alpha * minmax(den) + (1 - alpha) * minmax(bm) if den is not None else minmax(bm)
        if metodo == "hibrido":
            return hib
        base = minmax(bm) if metodo == "bm25+reranker" else hib
        return beta * minmax(rr) + (1 - beta) * base

    def buscar(self, consulta, k=10, metodo="sistema", top_cand=50, top_rr=30):
        """Top-k sobre todo el catalogo. Devuelve indices de catalogo ordenados."""
        bm = self.s_bm25(consulta)
        if metodo == "bm25":
            return list(np.argsort(-bm)[:k])
        usa_denso = self.encoder is not None and metodo != "bm25+reranker"   # ablacion: candidatos solo BM25
        den = self.s_denso(consulta) if usa_denso else None
        cand = set(np.argsort(-bm)[:top_cand])
        if den is not None:
            cand |= set(np.argsort(-den)[:top_cand])
        if metodo == "denso":
            return list(np.argsort(-den)[:k])
        cand = np.array(sorted(cand))
        s = self.combinar("hibrido", bm[cand], None if den is None else den[cand], alpha=self.alpha)
        orden = cand[np.argsort(-s)]
        if metodo == "hibrido" or self.reranker is None:
            return list(orden[:k])
        sub = orden[:top_rr]
        s = self.combinar(metodo, bm[sub], None if den is None else den[sub], self.s_rerank(consulta, sub),
                          self.alpha, self.beta)
        return list(sub[np.argsort(-s)][:k])


# --- evaluacion ---
def precomputar(rec, consultas, qrels, ganancias):
    """Puntajes de cada metodo sobre los candidatos anotados de cada consulta (se calculan una sola vez)."""
    out = {}
    q = qrels.assign(g=qrels["esci_label"].map(ganancias), i=qrels["product_id"].map(rec.pos))
    for qid, txt in zip(consultas["query_id"], consultas["query"]):
        f = q[q["query_id"] == qid]
        idx = f["i"].to_numpy()
        out[qid] = {"query": txt, "g": f["g"].to_numpy(), "etiquetas": f["esci_label"].to_numpy(),
                    "ids": f["product_id"].to_numpy(), "bm": rec.s_bm25(txt, idx),
                    "den": rec.s_denso(txt, idx) if rec.encoder is not None else None,
                    "rr": rec.s_rerank(txt, idx) if rec.reranker is not None else None}
    return out


def evaluar(pre, metodo, alpha, beta, k):
    filas = []
    for qid, d in pre.items():
        s = Recuperador.combinar(metodo, d["bm"], d["den"], d["rr"], alpha, beta)
        orden = np.argsort(-s, kind="stable")
        filas.append({"query_id": qid, "query": d["query"], "ndcg": ndcg(d["g"][orden], d["g"], k),
                      "top3": " | ".join(f"{d['etiquetas'][i]}" for i in orden[:3])})
    return pd.DataFrame(filas)


def ajustar(pre_dev, k, grid):
    """alpha en hibrido y beta en sistema / bm25+reranker, maximizando nDCG@k en dev."""
    tabla, mejor = [], {}
    if next(iter(pre_dev.values()))["den"] is not None:
        for a in grid:
            tabla.append({"metodo": "hibrido", "alpha": a, "beta": None,
                          "ndcg_dev": evaluar(pre_dev, "hibrido", a, 0, k)["ndcg"].mean()})
    t = pd.DataFrame(tabla)
    mejor["alpha"] = float(t.loc[t["ndcg_dev"].idxmax(), "alpha"]) if len(t) else 0.0
    if next(iter(pre_dev.values()))["rr"] is not None:
        for m in ("sistema", "bm25+reranker"):
            for b in grid:
                tabla.append({"metodo": m, "alpha": mejor["alpha"], "beta": b,
                              "ndcg_dev": evaluar(pre_dev, m, mejor["alpha"], b, k)["ndcg"].mean()})
        t = pd.DataFrame(tabla)
        for m in ("sistema", "bm25+reranker"):
            s = t[t["metodo"] == m]
            mejor[f"beta_{m}"] = float(s.loc[s["ndcg_dev"].idxmax(), "beta"])
    return mejor, pd.DataFrame(tabla)


def evaluar_catalogo(rec, consultas, qrels, metodo, ganancias, k, beta=None):
    """nDCG@k recuperando de todo el catalogo (productos no anotados = 0). Complementario al oficial."""
    if beta is not None:
        rec.beta = beta
    filas = []
    for qid, txt in zip(consultas["query_id"], consultas["query"]):
        f = qrels[qrels["query_id"] == qid]
        gmap = dict(zip(f["product_id"], f["esci_label"].map(ganancias)))
        top = [rec.ids[i] for i in rec.buscar(txt, k, metodo)]
        filas.append({"query_id": qid, "ndcg": ndcg([gmap.get(p, 0.0) for p in top], list(gmap.values()), k)})
    return pd.DataFrame(filas)
