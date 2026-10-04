"""Poblacion, etiqueta y variables de entrada con corte temporal explicito.

Para cada episodio, t_k = fecha_inicio + k semanas es el momento de la prediccion:

- Variables de entrada: SOLO informacion con fecha <= t_k. Un ciclo vencido antes de
  t_k pero pagado despues se ve como "sin pagar" con el atraso acumulado hasta t_k,
  porque eso es lo que se sabria ese dia.
- Etiqueta: ciclos con vencimiento en (t_k, t_k + H semanas]. Vale 1 si alguno llega a
  X o mas dias de atraso, o si nunca se pago porque el episodio se cerro antes.

Ver docs/reglas_de_negocio.md.
"""
import numpy as np
import pandas as pd

ENFERMEDAD = {"ENFERMO", "FAMILIAR MUERTO"}
INMOVILIZACION = {"VARADO", "ACIDENTADO", "PATIO", "PATIOS", "FISCALIA", "EN TALLER", "GARANTIA", "GARANTÍA"}
RETENCION = {"MOTO INGRESADA"}
PROBLEMA = {"PROBLEMA"}


def asignar_retiro(episodios, retiros, gracia_dias=30):
    """Primera carta de retiro dentro del episodio (o hasta `gracia_dias` despues de
    su fin, porque la carta se registra unos dias despues de quitar la moto)."""
    m = episodios[["id_episodio", "id_contrato", "fecha_inicio", "fin"]].merge(retiros, on="id_contrato")
    m = m[(m.fecha >= m.fecha_inicio) & (m.fecha <= m.fin + pd.Timedelta(days=gracia_dias))]
    m = m.sort_values("fecha").drop_duplicates("id_episodio")
    m = m.rename(columns={"fecha": "fecha_retiro", "motivo": "motivo_retiro"})
    return episodios.merge(m[["id_episodio", "fecha_retiro", "motivo_retiro"]], how="left")


def marcar_poblacion(episodios, ciclos, k, h, x, corte, inicio_cohorte):
    """Clasifica cada episodio segun si entra al modelo supervisado y por que no.

    `motivo_exclusion` vale None para los episodios de la poblacion.
    """
    ep = episodios.copy()
    con_pago = set(ciclos.loc[ciclos.pagado, "id_episodio"])
    ep["semanas"] = (ep.fin - ep.fecha_inicio).dt.days / 7
    ep["cerrado"] = ep.fin < corte - pd.Timedelta(days=3)
    t_k = ep.fecha_inicio + pd.Timedelta(weeks=k)
    t_h = ep.fecha_inicio + pd.Timedelta(weeks=k + h)
    reglas = [
        # El orden importa: cada episodio queda con el primer motivo que cumple
        ("inicio antes de la cohorte", ep.fecha_inicio < inicio_cohorte),
        ("error de asignacion (<= 1 semana sin pagos)", (ep.semanas <= 1) & ~ep.id_episodio.isin(con_pago)),
        ("sin dia_canon", (ep.tipopago == "SEMANAL") & ep.dia_canon_num.isna()),
        ("cerrado antes de la semana k", ep.fin <= t_k),
        # El desenlace se conoce si el horizonte (mas x dias para ver el atraso del
        # ultimo ciclo) ya paso, o si el episodio se cerro dentro del horizonte
        ("sin desenlace observable aun", ~((t_h + pd.Timedelta(days=x) <= corte) | (ep.cerrado & (ep.fin <= t_h)))),
    ]
    ep["motivo_exclusion"] = None
    for motivo, cond in reglas:
        ep.loc[ep.motivo_exclusion.isna() & cond, "motivo_exclusion"] = motivo
    return ep


def _semana(ciclos, episodios):
    c = ciclos.merge(episodios[["id_episodio", "fecha_inicio", "cerrado"]], on="id_episodio")
    c["semana"] = (c.fecha_esperada - c.fecha_inicio).dt.days / 7
    return c


def etiqueta(poblacion, ciclos, k, h, x):
    """1 = riesgo grave de mora: algun ciclo que vence en (k, k+h] semanas alcanza x o
    mas dias de atraso, o nunca se pago porque el episodio se cerro."""
    c = _semana(ciclos[ciclos.id_episodio.isin(poblacion.id_episodio)], poblacion)
    c = c[(c.semana > k) & (c.semana <= k + h)]
    nunca_pagado = ~c.pagado & c.cerrado
    c["grave"] = (c.dias_atraso >= x) | nunca_pagado
    y = c.groupby("id_episodio").grave.any()
    return y.reindex(poblacion.id_episodio, fill_value=False).astype(int).rename("y")


