"""Compara el modelo base contra el modelo con variables de trayectoria (mismo protocolo temporal)."""
import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from clasificacion import CAT, MARCAS, NUM_BASE, TRAYECTORIA, armar, cargar_base, construir_dataset, evaluar, modelos  # noqa: E402

ep, ciclos, pagos, diario, CORTE = cargar_base(RAIZ / "data" / "anon")
K, H, X = 8, 12, 14
data = construir_dataset(ep, ciclos, pagos, diario, CORTE, pd.Timestamp("2024-03-30"), K, H, X)
print(len(data), data.y.mean())
print(data[TRAYECTORIA].describe().T[["count", "mean", "min", "max"]])

filas = []
for nombre, clf in modelos(0).items():
    for etiqueta, tray in (("base", False), ("+trayectoria", True)):
        cols = NUM_BASE + MARCAS + CAT + (TRAYECTORIA if tray else [])
        r = evaluar(armar(clf, True, True, 0, con_trayectoria=tray), data, cols, K, H, X)
        filas.append({"modelo": nombre, "vars": etiqueta, "AUC val": r["auc_validacion"], "sd": r["auc_validacion_sd"],
                      "AUC prueba": r["prueba"]["AUC"], "BACC prueba": r["prueba"]["BACC"], "MCC prueba": r["prueba"]["MCC"]})
        print(filas[-1], flush=True)
tab = pd.DataFrame(filas); tab.to_csv(RAIZ / "reports" / "mejora_trayectoria.csv", index=False)
print(tab.round(3).to_string())
