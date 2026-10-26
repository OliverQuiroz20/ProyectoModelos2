"""Particion temporal con purga para evaluar el modelo como se usaria en la practica.

Los episodios se ordenan por `fecha_inicio`: los mas antiguos entrenan y los mas
recientes prueban. Como la etiqueta de un episodio solo se conoce `k + h` semanas (mas
`x` dias) despues de su inicio, un episodio de entrenamiento cuya etiqueta se resuelve
despues del inicio de la prueba usaria informacion del futuro; se purga.
"""

import numpy as np
import pandas as pd


def fecha_resolucion(fecha_inicio, k, h, x):
    """Fecha desde la cual la etiqueta del episodio es conocida (cota conservadora)."""
    return pd.to_datetime(fecha_inicio) + pd.Timedelta(weeks=k + h) + pd.Timedelta(days=x)


def corte_por_fraccion(fecha_inicio, frac_prueba=0.2):
    """Fecha de inicio a partir de la cual cae la fraccion mas reciente de episodios."""
    return pd.to_datetime(fecha_inicio).quantile(1 - frac_prueba)


def dividir_temporal(fecha_inicio, k, h, x, fecha_corte):
    """Devuelve (idx_train, idx_test) como posiciones sobre `fecha_inicio`.

    Prueba: episodios que inician en `fecha_corte` o despues. Entrenamiento: los que
    inician antes y cuya etiqueta ya se conocia en `fecha_corte` (purga).
    """
    f = pd.to_datetime(pd.Series(np.asarray(fecha_inicio)))
    prueba = f >= fecha_corte
    train = (~prueba) & (fecha_resolucion(f, k, h, x) <= fecha_corte)
    return np.flatnonzero(train.to_numpy()), np.flatnonzero(prueba.to_numpy())


def pliegues_expansivos(fecha_inicio, k, h, x, n_splits=4, fecha_max=None, q_inicial=0.3):
    """Validacion de ventana expansiva: el pliegue i entrena con lo anterior a un corte
    y valida en el tramo siguiente. Los cortes son cuantiles de `fecha_inicio`
    (anteriores a `fecha_max`, si se da, para no tocar el conjunto de prueba final). El
    primer corte parte del cuantil `q_inicial` porque, por la purga, los episodios mas
    antiguos no alcanzan a tener etiqueta conocida y el primer entrenamiento quedaria vacio.
    """
    f = pd.to_datetime(pd.Series(np.asarray(fecha_inicio)))
    base = f if fecha_max is None else f[f < fecha_max]
    cortes = [base.quantile(q) for q in np.linspace(q_inicial, 1, n_splits + 1)]
    pliegues = []
    for ini, fin in zip(cortes[:-1], cortes[1:]):
        train, _ = dividir_temporal(f, k, h, x, ini)
        val = np.flatnonzero(((f >= ini) & (f < fin)).to_numpy())
        if fin == cortes[-1]:  # el ultimo tramo incluye el borde superior
            val = np.flatnonzero(((f >= ini) & (f <= fin)).to_numpy())
        train = train[f.iloc[train] < ini]
        pliegues.append((train, val))
    return pliegues
