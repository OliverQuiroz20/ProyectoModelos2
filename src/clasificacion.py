"""Etapa 2 (clasificacion) con validacion temporal y sin fuga de informacion.

El preprocesamiento (imputacion, escalado, codificacion y, si se pide, el perfil de
la etapa 1) vive dentro del `Pipeline`: se ajusta de nuevo en cada pliegue con los
datos de entrenamiento y solo transforma los de validacion/prueba.
"""

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin, clone
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score, matthews_corrcoef, roc_auc_score
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

from modelado import Perfil, _log_con_signo
from particion import corte_por_fraccion, dividir_temporal, pliegues_expansivos
from variables import asignar_retiro, etiqueta, marcar_poblacion, variables_entrada

CAT = ["tipopago", "empresa", "dia_canon"]
MARCAS = ["retencion_temporal", "cliente_problema"]  # marcas de gestion de la empresa
NUM_BASE = [
    "ciclos_esperados", "prop_ciclos_atrasados", "prop_ciclos_atraso_3mas", "atraso_promedio",
    "ciclos_sin_pagar_k", "dias_hasta_primer_pago", "pago_canon_total", "cv_pago_canon",
    "multa_acumulada", "prop_pagos_con_multa", "repuesto_acumulado", "pagos_por_ciclo",
    "deficit_relativo", "justif_enfermedad", "justif_inmovilizacion", "cuota", "no_canon",
]


def construir_dataset(ep_base, ciclos, pagos, diario, corte, inicio_cohorte, k, h, x):
    """Variables (primeras k semanas), etiqueta y fecha de inicio para un (k, h, x)."""
    ep = marcar_poblacion(ep_base, ciclos, k, h, x, corte, inicio_cohorte)
    pob = ep[ep.motivo_exclusion.isna()].reset_index(drop=True)
    Xv = variables_entrada(pob, ciclos, pagos, diario, k)
    y = etiqueta(pob, ciclos, k, h, x)
    out = Xv.join(y).join(pob.set_index("id_episodio").fecha_inicio)
    out["fecha_inicio"] = pd.to_datetime(out.fecha_inicio)
    return out.replace([np.inf, -np.inf], np.nan).reset_index(names="id_episodio")


