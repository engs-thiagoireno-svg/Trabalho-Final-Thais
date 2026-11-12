"""Profiling genérico: uma linha por coluna de qualquer DataFrame."""
import pandas as pd


def perfil(df: pd.DataFrame, nome_tabela: str, top_n: int = 5) -> pd.DataFrame:
    total = len(df)
    linhas = []
    for col in df.columns:
        s = df[col]
        v = s.dropna()
        eh_texto = not (pd.api.types.is_numeric_dtype(s) or pd.api.types.is_datetime64_any_dtype(s))
        texto = v.astype(str).str.strip() if eh_texto else None
        info = {
            "tabela": nome_tabela, "coluna": col, "tipo": str(s.dtype), "total": total,
            "nulos": int(s.isna().sum()),
            "vazios": int((texto == "").sum()) if texto is not None else 0,
            "pct_nulos": round(100 * s.isna().mean(), 2) if total else 0.0,
            "distintos": int(v.nunique()),
            "minimo": None, "maximo": None, "distribuicao": None,
        }
        if len(v) and pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
            q = v.quantile([0.25, 0.5, 0.75])
            info.update(minimo=v.min(), maximo=v.max(),
                        distribuicao=f"média={v.mean():.2f} p25={q[0.25]:.2f} "
                                     f"p50={q[0.5]:.2f} p75={q[0.75]:.2f}")
        elif len(v) and (pd.api.types.is_datetime64_any_dtype(s) or col.startswith("data")):
            info.update(minimo=v.min(), maximo=v.max())
        elif len(v):
            top = v.astype(str).value_counts().head(top_n)
            info["distribuicao"] = "; ".join(f"{k}={n}" for k, n in top.items())
        linhas.append(info)
    out = pd.DataFrame(linhas)
    out[["minimo", "maximo"]] = out[["minimo", "maximo"]].astype(str)
    return out
