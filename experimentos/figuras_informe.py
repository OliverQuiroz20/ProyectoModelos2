"""Figuras del informe del Entregable II a partir de reports/ (no recalcula modelos)."""
import json
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
R, OUT = RAIZ / "reports", RAIZ / "informe" / "figuras"
OUT.mkdir(exist_ok=True)
AZUL, NARANJA, VERDE, GRIS = "#2a78d6", "#e8683a", "#2a9a6e", "#8a8f98"
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 200, "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "axes.axisbelow": True, "grid.color": "#e6e6e6"})

# 1. Seis clasificadores: AUC de validacion (media +- sd) y de prueba
m = json.load(open(R / "cifras_clasificacion.json", encoding="utf-8"))["modelos"]
nombres = {"Regresi": "Regresión logística", "Random": "Random Forest", "Gradient": "Gradient Boosting",
           "KNN": "KNN", "SVM": "SVM (RBF)", "rbol": "Árbol de decisión"}
filas = []
for k, v in m.items():
    n = next(val for key, val in nombres.items() if key in k)
    mu, sd = [float(x) for x in v["AUC validación"].replace("±", " ").replace("�", " ").split()[:2]]
    filas.append((n, mu, sd, v["AUC (prueba)"]))
t = pd.DataFrame(filas, columns=["modelo", "val", "sd", "prueba"]).sort_values("val", ascending=False)
fig, ax = plt.subplots(figsize=(6.4, 3.2))
x = range(len(t)); w = 0.38
ax.bar([i - w / 2 for i in x], t.val, w, yerr=t.sd, color=AZUL, capsize=3, label="validación (media de pliegues)")
ax.bar([i + w / 2 for i in x], t.prueba, w, color=NARANJA, label="prueba (más reciente)")
ax.set_xticks(list(x)); ax.set_xticklabels(t.modelo, rotation=20, ha="right"); ax.set_ylim(0.6, 0.88); ax.set_ylabel("AUC")
ax.legend(frameon=False, loc="upper center", ncol=2, fontsize=8); fig.tight_layout(); fig.savefig(OUT / "comparacion_modelos.png"); plt.close(fig)

# 2. Búsqueda de mejora: AUC de validacion de la logistica y el random forest en cada variante
tr = pd.read_csv(R / "mejora_trayectoria.csv"); ge = pd.read_csv(R / "mejora_gestion.csv")
aj = pd.read_csv(R / "ajuste_hiperparametros.csv"); en = pd.read_csv(R / "mejora_ensamble.csv")
def v(df, mod, var): return float(df[(df.modelo == mod) & (df.vars == var)]["AUC val"].iloc[0])
lr = [v(tr, "Regresión logística", "base"), v(tr, "Regresión logística", "+trayectoria"), v(ge, "Regresión logística", "+gestion"),
      aj[aj.modelo.str.startswith("LR")]["AUC val"].max(), float(en[en.modelo == "Ensamble"]["AUC val"].iloc[0])]
rf = [v(tr, "Random Forest", "base"), v(tr, "Random Forest", "+trayectoria"), v(ge, "Random Forest", "+gestion"),
      aj[aj.modelo.str.startswith("RF")]["AUC val"].max(), float(en[en.modelo == "Ensamble"]["AUC val"].iloc[0])]
et = ["modelo base", "+ trayectoria", "+ gestión\ny justificaciones", "hiperparámetros\najustados", "ensamble\n(3 modelos)"]
fig, ax = plt.subplots(figsize=(6.4, 3.2))
ax.axhspan(lr[0] - 0.02, lr[0] + 0.02, color=GRIS, alpha=0.18, zorder=0, label="± desv. entre pliegues (≈ 0,02)")
x = list(range(4))
ax.bar([i - w / 2 for i in x], lr[:4], w, color=AZUL, label="regresión logística", zorder=2)
ax.bar([i + w / 2 for i in x], rf[:4], w, color=VERDE, label="random forest", zorder=2)
ax.bar([4], [lr[4]], w * 1.4, color=NARANJA, label="ensamble", zorder=2)
ax.set_xticks(range(5)); ax.set_xticklabels(et, fontsize=8); ax.set_ylim(0.74, 0.855); ax.set_ylabel("AUC de validación")
ax.legend(frameon=False, loc="upper center", fontsize=7.5, ncol=4, columnspacing=1.0, handlelength=1.2); fig.tight_layout(); fig.savefig(OUT / "busqueda_mejora.png"); plt.close(fig)

# 3. Validación externa
s = pd.read_csv(R / "validacion_externa_sedes.csv"); s = s[s.vars == "con empresa"]
p = s.pivot(index="modelo", columns="sede", values="AUC").loc[["Regresión logística", "Random Forest", "Gradient Boosting"]]
p.insert(0, "Cartagena (prueba temporal)", [0.756, 0.784, 0.783])
fig, ax = plt.subplots(figsize=(6.4, 3.0))
p.plot.bar(ax=ax, rot=0, color=[GRIS, AZUL, NARANJA], width=0.75)
ax.set_ylim(0.6, 0.85); ax.set_ylabel("AUC"); ax.set_xlabel(""); ax.legend(frameon=False, fontsize=8, loc="upper left")
fig.tight_layout(); fig.savefig(OUT / "validacion_sedes.png"); plt.close(fig)

for f in ("riesgo_por_perfil", "modelo_final", "rejilla_khx", "shap_resumen"):
    shutil.copy(R / "figuras" / f"{f}.png", OUT / f"{f}.png")
print("ok", sorted(p.name for p in OUT.iterdir()))
