"""Indicadores de negócio calculados antes e depois da limpeza."""
import pandas as pd

HORAS_2025 = 8760


def indicadores(med, usina, pld=None):
    u = usina[["id_usina", "cod_usina", "potencia_mw", "cod_submercado"]]
    m = med.dropna(subset=["energia_mwh"]).merge(u, on="id_usina", how="left")
    out = [("registros", "total", len(med)),
           ("geracao_mwh", "total", m["energia_mwh"].sum())]

    por_usina = m.groupby("cod_usina")["energia_mwh"].sum()
    out += [("geracao_mwh", f"usina {k}", v) for k, v in por_usina.items()]
    por_mes = m.groupby(m["data_hora"].dt.strftime("%Y-%m"))["energia_mwh"].sum()
    out += [("geracao_mwh", f"mes {k}", v) for k, v in por_mes.items()]
    fc = 100 * por_usina / (u.set_index("cod_usina")["potencia_mw"].astype(float) * HORAS_2025)
    out += [("fator_capacidade_pct", f"usina {k}", v) for k, v in fc.dropna().items()]

    if pld is not None and len(pld):   # receita = geração da hora x PLD da hora no submercado
        mp = m.merge(pld[["data_hora", "cod_submercado", "pld_rs_mwh"]],
                     on=["data_hora", "cod_submercado"], how="inner")
        receita = mp["energia_mwh"].astype(float) * mp["pld_rs_mwh"].astype(float)
        out.append(("receita_rs", "total", receita.sum()))
        out += [("receita_rs", f"usina {k}", v)
                for k, v in receita.groupby(mp["cod_usina"]).sum().items()]
    return pd.DataFrame(out, columns=["indicador", "recorte", "valor"])


def comparar(antes, depois):
    c = antes.merge(depois, on=["indicador", "recorte"], how="outer", suffixes=("_antes", "_depois"))
    c[["valor_antes", "valor_depois"]] = c[["valor_antes", "valor_depois"]].astype(float).round(3)
    c["diferenca"] = (c["valor_depois"] - c["valor_antes"]).round(3)
    base = c["valor_antes"].where(c["valor_antes"] != 0)
    c["diferenca_pct"] = (100 * c["diferenca"] / base).round(2)
    return c
