"""Conexion de solo lectura a la base de la empresa.

Las credenciales se leen del archivo .env (excluido de git), nunca del codigo.
Solo se usa para extraer la copia de los datos; el notebook del proyecto trabaja
sobre la copia anonimizada, no sobre el servidor.
"""
import os
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

RAIZ = Path(__file__).resolve().parents[1]
load_dotenv(RAIZ / ".env")


def motor(base=None):
    """Engine de SQLAlchemy hacia MariaDB/MySQL; `base` sobreescribe DB_NAME."""
    usuario = os.environ["DB_USER"]
    clave = quote_plus(os.environ["DB_PASSWORD"])
    host = os.environ["DB_HOST"]
    puerto = os.environ.get("DB_PORT") or "3306"
    base = base if base is not None else (os.environ.get("DB_NAME") or "")
    url = f"mysql+pymysql://{usuario}:{clave}@{host}:{puerto}/{base}?charset=utf8mb4"
    return create_engine(url, pool_pre_ping=True)


def consultar(sql, base=None, **params):
    """Ejecuta un SELECT y devuelve un DataFrame."""
    with motor(base).connect() as con:
        return pd.read_sql(text(sql), con, params=params)
