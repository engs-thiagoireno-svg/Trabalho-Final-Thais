import configparser
import time
from datetime import datetime

import psycopg2
import requests


def ler_config(caminho="config/config.ini"):
    cfg = configparser.ConfigParser()
    cfg.read(caminho, encoding="utf-8")
    return cfg


def conectar(cfg):
    b = cfg["banco"]
    return psycopg2.connect(host=b["host"], port=b["porta"], dbname=b["banco"],
                            user=b["usuario"], password=b["senha"])


def abrir_log(conn, processo, fonte):
    with conn.cursor() as cur:
        cur.execute(
            "insert into extracao.log_extracao (processo, fonte, inicio, status) "
            "values (%s, %s, %s, 'em_execucao') returning id_log",
            (processo, fonte, datetime.now()))
        id_log = cur.fetchone()[0]
    conn.commit()
    return id_log


def fechar_log(conn, id_log, lidas, gravadas, status, erro=None):
    with conn.cursor() as cur:
        cur.execute(
            "update extracao.log_extracao set fim = %s, linhas_lidas = %s, "
            "linhas_gravadas = %s, status = %s, erro = %s where id_log = %s",
            (datetime.now(), lidas, gravadas, status, erro, id_log))
    conn.commit()


def buscar(url, params, cfg, headers=None):
    req = cfg["requisicoes"]
    tentativas = int(req["tentativas"])
    espera = float(req["espera_inicial"])
    ultimo_erro = None
    for _ in range(tentativas):
        try:
            r = requests.get(url, params=params, headers=headers,
                             timeout=int(req["timeout"]))
            if r.status_code == 429:
                ultimo_erro = "http 429"
                espera = max(espera, float(r.headers.get("Retry-After", 0)))
            elif r.status_code >= 500:
                ultimo_erro = f"http {r.status_code}"
            elif r.status_code >= 400:
                raise RuntimeError(f"http {r.status_code}")
            else:
                return r
        except requests.exceptions.RequestException as e:
            ultimo_erro = str(e)
        time.sleep(espera)
        espera *= 2
    raise RuntimeError(f"falhou apos {tentativas} tentativas: {ultimo_erro}")


if __name__ == "__main__":
    cfg = ler_config()
    conn = conectar(cfg)
    id_log = abrir_log(conn, "teste", "utils")
    fechar_log(conn, id_log, 0, 0, "ok")
    print("log gravado, id", id_log)