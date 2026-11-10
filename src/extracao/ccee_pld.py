"""Extrator do PLD horario (CCEE, API CKAN datastore_search).

Fluxo, por resource_id (um por ano):
  1. busca a primeira pagina e le o "total" informado pela API;
  2. se a resposta veio vazia, registra status 'vazio' e segue;
  3. se o raw ja tem esse total de registros, nao baixa de novo (use --forcar para ignorar);
  4. senao, apaga o raw daquele resource e baixa todas as paginas (limit/offset),
     gravando cada registro como chegou (raw_pld, jsonb) e a versao tratada
     (pld_horario, com upsert);
  5. tudo de um resource acontece em uma transacao: se falhar no meio, volta ao que era antes.

Uso:
    python src/extracao/ccee_pld.py
    python src/extracao/ccee_pld.py --forcar
"""
import sys
import time
from datetime import datetime

from psycopg2.extras import Json, execute_values

from utils import ler_config, conectar, abrir_log, fechar_log, buscar

COLUNAS_ESPERADAS = {"MES_REFERENCIA", "SUBMERCADO", "PERIODO_COMERCIALIZACAO",
                     "DIA", "HORA", "PLD_HORA"}
COLUNAS_ESSENCIAIS = {"MES_REFERENCIA", "SUBMERCADO", "DIA", "HORA", "PLD_HORA"}
SUBMERCADOS = {"SUDESTE": "SE", "SUL": "S", "NORDESTE": "NE", "NORTE": "N",
               "SE": "SE", "S": "S", "NE": "NE", "N": "N"}
PAUSA_ENTRE_PAGINAS = 0.5  # segundos; evita chamadas em rajada


def tratar_registro(rec):
    """Converte 1 registro da CCEE em (data_hora, cod_submercado, pld).

    Levanta ValueError (ou TypeError/KeyError) se o registro nao for aproveitavel.
    """
    mes = str(rec["MES_REFERENCIA"]).strip()
    if len(mes) != 6 or not mes.isdigit():
        raise ValueError(f"MES_REFERENCIA invalido: {mes!r}")
    dia = int(rec["DIA"])
    hora = int(rec["HORA"])
    if not 0 <= hora <= 23:
        raise ValueError(f"HORA fora de 0-23: {hora}")
    data_hora = datetime(int(mes[:4]), int(mes[4:]), dia, hora)

    sub = SUBMERCADOS.get(str(rec["SUBMERCADO"]).strip().upper())
    if sub is None:
        raise ValueError(f"SUBMERCADO desconhecido: {rec['SUBMERCADO']!r}")

    bruto = rec["PLD_HORA"]
    if bruto is None or str(bruto).strip() == "":
        raise ValueError("PLD_HORA vazio")
    texto = str(bruto).strip()
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    return data_hora, sub, float(texto)


def buscar_pagina(cfg, rid, offset):
    c = cfg["ccee"]
    params = {"resource_id": rid, "limit": int(c["limite"]),
              "offset": offset, "sort": "_id asc"}  # ordem fixa entre as paginas
    corpo = buscar(c["url"], params, cfg).json()
    if not corpo.get("success"):
        raise RuntimeError(f"API respondeu success=false: {corpo.get('error')}")
    res = corpo["result"]
    return int(res.get("total", 0)), res.get("records", [])


def checar_colunas(registros, rid, out):
    """Compara as colunas recebidas com as esperadas. Retorna False se faltar coluna essencial."""
    recebidas = set(registros[0].keys()) - {"_id"}
    faltando = COLUNAS_ESPERADAS - recebidas
    novas = recebidas - COLUNAS_ESPERADAS
    if faltando or novas:
        out["avisos"].append(
            f"{rid}: colunas diferentes do esperado (faltando={sorted(faltando)}, "
            f"novas={sorted(novas)})")
    if COLUNAS_ESSENCIAIS - recebidas:
        out["avisos"].append(
            f"{rid}: coluna essencial ausente; raw guardado, tratada NAO gerada")
        return False
    return True


def gravar_pagina(conn, cfg, rid, offset, registros, out, tratar):
    """Grava a pagina no raw e, se possivel, no tratado. Atualiza os contadores em 'out'."""
    origem = cfg["ccee"]["url"]
    with conn.cursor() as cur:
        ids = execute_values(
            cur,
            "insert into extracao.raw_pld (origem, resource_id, pagina_offset, payload) "
            "values %s returning id_raw",
            [(origem, rid, offset, Json(r)) for r in registros],
            page_size=len(registros), fetch=True)
    if not tratar:
        return

    tratadas = {}
    for (id_raw,), rec in zip(ids, registros):
        try:
            data_hora, sub, pld = tratar_registro(rec)
        except (ValueError, TypeError, KeyError) as e:
            out["descartados"] += 1
            if len(out["exemplos"]) < 3:
                out["exemplos"].append(f"{e} (id_raw={id_raw})")
            continue
        chave = (data_hora, sub)
        if chave in tratadas:
            out["duplicados"] += 1
        tratadas[chave] = (data_hora, sub, pld, id_raw)  # a ultima ocorrencia vale

    if tratadas:
        with conn.cursor() as cur:
            execute_values(
                cur,
                "insert into extracao.pld_horario (data_hora, cod_submercado, pld_rs_mwh, id_raw) "
                "values %s "
                "on conflict (data_hora, cod_submercado) do update set "
                "pld_rs_mwh = excluded.pld_rs_mwh, id_raw = excluded.id_raw",
                list(tratadas.values()), page_size=1000)
        out["gravadas"] += len(tratadas)


