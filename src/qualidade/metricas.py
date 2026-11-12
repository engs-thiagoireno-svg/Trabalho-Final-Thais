"""Padrão de resultado de regra e gravação na tabela qualidade.metricas_qualidade."""
from dataclasses import dataclass
from datetime import datetime

import pandas as pd


@dataclass
class Resultado:
    regra: str
    dimensao: str
    tabela: str
    avaliados: int
    falhas: pd.DataFrame          # linhas (ou chaves) que falharam, com o índice original

    @property
    def qtd_falhas(self) -> int:
        return len(self.falhas)

    @property
    def percentual(self) -> float:
        return round(100 * self.qtd_falhas / self.avaliados, 2) if self.avaliados else 0.0


def resumo(resultados) -> pd.DataFrame:
    return pd.DataFrame([{
        "regra": r.regra, "dimensao": r.dimensao, "tabela": r.tabela,
        "registros_avaliados": r.avaliados, "registros_falha": r.qtd_falhas,
        "percentual_falha": r.percentual,
    } for r in resultados])


def gravar_metricas(engine, resultados, data_execucao=None) -> pd.DataFrame:
    df = resumo(resultados).assign(data_execucao=data_execucao or datetime.now())
    df.to_sql("metricas_qualidade", engine, schema="qualidade", if_exists="append", index=False)
    return df
