"""Etapa 1 (perfiles de pago) y utilidades de modelado sin fuga de informacion.

Todo transformador se ajusta (`fit`) solo con entrenamiento; en prueba solo se usa
`transform`/`predict`.
"""

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

# Variables de comportamiento con las que se arman los perfiles (sin las redundantes
# del EDA: atraso_maximo~atraso_promedio y dias_con_pago~pagos_por_ciclo)
COLS_PERFIL = [
    "prop_ciclos_atrasados", "prop_ciclos_atraso_3mas", "atraso_promedio",
    "ciclos_sin_pagar_k", "pagos_por_ciclo", "deficit_relativo", "multa_acumulada",
    "prop_pagos_con_multa", "cv_pago_canon", "dias_hasta_primer_pago",
]


def _log_con_signo(x):
    """log1p que conserva el signo (deficit_relativo puede ser negativo si pago de mas)."""
    return np.sign(x) * np.log1p(np.abs(x))


def preparar_perfil(cols=COLS_PERFIL):
    """Imputacion por mediana + log1p con signo + estandarizacion (todo ajustado en train)."""
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import FunctionTransformer
    return Pipeline([
        ("imp", SimpleImputer(strategy="median")),
        ("log", FunctionTransformer(_log_con_signo, validate=False)),
        ("esc", StandardScaler()),
    ])


class Perfil(BaseEstimator, TransformerMixin):
    """Asigna cada episodio a un perfil de pago con k-means ajustado solo en `fit`."""

    def __init__(self, k=4, cols=None, seed=0):
        self.k, self.cols, self.seed = k, cols, seed

    def fit(self, X, y=None):
        self.cols_ = list(self.cols or COLS_PERFIL)
        self.prep_ = preparar_perfil(self.cols_)
        Z = self.prep_.fit_transform(X[self.cols_])
        self.km_ = KMeans(self.k, n_init=20, random_state=self.seed).fit(Z)
        # Se ordenan los perfiles por atraso promedio (en train) para que el numero
        # sea comparable entre ajustes: 0 = el mas puntual
        orden = np.argsort(self.km_.cluster_centers_[:, self.cols_.index("atraso_promedio")])
        self.mapa_ = {int(v): i for i, v in enumerate(orden)}
        return self

    def predict(self, X):
        Z = self.prep_.transform(X[self.cols_])
        return np.array([self.mapa_[int(c)] for c in self.km_.predict(Z)])

    def transform(self, X):
        p = self.predict(X)
        return np.eye(self.k)[p]
