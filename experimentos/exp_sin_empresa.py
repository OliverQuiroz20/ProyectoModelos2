"""Ablacion de la variable empresa en Cartagena: mismo protocolo temporal con y sin `empresa`."""
import sys, warnings
from pathlib import Path
import pandas as pd
warnings.filterwarnings("ignore")
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
import clasificacion as c
ep, ciclos, pagos, diario, CORTE = c.cargar_base(RAIZ / "data" / "anon")
K, H, X = 8, 12, 14
data = c.construir_dataset(ep, ciclos, pagos, diario, CORTE, pd.Timestamp("2024-03-30"), K, H, X)
print(data.groupby("empresa").y.agg(["size", "mean"]).round(3).to_string(), flush=True)
CAT_CON = list(c.CAT)
filas = []
for etiqueta, cat in (("con empresa", CAT_CON), ("sin empresa", [v for v in CAT_CON if v != "empresa"])):
    c.CAT = cat  # el Preprocesador lee la lista global al ajustar
    cols = c.NUM_BASE + c.MARCAS + cat
    for nombre, clf in c.modelos().items():
        if nombre not in ("Regresión logística", "Random Forest", "Gradient Boosting"):
            continue
        r = c.evaluar(c.armar(clf, True, True, 0), data, cols, K, H, X)
        print(etiqueta, nombre, f"val={r['auc_validacion']:.3f} prueba={r['prueba']['AUC']:.3f}", flush=True)
        filas.append({"variables": etiqueta, "modelo": nombre, "AUC val": r["auc_validacion"], "sd": r["auc_validacion_sd"],
                      "AUC prueba": r["prueba"]["AUC"], "BACC prueba": r["prueba"]["BACC"], "MCC prueba": r["prueba"]["MCC"]})
pd.DataFrame(filas).to_csv(RAIZ / "reports" / "ablacion_empresa_cartagena.csv", index=False)