def _eventos(diario_ep, valores):
    """Cuenta tramos de dias consecutivos con una justificacion del grupo."""
    d = diario_ep[diario_ep.just.isin(valores)].sort_values(["id_episodio", "fecha_registro"])
    if d.empty:
        return pd.Series(dtype=int)
    salto = d.groupby("id_episodio").fecha_registro.diff().dt.days.ne(1)
    return salto.groupby(d.id_episodio).sum().astype(int)


def variables_entrada(poblacion, ciclos, pagos, diario, k):
    """Variables de comportamiento de las primeras k semanas de cada episodio."""
    pob = poblacion.set_index("id_episodio")
    t_k = pob.fecha_inicio + pd.Timedelta(weeks=k)

    # Ciclos vencidos hasta t_k, vistos como se verian en t_k
    c = _semana(ciclos[ciclos.id_episodio.isin(pob.index)], poblacion)
    c = c[c.semana <= k].copy()
    c["t_k"] = c.id_episodio.map(t_k)
    c["pagado_k"] = c.pagado & (c.fecha_pago <= c.t_k)
    c["atraso_k"] = np.where(c.pagado_k, c.dias_atraso, (c.t_k - c.fecha_esperada).dt.days.clip(lower=0))
    g = c.groupby("id_episodio")
    tabla = pd.DataFrame({
        "ciclos_esperados": g.size(),
        "prop_ciclos_atrasados": g.atraso_k.apply(lambda s: (s > 0).mean()),
        "prop_ciclos_atraso_3mas": g.atraso_k.apply(lambda s: (s >= 3).mean()),
        "atraso_promedio": g.atraso_k.mean(),
        "atraso_maximo": g.atraso_k.max(),
        "ciclos_sin_pagar_k": g.pagado_k.apply(lambda s: (~s).sum()),
    })

    # Pagos del episodio en [fecha_inicio, t_k]
    p = pagos.merge(poblacion[["id_episodio", "id_contrato", "fecha_inicio"]], on="id_contrato")
    p = p[(p.fecha >= p.fecha_inicio) & (p.fecha <= p.id_episodio.map(t_k))]
    p["canon"] = p.abono + p.transf
    gp = p.groupby("id_episodio")
    tabla["dias_con_pago"] = gp.size()
    tabla["dias_hasta_primer_pago"] = (gp.fecha.min() - pob.fecha_inicio).dt.days
    tabla["pago_canon_total"] = gp.canon.sum()
    tabla["cv_pago_canon"] = gp.canon.std() / gp.canon.mean()
    tabla["multa_acumulada"] = gp.multa.sum()
    tabla["prop_pagos_con_multa"] = gp.multa.apply(lambda s: (s > 0).mean())
    tabla["repuesto_acumulado"] = gp.repuesto.sum()
    tabla = tabla.reindex(pob.index)
    for col in ("dias_con_pago", "pago_canon_total", "multa_acumulada", "repuesto_acumulado"):
        tabla[col] = tabla[col].fillna(0)  # sin pagos en la ventana: 0 real, no faltante
    tabla["pagos_por_ciclo"] = tabla.dias_con_pago / tabla.ciclos_esperados
    tabla["deficit_relativo"] = 1 - tabla.pago_canon_total / (pob.cuota * tabla.ciclos_esperados)

    # Justificaciones y marcas de gestion vigentes en [fecha_inicio, t_k]
    d = diario[["id_contrato", "fecha_registro", "justificacion"]].merge(
        poblacion[["id_episodio", "id_contrato", "fecha_inicio"]], on="id_contrato")
    d = d[(d.fecha_registro >= d.fecha_inicio) & (d.fecha_registro <= d.id_episodio.map(t_k))]
    d["just"] = d.justificacion.fillna("").str.strip().str.upper()
    for nombre, valores in (("justif_enfermedad", ENFERMEDAD), ("justif_inmovilizacion", INMOVILIZACION),
                            ("retencion_temporal", RETENCION), ("cliente_problema", PROBLEMA)):
        tabla[nombre] = _eventos(d, valores).reindex(pob.index, fill_value=0)

    # Variables del contrato (conocidas desde el inicio)
    tabla["tipopago"] = pob.tipopago
    tabla["empresa"] = pob.empresa
    tabla["cuota"] = pob.cuota
    tabla["no_canon"] = pob.no_canon
    tabla["dia_canon"] = pob.dia_canon.str.upper().str[:3].where(pob.tipopago == "SEMANAL", "QUI")
    return tabla
