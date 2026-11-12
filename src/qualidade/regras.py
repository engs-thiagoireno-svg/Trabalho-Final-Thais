"""Regras de qualidade. Cada função devolve um Resultado (avaliados + linhas que falharam).

As genéricas recebem (DataFrame, nome da tabela, colunas/parâmetros) e servem para
qualquer tabela. As específicas cruzam tabelas ou usam a física da usina.
"""
import unicodedata

import pandas as pd

from .metricas import Resultado

# ---------------------------------------------------------------- domínios e limites
SUBMERCADOS = {"SE", "S", "NE", "N"}
UFS = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
       "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}
# Submercado de cada UF no SIN (divisão CCEE/ONS)
SUBMERCADO_DA_UF = {
    **{uf: "S" for uf in ["PR", "SC", "RS"]},
    **{uf: "SE" for uf in ["SP", "RJ", "MG", "ES", "GO", "DF", "MT", "MS", "AC", "RO"]},
    **{uf: "NE" for uf in ["BA", "SE", "AL", "PE", "PB", "RN", "CE", "PI"]},
    **{uf: "N" for uf in ["PA", "TO", "MA", "AP", "AM", "RR"]},
}
# Caixa que contém o território brasileiro (graus decimais)
LAT_BRASIL, LON_BRASIL = (-33.8, 5.3), (-74.0, -34.7)
# PLD horário: (piso, teto HORÁRIO) em R$/MWh, ANEEL. Não usar o teto estrutural.
LIMITES_PLD = {2025: (58.60, 1542.23), 2026: (57.31, 1611.04)}


def _texto_normalizado(s: pd.Series) -> pd.Series:
    def norm(x):
        x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode()
        return " ".join(x.lower().split())
    return s.map(norm, na_action="ignore")


# ======================================================== GENÉRICAS
def nulos_ou_vazios(df, tabela, colunas, regra=None):                       # completude
    """Nulo OU texto vazio (''), que o banco aceita mesmo com NOT NULL."""
    mask = pd.Series(False, index=df.index)
    for c in colunas:
        mask |= df[c].isna()
        if not pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_datetime64_any_dtype(df[c]):
            mask |= df[c].astype(str).str.strip().eq("")
    return Resultado(regra or f"nulo_ou_vazio_{'_'.join(colunas)}", "completude",
                     tabela, len(df), df[mask])


def horas_faltantes(df, tabela, col_ent, entidades, col_hora, inicio, fim, regra=None):  # completude
    horas = pd.date_range(inicio, fim, freq="h")
    esperado = pd.MultiIndex.from_product([list(entidades), horas], names=[col_ent, col_hora])
    existe = pd.MultiIndex.from_frame(df[[col_ent, col_hora]].dropna().drop_duplicates())
    faltando = esperado.difference(existe).to_frame(index=False)
    return Resultado(regra or "horas_faltantes", "completude", tabela, len(esperado), faltando)


def duplicados(df, tabela, chaves, regra=None, normalizar=False, casas=4):  # unicidade
    """Marca TODAS as cópias. normalizar=True ignora caixa, acento, espaços e arredonda números."""
    chave = df[chaves].copy()
    if normalizar:
        for c in chaves:
            if pd.api.types.is_numeric_dtype(chave[c]):
                chave[c] = pd.to_numeric(chave[c]).astype(float).round(casas)
            else:
                chave[c] = _texto_normalizado(chave[c])
    mask = chave.duplicated(keep=False) & chave.notna().all(axis=1)
    return Resultado(regra or f"duplicado_{'_'.join(chaves)}", "unicidade",
                     tabela, len(df), df[mask])


def fora_do_intervalo(df, tabela, coluna, minimo=None, maximo=None, regra=None):  # validade
    s = df[coluna]
    mask = pd.Series(False, index=df.index)
    if minimo is not None:
        mask |= s < minimo
    if maximo is not None:
        mask |= s > maximo
    return Resultado(regra or f"intervalo_{coluna}", "validade",
                     tabela, int(s.notna().sum()), df[mask])


