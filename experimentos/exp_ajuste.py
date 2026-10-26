"""Ajuste de hiperparametros (criterio: AUC de validacion temporal) y ensamble.

La prueba solo se reporta; no interviene en la eleccion de la configuracion.
"""
import itertools
import sys
import warnings
from pathlib import Path

import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression

warnings.filterwarnings("ignore")
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from clasificacion import CAT, MARCAS, NUM_BASE, armar, cargar_base, construir_dataset, evaluar  # noqa: E402

ep, ciclos, pagos, diario, CORTE = cargar_base(RAIZ / "data" / "anon")
K, H, X = 8, 12, 14
data = construir_dataset(ep, ciclos, pagos, diario, CORTE, pd.Timestamp("2024-03-30"), K, H, X)
COLS = NUM_BASE + MARCAS + CAT


def correr(nombre, clf):
    r = evaluar(armar(clf, True, True, 0), data, COLS, K, H, X)
    fila = {"modelo": nombre, "AUC val": r["auc_validacion"], "sd": r["auc_validacion_sd"],
            "AUC prueba": r["prueba"]["AUC"], "BACC prueba": r["prueba"]["BACC"], "MCC prueba": r["prueba"]["MCC"]}
    print(fila, flush=True)
    return fila


filas = []
for C, pen in itertools.product([0.02, 0.05, 0.1, 0.5, 2.0], ["l2", "l1"]):
    filas.append(correr(f"LR C={C} {pen}", LogisticRegression(C=C, penalty=pen, solver="liblinear", class_weight="balanced")))
for d, leaf, mf in itertools.product([4, 6, None], [5, 15, 30], ["sqrt", 0.5]):
    filas.append(correr(f"RF depth={d} leaf={leaf} mf={mf}", RandomForestClassifier(
        n_estimators=300, max_depth=d, min_samples_leaf=leaf, max_features=mf, class_weight="balanced", n_jobs=-1, random_state=0)))
for n, d, lr in itertools.product([100, 200, 400], [2, 3], [0.02, 0.05]):
    filas.append(correr(f"GB n={n} d={d} lr={lr}", GradientBoostingClassifier(
        n_estimators=n, max_depth=d, learning_rate=lr, subsample=0.8, random_state=0)))

tab = pd.DataFrame(filas)
tab.to_csv(RAIZ / "reports" / "ajuste_hiperparametros.csv", index=False)
mejor = {p: tab[tab.modelo.str.startswith(p)].sort_values("AUC val").iloc[-1].modelo for p in ("LR", "RF", "GB")}
print("MEJORES:", mejor)
