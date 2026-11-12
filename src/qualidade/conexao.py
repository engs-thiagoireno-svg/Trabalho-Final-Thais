"""Conexão com o PostgreSQL a partir do config/config.ini (sem senha no código)."""
import configparser
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL

RAIZ = Path(__file__).resolve().parents[2]          # pasta do projeto, sem caminho fixo
CONFIG_PADRAO = RAIZ / "config" / "config.ini"


def ler_config(caminho=CONFIG_PADRAO):
    cfg = configparser.ConfigParser()
    if not cfg.read(caminho, encoding="utf-8"):
        raise FileNotFoundError(f"Config não encontrado: {caminho} "
                                "(copie config.example.ini para config.ini)")
    return cfg


def criar_engine(cfg=None):
    cfg = cfg or ler_config()
    b = cfg["banco"]
    url = URL.create("postgresql+psycopg2", username=b["usuario"], password=b["senha"],
                     host=b["host"], port=int(b["porta"]), database=b["banco"])
    return create_engine(url)


def ler_tabela(engine, schema, tabela):
    return pd.read_sql(f"select * from {schema}.{tabela}", engine)


def tabela_existe(engine, schema, tabela):
    return inspect(engine).has_table(tabela, schema=schema)