def fora_do_dominio(df, tabela, coluna, dominio, regra=None):                # validade
    v = df[coluna].dropna()
    return Resultado(regra or f"dominio_{coluna}", "validade",
                     tabela, len(v), df.loc[v.index[~v.isin(dominio)]])


def ordem_temporal(df, tabela, col_antes, col_depois, regra=None):           # consistência
    """Ex.: parada com fim antes do início; medição recebida antes de acontecer."""
    ok = df[[col_antes, col_depois]].notna().all(axis=1)
    mask = ok & (df[col_depois] < df[col_antes])
    return Resultado(regra or f"{col_depois}_antes_de_{col_antes}", "consistencia",
                     tabela, int(ok.sum()), df[mask])


def outliers_iqr(df, tabela, coluna, grupo, k=3.0, regra=None):             # acurácia
    """IQR por grupo, só sobre valores > 0 (zero = usina parada/sem recurso, outro estado)."""
    pos = df[df[coluna] > 0]
    g = pos.groupby(grupo)[coluna]
    q1, q3 = g.transform(lambda s: s.quantile(.25)), g.transform(lambda s: s.quantile(.75))
    iqr = q3 - q1
    mask = (pos[coluna] < q1 - k * iqr) | (pos[coluna] > q3 + k * iqr)
    return Resultado(regra or f"outlier_iqr_{coluna}", "acuracia",
                     tabela, len(pos), pos[mask])


def valor_travado(df, tabela, coluna, grupo, col_tempo, min_horas=6, regra=None):  # acurácia
    d = df.dropna(subset=[coluna]).sort_values([grupo, col_tempo])
    novo_bloco = (d[coluna] != d.groupby(grupo)[coluna].shift()) | \
                 (d[col_tempo].diff() != pd.Timedelta(hours=1))
    tam = d.groupby(novo_bloco.cumsum())[coluna].transform("size")
    mask = (tam >= min_horas) & (d[coluna] > 0)        # zeros repetidos são normais
    return Resultado(regra or f"{coluna}_travado_{min_horas}h", "acuracia",
                     tabela, len(d), d[mask])


def sem_correspondencia(df, tabela, coluna, chaves_pai, regra=None):         # integridade ref.
    mask = df[coluna].isna() | ~df[coluna].isin(set(chaves_pai))
    return Resultado(regra or f"fk_{coluna}", "integridade_referencial",
                     tabela, len(df), df[mask])


def atraso_chegada(df, tabela, col_evento, col_chegada, limite_horas, regra=None):  # atualidade
    atraso = (df[col_chegada] - df[col_evento]).dt.total_seconds() / 3600
    return Resultado(regra or f"atraso_maior_{limite_horas}h", "atualidade",
                     tabela, int(atraso.notna().sum()), df[atraso > limite_horas])


def parou_de_enviar(df, tabela, col_ent, entidades, col_tempo, fim_esperado,
                    tolerancia_h=24, regra=None):                            # atualidade
    ultimo = df[df[col_ent].isin(entidades)].groupby(col_ent)[col_tempo].max()
    ultimo = ultimo.reindex(list(entidades))          # usina sem nenhum dado também falha
    corte = pd.Timestamp(fim_esperado) - pd.Timedelta(hours=tolerancia_h)
    falhas = ultimo[ultimo.isna() | (ultimo < corte)].rename("ultimo_dado").reset_index()
    return Resultado(regra or "parou_de_enviar", "atualidade", tabela, len(ultimo), falhas)


# ======================================================== ESPECÍFICAS
def energia_acima_potencia(med, potencia, tabela="medicao_geracao"):         # consistência
    """Em 1 hora a usina gera no máximo potência (MW) x 1 h = MWh."""
    pot = med["id_usina"].map(potencia)
    return Resultado("energia_acima_potencia_x_1h", "consistencia", tabela,
                     int(pot.notna().sum()), med[med["energia_mwh"] > pot])


def disponibilidade_acima_potencia(med, potencia, tabela="medicao_geracao"):  # consistência
    pot = med["id_usina"].map(potencia)
    return Resultado("disponibilidade_acima_potencia", "consistencia", tabela,
                     int(pot.notna().sum()), med[med["disponibilidade_mw"] > pot])


