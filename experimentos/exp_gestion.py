"""Compara base vs base + variables de gestion/justificaciones (mismo protocolo temporal)."""
import sys, warnings
from pathlib import Path
import pandas as pd
warnings.filterwarnings("ignore")
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
import clasificacion as cl
from variables import variables_gestion
ep, ciclos, pagos, diario, CORTE = cl.cargar_base(RAIZ / "data" / "anon")
K, H, X = 8, 12, 14
data = cl.construir_dataset(ep, ciclos, pagos, diario, CORTE, pd.Timestamp("2024-03-30"), K, H, X)
just = pd.read_csv(RAIZ / "data/anon/justificaciones.csv.gz"); gest = pd.read_csv(RAIZ / "data/anon/gestion.csv.gz")
pob = ep[ep.id_episodio.isin(data.id_episodio)].set_index("id_episodio").loc[data.id_episodio].reset_index()
G = variables_gestion(pob, just, gest, K).reset_index(drop=True)
data = pd.concat([data.reset_index(drop=True), G], axis=1)
GC = list(G.columns)
print(data[GC].describe().T[["mean", "max"]].round(2)); print(data.groupby("y")[GC].mean().T.round(2))
COLS = cl.NUM_BASE + cl.MARCAS + cl.CAT
cl.NUM_BASE_ORIG = list(cl.NUM_BASE)
rows = []
for nombre, clf in cl.modelos(0).items():
    for et, extra in (("base", []), ("+gestion", GC)):
        cl.NUM_BASE[:] = cl.NUM_BASE_ORIG + extra
        r = cl.evaluar(cl.armar(clf, True, True, 0), data, cl.NUM_BASE + cl.MARCAS + cl.CAT, K, H, X)
        rows.append({"modelo": nombre, "vars": et, "AUC val": r["auc_validacion"], "sd": r["auc_validacion_sd"],
                     "AUC prueba": r["prueba"]["AUC"], "BACC": r["prueba"]["BACC"], "MCC": r["prueba"]["MCC"]})
        print(rows[-1], flush=True)
tab = pd.DataFrame(rows); tab.to_csv(RAIZ / "reports" / "mejora_gestion.csv", index=False)
print(tab.round(3).to_string())
