"""Exploracion de SOLO LECTURA: rechaza cualquier sentencia que no sea SELECT/SHOW/DESCRIBE."""
import re, sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "src"))
from conexion import consultar
def q(sql, **p):
    assert re.match(r"\s*(select|show|describe)\b", sql, re.I), "solo lectura"
    return consultar(sql, **p)
if __name__ == "__main__":
    print(q("SELECT table_name, table_type, table_rows FROM information_schema.tables WHERE table_schema='db_packgps' AND (table_name REGEXP 'gesti|justi|problem|estado|tramit|nopago|contact|llam') ORDER BY table_name").to_string())
