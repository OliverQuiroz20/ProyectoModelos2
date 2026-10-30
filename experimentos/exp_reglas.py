"""Simulacion descriptiva de reglas de retencion: "retener cuando una cuota llega a T dias de atraso".

Para cada umbral T se compara con lo que realmente paso (retiro por mal comportamiento dentro
de la ventana de prediccion, mas 30 dias de gracia para el registro de la carta) y con una
regla guiada por el modelo (revisar al p % de mayor riesgo en la semana k). Es un analisis
historico: no mide que habria pasado si la empresa hubiera retenido, y los retiros actuales,
que son discrecionales, ya cortan los atrasos observados.
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

warnings.filterwarnings("ignore")
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
import clasificacion as cl  # noqa: E402
from ciclos import CARTAS_RETIRO  # noqa: E402
from particion import corte_por_fraccion, dividir_temporal  # noqa: E402

K, H, X = 8, 12, 14
UMBRALES = [7, 14, 21, 28]
ep, ciclos, pagos, diario, CORTE = cl.cargar_base(RAIZ / "data" / "anon")
data = cl.construir_dataset(ep, ciclos, pagos, diario, CORTE, pd.Timestamp("2024-03-30"), K, H, X)
pob = ep.set_index("id_episodio").loc[data.id_episodio]
t_k = pob.fecha_inicio + pd.Timedelta(weeks=K)
t_h = pob.fecha_inicio + pd.Timedelta(weeks=K + H)

# Resultado real: retiro por mal comportamiento dentro de la ventana (+30 dias de gracia)
retiro = pd.to_datetime(pob.fecha_retiro)
malo = (pob.motivo_retiro.isin(CARTAS_RETIRO) & (retiro > t_k) & (retiro <= t_h + pd.Timedelta(days=30))).to_numpy()

# Atraso maximo de cada episodio en la ventana y fecha en que se alcanza cada umbral
c = ciclos[ciclos.id_episodio.isin(data.id_episodio)].merge(
    pd.DataFrame({"id_episodio": data.id_episodio, "t_k": t_k.to_numpy(), "t_h": t_h.to_numpy()}), on="id_episodio")
c = c[(c.fecha_esperada > c.t_k) & (c.fecha_esperada <= c.t_h)]
filas, flags = [], {}
te_mask = np.zeros(len(data), bool)
corte = corte_por_fraccion(data.fecha_inicio, 0.2)
i_dev, i_te = dividir_temporal(data.fecha_inicio, K, H, X, corte)
te_mask[i_te] = True
ids = data.id_episodio.to_numpy()
for T in UMBRALES:
    g = c[c.dias_atraso >= T].assign(disparo=lambda d: d.fecha_esperada + pd.Timedelta(days=T))
    primero = g.groupby("id_episodio").disparo.min().reindex(ids)
    flag = primero.notna().to_numpy()
    flags[T] = (flag, primero)

def resumen(nombre, flag, aviso, mask):
    f, m = flag[mask], malo[mask]
    tp = (f & m).sum()
    ant = (retiro.to_numpy()[mask] - aviso[mask])[f & m]
    return {"regla": nombre, "marcados %": 100 * f.mean(), "precision %": 100 * tp / max(f.sum(), 1),
            "cobertura %": 100 * tp / max(m.sum(), 1), "dias de anticipacion (mediana)": np.median(ant / np.timedelta64(1, "D")) if len(ant) else np.nan,
            "falsas alarmas %": 100 * (f & ~m).sum() / max(f.sum(), 1), "n": int(mask.sum()), "malos": int(m.sum())}

for T, (flag, primero) in flags.items():
    filas.append(resumen(f"atraso >= {T} dias", flag, primero.to_numpy(dtype="datetime64[ns]"), te_mask))

# Reglas guiadas por el modelo: revisar al p % de mayor riesgo en la semana k
cols = cl.NUM_BASE + cl.MARCAS + cl.CAT
dev, te = data.iloc[i_dev], data.iloc[i_te]
rf = RandomForestClassifier(n_estimators=300, max_depth=4, min_samples_leaf=5, max_features="sqrt",
                            class_weight="balanced", n_jobs=-1, random_state=0)
for nombre, clf in (("modelo (regresión logística)", LogisticRegression(C=0.5, max_iter=2000, class_weight="balanced")),
                    ("modelo (random forest)", rf)):
    m = cl.armar(clf, True, True, 0).fit(dev[cols], dev.y)
    p = np.full(len(data), np.nan); p[i_te] = m.predict_proba(te[cols])[:, 1]
    for frac in (0.1, 0.2, 0.3):
        flag = np.zeros(len(data), bool)
        orden = np.argsort(-np.nan_to_num(p, nan=-1))[: int(len(i_te) * frac)]
        flag[orden] = True
        filas.append(resumen(f"{nombre}: top {int(frac * 100)} %", flag, t_k.to_numpy(dtype="datetime64[ns]"), te_mask))

tab = pd.DataFrame(filas)
tab.to_csv(RAIZ / "reports" / "simulacion_reglas.csv", index=False)
print(tab.round(1).to_string(index=False))
print("tasa base de 'termina mal' en la prueba:", round(100 * malo[te_mask].mean(), 1), "%")
