import time

from psycopg2.extras import Json, execute_values

from utils import ler_config, conectar, abrir_log, fechar_log, buscar

LAT_MAX_BRASIL = 5.3
HORAS_ANO = 8760


def usinas_para_extrair(conn):
    # uma por coordenada; latitude positiva e corrigida so no pedido
    with conn.cursor() as cur:
        cur.execute("select cod_usina, latitude, longitude "
                    "from campo_real_energia.usina order by cod_usina")
        linhas = cur.fetchall()
    vistas, saida, avisos = set(), [], []
    for cod, lat, lon in linhas:
        lat, lon = float(lat), float(lon)
        if lat > LAT_MAX_BRASIL:
            avisos.append(f"{cod}: latitude {lat} invertida para {-lat}")
            lat = -lat
        if (lat, lon) in vistas:
            avisos.append(f"{cod}: coordenada repetida, ignorada")
            continue
        vistas.add((lat, lon))
        saida.append((cod, lat, lon))
    return saida, avisos


def ja_extraida(conn, cod):
    # evita baixar de novo o que ja esta gravado
    with conn.cursor() as cur:
        cur.execute("select count(*) from extracao.clima_horario "
                    "where cod_usina = %s", (cod,))
        return cur.fetchone()[0] >= HORAS_ANO


def extrair_usina(conn, cfg, cod, lat, lon):
    # grava raw e tratada; devolve (lidas, gravadas, aviso)
    om = cfg["open_meteo"]
    params = {"latitude": lat, "longitude": lon,
              "start_date": "2025-01-01", "end_date": "2025-12-31",
              "hourly": om["variaveis"], "timezone": om["timezone"],
              "wind_speed_unit": "ms"}
    r = buscar(om["url"], params, cfg)
    dados = r.json()
    hourly = dados.get("hourly") or {}
    horas = hourly.get("time") or []
    if not horas:
        return 0, 0, f"{cod}: resposta vazia"
    faltando = [v for v in om["variaveis"].split(",") if v not in hourly]
    aviso = f"{cod}: colunas ausentes {faltando}" if faltando else None

    def serie(nome):
        return hourly.get(nome) or [None] * len(horas)

    temp, chuva, rad = serie("temperature_2m"), serie("precipitation"), serie("shortwave_radiation")
    v10, v100 = serie("wind_speed_10m"), serie("wind_speed_100m")
    with conn.cursor() as cur:
        cur.execute("insert into extracao.raw_clima (cod_usina, origem, payload) "
                    "values (%s, %s, %s) returning id_raw", (cod, r.url, Json(dados)))
        id_raw = cur.fetchone()[0]
        linhas = [(cod, horas[i], temp[i], rad[i], v10[i], v100[i], chuva[i], id_raw)
                  for i in range(len(horas))]
        execute_values(
            cur,
            "insert into extracao.clima_horario (cod_usina, data_hora, temperatura_c, "
            "radiacao_wm2, vento_10m_ms, vento_100m_ms, chuva_mm, id_raw) values %s "
            "on conflict do nothing", linhas, page_size=10000)
        gravadas = cur.rowcount
    conn.commit()
    return len(horas), gravadas, aviso


def main():
    cfg = ler_config()
    conn = conectar(cfg)
    id_log = abrir_log(conn, "extracao_clima", "open-meteo")
    lidas = gravadas = 0
    avisos = []
    try:
        usinas, avisos = usinas_para_extrair(conn)
        for cod, lat, lon in usinas:
            if ja_extraida(conn, cod):
                avisos.append(f"{cod}: ja extraida, pulada")
                continue
            n_lidas, n_grav, aviso = extrair_usina(conn, cfg, cod, lat, lon)
            lidas += n_lidas
            gravadas += n_grav
            if aviso:
                avisos.append(aviso)
            print(cod, n_lidas, n_grav)
            time.sleep(1)
        status = "ok_com_avisos" if avisos else "ok"
        fechar_log(conn, id_log, lidas, gravadas, status, "; ".join(avisos) or None)
    except Exception as e:
        conn.rollback()
        fechar_log(conn, id_log, lidas, gravadas, "erro", str(e))
        raise


if __name__ == "__main__":
    main()