"""Ensamble (voto suave LR+RF+GB) y precision en el top-k de la prueba."""
import sys, warnings
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
warnings.filterwarnings("ignore")
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from clasificacion import CAT, MARCAS, NUM_BASE, armar, cargar_base, construir_dataset, evaluar
ep, ciclos, pagos, diario, CORTE = cargar_base(RAIZ / "data" / "anon")
K, H, X = 8, 12, 14
data = construir_dataset(ep, ciclos, pagos, diario, CORTE, pd.Timestamp("2024-03-30"), K, H, X)
COLS = NUM_BASE + MARCAS + CAT
lr = LogisticRegression(C=0.5, max_iter=2000, class_weight="balanced")
rf = RandomForestClassifier(n_estimators=300, max_depth=4, min_samples_leaf=5, max_features="sqrt", class_weight="balanced", n_jobs=-1, random_state=0)
gb = GradientBoostingClassifier(n_estimators=100, max_depth=2, learning_rate=0.02, subsample=0.8, random_state=0)
ens = VotingClassifier([("lr", lr), ("rf", rf), ("gb", gb)], voting="soft")
def topk(y, p, fr):
    n = int(len(y) * fr); i = np.argsort(-p)[:n]; return y[i].mean()
filas = []
for nombre, clf in (("LR", lr), ("RF", rf), ("Ensamble", ens)):
    r = evaluar(armar(clf, True, True, 0), data, COLS, K, H, X)
    y, p = r["y_prueba"], r["p_prueba"]
    print(nombre, f"AUCval={r['auc_validacion']:.3f}±{r['auc_validacion_sd']:.3f} AUCte={r['prueba']['AUC']:.3f} BACC={r['prueba']['BACC']:.3f} MCC={r['prueba']['MCC']:.3f}",
          " | precision top10/20/30%:", [round(topk(y, p, f), 3) for f in (.1, .2, .3)], f"base={y.mean():.3f}", flush=True)
    filas.append({"modelo": nombre, "AUC val": r["auc_validacion"], "sd": r["auc_validacion_sd"], "AUC prueba": r["prueba"]["AUC"],
                  "BACC prueba": r["prueba"]["BACC"], "MCC prueba": r["prueba"]["MCC"],
                  **{f"precision top{int(f*100)}%": topk(y, p, f) for f in (.1, .2, .3)}, "base prueba": y.mean()})
pd.DataFrame(filas).to_csv(RAIZ / "reports" / "mejora_ensamble.csv", index=False)
