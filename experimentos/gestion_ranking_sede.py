"""Ranking de gestion para otra sede: entrena con Cartagena (anon_hoy) y puntua los activos de la sede.
Uso: python experimentos/gestion_ranking_sede.py monteria"""
import os, sys, warnings
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression

warnings.filterwarnings("ignore")
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src")); sys.path.insert(0, str(RAIZ / "experimentos"))
sede = sys.argv[1]
os.environ["DB_HOST"] = {"sincelejo": "server-motosince.netbird.cloud", "monteria": "server-motomonteria.netbird.cloud"}[sede]
import clasificacion as cl  # noqa: E402
from variables import variables_entrada  # noqa: E402
from explorar_bd import q  # noqa: E402

K, H, X = 8, 12, 14
INI = pd.Timestamp("2024-03-30")
cols = cl.NUM_BASE + cl.MARCAS + cl.CAT
ep, ciclos, pagos, diario, corte = cl.cargar_base(RAIZ / "data" / "anon_hoy")
data = cl.construir_dataset(ep, ciclos, pagos, diario, corte, INI, K, H, X)
lr = LogisticRegression(C=0.5, max_iter=2000, class_weight="balanced")
rf = RandomForestClassifier(n_estimators=300, max_depth=4, min_samples_leaf=5, max_features="sqrt",
                            class_weight="balanced", n_jobs=-1, random_state=0)
gb = GradientBoostingClassifier(n_estimators=100, max_depth=2, learning_rate=0.02, subsample=0.8, random_state=0)
modelo = cl.armar(VotingClassifier([("lr", lr), ("rf", rf), ("gb", gb)], voting="soft"), True, True, 0)
modelo.fit(data[cols], data.y)

ep, ciclos, pagos, diario, corte = cl.cargar_base(RAIZ / "data" / "anon" / f"{sede}_hoy")
hoy = diario.fecha_registro.max()
act = ep[ep.ultimo_registro >= hoy].copy()
act["semanas"] = (hoy - act.fecha_inicio).dt.days / 7
print("activos:", len(act), "| por antiguedad:", pd.cut(act.semanas, [-1, 8, 20, 1000]).value_counts().sort_index().to_dict())
act["cerrado"] = False
act = act[(act.semanas >= K) & (act.semanas <= K + H) & (act.fecha_inicio >= INI)
          & ~((act.tipopago == "SEMANAL") & act.dia_canon_num.isna())].reset_index(drop=True)
Xa = variables_entrada(act, ciclos, pagos, diario, K).replace([np.inf, -np.inf], np.nan)
p = modelo.predict_proba(Xa[cols])[:, 1]
c = ciclos[ciclos.id_episodio.isin(act.id_episodio) & (ciclos.fecha_esperada <= corte)]
sin_pagar = c[~c.pagado].groupby("id_episodio").size()
atraso = c[~c.pagado].assign(d=lambda d: (corte - d.fecha_esperada).dt.days).groupby("id_episodio").d.max()
ult = pagos.merge(act[["id_episodio", "id_contrato"]], on="id_contrato").groupby("id_episodio").fecha.max()
out = pd.DataFrame({"id_contrato": act.id_contrato, "semanas_desde_inicio": act.semanas.round(1), "pago": act.tipopago,
                    "cuota": act.cuota, "puntaje_riesgo": p.round(3),
                    "cuotas_sin_pagar_hoy": act.id_episodio.map(sin_pagar).fillna(0).astype(int),
                    "dias_atraso_hoy": act.id_episodio.map(atraso).fillna(0).astype(int),
                    "dias_desde_ultimo_pago": (corte - act.id_episodio.map(ult)).dt.days})
mapa = pd.read_csv(RAIZ / "data" / "raw" / f"mapa_{sede}.csv", dtype=str).set_index("id_contrato").contrato
out["contrato"] = out.id_contrato.map(mapa)
est = q("SELECT contrato, estado FROM reporte_estado_motos WHERE tipo_estado = 'SEMANAL' "
        "AND fecha = (SELECT MAX(fecha) FROM reporte_estado_motos)")
out["estado_operativo"] = out.contrato.map(est.assign(contrato=est.contrato.astype(str)).set_index("contrato").estado).fillna("normal")
fuera = out.estado_operativo.str.contains("ealquil|Oficina|Fiscalia|triage|eocerca|arad")
out["fuera_de_gestion"] = fuera
out["posicion"] = np.nan
out.loc[~fuera, "posicion"] = out.loc[~fuera, "puntaje_riesgo"].rank(ascending=False, method="first")
frac = out.posicion / int((~fuera).sum())
out["prioridad"] = np.where(frac <= 0.10, "1 - Alta (top 10 %)", np.where(frac <= 0.20, "2 - Media-alta (10-20 %)",
                   np.where(frac <= 0.30, "3 - Media (20-30 %)", "4 - Baja")))
out.loc[fuera, "prioridad"] = "0 - Fuera de gestion"
out = out.drop(columns="id_contrato").sort_values(["fuera_de_gestion", "posicion"])
out.to_csv(RAIZ / "data" / "gestion" / f"ranking_gestion_{sede}_{hoy.date()}.csv", index=False, encoding="utf-8-sig")
print(len(out), "puntuados |", out.prioridad.value_counts().sort_index().to_dict())
print(out.estado_operativo.value_counts().to_dict())
print(out[out.prioridad.str[0] == "1"].drop(columns=["fuera_de_gestion", "prioridad"]).to_string(index=False))
