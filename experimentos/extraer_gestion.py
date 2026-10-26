"""Extrae (SOLO SELECT) np_justi_super y np_gestion, anonimizadas con el mapa de contratos.
No se traen comentarios, evidencias ni nombres: solo tipo, estado, fecha y valor."""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import pandas as pd
from explorar_bd import q
from pathlib import Path
RAIZ = str(Path(__file__).resolve().parents[1])
mapa = pd.read_csv(RAIZ + "/data/raw/mapa_contratos.csv", dtype=str).set_index("contrato").id_contrato
j = q("SELECT CONTRATO, FECHA, JUSTIFICACION, ESTADO, CONCEPTO, numcuota, valor FROM np_justi_super WHERE FECHA >= '2024-01-01'")
g = q("SELECT CONTRATO, FECHA, CONCEPTO, gestion, fecha_g, VALOR, num_gest FROM np_gestion WHERE FECHA >= '2024-01-01'")
for n, d in (("justificaciones", j), ("gestion", g)):
    d["CONTRATO"] = d.CONTRATO.astype(str).str.strip()
    d["id_contrato"] = d.CONTRATO.map(mapa)
    print(n, len(d), "con mapa:", d.id_contrato.notna().sum())
    d = d[d.id_contrato.notna()].drop(columns="CONTRATO")
    d.columns = [c.lower() for c in d.columns]
    d.to_csv(RAIZ + f"/data/anon/{n}.csv.gz", index=False)
