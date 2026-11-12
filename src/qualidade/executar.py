"""Etapa 2 - Qualidade de dados. Rodar da raiz do projeto:

    python -m src.qualidade.executar

Ordem: profiling -> regras na origem -> limpeza -> regras na limpa -> antes x depois.
"""
from datetime import datetime

import pandas as pd
from sqlalchemy import text

from . import regras as r
from .antes_depois import comparar, indicadores
from .conexao import RAIZ, criar_engine, ler_config, ler_tabela, tabela_existe
from .decisoes import DECISOES
from .limpeza import corrigir_medicao, gravar, limpar_parada, limpar_usina, separar
from .metricas import gravar_metricas, resumo
from .profiling import perfil

ORIGEM = "campo_real_energia"
INICIO, FIM = "2025-01-01 00:00", "2025-12-31 23:00"
TABELAS_ORIGEM = ["submercado", "fonte_energia", "usina", "feriado_nacional",
                  "parada_usina", "medicao_geracao", "log_carga"]
# Regras cuja falha manda a linha da medição para a quarentena (depois das correções)
REGRAS_QUARENTENA_MEDICAO = {
    "nulo_ou_vazio_energia_mwh", "energia_negativa", "data_fora_de_2025",
    "energia_acima_potencia_x_1h", "disponibilidade_acima_potencia", "geracao_durante_parada",
    "solar_gerando_a_noite", "energia_mwh_travado", "fk_id_usina",
}
CADASTRO_OBRIGATORIO = ["cod_usina", "nome", "uf", "municipio", "latitude", "longitude",
                        "potencia_mw", "data_inicio_operacao", "cod_submercado"]


# ------------------------------------------------------------------ carga
def carregar(engine):
    d = {t: ler_tabela(engine, ORIGEM, t) for t in TABELAS_ORIGEM}
    for nome, tab in [("pld", "pld_horario"), ("clima", "clima_horario")]:
        d[nome] = ler_tabela(engine, "extracao", tab) if tabela_existe(engine, "extracao", tab) else None
    med, par = d["medicao_geracao"], d["parada_usina"]
    # CHAR(n) do PostgreSQL chega ao pandas com espaço à direita ('S ', 'N '): padronizar
    for t, cols in {"usina": ["cod_submercado", "uf"], "submercado": ["cod_submercado"]}.items():
        for c in cols:
            d[t][c] = d[t][c].str.rstrip()
    if d["pld"] is not None:
        d["pld"]["cod_submercado"] = d["pld"]["cod_submercado"].str.rstrip()
    med["id_usina"] = med["id_usina"].astype("Int64")          # tem NULL: evita virar float
    for c in ["data_hora", "recebido_em"]:
        med[c] = pd.to_datetime(med[c])
    for c in ["inicio", "fim"]:
        par[c] = pd.to_datetime(par[c])
    d["usina"]["data_inicio_operacao"] = pd.to_datetime(d["usina"]["data_inicio_operacao"])
    for c in ["energia_mwh", "disponibilidade_mw"]:
        med[c] = med[c].astype(float)
    d["usina"]["potencia_mw"] = d["usina"]["potencia_mw"].astype(float)
    for nome in ["pld", "clima"]:
        if d[nome] is not None:
            d[nome]["data_hora"] = pd.to_datetime(d[nome]["data_hora"])
    return d


# ------------------------------------------------------------------ regras
def regras_cadastro(usina, fonte, submercado, tabela="campo_real_energia.usina"):
    hoje = pd.Timestamp.today().normalize()
    return [
        r.nulos_ou_vazios(usina, tabela, CADASTRO_OBRIGATORIO, regra="nulo_ou_vazio_cadastro_usina"),
        r.duplicados(usina, tabela, ["nome"], normalizar=True, regra="duplicado_usina_nome"),
        r.duplicados(usina, tabela, ["latitude", "longitude"], normalizar=True, casas=3,
                     regra="duplicado_usina_coordenadas"),
        r.fora_do_intervalo(usina, tabela, "latitude", *r.LAT_BRASIL, regra="latitude_fora_do_brasil"),
        r.fora_do_intervalo(usina, tabela, "longitude", *r.LON_BRASIL, regra="longitude_fora_do_brasil"),
        r.fora_do_intervalo(usina, tabela, "data_inicio_operacao", maximo=hoje,
                            regra="inicio_operacao_no_futuro"),
        r.fora_do_dominio(usina, tabela, "uf", r.UFS),
        r.fora_do_dominio(usina, tabela, "cod_submercado", r.SUBMERCADOS),
        r.uf_incompativel_submercado(usina, tabela),
        r.sem_correspondencia(usina, tabela, "id_fonte", fonte["id_fonte"]),
        r.sem_correspondencia(usina, tabela, "cod_submercado", submercado["cod_submercado"]),
    ]


