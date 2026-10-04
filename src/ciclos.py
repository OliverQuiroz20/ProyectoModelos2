"""Construccion de episodios y del calendario de pagos esperado.

Reglas de negocio en docs/reglas_de_negocio.md. Resumen de lo que implementa:

- Episodio = un cliente con una moto: (id_contrato, fecha_inicio) en la foto diaria
  (motos_diario), solo con tipopago SEMANAL o QUINCENAL y fecha_inicio valida.
- Fecha esperada de pago (semanal): cada `dia_canon` despues de la fecha de inicio.
  Confirmado con los datos: el 50 % de los pagos cae ese dia y la multa aparece
  desde el dia siguiente (escalones de 15 y 25 mil).
- Hubo pago = abono + transferencia + multa + repuesto > 0 en el dia. Las cartas no
  son pagos, salvo PRONTO PAGO.
- Cada dia con pago cubre un ciclo; si el pago al canon (abono + transferencia)
  alcanza varias cuotas, cubre esas varias (cliente que paga semanas por adelantado
  o se pone al dia de una vez).
"""
import numpy as np
import pandas as pd

DIAS_SEMANA = {"LUN": 0, "MAR": 1, "MIE": 2, "MIER": 2, "JUE": 3, "VIE": 4, "SAB": 5, "DOM": 6}
TIPOS_LEASING = {"SEMANAL": 7, "QUINCENAL": 14}
CARTAS_RETIRO = {"CARTA REGRESO DIARIO", "CARTA ADMINISTRACION", "CARTA REALQUILER", "CARTA PERDIDA"}


def _moda(serie):
    serie = serie.dropna()
    return serie.mode().iloc[0] if len(serie) else None


def construir_episodios(diario):
    """Un registro por episodio de leasing a partir de la foto diaria."""
    d = diario[diario.tipopago.isin(TIPOS_LEASING)].copy()
    # '0000-00-00' = cliente asignado con tramites pendientes: aun no tiene la moto
    d["fecha_inicio"] = pd.to_datetime(d.fecha_inicio.where(d.fecha_inicio != "0000-00-00"), errors="coerce")
    d = d[d.fecha_inicio.notna() & (d.fecha_inicio >= "2020-01-01")]
    ep = d.groupby(["id_contrato", "fecha_inicio"]).agg(
        tipopago=("tipopago", _moda),
        dia_canon=("dia_canon", _moda),
        cuota=("cuota", "median"),
        no_canon=("no_canon", "max"),
        empresa=("empresa", _moda),
        primer_registro=("fecha_registro", "min"),
        ultimo_registro=("fecha_registro", "max"),
    ).reset_index()
    ep["dia_canon_num"] = ep.dia_canon.str.upper().map(DIAS_SEMANA)
    # El episodio termina cuando empieza el siguiente cliente de la misma moto
    ep = ep.sort_values(["id_contrato", "fecha_inicio"])
    ep["inicio_siguiente"] = ep.groupby("id_contrato").fecha_inicio.shift(-1)
    ep["fin"] = ep[["ultimo_registro", "inicio_siguiente"]].min(axis=1)
    ep.insert(0, "id_episodio", [f"E{i:05d}" for i in range(1, len(ep) + 1)])
    return ep.reset_index(drop=True)


def pagos_por_dia(abonos):
    """Dias con pago real por contrato (cualquier dinero entregado)."""
    motivo = abonos.cartamotivo.fillna("").str.strip().str.upper()
    p = abonos[(abonos.carta != "SI") | (motivo == "PRONTO PAGO")].copy()
    for c in ("abono", "transf", "multa", "repuesto"):
        p[c] = p[c].fillna(0)
    p["total"] = p.abono + p.transf + p.multa + p.repuesto
    p = p[p.total > 0]
    return p.groupby(["id_contrato", "fecha"], as_index=False).agg(
        abono=("abono", "sum"), transf=("transf", "sum"), multa=("multa", "sum"),
        repuesto=("repuesto", "sum"), total=("total", "sum"))


def retiros(abonos):
    """Primera carta de retiro por contrato y fecha (variable de validacion)."""
    motivo = abonos.cartamotivo.fillna("").str.strip().str.upper()
    r = abonos[(abonos.carta == "SI") & motivo.isin(CARTAS_RETIRO)].assign(motivo=motivo)
    return r[["id_contrato", "fecha", "motivo"]].sort_values("fecha")


