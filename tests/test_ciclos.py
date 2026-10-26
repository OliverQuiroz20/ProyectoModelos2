"""Pruebas del calendario de pagos, la etiqueta y el corte temporal (datos sinteticos)."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ciclos import ciclos_episodio, pagos_por_dia  # noqa: E402
from variables import _cierre_ambiguo, etiqueta, variables_entrada  # noqa: E402

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


def _poblacion_y_ciclos(fechas_pago, fin=CORTE, cerrado=False, motivo_retiro=None):
    ep = episodio(fin=fin, cerrado=cerrado)
    pob = ep.to_frame().T.astype({"fecha_inicio": "datetime64[ns]", "fin": "datetime64[ns]", "cuota": float})
    pob["motivo_retiro"] = motivo_retiro
    return pob, ciclos(ep, fechas_pago)


def test_etiqueta_1_si_un_ciclo_del_horizonte_llega_a_x_dias():
    pagos = pd.date_range("2025-01-07", periods=8, freq="7D").tolist()  # semanas 1-8 al dia
    pagos += [pd.Timestamp("2025-03-20")]  # el ciclo del 2025-03-04 se paga 16 dias tarde
    pob, c = _poblacion_y_ciclos(pagos, fin=pd.Timestamp("2025-03-04"))
    assert etiqueta(pob, c, k=8, h=12, x=14).iat[0] == 1


def test_etiqueta_1_si_la_cuota_no_se_pago_y_cierra_con_carta_de_retiro():
    pagos = pd.date_range("2025-01-07", periods=8, freq="7D").tolist()
    # Se le quita la moto 5 dias despues de la cuota que no pago: nunca llega a 14 dias
    pob, c = _poblacion_y_ciclos(pagos, fin=pd.Timestamp("2025-03-09"), cerrado=True,
                                 motivo_retiro="CARTA REGRESO DIARIO")
    assert etiqueta(pob, c, k=8, h=12, x=14).iat[0] == 1
    assert len(_cierre_ambiguo(pob, c, k=8, h=12, x=14)) == 0


def test_cierre_sin_carta_y_con_atraso_menor_a_x_es_ambiguo_no_positivo():
    pagos = pd.date_range("2025-01-07", periods=8, freq="7D").tolist()
    pob, c = _poblacion_y_ciclos(pagos, fin=pd.Timestamp("2025-03-09"), cerrado=True)
    assert etiqueta(pob, c, k=8, h=12, x=14).iat[0] == 0
    assert list(_cierre_ambiguo(pob, c, k=8, h=12, x=14)) == list(pob.id_episodio)


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


# --- Particion temporal ---------------------------------------------------

from particion import dividir_temporal, fecha_resolucion, pliegues_expansivos  # noqa: E402


def _fechas(n=200):
    return pd.Series(pd.date_range("2024-04-01", periods=n, freq="5D"))


def test_la_prueba_es_mas_reciente_que_el_entrenamiento():
    f = _fechas()
    corte = f.quantile(0.8)
    tr, te = dividir_temporal(f, k=8, h=12, x=14, fecha_corte=corte)
    assert f.iloc[tr].max() < f.iloc[te].min()


def test_entrenamiento_no_usa_etiquetas_que_se_resuelven_despues_del_corte():
    f = _fechas()
    corte = f.quantile(0.8)
    tr, _ = dividir_temporal(f, k=8, h=12, x=14, fecha_corte=corte)
    assert (fecha_resolucion(f.iloc[tr], 8, 12, 14) <= corte).all()
    # Hay una purga real: no todo lo anterior al corte entra a entrenamiento
    assert len(tr) < (f < corte).sum()


def test_pliegues_expansivos_respetan_el_orden_y_no_tocan_la_prueba_final():
    f = _fechas()
    corte = f.quantile(0.8)
    for tr, va in pliegues_expansivos(f, 8, 12, 14, n_splits=4, fecha_max=corte):
        assert f.iloc[tr].max() < f.iloc[va].min()
        assert (fecha_resolucion(f.iloc[tr], 8, 12, 14) <= f.iloc[va].min()).all()
        assert (f.iloc[va] < corte).all()


# --- Variables de gestion y justificaciones ---------------------------------

from variables import variables_gestion  # noqa: E402


def test_variables_de_gestion_no_ven_eventos_posteriores_a_k():
    k = 8
    t_k = INICIO + pd.Timedelta(weeks=k)
    pob, _ = _poblacion_y_ciclos(pd.date_range("2025-01-07", t_k, freq="7D").tolist())
    just_antes = pd.DataFrame({"id_contrato": ["C1"], "fecha": [INICIO + pd.Timedelta(days=10)],
                               "justificacion": ["Multa"], "estado": ["APROBADO"], "concepto": ["NOPAGO"]})
    gest_antes = pd.DataFrame({"id_contrato": ["C1"], "fecha": [INICIO + pd.Timedelta(days=12)], "concepto": ["SINCOMUNICACION"]})
    # Eventos extra DESPUES de t_k (y uno antes de la fecha de inicio): no deben cambiar nada
    just_despues = pd.concat([just_antes, just_antes.assign(fecha=t_k + pd.Timedelta(days=1)),
                              just_antes.assign(fecha=INICIO - pd.Timedelta(days=5))], ignore_index=True)
    gest_despues = pd.concat([gest_antes, gest_antes.assign(fecha=t_k + pd.Timedelta(days=2), concepto="PAGONEGRO")], ignore_index=True)
    a = variables_gestion(pob, just_antes, gest_antes, k)
    b = variables_gestion(pob, just_despues, gest_despues, k)
    pd.testing.assert_frame_equal(a, b)
    assert a.loc["E1", "just_multa"] == 1 and a.loc["E1", "gest_sin_comunicacion"] == 1