def regras_parada(par, ids_usina, tabela="campo_real_energia.parada_usina"):
    return [
        r.ordem_temporal(par, tabela, "inicio", "fim", regra="fim_antes_de_inicio"),
        r.fora_do_dominio(par, tabela, "tipo", {"Programada", "Forçada"}),
        r.sem_correspondencia(par, tabela, "id_usina", ids_usina),
    ]


def regras_medicao(med, usina_ref, ids_validos, paradas, ids_solares, cfg_q, tabela, radiacao=None):
    pot = usina_ref.set_index("id_usina")["potencia_mw"]
    ini = usina_ref.set_index("id_usina")["data_inicio_operacao"]
    return [
        # completude
        r.horas_faltantes(med, tabela, "id_usina", ids_validos, "data_hora", INICIO, FIM,
                          regra="horas_faltantes_medicao"),
        r.nulos_ou_vazios(med, tabela, ["energia_mwh"]),
        # unicidade
        r.duplicados(med, tabela, ["id_usina", "data_hora"]),
        # validade
        r.fora_do_intervalo(med, tabela, "energia_mwh", minimo=0, regra="energia_negativa"),
        r.fora_do_intervalo(med, tabela, "data_hora", pd.Timestamp(INICIO), pd.Timestamp(FIM),
                            regra="data_fora_de_2025"),
        r.fora_do_dominio(med, tabela, "origem", {"SCADA", "MANUAL"}),
        # consistência
        r.energia_acima_potencia(med, pot, tabela),
        r.disponibilidade_acima_potencia(med, pot, tabela),
        r.geracao_durante_parada(med, paradas, tabela),
        r.solar_a_noite(med, ids_solares, tabela, radiacao=radiacao),
        r.ordem_temporal(med, tabela, "data_hora", "recebido_em"),
        r.geracao_antes_inicio_operacao(med, ini, tabela),
        # acurácia
        r.fator_de_escala(med, pot, tabela),
        r.valor_travado(med, tabela, "energia_mwh", "id_usina", "data_hora",
                        min_horas=cfg_q["min_horas_travado"], regra="energia_mwh_travado"),
        r.outliers_iqr(med, tabela, "energia_mwh", "id_usina"),
        # integridade referencial
        r.sem_correspondencia(med, tabela, "id_usina", ids_validos),
        # atualidade
        r.atraso_chegada(med, tabela, "data_hora", "recebido_em", cfg_q["limite_atraso_horas"],
                         regra="atraso_chegada"),
        r.parou_de_enviar(med, tabela, "id_usina", ids_validos, "data_hora", FIM),
    ]


def regras_pld(pld, tabela="extracao.pld_horario"):
    ult = pld["data_hora"].max()
    fim = FIM if pd.isna(ult) else min(pd.Timestamp(FIM), ult)
    res = [r.pld_fora_dos_limites(pld, tabela),
           r.horas_faltantes(pld[pld["data_hora"].dt.year == 2025], tabela, "cod_submercado",
                             sorted(r.SUBMERCADOS), "data_hora", INICIO, fim, regra="horas_faltantes_pld"),
           r.fora_do_dominio(pld, tabela, "cod_submercado", r.SUBMERCADOS),
           r.duplicados(pld, tabela, ["data_hora", "cod_submercado"])]
    if not pd.isna(ult) and ult.year == 2026:                       # 2026 até o último mês publicado
        res.append(r.horas_faltantes(pld[pld["data_hora"].dt.year == 2026], tabela, "cod_submercado",
                                     sorted(r.SUBMERCADOS), "data_hora", "2026-01-01 00:00", ult,
                                     regra="horas_faltantes_pld_2026"))
    return res


def regras_clima(clima, codigos, tabela="extracao.clima_horario"):
    return [
        r.horas_faltantes(clima, tabela, "cod_usina", codigos, "data_hora", INICIO, FIM,
                          regra="horas_faltantes_clima"),
        r.duplicados(clima, tabela, ["cod_usina", "data_hora"]),
        r.fora_do_intervalo(clima, tabela, "radiacao_wm2", 0, 1400, regra="clima_radiacao_fora_faixa"),
        r.fora_do_intervalo(clima, tabela, "vento_10m_ms", 0, 60, regra="clima_vento_10m_fora_faixa"),
        r.fora_do_intervalo(clima, tabela, "vento_100m_ms", 0, 80, regra="clima_vento_100m_fora_faixa"),
        r.fora_do_intervalo(clima, tabela, "temperatura_c", -10, 50, regra="clima_temperatura_fora_faixa"),
        r.fora_do_intervalo(clima, tabela, "chuva_mm", 0, 300, regra="clima_chuva_fora_faixa"),
        r.sem_correspondencia(clima, tabela, "cod_usina", codigos, regra="fk_cod_usina_clima"),
    ]


