"""Catalogo, consultas (dev = train, eval = test) y etiquetas ESCI a partir de la version small en espanol."""
import html
import re

import numpy as np
import pandas as pd

ARCH_EX = "shopping_queries_dataset_examples.parquet"
ARCH_PR = "shopping_queries_dataset_products.parquet"
COLS = {"product_id": "product_id", "product_title": "titulo", "product_description": "descripcion",
        "product_bullet_point": "caracteristicas", "product_brand": "marca", "product_color": "color"}


def limpiar(t):
    if t is None or (isinstance(t, float) and np.isnan(t)):
        return ""
    t = re.sub(r"<[^>]+>", " ", html.unescape(str(t)))
    return re.sub(r"\s+", " ", t).strip()


def preparar(ruta_input, ruta_datos, ruta_eval, n_eval, n_dev, min_catalogo, semilla):
    """Genera catalogo.parquet, consultas.parquet y evaluacion/qrels.parquet. Devuelve un resumen."""
    ex = pd.read_parquet(ruta_input / ARCH_EX, columns=["query_id", "query", "product_id", "esci_label",
                                                        "small_version", "product_locale", "split"])
    ex = ex[(ex["small_version"] == 1) & (ex["product_locale"] == "es")]
    rng = np.random.default_rng(semilla)
    q_test = np.sort(ex.loc[ex["split"] == "test", "query_id"].unique())
    q_train = np.sort(ex.loc[ex["split"] == "train", "query_id"].unique())
    q_eval = np.sort(rng.choice(q_test, n_eval, replace=False))
    q_dev = np.sort(rng.choice(q_train, n_dev, replace=False))
    sel = ex[ex["query_id"].isin(np.r_[q_eval, q_dev])]

    pr = pd.read_parquet(ruta_input / ARCH_PR, columns=list(COLS) + ["product_locale"],
                         filters=[("product_locale", "==", "es")]).drop(columns="product_locale")
    pr = pr.drop_duplicates("product_id").set_index("product_id")
    ids = set(sel["product_id"])
    faltan = max(0, min_catalogo - len(ids))
    if faltan:   # distractores: productos ES fuera de las consultas elegidas
        resto = np.sort(np.array(sorted(set(pr.index) - ids)))
        ids |= set(rng.choice(resto, faltan, replace=False))
    cat = pr.loc[sorted(ids)].reset_index().rename(columns=COLS)
    for c in COLS.values():
        if c != "product_id":
            cat[c] = cat[c].map(limpiar)

    consultas = (sel.drop_duplicates("query_id")[["query_id", "query", "split"]]
                 .assign(conjunto=lambda d: np.where(d["split"] == "test", "eval", "dev"))
                 .drop(columns="split").sort_values("query_id").reset_index(drop=True))
    qrels = sel[["query_id", "product_id", "esci_label"]].reset_index(drop=True)
    assert qrels["product_id"].isin(cat["product_id"]).all(), "producto anotado fuera del catalogo"
    assert len(cat) >= min_catalogo and (consultas["conjunto"] == "eval").sum() >= 200

    ruta_datos.mkdir(parents=True, exist_ok=True)
    ruta_eval.mkdir(parents=True, exist_ok=True)
    cat.to_parquet(ruta_datos / "catalogo.parquet", index=False)
    consultas.to_parquet(ruta_datos / "consultas.parquet", index=False)
    qrels.to_parquet(ruta_eval / "qrels.parquet", index=False)

    vc = qrels.merge(consultas, on="query_id").groupby(["conjunto", "esci_label"]).size().unstack(fill_value=0)
    return {"productos": len(cat), "distractores": faltan,
            "consultas_eval": int((consultas["conjunto"] == "eval").sum()),
            "consultas_dev": int((consultas["conjunto"] == "dev").sum()),
            "pares_anotados": len(qrels), "etiquetas": vc.to_dict(orient="index"),
            "faltantes_%": {c: round(float((cat[c] == "").mean() * 100), 1)
                            for c in ["descripcion", "caracteristicas", "marca", "color"]}}
