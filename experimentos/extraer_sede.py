"""Extrae (SOLO SELECT) una sede distinta de Cartagena con el mismo extractor.
Uso: python herramientas/extraer_sede.py sincelejo|monteria"""
import os, sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
HOSTS = {"sincelejo": "server-motosince.netbird.cloud", "monteria": "server-motomonteria.netbird.cloud"}
sede = sys.argv[1]
os.environ["DB_HOST"] = HOSTS[sede]
import extraer
extraer.MAPA = RAIZ / "data" / "raw" / f"mapa_{sede}.csv"
extraer.DIR_ANON = RAIZ / "data" / "anon" / sede
extraer.main()