# ------------------------------------------------------------------ relatório automático
def escrever_resumo(metr, destino, ad, caminho):
    dec = pd.DataFrame([(k, v[0]) for k, v in DECISOES.items()], columns=["regra", "decisao"])
    m = metr.merge(dec, on="regra", how="left")
    linhas = ["# Resultado da qualidade de dados (gerado por executar.py)", "",
              f"Execução: {metr['data_execucao'].iloc[0]:%d/%m/%Y %H:%M}", "",
              "## Regras com falha (origem)", "",
              "| Dimensão | Regra | Tabela | Avaliados | Falhas | % | Decisão |",
              "| --- | --- | --- | ---: | ---: | ---: | --- |"]
    origem = m[~m["tabela"].str.startswith("qualidade.") & (m["registros_falha"] > 0)]
    for x in origem.sort_values(["dimensao", "regra"]).itertuples():
        linhas.append(f"| {x.dimensao} | {x.regra} | {x.tabela} | {x.registros_avaliados} | "
                      f"{x.registros_falha} | {x.percentual_falha} | {x.decisao} |")
    linhas += ["", "## Para onde foi cada linha da medição", "",
               "| Destino | Linhas |", "| --- | ---: |"]
    linhas += [f"| {k} | {v} |" for k, v in destino.items()]
    linhas += ["", "## Antes × depois (total e por usina)", "",
               "| Indicador | Recorte | Antes | Depois | Diferença | % |",
               "| --- | --- | ---: | ---: | ---: | ---: |"]
    sel = ad[ad["recorte"].str.startswith(("total", "usina"))]
    for x in sel.itertuples():
        linhas.append(f"| {x.indicador} | {x.recorte} | {x.valor_antes:,.3f} | {x.valor_depois:,.3f} | "
                      f"{x.diferenca:,.3f} | {x.diferenca_pct} |")
    caminho.parent.mkdir(exist_ok=True)
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ principal
def garantir_schema(engine):
    """Roda sql/02_qualidade_ddl.sql (só cria o que não existe; não toca na origem)."""
    ddl = (RAIZ / "sql" / "02_qualidade_ddl.sql").read_text(encoding="utf-8")
    with engine.begin() as con:
        con.exec_driver_sql(ddl)


