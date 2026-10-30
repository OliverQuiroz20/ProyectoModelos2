"""Ranking de gestion: clientes activos con 8 a 20 semanas de antiguedad, ordenados por riesgo.

Usa el mismo modelo del Entregable II (K=8, H=12, X=14), entrenado con todos los episodios de
Cartagena con desenlace conocido. La salida contiene numeros de contrato REALES, por eso se
guarda en data/gestion/ (fuera de git).
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression

warnings.filterwarnings("ignore")
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
import clasificacion as cl  # noqa: E402
from variables import variables_entrada  # noqa: E402

K, H, X = 8, 12, 14
INICIO_COHORTE = pd.Timestamp("2024-03-30")
ep, ciclos, pagos, diario, corte = cl.cargar_base(RAIZ / "data" / "anon_hoy")
hoy = diario.fecha_registro.max()

# 1. Entrenamiento con todo lo etiquetado
data = cl.construir_dataset(ep, ciclos, pagos, diario, corte, INICIO_COHORTE, K, H, X)
cols = cl.NUM_BASE + cl.MARCAS + cl.CAT
lr = LogisticRegression(C=0.5, max_iter=2000, class_weight="balanced")
rf = RandomForestClassifier(n_estimators=300, max_depth=4, min_samples_leaf=5, max_features="sqrt",
                            class_weight="balanced", n_jobs=-1, random_state=0)
gb = GradientBoostingClassifier(n_estimators=100, max_depth=2, learning_rate=0.02, subsample=0.8, random_state=0)
modelo = cl.armar(VotingClassifier([("lr", lr), ("rf", rf), ("gb", gb)], voting="soft"), True, True, 0)
modelo.fit(data[cols], data.y)
print("entrenado con", len(data), "episodios (", round(100 * data.y.mean(), 1), "% positivos )")

# 2. Activos en el rango del modelo
act = ep[ep.ultimo_registro >= hoy].copy()
act["semanas"] = (hoy - act.fecha_inicio).dt.days / 7
act["cerrado"] = False
act = act[(act.semanas >= K) & (act.semanas <= K + H) & (act.fecha_inicio >= INICIO_COHORTE)
          & ~((act.tipopago == "SEMANAL") & act.dia_canon_num.isna())].reset_index(drop=True)
X_act = variables_entrada(act, ciclos, pagos, diario, K).replace([np.inf, -np.inf], np.nan)
p = modelo.predict_proba(X_act[cols])[:, 1]

# 3. Contexto actual (no entra al modelo): cuotas sin pagar y ultimo pago a hoy
c = ciclos[ciclos.id_episodio.isin(act.id_episodio) & (ciclos.fecha_esperada <= corte)]
sin_pagar = c[~c.pagado].groupby("id_episodio").size()
atraso_actual = c[~c.pagado].assign(d=lambda d: (corte - d.fecha_esperada).dt.days).groupby("id_episodio").d.max()
ult_pago = pagos.merge(act[["id_episodio", "id_contrato"]], on="id_contrato").groupby("id_episodio").fecha.max()

out = pd.DataFrame({
    "id_contrato": act.id_contrato, "semanas_desde_inicio": act.semanas.round(1), "pago": act.tipopago,
    "empresa": act.empresa, "cuota": act.cuota, "puntaje_riesgo": p.round(3),
    "cuotas_sin_pagar_hoy": act.id_episodio.map(sin_pagar).fillna(0).astype(int),
    "dias_atraso_hoy": act.id_episodio.map(atraso_actual).fillna(0).astype(int),
    "dias_desde_ultimo_pago": (corte - act.id_episodio.map(ult_pago)).dt.days,
})
# Estado operativo de hoy (solo SELECT): realquiler, oficina (moto retirada), fiscalia (meses) y triage no se gestionan
from explorar_bd import q  # noqa: E402
est = q("SELECT contrato, estado FROM reporte_estado_motos WHERE tipo_estado = 'SEMANAL' "
        "AND fecha = (SELECT MAX(fecha) FROM reporte_estado_motos)")
mapa = pd.read_csv(RAIZ / "data" / "raw" / "mapa_contratos.csv", dtype=str).set_index("id_contrato").contrato
out["contrato"] = out.id_contrato.map(mapa)
out["estado_operativo"] = out.contrato.map(est.assign(contrato=est.contrato.astype(str)).set_index("contrato").estado).fillna("normal")
fuera = out.estado_operativo.str.contains("ealquil|Oficina|Fiscalia|triage|eocerca|arad")
out["fuera_de_gestion"] = fuera
out["posicion"] = np.nan
out.loc[~fuera, "posicion"] = out.loc[~fuera, "puntaje_riesgo"].rank(ascending=False, method="first")
n_gest = int((~fuera).sum())
frac = out.posicion / n_gest
out["prioridad"] = np.where(frac <= 0.10, "1 - Alta (top 10 %)", np.where(frac <= 0.20, "2 - Media-alta (10-20 %)",
                   np.where(frac <= 0.30, "3 - Media (20-30 %)", "4 - Baja")))
out.loc[fuera, "prioridad"] = "0 - Fuera de gestion (realquiler/oficina/fiscalia/triage/geocerca/varadas)"
out = out.sort_values(["fuera_de_gestion", "posicion"])

# 4. Numero de contrato real (mapa local, nunca se comparte)
out = out.drop(columns="id_contrato")
out.insert(0, "contrato", out.pop("contrato"))
salida = RAIZ / "data" / "gestion"
salida.mkdir(parents=True, exist_ok=True)
out.to_csv(salida / f"ranking_gestion_{hoy.date()}.csv", index=False, encoding="utf-8-sig")
print(len(out), "clientes puntuados |", out.prioridad.value_counts().sort_index().to_dict())
print(out.head(12).drop(columns="empresa").to_string(index=False))
print("\nPuntaje de riesgo: min", out.puntaje_riesgo.min(), "mediana", out.puntaje_riesgo.median(), "max", out.puntaje_riesgo.max())
