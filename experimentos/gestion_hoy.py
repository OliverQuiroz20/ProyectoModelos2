"""Paso 1: trae datos al dia (solo SELECT) a data/anon_hoy y resume las motos activas por antiguedad."""
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
import extraer  # noqa: E402

DESTINO = RAIZ / "data" / "anon_hoy"
if not (DESTINO / "abonos.csv.gz").exists() or "--refrescar" in sys.argv:
    extraer.DIR_ANON = DESTINO  # el mapa de codigos es el mismo: los codigos no cambian
    extraer.main()

import clasificacion as cl  # noqa: E402

ep, ciclos, pagos, diario, corte = cl.cargar_base(DESTINO)
hoy = diario.fecha_registro.max()
activos = ep[ep.ultimo_registro >= hoy].copy()
activos["semanas"] = (hoy - activos.fecha_inicio).dt.days / 7
print("hoy:", hoy.date(), "| corte de pagos:", corte.date(), "| episodios activos:", len(activos))
print(activos.tipopago.value_counts().to_dict())
print(pd.cut(activos.semanas, [-1, 8, 20, 52, 104, 1000]).value_counts().sort_index())