def extrair_resource(conn, cfg, rid, forcar=False):
    limite = int(cfg["ccee"]["limite"])
    out = {"lidas": 0, "gravadas": 0, "descartados": 0, "duplicados": 0,
           "status": "ok", "avisos": [], "exemplos": [], "info": []}

    total, registros = buscar_pagina(cfg, rid, 0)
    if total == 0 or not registros:
        out["status"] = "vazio"
        out["avisos"].append(f"{rid}: resposta vazia (mes ainda nao publicado?)")
        return out

    with conn.cursor() as cur:
        cur.execute("select count(*) from extracao.raw_pld where resource_id = %s", (rid,))
        existentes = cur.fetchone()[0]
    if existentes == total and not forcar:
        conn.rollback()
        out["status"] = "ja_extraido"
        out["info"].append(f"{rid}: raw ja tem {total} registros; nada a baixar")
        return out

    print(f"  {rid}: total informado = {total}")
    try:
        with conn.cursor() as cur:  # recarga completa do resource, na mesma transacao
            cur.execute("delete from extracao.raw_pld where resource_id = %s", (rid,))
        tratar = checar_colunas(registros, rid, out)
        offset = 0
        while True:
            if offset > 0:
                _, registros = buscar_pagina(cfg, rid, offset)
                if not registros:
                    out["avisos"].append(
                        f"{rid}: pagina vazia no offset {offset}, antes de chegar ao total {total}")
                    break
            gravar_pagina(conn, cfg, rid, offset, registros, out, tratar)
            out["lidas"] += len(registros)
            print(f"    offset {offset}: {len(registros)} registros")
            offset += limite
            if offset >= total:
                break
            time.sleep(PAUSA_ENTRE_PAGINAS)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    if out["lidas"] < total:
        out["avisos"].append(f"{rid}: leu {out['lidas']} de {total} registros")
    if out["descartados"]:
        out["avisos"].append(
            f"{rid}: {out['descartados']} registros descartados da tratada "
            f"(ex.: {'; '.join(out['exemplos'])})")
    if out["duplicados"]:
        out["avisos"].append(f"{rid}: {out['duplicados']} chaves repetidas na mesma pagina")
    return out


def definir_status(resultados, erros):
    bons = [r for r in resultados if r["status"] in ("ok", "ja_extraido")]
    vazios = [r for r in resultados if r["status"] == "vazio"]
    avisos = any(r["avisos"] for r in resultados)
    if erros:
        return "parcial" if bons else "erro"
    if not bons:
        return "vazio"
    if vazios or avisos:
        return "ok_com_avisos"
    return "ok"


def main():
    forcar = "--forcar" in sys.argv
    cfg = ler_config()
    conn = conectar(cfg)
    id_log = abrir_log(conn, "extracao_pld", "ccee")
    resources = sorted((k, v) for k, v in cfg["ccee"].items() if k.startswith("resource_id_"))

    resultados, erros = [], []
    try:
        for chave, rid in resources:
            print(f"Extraindo {chave} ...")
            try:
                resultados.append(extrair_resource(conn, cfg, rid, forcar))
            except Exception as e:  # segue para o proximo sem perder o que ja foi gravado
                conn.rollback()
                erros.append(f"{rid}: {e}")
                print(f"  ERRO: {e}")

        status = definir_status(resultados, erros)
        lidas = sum(r["lidas"] for r in resultados)
        gravadas = sum(r["gravadas"] for r in resultados)
        mensagens = erros + [a for r in resultados for a in r["avisos"]]
        texto = " | ".join(mensagens)[:2000] or None
        fechar_log(conn, id_log, lidas, gravadas, status, texto)
    except Exception as e:
        conn.rollback()
        fechar_log(conn, id_log, 0, 0, "erro", str(e)[:2000])
        raise
    finally:
        conn.close()

    for r in resultados:
        for i in r["info"]:
            print(i)
    print(f"Status: {status} | lidas={lidas} gravadas={gravadas}")
    if texto:
        print(f"Avisos/erros: {texto}")


if __name__ == "__main__":
    main()