"""Gera as tabelas limpas e de quarentena. A origem nunca é alterada."""
import pandas as pd
from sqlalchemy import text

from . import regras as r
from .decisoes import CORRECOES_CADASTRO


# ------------------------------------------------------------------ cadastro de usinas
def limpar_usina(usina: pd.DataFrame):
    """Devolve (usina_limpa, usina_quarentena, de_para {id_descartado: id_mantido})."""
    u = usina.copy()
    u["correcao"] = ""

    # 1. coordenada com sinal invertido
    for col, (lo, hi) in [("latitude", r.LAT_BRASIL), ("longitude", r.LON_BRASIL)]:
        fora = ~u[col].between(lo, hi)
        invertivel = fora & (-u[col]).between(lo, hi)
        u.loc[invertivel, col] = -u.loc[invertivel, col]
        u.loc[invertivel, "correcao"] += f"{col}_sinal_invertido;"

    # 2. correções manuais documentadas (decisoes.CORRECOES_CADASTRO)
    for cod, col, novo, _ in CORRECOES_CADASTRO:
        m = u["cod_usina"] == cod
        u.loc[m & (u[col] != novo), "correcao"] += f"{col}_corrigida;"
        u.loc[m, col] = novo

    # 3. cadastro duplicado: agrupa por nome normalizado OU coordenadas
    dup_nome = r.duplicados(u, "usina", ["nome"], normalizar=True).falhas.index
    dup_coord = r.duplicados(u, "usina", ["latitude", "longitude"], normalizar=True, casas=3).falhas.index
    de_para, descartar = {}, set()
    suspeitas = u.loc[sorted(set(dup_nome) | set(dup_coord))]
    if len(suspeitas):
        grupo = suspeitas["latitude"].round(3).astype(str) + "|" + suspeitas["longitude"].round(3).astype(str)
        for _, g in suspeitas.groupby(grupo):
            vazios = r.nulos_ou_vazios(g, "usina", ["nome", "municipio", "uf"]).falhas.index
            g = g.assign(_vazio=g.index.isin(vazios)).sort_values(["_vazio", "id_usina"])
            mantido = g.iloc[0]["id_usina"]
            for idu in g["id_usina"].iloc[1:]:
                de_para[int(idu)] = int(mantido)
                descartar.add(idu)

    quarentena = u[u["id_usina"].isin(descartar)].assign(
        motivo="cadastro_duplicado", id_usina_canonico=lambda d: d["id_usina"].map(de_para))
    limpa = u[~u["id_usina"].isin(descartar)].copy()

    # 4. sinalizar início de operação no futuro
    hoje = pd.Timestamp.today().normalize()
    limpa["flag_inicio_operacao_invalido"] = pd.to_datetime(limpa["data_inicio_operacao"]) > hoje
    limpa["correcao"] = limpa["correcao"].where(limpa["correcao"] != "")
    return limpa, quarentena.drop(columns=["correcao"]), de_para


# ------------------------------------------------------------------ paradas
def limpar_parada(parada: pd.DataFrame, ids_validos):
    inv = r.ordem_temporal(parada, "parada_usina", "inicio", "fim").falhas.index
    fk = r.sem_correspondencia(parada, "parada_usina", "id_usina", ids_validos).falhas.index
    motivo = pd.Series("", index=parada.index)
    motivo[inv] += "fim_antes_de_inicio;"
    motivo[fk] += "fk_id_usina;"
    return parada[motivo == ""].copy(), parada[motivo != ""].assign(motivo=motivo[motivo != ""])


# ------------------------------------------------------------------ medição
def corrigir_medicao(med, potencia, de_para, pct_negativo=0.02):
    """Correções justificáveis. Devolve (medição corrigida, descartadas, conflitantes)."""
    m = med.copy()
    m["id_usina"] = m["id_usina"].replace(de_para)
    m["energia_mwh_original"] = m["energia_mwh"]
    m["correcao"] = None

    # a) escala: kWh no lugar de MWh (÷1000) ou vírgula deslocada (÷10)
    esc = r.fator_de_escala(m, potencia).falhas
    if len(esc):
        m.loc[esc.index, "energia_mwh"] = (m.loc[esc.index, "energia_mwh"] / esc["escala"].astype(float)).round(3)
        m.loc[esc.index, "correcao"] = esc["escala"].map({1000: "kwh_para_mwh", 10: "virgula_deslocada"})

    # b) negativo pequeno = consumo dos serviços auxiliares -> 0
    pot = m["id_usina"].map(potencia)
    neg = (m["energia_mwh"] < 0) & (m["energia_mwh"].abs() <= pct_negativo * pot)
    m.loc[neg, "energia_mwh"] = 0.0
    m.loc[neg, "correcao"] = "consumo_auxiliar_zerado"

    # c) duplicatas de usina+hora: SCADA antes de MANUAL; na mesma origem, a 1ª chegada
    m["_prio"] = (m["origem"] != "SCADA").astype(int)
    m = m.sort_values(["id_usina", "data_hora", "_prio", "recebido_em"])
    chave = ["id_usina", "data_hora"]
    eh_copia = m.duplicated(chave, keep="first") & m[chave].notna().all(axis=1)
    primeira = m[~eh_copia].set_index(chave)[["energia_mwh", "disponibilidade_mw"]]
    copias = m[eh_copia]
    ref = primeira.reindex(pd.MultiIndex.from_frame(copias[chave]))
    iguais = ((copias["energia_mwh"].values == ref["energia_mwh"].values)
              & (copias["disponibilidade_mw"].values == ref["disponibilidade_mw"].values))
    descartadas = copias[iguais]
    conflitantes = copias[~iguais].assign(motivo="duplicata_conflitante;")
    m = m[~eh_copia].drop(columns="_prio")
    return m, descartadas.drop(columns="_prio"), conflitantes.drop(columns="_prio")


def separar(df, regras_quarentena, flags):
    """regras_quarentena: lista de Resultado; flags: {nome_coluna: Resultado}."""
    motivo = pd.Series("", index=df.index)
    for res in regras_quarentena:
        idx = res.falhas.index.intersection(df.index)
        motivo.loc[idx] += res.regra + ";"
    quarentena = df[motivo != ""].assign(motivo=motivo[motivo != ""])
    limpa = df[motivo == ""].copy()
    for coluna, res in flags.items():
        limpa[coluna] = limpa.index.isin(res.falhas.index)
    return limpa, quarentena


def gravar(engine, df, tabela, schema="qualidade"):
    """Troca o conteúdo da tabela (criada pelo DDL) numa transação só."""
    with engine.begin() as con:
        colunas = [c[0] for c in con.execute(text(
            "select column_name from information_schema.columns "
            "where table_schema = :s and table_name = :t order by ordinal_position"),
            {"s": schema, "t": tabela})]
        con.execute(text(f"truncate table {schema}.{tabela}"))
        df[[c for c in colunas if c in df.columns]].to_sql(
            tabela, con, schema=schema, if_exists="append", index=False)