def main():
    cfg = ler_config()
    cfg_q = {"limite_atraso_horas": cfg.getfloat("qualidade", "limite_atraso_horas", fallback=6),
             "min_horas_travado": cfg.getint("qualidade", "min_horas_travado", fallback=6)}
    engine = criar_engine(cfg)
    garantir_schema(engine)
    agora = datetime.now().replace(microsecond=0)
    d = carregar(engine)
    usina, med, par = d["usina"], d["medicao_geracao"], d["parada_usina"]

    # 1. profiling de todas as tabelas
    perfis = [perfil(d[t], f"{ORIGEM}.{t}") for t in TABELAS_ORIGEM]
    perfis += [perfil(d[n], f"extracao.{n}") for n in ["pld", "clima"] if d[n] is not None]
    (pd.concat(perfis, ignore_index=True).assign(data_execucao=agora)
       .to_sql("profiling", engine, schema="qualidade", if_exists="append", index=False))

    # 2. cadastro e paradas limpos (a medição depende deles)
    usina_l, usina_q, de_para = limpar_usina(usina)
    ids_validos = sorted(usina_l["id_usina"].tolist())
    par_l, par_q = limpar_parada(par, ids_validos)
    solares = usina_l.merge(d["fonte_energia"], on="id_fonte").query("cod_fonte == 'UFV'")["id_usina"]
    radiacao = None
    if d["clima"] is not None:
        cl = d["clima"].merge(usina_l[["cod_usina", "id_usina"]], on="cod_usina")
        radiacao = cl.set_index(["id_usina", "data_hora"])["radiacao_wm2"]

    # 3. regras na ORIGEM
    tab_med = f"{ORIGEM}.medicao_geracao"
    res_origem = (regras_cadastro(usina, d["fonte_energia"], d["submercado"])
                  + regras_parada(par, usina["id_usina"])
                  + regras_medicao(med, usina_l, ids_validos, par_l, solares, cfg_q, tab_med, radiacao))
    if d["pld"] is not None:
        res_origem += regras_pld(d["pld"])
    if d["clima"] is not None:
        res_origem += regras_clima(d["clima"], usina_l["cod_usina"])

    # 4. limpeza da medição
    pot = usina_l.set_index("id_usina")["potencia_mw"]
    med_c, descartadas, conflitantes = corrigir_medicao(med, pot, de_para)
    regras_q = [x for x in regras_medicao(med_c, usina_l, ids_validos, par_l, solares, cfg_q, tab_med, radiacao)
                if x.regra in REGRAS_QUARENTENA_MEDICAO]
    flags = {
        "flag_outlier": r.outliers_iqr(med_c, tab_med, "energia_mwh", "id_usina"),
        "flag_atraso": r.atraso_chegada(med_c, tab_med, "data_hora", "recebido_em",
                                        cfg_q["limite_atraso_horas"]),
        "flag_recebido_antes": r.ordem_temporal(med_c, tab_med, "data_hora", "recebido_em"),
    }
    med_l, med_q = separar(med_c, regras_q, flags)
    med_q = pd.concat([med_q, conflitantes])

    # 5. regras de novo na LIMPA (prova de que a limpeza funcionou)
    tab_l = "qualidade.medicao_geracao_limpa"
    res_limpa = regras_medicao(med_l, usina_l, ids_validos, par_l, solares, cfg_q, tab_l, radiacao)
    res_limpa += regras_cadastro(usina_l, d["fonte_energia"], d["submercado"], "qualidade.usina_limpa")

    # 6. gravar tudo
    metr = gravar_metricas(engine, res_origem + res_limpa, agora)
    with engine.begin() as con:
        con.execute(text("truncate table qualidade.decisoes"))
    pd.DataFrame([(k, v[0], v[1]) for k, v in DECISOES.items()],
                 columns=["regra", "decisao", "justificativa"]).to_sql(
        "decisoes", engine, schema="qualidade", if_exists="append", index=False)
    gravar(engine, usina_l, "usina_limpa")
    gravar(engine, usina_q, "usina_quarentena")
    gravar(engine, par_l, "parada_usina_limpa")
    gravar(engine, par_q, "parada_usina_quarentena")
    gravar(engine, med_l, "medicao_geracao_limpa")
    gravar(engine, med_q, "medicao_geracao_quarentena")

    pld_l = None
    if d["pld"] is not None:                 # PLD limpo = tratado menos quarentena
        q = r.pld_fora_dos_limites(d["pld"]).falhas.index
        pld_l = d["pld"].drop(index=q)
        with engine.begin() as con:
            con.execute(text("create table if not exists qualidade.pld_horario_limpo "
                             "(like extracao.pld_horario)"))
        gravar(engine, pld_l, "pld_horario_limpo")
    if d["clima"] is not None:
        q = set()
        for x in regras_clima(d["clima"], usina_l["cod_usina"]):
            if x.regra.startswith(("clima_", "fk_", "duplicado")):
                q |= set(x.falhas.index)
        with engine.begin() as con:
            con.execute(text("create table if not exists qualidade.clima_horario_limpo "
                             "(like extracao.clima_horario)"))
        gravar(engine, d["clima"].drop(index=list(q)), "clima_horario_limpo")

    # 7. antes x depois (mesmo cadastro limpo nos dois lados; receita só 2025)
    pld_2025 = pld_l[pld_l["data_hora"].dt.year == 2025] if pld_l is not None else None
    ad = comparar(indicadores(med, usina_l, pld_2025), indicadores(med_l, usina_l, pld_2025))
    ad.assign(data_execucao=agora).to_sql("antes_depois", engine, schema="qualidade",
                                          if_exists="append", index=False)

    # 8. conferência e resumo
    destino = {"origem": len(med), "limpa": len(med_l), "quarentena": len(med_q),
               "descartadas (cópia exata)": len(descartadas)}
    assert destino["origem"] == len(med_l) + len(med_q) + len(descartadas), "conta não fecha!"
    escrever_resumo(metr, destino, ad, RAIZ / "docs" / "resultado_qualidade.md")
    if d["pld"] is not None and d["pld"].empty:
        print("AVISO: extracao.pld_horario está vazia (CCEE bloqueada?). "
              "Qualidade do PLD registrada como 100% faltante; receita não calculada.")
    print(resumo(res_origem).query("registros_falha > 0").to_string(index=False))
    print("\nDestino das linhas da medição:", destino)
    print(ad[ad["recorte"] == "total"].to_string(index=False))


if __name__ == "__main__":
    main()
