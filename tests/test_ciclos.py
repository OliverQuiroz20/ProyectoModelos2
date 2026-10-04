"""Pruebas del calendario de pagos, la etiqueta y el corte temporal (datos sinteticos)."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ciclos import ciclos_episodio, pagos_por_dia  # noqa: E402
from variables import etiqueta, variables_entrada  # noqa: E402

CORTE = pd.Timestamp("2025-12-31")
INICIO = pd.Timestamp("2025-01-06")  # lunes; canon los martes -> primer vencimiento 2025-01-07


def episodio(fin=CORTE, cerrado=False):
    return pd.Series({
        "id_episodio": "E1", "id_contrato": "C1", "fecha_inicio": INICIO, "fin": fin,
        "tipopago": "SEMANAL", "dia_canon": "Mar", "dia_canon_num": 1, "cuota": 200.0,
        "no_canon": 60, "empresa": "MOTOHOY", "cerrado": cerrado,
    })


def abonos(fechas, abono=200.0, multa=0.0):
    return pd.DataFrame({
        "id_contrato": "C1", "fecha": pd.to_datetime(fechas), "abono": abono, "transf": 0.0,
        "multa": multa, "repuesto": 0.0, "carta": "NO", "cartamotivo": None,
    })


def ciclos(ep, fechas_pago, **kw):
    return ciclos_episodio(ep, pagos_por_dia(abonos(fechas_pago, **kw)), CORTE)


def test_pago_el_dia_del_canon_no_tiene_atraso():
    ep = episodio(fin=pd.Timestamp("2025-01-28"))
    c = ciclos(ep, ["2025-01-07", "2025-01-14", "2025-01-21", "2025-01-28"])
    assert c.dias_atraso.tolist() == [0, 0, 0, 0]


def test_pago_dos_dias_despues_cuenta_dos_dias_de_atraso():
    ep = episodio(fin=pd.Timestamp("2025-01-14"))
    c = ciclos(ep, ["2025-01-09", "2025-01-16"])
    assert c.dias_atraso.tolist() == [2, 2]


def test_atraso_no_se_reinicia_con_la_semana():
    # Paga 8 dias tarde: el modulo 7 lo veria como 1 dia, el calendario lo ve como 8
    ep = episodio(fin=pd.Timestamp("2025-01-07"))
    c = ciclos(ep, ["2025-01-15"])
    assert c.dias_atraso.tolist() == [8]


def test_pago_doble_cubre_dos_ciclos():
    # No paga la primera semana y en la segunda paga dos cuotas juntas
    ep = episodio(fin=pd.Timestamp("2025-01-14"))
    c = ciclos(ep, ["2025-01-14"], abono=400.0)
    assert c.dias_atraso.tolist() == [7, 0]


def test_cualquier_dinero_cuenta_como_pago():
    # Todo el dinero va a multa: para la empresa el cliente si pago
    ep = episodio(fin=pd.Timestamp("2025-01-07"))
    c = ciclos(ep, ["2025-01-07"], abono=0.0, multa=15.0)
    assert c.pagado.tolist() == [True]


def test_ciclo_sin_pago_queda_censurado_al_fin_del_episodio():
    ep = episodio(fin=pd.Timestamp("2025-01-20"))
    c = ciclos(ep, ["2025-01-07"])
    assert c.pagado.tolist() == [True, False]
    assert c.dias_atraso.tolist() == [0, 6]


def _poblacion_y_ciclos(fechas_pago, fin=CORTE, cerrado=False):
    ep = episodio(fin=fin, cerrado=cerrado)
    pob = ep.to_frame().T.astype({"fecha_inicio": "datetime64[ns]", "fin": "datetime64[ns]", "cuota": float})
    return pob, ciclos(ep, fechas_pago)


def test_etiqueta_1_si_un_ciclo_del_horizonte_llega_a_x_dias():
    pagos = pd.date_range("2025-01-07", periods=8, freq="7D").tolist()  # semanas 1-8 al dia
    pagos += [pd.Timestamp("2025-03-20")]  # el ciclo del 2025-03-04 se paga 16 dias tarde
    pob, c = _poblacion_y_ciclos(pagos, fin=pd.Timestamp("2025-03-04"))
    assert etiqueta(pob, c, k=8, h=12, x=14).iat[0] == 1


def test_etiqueta_1_si_la_cuota_nunca_se_pago_y_el_episodio_se_cerro():
    pagos = pd.date_range("2025-01-07", periods=8, freq="7D").tolist()
    # Se le quita la moto 5 dias despues de la cuota que no pago: nunca llega a 14 dias
    pob, c = _poblacion_y_ciclos(pagos, fin=pd.Timestamp("2025-03-09"), cerrado=True)
    assert etiqueta(pob, c, k=8, h=12, x=14).iat[0] == 1


def test_etiqueta_0_si_paga_al_dia_todo_el_horizonte():
    pagos = pd.date_range("2025-01-07", periods=20, freq="7D").tolist()
    pob, c = _poblacion_y_ciclos(pagos, fin=pd.Timestamp("2025-05-20"))
    assert etiqueta(pob, c, k=8, h=12, x=14).iat[0] == 0


@pytest.mark.parametrize("cambio_posterior", ["sin_pagos", "pagos_tardios"])
def test_variables_de_entrada_no_ven_informacion_posterior_a_k(cambio_posterior):
    """Cambiar todo lo que pasa despues de la semana k no debe mover ninguna variable."""
    k = 8
    t_k = INICIO + pd.Timedelta(weeks=k)
    antes = pd.date_range("2025-01-07", t_k, freq="7D").tolist()
    # El ciclo que vence justo antes de t_k se paga despues de t_k en un escenario
    despues = {"sin_pagos": [], "pagos_tardios": [t_k + pd.Timedelta(days=3)]}
    diario = pd.DataFrame({"id_contrato": ["C1"], "fecha_registro": [INICIO], "justificacion": [None]})
    resultados = []
    for extra in ([pd.Timestamp("2025-04-01"), pd.Timestamp("2025-05-01")], despues[cambio_posterior]):
        fechas = antes[:-1] + extra
        pob, c = _poblacion_y_ciclos(fechas)
        pagos = pagos_por_dia(abonos(fechas))
        resultados.append(variables_entrada(pob, c, pagos, diario, k))
    pd.testing.assert_frame_equal(resultados[0], resultados[1])
