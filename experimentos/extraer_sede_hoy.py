"""Datos al dia (SOLO SELECT) de una sede, a data/anon/<sede>_hoy, reusando el mapa de codigos de la sede."""
import os, sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
HOSTS = {"sincelejo": "server-motosince.netbird.cloud", "monteria": "server-motomonteria.netbird.cloud"}
sede = sys.argv[1]
os.environ["DB_HOST"] = HOSTS[sede]
import extraer
extraer.MAPA = RAIZ / "data" / "raw" / f"mapa_{sede}.csv"
extraer.DIR_ANON = RAIZ / "data" / "anon" / f"{sede}_hoy"
extraer.main()