def fechas_esperadas(ep, corte):
    """Fechas de pago esperadas del episodio, hasta su fin o el corte de datos."""
    paso = TIPOS_LEASING[ep.tipopago]
    fin = min(ep.fin, corte)
    if ep.tipopago == "SEMANAL":
        if pd.isna(ep.dia_canon_num):
            return pd.DatetimeIndex([])
        # Primer canon: el primer dia_canon estrictamente despues del inicio
        desfase = (int(ep.dia_canon_num) - ep.fecha_inicio.weekday()) % 7 or 7
        primera = ep.fecha_inicio + pd.Timedelta(days=desfase)
    else:
        primera = ep.fecha_inicio + pd.Timedelta(days=paso)
    return pd.date_range(primera, fin, freq=f"{paso}D")


def ciclos_episodio(ep, pagos_ep, corte):
    """Asigna los pagos del episodio a sus fechas esperadas.

    Devuelve un registro por ciclo con su fecha esperada, la fecha del pago que lo
    cubrio y los dias de atraso. Un ciclo sin pago hasta el fin observable queda
    con `pagado=False` y su atraso es censurado (al menos esos dias).
    """
    esperadas = fechas_esperadas(ep, corte)
    if len(esperadas) == 0:
        return pd.DataFrame()
    paso = TIPOS_LEASING[ep.tipopago]
    fechas = pagos_ep.fecha.to_numpy()
    canon = (pagos_ep.abono + pagos_ep.transf).to_numpy()
    cuota = ep.cuota if ep.cuota and ep.cuota > 0 else np.nan
    # Ciclos que cubre cada dia de pago: 1, o varios si el pago al canon alcanza
    cubre = np.ones(len(fechas), dtype=int)
    if not np.isnan(cuota):
        cubre = np.maximum(1, np.floor(canon / cuota + 0.05).astype(int))
    filas, j, saldo_j = [], 0, (cubre[0] if len(cubre) else 0)
    fin_obs = min(ep.fin, corte)
    for i, fe in enumerate(esperadas, start=1):
        apertura = fe - pd.Timedelta(days=paso - 1)
        # Pagos anteriores a la ventana de este ciclo que no alcanzaron a usarse
        # (por ejemplo, un abono de prueba antes del primer canon) se descartan.
        while j < len(fechas) and fechas[j] < apertura and saldo_j == cubre[j]:
            j += 1
            saldo_j = cubre[j] if j < len(fechas) else 0
        if j < len(fechas):
            fecha_pago = pd.Timestamp(fechas[j])
            atraso = max(0, (fecha_pago - fe).days)
            filas.append((i, fe, fecha_pago, True, atraso, pagos_ep.multa.iat[j] if saldo_j == cubre[j] else 0.0))
            saldo_j -= 1
            if saldo_j == 0:
                j += 1
                saldo_j = cubre[j] if j < len(fechas) else 0
        else:
            filas.append((i, fe, pd.NaT, False, max(0, (fin_obs - fe).days), np.nan))
    out = pd.DataFrame(filas, columns=["ciclo", "fecha_esperada", "fecha_pago", "pagado", "dias_atraso", "multa"])
    out.insert(0, "id_episodio", ep.id_episodio)
    return out


def construir_ciclos(episodios, pagos, corte):
    """Ciclos de todos los episodios. Los pagos de cada contrato se reparten por
    episodio segun su intervalo [fecha_inicio, fin + un ciclo de gracia)."""
    pagos = pagos.sort_values(["id_contrato", "fecha"])
    por_contrato = dict(tuple(pagos.groupby("id_contrato")))
    partes = []
    for ep in episodios.itertuples(index=False):
        p = por_contrato.get(ep.id_contrato)
        if p is None:
            p = pagos.iloc[0:0]
        gracia = pd.Timedelta(days=TIPOS_LEASING[ep.tipopago])
        p = p[(p.fecha >= ep.fecha_inicio) & (p.fecha < ep.fin + gracia)]
        if pd.notna(ep.inicio_siguiente):
            p = p[p.fecha < ep.inicio_siguiente]
        c = ciclos_episodio(ep, p, corte)
        if len(c):
            partes.append(c)
    return pd.concat(partes, ignore_index=True)