def geracao_durante_parada(med, paradas, tabela="medicao_geracao"):          # consistência
    """Fim da parada é inclusivo (a hora 'fim' também está parada, como no script de origem)."""
    idx = set()
    validas = paradas[paradas["fim"] >= paradas["inicio"]]
    for p in validas.itertuples():
        m = ((med["id_usina"] == p.id_usina) & med["data_hora"].between(p.inicio, p.fim)
             & (med["energia_mwh"] > 0))
        idx.update(med.index[m])
    return Resultado("geracao_durante_parada", "consistencia", tabela,
                     len(med), med.loc[sorted(idx)])


def solar_a_noite(med, ids_solares, tabela="medicao_geracao", inicio_noite=19, fim_noite=6,
                  radiacao=None):                                             # consistência
    """Sem clima: noite = 19h às 5h. Com clima (Series indexada por id_usina, data_hora):
    noite = radiação 0 na própria usina."""
    s = med[med["id_usina"].isin(ids_solares)]
    if radiacao is not None:
        rad = pd.MultiIndex.from_frame(s[["id_usina", "data_hora"]]).map(radiacao.get)
        eh_noite = pd.Series(rad, index=s.index).fillna(-1).eq(0)
    else:
        h = s["data_hora"].dt.hour
        eh_noite = (h >= inicio_noite) | (h < fim_noite)
    return Resultado("solar_gerando_a_noite", "consistencia", tabela,
                     int(eh_noite.sum()), s[eh_noite & (s["energia_mwh"] > 0)])


def uf_incompativel_submercado(usina, tabela="usina", mapa=SUBMERCADO_DA_UF):  # consistência
    esperado = usina["uf"].map(mapa)
    mask = esperado.notna() & (esperado != usina["cod_submercado"])
    return Resultado("uf_incompativel_com_submercado", "consistencia", tabela,
                     int(esperado.notna().sum()), usina[mask])


def geracao_antes_inicio_operacao(med, inicio_operacao, tabela="medicao_geracao"):  # consistência
    ini = med["id_usina"].map(inicio_operacao)
    mask = ini.notna() & (med["data_hora"] < ini) & (med["energia_mwh"] > 0)
    return Resultado("geracao_antes_inicio_operacao", "consistencia", tabela,
                     int(ini.notna().sum()), med[mask])


def fator_de_escala(med, potencia, tabela="medicao_geracao"):                # acurácia
    """Valor acima da potência e ~10x ou ~1000x a mediana mensal (> 0) da usina:
    vírgula deslocada ou planilha em kWh. Devolve a coluna 'escala' (10 ou 1000)."""
    m = med.dropna(subset=["energia_mwh", "data_hora"])
    pos = m[m["energia_mwh"] > 0]
    mediana = pos.groupby([pos["id_usina"], pos["data_hora"].dt.month])["energia_mwh"].median()
    chave = pd.MultiIndex.from_arrays([m["id_usina"], m["data_hora"].dt.month])
    ref = pd.Series(chave.map(mediana.get), index=m.index, dtype=float)
    razao = m["energia_mwh"] / ref
    pot = m["id_usina"].map(potencia)
    acima = m["energia_mwh"] > pot
    escala = pd.Series(pd.NA, index=m.index, dtype="Int64")
    escala[acima & razao.between(500, 2000) & (m["energia_mwh"] / 1000 <= pot)] = 1000
    escala[acima & razao.between(7, 14) & (m["energia_mwh"] / 10 <= pot)] = 10
    falhas = m[escala.notna()].assign(escala=escala[escala.notna()])
    return Resultado("fator_de_escala_kwh_ou_virgula", "acuracia", tabela,
                     int(pot.notna().sum()), falhas)


def pld_fora_dos_limites(pld, tabela="extracao.pld_horario", limites=LIMITES_PLD):  # validade
    ano = pld["data_hora"].dt.year
    piso = ano.map({a: l[0] for a, l in limites.items()})
    teto = ano.map({a: l[1] for a, l in limites.items()})
    v = pld["pld_rs_mwh"]
    mask = piso.isna() | (v < piso - 0.01) | (v > teto + 0.01)
    return Resultado("pld_fora_piso_teto_horario", "validade", tabela, len(pld), pld[mask])
