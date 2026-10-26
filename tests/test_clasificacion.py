"""El preprocesamiento de la etapa 2 se ajusta solo con entrenamiento (datos sinteticos)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from clasificacion import CAT, MARCAS, NUM_BASE, Preprocesador  # noqa: E402


def _datos(n, desplazamiento, semilla):
    rng = np.random.default_rng(semilla)
    d = pd.DataFrame(rng.gamma(2.0, 1.0, (n, len(NUM_BASE + MARCAS))) + desplazamiento, columns=NUM_BASE + MARCAS)
    d["tipopago"], d["empresa"], d["dia_canon"] = "SEMANAL", "A", "LUN"
    return d


def test_transformar_prueba_no_reajusta_el_preprocesador():
    train, test = _datos(300, 0.0, 1), _datos(100, 50.0, 2)  # la prueba es muy distinta
    pre = Preprocesador(con_perfil=True).fit(train)
    medias = pre.pipe_num_.named_steps["esc"].mean_.copy()
    centros = pre.perfil_.km_.cluster_centers_.copy()
    pre.transform(test)
    assert np.allclose(pre.pipe_num_.named_steps["esc"].mean_, medias)
    assert np.allclose(pre.perfil_.km_.cluster_centers_, centros)


def test_el_ajuste_solo_depende_del_entrenamiento():
    train = _datos(300, 0.0, 1)
    a = Preprocesador(con_perfil=True).fit(train)
    b = Preprocesador(con_perfil=True).fit(train)
    prueba = _datos(80, 5.0, 3)
    assert np.allclose(a.transform(prueba), b.transform(prueba))
