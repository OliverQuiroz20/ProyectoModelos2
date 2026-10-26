"""Validacion externa: entrena con Cartagena y prueba en Sincelejo y Monteria (mismos K, H, X)."""
import sys, warnings, json
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.base import clone
from sklearn.metrics import roc_auc_score
warnings.filterwarnings("ignore")
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
import clasificacion as cl
K, H, X = 8, 12, 14
def datos(dir_, inicio):
    ep, ciclos, pagos, diario, corte = cl.cargar_base(dir_)
    return cl.construir_dataset(ep, ciclos, pagos, diario, corte, pd.Timestamp(inicio), K, H, X)
cart = datos(RAIZ / "data/anon", "2024-03-30")
sedes = {"Sincelejo": datos(RAIZ / "data/anon/sincelejo", "2025-06-01"), "Montería": datos(RAIZ / "data/anon/monteria", "2026-01-01")}
print("Cartagena", len(cart), round(cart.y.mean(), 3))
for n, d in sedes.items():
    print(n, len(d), "positivos", round(d.y.mean(), 3), "| empresa:", d.empresa.value_counts().to_dict(), "| tipopago:", d.tipopago.value_counts().to_dict())
def topk(y, p, f):
    n = max(1, int(len(y) * f)); return y[np.argsort(-p)[:n]].mean()
CAT0 = list(cl.CAT)
filas = []
for etiqueta, cat in (("con empresa", CAT0), ("sin empresa", [c for c in CAT0 if c != "empresa"])):
    cl.CAT[:] = cat
    cols = cl.NUM_BASE + cl.MARCAS + cl.CAT
    for nombre, clf in list(cl.modelos(0).items()):
        if nombre not in ("Regresión logística", "Random Forest", "Gradient Boosting"): continue
        m = cl.armar(clf, True, True, 0).fit(cart[cols], cart.y)
        for sede, d in sedes.items():
            p = m.predict_proba(d[cols])[:, 1]; y = d.y.to_numpy()
            filas.append({"vars": etiqueta, "modelo": nombre, "sede": sede, "n": len(d), "pos": round(y.mean(), 3),
                          "AUC": round(roc_auc_score(y, p), 3), "top10": round(topk(y, p, .1), 3), "top20": round(topk(y, p, .2), 3)})
            print(filas[-1], flush=True)
cl.CAT[:] = CAT0
pd.DataFrame(filas).to_csv(RAIZ / "reports/validacion_externa_sedes.csv", index=False)