class Preprocesador(BaseEstimator, TransformerMixin):
    """Imputa (mediana + indicador), aplica log con signo, estandariza, codifica las
    categoricas y, opcionalmente, agrega el perfil de pago (etapa 1) en one-hot."""

    def __init__(self, con_perfil=False, con_marcas=True, k_perfil=4, seed=0):
        self.con_perfil, self.con_marcas, self.k_perfil, self.seed = con_perfil, con_marcas, k_perfil, seed

    def fit(self, X, y=None):
        self.num_ = NUM_BASE + (MARCAS if self.con_marcas else [])
        self.pipe_num_ = Pipeline([
            ("imp", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
            ("log", FunctionTransformer(_log_con_signo, validate=False)),
            ("esc", StandardScaler()),
        ]).fit(X[self.num_])
        self.ohe_ = OneHotEncoder(handle_unknown="ignore", sparse_output=False).fit(X[CAT])
        self.perfil_ = Perfil(self.k_perfil, seed=self.seed).fit(X) if self.con_perfil else None
        return self

    def transform(self, X):
        partes = [self.pipe_num_.transform(X[self.num_]), self.ohe_.transform(X[CAT])]
        if self.perfil_ is not None:
            partes.append(self.perfil_.transform(X))
        return np.hstack(partes)

    def get_feature_names_out(self, input_features=None):
        nombres = list(self.pipe_num_.named_steps["imp"].get_feature_names_out(self.num_))
        nombres += list(self.ohe_.get_feature_names_out(CAT))
        if self.perfil_ is not None:
            nombres += [f"perfil_{i}" for i in range(self.k_perfil)]
        return np.array(nombres)


def modelos(seed=0, peso_clases=True):
    """Modelos del curso. `peso_clases` aplica ponderacion de clases cuando el modelo la admite."""
    cw = "balanced" if peso_clases else None
    return {
        "Regresión logística": LogisticRegression(C=0.5, max_iter=2000, class_weight=cw),
        "KNN": KNeighborsClassifier(n_neighbors=25, weights="distance"),
        "Árbol de decisión": DecisionTreeClassifier(max_depth=5, min_samples_leaf=30, class_weight=cw, random_state=seed),
        "Random Forest": RandomForestClassifier(n_estimators=300, min_samples_leaf=10, class_weight=cw,
                                                n_jobs=-1, random_state=seed),
        "Gradient Boosting": GradientBoostingClassifier(n_estimators=150, max_depth=2, learning_rate=0.05,
                                                        subsample=0.8, random_state=seed),
        "SVM (RBF)": SVC(C=1.0, kernel="rbf", probability=True, class_weight=cw, random_state=seed),
    }


def armar(clasificador, con_perfil=False, con_marcas=True, seed=0):
    return Pipeline([("pre", Preprocesador(con_perfil, con_marcas, seed=seed)), ("clf", clone(clasificador))])


def metricas(y, p, umbral):
    """AUC-ROC (independiente del umbral) y metricas de clasificacion con el umbral dado."""
    y = np.asarray(y)
    pred = (np.asarray(p) >= umbral).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    sens, esp = tp / max(tp + fn, 1), tn / max(tn + fp, 1)
    return {
        "AUC": roc_auc_score(y, p) if len(np.unique(y)) > 1 else np.nan,
        "F1 (clase 0)": f1_score(y, pred, pos_label=0, zero_division=0),
        "F1 (clase 1)": f1_score(y, pred, pos_label=1, zero_division=0),
        "BACC": (sens + esp) / 2,
        "G-mean": float(np.sqrt(sens * esp)),
        "MCC": matthews_corrcoef(y, pred),
        "exactitud": (tp + tn) / len(y),
    }


def umbral_gmean(y, p):
    """Umbral que maximiza la G-mean; se elige con predicciones fuera de muestra del desarrollo."""
    cand = np.unique(np.quantile(p, np.linspace(0.05, 0.95, 91)))
    gm = [np.sqrt(((p >= u)[y == 1]).mean() * ((p < u)[y == 0]).mean()) for u in cand]
    return float(cand[int(np.argmax(gm))])


def evaluar(modelo, data, columnas, k, h, x, frac_prueba=0.2, n_splits=4, semilla=0):
    """Validacion temporal de un pipeline `modelo` sobre `data` (salida de `construir_dataset`).

    1. Desarrollo = episodios que inician antes del corte (con purga) y prueba = el resto.
    2. En desarrollo se validan pliegues de ventana expansiva (el modelo se reajusta en cada uno).
    3. El umbral se elige con las predicciones de validacion y se aplica a la prueba, que se
       usa una sola vez con el modelo ajustado a todo el desarrollo.
    Devuelve metricas de validacion (media y desviacion por pliegue) y de prueba.
    """
    corte = corte_por_fraccion(data.fecha_inicio, frac_prueba)
    i_dev, i_te = dividir_temporal(data.fecha_inicio, k, h, x, corte)
    dev, te = data.iloc[i_dev], data.iloc[i_te]
    X_all, y_all = data[columnas], data.y.to_numpy()

    oof_p, oof_y, por_pliegue = [], [], []
    for tr, va in pliegues_expansivos(data.fecha_inicio, k, h, x, n_splits, fecha_max=corte):
        if len(tr) < 100 or len(np.unique(y_all[tr])) < 2 or len(np.unique(y_all[va])) < 2:
            continue
        m = clone(modelo).fit(X_all.iloc[tr], y_all[tr])
        p = m.predict_proba(X_all.iloc[va])[:, 1]
        oof_p.append(p); oof_y.append(y_all[va])
        por_pliegue.append(roc_auc_score(y_all[va], p))
    oof_p, oof_y = np.concatenate(oof_p), np.concatenate(oof_y)
    u = umbral_gmean(oof_y, oof_p)

    m = clone(modelo).fit(dev[columnas], dev.y)
    p_te = m.predict_proba(te[columnas])[:, 1]
    return {
        "umbral": u,
        "auc_validacion": float(np.mean(por_pliegue)), "auc_validacion_sd": float(np.std(por_pliegue)),
        "validacion": metricas(oof_y, oof_p, u), "prueba": metricas(te.y, p_te, u),
        "n_dev": len(dev), "n_prueba": len(te), "pos_dev": float(dev.y.mean()), "pos_prueba": float(te.y.mean()),
        "p_prueba": p_te, "y_prueba": te.y.to_numpy(),
    }


def cargar_base(dir_datos):
    """Lee la copia anonimizada y arma episodios, ciclos y pagos (independientes de k, h, x)."""
    from pathlib import Path
    from ciclos import construir_ciclos, construir_episodios, pagos_por_dia, retiros
    d = Path(dir_datos)
    abonos = pd.read_csv(d / "abonos.csv.gz", parse_dates=["fecha"])
    diario = pd.read_csv(d / "motos_diario.csv.gz", parse_dates=["fecha_registro"], dtype={"justificacion": str})
    corte = abonos.fecha.max()
    pagos = pagos_por_dia(abonos)
    ep = construir_episodios(diario)
    ciclos = construir_ciclos(ep, pagos, corte)
    ep = asignar_retiro(ep, retiros(abonos))
    return ep, ciclos, pagos, diario, corte
